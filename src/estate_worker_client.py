"""Control-plane side of the ``aoteru-worker/1`` contract (Stage 3:
docs/aoteru-multihost-execution-implementation-plan.md). `call_worker()` is
the only way `src.estate_router` reaches a worker — it never imports
`estate_worker`'s verb functions directly, so execution always crosses the
same transport/attestation seam regardless of whether the routed host
happens to be this process's own host.

`LocalTransport` still subprocesses `python -m src.estate_worker` even for
the local host, rather than calling `estate_worker.handle()` in-process,
because the wire contract (validation, attestation, identity refusal) is
exactly what makes a local route "attested" in the same sense a remote one
is — an in-process shortcut would make `executed_host_id` trustworthy only
by convention, which is the defect this stage closes."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from src.estate_worker_protocol import build_request, validate_response
from src.runtime_paths import get_app_root


class WorkerTransportError(Exception):
    """Raised for any transport, protocol or attestation failure. `.code`
    is always one of the client-side error codes in
    `estate_worker_protocol.ERROR_CODES` (`worker_protocol_error`,
    `worker_unreachable`, `placement_mismatch`) or a worker-reported error
    code echoed straight through."""

    def __init__(self, code: str, message: Optional[str] = None):
        super().__init__(message or code)
        self.code = code


class LocalTransport:
    """Only ever used when the routed host is this process's own host —
    `transport_for_host` refuses to build one otherwise."""

    def send(self, request: dict, *, deadline_s: float) -> dict:
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "src.estate_worker"],
                input=json.dumps(request),
                capture_output=True,
                text=True,
                cwd=str(Path(get_app_root()).resolve()),
                timeout=deadline_s + 15,
            )
        except subprocess.TimeoutExpired as exc:
            raise WorkerTransportError("worker_unreachable", f"local worker timed out: {exc}") from exc
        except OSError as exc:
            raise WorkerTransportError("worker_unreachable", f"local worker failed to start: {exc}") from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip() or f"local worker exited {completed.returncode}"
            raise WorkerTransportError("worker_protocol_error", detail)
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise WorkerTransportError("worker_protocol_error", f"local worker returned invalid JSON: {exc}") from exc
        if not isinstance(response, dict):
            raise WorkerTransportError("worker_protocol_error", "local worker response was not a JSON object")
        return response


class SshTransport:
    """Full implementation lands in Stage 4 (§C.1 of the plan). Constructed
    here so `transport_for_host` has somewhere to route an `ssh`-pinned
    host without a second host-eligibility branch, but every call fails
    truthfully until Stage 4."""

    def __init__(self, host_cfg: dict):
        self.host_cfg = host_cfg

    def send(self, request: dict, *, deadline_s: float) -> dict:
        raise WorkerTransportError("worker_unreachable", "ssh transport lands in stage 4")


def _host_config(host_id: str) -> dict:
    from src import estate_router

    estate = estate_router._load_yaml("estate")
    host_cfg = next((h for h in estate.get("hosts", []) if h.get("id") == host_id), None)
    if host_cfg is None:
        raise WorkerTransportError("placement_mismatch", f"host {host_id!r} is not registered in config/estate.yaml")
    return host_cfg


def transport_for_host(host_id: str):
    """Build the transport for `host_id`, refusing local transport for any
    host other than this process's own current host — a config typo or a
    stale route response must never make this process execute work on
    behalf of a different host under a false local identity."""
    from src import estate_router

    host_cfg = _host_config(host_id)
    transport = (host_cfg.get("worker") or {}).get("transport")
    if transport == "local":
        if host_id != estate_router.current_host_id():
            raise WorkerTransportError(
                "placement_mismatch",
                f"host {host_id!r} is configured for local transport but is not this host",
            )
        return LocalTransport()
    if transport == "ssh":
        return SshTransport(host_cfg)
    raise WorkerTransportError("placement_mismatch", f"host {host_id!r} has no worker transport configured")


def verify_attestation(response: dict, request: dict, host_cfg: dict) -> None:
    """Raise `placement_mismatch` unless the worker's attestation proves it
    is actually the host we routed to, replying to this exact request."""
    attestation = response.get("attestation") or {}
    expected_host = request.get("expected_host_id")
    if attestation.get("host_id") != expected_host:
        raise WorkerTransportError(
            "placement_mismatch",
            f"attested host {attestation.get('host_id')!r} does not match routed host {expected_host!r}",
        )
    if attestation.get("nonce") != request.get("nonce"):
        raise WorkerTransportError("placement_mismatch", "attestation nonce does not match request")
    pinned_fingerprint = (host_cfg.get("worker") or {}).get("machine_fingerprint")
    if pinned_fingerprint and attestation.get("machine_fingerprint") != pinned_fingerprint:
        raise WorkerTransportError(
            "placement_mismatch",
            f"attested machine_fingerprint does not match the fingerprint pinned for {expected_host!r}",
        )


def call_worker(host_id: str, verb: str, payload: dict, *, deadline_s: float) -> dict:
    """Build one `aoteru-worker/1` request, send it over the transport
    pinned to `host_id` in config/estate.yaml, validate the response
    envelope, and verify its attestation. Raises `WorkerTransportError` on
    any failure — transport, protocol, worker-reported error, or
    attestation mismatch — so callers never get a result that silently
    came from the wrong place."""
    host_cfg = _host_config(host_id)
    transport = transport_for_host(host_id)
    request = build_request(verb, host_id, payload, deadline_s)
    response = transport.send(request, deadline_s=deadline_s)
    valid, error = validate_response(response, request)
    if not valid:
        raise WorkerTransportError(error["code"], error["message"])
    verify_attestation(response, request, host_cfg)
    if not response.get("ok"):
        err = response.get("error") or {}
        raise WorkerTransportError(err.get("code", "execution_failed"), err.get("message"))
    return response


_HEALTH_TTL_S = 30.0
_INVENTORY_TTL_S = 60.0
_health_cache: dict[str, tuple[float, dict]] = {}
_inventory_cache: dict[tuple, tuple[float, dict]] = {}


def clear_caches() -> None:
    """Test-only reset of the in-memory TTL caches. Never persisted —
    live health/inventory is explicitly not a new database table (plan
    §D: 'Nothing about health or inventory is persisted in a new table')."""
    _health_cache.clear()
    _inventory_cache.clear()


def worker_health(host_id: str, *, deadline_s: float = 20.0) -> dict:
    now = time.monotonic()
    cached = _health_cache.get(host_id)
    if cached is not None and now - cached[0] < _HEALTH_TTL_S:
        return cached[1]
    response = call_worker(host_id, "health", {}, deadline_s=deadline_s)
    result = response["result"]
    _health_cache[host_id] = (now, result)
    return result


def worker_inventory(host_id: str, models_of_interest: Optional[list[str]] = None, *, deadline_s: float = 30.0) -> dict:
    key = (host_id, tuple(sorted(models_of_interest or [])))
    now = time.monotonic()
    cached = _inventory_cache.get(key)
    if cached is not None and now - cached[0] < _INVENTORY_TTL_S:
        return cached[1]
    response = call_worker(
        host_id, "inventory", {"models_of_interest": list(models_of_interest or [])}, deadline_s=deadline_s,
    )
    result = response["result"]
    _inventory_cache[key] = (now, result)
    return result

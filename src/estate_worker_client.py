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
import os
import subprocess
import sys
import tempfile
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
    code echoed straight through.

    `.observed_host_id` (pre-Stage-6 review finding) carries the actual
    `attestation.host_id` a `placement_mismatch` was raised against, when
    one was observed -- otherwise `str(exc)` is the only place that
    identity lived, and a caller building routing telemetry (`actual_route
    = "placement_mismatch:<observed-host>"`) had no structured field to
    read it from. Not a widening of the worker protocol: this is a
    client-side exception attribute, never sent or received on the wire.
    A plain transport failure (no attestation observed at all) leaves it
    `None`, same as before this attribute existed."""

    def __init__(self, code: str, message: Optional[str] = None, *, observed_host_id: Optional[str] = None):
        super().__init__(message or code)
        self.code = code
        self.observed_host_id = observed_host_id


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
    """§C.1 of the plan: a pinned-host-key, forced-command SSH transport.
    No remote command argument is ever sent -- the home
    `authorized_keys` entry pins the actual command
    (`python -m src.estate_worker --root <checkout>`), so this transport
    only has to get the JSON request onto stdin and the JSON response
    off stdout. `StrictHostKeyChecking=no` is forbidden and this
    deliberately does not reuse `routes/shell_routes.py:_ssh_base_argv`,
    which allows it."""

    def __init__(self, host_cfg: dict):
        self.host_cfg = host_cfg

    def send(self, request: dict, *, deadline_s: float) -> dict:
        host_id = self.host_cfg.get("id")
        ssh_cfg = (self.host_cfg.get("worker") or {}).get("ssh") or {}
        host_public_key = ssh_cfg.get("host_public_key")
        target = ssh_cfg.get("target")
        if not host_public_key:
            raise WorkerTransportError(
                "host_key_unpinned", f"{host_id!r} has no worker.ssh.host_public_key pinned",
            )
        if not target:
            raise WorkerTransportError("worker_unreachable", f"{host_id!r} has no worker.ssh.target configured")
        key_path = Path.home() / ".aoteru" / "worker_ssh_key"
        if not key_path.exists():
            raise WorkerTransportError("worker_unreachable", f"no local SSH key at {key_path}")

        host_part = target.rsplit("@", 1)[-1].split(":", 1)[0]
        known_hosts = tempfile.NamedTemporaryFile(
            mode="w", prefix="aoteru-worker-known-hosts-", delete=False, encoding="utf-8",
        )
        try:
            known_hosts.write(f"{host_part} {host_public_key}\n")
            known_hosts.close()
            argv = [
                "ssh",
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=yes",
                "-o", f"UserKnownHostsFile={known_hosts.name}",
                "-o", "ConnectTimeout=6",
                "-o", "ServerAliveInterval=15",
                "-o", "ServerAliveCountMax=2",
                "-i", str(key_path),
                target,
            ]
            try:
                completed = subprocess.run(
                    argv,
                    input=json.dumps(request),
                    capture_output=True,
                    text=True,
                    timeout=deadline_s + 15,
                )
            except subprocess.TimeoutExpired as exc:
                raise WorkerTransportError("worker_unreachable", f"ssh worker timed out: {exc}") from exc
            except OSError as exc:
                raise WorkerTransportError("worker_unreachable", f"ssh failed to start: {exc}") from exc
        finally:
            try:
                os.unlink(known_hosts.name)
            except OSError:
                pass

        if completed.returncode != 0:
            detail = completed.stderr.strip() or f"ssh exited {completed.returncode}"
            raise WorkerTransportError("worker_protocol_error", detail)
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise WorkerTransportError("worker_protocol_error", f"ssh worker returned invalid JSON: {exc}") from exc
        if not isinstance(response, dict):
            raise WorkerTransportError("worker_protocol_error", "ssh worker response was not a JSON object")
        return response


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
    is actually the host we routed to, replying to this exact request.

    Every raise here carries `observed_host_id` = the attested
    `host_id` actually reported (pre-Stage-6 review finding) -- the
    identity a caller needs to diagnose *which* host answered wrongly,
    without this function ever treating that host as having executed
    anything.

    The nonce check below is the real classification for a nonce
    mismatch (Stage 3 contract fix): `estate_worker_protocol.
    validate_response()` only checks the attestation nonce is a
    non-empty string (envelope shape), never that it equals the
    request's — that equality/replay-correlation question is an
    attestation/identity concern, so `call_worker()` always reaches this
    function for it and a mismatch is correctly `placement_mismatch`,
    not `worker_protocol_error`."""
    attestation = response.get("attestation") or {}
    observed_host_id = attestation.get("host_id")
    expected_host = request.get("expected_host_id")
    if observed_host_id != expected_host:
        raise WorkerTransportError(
            "placement_mismatch",
            f"attested host {observed_host_id!r} does not match routed host {expected_host!r}",
            observed_host_id=observed_host_id,
        )
    if attestation.get("nonce") != request.get("nonce"):
        raise WorkerTransportError(
            "placement_mismatch", "attestation nonce does not match request",
            observed_host_id=observed_host_id,
        )
    pinned_fingerprint = (host_cfg.get("worker") or {}).get("machine_fingerprint")
    if pinned_fingerprint and attestation.get("machine_fingerprint") != pinned_fingerprint:
        raise WorkerTransportError(
            "placement_mismatch",
            f"attested machine_fingerprint does not match the fingerprint pinned for {expected_host!r}",
            observed_host_id=observed_host_id,
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
_REPO_PROBE_TTL_S = 30.0
_health_cache: dict[str, tuple[float, dict]] = {}
_inventory_cache: dict[tuple, tuple[float, dict]] = {}
_repo_probe_cache: dict[tuple, tuple[float, dict]] = {}


def clear_caches() -> None:
    """Test-only reset of the in-memory TTL caches. Never persisted —
    live health/inventory is explicitly not a new database table (plan
    §D: 'Nothing about health or inventory is persisted in a new table')."""
    _health_cache.clear()
    _inventory_cache.clear()
    _repo_probe_cache.clear()


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


def worker_repo_probe(host_id: str, repo_id: str, *, deadline_s: float = 15.0) -> dict:
    """Worker-attested truth about whether `repo_id` resolves on
    `host_id` — used by `estate_router.eligible_hosts()` to add repo
    locality to host selection (Stage 5 review finding: a host was never
    excluded merely for lacking the repo). Never derived from the
    control-plane's own checkout or from config alone."""
    key = (host_id, repo_id)
    now = time.monotonic()
    cached = _repo_probe_cache.get(key)
    if cached is not None and now - cached[0] < _REPO_PROBE_TTL_S:
        return cached[1]
    response = call_worker(host_id, "repo.probe", {"repo_id": repo_id}, deadline_s=deadline_s)
    result = response["result"]
    _repo_probe_cache[key] = (now, result)
    return result

"""Stateless host-local worker for the ``aoteru-worker/1`` contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import estate_router, estate_worker_procs, worktree_ops
from src.estate_worker_protocol import PROTOCOL, error_response, validate_request
from src.park_lease_ops import git_is_clean
from src.runtime_paths import get_app_root


_OLLAMA_BASE = os.getenv("AOTERU_WORKER_OLLAMA_BASE", "http://127.0.0.1:11434").rstrip("/")
_SPOOL_ROOT = Path.home() / ".aoteru" / "worker-spool"
_PREPARE_ROOT = Path.home() / ".aoteru" / "worker-prepare"
_SPOOL_TTL_SECONDS = 7 * 24 * 60 * 60
_TERMINAL_STATES = frozenset({"succeeded", "failed", "timed_out"})
# No dots (6c adjudication finding 5): an id is embedded in a systemd unit
# name, and a suffix such as ".service" must never be formable.
_EXECUTION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_WORKER_CAPABILITIES_PATH = Path.home() / ".aoteru" / "worker_capabilities.json"
_WORKER_SELFTEST_SENTINEL_PATH = Path.home() / ".aoteru" / "worker_selftest_enabled"


def _selftest_spawn_delay(payload: dict) -> None:
    """Plan §G I6(b): a self-test-only delay between the start claim and the
    spawn, read from the operator's sentinel file (JSON `{"spawn_delay_s":
    N}`) and honoured only for the `noop-sleep` kind while the sentinel
    exists. Never affects codex-write."""
    if payload.get("kind") != "noop-sleep" or not _selftest_enabled():
        return
    try:
        delay = float(json.loads(_WORKER_SELFTEST_SENTINEL_PATH.read_text() or "{}").get("spawn_delay_s", 0))
    except (OSError, ValueError, AttributeError):
        return
    time.sleep(max(0.0, min(delay, 30.0)))


def _selftest_enabled() -> bool:
    """Whether the operator has manually enabled the bounded `noop-sleep`
    self-test gate (Stage 4 review finding). A sentinel file, not an
    environment variable: `SshTransport` opens a fresh forced-command SSH
    session for every `call_worker()` call, so an env var set in one
    interactive session (the runbook's old mechanism) is never visible to
    the `start` call's own session, let alone the detached spooled
    process that call spawns. A file under `~/.aoteru/` is visible to
    every one of those, is created and removed by hand by the operator
    (never by any routing code path), and only ever gates `noop-sleep` —
    never `codex-write`, which has its own, unrelated authority checks."""
    return _WORKER_SELFTEST_SENTINEL_PATH.is_file()


class WorkerError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _json_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    try:
        temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _detached_spawn_verified() -> bool:
    """Whether this worker's process layer has actually proven it can
    outlive its launching session, gating `codex-write` eligibility
    (Stage 4). Linux's `spawn_detached` (`start_new_session=True`) has
    no session-scoped job object to be refused by, so it's proven by
    construction. Windows's breakaway flags can be silently refused by
    the sshd job (docs/aoteru-home-worker-setup.md step 7), so there the
    flag file is the only evidence -- written once, manually, by that
    live survival check, never by any code path that routes work."""
    if os.name != "nt":
        return True
    return bool(_json_read(_WORKER_CAPABILITIES_PATH).get("detached_spawn_verified"))


def _spool_path(execution_id: str) -> Path:
    if not isinstance(execution_id, str) or not _EXECUTION_ID_RE.fullmatch(execution_id):
        raise WorkerError("bad_request", "execution_id contains unsupported characters")
    return _SPOOL_ROOT / execution_id


def _gc_spools() -> None:
    """S6.8 retention. Never deletes a spool directory or any decision
    file. Compacts (drops worker.log/result.json, tombstones state.json):
    a write spool only 7 days after the control plane's spool.release; a
    self-test spool 7 days after it became terminal and quiescent. Deletes
    only stale decide_once temp files, which were never decisions."""
    try:
        entries = list(_SPOOL_ROOT.iterdir())
    except OSError:
        return
    for entry in entries:
        if not entry.is_dir():
            continue
        try:
            for temp in entry.glob(".*.tmp-*"):
                age = time.time() - temp.stat().st_mtime
                if age > STARTING_STALE_SECONDS:
                    temp.unlink()
            _compact_if_due(entry)
        except (OSError, WorkerError):
            continue


def _compact_if_due(spool: Path) -> None:
    files = _spool_files(spool)
    claim = read_decision(files["claim"])
    if claim is None or claim.get("kind") != "start":
        return
    telemetry = _json_read(files["state"])
    if telemetry.get("state") == "tombstone":
        return
    kind = (claim.get("request") or {}).get("kind")
    released = read_decision(files["released"])
    if kind in _WRITE_KINDS:
        age = _age_seconds((released or {}).get("released_at"))
        if released is None or age is None or age < SPOOL_COMPACT_AFTER_RELEASE_SECONDS:
            return
    else:
        view = _execution_view(spool)
        if view["state"] not in _TERMINAL_STATES | {"start_failed"} or view["quiescent"] is not True:
            return
        try:
            if time.time() - files["state"].stat().st_mtime < _SPOOL_TTL_SECONDS:
                return
        except OSError:
            return
    original = telemetry.get("state")
    for name in ("log", "result"):
        try:
            files[name].unlink()
        except FileNotFoundError:
            pass
    _json_write(files["state"], {"state": "tombstone", "kind": kind, "original_state": original,
                                 "resolution": (released or {}).get("resolution"), "compacted_at": _utcnow()})


def machine_fingerprint() -> str:
    """Return the non-secret, shortened machine-id digest."""
    machine_id = ""
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            ) as key:
                machine_id = str(winreg.QueryValueEx(key, "MachineGuid")[0]).strip()
        except (OSError, ImportError):
            machine_id = socket.gethostname()
    else:
        try:
            machine_id = Path("/etc/machine-id").read_text(encoding="utf-8").strip()
        except OSError:
            machine_id = socket.gethostname()
    return hashlib.sha256(machine_id.encode("utf-8")).hexdigest()[:16]


def _worker_version() -> str:
    root = Path(estate_router._CONFIG_DIR).parent
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    version = result.stdout.strip()
    return version if result.returncode == 0 and version else "unknown"


def attestation(nonce: str) -> dict:
    return {
        "host_id": estate_router.current_host_id(),
        "hostname": socket.gethostname(),
        "machine_fingerprint": machine_fingerprint(),
        "os": platform.system().lower(),
        "worker_pid": os.getpid(),
        "worker_version": _worker_version(),
        "nonce": nonce,
        "observed_at": _utcnow(),
    }


def _success_response(request: dict, proof: dict, result: dict) -> dict:
    return {
        "protocol": PROTOCOL,
        "request_id": request["request_id"],
        "ok": True,
        "error": None,
        "attestation": proof,
        "result": result,
    }


def handle(request: dict) -> dict:
    """Validate, attest, identity-check and dispatch one worker request."""
    _gc_spools()
    request_for_error = request if isinstance(request, dict) else {"request_id": None, "nonce": ""}
    nonce = request_for_error.get("nonce") if isinstance(request_for_error.get("nonce"), str) else ""
    proof = attestation(nonce)
    valid, validation_error = validate_request(request)
    if not valid:
        return error_response(
            request_for_error,
            validation_error["code"],
            validation_error["message"],
            proof,
        )
    if proof["host_id"] is None:
        return error_response(request, "identity_unregistered", "worker hostname is not registered", proof)
    if request["expected_host_id"] != proof["host_id"]:
        return error_response(
            request,
            "identity_mismatch",
            f"expected host {request['expected_host_id']!r}, worker is {proof['host_id']!r}",
            proof,
        )

    function_name = f"_verb_{request['verb'].replace('.', '_')}"
    verb = globals()[function_name]
    _CURRENT_DEADLINE_S["value"] = request.get("deadline_s")
    # One monotonic budget for the whole verb (gate round 11): every bounded
    # subprocess inside verification is capped by what remains, so the verb
    # always answers before the transport's own limit.
    deadline = request.get("deadline_s") if isinstance(request.get("deadline_s"), (int, float)) else None
    _BUDGET["end"] = (time.monotonic() + float(deadline) - _BUDGET_MARGIN_S) if deadline else None
    if os.name != "nt":
        _disable_git_side_processes(_SPOOL_ROOT)
    try:
        result = verb(request["payload"])
    except WorkerError as exc:
        return error_response(request, exc.code, str(exc), proof)
    except Exception as exc:
        return error_response(request, "execution_failed", str(exc), proof)
    return _success_response(request, proof, result)


def _ollama_inventory() -> tuple[bool, list[dict], str | None]:
    try:
        req = urllib.request.Request(
            f"{_OLLAMA_BASE}/api/tags",
            headers={"User-Agent": "aoteru-worker/1"},
        )
        with urllib.request.urlopen(req, timeout=4) as response:  # noqa: S310
            body = json.loads(response.read().decode("utf-8"))
        models = [
            {"name": model.get("name"), "digest": model.get("digest")}
            for model in body.get("models", [])
            if isinstance(model, dict) and isinstance(model.get("name"), str)
        ]
        return True, models, None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        return False, [], str(exc)


def _in_flight_execution_ids() -> list[str]:
    try:
        entries = list(_SPOOL_ROOT.iterdir())
    except OSError:
        return []
    result = []
    for entry in entries:
        if not entry.is_dir() or not (entry / "claim.json").exists():
            continue
        try:
            if _execution_view(entry)["state"] in {"starting", "running"}:
                result.append(entry.name)
        except WorkerError:
            result.append(entry.name)   # unreadable -> never reported as idle
    return sorted(result)


def _verb_health(payload: dict) -> dict:
    if payload:
        raise WorkerError("bad_request", "health payload must be empty")
    reachable, _models, ollama_error = _ollama_inventory()
    codex_available, codex_detail = estate_router._codex_available()
    gpu_active, gpu_reason = estate_router.experiment_priority_active()
    return {
        "ollama": {"reachable": reachable, "base_url": _OLLAMA_BASE, "error": ollama_error},
        "codex": {"available": codex_available, "detail": codex_detail},
        "gpu_yield": {"active": gpu_active, "reason": gpu_reason},
        "in_flight": _in_flight_execution_ids(),
        "write_prerequisites": _write_prerequisites(),
        "time_utc": _utcnow(),
    }


def _run_git(path: str, args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", "-C", path, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkerError("repo_unavailable", f"git {' '.join(args)} failed: {exc}") from exc


def _probe_repo(repo_id: str) -> dict:
    path = estate_router.resolve_repo_path(repo_id)
    if path is None:
        return {"resolved": False, "path": None, "head_sha": None, "branch": None, "clean": False}
    head = _run_git(path, ["rev-parse", "HEAD"], timeout=15)
    branch = _run_git(path, ["branch", "--show-current"], timeout=15)
    clean, _reason = git_is_clean(path)
    resolved = head.returncode == 0 and branch.returncode == 0
    return {
        "resolved": resolved,
        "path": str(Path(path).resolve()),
        "head_sha": head.stdout.strip() if head.returncode == 0 else None,
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "clean": clean,
    }


def _verb_inventory(payload: dict) -> dict:
    models_of_interest = payload.get("models_of_interest", [])
    if set(payload) - {"models_of_interest"}:
        raise WorkerError("bad_request", "inventory payload has unknown fields")
    if not isinstance(models_of_interest, list) or not all(isinstance(name, str) for name in models_of_interest):
        raise WorkerError("bad_request", "models_of_interest must be a list of strings")
    reachable, models, _error = _ollama_inventory()
    from src.model_context import get_context_length_known
    context = {}
    for model in models_of_interest:
        try:
            length, known = get_context_length_known(_OLLAMA_BASE, model)
        except Exception:
            length, known = 0, False
        context[model] = {"length": length, "known": known}
    codex_available, _detail = estate_router._codex_available()
    registry = estate_router._load_yaml("repositories")
    repos = []
    for entry in registry.get("repos", []):
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            probe = _probe_repo(entry["id"])
            repos.append({
                "repo_id": entry["id"],
                "resolved": probe["resolved"],
                "path": probe["path"],
                "head_sha": probe["head_sha"],
                "clean": probe["clean"],
            })
    from scripts.home_reentry_inventory import _hardware
    return {
        "models": models,
        "context": context,
        "executors": {
            "deterministic": True,
            "local": reachable,
            "codex": codex_available,
            "codex-write": codex_available and _detached_spawn_verified() and _write_prerequisites_ok(),
        },
        "repos": repos,
        "hardware": _hardware(),
    }


def _write_prerequisites_ok() -> bool:
    prerequisites = _write_prerequisites()
    return prerequisites["decision_fs"] and prerequisites["runner_units"]


def _verb_repo_probe(payload: dict) -> dict:
    repo_id = payload.get("repo_id")
    if set(payload) != {"repo_id"} or not isinstance(repo_id, str) or not repo_id:
        raise WorkerError("bad_request", "repo.probe requires repo_id")
    return _probe_repo(repo_id)


def _timeout(payload: dict, default: float) -> float:
    value = payload.get("timeout_s", default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise WorkerError("bad_request", "timeout_s must be a positive number")
    return float(value)


def _verb_execute(payload: dict) -> dict:
    kind = payload.get("kind")
    objective = payload.get("objective")
    if not isinstance(objective, (str, list)):
        raise WorkerError("bad_request", "execute requires a string or multimodal-list objective")
    timeout_s = _timeout(payload, 180.0)
    if kind == "local-inference":
        model = payload.get("model")
        if not isinstance(model, str) or not model:
            raise WorkerError("bad_request", "local-inference requires model")
        result = estate_router.execute_local(model, objective, timeout=timeout_s)
        result.setdefault("provider", "ollama")
        result.setdefault("concrete_model", model)
        return result
    if kind == "codex-readonly":
        if not isinstance(objective, str):
            raise WorkerError("bad_request", "codex-readonly objective must be a string")
        repo_id = payload.get("repo_id")
        cwd = None
        if repo_id is not None:
            if not isinstance(repo_id, str) or not repo_id:
                raise WorkerError("bad_request", "repo_id must be a non-empty string")
            cwd = estate_router.resolve_repo_path(repo_id)
            if cwd is None:
                raise WorkerError("repo_unavailable", f"repo {repo_id!r} does not resolve on this worker")
        result = estate_router.execute_codex(objective, timeout=timeout_s, cwd=cwd)
        result.setdefault("provider", "codex")
        result.setdefault("concrete_model", "codex-cli")
        result.setdefault("retries", 0)
        return result
    raise WorkerError("bad_request", f"unsupported execute kind {kind!r}")


def _worktree_verification(repo_id: Any, worktree_path: Any, branch: Any) -> dict:
    """Worktree-touching verification. Where runner units exist (Linux), the
    git work runs synchronously in its own transient unit so no helper it
    may launch (fsmonitor, filters) can outlive the call (6c adjudication
    finding 2); elsewhere it runs in-process (Windows write verbs are
    refused anyway)."""
    if not all(isinstance(value, str) and value for value in (repo_id, worktree_path, branch)):
        raise WorkerError("bad_request", "worktree verification requires repo_id, worktree_path and branch")
    if _remaining(1.0) <= 0:
        raise _budget_exhausted("before the unit probe")
    units_ok, _detail = estate_worker_procs.runner_units_supported(timeout=_remaining(30.0))
    if units_ok and not _IN_VERIFY_UNIT["value"]:
        scope = _verify_scope(worktree_path)
        # A late verification of the same path is a short read: wait for it
        # (bounded) instead of refusing (gate round 8). The wait, each poll
        # and the unit run are all capped by the verb's single budget, and
        # exhaustion is a retryable, state-free answer (gate round 11).
        wait_until = time.monotonic() + _VERIFY_UNIT_WAIT_S
        reserve = VERIFY_UNIT_TIMEOUT_S + VERIFY_KILL_PROOF_S
        while estate_worker_procs.verify_units_quiescent(scope, timeout=_remaining(15.0)) is not True:
            if time.monotonic() >= wait_until:
                raise WorkerError("executor_unavailable",
                                  "an earlier verification of this worktree is still live or unknown; retryable")
            if _remaining(1e9) <= reserve:
                raise _budget_exhausted("waiting for an earlier verification of this worktree")
            time.sleep(0.2)
        run_limit = min(VERIFY_UNIT_TIMEOUT_S, _remaining(1e9) - VERIFY_KILL_PROOF_S)
        if run_limit < 1.0:
            raise _budget_exhausted("no time left to run the verification unit")
        payload = json.dumps({"repo_id": repo_id, "worktree_path": worktree_path, "branch": branch})
        completed = estate_worker_procs.run_in_unit(
            _runner_argv("--run-verify"), str(Path(get_app_root()).resolve()),
            f"aoteru-verify-{scope}-{uuid.uuid4().hex}", timeout=run_limit, input_text=payload,
        )
        try:
            answer = json.loads(completed.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise WorkerError("execution_failed",
                              f"verification unit failed (rc={completed.returncode}): "
                              f"{(completed.stderr or completed.stdout).strip()[-300:]}") from exc
        if "error" in answer:
            raise WorkerError(answer["error"]["code"], answer["error"]["message"])
        return answer
    return _worktree_verification_local(repo_id, worktree_path, branch)


_IN_VERIFY_UNIT = {"value": False}
_BUDGET = {"end": None}
_BUDGET_MARGIN_S = 5.0


def _remaining(cap: float) -> float:
    """Seconds left in the verb's budget, capped at `cap`."""
    end = _BUDGET["end"]
    return cap if end is None else max(0.0, min(cap, end - time.monotonic()))


def _budget_exhausted(reason: str):
    return WorkerError("executor_unavailable", f"verification budget exhausted ({reason}); retryable")
# Bounds are consistent by construction (gate round 9): a verify unit runs
# at most VERIFY_UNIT_TIMEOUT_S, then run_in_unit stops it and proves its
# cgroup quiescent within VERIFY_KILL_PROOF_S. A same-path verification
# waits longer than that whole lifetime, so a healthy late read can only
# delay -- never refuse -- a later admission; only a unit that cannot be
# proven stopped still fails closed. Control-plane verify calls allow
# VERIFY_CALL_DEADLINE_S, which covers the wait plus the verification.
VERIFY_UNIT_TIMEOUT_S = 10.0
VERIFY_KILL_PROOF_S = estate_worker_procs.KILL_UNIT_TIMEOUT_S + estate_worker_procs.UNIT_STOP_PROOF_S
_VERIFY_UNIT_WAIT_S = 35.0          # > 10 + 5 + 15 = 30 s worst-case late-unit lifetime
VERIFY_CALL_DEADLINE_S = 60.0


def _verify_scope(worktree_path: str) -> str:
    """Verify units are named per worktree path (gate round 7 finding 3), so
    a late or unproven verification only delays work on that same path."""
    return hashlib.sha256(str(Path(worktree_path).resolve()).encode("utf-8")).hexdigest()[:16]


def _run_verify() -> int:
    """Body of an `aoteru-verify-*` unit: read the request on stdin, verify
    in-process (git side processes disabled), print one JSON line."""
    _IN_VERIFY_UNIT["value"] = True
    _disable_git_side_processes(_SPOOL_ROOT)
    try:
        request = json.loads(sys.stdin.read())
        answer = _worktree_verification_local(request["repo_id"], request["worktree_path"], request["branch"])
    except WorkerError as exc:
        answer = {"error": {"code": exc.code, "message": str(exc)}}
    except Exception as exc:
        answer = {"error": {"code": "execution_failed", "message": str(exc)}}
    print(json.dumps(answer))
    return 0


def _worktree_verification_local(repo_id: str, worktree_path: str, branch: str) -> dict:
    if worktree_ops.is_live_checkout_path(repo_id, worktree_path):
        return {"ok": False, "path": str(Path(worktree_path).resolve()), "reason": "refusing the live checkout"}
    verified = worktree_ops.verify_worktree(repo_id, worktree_path, branch)
    ok = bool(verified.get("ok"))
    path = verified.get("path") or str(Path(worktree_path).resolve())
    clean = False
    if ok:
        clean, _reason = git_is_clean(path)
    return {
        "ok": ok,
        "path": path,
        "reason": None if ok else verified.get("reason", "worktree verification failed"),
        # S6.1/S6.2: explicit evidence, never inferred from path/branch.
        "head_sha": verified.get("head") if ok else None,
        "clean": bool(clean),
    }


def _verb_worktree_verify(payload: dict) -> dict:
    return _worktree_verification(payload.get("repo_id"), payload.get("worktree_path"), payload.get("branch"))


# ---------------------------------------------------------------------
# Stage 6 decision primitive (plan §6.0 S6.11)
# ---------------------------------------------------------------------

STARTING_STALE_SECONDS = 60
SPOOL_COMPACT_AFTER_RELEASE_SECONDS = 7 * 24 * 60 * 60
_DEFAULT_PREPARE_WAIT_S = 90.0
_DEFAULT_GIT_UNIT_WAIT_S = 120.0
_WRITE_KINDS = frozenset({"codex-write"})
_DECISION_FS_PROBED: dict = {}
_CURRENT_DEADLINE_S = {"value": None}


def _fsync_dir(path: Path) -> None:
    """Durably persist a directory's entries. Windows has no directory
    fsync through Python -- decision crash-durability there is unproven
    (plan B13), and Windows write verbs are refused anyway (S6.12)."""
    if os.name == "nt":
        return
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _anchor_for(path: Path) -> Path:
    """The fixed durability anchor of a decision path: the parent of the
    root (spool / prepare) it lives under."""
    path = Path(path)
    for root in (_SPOOL_ROOT, _PREPARE_ROOT):
        try:
            path.relative_to(root)
        except ValueError:
            continue
        return Path(root).parent
    raise WorkerError("execution_failed", f"decision path {path} is outside every worker root")


def _ensure_durable_dir(directory: Path) -> None:
    """S6.11 directory durability: from the anchor down, mkdir each
    component and fsync its parent -- always, whether or not this caller
    created it, since a concurrent creator may not have fsynced yet."""
    directory = Path(directory)
    anchor = _anchor_for(directory)
    anchor.mkdir(parents=True, exist_ok=True)
    _fsync_dir(anchor.parent)
    current = anchor
    for part in directory.relative_to(anchor).parts:
        child = current / part
        child.mkdir(exist_ok=True)
        _fsync_dir(current)
        current = child


def _fsync_chain(directory: Path) -> None:
    """fsync `directory` and every ancestor up to (and including) its anchor."""
    directory = Path(directory)
    anchor = _anchor_for(directory)
    current = directory
    while True:
        _fsync_dir(current)
        if current == anchor or current == current.parent:
            break
        current = current.parent


def _load_decision(target: Path) -> dict:
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        # A linked decision is always a complete inode; unparsable means
        # corruption, which must never be read as "absent".
        raise WorkerError("execution_failed", f"corrupt decision file {target}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkerError("execution_failed", f"corrupt decision file {target}")
    return value


def decide_once(target: Path, content: dict) -> tuple[bool, dict]:
    """S6.11: exactly one caller ever wins `target`. Temp file + fsync,
    then `os.link` (fail-if-exists on POSIX and NTFS; publishes a complete
    inode), then fsync the directory chain. Winners and losers alike
    return only after their own fsync, so nobody acts on an undurable
    decision. Decision files are never overwritten, renamed over or
    deleted."""
    target = Path(target)
    directory = target.parent
    _ensure_durable_dir(directory)
    temporary = directory / f".{target.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
    with open(temporary, "x", encoding="utf-8") as handle:
        json.dump(content, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        try:
            os.link(temporary, target)
            won = True
        except FileExistsError:
            won = False
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    _fsync_chain(directory)
    return won, (content if won else _load_decision(target))


def read_decision(target: Path) -> dict | None:
    """Observe -> fsync -> act (S6.11): a present decision is returned only
    after this reader has itself fsynced its directory chain. An absent
    decision is returned as None and must never be acted on directly --
    any action on absence is itself a `decide_once`."""
    target = Path(target)
    if not target.exists():
        return None
    value = _load_decision(target)
    _fsync_chain(target.parent)
    return value


def _decision_fs_supported(root: Path) -> tuple[bool, str]:
    key = str(root)
    if key in _DECISION_FS_PROBED:
        return _DECISION_FS_PROBED[key]
    probe = Path(root) / f".decision-probe-{os.getpid()}-{uuid.uuid4().hex}"
    result = (False, "decision filesystem unsupported")
    try:
        _ensure_durable_dir(probe)
        first, second, target = probe / "a", probe / "b", probe / "t"
        first.write_text("a", encoding="utf-8")
        second.write_text("b", encoding="utf-8")
        os.link(first, target)
        try:
            os.link(second, target)
        except FileExistsError:
            result = (True, "hard-link decisions ok")
        else:
            result = (False, "decision filesystem unsupported: link overwrote an existing target")
    except OSError as exc:
        result = (False, f"decision filesystem unsupported: {exc}")
    finally:
        shutil.rmtree(probe, ignore_errors=True)  # probe scratch only, never a decision
    _DECISION_FS_PROBED[key] = result
    return result


def _write_prerequisites() -> dict:
    decision_ok, decision_detail = _decision_fs_supported(_SPOOL_ROOT)
    prepare_ok, prepare_detail = _decision_fs_supported(_PREPARE_ROOT)
    units_ok, units_detail = estate_worker_procs.runner_units_supported()
    return {
        "decision_fs": decision_ok and prepare_ok,
        "runner_units": units_ok,
        "detail": "; ".join((decision_detail, prepare_detail, units_detail)),
    }


def _require_write_prerequisites() -> None:
    """Every write verb refuses BEFORE any claim unless both the decision
    filesystem (S6.11) and runner units (S6.12) are proven. No fallback."""
    prerequisites = _write_prerequisites()
    if not (prerequisites["decision_fs"] and prerequisites["runner_units"]):
        raise WorkerError("executor_unavailable", prerequisites["detail"])


def _age_seconds(iso_value: Any) -> float | None:
    if not isinstance(iso_value, str):
        return None
    try:
        moment = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - moment).total_seconds()


def _git_env_dir(record: Path) -> Path:
    hooks = record / ".no-hooks"      # dot-prefixed: can never be an execution/lease id
    hooks.mkdir(parents=True, exist_ok=True)
    return hooks


def _disable_git_side_processes(record: Path) -> None:
    """Defence in depth (S6.10): no hooks, no fsmonitor daemon, no
    auto-gc/maintenance for every git child of this process. The unit's
    cgroup stays the proof of quiescence."""
    pairs = [("core.hooksPath", str(_git_env_dir(record))), ("gc.auto", "0"), ("maintenance.auto", "false"),
             ("core.fsmonitor", "false")]
    # Verification and probes are strictly read-only: no optional locks, so
    # `git status` never refreshes/rewrites the index (gate round 6 finding
    # 1) -- a late read can observe a worktree but never mutate it.
    os.environ["GIT_OPTIONAL_LOCKS"] = "0"
    os.environ["GIT_CONFIG_COUNT"] = str(len(pairs))
    for index, (key, value) in enumerate(pairs):
        os.environ[f"GIT_CONFIG_KEY_{index}"] = key
        os.environ[f"GIT_CONFIG_VALUE_{index}"] = value


def _runner_argv(flag: str, *args: str) -> list[str]:
    root = str(Path(get_app_root()).resolve())
    return [sys.executable, "-m", "src.estate_worker", "--root", root, flag, *args]


def _launch_runner(flag: str, args: list[str], *, unit: str, log_path: Path) -> dict:
    return estate_worker_procs.spawn_runner_unit(
        _runner_argv(flag, *args), str(Path(get_app_root()).resolve()), str(log_path), unit,
    )


def _runner_self_check(unit: str) -> tuple[dict | None, str | None]:
    """A runner may execute only inside its own dedicated unit cgroup."""
    cgroup = estate_worker_procs.own_cgroup()
    if not estate_worker_procs.cgroup_is_dedicated(cgroup, unit):
        return None, f"runner is not inside its dedicated unit {unit} (cgroup {cgroup!r})"
    create_time = None
    fields = estate_worker_procs._proc_stat_fields(os.getpid())
    if fields is not None:
        create_time = fields[2]
    return {"pid": os.getpid(), "create_time": create_time, "cgroup": cgroup, "unit": unit}, None


def _unit_quiescent(run_decision: dict | None) -> bool | None:
    if not isinstance(run_decision, dict):
        return None
    if run_decision.get("decision") == "abort":
        return True
    return estate_worker_procs.tree_quiescent(run_decision)


# ---------------------------------------------------------------------
# Execution spool (S6.6 / S6.8 / S6.12)
# ---------------------------------------------------------------------

def _spool_files(spool: Path) -> dict:
    return {
        "claim": spool / "claim.json", "run": spool / "run.json", "state": spool / "state.json",
        "result": spool / "result.json", "released": spool / "released.json",
        "closed": spool / "closed.json", "log": spool / "worker.log",
    }


def _attempts(spool: Path, kind: str) -> list[tuple[int, dict, dict | None]]:
    """Recorded attempts (finalize|push) as (n, attempt, run_decision)."""
    directory = spool / kind
    out = []
    if not directory.is_dir():
        return out
    for entry in directory.iterdir():
        match = re.fullmatch(r"attempt-(\d+)\.json", entry.name)
        if not match:
            continue
        number = int(match.group(1))
        attempt = read_decision(entry)
        run = read_decision(directory / f"attempt-{number}.run.json")
        out.append((number, attempt or {}, run))
    return sorted(out, key=lambda item: item[0])


def _abort_run(run_path: Path, by: str, reason: str) -> dict:
    _won, decided = decide_once(run_path, {"decision": "abort", "by": by, "reason": reason, "at": _utcnow()})
    return decided


def _maybe_abort_stale_start(spool: Path, claim: dict) -> None:
    files = _spool_files(spool)
    if claim.get("kind") != "start" or files["run"].exists():
        return
    age = _age_seconds(claim.get("claimed_at"))
    if age is not None and age > STARTING_STALE_SECONDS:
        _abort_run(files["run"], "observer", f"starting claim older than {STARTING_STALE_SECONDS}s")


def _execution_aggregate(spool: Path, *, fence_unstarted: bool) -> tuple[bool | None, list[dict]]:
    """S6.12 aggregate execution quiescence over every worktree-touching
    unit: the writer runner plus every finalize attempt (push attempts are
    excluded; they never touch the worktree). With `fence_unstarted`, an
    attempt/writer with no run decision is fenced (abort won) first --
    otherwise it counts as not proven."""
    files = _spool_files(spool)
    units = []
    claim = read_decision(files["claim"])
    if claim is not None and claim.get("kind") == "start":
        run = read_decision(files["run"])
        if run is None and fence_unstarted:
            run = _abort_run(files["run"], "fence", "closed before the runner decided")
        units.append({"unit": (run or {}).get("unit"), "kind": "writer", "quiescent": _unit_quiescent(run)})
    for number, _attempt, run in _attempts(spool, "finalize"):
        if run is None and fence_unstarted:
            run = _abort_run(spool / "finalize" / f"attempt-{number}.run.json", "fence",
                             "closed before the attempt decided")
        units.append({"unit": (run or {}).get("unit"), "kind": f"finalize-{number}",
                      "quiescent": _unit_quiescent(run)})
    if estate_worker_procs.runner_units_supported()[0] and claim is not None and claim.get("kind") == "start":
        # A verification of THIS execution's worktree that timed out unproven
        # may still touch it; the aggregate cannot be proven while one is live.
        worktree = ((claim.get("request") or {}).get("lease") or {}).get("worktree_path")
        if worktree:
            scope = _verify_scope(worktree)
            units.append({"unit": f"aoteru-verify-{scope}-*", "kind": "verify",
                          "quiescent": estate_worker_procs.verify_units_quiescent(scope)})
    if any(unit["quiescent"] is None for unit in units):
        aggregate = None
    else:
        aggregate = all(unit["quiescent"] for unit in units)
    return aggregate, units


def _execution_view(spool: Path) -> dict:
    """Derived state (S6.6): computed only from decision files plus
    quiescence, never from an overwritable field."""
    files = _spool_files(spool)
    claim = read_decision(files["claim"])
    base = {"handle": None, "spawned": False, "started_at": None, "finished_at": None,
            "released": read_decision(files["released"]) is not None}
    if claim is None:
        return {**base, "state": "unknown", "quiescent": True, "process_alive": False, "units": []}
    if claim.get("kind") == "fence":
        return {**base, "state": "fenced", "quiescent": True, "process_alive": False, "units": []}
    telemetry = _json_read(files["state"])
    aggregate, units = _execution_aggregate(spool, fence_unstarted=False)
    view = {
        **base,
        "spawned": bool(_json_read(spool / "spawn.json").get("spawn")) or bool(telemetry.get("state")),
        "started_at": telemetry.get("started_at"), "finished_at": telemetry.get("finished_at"),
        "quiescent": aggregate, "process_alive": aggregate is not True, "units": units,
    }
    run = read_decision(files["run"])
    if telemetry.get("state") == "tombstone":
        view["state"] = "tombstone"
        return view
    if run is None:
        view["state"] = "starting"
        return view
    if run.get("decision") == "abort":
        view["state"] = "start_failed"
        view["error"] = run.get("reason")
        return view
    view["handle"] = {key: run.get(key) for key in ("pid", "create_time", "cgroup", "unit")}
    view["finalize_commit"] = read_decision(spool / "finalize" / "commit.json")
    writer_quiescent = _unit_quiescent(run)
    recorded = telemetry.get("state")
    if recorded in _TERMINAL_STATES and writer_quiescent is True and aggregate is True:
        view["state"] = recorded
        result = _json_read(files["result"])
        if result:
            view["result"] = result
    elif recorded in _TERMINAL_STATES:
        # Terminal record, but the writer or a finalize attempt is not proven
        # quiescent yet (6c finding 4): still running for every consumer.
        view["state"] = "running"
        view["terminal_pending"] = True
    elif writer_quiescent is True:
        # The runner decided `execute`, its whole unit is proven gone, and
        # it never recorded a terminal state: positively observed dead
        # (the control plane's `interrupted`), never guessed.
        view["state"] = "interrupted"
    else:
        view["state"] = "running"
        view["terminal_pending"] = recorded in _TERMINAL_STATES
    view["finalize_result"] = _latest_finalize_result(spool)
    return view


def _latest_finalize_result(spool: Path) -> dict | None:
    """The newest quiescent finalize attempt's recorded result -- what the
    control plane reads after closure to record `finalized` idempotently
    (6c finding 1), even when the finalize response itself was lost."""
    for number, _attempt, run in reversed(_attempts(spool, "finalize")):
        if run is None or run.get("decision") != "execute" or _unit_quiescent(run) is not True:
            continue
        result = _json_read(spool / "finalize" / f"attempt-{number}.result.json")
        if result:
            return {**result, "attempt": number}
    return None


def _start_answer(spool: Path, *, reused: bool) -> dict:
    view = _execution_view(spool)
    accepted = view["state"] not in ("unknown", "fenced", "tombstone", "start_failed")
    if reused and view["state"] == "starting":
        # §G U46 / S6.6: a same-id start that finds an in-progress claim is
        # a pending, non-terminal answer: accepted false, never execution_failed.
        accepted = False
    answer = {"accepted": accepted, "state": view["state"], "handle": view["handle"],
              "reused": reused, "spawned": view["spawned"]}
    if view.get("error"):
        answer["error"] = view["error"]
    return answer


def _validate_start(payload: dict) -> None:
    kind = payload.get("kind")
    if kind == "noop-sleep":
        if not _selftest_enabled():
            raise WorkerError("bad_request", "noop-sleep is available only in worker self-test mode")
        _timeout(payload, 1.0)
        return
    if kind != "codex-write":
        raise WorkerError("bad_request", f"unsupported start kind {kind!r}")
    lease = payload.get("lease")
    if not isinstance(lease, dict) or not isinstance(lease.get("lease_id"), str):
        raise WorkerError("bad_request", "codex-write start requires a lease")
    if not isinstance(payload.get("objective"), str):
        raise WorkerError("bad_request", "codex-write start requires objective")
    _timeout(payload, 1800.0)
    verified = _worktree_verification(payload.get("repo_id"), lease.get("worktree_path"), lease.get("branch"))
    if not verified["ok"]:
        raise WorkerError("authority_denied", verified["reason"])
    if verified.get("clean") is not True:
        # Gate round 7 finding 2: changes that arrived after admission's
        # clean check must never be mixed into this execution.
        raise WorkerError("authority_denied", "leased worktree is not clean at start")
    expected_head = lease.get("expected_head_sha")
    if expected_head is not None:
        if verified.get("head_sha") != expected_head:
            raise WorkerError("authority_denied",
                              f"worktree HEAD {verified.get('head_sha')!r} != admission head {expected_head!r}")


def _verb_start(payload: dict) -> dict:
    execution_id = payload.get("execution_id")
    spool = _spool_path(execution_id)
    files = _spool_files(spool)
    existing = read_decision(files["claim"])
    if existing is not None:
        _maybe_abort_stale_start(spool, existing)
        return _start_answer(spool, reused=True)
    # Everything below the claim is pre-claim validation: a refusal here is
    # a deterministic pre-spawn refusal of THIS request only (S6.6).
    _validate_start(payload)
    _require_write_prerequisites()
    won, decided = decide_once(files["claim"], {"kind": "start", "request": payload, "claimed_at": _utcnow()})
    if not won:
        _maybe_abort_stale_start(spool, decided)
        return _start_answer(spool, reused=True)
    # Gate round 8: nothing after the claim may surface as an error -- a
    # worker error must only ever mean "refused before the claim". Every
    # post-claim failure is answered from the decision files instead.
    try:
        unit = f"aoteru-run-{execution_id}"
        _selftest_spawn_delay(payload)
        try:
            spawn = _launch_runner("--run-spooled", [execution_id], unit=unit, log_path=files["log"])
        except estate_worker_procs.ProcessLayerError as exc:
            _abort_run(files["run"], "starter", f"{exc.code}: {exc}")
            _json_write(files["result"], {"ok": False, "error": str(exc)})
            return _start_answer(spool, reused=False)
        # spawn.json, never state.json: state.json belongs to the runner alone,
        # so a fast runner's terminal write can never be clobbered (6c finding 3).
        try:
            _json_write(spool / "spawn.json", {"spawn": spawn, "at": _utcnow()})
        except OSError:
            pass
    except Exception:
        pass
    try:
        return _start_answer(spool, reused=False)
    except Exception:
        return {"accepted": False, "state": "starting", "handle": None, "reused": False, "spawned": None}


def _verb_status(payload: dict) -> dict:
    execution_id = payload.get("execution_id")
    if set(payload) - {"execution_id", "fence", "close"}:
        raise WorkerError("bad_request", "status accepts only execution_id, fence and close")
    fence, close = bool(payload.get("fence")), bool(payload.get("close"))
    spool = _spool_path(execution_id)
    files = _spool_files(spool)
    claim = read_decision(files["claim"])
    fenced_now = False
    if fence or close:
        if claim is None:
            fenced_now, claim = decide_once(files["claim"], {"kind": "fence", "fenced_at": _utcnow()})
        elif claim.get("kind") == "start" and not files["run"].exists():
            decided = _abort_run(files["run"], "fence", "fenced by status")
            fenced_now = decided.get("by") == "fence"
    elif claim is not None:
        _maybe_abort_stale_start(spool, claim)
    if close:
        # Closer side of the Dekker pair (S6.12): closure first, then scan
        # every attempt (fencing any without a run decision).
        decide_once(files["closed"], {"by": "status", "at": _utcnow()})
        _execution_aggregate(spool, fence_unstarted=True)
    view = _execution_view(spool)
    view["fenced_now"] = fenced_now
    view["closed"] = read_decision(files["closed"]) is not None
    return view


def _verb_spool_release(payload: dict) -> dict:
    execution_id = payload.get("execution_id")
    resolution = payload.get("resolution")
    if set(payload) != {"execution_id", "resolution"} or resolution not in ("not_started", "finalized", "recovered"):
        raise WorkerError("bad_request", "spool.release requires execution_id and a resolved resolution")
    spool = _spool_path(execution_id)
    files = _spool_files(spool)
    existing = read_decision(files["released"])
    if existing is not None:
        return {"released": True, "state": _execution_view(spool)["state"], "already_released": True}
    _require_write_prerequisites()
    # §G U62: a `starting` writer (claimed, no run decision) is refused
    # BEFORE any closure -- release is an acknowledgement of a resolution
    # the control plane already proved, never a way to fence a live start.
    current = read_decision(files["claim"])
    if current is not None and current.get("kind") == "start" and read_decision(files["run"]) is None:
        raise WorkerError("authority_denied", "refusing to acknowledge resolution of a starting writer")
    closure = _verb_status({"execution_id": execution_id, "close": True})
    if closure["state"] == "starting" or closure["quiescent"] is not True:
        raise WorkerError("authority_denied",
                          f"refusing to acknowledge resolution: execution not quiescent ({closure['state']})")
    won, _decided = decide_once(files["released"], {"resolution": resolution, "released_at": _utcnow()})
    return {"released": True, "state": closure["state"], "already_released": not won}


def _verb_cancel(payload: dict) -> dict:
    execution_id = payload.get("execution_id")
    if set(payload) != {"execution_id"}:
        raise WorkerError("bad_request", "cancel requires only execution_id")
    spool = _spool_path(execution_id)
    files = _spool_files(spool)
    claim = read_decision(files["claim"])
    if claim is None or claim.get("kind") != "start":
        raise WorkerError("not_found", f"execution {execution_id!r} was not found")
    run = read_decision(files["run"])
    if run is None:
        run = _abort_run(files["run"], "cancel", "cancelled before the runner decided")
    if run.get("decision") == "abort":
        return {"killed": True, "still_alive_pids": []}
    outcome = estate_worker_procs.kill_unit(run.get("unit"))
    quiescent = _unit_quiescent(run)
    telemetry = _json_read(files["state"])
    if telemetry.get("state") not in _TERMINAL_STATES:
        _json_write(files["result"], {"ok": False, "error": "execution cancelled"})
        _json_write(files["state"], {**telemetry, "state": "failed", "finished_at": _utcnow()})
    return {"killed": bool(outcome.get("ok")) and quiescent is True,
            "still_alive_pids": [] if quiescent is True else [run.get("pid")]}


def _run_spooled(execution_id: str) -> int:
    spool = _spool_path(execution_id)
    files = _spool_files(spool)
    claim = read_decision(files["claim"])
    if claim is None or claim.get("kind") != "start":
        return 1
    unit = f"aoteru-run-{execution_id}.service"
    handle, problem = _runner_self_check(unit)
    if handle is None:
        _abort_run(files["run"], "runner", problem)
        return 1
    won, _decided = decide_once(files["run"], {"decision": "execute", **handle, "at": _utcnow()})
    if not won:
        return 0   # an abort won first: the writer must never run
    request = claim.get("request") or {}
    started_at = _utcnow()
    telemetry = _json_read(files["state"])

    def on_started(pid: int) -> None:
        _json_write(files["state"], {**telemetry, "state": "running", "writer_pid": pid,
                                     "started_at": started_at, "finished_at": None})

    kind = request.get("kind")
    try:
        if kind == "noop-sleep" and _selftest_enabled():
            on_started(os.getpid())
            time.sleep(_timeout(request, 1.0))
            result = {"ok": True, "output": "noop-sleep complete", "provider": "selftest"}
        elif kind == "codex-write":
            lease = request.get("lease") or {}
            # Re-check AFTER winning the execute decision: the tree must still
            # be clean at the admitted HEAD, or the writer never runs.
            previous_in_unit = _IN_VERIFY_UNIT["value"]
            _IN_VERIFY_UNIT["value"] = True          # inside our own tracked unit
            try:
                now_verified = _worktree_verification(request.get("repo_id"), lease.get("worktree_path"),
                                                      lease.get("branch"))
            finally:
                _IN_VERIFY_UNIT["value"] = previous_in_unit
            if not now_verified["ok"] or now_verified.get("clean") is not True \
                    or (lease.get("expected_head_sha") and now_verified.get("head_sha") != lease["expected_head_sha"]):
                raise WorkerError("authority_denied", "worktree changed between admission and runner start; "
                                                      "writer not run")
            result = estate_router._execute_codex_with_sandbox(
                request.get("objective", ""),
                sandbox="workspace-write",
                provider="codex",
                timeout=_timeout(request, 1800.0),
                cwd=lease.get("worktree_path"),
                on_started=on_started,
            )
        else:
            raise WorkerError("bad_request", f"unsupported spooled kind {kind!r}")
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    _json_write(files["result"], result)
    error_text = str(result.get("error", "")).lower()
    terminal = "succeeded" if result.get("ok") else ("timed_out" if "timed out" in error_text or "timeout" in error_text else "failed")
    current = _json_read(files["state"])
    _json_write(files["state"], {**current, "state": terminal,
                                 "started_at": current.get("started_at") or started_at, "finished_at": _utcnow()})
    return 0


# ---------------------------------------------------------------------
# Prepare record and runner (S6.9)
# ---------------------------------------------------------------------

def _prepare_path(lease_id: Any) -> Path:
    if not isinstance(lease_id, str) or not _EXECUTION_ID_RE.fullmatch(lease_id):
        raise WorkerError("bad_request", "lease_id contains unsupported characters")
    return _PREPARE_ROOT / lease_id


def _prepare_view(record: Path) -> dict:
    files = _spool_files(record)
    claim = read_decision(files["claim"])
    if claim is None:
        return {"state": "unknown", "quiescent": True, "record": None}
    if claim.get("kind") == "fence":
        return {"state": "fenced", "quiescent": True, "record": claim}
    run = read_decision(files["run"])
    if run is None:
        return {"state": "preparing", "quiescent": None, "record": claim}
    if run.get("decision") == "abort":
        return {"state": "fenced", "quiescent": True, "record": run}
    quiescent = _unit_quiescent(run)
    result = _json_read(files["result"])
    if quiescent is not True:
        return {"state": "preparing", "quiescent": quiescent, "record": run}
    if result.get("state") in ("prepared", "prepare_failed"):
        return {**result, "quiescent": True, "record": run}
    return {"state": "prepare_interrupted", "quiescent": True, "record": run}


def _wait_s(default: float) -> float:
    deadline = _CURRENT_DEADLINE_S["value"]
    if isinstance(deadline, (int, float)) and deadline > 10:
        return min(default, float(deadline) - 10)
    return default


def _verb_worktree_prepare(payload: dict) -> dict:
    repo_id = payload.get("repo_id")
    branch = payload.get("branch")
    base_ref = payload.get("base_ref")
    lease = payload.get("lease")
    if not all(isinstance(value, str) and value for value in (repo_id, branch, base_ref)):
        raise WorkerError("bad_request", "worktree.prepare requires repo_id, branch and base_ref")
    if not isinstance(lease, dict) or not isinstance(lease.get("lease_id"), str) or not lease.get("lease_id"):
        raise WorkerError("bad_request", "worktree.prepare requires lease {lease_id, host_id} (S6.7)")
    record = _prepare_path(lease["lease_id"])
    files = _spool_files(record)
    reused = True
    if read_decision(files["claim"]) is None:
        _require_write_prerequisites()
        won, _claim = decide_once(files["claim"], {"kind": "prepare", "request": payload, "claimed_at": _utcnow()})
        if won:
            reused = False
            try:
                _launch_runner("--run-prepare", [lease["lease_id"]],
                               unit=f"aoteru-prepare-{lease['lease_id']}", log_path=files["log"])
            except estate_worker_procs.ProcessLayerError as exc:
                _abort_run(files["run"], "starter", f"{exc.code}: {exc}")
            except Exception:
                pass                      # post-claim: answered from the record below, never an error
    try:
        deadline = time.monotonic() + _wait_s(_DEFAULT_PREPARE_WAIT_S)
        view = _prepare_view(record)
        while view["state"] == "preparing" and time.monotonic() < deadline:
            time.sleep(0.2)
            view = _prepare_view(record)
    except Exception:
        view = {"state": "preparing", "quiescent": None, "record": None}
    return {**view, "reused": reused}


def _verb_worktree_prepare_status(payload: dict) -> dict:
    lease_id = payload.get("lease_id")
    if set(payload) - {"lease_id", "fence"}:
        raise WorkerError("bad_request", "worktree.prepare_status accepts only lease_id and fence")
    record = _prepare_path(lease_id)
    files = _spool_files(record)
    if payload.get("fence"):
        if read_decision(files["claim"]) is None:
            decide_once(files["claim"], {"kind": "fence", "fenced_at": _utcnow()})
        elif not files["run"].exists():
            _abort_run(files["run"], "fence", "fenced by prepare_status")
    return _prepare_view(record)


def _run_prepare(lease_id: str) -> int:
    record = _prepare_path(lease_id)
    files = _spool_files(record)
    claim = read_decision(files["claim"])
    if claim is None or claim.get("kind") != "prepare":
        return 1
    handle, problem = _runner_self_check(f"aoteru-prepare-{lease_id}.service")
    if handle is None:
        _abort_run(files["run"], "runner", problem)
        return 1
    won, _decided = decide_once(files["run"], {"decision": "execute", **handle, "at": _utcnow()})
    if not won:
        return 0
    _disable_git_side_processes(record)
    request = claim.get("request") or {}
    try:
        created = worktree_ops.create_or_reuse_worktree(
            request["repo_id"], request["branch"], base_ref=request["base_ref"],
        )
        verified = worktree_ops.verify_worktree(request["repo_id"], created["path"], request["branch"])
        if not verified["ok"]:
            result = {"state": "prepare_failed", "error": verified["reason"], "stage": "verify"}
        else:
            clean, _reason = git_is_clean(verified["path"])
            result = {"state": "prepared", "path": verified["path"], "branch": verified["branch"],
                      "head_sha": verified["head"], "clean": clean}
    except Exception as exc:
        result = {"state": "prepare_failed", "error": str(exc), "stage": "create"}
    _json_write(files["result"], result)
    _json_write(files["state"], {"state": result["state"], "finished_at": _utcnow()})
    return 0


# ---------------------------------------------------------------------
# Finalize and push attempts (S6.10 / S6.12)
# ---------------------------------------------------------------------

def _record_attempt(spool: Path, kind: str, request: dict) -> int:
    directory = spool / kind
    number = len(_attempts(spool, kind)) + 1
    while True:
        won, _decided = decide_once(directory / f"attempt-{number}.json",
                                    {"request": request, "recorded_at": _utcnow()})
        if won:
            return number
        number += 1


def _wait_attempts(spool: Path, kind: str, number: int, wait_s: float) -> dict | None:
    """Wait for attempt `number`'s result AND quiescence of EVERY recorded
    attempt of this kind (S6.10). Earlier attempts with no run decision are
    fenced so they can never start later."""
    directory = spool / kind
    deadline = time.monotonic() + wait_s
    while True:
        attempts = _attempts(spool, kind)
        pending = False
        for other, _attempt, run in attempts:
            if run is None and other != number:
                run = _abort_run(directory / f"attempt-{other}.run.json", "fence",
                                 f"superseded by attempt {number}")
            if run is None or _unit_quiescent(run) is not True:
                pending = True
        result = _json_read(directory / f"attempt-{number}.result.json")
        if result and not pending:
            return result
        own_run = read_decision(directory / f"attempt-{number}.run.json")
        if own_run is not None and own_run.get("decision") == "abort" and not pending:
            return {"outcome": "execution_closed" if "closed" in str(own_run.get("reason")) else "aborted",
                    "reason": own_run.get("reason")}
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.2)


def _verb_worktree_finalize(payload: dict) -> dict:
    execution_id = payload.get("execution_id")
    for name in ("repo_id", "worktree_path", "branch", "commit_message", "expected_head_sha"):
        if not isinstance(payload.get(name), str) or not payload.get(name):
            raise WorkerError("bad_request", f"worktree.finalize requires {name}")
    spool = _spool_path(execution_id)
    files = _spool_files(spool)
    claim = read_decision(files["claim"])
    if claim is None or claim.get("kind") != "start":
        raise WorkerError("not_found", f"execution {execution_id!r} has no start claim on this worker")
    _require_write_prerequisites()
    number = _record_attempt(spool, "finalize", payload)
    run_path = spool / "finalize" / f"attempt-{number}.run.json"
    # Attempt side of the Dekker pair (S6.12): recorded, THEN read closure --
    # and only then touch the worktree at all (gate round 4: a late finalize
    # after closure runs NO git command, not even verification).
    if read_decision(files["closed"]) is not None:
        _abort_run(run_path, "attempt", "execution_closed")
        return {"outcome": "execution_closed", "attempt": number}
    # No worktree git here at all (gate round 5): verification runs inside
    # the attempt runner AFTER it wins its run.json `execute` decision --
    # the same decision a closer's fence takes -- so an attempt fenced
    # between this closure read and its launch can never touch the tree.
    try:
        _launch_runner("--run-finalize", [execution_id, str(number)],
                       unit=f"aoteru-finalize-{execution_id}-{number}",
                       log_path=spool / "finalize" / f"attempt-{number}.log")
    except estate_worker_procs.ProcessLayerError as exc:
        _abort_run(run_path, "starter", f"{exc.code}: {exc}")
        return {"outcome": "finalize_in_progress", "attempt": number, "reason": str(exc)}
    result = _wait_attempts(spool, "finalize", number, _wait_s(_DEFAULT_GIT_UNIT_WAIT_S))
    if result is None:
        return {"outcome": "finalize_in_progress", "attempt": number}
    if result.get("outcome") == "authority_denied":
        raise WorkerError("authority_denied", result.get("reason", "unattributable history"))
    return {**result, "attempt": number}


def _git(path: str, args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
    return _run_git(path, args, timeout=timeout)


def _exact_commit_push(path: str, commit_sha: str, branch: str) -> dict:
    pushed = _git(path, ["push", "origin", f"{commit_sha}:refs/heads/{branch}"], timeout=300)
    if pushed.returncode == 0:
        return {"state": "pushed", "commit_sha": commit_sha, "remote": "origin", "branch": branch,
                "contained": False, "at": _utcnow()}
    fetched = _git(path, ["fetch", "origin", branch], timeout=300)
    if fetched.returncode == 0:
        ancestor = _git(path, ["merge-base", "--is-ancestor", commit_sha, "FETCH_HEAD"])
        if ancestor.returncode == 0:
            return {"state": "pushed", "commit_sha": commit_sha, "remote": "origin", "branch": branch,
                    "contained": True, "at": _utcnow()}
    return {"state": "failed", "commit_sha": commit_sha, "remote": "origin", "branch": branch,
            "error": (pushed.stderr or "").strip()[-500:] or "git push failed", "at": _utcnow()}


def _finalize_logic(execution_id: str, spool: Path, request: dict) -> dict:
    path = str(Path(request["worktree_path"]).resolve())
    branch, expected = request["branch"], request["expected_head_sha"]
    commit_record = spool / "finalize" / "commit.json"
    current = _git(path, ["branch", "--show-current"])
    if current.returncode != 0 or current.stdout.strip() != branch:
        return {"outcome": "authority_denied", "reason": "worktree branch changed before finalization"}

    def _head() -> str:
        return _git(path, ["rev-parse", "HEAD"]).stdout.strip()

    def _clean() -> bool:
        status = _git(path, ["status", "--porcelain"])
        return status.returncode == 0 and not status.stdout.strip()

    for _round in range(4):
        proven = read_decision(commit_record)
        head = _head()
        if proven is not None:
            if head == proven.get("commit_sha") and _clean():
                return {"outcome": "finalized", "committed": True, "adopted": True,
                        "commit_sha": head, "parent_sha": proven.get("parent_sha"),
                        "dirty_paths": proven.get("dirty_paths", []),
                        "push": _exact_commit_push(path, head, branch)}
            return {"outcome": "authority_denied", "reason": "history moved after the recorded finalize commit"}
        if head != expected:
            parent = _git(path, ["rev-parse", "HEAD^"]).stdout.strip()
            message = _git(path, ["log", "-1", "--format=%B"]).stdout
            return {"outcome": "finalize_ambiguous", "head": head, "parent": parent,
                    "trailer_matches": f"Aoteru-Execution: {execution_id}" in message}
        status = _git(path, ["status", "--porcelain"])
        if status.returncode != 0:
            return {"outcome": "authority_denied", "reason": status.stderr.strip() or "git status failed"}
        dirty_paths = [line[3:] for line in status.stdout.splitlines() if line.strip()]
        if not dirty_paths:
            if _head() != expected or read_decision(commit_record) is not None:
                # A concurrent same-execution attempt committed between our
                # HEAD read and the clean check: re-evaluate (adoption via
                # commit.json), never report a stale no-change result.
                continue
            return {"outcome": "finalized", "committed": False, "adopted": False, "commit_sha": head,
                    "parent_sha": None, "dirty_paths": [],
                    "push": {"state": "not_required", "commit_sha": head, "branch": branch}}
        added = _git(path, ["add", "--", *dirty_paths])
        committed = _git(path, ["commit", "-m", f"{request['commit_message']}\n\nAoteru-Execution: {execution_id}"]) \
            if added.returncode == 0 else added
        if committed.returncode != 0:
            continue   # re-evaluate once: a concurrent same-execution attempt may have committed
        sha = _head()
        parent = _git(path, ["rev-parse", "HEAD^"]).stdout.strip()
        if parent != expected:
            return {"outcome": "finalize_ambiguous", "head": sha, "parent": parent, "trailer_matches": True}
        decide_once(commit_record, {"commit_sha": sha, "parent_sha": parent,
                                    "dirty_paths": dirty_paths, "at": _utcnow()})
        return {"outcome": "finalized", "committed": True, "adopted": False, "commit_sha": sha,
                "parent_sha": parent, "dirty_paths": dirty_paths,
                "push": _exact_commit_push(path, sha, branch)}
    return {"outcome": "finalize_ambiguous", "head": _head(), "parent": None, "trailer_matches": False}


def _run_attempt(kind: str, execution_id: str, number: str) -> int:
    spool = _spool_path(execution_id)
    directory = spool / kind
    attempt = read_decision(directory / f"attempt-{number}.json")
    if attempt is None:
        return 1
    run_path = directory / f"attempt-{number}.run.json"
    handle, problem = _runner_self_check(f"aoteru-{kind}-{execution_id}-{number}.service")
    if handle is None:
        _abort_run(run_path, "runner", problem)
        return 1
    won, _decided = decide_once(run_path, {"decision": "execute", **handle, "at": _utcnow()})
    if not won:
        return 0          # fenced (closure) or superseded: never touches the worktree
    _disable_git_side_processes(spool)
    previous_in_unit = _IN_VERIFY_UNIT["value"]
    _IN_VERIFY_UNIT["value"] = True    # this runner's own unit already tracks every git child
    request = attempt.get("request") or {}
    try:
        return _run_attempt_body(kind, execution_id, spool, directory, number, request)
    finally:
        _IN_VERIFY_UNIT["value"] = previous_in_unit


def _run_attempt_body(kind, execution_id, spool, directory, number, request) -> int:
    try:
        if kind == "finalize":
            verified = _worktree_verification(request["repo_id"], request["worktree_path"], request["branch"])
            if not verified["ok"]:
                result = {"outcome": "authority_denied", "reason": verified["reason"]}
            else:
                result = _finalize_logic(execution_id, spool, request)
        else:
            result = _push_logic(request)
    except Exception as exc:
        result = {"outcome": "finalize_ambiguous" if kind == "finalize" else "push_failed", "reason": str(exc)}
    _json_write(directory / f"attempt-{number}.result.json", result)
    return 0


def _push_logic(request: dict) -> dict:
    repo_path = estate_router.resolve_repo_path(request["repo_id"])
    if repo_path is None:
        return {"outcome": "repo_unavailable", "reason": f"repo {request['repo_id']!r} does not resolve"}
    commit_sha, branch = request["commit_sha"], request["branch"]
    exists = _git(repo_path, ["cat-file", "-e", f"{commit_sha}^{{commit}}"])
    if exists.returncode != 0:
        return {"outcome": "not_found", "reason": f"commit {commit_sha} is absent on this worker"}
    return {"outcome": "pushed_or_failed", "push": _exact_commit_push(repo_path, commit_sha, branch)}


def _verb_worktree_push(payload: dict) -> dict:
    execution_id = payload.get("execution_id")
    for name in ("repo_id", "branch", "commit_sha"):
        if not isinstance(payload.get(name), str) or not payload.get(name):
            raise WorkerError("bad_request", f"worktree.push requires {name}")
    if not re.fullmatch(r"[0-9a-f]{40}", payload["commit_sha"]):
        raise WorkerError("bad_request", "commit_sha must be a full 40-hex sha")
    spool = _spool_path(execution_id)
    if read_decision(_spool_files(spool)["claim"]) is None:
        raise WorkerError("not_found", f"execution {execution_id!r} has no record on this worker")
    _require_write_prerequisites()
    # Push never reads closed.json: it touches no worktree (S6.12, round 7).
    number = _record_attempt(spool, "push", payload)
    try:
        _launch_runner("--run-push", [execution_id, str(number)], unit=f"aoteru-push-{execution_id}-{number}",
                       log_path=spool / "push" / f"attempt-{number}.log")
    except estate_worker_procs.ProcessLayerError as exc:
        _abort_run(spool / "push" / f"attempt-{number}.run.json", "starter", f"{exc.code}: {exc}")
        return {"pushed": False, "outcome": "push_in_progress", "error": str(exc)}
    result = _wait_attempts(spool, "push", number, _wait_s(_DEFAULT_GIT_UNIT_WAIT_S))
    if result is None:
        return {"pushed": False, "outcome": "push_in_progress"}
    if result.get("outcome") == "not_found":
        raise WorkerError("not_found", result["reason"])
    push = result.get("push") or {"state": "failed", "error": result.get("reason")}
    return {"pushed": push.get("state") == "pushed", "contained": bool(push.get("contained")),
            "commit_sha": payload["commit_sha"], "push": push, "error": push.get("error")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="worker checkout root")
    parser.add_argument("--run-spooled", metavar="EXECUTION_ID")
    parser.add_argument("--run-prepare", metavar="LEASE_ID")
    parser.add_argument("--run-finalize", nargs=2, metavar=("EXECUTION_ID", "ATTEMPT"))
    parser.add_argument("--run-push", nargs=2, metavar=("EXECUTION_ID", "ATTEMPT"))
    parser.add_argument("--run-verify", action="store_true")
    args = parser.parse_args(argv)
    if args.root:
        root = Path(args.root).expanduser().resolve()
        os.chdir(root)
        try:
            sys.path.remove(str(root))
        except ValueError:
            pass
        sys.path.insert(0, str(root))
        estate_router._CONFIG_DIR = root / "config"
    if args.run_spooled:
        return _run_spooled(args.run_spooled)
    if args.run_prepare:
        return _run_prepare(args.run_prepare)
    if args.run_finalize:
        return _run_attempt("finalize", *args.run_finalize)
    if args.run_push:
        return _run_attempt("push", *args.run_push)
    if args.run_verify:
        return _run_verify()
    try:
        request = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        print(f"invalid worker request JSON: {exc}", file=sys.stderr)
        return 2
    response = handle(request)
    print(json.dumps(response, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())

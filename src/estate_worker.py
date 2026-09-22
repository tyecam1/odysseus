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
_SPOOL_TTL_SECONDS = 7 * 24 * 60 * 60
_TERMINAL_STATES = frozenset({"succeeded", "failed", "timed_out"})
_EXECUTION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


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


def _spool_path(execution_id: str) -> Path:
    if not isinstance(execution_id, str) or not _EXECUTION_ID_RE.fullmatch(execution_id):
        raise WorkerError("bad_request", "execution_id contains unsupported characters")
    return _SPOOL_ROOT / execution_id


def _gc_spools() -> None:
    try:
        entries = list(_SPOOL_ROOT.iterdir())
    except OSError:
        return
    cutoff = time.time() - _SPOOL_TTL_SECONDS
    for entry in entries:
        if not entry.is_dir():
            continue
        state_path = entry / "state.json"
        state = _json_read(state_path)
        if state.get("state") not in _TERMINAL_STATES:
            continue
        try:
            stale = state_path.stat().st_mtime < cutoff
        except OSError:
            stale = False
        if stale:
            shutil.rmtree(entry, ignore_errors=True)


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
        if entry.is_dir() and _json_read(entry / "state.json").get("state") in {"accepted", "running"}:
            result.append(entry.name)
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
            "codex-write": codex_available and os.name != "nt",
        },
        "repos": repos,
        "hardware": _hardware(),
    }


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


def _verb_worktree_prepare(payload: dict) -> dict:
    repo_id = payload.get("repo_id")
    branch = payload.get("branch")
    base_ref = payload.get("base_ref")
    if not all(isinstance(value, str) and value for value in (repo_id, branch, base_ref)):
        raise WorkerError("bad_request", "worktree.prepare requires repo_id, branch and base_ref")
    try:
        created = worktree_ops.create_or_reuse_worktree(repo_id, branch, base_ref=base_ref)
    except RuntimeError as exc:
        raise WorkerError("repo_unavailable", str(exc)) from exc
    verified = worktree_ops.verify_worktree(repo_id, created["path"], branch)
    if not verified["ok"]:
        raise WorkerError("authority_denied", verified["reason"])
    clean, _reason = git_is_clean(verified["path"])
    return {
        "path": verified["path"],
        "branch": verified["branch"],
        "head_sha": verified["head"],
        "clean": clean,
    }


def _worktree_verification(repo_id: Any, worktree_path: Any, branch: Any) -> dict:
    if not all(isinstance(value, str) and value for value in (repo_id, worktree_path, branch)):
        raise WorkerError("bad_request", "worktree verification requires repo_id, worktree_path and branch")
    if worktree_ops.is_live_checkout_path(repo_id, worktree_path):
        return {"ok": False, "path": str(Path(worktree_path).resolve()), "reason": "refusing the live checkout"}
    verified = worktree_ops.verify_worktree(repo_id, worktree_path, branch)
    return {
        "ok": bool(verified.get("ok")),
        "path": verified.get("path") or str(Path(worktree_path).resolve()),
        "reason": None if verified.get("ok") else verified.get("reason", "worktree verification failed"),
    }


def _verb_worktree_verify(payload: dict) -> dict:
    return _worktree_verification(payload.get("repo_id"), payload.get("worktree_path"), payload.get("branch"))


def _existing_start_result(spool: Path) -> dict:
    state = _json_read(spool / "state.json")
    handle = state.get("handle")
    if not isinstance(handle, dict):
        for _ in range(20):
            time.sleep(0.01)
            state = _json_read(spool / "state.json")
            handle = state.get("handle")
            if isinstance(handle, dict):
                break
    if not isinstance(handle, dict):
        raise WorkerError("execution_failed", "execution spool exists without a worker handle")
    return {"accepted": True, "handle": handle, "reused": True}


def _verb_start(payload: dict) -> dict:
    execution_id = payload.get("execution_id")
    spool = _spool_path(execution_id)
    if spool.exists():
        return _existing_start_result(spool)
    kind = payload.get("kind")
    if kind == "noop-sleep":
        if os.getenv("AOTERU_WORKER_SELFTEST") != "1":
            raise WorkerError("bad_request", "noop-sleep is available only in worker self-test mode")
        _timeout(payload, 1.0)
    elif kind == "codex-write":
        lease = payload.get("lease")
        if not isinstance(lease, dict) or not isinstance(lease.get("lease_id"), str):
            raise WorkerError("bad_request", "codex-write start requires a lease")
        if not isinstance(payload.get("objective"), str):
            raise WorkerError("bad_request", "codex-write start requires objective")
        _timeout(payload, 1800.0)
        verified = _worktree_verification(
            payload.get("repo_id"), lease.get("worktree_path"), lease.get("branch"),
        )
        if not verified["ok"]:
            raise WorkerError("authority_denied", verified["reason"])
    else:
        raise WorkerError("bad_request", f"unsupported start kind {kind!r}")

    _SPOOL_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        spool.mkdir()
    except FileExistsError:
        return _existing_start_result(spool)
    try:
        _json_write(spool / "request.json", payload)
        root = str(Path(get_app_root()).resolve())
        handle = estate_worker_procs.spawn_detached(
            [sys.executable, "-m", "src.estate_worker", "--run-spooled", execution_id],
            root,
            str(spool / "worker.log"),
        )
        handle = {**handle, "spool_id": execution_id}
        _json_write(spool / "state.json", {
            "state": "accepted",
            "handle": handle,
            "started_at": None,
            "finished_at": None,
        })
    except Exception:
        shutil.rmtree(spool, ignore_errors=True)
        raise
    return {"accepted": True, "handle": handle, "reused": False}


def _verb_status(payload: dict) -> dict:
    execution_id = payload.get("execution_id")
    if set(payload) != {"execution_id"}:
        raise WorkerError("bad_request", "status requires only execution_id")
    spool = _spool_path(execution_id)
    state = _json_read(spool / "state.json")
    if not state:
        return {
            "state": "unknown", "handle": None, "process_alive": False,
            "started_at": None, "finished_at": None,
        }
    handle_value = state.get("handle")
    process_alive = estate_worker_procs.is_alive(handle_value) if isinstance(handle_value, dict) else False
    result = {
        "state": state.get("state", "unknown"),
        "handle": handle_value,
        "process_alive": process_alive,
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
    }
    result_value = _json_read(spool / "result.json")
    if result_value:
        result["result"] = result_value
    return result


def _verb_cancel(payload: dict) -> dict:
    execution_id = payload.get("execution_id")
    if set(payload) != {"execution_id"}:
        raise WorkerError("bad_request", "cancel requires only execution_id")
    spool = _spool_path(execution_id)
    state = _json_read(spool / "state.json")
    handle_value = state.get("handle")
    if not isinstance(handle_value, dict):
        raise WorkerError("not_found", f"execution {execution_id!r} was not found")
    outcome = estate_worker_procs.kill_tree(handle_value)
    if outcome.get("ok"):
        cancelled_result = {"ok": False, "error": "execution cancelled"}
        _json_write(spool / "result.json", cancelled_result)
        _json_write(spool / "state.json", {
            "state": "failed",
            "handle": handle_value,
            "pid": state.get("pid"),
            "started_at": state.get("started_at"),
            "finished_at": _utcnow(),
        })
    return {"killed": bool(outcome.get("ok")), "still_alive_pids": outcome.get("still_alive_pids", [])}


def _verb_worktree_finalize(payload: dict) -> dict:
    repo_id = payload.get("repo_id")
    worktree_path = payload.get("worktree_path")
    branch = payload.get("branch")
    commit_message = payload.get("commit_message")
    if not isinstance(commit_message, str) or not commit_message:
        raise WorkerError("bad_request", "worktree.finalize requires commit_message")
    verified = _worktree_verification(repo_id, worktree_path, branch)
    if not verified["ok"]:
        raise WorkerError("authority_denied", verified["reason"])
    path = verified["path"]
    branch_result = _run_git(path, ["branch", "--show-current"])
    if branch_result.returncode != 0 or branch_result.stdout.strip() != branch:
        raise WorkerError("authority_denied", "worktree branch changed before finalization")
    status_result = _run_git(path, ["status", "--porcelain"])
    if status_result.returncode != 0:
        raise WorkerError("execution_failed", status_result.stderr.strip() or "git status failed")
    dirty_paths = [line[3:] for line in status_result.stdout.splitlines() if line.strip()]
    if not dirty_paths:
        head = _run_git(path, ["rev-parse", "HEAD"])
        return {
            "committed": False,
            "pushed": False,
            "commit_sha": head.stdout.strip() if head.returncode == 0 else None,
            "dirty_paths": [],
        }
    added = _run_git(path, ["add", "--", *dirty_paths])
    if added.returncode != 0:
        raise WorkerError("execution_failed", added.stderr.strip() or "git add failed")
    committed = _run_git(path, ["commit", "-m", commit_message])
    if committed.returncode != 0:
        raise WorkerError("execution_failed", committed.stderr.strip() or "git commit failed")
    sha = _run_git(path, ["rev-parse", "HEAD"]).stdout.strip()
    pushed = _run_git(path, ["push", "origin", branch])
    result = {
        "committed": True,
        "pushed": pushed.returncode == 0,
        "commit_sha": sha,
        "dirty_paths": dirty_paths,
    }
    if pushed.returncode != 0:
        result["push_error"] = pushed.stderr.strip() or "git push failed"
    return result


def _run_spooled(execution_id: str) -> int:
    spool = _spool_path(execution_id)
    request = _json_read(spool / "request.json")
    state_path = spool / "state.json"
    initial = _json_read(state_path)
    for _ in range(500):
        if isinstance(initial.get("handle"), dict):
            break
        time.sleep(0.01)
        initial = _json_read(state_path)
    handle_value = initial.get("handle")
    if not isinstance(handle_value, dict):
        _json_write(spool / "result.json", {"ok": False, "error": "worker handle was not recorded"})
        _json_write(state_path, {
            "state": "failed", "handle": None, "pid": None,
            "started_at": None, "finished_at": _utcnow(),
        })
        return 1
    started_at = _utcnow()

    def on_started(pid: int) -> None:
        _json_write(state_path, {
            "state": "running",
            "handle": handle_value,
            "pid": pid,
            "started_at": started_at,
            "finished_at": None,
        })

    kind = request.get("kind")
    try:
        if kind == "noop-sleep" and os.getenv("AOTERU_WORKER_SELFTEST") == "1":
            on_started(os.getpid())
            time.sleep(_timeout(request, 1.0))
            result = {"ok": True, "output": "noop-sleep complete", "provider": "selftest"}
        elif kind == "codex-write":
            lease = request.get("lease") or {}
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
    _json_write(spool / "result.json", result)
    error_text = str(result.get("error", "")).lower()
    terminal = "succeeded" if result.get("ok") else ("timed_out" if "timed out" in error_text or "timeout" in error_text else "failed")
    current = _json_read(state_path)
    _json_write(state_path, {
        "state": terminal,
        "handle": current.get("handle", handle_value),
        "pid": current.get("pid"),
        "started_at": current.get("started_at") or started_at,
        "finished_at": _utcnow(),
    })
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="worker checkout root")
    parser.add_argument("--run-spooled", metavar="EXECUTION_ID")
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

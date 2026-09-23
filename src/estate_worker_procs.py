"""Host-local process primitives used by the estate worker."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Optional


class ProcessLayerError(RuntimeError):
    """Raised for a process-layer failure that needs a specific worker
    error code (currently only `executor_unavailable`, for a detached
    spawn refused by the host) rather than the generic `execution_failed`
    a bare exception maps to in `estate_worker.handle()`."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# Win32 constants (avoids a ctypes.wintypes/win32con dependency for the
# handful of values this module needs).
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_DETACHED_PROCESS = 0x00000008
_CREATE_BREAKAWAY_FROM_JOB = 0x01000000
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259


def _proc_stat_fields(pid: int) -> Optional[tuple[str, int, int]]:
    """(state, ppid, starttime) from /proc/<pid>/stat, the only
    dependency-free way to read this (no psutil in this codebase). The
    comm field is parenthesised and may itself contain spaces or
    parens, so split on the *last* ')' rather than whitespace-splitting
    the whole line -- everything after it is state/ppid/pgrp/session/...
    in fixed order; starttime (ticks since boot) is field 20 of that
    fixed order, i.e. rest[19] once state=rest[0]. starttime is what
    makes PID-reuse detection possible: two different process instances
    that happen to share a pid can never share a starttime."""
    try:
        with open(f"/proc/{pid}/stat", "r") as f:
            raw = f.read()
        rest = raw.rsplit(")", 1)[1].split()
        return rest[0], int(rest[1]), int(rest[19])  # state, ppid, starttime
    except (FileNotFoundError, ProcessLookupError, IndexError, ValueError, OSError):
        return None


def _proc_ppid(pid: int) -> Optional[int]:
    fields = _proc_stat_fields(pid)
    return fields[1] if fields else None


def _proc_is_live_nonzombie(pid: int, expected_starttime: Optional[int] = None) -> bool:
    """True only for a process that can still hold resources (pipes,
    CPU, an unreaped worktree lock, etc.) -- a zombie ('Z') already
    received its kill and is just awaiting reap by its parent (which,
    once its own leader has also been killed, is typically PID 1 taking
    over promptly, not instant). Re-scanning after a kill must not count
    an already-dead zombie as "still alive" merely because /proc/<pid>
    has not been removed yet.

    When expected_starttime is given, a pid whose current starttime
    doesn't match it is treated as gone (not "still alive") -- the
    original target already exited and this pid number has since been
    reused by an unrelated process; that unrelated process is not what
    the caller is waiting on."""
    fields = _proc_stat_fields(pid)
    if fields is None:
        return False
    state, _ppid, starttime = fields
    if expected_starttime is not None and starttime != expected_starttime:
        return False
    return state != "Z"


def _process_tree_pids(root_pid: int) -> dict[int, int]:
    """Every live descendant of root_pid (root included), found by
    scanning /proc rather than relying on process-group/session
    membership -- a descendant that has escaped into its own process
    group (observed live: a codex-spawned MCP server child calls
    something equivalent to setpgid(0, 0), landing in its own pgid
    while remaining in the parent's session) is still found here,
    because this walks real parent-child links instead. Returns
    {pid: starttime} rather than a bare list so a caller can later
    detect pid reuse (a killed pid's number reassigned to an unrelated
    process before cleanup gets to it) rather than trusting pid alone."""
    import os as _os
    children: dict[int, list[int]] = {}
    try:
        pids = [int(name) for name in _os.listdir("/proc") if name.isdigit()]
    except OSError:
        fields = _proc_stat_fields(root_pid)
        return {root_pid: fields[2] if fields else 0}
    for pid in pids:
        ppid = _proc_ppid(pid)
        if ppid is not None:
            children.setdefault(ppid, []).append(pid)
    tree = [root_pid]
    frontier = [root_pid]
    while frontier:
        next_frontier: list[int] = []
        for pid in frontier:
            for child in children.get(pid, []):
                if child not in tree:
                    tree.append(child)
                    next_frontier.append(child)
        frontier = next_frontier
    result: dict[int, int] = {}
    for pid in tree:
        fields = _proc_stat_fields(pid)
        result[pid] = fields[2] if fields else 0
    return result


def _kill_process_tree(root_pid: int, process_group_id: int, *, reap_timeout: float = 5.0) -> dict:
    """Timeout cleanup for a codex-launched process, robust to a
    descendant that has left the leader's process group. Kills both the
    process group (cheap, covers the common case, unchanged behaviour
    for a tree with no escapees) AND every PID found by walking real
    /proc parent-child links (covers an escapee like the observed MCP
    server child), then re-scans /proc to prove the whole tree is
    actually gone rather than assuming the kill succeeded. Fails closed:
    returns ok=False with the surviving pids if any remain, instead of
    silently reporting a clean kill.

    PID-reuse safe: every pid is snapshotted with its starttime before
    signalling and re-checked against that same starttime afterward, so
    a target that already exited and whose pid number has since been
    reused by an unrelated process is never signalled or reported as
    "still alive" -- the unrelated occupant is left alone either way.
    """
    import os as _os
    import signal as _signal
    import time as _time

    tree_before = _process_tree_pids(root_pid)  # {pid: starttime}

    try:
        _os.killpg(process_group_id, _signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        pass

    for pid, starttime in tree_before.items():
        current = _proc_stat_fields(pid)
        if current is None or current[2] != starttime:
            continue  # already gone, or this pid now belongs to someone else
        try:
            _os.kill(pid, _signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            pass

    deadline = _time.monotonic() + reap_timeout
    still_alive: list[int] = list(tree_before)
    while _time.monotonic() < deadline:
        still_alive = [
            pid for pid, starttime in tree_before.items()
            if _proc_is_live_nonzombie(pid, expected_starttime=starttime)
        ]
        if not still_alive:
            break
        _time.sleep(0.2)

    return {
        "ok": not still_alive,
        "attempted_pids": list(tree_before),
        "still_alive_pids": still_alive,
    }


def _win_configure_kernel32(kernel32) -> None:
    """Declare explicit ctypes argtypes/restype for every Win32 call this
    module makes (Stage 4 review finding). Left undeclared, ctypes
    assumes 32-bit `c_int` for both arguments and return value; a HANDLE
    is pointer-sized (64-bit on Win64), so an undeclared `OpenProcess`
    return value or `GetProcessTimes`/`GetExitCodeProcess`/`CloseHandle`
    handle argument can be silently truncated instead of raising -- the
    kind of defect that only shows up as a rare, unreproducible handle
    mismatch in the field. Idempotent: safe to call on every access,
    real ctypes function pointers cache the assigned types."""
    from ctypes import wintypes
    import ctypes

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL


def _win_creation_time(handle) -> Optional[int]:
    """Read a Windows process's creation time (100ns ticks since 1601,
    the same units GetProcessTimes always returns) from an already-open
    handle -- the pid-reuse-safety anchor `is_alive`/`kill_tree` compare
    against, same role `/proc/<pid>/stat`'s starttime field plays on
    Linux."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    _win_configure_kernel32(kernel32)
    creation, exit_time, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
    ok = kernel32.GetProcessTimes(
        handle, ctypes.byref(creation), ctypes.byref(exit_time),
        ctypes.byref(kernel_time), ctypes.byref(user_time),
    )
    if not ok:
        return None
    return (creation.dwHighDateTime << 32) | creation.dwLowDateTime


def _win_open_process(pid: int):
    import ctypes

    kernel32 = ctypes.windll.kernel32
    _win_configure_kernel32(kernel32)
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    return handle or None


def spawn_detached(argv: list[str], cwd: str, log_path: str) -> dict[str, int]:
    """Start one detached process (Windows or Linux) and return its PID
    identity."""
    if os.name == "nt":
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as log_file:
            try:
                proc = subprocess.Popen(
                    argv,
                    cwd=cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    creationflags=(
                        _CREATE_NEW_PROCESS_GROUP | _DETACHED_PROCESS | _CREATE_BREAKAWAY_FROM_JOB
                    ),
                    close_fds=True,
                )
            except OSError as exc:
                raise ProcessLayerError(
                    "executor_unavailable",
                    f"detached spawn not permitted in this session: {exc}",
                ) from exc
        create_time = _win_creation_time(int(proc._handle))
        if create_time is None:
            raise ProcessLayerError(
                "executor_unavailable", f"could not read creation time for spawned pid {proc.pid}",
            )
        return {"pid": proc.pid, "create_time": create_time}
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as log_file:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    fields = _proc_stat_fields(proc.pid)
    if fields is None:
        raise RuntimeError(f"spawned process {proc.pid} has no readable /proc starttime")
    return {"pid": proc.pid, "create_time": fields[2]}


def is_alive(handle: dict) -> bool:
    """Return true only while the same, non-zombie/non-exited process is
    present, matched by creation time so a reused pid is never mistaken
    for the original."""
    try:
        pid = int(handle["pid"])
        create_time = int(handle["create_time"])
    except (KeyError, TypeError, ValueError):
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        win_handle = _win_open_process(pid)
        if win_handle is None:
            return False
        kernel32 = ctypes.windll.kernel32
        _win_configure_kernel32(kernel32)
        try:
            if _win_creation_time(win_handle) != create_time:
                return False
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(win_handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == _STILL_ACTIVE
        finally:
            kernel32.CloseHandle(win_handle)
    return _proc_is_live_nonzombie(pid, expected_starttime=create_time)


def kill_tree(handle: dict) -> dict:
    """Kill a detached process tree without ever targeting a reused PID
    for the *liveness check* above `taskkill` -- `is_alive()` compares
    Win32 `GetProcessTimes` creation time (or /proc/<pid>/stat starttime
    on Linux) against the handle's recorded `create_time` before this
    function ever signals anything.

    Residual, accepted race on Windows (truthful guarantee, not an
    absolute one): `taskkill /PID <pid> /T /F` is the only tool-provided
    way to kill a whole process tree by pid without this module
    reimplementing Win32 process-tree enumeration and termination itself
    (out of scope -- "do not expand this into a new Windows process
    framework"), and `taskkill` takes a bare pid with no creation-time
    argument. So there is an unavoidable, narrow window between the
    `is_alive()` check above and `taskkill` actually signalling the
    process where that pid could in theory have already been reused by
    an unrelated process. Linux's `_kill_process_tree` below does not
    have this gap -- it signals via `os.kill`/`os.killpg` directly and
    re-verifies every pid's starttime both before signalling and after,
    with no external tool in between."""
    try:
        pid = int(handle["pid"])
    except (KeyError, TypeError, ValueError):
        return {"ok": False, "attempted_pids": [], "still_alive_pids": []}
    if not is_alive(handle):
        return {"ok": True, "attempted_pids": [], "still_alive_pids": []}
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if not is_alive(handle):
                return {"ok": True, "attempted_pids": [pid], "still_alive_pids": []}
            time.sleep(0.2)
        return {"ok": False, "attempted_pids": [pid], "still_alive_pids": [pid]}
    return _kill_process_tree(pid, pid)


# ---------------------------------------------------------------------
# Stage 6 (plan §6.0 S6.12): cgroup-scoped runner units and tree quiescence
# ---------------------------------------------------------------------

_CGROUP_ROOT = Path("/sys/fs/cgroup")
# Bounded unit cleanup (gate round 10): `systemctl --user kill` may take at
# most KILL_UNIT_TIMEOUT_S, and run_in_unit then proves the cgroup quiescent
# within UNIT_STOP_PROOF_S. A timed-out verify unit therefore lives at most
# its run limit + KILL_UNIT_TIMEOUT_S + UNIT_STOP_PROOF_S.
KILL_UNIT_TIMEOUT_S = 5.0
UNIT_STOP_PROOF_S = 15.0
# Environment a runner unit inherits. A transient user service starts from
# the user manager's environment, not the caller's, so only these are
# forwarded explicitly (plus every AOTERU_* variable).
_RUNNER_ENV_KEYS = ("HOME", "PATH", "LANG", "LC_ALL", "USER", "LOGNAME", "CODEX_HOME", "PYTHONPATH")


def _user_manager_env() -> dict:
    env = dict(os.environ)
    if hasattr(os, "getuid"):
        env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return env


def own_cgroup() -> Optional[str]:
    """This process's cgroup v2 path (`/proc/self/cgroup` `0::<path>`), or
    None when unavailable (non-Linux, cgroup v1 only)."""
    try:
        for line in Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines():
            if line.startswith("0::"):
                return line[3:].strip() or None
    except OSError:
        return None
    return None


def cgroup_is_dedicated(cgroup: Optional[str], unit: Optional[str]) -> bool:
    """True only for the runner's own dedicated `<unit>` cgroup -- never the
    root cgroup or any shared slice (plan S6.12)."""
    if not cgroup or not unit or not unit.startswith("aoteru-") or not unit.endswith(".service"):
        return False
    return cgroup.rstrip("/").endswith("/" + unit)


def spawn_runner_unit(argv: list[str], cwd: str, log_path: str, unit: str) -> dict:
    """Launch a worker runner as a transient systemd *user service* whose
    cgroup contains every descendant (S6.12). Service mode, never
    `--scope`: a scope migrates the calling process, which cgroup v2 does
    not allow an unprivileged user to do from the backend's system-service
    cgroup. Returns the unit name only -- the canonical runner handle is
    what the runner itself records in its `run.json` decision.

    Windows has no job-object implementation yet, so there is no runner
    unit there; callers must gate on `runner_units_supported()` first."""
    if os.name == "nt":
        raise ProcessLayerError("executor_unavailable", "runner units are not implemented on Windows (S6.12)")
    if not unit.startswith("aoteru-"):
        raise ValueError(f"runner unit {unit!r} must be a dedicated aoteru-* unit")
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    command = [
        "systemd-run", "--user", f"--unit={unit}", "--collect", "--quiet",
        f"--working-directory={cwd}",
        "-p", f"StandardOutput=append:{log_path}", "-p", f"StandardError=append:{log_path}",
    ]
    for key in _RUNNER_ENV_KEYS:
        if os.environ.get(key):
            command.append(f"--setenv={key}={os.environ[key]}")
    for key, value in os.environ.items():
        if key.startswith("AOTERU_"):
            command.append(f"--setenv={key}={value}")
    command += ["--", *argv]
    try:
        completed = subprocess.run(command, env=_user_manager_env(), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProcessLayerError("executor_unavailable", f"systemd-run failed to launch {unit}: {exc}") from exc
    if completed.returncode != 0:
        raise ProcessLayerError(
            "executor_unavailable",
            f"systemd-run refused {unit}: {(completed.stderr or completed.stdout).strip()[-400:]}",
        )
    return {"unit": f"{unit}.service"}


_RUNNER_UNITS_PROBE: dict = {}


def runner_units_supported() -> tuple[bool, str]:
    """Per-process probe (S6.12): a transient user unit must start and report
    its own dedicated `aoteru-probe-*.service` cgroup. Cached for the life
    of this (per-call) worker process."""
    if "result" in _RUNNER_UNITS_PROBE:
        return _RUNNER_UNITS_PROBE["result"]
    if os.name == "nt":
        result = (False, "runner units are not implemented on Windows (S6.12 job objects pending, B12)")
    else:
        import uuid
        unit = f"aoteru-probe-{uuid.uuid4().hex}"
        try:
            completed = subprocess.run(
                ["systemd-run", "--user", f"--unit={unit}", "--collect", "--quiet", "--wait", "--pipe",
                 "--", "cat", "/proc/self/cgroup"],
                env=_user_manager_env(), capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            result = (False, f"systemd-run --user unavailable: {exc}")
        else:
            cgroup = next((line[3:].strip() for line in completed.stdout.splitlines() if line.startswith("0::")), None)
            if completed.returncode == 0 and cgroup_is_dedicated(cgroup, f"{unit}.service"):
                result = (True, f"transient user units ok ({cgroup})")
            else:
                detail = (completed.stderr or completed.stdout).strip()[-300:]
                result = (False, f"runner unit probe failed (rc={completed.returncode}): {detail or cgroup}")
    _RUNNER_UNITS_PROBE["result"] = result
    return result


def tree_quiescent(handle: Optional[dict]) -> Optional[bool]:
    """S6.12: True only when the runner's recorded dedicated cgroup is gone
    or reports `populated 0` (cgroup v2 `populated` is recursive, so a
    `setsid`'d descendant still counts). False while populated. None when
    it cannot be proven -- no recorded/dedicated cgroup, unreadable
    cgroupfs, or Windows. Callers treat None exactly like False."""
    if os.name == "nt" or not isinstance(handle, dict):
        return None
    cgroup, unit = handle.get("cgroup"), handle.get("unit")
    if not cgroup_is_dedicated(cgroup, unit):
        return None
    if not _CGROUP_ROOT.is_dir():
        return None
    path = _CGROUP_ROOT / cgroup.lstrip("/")
    try:
        events = (path / "cgroup.events").read_text(encoding="utf-8")
    except FileNotFoundError:
        # The unit embeds a unique id, so a missing cgroup was removed
        # after emptying and can never be a reused one.
        return True
    except OSError:
        return None
    for line in events.splitlines():
        if line.startswith("populated "):
            return line.split()[1] == "0"
    return None


def kill_unit(unit: Optional[str]) -> dict:
    """SIGKILL every process in a runner unit's cgroup (all descendants)."""
    if os.name == "nt" or not unit:
        return {"ok": False, "detail": "no runner unit"}
    try:
        completed = subprocess.run(
            ["systemctl", "--user", "kill", "--signal=KILL", unit],
            env=_user_manager_env(), capture_output=True, text=True, timeout=KILL_UNIT_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "detail": str(exc)}
    # A unit that already stopped and was collected is "not loaded": fine.
    return {"ok": completed.returncode == 0 or "not loaded" in (completed.stderr or ""),
            "detail": (completed.stderr or "").strip()}


def run_in_unit(argv: list[str], cwd: str, unit: str, *, timeout: float = 60.0,
                input_text: Optional[str] = None) -> subprocess.CompletedProcess:
    """Run a short worktree-touching command synchronously in its own
    transient user unit (6c adjudication finding 2). `--wait` returns only
    once the unit is inactive, and `SendSIGKILL`/`TimeoutStopSec` bound the
    stop, so every descendant (an fsmonitor daemon, a filter process) is
    gone when this returns. Linux only; callers gate on
    runner_units_supported()."""
    if os.name == "nt":
        raise ProcessLayerError("executor_unavailable", "runner units are not implemented on Windows (S6.12)")
    command = [
        "systemd-run", "--user", f"--unit={unit}", "--collect", "--quiet", "--wait", "--pipe",
        f"--working-directory={cwd}", "-p", "TimeoutStopSec=5", "-p", "SendSIGKILL=yes",
        "-p", "KillMode=control-group",
    ]
    for key in _RUNNER_ENV_KEYS:
        if os.environ.get(key):
            command.append(f"--setenv={key}={os.environ[key]}")
    for key, value in os.environ.items():
        if key.startswith(("AOTERU_", "GIT_CONFIG_", "GIT_OPTIONAL_LOCKS")):
            command.append(f"--setenv={key}={value}")
    command += ["--", *argv]
    try:
        return subprocess.run(command, env=_user_manager_env(), capture_output=True, text=True,
                              timeout=timeout, input=input_text)
    except subprocess.TimeoutExpired as exc:
        # The client timing out proves nothing about the unit (6d
        # adjudication finding 1): stop it and prove its cgroup quiescent
        # before reporting; otherwise the unit stays visible to
        # verify_units_quiescent() and every later check fails closed.
        kill_unit(f"{unit}.service")
        handle = {"cgroup": f"{_app_slice()}/{unit}.service", "unit": f"{unit}.service"}
        deadline = time.monotonic() + UNIT_STOP_PROOF_S
        while time.monotonic() < deadline and tree_quiescent(handle) is not True:
            time.sleep(0.2)
        state = "stopped" if tree_quiescent(handle) is True else "NOT proven stopped"
        raise ProcessLayerError("executor_unavailable",
                                f"verification unit {unit} timed out and was {state}") from exc
    except OSError as exc:
        raise ProcessLayerError("executor_unavailable", f"systemd-run --wait failed for {unit}: {exc}") from exc


def _app_slice() -> str:
    uid = os.getuid() if hasattr(os, "getuid") else 0
    return f"/user.slice/user-{uid}.slice/user@{uid}.service/app.slice"


def verify_units_quiescent(scope: Optional[str] = None) -> Optional[bool]:
    """True when no `aoteru-verify-*` unit is loaded in a live state (6d
    adjudication finding 1): a timed-out verification that could not be
    proven stopped keeps every later verification and closure fail-closed
    until it is gone. None when systemd cannot be asked."""
    if os.name == "nt":
        return None
    try:
        completed = subprocess.run(
            ["systemctl", "--user", "list-units", "--all", "--no-legend", "--plain",
             f"aoteru-verify-{scope}-*" if scope else "aoteru-verify-*"],
            env=_user_manager_env(), capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[0].startswith("aoteru-verify-") and fields[2] not in ("inactive", "failed"):
            return False
    return True

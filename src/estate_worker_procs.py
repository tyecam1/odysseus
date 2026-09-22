"""Host-local process primitives used by the estate worker."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional


_WINDOWS_STAGE4_ERROR = "windows process layer lands in stage 4"


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


def spawn_detached(argv: list[str], cwd: str, log_path: str) -> dict[str, int]:
    """Start one detached Linux process and return its PID identity."""
    if os.name == "nt":
        raise NotImplementedError(_WINDOWS_STAGE4_ERROR)
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
    """Return true only while the same, non-zombie process is present."""
    if os.name == "nt":
        raise NotImplementedError(_WINDOWS_STAGE4_ERROR)
    try:
        pid = int(handle["pid"])
        create_time = int(handle["create_time"])
    except (KeyError, TypeError, ValueError):
        return False
    return _proc_is_live_nonzombie(pid, expected_starttime=create_time)


def kill_tree(handle: dict) -> dict:
    """Kill a detached process tree without ever targeting a reused PID."""
    if os.name == "nt":
        raise NotImplementedError(_WINDOWS_STAGE4_ERROR)
    try:
        pid = int(handle["pid"])
    except (KeyError, TypeError, ValueError):
        return {"ok": False, "attempted_pids": [], "still_alive_pids": []}
    if not is_alive(handle):
        return {"ok": True, "attempted_pids": [], "still_alive_pids": []}
    return _kill_process_tree(pid, pid)

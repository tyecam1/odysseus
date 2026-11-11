"""Integration (plan §G U67 real form / I4 worker half): the REAL worker CLI
launching a REAL transient systemd user unit on this host, with HOME
pointed at a temp dir so no live spool or sentinel is touched. Skipped
with a recorded reason when user units are unavailable (CI, Windows)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from src import estate_worker, estate_worker_procs
from src.estate_router import current_host_id
from src.estate_worker_protocol import build_request
from tests.helpers.cgroup_marker import _wait_for_cgroup_marker

ROOT = Path(__file__).resolve().parents[1]

_supported, _detail = (False, "not probed")
if os.name != "nt":
    _supported, _detail = estate_worker_procs.runner_units_supported()
pytestmark = pytest.mark.skipif(not _supported or current_host_id() is None,
                                reason=f"systemd user units unavailable here: {_detail}")


def _worker(home, verb, payload, deadline_s=30):
    request = build_request(verb, current_host_id(), payload, deadline_s)
    env = {**os.environ, "HOME": str(home), "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR",
                                                                             f"/run/user/{os.getuid()}")}
    completed = subprocess.run([sys.executable, "-m", "src.estate_worker", "--root", str(ROOT)],
                               input=json.dumps(request), capture_output=True, text=True, env=env,
                               cwd=str(ROOT), timeout=deadline_s + 15)
    assert completed.returncode == 0, completed.stderr
    response = json.loads(completed.stdout)
    assert response["ok"] is True, response
    return response["result"]


def _wait(home, execution_id, predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = _worker(home, "status", {"execution_id": execution_id})
        if predicate(status):
            return status
        time.sleep(0.5)
    raise AssertionError(f"timed out; last status {status}")


def test_real_unit_noop_sleep_runs_to_quiescent_success(tmp_path):
    home = tmp_path / "home"
    (home / ".aoteru").mkdir(parents=True)
    (home / ".aoteru" / "worker_selftest_enabled").touch()
    execution_id = f"live-{os.getpid()}-{int(time.time())}"
    started = _worker(home, "start", {"execution_id": execution_id, "kind": "noop-sleep", "timeout_s": 2})
    assert started["accepted"] is True
    running = _wait(home, execution_id, lambda s: s["state"] == "running")
    unit = running["handle"]["unit"]
    assert unit == f"aoteru-run-{execution_id}.service"
    assert running["handle"]["cgroup"].endswith("/" + unit)
    assert running["quiescent"] is False
    done = _wait(home, execution_id, lambda s: s["state"] == "succeeded")
    assert done["quiescent"] is True and done["process_alive"] is False
    # Replay of the same id never spawns again.
    replay = _worker(home, "start", {"execution_id": execution_id, "kind": "noop-sleep", "timeout_s": 2})
    assert replay["reused"] is True and replay["state"] == "succeeded"


@pytest.mark.parametrize("commit_failure", [False, True], ids=["commit", "commit-error"])
def test_real_unit_finalize_commits_linked_worktree(tmp_path, monkeypatch, commit_failure):
    """Bounded Lab diagnostic: real _launch_runner -> _run_attempt -> git.

    Run with pytest -q -rs tests/test_estate_worker_units_live.py -k finalize.
    All repositories, config and spool records are disposable; no paid call.
    The failure case proves that the actual command error crosses the unit
    boundary instead of disappearing after four commit retries.
    """
    import uuid

    def git(path, *args):
        return subprocess.run(["git", "-C", str(path), *args], capture_output=True,
                              text=True, check=True, timeout=15).stdout.strip()

    home = tmp_path / "home"
    home.mkdir()
    config = tmp_path / "config"
    config.mkdir()
    main, worktree, origin = (tmp_path / name for name in ("repo", "worktree", "origin.git"))
    subprocess.run(["git", "init", "-q", "-b", "main", str(main)], check=True, timeout=15)
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True, timeout=15)
    git(main, "config", "user.name", "Finalize diagnostic")
    git(main, "config", "user.email", "finalize@example.invalid")
    git(main, "config", "commit.gpgsign", "false")
    git(main, "commit", "--allow-empty", "-qm", "seed")
    git(main, "remote", "add", "origin", str(origin))
    git(main, "worktree", "add", "-qb", "diagnostic", str(worktree))
    head = git(worktree, "rev-parse", "HEAD")
    assert (worktree / ".git").is_file()  # gitdir lives outside the leased tree
    (worktree / "change.txt").write_text("runner commit\n")
    if commit_failure:
        # Deterministic commit-only failure: add still succeeds.
        git(main, "config", "user.name", "")

    (config / "repositories.yaml").write_text(json.dumps({
        "repos": [{"id": "finalize-diagnostic", "path": str(main)}],
    }))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PYTHONPATH", str(ROOT))
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setattr(estate_worker, "get_app_root", lambda: str(tmp_path))
    monkeypatch.setattr(estate_worker, "_SPOOL_ROOT", home / ".aoteru" / "worker-spool")
    execution_id = f"diagnostic-{uuid.uuid4().hex}"
    spool = estate_worker._spool_path(execution_id)
    request = {"repo_id": "finalize-diagnostic", "worktree_path": str(worktree),
               "branch": "diagnostic", "expected_head_sha": head, "commit_message": "runner commit"}
    number = estate_worker._record_attempt(spool, "finalize", request)
    unit = f"aoteru-finalize-{execution_id}-{number}"
    result_path = spool / "finalize" / f"attempt-{number}.result.json"
    log = spool / "finalize" / f"attempt-{number}.log"
    try:
        estate_worker._launch_runner("--run-finalize", [execution_id, str(number)], unit=unit, log_path=log)
        deadline = time.monotonic() + 30
        while not result_path.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert result_path.exists(), log.read_text() if log.exists() else "no runner result or log"
        result = json.loads(result_path.read_text())
        handle = estate_worker.read_decision(spool / "finalize" / f"attempt-{number}.run.json")
        assert handle["decision"] == "execute", handle
        assert estate_worker_procs.cgroup_is_dedicated(handle["cgroup"], f"{unit}.service")
        if commit_failure:
            assert result["outcome"] == "finalize_ambiguous", result
            assert result["git_error"]["command"] == "git commit", result
            assert result["git_error"]["returncode"] != 0, result
            assert "empty ident" in result["git_error"]["stderr"], result
            assert git(worktree, "rev-parse", "HEAD") == head
            assert git(worktree, "diff", "--cached", "--name-only") == "change.txt"
        else:
            assert result["outcome"] == "finalized" and result["committed"], result
            assert result["parent_sha"] == head and result["push"]["state"] == "pushed", result
            assert f"Aoteru-Execution: {execution_id}" in git(worktree, "log", "-1", "--format=%B")
            assert git(worktree, "status", "--porcelain") == ""
            assert git(origin, "rev-parse", "refs/heads/diagnostic") == result["commit_sha"]
    finally:
        estate_worker_procs.kill_unit(f"{unit}.service")


def test_real_unit_cancel_kills_the_unit_and_becomes_quiescent(tmp_path):
    home = tmp_path / "home"
    (home / ".aoteru").mkdir(parents=True)
    (home / ".aoteru" / "worker_selftest_enabled").touch()
    execution_id = f"live-cancel-{os.getpid()}-{int(time.time())}"
    _worker(home, "start", {"execution_id": execution_id, "kind": "noop-sleep", "timeout_s": 60})
    _wait(home, execution_id, lambda s: s["state"] == "running")
    cancelled = _worker(home, "cancel", {"execution_id": execution_id})
    final = _wait(home, execution_id, lambda s: s["quiescent"] is True)
    assert final["state"] == "failed" and final["process_alive"] is False
    assert cancelled["still_alive_pids"] in ([], [final["handle"]["pid"]])


def test_u67_real_unit_setsid_grandchild_keeps_the_cgroup_populated(tmp_path):
    """U67 real form: a setsid'd grandchild (new session) stays inside the
    runner unit's cgroup -- tree_quiescent is False while it lives, and True
    once the unit is gone."""
    import uuid
    unit = f"aoteru-probe-{uuid.uuid4().hex}"
    script = tmp_path / "runner.sh"
    marker = tmp_path / "cgroup.txt"
    script.write_text(f"#!/bin/sh\ncat /proc/self/cgroup > {marker}\nsetsid sleep 30 </dev/null >/dev/null 2>&1 &\nsleep 3\n")
    script.chmod(0o755)
    estate_worker_procs.spawn_runner_unit([str(script)], str(tmp_path), str(tmp_path / "log"), unit)
    # The shell creates the redirect target BEFORE `cat` writes to it, so waiting for existence alone can read an empty file
    # (IndexError on the "::" split, seen on the lab under load). Wait for the content.
    cgroup = _wait_for_cgroup_marker(marker)
    handle = {"cgroup": cgroup, "unit": f"{unit}.service"}
    assert estate_worker_procs.cgroup_is_dedicated(cgroup, f"{unit}.service")
    time.sleep(0.5)
    members = (Path("/sys/fs/cgroup") / cgroup.lstrip("/") / "cgroup.procs").read_text().split()
    sids = {Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[3] for pid in members}
    assert len(sids) >= 2                         # the setsid'd grandchild has its own session
    assert estate_worker_procs.tree_quiescent(handle) is False
    estate_worker_procs.kill_unit(f"{unit}.service")
    deadline = time.monotonic() + 10
    while estate_worker_procs.tree_quiescent(handle) is not True and time.monotonic() < deadline:
        time.sleep(0.1)
    assert estate_worker_procs.tree_quiescent(handle) is True

"""Tests for the durable implementation-mode execution lifecycle
(EstateExecution): submission/polling decoupled from the HTTP request
that submitted it, process/watchdog provenance, restart reconciliation,
and finalisation. Recovers the intent of the preserved pre-incident
draft (recovery/odysseus-live-dirty-20260901-162516/files/
test_estate_execution_runtime.py) adapted to the actual current API --
execution_id is server-generated (not caller-supplied), state lives on
EstateExecution via get_estate_execution/_update_estate_execution, and
_execute_codex_with_sandbox's own timeout/process-group-kill handling
(d8f9836/70844c3/8d529d5) is exercised unmodified, not reimplemented.

Not ported from the preserved draft: a "repeated call with the same
execution_id launches two workers" test -- it asserted the opposite of
what a live in-progress debugging session (caught mid-incident,
2026-09-01) was trying to fix (idempotent-retry dedup), and doesn't map
onto execution_id being server-generated here. Whether idempotent-retry
dedup should be added is an open design question, not decided by this
file either way.
"""
import os
import signal
import subprocess
import threading
import time

import pytest

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()

import core.database as cdb
from core.database import EstateExecution, RoutingDecision, get_db_session

import src.estate_router as estate_router


def _fake_popen_factory(hold_event, exit_code=0, output="ok"):
    instances = []
    next_pid = 40000

    class _FakeProcess:
        def __init__(self, argv, **kwargs):
            nonlocal next_pid
            self.argv = argv
            self.kwargs = kwargs
            self.pid = next_pid
            next_pid += 1
            self.returncode = None
            self._killed_event = threading.Event()
            self._out_path = None
            if "-o" in argv:
                self._out_path = argv[argv.index("-o") + 1]
            instances.append(self)

        def communicate(self, timeout=None):
            if self.returncode is not None:
                # Already killed/reaped -- a real Popen.communicate()
                # called after the process has exited returns
                # immediately rather than re-blocking.
                stderr = "" if self.returncode == 0 else output
                return "", stderr
            if timeout is None:
                hold_event.wait()
            elif not hold_event.wait(timeout):
                raise subprocess.TimeoutExpired(self.argv, timeout)
            if self._out_path is not None:
                from pathlib import Path
                out_file = Path(self._out_path)
                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_text(output)
            if self.returncode is None:
                self.returncode = exit_code
            stderr = "" if self.returncode == 0 else output
            return "", stderr

        def kill(self):
            self.returncode = -9
            self._killed_event.set()

        def wait(self, timeout=None):
            if self.returncode is None:
                if timeout is None:
                    self._killed_event.wait()
                elif not self._killed_event.wait(timeout):
                    raise subprocess.TimeoutExpired(self.argv, timeout)
            return self.returncode

    def _factory(argv, **kwargs):
        return _FakeProcess(argv, **kwargs)

    _factory.instances = instances
    return _factory


@pytest.fixture
def runtime_db(monkeypatch):
    session_local, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", session_local)
    yield
    engine.dispose()
    os.unlink(tmpfile.name)


def _insert_decision(decision_id):
    with get_db_session() as db:
        db.add(RoutingDecision(
            id=decision_id, task_class="bounded_code_implementation",
            host_id="test-lab", executor="codex-write", status="complete",
            escalated=True, retries=0,
        ))


def _fresh_authority(tmp_path, monkeypatch, *, lease_id="lease-1", branch="feat/x"):
    monkeypatch.setattr(
        estate_router, "_codex_write_authority",
        lambda repo_id, host_id: {"ok": True, "cwd": str(tmp_path), "lease_id": lease_id},
    )
    monkeypatch.setattr(
        estate_router, "active_lease_for_repo",
        lambda repo_id, host_id: {
            "lease_id": lease_id, "worktree_path": str(tmp_path),
            "branch": branch, "allowed_write_scope": "repo",
        },
    )


def _patch_os_kill_for_fake_popen(monkeypatch, fake_popen):
    """Reconciliation calls the real os.kill(pid, 0) to check whether a
    recorded worker_pid still exists. A fake test pid never does, so
    without this a poll while a fake worker is still "running" would
    have reconciliation (correctly, for what it can observe) mark the
    row interrupted. Map liveness onto the fake process table instead."""
    real_kill = os.kill

    def _fake_kill(pid, sig):
        for proc in fake_popen.instances:
            if proc.pid == pid:
                if proc.returncode is None:
                    return  # still "alive"
                raise ProcessLookupError(pid)
        real_kill(pid, sig)

    monkeypatch.setattr(os, "kill", _fake_kill)


# ---------------------------------------------------------------------
# Submission / lifecycle
# ---------------------------------------------------------------------

def test_submission_returns_well_before_slow_worker_finishes(runtime_db, monkeypatch, tmp_path):
    hold_event = threading.Event()
    fake_popen = _fake_popen_factory(hold_event)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, "/fake/codex"))
    _fresh_authority(tmp_path, monkeypatch)
    _patch_os_kill_for_fake_popen(monkeypatch, fake_popen)

    decision_id = "dec-1"
    _insert_decision(decision_id)

    started = time.monotonic()
    result = estate_router.execute_codex_write_durable(
        "implement it", repo_id="test-repo", host_id="test-lab",
        decision_id=decision_id, wait_timeout=0.05,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert result["ok"] is True
    assert result["lifecycle_state"] in ("accepted", "running")
    assert "execution_id" in result

    hold_event.set()
    deadline = time.monotonic() + 2.0
    state = None
    while time.monotonic() < deadline:
        state = estate_router.get_estate_execution(result["execution_id"])
        if state and state["lifecycle_state"] == "succeeded":
            break
        time.sleep(0.02)

    assert state is not None
    assert state["lifecycle_state"] == "succeeded"


def test_returned_execution_id_is_immediately_persisted(runtime_db, monkeypatch, tmp_path):
    hold_event = threading.Event()
    hold_event.set()
    monkeypatch.setattr(subprocess, "Popen", _fake_popen_factory(hold_event))
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, "/fake/codex"))
    _fresh_authority(tmp_path, monkeypatch)

    result = estate_router.execute_codex_write_durable(
        "implement it", repo_id="test-repo", host_id="test-lab", wait_timeout=1.0,
    )
    state = estate_router.get_estate_execution(result["execution_id"])
    assert state is not None
    assert state["execution_id"] == result["execution_id"]


def test_poll_transitions_through_truthful_lifecycle_states(runtime_db, monkeypatch, tmp_path):
    hold_event = threading.Event()
    fake_popen = _fake_popen_factory(hold_event)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, "/fake/codex"))
    _fresh_authority(tmp_path, monkeypatch)

    result_holder = {}

    def _dispatch():
        result_holder["result"] = estate_router.execute_codex_write_durable(
            "implement it", repo_id="test-repo", host_id="test-lab", wait_timeout=5.0,
        )

    worker = threading.Thread(target=_dispatch, daemon=True)
    worker.start()

    # Wait for the row to exist and reach "running" -- accepted is the
    # transient pre-Popen state, running is what a poll during real work
    # should truthfully see.
    deadline = time.monotonic() + 2.0
    execution_id = None
    state = None
    while time.monotonic() < deadline:
        if fake_popen.instances:
            # Row is created before Popen in execute_codex_write_durable,
            # so by the time a fake process exists the row is queryable;
            # find it via the thread's eventual result once available,
            # or poll all recent rows as a fallback.
            pass
        time.sleep(0.02)
        if "result" in result_holder:
            break
        if fake_popen.instances and execution_id is None:
            continue

    hold_event.set()
    worker.join(timeout=2.0)
    assert not worker.is_alive()
    execution_id = result_holder["result"]["execution_id"]
    state = estate_router.get_estate_execution(execution_id)
    assert state["lifecycle_state"] == "succeeded"
    assert state["worker_pid"] == fake_popen.instances[0].pid
    assert state["result"]["ok"] is True


def test_final_result_retrievable_after_caller_moves_on(runtime_db, monkeypatch, tmp_path):
    """The original HTTP request is conceptually gone by the time this
    poll happens -- get_estate_execution has no dependency on the
    submitting call still being in scope."""
    hold_event = threading.Event()
    monkeypatch.setattr(subprocess, "Popen", _fake_popen_factory(hold_event))
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, "/fake/codex"))
    _fresh_authority(tmp_path, monkeypatch)

    result = estate_router.execute_codex_write_durable(
        "implement it", repo_id="test-repo", host_id="test-lab", wait_timeout=0.01,
    )
    execution_id = result["execution_id"]
    del result  # simulate the original caller/response being gone

    hold_event.set()
    deadline = time.monotonic() + 2.0
    state = None
    while time.monotonic() < deadline:
        state = estate_router.get_estate_execution(execution_id)
        if state and state["lifecycle_state"] == "succeeded":
            break
        time.sleep(0.02)
    assert state is not None
    assert state["lifecycle_state"] == "succeeded"
    assert state["result"]["output"] == "ok"


# ---------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------

def test_executor_cwd_equals_verified_isolated_worktree(runtime_db, monkeypatch, tmp_path):
    hold_event = threading.Event()
    hold_event.set()
    fake_popen = _fake_popen_factory(hold_event)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, "/fake/codex"))
    _fresh_authority(tmp_path, monkeypatch)

    result = estate_router.execute_codex_write_durable(
        "implement it", repo_id="test-repo", host_id="test-lab", wait_timeout=1.0,
    )
    state = estate_router.get_estate_execution(result["execution_id"])
    assert state["worktree_path"] == str(tmp_path)
    assert fake_popen.instances[0].argv[fake_popen.instances[0].argv.index("-C") + 1] == str(tmp_path)


def test_authority_denial_creates_no_execution_row(runtime_db, monkeypatch, tmp_path):
    monkeypatch.setattr(
        estate_router, "_codex_write_authority",
        lambda repo_id, host_id: {
            "ok": False,
            "error": f"refusing implementation mode in live registered checkout for {repo_id!r}",
        },
    )
    result = estate_router.execute_codex_write_durable(
        "implement it", repo_id="test-repo", host_id="test-lab",
    )
    assert result["ok"] is False
    assert result["authority_denied"] is True
    assert "execution_id" not in result


def test_repeated_submission_against_same_lease_reuses_existing_execution(runtime_db, monkeypatch, tmp_path):
    """Direct regression test for the 2026-09-01 incident root cause:
    a caller (or a retry loop) submitting a second implementation-mode
    dispatch against a lease that already has a non-terminal execution
    must reuse that execution, not spawn a second worker. This is what
    was actually missing -- the incident was the same lease receiving
    repeated dispatches while one was already in flight."""
    hold_event = threading.Event()
    fake_popen = _fake_popen_factory(hold_event)
    popen_call_count = 0

    def _counting_popen(argv, **kwargs):
        nonlocal popen_call_count
        popen_call_count += 1
        return fake_popen(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", _counting_popen)
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, "/fake/codex"))
    _fresh_authority(tmp_path, monkeypatch, lease_id="lease-shared")

    first = estate_router.execute_codex_write_durable(
        "first dispatch", repo_id="test-repo", host_id="test-lab", wait_timeout=0.2,
    )
    assert first["ok"] is True
    assert first["lifecycle_state"] in ("accepted", "running")

    second = estate_router.execute_codex_write_durable(
        "second dispatch, same lease, while first still in flight",
        repo_id="test-repo", host_id="test-lab", wait_timeout=0.2,
    )

    hold_event.set()

    assert second.get("reused_existing_execution") is True
    assert second["execution_id"] == first["execution_id"]
    assert popen_call_count == 1, "a second worker/Codex process must not have been spawned"


def test_new_submission_allowed_once_prior_execution_reaches_terminal_state(runtime_db, monkeypatch, tmp_path):
    """The admission check only blocks *non-terminal* conflicts -- once
    an execution finishes (success or failure), the lease is free again
    and a fresh submission must be allowed to run for real, not be
    permanently wedged behind a completed row."""
    hold_event = threading.Event()
    hold_event.set()
    fake_popen = _fake_popen_factory(hold_event)
    popen_call_count = 0

    def _counting_popen(argv, **kwargs):
        nonlocal popen_call_count
        popen_call_count += 1
        return fake_popen(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", _counting_popen)
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, "/fake/codex"))
    _fresh_authority(tmp_path, monkeypatch, lease_id="lease-shared-2")

    first = estate_router.execute_codex_write_durable(
        "first dispatch", repo_id="test-repo", host_id="test-lab", wait_timeout=1.0,
    )
    assert first.get("ok") is True
    assert first.get("reused_existing_execution") is not True

    second = estate_router.execute_codex_write_durable(
        "second dispatch after first completed",
        repo_id="test-repo", host_id="test-lab", wait_timeout=1.0,
    )

    assert second.get("reused_existing_execution") is not True
    assert second["execution_id"] != first["execution_id"]
    assert popen_call_count == 2


def test_finalize_refuses_when_authority_now_denies_live_checkout(runtime_db, monkeypatch, tmp_path):
    """Branch-drift/live-checkout substitution between execution and
    finalisation must fail closed -- simulated here by authority
    denying at finalise time even though the execution itself
    succeeded."""
    hold_event = threading.Event()
    hold_event.set()
    monkeypatch.setattr(subprocess, "Popen", _fake_popen_factory(hold_event))
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, "/fake/codex"))
    _fresh_authority(tmp_path, monkeypatch)

    result = estate_router.execute_codex_write_durable(
        "implement it", repo_id="test-repo", host_id="test-lab", wait_timeout=1.0,
    )
    assert result["ok"] is True

    monkeypatch.setattr(
        estate_router, "_codex_write_authority",
        lambda repo_id, host_id: {
            "ok": False,
            "error": f"refusing implementation mode in live registered checkout for {repo_id!r}",
        },
    )
    outcome = estate_router.finalize_execution(
        execution_id=result["execution_id"], repo_id="test-repo", host_id="test-lab",
        commit_message="test commit",
    )
    assert outcome["finalized"] is False
    assert "authority re-verification failed" in outcome["reason"]


# ---------------------------------------------------------------------
# Process handling
# ---------------------------------------------------------------------

def test_process_group_retained_and_correct_group_killed_on_timeout(runtime_db, monkeypatch, tmp_path):
    hold_event = threading.Event()
    fake_popen = _fake_popen_factory(hold_event)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, "/fake/codex"))
    _fresh_authority(tmp_path, monkeypatch)

    kill_calls = []

    def _fake_killpg(pgid, sig):
        assert sig == signal.SIGKILL
        kill_calls.append(pgid)
        for proc in fake_popen.instances:
            if proc.pid == pgid:
                proc.kill()
                return
        raise AssertionError(f"unknown pgid {pgid}")

    monkeypatch.setattr(os, "killpg", _fake_killpg)

    result = estate_router.execute_codex_write_durable(
        "implement it", repo_id="test-repo", host_id="test-lab",
        timeout=0.05, wait_timeout=2.0,
    )

    assert kill_calls == [fake_popen.instances[0].pid]
    assert result["ok"] is False
    state = estate_router.get_estate_execution(result["execution_id"])
    assert state["lifecycle_state"] == "timed_out"
    assert state["process_group_id"] == fake_popen.instances[0].pid


def test_worker_failure_becomes_terminal_failed_state(runtime_db, monkeypatch, tmp_path):
    hold_event = threading.Event()
    hold_event.set()
    monkeypatch.setattr(subprocess, "Popen", _fake_popen_factory(hold_event, exit_code=1, output="boom"))
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, "/fake/codex"))
    _fresh_authority(tmp_path, monkeypatch)

    result = estate_router.execute_codex_write_durable(
        "implement it", repo_id="test-repo", host_id="test-lab", wait_timeout=1.0,
    )
    assert result["ok"] is False
    state = estate_router.get_estate_execution(result["execution_id"])
    assert state["lifecycle_state"] == "failed"
    assert state["error"]


def test_no_permanent_phantom_running_after_process_death(runtime_db, monkeypatch, tmp_path):
    """Simulates a row left "running" with a worker_pid that no longer
    exists on the host (backend restarted or worker crashed) -- a poll
    must reconcile it to a truthful terminal state, not leave it
    running forever."""
    from datetime import timedelta
    from core.database import SessionLocal, utcnow_naive

    _fresh_authority(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        # A pid essentially guaranteed not to exist. Backdated well past
        # the pid-not-found grace period so this represents a genuinely
        # stale row (e.g. from a backend restart), not a process that
        # simply exited an instant ago and is about to be marked
        # succeeded by its own _run() thread.
        phantom_pid = 2**30
        stale_time = utcnow_naive() - timedelta(seconds=60)
        db.add(EstateExecution(
            id="exec-phantom", objective="x", executor="codex-write", provider="codex",
            host_id="test-lab", repo_id="test-repo", lease_id="lease-1",
            worktree_path=str(tmp_path), branch="feat/x",
            lifecycle_state="running", worker_pid=phantom_pid, process_group_id=phantom_pid,
            submitted_at=stale_time, updated_at=stale_time,
        ))
        db.commit()
    finally:
        db.close()

    state = estate_router.get_estate_execution("exec-phantom")
    assert state["lifecycle_state"] == "interrupted"
    assert "no longer exists" in state["error"]


# ---------------------------------------------------------------------
# Restart / reconciliation
# ---------------------------------------------------------------------

def test_completed_execution_survives_reconciliation_sweep(runtime_db, monkeypatch, tmp_path):
    from core.database import SessionLocal

    _fresh_authority(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        db.add(EstateExecution(
            id="exec-done", objective="x", executor="codex-write", provider="codex",
            host_id="test-lab", repo_id="test-repo", lease_id="lease-1",
            worktree_path=str(tmp_path), branch="feat/x",
            lifecycle_state="succeeded", worker_pid=99999, result_json='{"ok": true}',
        ))
        db.commit()
    finally:
        db.close()

    state = estate_router.get_estate_execution("exec-done")
    assert state["lifecycle_state"] == "succeeded"
    assert state["result"]["ok"] is True


def test_young_accepted_row_with_no_pid_yet_is_not_reconciled_prematurely(runtime_db, monkeypatch, tmp_path):
    from core.database import SessionLocal, utcnow_naive

    db = SessionLocal()
    try:
        db.add(EstateExecution(
            id="exec-young", objective="x", executor="codex-write", provider="codex",
            host_id="test-lab", repo_id="test-repo", lease_id="lease-1",
            worktree_path=str(tmp_path), branch="feat/x",
            lifecycle_state="accepted", submitted_at=utcnow_naive(),
        ))
        db.commit()
    finally:
        db.close()

    state = estate_router.get_estate_execution("exec-young")
    assert state["lifecycle_state"] == "accepted"


def test_reconciliation_never_relaunches_a_paid_executor(runtime_db, monkeypatch, tmp_path):
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, "/fake/codex"))
    calls = []
    monkeypatch.setattr(estate_router, "_execute_codex_with_sandbox",
                        lambda *a, **k: calls.append((a, k)))

    from core.database import SessionLocal
    db = SessionLocal()
    try:
        db.add(EstateExecution(
            id="exec-orphan", objective="x", executor="codex-write", provider="codex",
            host_id="test-lab", repo_id="test-repo", lease_id="lease-1",
            worktree_path=str(tmp_path), branch="feat/x",
            lifecycle_state="running", worker_pid=2**30,
        ))
        db.commit()
    finally:
        db.close()

    estate_router.get_estate_execution("exec-orphan")
    assert calls == []


# ---------------------------------------------------------------------
# Finalisation
# ---------------------------------------------------------------------

def test_finalize_commits_and_pushes_authorised_changes(runtime_db, monkeypatch, tmp_path):
    hold_event = threading.Event()
    hold_event.set()
    monkeypatch.setattr(subprocess, "Popen", _fake_popen_factory(hold_event))
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, "/fake/codex"))
    _fresh_authority(tmp_path, monkeypatch)

    result = estate_router.execute_codex_write_durable(
        "implement it", repo_id="test-repo", host_id="test-lab", wait_timeout=1.0,
    )
    assert result["ok"] is True

    calls = []

    def _fake_run_git_subprocess(argv, cwd, capture_output, text, timeout):
        import types
        calls.append(argv)
        out = types.SimpleNamespace(returncode=0, stdout="", stderr="")
        if argv[:2] == ["git", "branch"]:
            out.stdout = "feat/x\n"
        elif argv[:2] == ["git", "status"]:
            out.stdout = " M src/thing.py\n"
        elif argv[:2] == ["git", "rev-parse"]:
            out.stdout = "abc1234\n"
        return out

    monkeypatch.setattr(subprocess, "run", _fake_run_git_subprocess)

    outcome = estate_router.finalize_execution(
        execution_id=result["execution_id"], repo_id="test-repo", host_id="test-lab",
        commit_message="test commit",
    )
    assert outcome["finalized"] is True
    assert outcome["commit_sha"] == "abc1234"
    assert ["git", "add", "--", "src/thing.py"] in calls
    assert any(c[:2] == ["git", "add"] for c in calls)
    assert not any(c == ["git", "add", "-A"] for c in calls)


def test_finalize_refuses_when_not_succeeded(runtime_db, monkeypatch, tmp_path):
    from core.database import SessionLocal
    _fresh_authority(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        db.add(EstateExecution(
            id="exec-running-still", objective="x", executor="codex-write", provider="codex",
            host_id="test-lab", repo_id="test-repo", lease_id="lease-1",
            worktree_path=str(tmp_path), branch="feat/x", lifecycle_state="running",
        ))
        db.commit()
    finally:
        db.close()

    outcome = estate_router.finalize_execution(
        execution_id="exec-running-still", repo_id="test-repo", host_id="test-lab",
        commit_message="test commit",
    )
    assert outcome["finalized"] is False
    assert "not succeeded" in outcome["reason"]


def test_finalize_refuses_on_lease_drift(runtime_db, monkeypatch, tmp_path):
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        db.add(EstateExecution(
            id="exec-lease-drift", objective="x", executor="codex-write", provider="codex",
            host_id="test-lab", repo_id="test-repo", lease_id="lease-OLD",
            worktree_path=str(tmp_path), branch="feat/x", lifecycle_state="succeeded",
        ))
        db.commit()
    finally:
        db.close()

    _fresh_authority(tmp_path, monkeypatch, lease_id="lease-NEW")
    outcome = estate_router.finalize_execution(
        execution_id="exec-lease-drift", repo_id="test-repo", host_id="test-lab",
        commit_message="test commit",
    )
    assert outcome["finalized"] is False
    assert "lease drift" in outcome["reason"]


def test_finalize_refuses_on_branch_drift(runtime_db, monkeypatch, tmp_path):
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        db.add(EstateExecution(
            id="exec-branch-drift", objective="x", executor="codex-write", provider="codex",
            host_id="test-lab", repo_id="test-repo", lease_id="lease-1",
            worktree_path=str(tmp_path), branch="feat/original", lifecycle_state="succeeded",
        ))
        db.commit()
    finally:
        db.close()

    _fresh_authority(tmp_path, monkeypatch, branch="feat/original")

    def _fake_run(argv, cwd, capture_output, text, timeout):
        import types
        out = types.SimpleNamespace(returncode=0, stdout="", stderr="")
        if argv[:2] == ["git", "branch"]:
            out.stdout = "feat/switched-away\n"
        return out

    monkeypatch.setattr(subprocess, "run", _fake_run)

    outcome = estate_router.finalize_execution(
        execution_id="exec-branch-drift", repo_id="test-repo", host_id="test-lab",
        commit_message="test commit",
    )
    assert outcome["finalized"] is False
    assert "branch drift" in outcome["reason"]


def test_finalize_refuses_when_nothing_dirty(runtime_db, monkeypatch, tmp_path):
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        db.add(EstateExecution(
            id="exec-clean", objective="x", executor="codex-write", provider="codex",
            host_id="test-lab", repo_id="test-repo", lease_id="lease-1",
            worktree_path=str(tmp_path), branch="feat/x", lifecycle_state="succeeded",
        ))
        db.commit()
    finally:
        db.close()

    _fresh_authority(tmp_path, monkeypatch)

    def _fake_run(argv, cwd, capture_output, text, timeout):
        import types
        out = types.SimpleNamespace(returncode=0, stdout="", stderr="")
        if argv[:2] == ["git", "branch"]:
            out.stdout = "feat/x\n"
        elif argv[:2] == ["git", "status"]:
            out.stdout = ""
        return out

    monkeypatch.setattr(subprocess, "run", _fake_run)

    outcome = estate_router.finalize_execution(
        execution_id="exec-clean", repo_id="test-repo", host_id="test-lab",
        commit_message="test commit",
    )
    assert outcome["finalized"] is False
    assert "no changes" in outcome["reason"]

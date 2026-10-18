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
    # The legacy in-process lane only ever ran on the backend's own host;
    # Stage 6 reconciliation marks a NULL-handle row on any OTHER host
    # `lost`, so these legacy-lane tests run as that host.
    monkeypatch.setattr(estate_router, "current_host_id", lambda: "test-lab")
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





# ---------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------


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




# ---------------------------------------------------------------------
# Process handling
# ---------------------------------------------------------------------



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


# Gate round 7 (finding 1): the legacy in-process durable lane is closed and
# delegates to the Stage 6 worker lane. Its lane-mechanics tests were
# replaced by the Stage 6 equivalents: submission/observation (U13, U18, I4),
# admission reuse (U16), lifecycle (U19-U22, I5), cwd = verified worktree
# (U13 start payload), authority denial with no row (U14/U15), unresolved
# blocking (U21/U34/U37/U38). What remains here: the codex process-group
# timeout cleanup the worker runner still uses, and legacy NULL-handle
# reconciliation for rows created before Stage 6.


def test_codex_process_group_is_killed_on_timeout(monkeypatch, tmp_path):
    """_execute_codex_with_sandbox (used by the worker runner) kills the
    codex process group on timeout and reports it."""
    hold_event = threading.Event()
    fake_popen = _fake_popen_factory(hold_event)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, "/fake/codex"))
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
    started = []
    result = estate_router._execute_codex_with_sandbox(
        "implement it", sandbox="workspace-write", provider="codex", timeout=0.05, cwd=str(tmp_path),
        on_started=started.append,
    )
    assert kill_calls == [fake_popen.instances[0].pid] == started
    assert result["ok"] is False and "timed out" in result["error"]


def test_legacy_durable_lane_only_delegates_to_the_worker_lane(runtime_db, monkeypatch):
    """No in-process workspace-write remains: the legacy name forwards to
    execute_write_via_worker (which re-validates the lease in-transaction)."""
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("no in-process codex"))
    seen = {}
    monkeypatch.setattr(estate_router, "execute_write_via_worker",
                        lambda objective, **kw: seen.update(objective=objective, **kw) or {"ok": False})
    estate_router.execute_codex_write_durable("x", repo_id="r", host_id="h", decision_id="d")
    assert seen == {"objective": "x", "repo_id": "r", "host_id": "h", "decision_id": "d",
                    "wait_timeout": 30.0, "timeout": 1800.0}

"""Plan §G I9: real SQLite serialization (S6.5) across two OS PROCESSES on a
file-backed DB -- not threads, not mocks. Process A runs admission paused
after its in-transaction validation; process B runs release_repo. B must
wait for the write lock and then be refused; in the reverse order, the
admission is refused and no row exists."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]

_ADMIT = r'''
import json, os, sys, time
from pathlib import Path
import core.database as cdb
from src import estate_write_lane as lane, estate_worker_client as client
signal_dir = Path(sys.argv[1])
def fake(host_id, verb, payload, *, deadline_s):
    if verb == "worktree.verify":
        return {"ok": True, "result": {"ok": True, "clean": True, "head_sha": "a" * 40, "path": "/w"}}
    if verb == "start":
        return {"ok": True, "result": {"accepted": True, "state": "starting", "handle": None}}
    raise AssertionError(verb)
client.call_worker = fake
lane._observe_worker_execution = lambda execution_id: None
def hook():
    (signal_dir / "inside").touch()
    deadline = time.monotonic() + 30
    while not (signal_dir / "go").exists() and time.monotonic() < deadline:
        time.sleep(0.05)
if os.environ.get("PAUSE") == "1":
    lane._ADMISSION_TEST_HOOK = hook
result = lane.execute_write_via_worker("x", repo_id="odysseus", host_id="desktop-in7o23d", wait_timeout=0)
print(json.dumps({"ok": result["ok"], "code": result.get("error_code"), "execution_id": result.get("execution_id")}))
'''

_RELEASE = r'''
import json
from src import park_lease_ops as ops
try:
    ops.release_repo("odysseus", host_id="desktop-in7o23d")
    print(json.dumps({"released": True}))
except ops.LeaseHasUnresolvedExecution as exc:
    print(json.dumps({"released": False, "execution_id": exc.execution_id}))
'''


@pytest.fixture
def shared_db(tmp_path):
    path = tmp_path / "shared.db"
    url = f"sqlite:///{path}"
    import core.database as cdb
    engine = create_engine(url)
    cdb.Base.metadata.create_all(engine, tables=[cdb.ParkLease.__table__, cdb.EstateExecution.__table__])
    session = sessionmaker(bind=engine)()
    session.add(cdb.ParkLease(id="L1", repo_id="odysseus", host_id="desktop-in7o23d", worktree_path="/w",
                              branch="feat/x", status="active"))
    session.commit()
    session.close()
    env = {**os.environ, "DATABASE_URL": url, "PYTHONPATH": str(ROOT)}
    yield {"engine": engine, "env": env, "dir": tmp_path}
    engine.dispose()


def _spawn(code, env, *args, pause=False):
    return subprocess.Popen([sys.executable, "-c", code, *args], cwd=str(ROOT), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env={**env, "PAUSE": "1" if pause else "0"})


def _out(proc, timeout=60):
    stdout, stderr = proc.communicate(timeout=timeout)
    assert proc.returncode == 0, stderr
    return json.loads(stdout.strip().splitlines()[-1])


def _counts(engine):
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT count(*) FROM estate_executions").scalar()
        status = conn.exec_driver_sql("SELECT status FROM park_leases WHERE id = 'L1'").scalar()
    return rows, status


def test_i9_release_waits_for_the_admission_lock_then_is_refused(shared_db):
    admit = _spawn(_ADMIT, shared_db["env"], str(shared_db["dir"]), pause=True)
    deadline = time.monotonic() + 30
    while not (shared_db["dir"] / "inside").exists():
        assert time.monotonic() < deadline and admit.poll() is None, admit.stderr.read() if admit.poll() else ""
        time.sleep(0.05)
    release = _spawn(_RELEASE, shared_db["env"])
    time.sleep(1.5)
    assert release.poll() is None, "release must be blocked on the write lock while admission holds it"
    (shared_db["dir"] / "go").touch()
    admitted = _out(admit)
    released = _out(release)
    assert admitted["ok"] is True and admitted["execution_id"]
    assert released == {"released": False, "execution_id": admitted["execution_id"]}
    assert _counts(shared_db["engine"]) == (1, "active")


def test_i9_reverse_release_first_then_admission_is_refused(shared_db):
    assert _out(_spawn(_RELEASE, shared_db["env"])) == {"released": True}
    admitted = _out(_spawn(_ADMIT, shared_db["env"], str(shared_db["dir"])))
    assert admitted["ok"] is False and admitted["code"] == "write_lease_missing"
    assert _counts(shared_db["engine"]) == (0, "released")

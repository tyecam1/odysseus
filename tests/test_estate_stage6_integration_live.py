"""Stage 6 integration through REAL subprocess workers (plan §G I4, I5, I6,
I7-local, I10): the control plane in this process, a real LocalTransport
`python -m src.estate_worker` per call, real transient systemd user units,
a real git repo + worktree, and no paid inference -- the dispatched kind is
the sentinel-gated `noop-sleep` (plan I4). HOME points at a temp dir so no
live spool, sentinel or host-local config is touched. Skipped unless this
host is a registered local-transport worker with user units."""
import json
import os
import subprocess
import time
from datetime import timedelta
from pathlib import Path

import pytest

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()

import core.database as cdb
from core.database import EstateExecution, ParkLease, get_db_session
from src import estate_router, estate_worker_procs, park_lease_ops
from src import estate_write_lane as lane

_HOST = estate_router.current_host_id()
_UNITS, _DETAIL = estate_worker_procs.runner_units_supported() if os.name != "nt" else (False, "windows")
pytestmark = pytest.mark.skipif(not (_HOST and _UNITS),
                                reason=f"needs a registered local worker host with user units: {_HOST} {_DETAIL}")


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def estate(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".aoteru").mkdir(parents=True)
    (home / ".aoteru" / "worker_selftest_enabled").touch()
    ai_root = tmp_path / "ai"
    repo = ai_root / "odysseus-aoteru"
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    _git(repo, "config", "user.email", "it@example.com")
    _git(repo, "config", "user.name", "it")
    (repo / "README").write_text("r\n")
    _git(repo, "add", "README")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "remote", "add", "origin", str(origin))
    (home / ".aoteru" / "config.local.json").write_text(json.dumps({"AI_ROOT": str(ai_root)}))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_RUNTIME_DIR", os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    session_local, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", session_local)
    monkeypatch.setattr(lane, "MONITOR_INTERVAL_SECONDS", 0.3)
    from src import estate_worker_client
    estate_worker_client.clear_caches()

    real_payload = lane._start_payload

    def _selftest_payload(row):
        payload = real_payload(row)
        payload["kind"] = "noop-sleep"          # test-only: never codex, never paid
        payload["timeout_s"] = float(os.environ.get("IT_SLEEP_S", "3"))
        return payload

    monkeypatch.setattr(lane, "_start_payload", _selftest_payload)
    yield {"home": home, "repo": repo, "origin": origin}
    engine.dispose()
    os.unlink(tmpfile.name)
    _stop_units()


def _stop_units():
    env = {**os.environ, "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")}
    listing = subprocess.run(["systemctl", "--user", "list-units", "--all", "--no-legend", "aoteru-*"],
                             capture_output=True, text=True, env=env).stdout
    for line in listing.splitlines():
        unit = line.split()[0].lstrip("●")
        subprocess.run(["systemctl", "--user", "kill", "--signal=KILL", unit], capture_output=True, env=env)


def _wait_row(execution_id, predicate, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        view = estate_router.get_estate_execution(execution_id, wait_s=2)
        if predicate(view):
            return view
    raise AssertionError(f"timed out: {view}")


def _dispatch():
    return lane.execute_write_via_worker("it", repo_id="odysseus", host_id=_HOST, wait_timeout=0, timeout=60)


def test_i4_i6_i10_full_lifecycle_through_real_workers(estate, monkeypatch):
    # I7 (local host): reserve -> real prepare unit -> bind.
    parked = park_lease_ops.park_with_worktree("odysseus", _HOST, "acceptance/it")
    worktree = Path(parked["worktree_path"])
    assert parked["status"] == "active" and worktree.is_dir()
    assert _git(worktree, "branch", "--show-current") == "acceptance/it"

    # I4 + I6: dispatch E, duplicate while running -> same E.
    first = _dispatch()
    assert first["ok"] is True and first["dispatch"] == "new"
    e1 = first["execution_id"]
    duplicate = _dispatch()
    assert duplicate["dispatch"] == "reused_in_flight" and duplicate["execution_id"] == e1
    with get_db_session() as s:
        assert s.query(EstateExecution).count() == 1
    done = _wait_row(e1, lambda v: v["lifecycle_state"] == "succeeded")
    assert done["worker_handle"]["unit"] == f"aoteru-run-{e1}.service"   # real handle, never NULL
    # succeeded but unfinalized blocks a new dispatch
    blocked = _dispatch()
    assert blocked["ok"] is False and blocked["error_code"] == "lease_has_unfinalized_execution"
    # finalize: nothing to commit -> finalized; admission reopens
    finalized = lane.finalize_execution(execution_id=e1, repo_id="odysseus", host_id=_HOST, commit_message="it")
    assert finalized["finalized"] is True and finalized["committed"] is False
    assert finalized["push"]["state"] == "not_required"

    # I5 / I10: a second execution whose runner unit is killed mid-run.
    monkeypatch.setenv("IT_SLEEP_S", "60")
    second = _dispatch()
    assert second["dispatch"] == "new"
    e2 = second["execution_id"]
    running = _wait_row(e2, lambda v: v["lifecycle_state"] == "running")
    unit = running["worker_handle"]["unit"]
    subprocess.run(["systemctl", "--user", "kill", "--signal=KILL", unit], check=True, capture_output=True)
    interrupted = _wait_row(e2, lambda v: v["lifecycle_state"] == "interrupted")
    assert interrupted["worktree_resolution"] == "unresolved"
    with pytest.raises(park_lease_ops.LeaseHasUnresolvedExecution):
        park_lease_ops.release_repo("odysseus", host_id=_HOST)
    ids = {"lease_id": parked["lease_id"], "host_id": _HOST, "repo_id": "odysseus",
           "branch": "acceptance/it", "worktree_path": str(worktree)}
    (worktree / "stray.txt").write_text("dirty")
    assert lane.recover_execution_lease(e2, **ids)["code"] == "worktree_not_clean"
    (worktree / "stray.txt").unlink()
    recovered = lane.recover_execution_lease(e2, **ids)
    assert recovered["recovered"] is True
    with get_db_session() as s:
        assert s.query(ParkLease).filter(ParkLease.id == parked["lease_id"]).one().status == "released"
    # a fresh park reuses the clean worktree under a NEW lease id
    again = park_lease_ops.park_with_worktree("odysseus", _HOST, "acceptance/it")
    assert again["lease_id"] != parked["lease_id"] and Path(again["worktree_path"]) == worktree


def test_i8_dirty_existing_worktree_fails_closed_and_leaves_no_lease(estate):
    parked = park_lease_ops.park_with_worktree("odysseus", _HOST, "acceptance/dirty")
    worktree = Path(parked["worktree_path"])
    with get_db_session() as s:
        s.query(ParkLease).filter(ParkLease.id == parked["lease_id"]).update({"status": "released"})
    (worktree / "stray.txt").write_text("dirty")
    with pytest.raises(park_lease_ops.RepoNotClean):
        park_lease_ops.park_with_worktree("odysseus", _HOST, "acceptance/dirty")
    with get_db_session() as s:
        assert s.query(ParkLease).filter(ParkLease.status.in_(("active", "preparing"))).count() == 0

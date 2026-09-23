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


def _wrap_transport(monkeypatch, drop_verbs):
    """Drop the RESPONSE (not the request) of the first call per verb: the
    real worker runs, the control plane sees worker_unreachable."""
    from src import estate_worker_client as client
    real = client.LocalTransport.send
    dropped = set()

    def _send(self, request, *, deadline_s):
        response = real(self, request, deadline_s=deadline_s)
        if request["verb"] in drop_verbs and request["verb"] not in dropped:
            dropped.add(request["verb"])
            raise client.WorkerTransportError("worker_unreachable", "test: response dropped after the worker ran")
        return response

    monkeypatch.setattr(client.LocalTransport, "send", _send)


def test_i4_i5_laptop_observation_handle_never_null_and_interrupt(estate, monkeypatch, capsys):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import companion.laptop_client.aoteru as laptop
    import routes.estate_routing_routes as routes_mod
    monkeypatch.setenv("AUTH_ENABLED", "false")
    app = FastAPI()
    app.include_router(routes_mod.setup_estate_routing_routes())
    http = TestClient(app)
    monkeypatch.setattr(laptop, "_load_config", lambda: {"url": "http://test", "token": "t"})
    monkeypatch.setattr(laptop, "_request", lambda cfg, method, path, body=None, timeout=30.0: (
        lambda r: {"status": r.status_code, "body": r.json()})(http.request(method, path, json=body)))
    park_lease_ops.park_with_worktree("odysseus", _HOST, "acceptance/obs")
    e1 = _dispatch()["execution_id"]
    handles = []
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        with get_db_session() as s:
            row = s.query(EstateExecution).filter(EstateExecution.id == e1).one()
            handles.append(row.worker_handle_json)
            if row.lifecycle_state == "succeeded":
                break
        time.sleep(0.2)
    assert handles and all(h is not None for h in handles)       # placeholder, then the real handle
    assert laptop.main(["execution", e1, "--wait", "30"]) == 0
    assert json.loads(capsys.readouterr().out)["lifecycle_state"] == "succeeded"
    lane.finalize_execution(execution_id=e1, repo_id="odysseus", host_id=_HOST, commit_message="x")
    # I5: kill the runner mid-run; the real worker reports process_alive false.
    monkeypatch.setenv("IT_SLEEP_S", "60")
    e2 = _dispatch()["execution_id"]
    running = _wait_row(e2, lambda v: v["lifecycle_state"] == "running")
    subprocess.run(["systemctl", "--user", "kill", "--signal=KILL", running["worker_handle"]["unit"]],
                   check=True, capture_output=True)
    _wait_row(e2, lambda v: v["lifecycle_state"] == "interrupted")
    from src.estate_worker_client import call_worker
    status = call_worker(_HOST, "status", {"execution_id": e2}, deadline_s=20)["result"]
    assert status["process_alive"] is False and status["state"] == "interrupted"
    with get_db_session() as s:
        assert s.query(EstateExecution).count() == 2              # no redispatch


def test_i6a_start_response_dropped_after_spawn_is_confirmed_by_same_id_retry(estate, monkeypatch):
    park_lease_ops.park_with_worktree("odysseus", _HOST, "acceptance/drop")
    _wrap_transport(monkeypatch, {"start"})
    result = _dispatch()
    execution_id = result["execution_id"]
    with get_db_session() as s:
        row = s.query(EstateExecution).filter(EstateExecution.id == execution_id).one()
        assert row.lifecycle_state != "failed" and row.worktree_resolution == "unresolved"
    done = _wait_row(execution_id, lambda v: v["lifecycle_state"] == "succeeded")
    assert done["worker_handle"]["unit"] == f"aoteru-run-{execution_id}.service"
    spool = Path(os.environ["HOME"]) / ".aoteru" / "worker-spool" / execution_id
    assert json.loads((spool / "run.json").read_text())["decision"] == "execute"   # exactly one runner decision


def test_i6b_concurrent_same_id_real_starts_spawn_once(estate):
    import threading
    from src.estate_worker_client import call_worker
    execution_id = f"conc-{os.getpid()}"
    payload = {"execution_id": execution_id, "kind": "noop-sleep", "timeout_s": 2}
    answers = []
    threads = [threading.Thread(target=lambda: answers.append(
        call_worker(_HOST, "start", payload, deadline_s=30)["result"])) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(40)
    assert sum(1 for a in answers if a["reused"] is False) == 1
    assert all(a["state"] != "execution_failed" for a in answers)


def test_i11a_dropped_prepare_response_resolves_via_fence_then_fresh_park(estate, monkeypatch):
    _wrap_transport(monkeypatch, {"worktree.prepare"})
    with pytest.raises(park_lease_ops.PrepareOutcomeUnresolved) as info:
        park_lease_ops.park_with_worktree("odysseus", _HOST, "acceptance/dropped")
    with get_db_session() as s:
        assert s.query(ParkLease).filter(ParkLease.id == info.value.lease_id).one().status == "preparing"
    resolved = park_lease_ops.resolve_preparing_reservation(info.value.lease_id)
    assert resolved["released"] is True and resolved["state"] == "prepared"
    fresh = park_lease_ops.park_with_worktree("odysseus", _HOST, "acceptance/dropped")
    assert fresh["status"] == "active" and fresh["lease_id"] != info.value.lease_id


def test_i11b_released_execution_tombstones_and_replay_never_spawns(estate, monkeypatch):
    from src import estate_worker
    from src.estate_worker_client import call_worker
    park_lease_ops.park_with_worktree("odysseus", _HOST, "acceptance/tomb")
    e1 = _dispatch()["execution_id"]
    _wait_row(e1, lambda v: v["lifecycle_state"] == "succeeded")
    assert lane.finalize_execution(execution_id=e1, repo_id="odysseus", host_id=_HOST,
                                   commit_message="x")["finalized"] is True
    spool_root = Path(os.environ["HOME"]) / ".aoteru" / "worker-spool"
    assert (spool_root / e1 / "released.json").exists()
    monkeypatch.setattr(estate_worker, "_SPOOL_ROOT", spool_root)
    monkeypatch.setattr(estate_worker, "SPOOL_COMPACT_AFTER_RELEASE_SECONDS", -1)
    # The dispatched kind here is the self-test noop-sleep, which compacts on
    # the self-test rule (terminal + TTL), so advance that clock as well.
    monkeypatch.setattr(estate_worker, "_SPOOL_TTL_SECONDS", -1)
    estate_worker._gc_spools()                                   # clock-advanced compaction
    assert json.loads((spool_root / e1 / "state.json").read_text())["state"] == "tombstone"
    replay = call_worker(_HOST, "start", {"execution_id": e1, "kind": "noop-sleep", "timeout_s": 1},
                         deadline_s=30)["result"]
    assert replay["reused"] is True and replay["state"] == "tombstone" and replay["accepted"] is False


def test_i11c_rejected_push_then_aoteru_push_retry(estate, monkeypatch, capsys):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import companion.laptop_client.aoteru as laptop
    import routes.estate_routing_routes as routes_mod
    monkeypatch.setenv("AUTH_ENABLED", "false")
    app = FastAPI()
    app.include_router(routes_mod.setup_estate_routing_routes())
    http = TestClient(app)
    monkeypatch.setattr(laptop, "_load_config", lambda: {"url": "http://test", "token": "t"})
    monkeypatch.setattr(laptop, "_request", lambda cfg, method, path, body=None, timeout=30.0: (
        lambda r: {"status": r.status_code, "body": r.json()})(http.request(method, path, json=body)))
    parked = park_lease_ops.park_with_worktree("odysseus", _HOST, "acceptance/push")
    worktree = Path(parked["worktree_path"])
    e1 = _dispatch()["execution_id"]
    _wait_row(e1, lambda v: v["lifecycle_state"] == "succeeded")
    (worktree / "ACCEPTANCE.txt").write_text("written by the (self-test) writer\n")
    hook = estate["origin"] / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    finalized = lane.finalize_execution(execution_id=e1, repo_id="odysseus", host_id=_HOST, commit_message="it")
    assert finalized["finalized"] is True and finalized["committed"] is True
    assert finalized["push"]["state"] == "failed" and finalized["next_action"]["cli"] == f"aoteru push {e1}"
    hook.unlink()
    assert laptop.main(["push", e1]) == 0
    assert json.loads(capsys.readouterr().out)["pushed"] is True
    assert _git(estate["origin"], "rev-parse", "refs/heads/acceptance/push") == finalized["commit_sha"]

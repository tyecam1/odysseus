"""Disposable in-process acceptance; these fixtures are not live delivery evidence.

Run separately: pytest -m lazy_usage_acceptance tests/test_lazy_usage_acceptance.py
Only host/provider boundaries are mocked; discovery, preflight, DB admission,
verification and owner-card reconciliation use the production functions.
"""
import asyncio
import gc
import os
from pathlib import Path
import threading

import pytest
import yaml
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite
from tests.helpers.fake_worker import FakeWorker

clear_fake_database_modules()
import core.database as cdb
from routes.lazy_usage_routes import setup_lazy_usage_routes
from src import estate_router, estate_write_lane as lane, lazy_usage_runtime as rt, park_lease_ops
from src import estate_worker_client

pytestmark = pytest.mark.lazy_usage_acceptance
LAB = "hz2-workstation"


@pytest.fixture
def acceptance(tmp_path, monkeypatch):
    factory, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", factory)
    root = tmp_path / "owner"
    queue = root / "automation/review/agent-tasks"
    for bucket in ("ready", "inbox", "blocked", "done"):
        (queue / bucket).mkdir(parents=True)
    card = queue / "ready/fixture.md"
    card.write_text("---\n" + yaml.safe_dump({
        "task_id": "bounded-fixture", "title": "Bounded fixture delivery", "status": "ready",
        "priority": "high", "risk_level": "low", "execution_mode": "implementation",
        "verification_route": "deterministic", "allowed_paths": ["fixture-result.txt"],
    }) + "---\nCreate fixture-result.txt with the exact content verified.\n")
    monkeypatch.setattr(rt.portfolio, "resolve_roots", lambda *a: ({"odysseus": root}, {}))
    hosts = [{"host_id": LAB, "eligible": True, "qualified_executors": ["codex", "codex-write"]}]
    monkeypatch.setattr(estate_router, "current_host_id", lambda: LAB)
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda *a: hosts)
    monkeypatch.setattr(estate_worker_client, "worker_health", lambda *a: {"codex": {"available": True}})
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda *a, **k: {"allowed": True, "reason": "fixture provider"})
    monkeypatch.setattr(estate_router, "resolve_route", lambda *a, **k: {
        "ok": False, "route": {"host": LAB, "executor": "none", "model_alias": "code-strong"},
        "hosts_checked": hosts})
    # Worker attests the worktree; the real preflight still checks the real DB lease.
    monkeypatch.setattr(estate_router, "_codex_write_authority", lane._lease_authority)
    worker = FakeWorker(monkeypatch, path=str(root))
    monkeypatch.setattr(park_lease_ops, "park_with_worktree", lambda repo, host, branch, session_id:
                        park_lease_ops.park_repo(repo, host, str(root), branch=branch, session_id=session_id))
    monkeypatch.setattr(lane, "_trigger_background_reconcile", lambda: None)
    monkeypatch.setattr(lane, "_observe_worker_execution", lambda execution_id: None)
    preflights = []
    original_preflight = rt.delegation_preflight

    def preflight(units):
        result = original_preflight(units)
        preflights.append(result)
        return result

    monkeypatch.setattr(rt, "delegation_preflight", preflight)
    app = FastAPI()

    @app.middleware("http")
    async def identity(request: Request, call_next):
        request.state.api_token = True
        request.state.api_token_owner = "operator"
        request.state.api_token_scopes = ["estate:execute"]
        return await call_next(request)

    app.include_router(setup_lazy_usage_routes())

    def deliver(execution_id):
        # The mocked executor performs the bounded fixture task and its owner
        # acceptance, rather than asking the controller to assert delivery.
        artifact = root / "fixture-result.txt"
        artifact.write_text("verified\n")
        assert artifact.read_text() == "verified\n"
        meta, body = rt.portfolio.split_card(card.read_text())
        meta.update(status="done", acceptance_evidence="fixture-result.txt exact-content check passed")
        (queue / "done/fixture.md").write_text("---\n" + yaml.safe_dump(meta) + "---\n" + body)
        card.unlink()
        worker.set_state(execution_id, "succeeded", result={"ok": True, "executed": True,
            "deterministic_gate": "pass", "usage": {"paid_calls": 2, "tool_calls": 4}})
        lane._apply_view(execution_id, worker._view(execution_id))

    yield factory, app, worker, preflights, deliver
    engine.dispose()
    os.unlink(tmpfile.name)


def start(app):
    with TestClient(app) as client:
        response = client.post("/api/lazy-usage/start", json={"repo_scope": ["odysseus"]})
        assert response.status_code == 200
        run_id = response.json()["id"]
        assert client.post("/api/lazy-usage/start", json={}).status_code == 409
        return run_id


def test_fixture_delivery_through_frontier_preflight_dispatch_verify_and_status(acceptance):
    factory, app, worker, preflights, deliver = acceptance
    run_id = start(app)
    with factory() as db:
        first = rt.advance(db, run_id)
    execution_id = first["checkpoint"]["in_flight_execution_id"]
    assert preflights[0]["ok"]
    assert preflights[0]["units"][0]["write_authority"]["ready"]
    assert first["counters"]["paid_calls"] == 1
    deliver(execution_id)
    with factory() as db:
        result = rt.advance(db, run_id)
        assert result["checkpoint"]["acceptance"]["delivered"] is True
        assert result["checkpoint"]["last_execution_id"] == execution_id
        assert result["counters"]["paid_calls"] == 2
        assert result["counters"]["tool_calls"] > first["counters"]["tool_calls"]
        assert not result["owed_reviews"]
        assert rt.advance(db, run_id)["state"] == "completed"
    assert worker.verbs().count("start") == 1


def test_disconnect_while_advance_is_in_flight_does_not_cancel(acceptance):
    factory, app, worker, _, deliver = acceptance
    client = TestClient(app)
    run_id = client.post("/api/lazy-usage/start", json={"repo_scope": ["odysseus"]}).json()["id"]
    entered, release = threading.Event(), threading.Event()
    failures = []

    def hold(host, verb, payload):
        if verb == "start":
            entered.set()
            assert release.wait(10)

    worker.on_call = hold

    def advance():
        try:
            with factory() as db:
                rt.advance(db, run_id)
        except BaseException as exc:
            failures.append(exc)

    thread = threading.Thread(target=advance)
    thread.start()
    try:
        assert entered.wait(10)
        client.close()
        del client
        gc.collect()
        with factory() as db:
            row = db.get(cdb.LazyUsageRun, run_id)
            execution_id = row.checkpoint["in_flight_execution_id"]
            assert row.state == "running"
            assert db.get(cdb.EstateExecution, execution_id).lifecycle_state in {"accepted", "running"}
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive() and not failures
    assert "cancel" not in worker.verbs()
    deliver(execution_id)
    with factory() as db:
        assert rt.advance(db, run_id)["checkpoint"]["acceptance"]["delivered"]


@pytest.mark.asyncio
async def test_new_lifecycle_loop_recovers_checkpoint_without_duplicate_dispatch(acceptance, monkeypatch):
    factory, app, worker, _, deliver = acceptance
    run_id = start(app)
    first_tick, second_tick = asyncio.Event(), asyncio.Event()
    loop = asyncio.get_running_loop()
    original_tick = rt.lifecycle_tick
    ticks = []

    def tick():
        result = original_tick()
        ticks.append(result)
        loop.call_soon_threadsafe((first_tick if len(ticks) == 1 else second_tick).set)
        return result

    monkeypatch.setattr(rt, "lifecycle_tick", tick)
    task = asyncio.create_task(rt.lazy_usage_lifecycle_loop())
    try:
        await asyncio.wait_for(first_tick.wait(), 10)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    first = ticks[0]
    execution_id = first["checkpoint"]["in_flight_execution_id"]
    # New service-loop instance, fresh sessions, same durable database and worker.
    restarted = asyncio.create_task(rt.lazy_usage_lifecycle_loop())
    try:
        await asyncio.wait_for(second_tick.wait(), 10)
    finally:
        restarted.cancel()
        with pytest.raises(asyncio.CancelledError):
            await restarted
    assert ticks[1]["checkpoint"]["in_flight_execution_id"] == execution_id
    assert ticks[1]["counters"]["paid_calls"] == first["counters"]["paid_calls"] == 1
    assert ticks[1]["counters"]["tool_calls"] > first["counters"]["tool_calls"]
    deliver(execution_id)
    with factory() as db:
        final = rt.advance(db, run_id)
        assert final["counters"]["paid_calls"] == 2
        assert final["checkpoint"]["acceptance"]["delivered"]
        assert db.query(cdb.EstateExecution).count() == 1
    assert worker.verbs().count("start") == 1
    assert worker.executions[execution_id]["spawns"] == 1


def test_documented_rollback_is_code_restart_and_terminal_activation():
    doc = (Path(__file__).resolve().parents[1] / "docs/runtime-work-packages/2026-11-09-lazyusage-lab-persistence-acceptance.md").read_text()
    rollback = doc.split("## Rollback", 1)[1].split("## ", 1)[0]
    assert "git revert" in rollback and "merge commit" in rollback
    assert "systemctl restart odysseus-aoteru-lab.service" in rollback
    assert "POST /api/lazy-usage/stop" in rollback and "terminal" in rollback

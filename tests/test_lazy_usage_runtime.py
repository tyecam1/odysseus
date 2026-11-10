"""Durable activation controls and real DB admission/recovery boundaries."""
import asyncio
import json
import os
import threading
from datetime import timedelta

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()
import core.database as cdb
from core.database import EstateExecution, LazyUsageRun, ParkLease, utcnow_naive
from src import estate_router, estate_write_lane as lane, lazy_usage_runtime as rt, park_lease_ops
from routes.lazy_usage_routes import setup_lazy_usage_routes
from tests.helpers.fake_worker import FakeWorker

LAB = "hz2-workstation"


@pytest.fixture
def db(monkeypatch):
    factory, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", factory)
    monkeypatch.setattr(estate_router, "current_host_id", lambda: LAB)
    monkeypatch.setattr(lane, "_trigger_background_reconcile", lambda: None)
    monkeypatch.setattr(lane, "_observe_worker_execution", lambda execution_id: None)
    session = factory()
    yield session
    session.close()
    engine.dispose()
    os.unlink(tmpfile.name)


def activate(db, **overrides):
    return rt.activate_run(db, "operator", ["odysseus"], overrides)["id"]


def fail_dispatch(*args, **kwargs):
    pytest.fail("unexpected dispatch")


@pytest.fixture
def frontier(tmp_path, monkeypatch):
    root = tmp_path / "odysseus"
    queue = root / "automation/review/agent-tasks/ready"
    queue.mkdir(parents=True)
    records = []

    def add(name="a", write=False, **meta):
        metadata = {"task_id": name, "title": name, "status": "ready", "priority": "high",
                    "execution_mode": "implementation" if write else "read-only", **meta}
        import yaml
        (queue / (name + ".md")).write_text("---\n" + yaml.safe_dump(metadata) +
                                           "---\nRun the bounded owning task.\n")
        record = {"ref": "odysseus:ready/" + name + ".md", "repo_id": "odysseus", "bucket": "ready",
                  "task_id": name, "status": "ready", "priority": "high", "eligible": "unverified"}
        records.append(record)
        return record

    monkeypatch.setattr(rt, "refresh_frontier", lambda scope: {
        "roots": {"odysseus": root}, "records": list(records), "unavailable": {},
        "counts": {"odysseus": {"ready": len(records)}}, "warnings": []})
    monkeypatch.setattr(estate_router, "resolve_route", lambda *a, **kw: {
        "ok": False, "route": {"host": LAB, "executor": "none", "model_alias": "code-strong"},
        "hosts_checked": [{"host_id": LAB, "qualified_executors": ["local", "codex", "codex-write"]}]})
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda *a, **kw: {"allowed": True})
    monkeypatch.setattr(rt, "delegation_preflight", lambda units: {"ok": True})
    return add, records


def read_result(**extra):
    return {"ok": True, "executed": True, "deterministic_gate": "pass", **extra}


def test_table_created_and_ceiling_clamp_conflict(db):
    assert "lazy_usage_runs" in inspect(db.get_bind()).get_table_names()
    result = rt.activate_run(db, "operator", None, {k: v * 2 for k, v in rt.CEILINGS.items()})
    assert result["budgets"] == rt.CEILINGS
    assert result["repo_scope"] == list(rt.portfolio.LAYOUT)
    with pytest.raises(rt.RunError, match="already exists") as exc:
        activate(db)
    assert exc.value.status_code == 409
    assert db.query(LazyUsageRun).count() == 1


@pytest.mark.parametrize("overrides", [{"max_paid_calls": -1}, {"max_tool_calls": True}, {"other": 3}])
def test_invalid_budgets_fail_closed(db, overrides):
    with pytest.raises(rt.RunError):
        rt.activate_run(db, "operator", None, overrides)
    assert not db.query(LazyUsageRun).count()


def test_pause_resume_stop_and_owner(db):
    run_id = activate(db)
    assert rt.pause_run(db, run_id, "operator")["state"] == "paused"
    assert rt.resume_run(db, run_id, "operator")["state"] == "running"
    with pytest.raises(rt.RunError) as exc:
        rt.pause_run(db, run_id, "intruder")
    assert exc.value.status_code == 403
    result = rt.stop_run(db, run_id, "operator")
    assert result["state"] == "stopped"
    for function in (rt.pause_run, rt.resume_run):
        with pytest.raises(rt.RunError) as exc:
            function(db, run_id, "operator")
        assert exc.value.status_code == 409
    assert rt.advance(db, run_id) == result
    assert rt.stop_run(db, run_id, "operator") == result
    assert activate(db) != run_id


@pytest.mark.parametrize("state", sorted(rt.TERMINAL))
def test_terminal_rows_cannot_be_laundered(db, state):
    run_id = activate(db)
    row = db.get(LazyUsageRun, run_id)
    row.state, row.finished_at, row.terminal_reason = state, utcnow_naive(), "original"
    db.commit()
    before = rt.run_dict(row)
    for fn in (rt.pause_run, rt.resume_run):
        with pytest.raises(rt.RunError):
            fn(db, run_id, "operator")
    assert rt.stop_run(db, run_id, "operator") == before
    assert rt.advance(db, run_id) == before


@pytest.mark.parametrize("ceiling,counter", [
    ("max_seconds", None), ("max_paid_calls", "paid_calls"), ("max_tool_calls", "tool_calls"),
    ("max_no_delivery_turns", "no_delivery_turns"), ("max_repeat_failures", "repeated_failures")])
def test_all_five_budgets_survive_restart_and_forbid_dispatch(db, monkeypatch, ceiling, counter):
    run_id = activate(db)
    row = db.get(LazyUsageRun, run_id)
    if counter:
        row.counters = {**row.counters, counter: rt.CEILINGS[ceiling]}
    else:
        row.started_at = utcnow_naive() - timedelta(seconds=rt.CEILINGS[ceiling] + 1)
    db.commit()
    monkeypatch.setattr(estate_router, "run_task", fail_dispatch)
    monkeypatch.setattr(estate_router, "execute_write_via_worker", fail_dispatch)
    db.close()
    with cdb.SessionLocal() as restarted:
        result = rt.advance(restarted, run_id)
        assert result["state"] == "budget_exhausted"
        assert result["terminal_reason"] == ceiling
        assert rt.advance(restarted, run_id) == result
        with pytest.raises(rt.RunError):
            rt.resume_run(restarted, run_id, "operator")


def test_no_eligible_frontier_backs_off_without_spin(db, frontier, monkeypatch):
    add, _ = frontier
    add(protected_gate="operator_release")
    run_id = activate(db)
    calls = []
    original = rt.refresh_frontier
    monkeypatch.setattr(rt, "refresh_frontier", lambda scope: (calls.append(scope), original(scope))[1])
    monkeypatch.setattr(estate_router, "run_task", fail_dispatch)
    result = rt.advance(db, run_id)
    assert result["state"] == "paused"
    assert result["checkpoint"]["recheck_at"]
    for _ in range(5):
        rt.advance(db, run_id)
    assert len(calls) == 1
    row = db.get(LazyUsageRun, run_id)
    row.checkpoint = {**row.checkpoint, "recheck_at": (utcnow_naive() - timedelta(seconds=1)).isoformat()}
    db.commit()
    rt.advance(db, run_id)
    assert len(calls) == 2


def write_setup(db, monkeypatch):
    worker = FakeWorker(monkeypatch)

    def park(repo, host, branch, session_id):
        return park_lease_ops.park_repo(repo, host, "/w/feat", branch=branch, session_id=session_id)

    monkeypatch.setattr(park_lease_ops, "park_with_worktree", park)
    return worker


def test_restart_observes_one_actual_write_dispatch(db, frontier, monkeypatch):
    add, _ = frontier
    add(write=True)
    worker = write_setup(db, monkeypatch)
    run_id = activate(db)

    def checkpoint_before_start(host, verb, payload):
        if verb == "start":
            with cdb.SessionLocal() as other:
                row = other.get(LazyUsageRun, run_id)
                assert row.checkpoint["in_flight_execution_id"] == payload["execution_id"]
                assert row.counters["paid_calls"] == 1

    worker.on_call = checkpoint_before_start
    result = rt.advance(db, run_id)
    execution_id = result["checkpoint"]["in_flight_execution_id"]
    assert execution_id
    db.close()
    with cdb.SessionLocal() as restarted:
        for _ in range(3):
            rt.advance(restarted, run_id)
    assert worker.verbs().count("start") == 1
    assert db.query(EstateExecution).count() == 1
    assert worker.executions[execution_id]["spawns"] == 1


def test_stop_uses_worker_cancel_and_preserves_unresolved_lease(db, frontier, monkeypatch):
    add, _ = frontier
    add(write=True)
    worker = write_setup(db, monkeypatch)
    run_id = activate(db)
    first = rt.advance(db, run_id)
    execution_id = first["checkpoint"]["in_flight_execution_id"]
    cancelled = []

    def cancel(host, verb, payload, *, deadline_s):
        assert host == LAB and deadline_s <= 10
        if verb == "status":
            return {"result": worker._view(payload["execution_id"])}
        assert verb == "cancel"
        cancelled.append(payload["execution_id"])
        worker.set_state(payload["execution_id"], "failed", result={"ok": False, "error": "execution cancelled"})
        lane._apply_view(payload["execution_id"], worker._view(payload["execution_id"]))
        return {"result": {"killed": True}}

    monkeypatch.setattr(rt, "call_worker", cancel)
    stopped = rt.stop_run(db, run_id, "operator")
    assert stopped["state"] == "stopped"
    assert cancelled == [execution_id]
    db.expire_all()
    lease = db.query(ParkLease).one()
    assert lease.status == "active"  # existing unresolved-worktree gate wins
    assert stopped["checkpoint"]["lease_release_debt"]
    rt.advance(db, run_id)
    assert worker.verbs().count("start") == 1


def test_stop_before_dispatch_releases_exact_owned_lease(db, frontier, monkeypatch):
    add, _ = frontier
    add(write=True)
    write_setup(db, monkeypatch)
    run_id = activate(db)

    def preflight(units):
        with cdb.SessionLocal() as other:
            rt.stop_run(other, run_id, "operator")
        return {"ok": True}

    monkeypatch.setattr(rt, "delegation_preflight", preflight)
    monkeypatch.setattr(estate_router, "execute_write_via_worker", fail_dispatch)
    rt.advance(db, run_id)
    rt.advance(db, run_id)
    assert db.get(LazyUsageRun, run_id).state == "stopped"
    assert db.query(ParkLease).one().status == "released"


def test_quota_error_parks_verbatim_debt_and_other_task_continues(db, frontier, monkeypatch):
    add, _ = frontier
    add("a")
    add("b")
    error = "You've hit your usage limit. Try again at 23:45 on 2026-11-10."
    calls = []

    def execute(task):
        calls.append(task["objective"])
        if len(calls) == 1:
            return {"ok": False, "executed": True, "provider": "codex", "error": error,
                    "provider_health": {"state": "quota_exhausted", "retry_after": "2026-11-10T23:45:00+00:00",
                                        "retry_after_assumed": False}}
        return read_result()

    monkeypatch.setattr(estate_router, "run_task", execute)
    run_id = activate(db)
    first = rt.advance(db, run_id)
    assert first["state"] == "running"
    debt = first["owed_reviews"][0]
    assert debt["error"] == error
    assert debt["retry_after"] == "2026-11-10T23:45:00+00:00"
    second = rt.advance(db, run_id)
    assert len(calls) == 2 and "ready/b.md" in calls[1]
    assert second["owed_reviews"][0] == debt
    assert "Run the bounded owning task" not in json.dumps(second["checkpoint"])


def test_uncertain_read_response_is_observed_never_replayed(db, frontier, monkeypatch):
    add, _ = frontier
    add()
    calls = []

    def execute(task):
        calls.append(task)
        raise ConnectionError("response lost")

    monkeypatch.setattr(estate_router, "run_task", execute)
    run_id = activate(db)
    first = rt.advance(db, run_id)
    assert first["checkpoint"]["in_flight_execution_id"]
    rt.resume_run(db, run_id, "operator")
    rt.advance(db, run_id)
    assert len(calls) == 1


def test_child_usage_accounted_once_and_exhausts_budget(db, frontier, monkeypatch):
    add, _ = frontier
    add()
    monkeypatch.setattr(estate_router, "run_task", lambda task: read_result(usage={"paid_calls": 12, "tool_calls": 30}))
    run_id = activate(db)
    result = rt.advance(db, run_id)
    assert result["counters"]["paid_calls"] == 12
    assert result["counters"]["tool_calls"] == 33  # frontier/preflight/observation plus child aggregate
    assert result["state"] == "budget_exhausted"
    assert rt.advance(db, run_id) == result


def test_no_dispatch_with_unqualified_provider(db, frontier, monkeypatch):
    add, _ = frontier
    add(write=True)
    monkeypatch.setattr(estate_router, "_resolve_paid_provider", lambda *a, **k: {"provider": "glm"})
    monkeypatch.setattr(estate_router, "execute_write_via_worker", fail_dispatch)
    assert rt.advance(db, activate(db))["state"] == "paused"
    assert not db.query(ParkLease).count()


def test_last_reserved_paid_call_can_be_admitted(db, frontier, monkeypatch):
    add, _ = frontier
    add(write=True)
    worker = write_setup(db, monkeypatch)
    result = rt.advance(db, activate(db, max_paid_calls=1))
    assert result["checkpoint"]["in_flight_execution_id"]
    assert worker.verbs().count("start") == 1


def test_stop_after_admission_before_start_fences_worker(db, frontier, monkeypatch):
    add, _ = frontier
    add(write=True)
    worker = write_setup(db, monkeypatch)
    monkeypatch.setattr(rt, "call_worker", worker.call)
    run_id = activate(db)
    original_start = lane._dispatch_start

    def delayed_start(execution_id):
        with cdb.SessionLocal() as other:
            stopped = rt.stop_run(other, run_id, "operator")
            assert stopped["state"] == "stopped"
        original_start(execution_id)

    monkeypatch.setattr(lane, "_dispatch_start", delayed_start)
    result = rt.advance(db, run_id)
    assert result["state"] == "stopped"
    assert not result["checkpoint"]["in_flight_execution_id"]
    assert worker.verbs().count("start") == 0
    assert db.query(ParkLease).one().status == "released"


def test_stop_before_admission_guard_prevents_start(db, frontier, monkeypatch):
    add, _ = frontier
    add(write=True)
    worker = write_setup(db, monkeypatch)
    run_id = activate(db)

    def stop_during_verify(host, verb, payload):
        if verb == "worktree.verify":
            with cdb.SessionLocal() as other:
                rt.stop_run(other, run_id, "operator")

    worker.on_call = stop_during_verify
    result = rt.advance(db, run_id)
    assert result["state"] == "stopped"
    assert not db.query(EstateExecution).count()
    assert "start" not in worker.verbs()


def test_competing_advances_do_not_duplicate_dispatch(db, frontier, monkeypatch):
    add, _ = frontier
    add()
    run_id = activate(db)
    entered, release = threading.Event(), threading.Event()
    original = rt.refresh_frontier
    calls, results = [], []

    def hold_frontier(scope):
        entered.set()
        assert release.wait(10)
        return original(scope)

    monkeypatch.setattr(rt, "refresh_frontier", hold_frontier)
    monkeypatch.setattr(estate_router, "run_task", lambda task: (calls.append(task), read_result())[1])

    def advance_worker():
        with cdb.SessionLocal() as other:
            results.append(rt.advance(other, run_id))

    thread = threading.Thread(target=advance_worker)
    thread.start()
    try:
        assert entered.wait(5)
        other = rt.advance(db, run_id)
        assert other["checkpoint"]["phase"] == "selecting"
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive() and len(results) == 1
    assert len(calls) == 1


def test_stale_approval_claim_gets_read_only_assessment(db, frontier, monkeypatch):
    add, _ = frontier
    add(write=True, approval_required=True)
    calls = []
    monkeypatch.setattr(estate_router, "run_task", lambda task: (calls.append(task), read_result())[1])
    rt.advance(db, activate(db))
    assert len(calls) == 1
    assert calls[0]["task_class"] == "repository-reconnaissance"
    assert "mode" not in calls[0]["routing"]
    assert "re-adjudicate" in calls[0]["objective"]
    assert not db.query(ParkLease).count()


def test_unreported_child_usage_fences_continuation_until_accounted(db, frontier, monkeypatch):
    add, _ = frontier
    add("a")
    add("b")
    calls = []
    monkeypatch.setattr(estate_router, "run_task", lambda task: (calls.append(task), read_result())[1])
    run_id = activate(db)
    result = rt.advance(db, run_id)
    assert result["state"] == "paused"
    execution_id = result["checkpoint"]["usage_accounting_pending"]
    rt.resume_run(db, run_id, "operator")
    assert rt.advance(db, run_id)["state"] == "paused"
    assert len(calls) == 1
    execution = db.get(EstateExecution, execution_id)
    execution.result_json = json.dumps(read_result(usage={"paid_calls": 2, "tool_calls": 10}))
    db.commit()
    rt.resume_run(db, run_id, "operator")
    result = rt.advance(db, run_id)
    assert len(calls) == 2
    assert result["counters"]["paid_calls"] == 3


def test_simultaneous_activations_use_database_singleton_guard(db):
    barrier = threading.Barrier(2)
    outcomes = []

    def start():
        with cdb.SessionLocal() as other:
            barrier.wait(timeout=5)
            try:
                outcomes.append(rt.activate_run(other, "operator")["state"])
            except rt.RunError as exc:
                outcomes.append(exc.status_code)

    threads = [threading.Thread(target=start) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
        assert not thread.is_alive()
    assert sorted(outcomes, key=str) == [409, "requested"]
    assert db.query(LazyUsageRun).count() == 1


def test_read_timeout_is_clamped_before_existing_worker_boundary(monkeypatch):
    from datetime import datetime, timezone
    from src import estate_worker_client
    monkeypatch.setattr(estate_worker_client, "call_worker", fail_dispatch)
    result = estate_router._dispatch_read_only(LAB, "codex", {
        "objective": "bounded", "_activation_deadline":
            (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()})
    assert result["executed"] is False
    assert result["error_code"] == "activation_deadline_exhausted"


def test_verified_quota_fails_over_only_to_qualified_glm_read(db, frontier, monkeypatch):
    add, _ = frontier
    add()
    def route(task, **kwargs):
        provider = task["routing"].get("paid_provider", "codex")
        return {"route": {"executor": "none", "host": LAB, "model_alias": "code-strong"},
                "hosts_checked": [{"host_id": LAB, "qualified_executors": [provider]}]}
    monkeypatch.setattr(estate_router, "resolve_route", route)
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda provider, **kwargs: {
        "allowed": provider == "glm", "state": "ok" if provider == "glm" else "quota_exhausted"})
    calls = []
    monkeypatch.setattr(estate_router, "run_task", lambda task: (calls.append(task), read_result())[1])
    rt.advance(db, activate(db))
    assert len(calls) == 1
    assert calls[0]["routing"]["paid_provider"] == "glm"


def test_observer_without_activation_is_inert(db, monkeypatch):
    monkeypatch.setattr(rt, "advance", fail_dispatch)
    monkeypatch.setattr(estate_router, "reconcile_stale_estate_executions", fail_dispatch)
    assert rt.lifecycle_tick() is None


def test_lifecycle_reconciles_before_advancing_and_cancels(db, monkeypatch):
    run_id = activate(db)
    calls = []
    monkeypatch.setattr(estate_router, "reconcile_stale_estate_executions", lambda *a: calls.append("reconcile"))
    monkeypatch.setattr(rt, "advance", lambda db, rid: calls.append(rid))
    rt.lifecycle_tick()
    assert calls == ["reconcile", run_id]

    async def exercise():
        reached = asyncio.Event()

        async def tick(func):
            reached.set()

        monkeypatch.setattr(rt.asyncio, "to_thread", tick)
        task = asyncio.create_task(rt.lazy_usage_lifecycle_loop())
        await reached.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(exercise())


def client(scopes, owner="operator"):
    app = FastAPI()

    @app.middleware("http")
    async def auth(request: Request, call_next):
        request.state.api_token = True
        request.state.api_token_scopes = scopes
        request.state.api_token_owner = owner
        return await call_next(request)

    app.include_router(setup_lazy_usage_routes())
    return TestClient(app)


@pytest.mark.parametrize("action", ["start", "stop", "pause", "resume"])
def test_api_read_scope_cannot_control_runs(db, action):
    response = client(["estate:read"]).post("/api/lazy-usage/" + action,
                                           json={} if action == "start" else {"run_id": "any"})
    assert response.status_code == 403
    assert not db.query(LazyUsageRun).count()


def test_api_start_conflict_status_history_and_controls(db):
    writer = client(["estate:execute"])
    response = writer.post("/api/lazy-usage/start", json={"budget_overrides": {"max_paid_calls": 99}})
    assert response.status_code == 200
    run = response.json()
    assert run["budgets"]["max_paid_calls"] == 12
    assert writer.post("/api/lazy-usage/start", json={}).status_code == 409
    reader = client(["estate:read"])
    assert reader.get("/api/lazy-usage/status").json()["id"] == run["id"]
    assert reader.get("/api/lazy-usage/status", params={"run_id": run["id"]}).json()["id"] == run["id"]
    assert reader.get("/api/lazy-usage/status", params={"run_id": "missing"}).status_code == 404
    assert client(["estate:read"], "other").get(
        "/api/lazy-usage/status", params={"run_id": run["id"]}).status_code == 403
    assert len(reader.get("/api/lazy-usage/history").json()["runs"]) == 1
    for action, state in (("pause", "paused"), ("resume", "running"), ("stop", "stopped")):
        response = writer.post("/api/lazy-usage/" + action, json={"run_id": run["id"]})
        assert response.status_code == 200 and response.json()["state"] == state
        assert set(response.json()) >= {"counters", "budgets", "checkpoint", "owed_reviews"}
    assert client(["estate:read"], "other").get("/api/lazy-usage/history").json() == {"runs": []}
    assert client(["estate:execute"], "other").post("/api/lazy-usage/stop", json={"run_id": run["id"]}).status_code == 403
    assert client(["chat"]).get("/api/lazy-usage/status").status_code == 403


def test_api_rejects_unauthenticated_request_and_boolean_budgets(db, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv("AUTH_ENABLED", "true")
    app = FastAPI()
    app.state.auth_manager = SimpleNamespace(is_configured=True)
    app.include_router(setup_lazy_usage_routes())
    with TestClient(app) as unauthenticated:
        assert unauthenticated.get("/api/lazy-usage/status").status_code == 401
    assert client(["estate:execute"]).post("/api/lazy-usage/start", json={
        "budget_overrides": {"max_paid_calls": True}}).status_code == 422

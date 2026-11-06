"""Packet routing integration: model verdicts never discharge verification debt."""
import json
from contextlib import contextmanager
from dataclasses import asdict, replace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core import database
from routes.estate_routing_routes import RunTaskEnvelope
from src import estate_router as router, sol_packet_compiler as packets


@pytest.fixture
def packet_run(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    database.RoutingDecision.__table__.create(engine)
    factory = sessionmaker(bind=engine)

    @contextmanager
    def session():
        with factory() as db:
            yield db
            db.commit()

    monkeypatch.setattr(database, "get_db_session", session)
    with session() as db:
        db.add(database.RoutingDecision(id="d", task_class="review", host_id="lab", executor="none", status="needs_escalation"))
    route = {"ok": False, "route": {"host": "lab", "executor": "none", "model_alias": "strong"},
             "decision_id": "d", "escalation_reason": "quality_floor_not_met",
             "hosts_checked": [{"host_id": "lab", "qualified_executors": ["codex"]}]}
    monkeypatch.setattr(router, "resolve_route", lambda task: route)
    monkeypatch.setattr(router, "_resolve_paid_provider", lambda alias: {"provider": "codex"})
    items = [packets.Item(i, "parent", "reviewer", "Q", "review", "medium", "verification",
                         ("e",), ("c",), packets.VERIFICATION_VERDICTS, "none", False,
                         protocol="p", open_judgment=True, shared_context_key="ctx", context_manifest_hash="h",
                         context_tokens=100, unique_tokens=10, output_reserve_tokens=10) for i in ("a", "b")]
    # Synthetic calibration is confined to this fixture; production has no thresholds.
    authority = {"repo": "repo", "shared_context": "context", "items": {i.decision_id: i for i in items},
                 "certificates": [("a", "b")], "policy": packets.Policy({}, 1, 1, 1000, 1000, 4, 1, 2, 1, 0, "fixture-v1")}
    task = {"repo": "repo", "objective": "context", "recommended_route": "codex",
            "routing": {"allow_paid_escalation": True}, "prepared_items": [asdict(i) for i in items]}
    calls = []

    def dispatch(host, executor, envelope, **kwargs):
        body = json.loads(envelope["objective"].split("\n", 1)[1])
        calls.append((host, executor, body))
        return {"ok": True, "placement": {"executed_host": "lab"}, "output": json.dumps({"results": [
            {"decision_id": i["decision_id"], "verdict": "PASS", "rationale": "reviewed", "evidence_refs": ["e"],
             "uncertainty": "", "another_strong_call_could_change": False} for i in body["items"]]})}

    monkeypatch.setattr(router, "_dispatch_read_only", dispatch)
    yield task, authority, calls, route, session
    engine.dispose()


def groups(result):
    return json.loads(result["reason"].split(" | sol_packet=", 1)[1])["groups"]


def test_one_packet_persisted_and_pass_is_only_advice(packet_run):
    task, authority, calls, route, session = packet_run
    result = router.run_task(task, packet_authority=authority)
    assert len(calls) == 1 and len(calls[0][2]["items"]) == 2
    assert result["route"] == route["route"] and result["executed"] is True
    assert result["deterministic_gate"] == "pass" and result["verification_outcome"] == "pending"
    assert result["acceptance"] == "blocked" and not result["ok"]
    assert all(r["verification_outcome"] == "pending" and r["acceptance"] == "blocked" for r in result["packet_results"].values())
    assert groups(result)[0]["policy_evidence_version"] == "fixture-v1"
    with session() as db:
        row = db.get(database.RoutingDecision, "d")
        prefix, call = row.escalation_reason.split(" |call=", 1)
        assert prefix == result["reason"] and row.verification_outcome == "pending"
        assert json.loads(call)["launched"] is False  # placement alone is not a process start
        assert row.status == "needs_escalation" and row.escalation_reason.startswith("quality_floor_not_met |")
    router._update_decision_outcome("d", status="failed", deterministic_gate="fail", escalation_reason="worker_failed")
    with session() as db:
        reason = db.get(database.RoutingDecision, "d").escalation_reason
        assert reason.partition(" |call=")[0].split(" | ")[1] == result["reason"].split(" | ")[1]
        assert reason.endswith(" |call=" + call)


@pytest.mark.parametrize("flag", ["independence_required", "fresh_context_required", "separate_adjudication_required", "independent_model_required"])
@pytest.mark.parametrize("where", ["verification", "requirements"])
def test_parent_mandatory_requirements_force_single_calls(packet_run, flag, where):
    task, authority, calls, _, _ = packet_run
    task[where] = {flag: True}
    result = router.run_task(task, packet_authority=authority)
    assert len(calls) == 2 and all(g["outcome"] == packets.SINGLE for g in groups(result))


@pytest.mark.parametrize("mode", ["untrusted", "no_authority", "unknown", "changed", "mandatory", "no_policy"])
def test_unestablished_authority_or_policy_never_batches(packet_run, mode):
    task, authority, calls, _, _ = packet_run
    if mode == "untrusted":
        task["certificates"] = [("a", "b")]  # direct callers cannot grant compatibility
        authority.pop("certificates")
    elif mode == "no_authority":
        authority = None
    elif mode == "unknown":
        task["prepared_items"][0].pop("independence_required")
    elif mode == "changed":
        task["prepared_items"][0]["question"] = "different question"
    elif mode == "mandatory":
        authority["items"]["a"] = replace(authority["items"]["a"], fresh_context_required=True)
    else:
        authority.pop("policy")
    result = router.run_task(task, packet_authority=authority)
    assert len(calls) == 2 and all(g["outcome"] == packets.SINGLE for g in groups(result))


@pytest.mark.parametrize("bad", ["missing", "duplicate", "malformed", "nonempty", "wrong_host"])
def test_partial_and_invalid_results_are_not_success(packet_run, monkeypatch, bad):
    task, authority, _, _, _ = packet_run
    original = router._dispatch_read_only

    def dispatch(*args, **kwargs):
        result = original(*args, **kwargs)
        entries = json.loads(result["output"])["results"]
        if bad == "missing": entries.pop()
        if bad == "duplicate": entries.append(entries[0])
        if bad == "malformed": entries[0].pop("rationale")
        result["output"] = "PASS" if bad == "nonempty" else json.dumps({"results": entries})
        if bad == "wrong_host": result["placement"]["executed_host"] = "other"
        return result

    monkeypatch.setattr(router, "_dispatch_read_only", dispatch)
    result = router.run_task(task, packet_authority=authority)
    assert result["deterministic_gate"] == "fail" and not result["ok"]
    assert result["verification_outcome"] == "pending" and result["acceptance"] == "blocked"
    assert any(type(r["result"]) is str for r in result["packet_results"].values())


@pytest.mark.parametrize("terminal", [False, True])
def test_persistence_failure_preserves_reason_and_blocks_unconfirmed_dispatch(packet_run, monkeypatch, terminal):
    task, authority, calls, _, _ = packet_run
    original, writes = router._update_decision_outcome, []

    def update(*args, **kwargs):
        writes.append(kwargs)
        return original(*args, **kwargs) if terminal and len(writes) == 1 else False

    monkeypatch.setattr(router, "_update_decision_outcome", update)
    result = router.run_task(task, packet_authority=authority)
    assert len(calls) == int(terminal)
    assert groups(result)[0]["persistence"] == "unconfirmed"
    assert result["reason"].startswith("quality_floor_not_met | sol_packet=") and not result["ok"]


@pytest.mark.parametrize("change", ["duplicate", "mixed_scope", "extra", "overbound", "unprepared"])
def test_invalid_collection_never_dispatches(packet_run, change):
    task, authority, calls, _, _ = packet_run
    if change == "duplicate": task["prepared_items"][1] = task["prepared_items"][0]
    if change == "mixed_scope": task["prepared_items"][1]["parent_task"] = "other"
    if change == "extra": task["prepared_items"][0]["repo"] = "other"
    if change == "overbound": task["prepared_items"] *= 17
    if change == "unprepared":
        for item in task["prepared_items"]: item["evidence_pointers"] = []
    result = router.run_task(task, packet_authority=authority)
    assert not calls and not result["executed"] and all(g["outcome"] == packets.NEEDS_PREPARATION for g in groups(result))


def test_http_plumbing_retains_requirements_and_refuses_unknowns(packet_run):
    task = packet_run[0]
    envelope = RunTaskEnvelope(objective="context", prepared_items=task["prepared_items"],
                               verification={"independent_model_required": True}, requirements={"fresh_context_required": True})
    assert envelope.to_task()["prepared_items"] == task["prepared_items"]
    assert envelope.to_task()["requirements"]["fresh_context_required"] is True
    for extra in ({"packet_authority": {}}, {"certificates": []}, {"prepared_items": [{}] * 33}):
        with pytest.raises(ValidationError): RunTaskEnvelope(**extra)


def test_database_exception_blocks_dispatch_with_reason_intact(packet_run, monkeypatch):
    task, authority, calls, _, _ = packet_run
    def broken_session():
        raise RuntimeError("database unavailable")
    monkeypatch.setattr(database, "get_db_session", broken_session)
    result = router.run_task(task, packet_authority=authority)
    assert not calls and groups(result)[0]["persistence"] == "unconfirmed"
    assert groups(result)[0]["reason"] == "all_admission_tests_passed"


@pytest.mark.parametrize("lane", ["local", "no_paid_escalation"])
def test_prepared_items_outside_the_paid_advisory_lane_are_refused(packet_run, monkeypatch, lane):
    task, authority, calls, route, _ = packet_run
    if lane == "local":
        monkeypatch.setattr(router, "resolve_route", lambda t: {**route, "ok": True, "route": {"host": "lab", "executor": "local"}})
    else:
        task["routing"] = {}
    result = router.run_task(task, packet_authority=authority)
    assert not calls and not result["ok"] and not result["executed"]
    assert result["execution_error"] == "prepared items require the read-only advisory lane"

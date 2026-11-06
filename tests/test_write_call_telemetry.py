"""Write acknowledgements update one existing call suffix; observation never counts."""
import json

import pytest

from core import database as cdb
from src import estate_router as router, estate_write_lane as lane
from tests.test_estate_stage6_control import db, worker, _lease, _dispatch, _row, HOME  # noqa: F401

SUBJECT, HEAD = "odysseus:pr:225", "b" * 64
PREFIX = 'insufficient_capability | sol_packet={"groups":[]} | trace={"v":2}'


def decision(key="D"):
    with cdb.get_db_session() as session:
        session.add(cdb.RoutingDecision(id=key, task_class="code_review", host_id=HOME,
                                       executor="codex-write", status="pending", escalation_reason=PREFIX))


def calls():
    with cdb.get_db_session() as session:
        return [(r.escalation_reason, json.loads(r.escalation_reason.split(" |call=", 1)[1]))
                for r in session.query(cdb.RoutingDecision).all() if " |call=" in (r.escalation_reason or "")]


def start(**extra):
    return _dispatch(decision_id="D", subject=SUBJECT, head_sha=HEAD, **extra)


def test_envelope_to_write_start_final_suffix_and_polling(db, worker, monkeypatch):
    from routes.estate_routing_routes import RunTaskEnvelope
    _lease()
    decision()
    route = {"decision_id": "D", "route": {"executor": "none", "host": HOME},
             "hosts_checked": [{"host_id": HOME, "qualified_executors": ["codex-write"]}]}
    monkeypatch.setattr(router, "resolve_route", lambda task: route)
    monkeypatch.setattr(lane, "_trigger_background_reconcile", lambda: None)
    monkeypatch.setattr(router, "_resolve_paid_provider", lambda alias: {"provider": "codex"})
    task = RunTaskEnvelope(objective="review", repo="odysseus", mode="implementation",
                           allow_paid_escalation=True, subject=SUBJECT, head_sha=HEAD).to_task()
    task["recommended_route"] = "codex"
    result = router.run_task(task)
    assert result["ok"] and result["execution"]["dispatch"] == "new"
    reason, call = calls()[0]
    assert reason.startswith(PREFIX) and reason.endswith(" |call=" + json.dumps(call, separators=(",", ":")))
    assert call["subject"] == SUBJECT and call["head_sha"] == HEAD and call["launched"] is True
    assert call["started_at"].endswith("+00:00") and len(reason.split(" |call=")[1]) < 512
    execution = result["execution_id"]
    lane._dispatch_start(execution)
    worker.set_state(execution, "succeeded", result={"ok": True, "output": "reviewed"})
    lane._transition(execution, ("running",), last_observed_at=None)
    polled_calls = []
    monkeypatch.setattr(router, "_record_advisory_call", lambda *a, **k: polled_calls.append(True))
    for _ in range(2):
        lane.get_estate_execution(execution, wait_s=20)
    assert len(calls()) == 1 and calls()[0][1] == call and _row(execution).lifecycle_state == "succeeded"
    assert calls()[0][0].startswith('insufficient_capability | sol_packet=')
    assert worker.verbs().count("status") >= 1 and polled_calls == []


@pytest.mark.parametrize("refusal", ["lease", "dirty", "ambiguous"])
def test_refusals_and_proven_not_started_never_count(db, worker, refusal):
    decision()
    if refusal != "lease":
        _lease()
    if refusal == "dirty":
        worker.clean = False
    if refusal == "ambiguous":
        worker.fail["start"] = ["worker_unreachable", "authority_denied"]
    result = start()
    assert result["ok"] is (refusal == "ambiguous")
    assert all(not call["launched"] and call["started_at"] is None for _, call in calls())
    if refusal == "ambiguous":
        assert _row(result["execution_id"]).worktree_resolution == "not_started"


def test_retry_redrive_reuse_and_status_never_double_count(db, worker):
    _lease()
    decision()
    worker.start_mode = "lost_after_spawn"
    result = start()
    first = calls()[0][1]
    assert first["launched"] is True and worker.verbs().count("start") == 2
    for _ in range(2):
        lane._dispatch_start(result["execution_id"])
        lane.get_estate_execution(result["execution_id"])
    decision("reuse")
    reused = _dispatch(decision_id="reuse", subject=SUBJECT, head_sha=HEAD)
    assert reused["dispatch"] == "reused_in_flight"
    assert len(calls()) == 2 and sum(c["launched"] for _, c in calls()) == 1
    assert next(c for _, c in calls() if c["launched"]) == first


@pytest.mark.parametrize("subject,head", [(42, {}), ("repo:pr:é", "A" * 40), (None, None)])
def test_invalid_values_and_absent_head_never_use_admission_head(db, worker, subject, head):
    _lease()
    decision()
    result = _dispatch(decision_id="D", subject=subject, head_sha=head)
    assert result["ok"] and _row(result["execution_id"]).admission_head_sha
    assert calls()[0][1]["subject"] is None and calls()[0][1]["head_sha"] is None
    assert calls()[0][1]["launched"] is True


def test_recorder_exception_preserves_result_and_lifecycle(db, worker, monkeypatch):
    _lease()
    decision()
    attempted = []
    def broken(*args, **kwargs):
        attempted.append(True)
        raise RuntimeError("telemetry unavailable")
    monkeypatch.setattr(router, "_record_advisory_call", broken)
    result = start()
    row = _row(result["execution_id"])
    assert result["ok"] and row.lifecycle_state == "accepted" and row.worktree_resolution == "unresolved"
    assert attempted == [True, True] and worker.verbs() == ["worktree.verify", "start"] and not calls()


def test_no_decision_creates_no_routing_row(db, worker):
    _lease()
    result = _dispatch(subject=SUBJECT, head_sha=HEAD)
    assert result["ok"] and not calls()
    with cdb.get_db_session() as session:
        assert session.query(cdb.RoutingDecision).count() == 0

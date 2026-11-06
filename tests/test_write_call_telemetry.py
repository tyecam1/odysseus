"""Admitted submissions count once, independently of worker lifecycle observations."""
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import text

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


@pytest.mark.parametrize("mode", ["normal", "lost_after_spawn", "lost_both", "refuse", "self_check"])
def test_submission_final_suffix_survives_recovery_polling_and_terminal(db, worker, monkeypatch, mode):
    _lease(); decision()
    recorder = Mock(wraps=router._call_suffix)
    monkeypatch.setattr(router, "_call_suffix", recorder)
    worker.start_mode = mode if mode in ("lost_after_spawn", "refuse") else "normal"
    real_start = worker._start
    def answer(payload):
        assert len(calls()) == 1 and calls()[0][0].startswith(PREFIX)  # committed before start
        reply = real_start(payload)
        if mode == "lost_both":
            worker._raise("worker_unreachable")
        if mode == "self_check":
            worker.set_state(payload["execution_id"], "start_failed")
        return reply
    monkeypatch.setattr(worker, "_start", answer)
    result = _dispatch(decision_id="D", subject=SUBJECT, head_sha=HEAD)
    execution = result["execution_id"]
    reason, call = calls()[0]
    assert result["ok"] and reason.endswith(" |call=" + json.dumps(call, separators=(",", ":")))
    assert call == {"v": 1, "subject": SUBJECT, "head_sha": HEAD, "submitted": True,
                    "execution_id": execution, "started_at": _row(execution).submitted_at.replace(tzinfo=timezone.utc).isoformat()}
    assert datetime.fromisoformat(call["started_at"]).utcoffset().total_seconds() == 0
    assert len(reason.partition(" |call=")[2].encode()) + len(" |call=") <= 512
    if mode == "lost_both":
        assert worker.verbs().count("start") == 2 and any(p.get("fence") for _, v, p in worker.calls if v == "status")
    monkeypatch.setattr(lane, "_trigger_background_reconcile", lambda: None)
    for _ in range(2):
        lane._dispatch_start(execution)
        lane._transition(execution, ("accepted", "running"), last_observed_at=None)
        lane.get_estate_execution(execution, wait_s=1)
    worker.set_state(execution, "succeeded", result={"ok": True, "output": "reviewed"})
    lane._apply_view(execution, worker._view(execution))
    assert _row(execution).lifecycle_state == ("failed" if mode in ("refuse", "self_check") else "succeeded")
    assert len(calls()) == 1 and calls()[0][1] == call and calls()[0][0].endswith(reason[reason.index(" |call="):])
    assert ' | sol_packet={"groups":[]} | trace={"v":2}' in calls()[0][0] and recorder.call_count == 1
    sql = Path("docs/aoteru-model-host-routing-contract.md").read_text().split("```sql\n", 1)[1].split("```", 1)[0]
    with cdb.get_db_session() as session:
        assert session.execute(text(sql)).all() == [(SUBJECT, 1, 0)]


@pytest.mark.parametrize("refusal", ["lease", "dirty"])
def test_pre_admission_refusals_write_nothing(db, worker, refusal):
    decision()
    if refusal == "dirty":
        _lease(); worker.clean = False
    result = _dispatch(decision_id="D", subject=SUBJECT, head_sha=HEAD)
    assert not result["ok"] and result["error_code"] == ("write_lease_missing" if refusal == "lease" else "worktree_not_clean")
    assert not calls()
    with cdb.get_db_session() as session:
        assert session.query(cdb.EstateExecution).count() == 0


@pytest.mark.parametrize("metadata", [(42, {}), ("repo:pr:é", "A" * 40), (None, None), "broken", "no_decision"])
def test_invalid_missing_metadata_and_failure_are_fail_open(db, worker, monkeypatch, metadata):
    _lease(); decision()
    if metadata == "broken":
        monkeypatch.setattr(router, "_call_suffix", Mock(side_effect=RuntimeError("telemetry unavailable")))
    subject, head = metadata if isinstance(metadata, tuple) else (SUBJECT, HEAD)
    result = _dispatch(decision_id=None if metadata == "no_decision" else "D", subject=subject, head_sha=head)
    row = _row(result["execution_id"])
    assert result["ok"] and row.lifecycle_state == "accepted" and row.worktree_resolution == "unresolved"
    assert row.admission_head_sha and worker.verbs() == ["worktree.verify", "start"]
    if metadata in ("broken", "no_decision"):
        assert not calls()
    else:
        assert calls()[0][1]["subject"] is None and calls()[0][1]["head_sha"] is None
        assert calls()[0][1]["submitted"] is True

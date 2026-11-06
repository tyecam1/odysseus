"""Call counts come from process starts, never placement or successful advice."""
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from core import database
from routes.estate_routing_routes import RunTaskEnvelope
from src import estate_router as router, sol_packet_compiler as packets
from tests.test_provider_quota_health import lab, fixture_config, record_outcome, TASK, LIMIT  # noqa: F401

SUBJECT, HEAD = "odysseus:pr:219", "a" * 40


def run(**extra):
    return router.run_task({**TASK, "subject": SUBJECT, "head_sha": HEAD,
                            "routing": {"allow_paid_escalation": True}, **extra})


def records():
    with database.get_db_session() as db:
        reasons = [r.escalation_reason for r in db.query(database.RoutingDecision).all()
                   if " |call=" in (r.escalation_reason or "")]
    return [(reason, json.loads(reason.split(" |call=", 1)[1])) for reason in reasons]


@pytest.mark.parametrize("items", [0, 1, 2])
def test_actual_launch_and_packets_keep_final_suffix(lab, items):
    lab[1]("", success=True)
    extra = {}
    if items:
        item = packets.Item("a", "parent", "reviewer", "Q", "review", "medium", "verification",
                            ("e",), ("c",), packets.VERIFICATION_VERDICTS, "none", False,
                            protocol="p", open_judgment=True, shared_context_key="ctx", context_manifest_hash="h",
                            context_tokens=100, unique_tokens=10, output_reserve_tokens=10)
        extra = {"repo": "odysseus", "prepared_items": [{**asdict(item), "decision_id": str(i)} for i in range(items)]}
    result = run(**extra)
    assert result["executed"]
    saved = records()
    assert len(saved) == max(items, 1) == len(lab[2].read_text().splitlines())
    for reason, call in saved:
        assert call["v"] == 1 and call["subject"] == SUBJECT and call["head_sha"] == HEAD
        assert call["launched"] is True and datetime.fromisoformat(call["started_at"]).utcoffset().total_seconds() == 0
        assert len((" |call=" + reason.split(" |call=")[1]).encode()) <= 512
        if items:
            packet = json.loads(reason.split(" | sol_packet=", 1)[1].split(" |call=", 1)[0])
            assert len(packet["groups"]) == items
    sql = (Path(__file__).parents[1] / "docs/aoteru-model-host-routing-contract.md").read_text().split("```sql\n", 1)[1].split("```", 1)[0]
    with database.get_db_session() as db:
        assert db.execute(text(sql)).all() == [(SUBJECT, max(items, 1), max(items, 1) - 1)]


def test_quota_admission_is_not_a_call(lab):
    record_outcome({"ok": False, "error": LIMIT})
    result = run()
    assert not result["executed"] and "quota_exhausted" in result["execution_error"]
    assert not lab[2].exists()
    assert len(records()) == 1
    call = records()[0][1]
    assert call["subject"] == SUBJECT and call["launched"] is False and call["started_at"] is None


@pytest.mark.parametrize("subject,head", [
    ("odysseus:pr:" + "x" * 160, "a" * 65), ("a" * 513, "g" * 40),
    ("odysseus:pr:Review this", "A" * 40), ("https://host/pr/219", "a" * 39),
    ("odysseus:pr:é", "a" * 41), ("/repo:pr:219", "a" * 63),
    ("odysseus:unknown:219", "0" * 64 + "\n"), (None, None), (42, {}),
])
def test_invalid_metadata_is_unknown_without_changing_execution(lab, subject, head):
    lab[1]("", success=True)
    task = RunTaskEnvelope(task_class="code_review", objective=TASK["objective"],
                           requirements=TASK["requirements"], allow_paid_escalation=True,
                           subject=subject, head_sha=head).to_task()
    assert task["subject"] == subject and task["head_sha"] == head
    result = router.run_task(task)
    assert result["ok"] and result["execution"]["output"] == "review complete"
    call = records()[0][1]
    assert call["subject"] is None and call["head_sha"] is None and call["launched"] is True


def test_telemetry_exception_cannot_change_dispatch_or_result(lab, monkeypatch):
    lab[1]("", success=True)
    attempted = []
    def broken(*args):
        attempted.append(True)
        raise RuntimeError("telemetry unavailable")
    monkeypatch.setattr(router, "_record_advisory_call", broken, raising=False)
    result = run()
    assert attempted == [True] and lab[2].read_text().splitlines() == ["call"]
    assert result["ok"] and result["executed"] and result["execution"]["output"] == "review complete"
    assert "_advisory_launch" not in result["execution"]
    assert not records()


def test_terminal_update_preserves_all_namespaces(lab):
    lab[1]("", success=True)
    result = run()
    before, call = records()[0]
    router._update_decision_outcome(result["decision_id"], status="failed", deterministic_gate="fail",
                                    escalation_reason='worker_failed | sol_packet={"groups":[]} | trace={"v":2}')
    after, retained = records()[0]
    assert after.startswith('worker_failed | sol_packet={"groups":[]} | trace={"v":2}')
    assert after.endswith(before[before.index(" |call="):]) and retained == call
    router._update_decision_outcome(result["decision_id"], status="complete", deterministic_gate="pass",
                                    escalation_reason="recovered")
    assert records()[0][0] == after.replace("worker_failed", "recovered", 1)


def test_reuse_does_not_count_again_and_full_sha256_is_retained(lab, monkeypatch):
    lab[1]("", success=True)
    cached = router._dispatch_read_only("test-lab", "codex", TASK)
    monkeypatch.setattr(router, "_dispatch_read_only", lambda *a, **k: cached)
    assert run(head_sha="b" * 64)["ok"]
    assert run()["ok"]
    calls = [call for _, call in records()]
    assert sorted(c["launched"] for c in calls) == [False, True]
    assert next(c for c in calls if c["launched"])["head_sha"] == "b" * 64
    assert lab[2].read_text().splitlines() == ["call"]


def test_envelope_forwards_subject_and_refuses_unknown_fields():
    task = RunTaskEnvelope(subject=SUBJECT, head_sha=HEAD).to_task()
    assert (task["subject"], task["head_sha"]) == (SUBJECT, HEAD)
    with pytest.raises(ValidationError):
        RunTaskEnvelope(subject_typo=SUBJECT)


def test_item_text_cannot_forge_the_call_delimiter(lab):
    lab[1]("", success=True)
    item = packets.Item("a", "parent", "reviewer", "Q", "review", "medium", "verification",
                        ("e",), ("c",), packets.VERIFICATION_VERDICTS, "none", False,
                        protocol="p", open_judgment=True, shared_context_key="ctx", context_manifest_hash="h",
                        context_tokens=100, unique_tokens=10, output_reserve_tokens=10)
    run(repo="odysseus", prepared_items=[{**asdict(item), "decision_id": "item |call=note"}])
    (reason, call), = records()
    assert reason.count(" |call=") == 1 and call["launched"] is True
    packet = json.loads(reason.split(" | sol_packet=", 1)[1].split(" |call=", 1)[0])
    assert "item |call=note" in json.dumps(packet)
    sql = (Path(__file__).parents[1] / "docs/aoteru-model-host-routing-contract.md").read_text().split("```sql\n", 1)[1].split("```", 1)[0]
    with database.get_db_session() as db:
        assert db.execute(text(sql)).all() == [(SUBJECT, 1, 0)]

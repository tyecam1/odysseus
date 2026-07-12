from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.misumi_operator_runtime import HeartbeatRuntime, OperatorConferenceStore


def test_operator_conference_lifecycle(tmp_path: Path):
    store = OperatorConferenceStore(tmp_path)
    event = store.create(
        requesting_persona="aoteru",
        reason="Aoteru needs the Operator to confer on running loops.",
        context_summary="User asked what loops are running; no operator event existed.",
        timeout_seconds=60,
    )

    assert event["status"] == "pending"
    assert event["event_id"] == event["id"]
    assert event["writes_allowed"] is False

    pending, corrupt = store.list(status="pending")
    assert corrupt == 0
    assert [item["id"] for item in pending] == [event["id"]]

    responded = store.respond(event["id"], response="Operator confirms no loop is running until heartbeat is started.")
    assert responded["status"] == "responded"
    assert "no loop is running" in responded["response"]

    with pytest.raises(ValueError):
        store.respond(event["id"], response="Second response should be rejected.")


def test_operator_conference_timeout_is_explicit(tmp_path: Path):
    store = OperatorConferenceStore(tmp_path)
    event = store.create(requesting_persona="aoteru", reason="timeout test", timeout_seconds=30)

    path = tmp_path / "operator_conferences.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["expires_at"] = "2000-01-01T00:00:00Z"
    path.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")

    expired = store.get(event["id"])
    assert expired["status"] == "expired"
    assert expired["timeout_result"] == "operator did not respond before timeout"


def test_heartbeat_status_distinguishes_loop_state(tmp_path: Path):
    heartbeat = HeartbeatRuntime(tmp_path)
    status = heartbeat.status()

    assert status["registered_count"] == 7
    assert status["running_count"] == 0
    assert status["writes_allowed"] is False
    assert {item["loop_id"] for item in status["loops"]} >= {
        "operator_handoff_loop",
        "regression_guard_loop",
        "proposal_consolidation_loop",
    }
    for loop in status["loops"]:
        assert loop["registered"] is True
        assert loop["currently_running"] is False
        assert loop["permission_mode"] == "propose"
        assert loop["backend"]["token_exposed_to_browser"] is False


def test_heartbeat_run_once_outputs_proposal_only(tmp_path: Path):
    heartbeat = HeartbeatRuntime(tmp_path)
    result = heartbeat.run_once(
        "operator_handoff_loop",
        input_summary="Aoteru claimed operator status but no operator conference event existed.",
    )

    assert result["run"]["status"] == "success"
    assert result["run"]["writes_allowed"] is False
    assert result["proposal"]["requires_human_ratification"] is True
    assert result["proposal"]["writes_allowed"] is False
    assert "event_id" in result["proposal"]["finding"] or "conference" in result["proposal"]["finding"]
    assert Path(result["run"]["output_artifact"]).is_file()

    after = heartbeat.status()
    by_id = {item["loop_id"]: item for item in after["loops"]}
    assert by_id["operator_handoff_loop"]["last_successful_run"] is not None
    assert by_id["operator_handoff_loop"]["last_output_artifact"] == result["run"]["output_artifact"]


def test_heartbeat_rejects_unknown_loop(tmp_path: Path):
    heartbeat = HeartbeatRuntime(tmp_path)
    with pytest.raises(KeyError):
        heartbeat.run_once("free_running_self_mutation_loop")

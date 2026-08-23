"""Tests for src.routing_evaluator.get_decision_by_id — the "logs/result
pointers surface" Workstream K's next_action asked for. Every
POST /api/estate/run response and `agent explain <alias>` evidence entry
already returns a decision_id; this closes the other half, looking that
id back up afterward, at the module level, the `agent decision <id>` CLI
subcommand, and GET /api/estate/decision/{id}.
"""
import uuid

import pytest

from src.routing_evaluator import get_decision_by_id


def _make_decision(**overrides):
    from core.database import RoutingDecision
    fields = dict(
        id=str(uuid.uuid4()), task_class="test-task-class", host_id="test-lab",
        executor="local", model_alias="local-fast", concrete_model="qwen3:8b",
        status="complete", escalated=False, retries=0, deterministic_gate="pass",
        latency_ms=123,
    )
    fields.update(overrides)
    return RoutingDecision(**fields)


@pytest.fixture(autouse=True)
def _clean_decisions():
    from core.database import RoutingDecision, get_db_session
    with get_db_session() as db:
        db.query(RoutingDecision).filter(RoutingDecision.task_class == "test-task-class").delete(synchronize_session=False)
    yield
    with get_db_session() as db:
        db.query(RoutingDecision).filter(RoutingDecision.task_class == "test-task-class").delete(synchronize_session=False)


def test_get_decision_by_id_returns_full_row():
    from core.database import get_db_session
    decision_id = str(uuid.uuid4())
    with get_db_session() as db:
        db.add(_make_decision(id=decision_id))

    row = get_decision_by_id(decision_id)
    assert row["id"] == decision_id
    assert row["task_class"] == "test-task-class"
    assert row["executor"] == "local"
    assert row["concrete_model"] == "qwen3:8b"
    assert row["deterministic_gate"] == "pass"
    assert row["latency_ms"] == 123
    assert row["created_at"]


def test_get_decision_by_id_unknown_id_returns_none():
    assert get_decision_by_id("does-not-exist") is None


def test_agent_decision_cli_prints_the_row(monkeypatch, capsys):
    import importlib.machinery
    import importlib.util
    import json
    import sys
    from pathlib import Path

    from core.database import get_db_session

    decision_id = str(uuid.uuid4())
    with get_db_session() as db:
        db.add(_make_decision(id=decision_id, executor="codex", escalated=True))

    root = Path(__file__).resolve().parents[1]
    loader = importlib.machinery.SourceFileLoader("agent_cli_decision", str(root / "scripts" / "agent"))
    spec = importlib.util.spec_from_loader("agent_cli_decision", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)

    monkeypatch.setattr(sys, "argv", ["agent", "decision", decision_id])
    rc = module.run(module._build_parser())
    out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert out["id"] == decision_id
    assert out["executor"] == "codex"
    assert out["escalated"] is True


def test_agent_decision_cli_unknown_id_fails_cleanly(monkeypatch, capsys):
    import importlib.machinery
    import importlib.util
    import sys
    from pathlib import Path

    import pytest

    root = Path(__file__).resolve().parents[1]
    loader = importlib.machinery.SourceFileLoader("agent_cli_decision2", str(root / "scripts" / "agent"))
    spec = importlib.util.spec_from_loader("agent_cli_decision2", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)

    monkeypatch.setattr(sys, "argv", ["agent", "decision", "does-not-exist"])
    with pytest.raises(SystemExit) as exc:
        module.run(module._build_parser())
    err = capsys.readouterr().err

    assert exc.value.code == 1
    assert "no routing decision found" in err

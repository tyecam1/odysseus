"""Tests for `agent status`'s recent-RoutingDecision summary (Workstream K
next_action: "recent-RoutingDecision summary directly in `agent status`" —
`agent explain <alias>` already covers per-alias evidence via
src.routing_evaluator; status previously had no at-a-glance 'what just ran'
view at all, only the lease view added earlier this workstream).
"""
import importlib.machinery
import importlib.util
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "agent"


def load_module():
    loader = importlib.machinery.SourceFileLoader("agent_cli_recent_decisions", str(SCRIPT_PATH))
    spec = importlib.util.spec_from_loader("agent_cli_recent_decisions", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


def _make_decision(**overrides):
    from core.database import RoutingDecision
    fields = dict(
        id=str(uuid.uuid4()), task_class="test-task-class", host_id="test-lab",
        executor="local", model_alias="local-fast", status="complete",
        escalated=False, retries=0,
    )
    fields.update(overrides)
    return RoutingDecision(**fields)


def test_recent_routing_decisions_summary_orders_newest_first_and_bounds_limit():
    from core.database import get_db_session, RoutingDecision

    marker = str(uuid.uuid4())
    with get_db_session() as db:
        db.query(RoutingDecision).filter(RoutingDecision.task_class == marker).delete(synchronize_session=False)
        for i in range(3):
            db.add(_make_decision(task_class=marker, id=f"{marker}-{i}"))

    module = load_module()
    summary = module._recent_routing_decisions_summary(limit=2)
    assert len(summary) <= 2
    # newest-first: created_at should be non-increasing across the returned rows
    timestamps = [row["created_at"] for row in summary if row["created_at"]]
    assert timestamps == sorted(timestamps, reverse=True)

    with get_db_session() as db:
        db.query(RoutingDecision).filter(RoutingDecision.task_class == marker).delete(synchronize_session=False)


def test_recent_routing_decisions_summary_includes_expected_fields():
    from core.database import get_db_session, RoutingDecision

    marker = str(uuid.uuid4())
    with get_db_session() as db:
        db.add(_make_decision(
            task_class=marker, id=marker, executor="codex", model_alias="code-strong",
            status="complete", escalated=True, retries=1,
        ))

    module = load_module()
    summary = module._recent_routing_decisions_summary(limit=50)
    row = next(r for r in summary if r["id"] == marker)
    assert row["task_class"] == marker
    assert row["executor"] == "codex"
    assert row["model_alias"] == "code-strong"
    assert row["escalated"] is True
    assert row["retries"] == 1

    with get_db_session() as db:
        db.query(RoutingDecision).filter(RoutingDecision.task_class == marker).delete(synchronize_session=False)


def test_recent_routing_decisions_summary_degrades_to_empty_on_db_error(monkeypatch):
    """A missing/unreachable DB must not crash `agent status` — same
    best-effort degrade pattern as _active_park_leases_summary()."""
    module = load_module()
    import core.database as database

    def boom():
        raise RuntimeError("db unavailable")
    monkeypatch.setattr(database, "get_db_session", boom)

    assert module._recent_routing_decisions_summary() == []

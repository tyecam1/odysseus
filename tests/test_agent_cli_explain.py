"""Tests for `agent explain <alias>` (Workstream K's "why this route?"
diagnostic). Mocks src.estate_router/src.routing_evaluator entirely — this
is about cmd_explain's own assembly/output-shape logic, not re-testing
resolve_alias/eligible_hosts/aggregation math, which already have their
own test files.
"""
import argparse
import importlib.machinery
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "agent"


def load_module():
    loader = importlib.machinery.SourceFileLoader("agent_cli_explain", str(SCRIPT_PATH))
    spec = importlib.util.spec_from_loader("agent_cli_explain", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


def _args(alias="local-fast", **kw):
    ns = argparse.Namespace(alias=alias, repo=None, pretty=False)
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def test_explain_assembles_resolution_hosts_and_evidence(monkeypatch, capsys):
    module = load_module()
    import src.estate_router as estate_router
    import src.routing_evaluator as routing_evaluator

    monkeypatch.setattr(estate_router, "resolve_alias", lambda alias: {
        "alias": alias, "resolved": True, "concrete_model": "qwen3:8b", "evidence": "docs/x.md",
    })
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo=None: [
        {"host_id": "hz2-workstation", "role": "lab", "eligible": True, "reason": "this host"},
    ])

    class FakeAgg:
        model_alias = "local-fast"
        def to_dict(self):
            return {"task_class": "coding", "n": 4, "success_rate": 0.75}

    monkeypatch.setattr(routing_evaluator, "load_and_aggregate", lambda: [FakeAgg()])

    module.cmd_explain(_args())
    out = capsys.readouterr().out
    assert '"resolved": true' in out
    assert '"host_id": "hz2-workstation"' in out
    assert '"task_class": "coding"' in out


def test_explain_reports_no_evidence_without_failing(monkeypatch, capsys):
    module = load_module()
    import src.estate_router as estate_router
    import src.routing_evaluator as routing_evaluator

    monkeypatch.setattr(estate_router, "resolve_alias", lambda alias: {
        "alias": alias, "resolved": False, "reason": "no evidence-backed binding yet",
    })
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo=None: [])
    monkeypatch.setattr(routing_evaluator, "load_and_aggregate", lambda: [])

    module.cmd_explain(_args(alias="code-strong"))
    out = capsys.readouterr().out
    assert "no recorded routing decisions" in out


def test_explain_degrades_gracefully_when_evaluator_db_unavailable(monkeypatch, capsys):
    """A caller running `agent explain` off-host or without DB access
    should still get the resolution/eligibility answer, not a crash —
    the evaluator query is best-effort context, not the point of the
    command."""
    module = load_module()
    import src.estate_router as estate_router
    import src.routing_evaluator as routing_evaluator

    monkeypatch.setattr(estate_router, "resolve_alias", lambda alias: {"alias": alias, "resolved": True})
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo=None: [])

    def _boom():
        raise RuntimeError("no database configured")
    monkeypatch.setattr(routing_evaluator, "load_and_aggregate", _boom)

    module.cmd_explain(_args())
    out = capsys.readouterr().out
    assert "no recorded routing decisions" in out

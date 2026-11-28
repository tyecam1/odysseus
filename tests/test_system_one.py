from pathlib import Path

import pytest
import yaml

from src import estate_router
from src.system_one import CONTRACT, Decision, DecisionError, UnsupportedPrimitive, configured_adapter, tuner_vector


def test_native_contract_and_closed_candidates():
    adapter = configured_adapter("clm-8b", "local", ["choice", "score", "noul", "rank"],
                                 "model", "checkpoint", "http://127.0.0.1:8700")
    rank = Decision.rank("State", ["a", "b"])
    reply = {"model": "model", "ranked": [{"candidate": "b", "prob": 0.7}, {"candidate": "a", "prob": 0.3}]}
    assert adapter.decode(rank, reply, 2).selected == "b"
    reply["ranked"][1]["candidate"] = "invented"
    with pytest.raises(DecisionError, match="candidate_mismatch"):
        adapter.decode(rank, reply, 2)
    score = Decision.score("State", "How much?", ["low", "high"])
    reply = {"model": "model", "answers": {"decision": {
        "legend": {"0": "low", "1": "high"}, "probabilities": {"0": 0.25, "1": 0.75},
    }}}
    assert adapter.decode(score, reply, 2).expected_score == 0.75
    noul = Decision.noul("State", "Enough information?")
    reply["answers"]["decision"] = {"noul": 0.2}
    assert adapter.decode(noul, reply, 2).selected == "false"
    reply["usage"] = {"state_tokens_dropped": 1}
    with pytest.raises(DecisionError, match="truncated"):
        adapter.decode(noul, reply, 2)


def test_unsupported_and_remote_approval_precede_http():
    jev = configured_adapter("jev", "remote", ["choice"], "model", "rev", "https://api.typesafe.ai")
    with pytest.raises(UnsupportedPrimitive):
        jev.decide(Decision.rank("State", ["a", "b"]), timeout=1)
    with pytest.raises(DecisionError, match="remote_approval_required"):
        jev.decide(Decision.choice("State", "Which?", {"a": "A", "b": "B"}), timeout=1)
    with pytest.raises(DecisionError, match="loopback"):
        configured_adapter("laya", "local", ["choice"], "model", "rev", "http://127.0.0.1.example.com")


@pytest.fixture
def telemetry(monkeypatch):
    rows = []
    monkeypatch.setattr(estate_router, "_record_decision", lambda *_, **__: "decision-id")
    def update(*_, **outcome):
        rows.append(outcome)
        return True

    monkeypatch.setattr(estate_router, "_update_decision_outcome", update)
    return rows


def test_stock_config_has_no_promoted_route_and_rejects_scope_overrides(telemetry):
    decision = Decision.choice("Private text", "Which paper?", {"unpublished-id": "paper", "other": "other"})
    result = estate_router.research_decision("paper-triage", decision, parent_run_id="run")
    assert result["escalation_reason"] == "no_adequate_system_one_route"
    assert result["selected"] is None
    assert "Private text" not in str(telemetry)
    assert "unpublished-id" not in str(telemetry)
    providers = estate_router.research_decision_providers()
    assert set(providers) == {"jev", "clm-8b", "laya"}
    assert all(not provider["enabled"] for provider in providers.values())
    profiles = yaml.safe_load(Path("config/system-one-tuners.yaml").read_text())
    with pytest.raises(DecisionError, match="eight research tuners"):
        tuner_vector(profiles, "red-team", {"evidence_ceiling": 0})
    for invalid in (True, -0.1, 1.1, float("nan")):
        with pytest.raises(DecisionError):
            tuner_vector(profiles, "red-team", {"exploration": invalid})


def test_routing_prioritises_only_candidates_and_escalates_high_consequence(monkeypatch, telemetry):
    from src.system_one import Adapter

    original = estate_router._load_yaml
    binding = {
        "task_class": "next-action", "provider": "laya", "host": "lab", "primitive": "choice",
        "contract": CONTRACT, "languages": ["en"], "max_request_bytes": 1000, "min_options": 2,
        "max_options": 3, "p95_latency_ms": 10, "brier": 0.1, "accuracy": 0.9,
        "brier_ceiling": 0.2, "accuracy_floor": 0.8,
        "min_confidence": 0.38, "reviewed": True, "held_out_evidence": "test-only",
        "model": "model", "checkpoint": "rev", "endpoint": "http://127.0.0.1:8000",
    }
    decision = Decision.choice("State", "Which?", {"counterexample-search": "red team", "search": "search", "extract": "extract"})
    spec = {"system_one": {"adapters": {"laya": {
        "enabled": True, "placement": "local", "primitives": ["choice"],
    }}, "bindings": [binding]}}
    monkeypatch.setattr(estate_router, "_load_yaml", lambda name: spec if name == "models" else original(name))
    monkeypatch.setattr(estate_router, "current_host_id", lambda: "lab")
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda: [
        {"host_id": "lab", "eligible": True, "qualified_executors": ["local"]},
    ])

    def decide(self, request, **kwargs):
        return self.decode(request, {"model": "model", "answers": {"decision": {
            "choice": "search", "probabilities": {"counterexample-search": 0.4, "search": 0.5, "extract": 0.1},
        }}}, 1)
    monkeypatch.setattr(Adapter, "decide", decide)
    baseline = estate_router.research_decision("next-action", decision, parent_run_id="run")
    changed = estate_router.research_decision("next-action", decision, parent_run_id="run",
                                              profile="red-team", overrides={"exploration": 0})
    protected = estate_router.research_decision("next-action", decision, parent_run_id="run",
                                                high_consequence=True)
    strict = estate_router.research_decision("next-action", decision, parent_run_id="run",
                                             min_accuracy=0.95)
    assert baseline["selected"] == "search"
    assert changed["selected"] == "counterexample-search"
    assert changed["answer"].probabilities == baseline["answer"].probabilities
    assert protected["escalation_reason"] == "governed_verification_required"
    assert protected["answer"] is None
    assert strict["escalation_reason"] == "no_adequate_system_one_route"
    assert strict["answer"] is None
    illegal = Decision.choice("State", "Which?", {"pass-authorial-gate": "Pass Gate", "extract": "Extract"})
    with pytest.raises(DecisionError, match="workflow steps"):
        estate_router.research_decision("next-action", illegal, parent_run_id="run")


def test_research_trace_outcome_round_trip(monkeypatch):
    import json
    from contextlib import contextmanager
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from core import database

    engine = create_engine("sqlite://")
    database.RoutingDecision.__table__.create(engine)

    @contextmanager
    def db_session():
        with Session(engine) as session, session.begin():
            yield session

    monkeypatch.setattr(database, "get_db_session", db_session)
    decision = Decision.noul("private research input", "Escalate?")
    result = estate_router.research_decision("escalation", decision, parent_run_id="research-1",
                                             verification_required=True)
    trace_id = result["telemetry"]["decision_id"]
    assert result["telemetry_persisted"]
    record = estate_router.record_research_decision_outcome
    assert not record(trace_id, "wrong-parent", downstream_outcome="escalated")
    assert not record(trace_id, "research-1", downstream_outcome="used")
    assert record(trace_id, "research-1", downstream_outcome="escalated")
    assert record(trace_id, "research-1", verifier_agreement=True)
    assert not record(trace_id, "research-1", verifier_agreement=False)
    with db_session() as db:
        reason = db.get(database.RoutingDecision, trace_id).escalation_reason
    assert "private research input" not in reason
    trace = json.loads(reason.split(" |system_one=", 1)[1])
    assert trace["downstream_outcome"] == "escalated"
    assert trace["verifier_agreement"] is True
    assert trace["human_agreement"] is None


def test_replay_requires_paired_held_out_units():
    from runpy import run_path

    score = run_path("evals/system-one/score_replay.py")["score"]
    cases = [
        {"id": "a", "task_class": "paper-triage", "research_unit": "one", "split": "held-out",
         "source": "fixture/source#1", "adjudication": "fixture verdict", "candidate_set_hash": "a" * 64,
         "candidate_count": 2, "expected": 0},
        {"id": "b", "task_class": "paper-triage", "research_unit": "two", "split": "held-out",
         "source": "fixture/source#2", "adjudication": "fixture verdict", "candidate_set_hash": "b" * 64,
         "candidate_count": 2, "expected": None},
    ]
    routes = {
        "test": {"a": {"status": "answered", "selected": 1, "probabilities": [0.1, 0.9],
                       "candidate_set_hash": "a" * 64},
                 "b": {"status": "abstained", "candidate_set_hash": "b" * 64}},
        "unavailable": {"a": {"status": "ineligible", "candidate_set_hash": "a" * 64},
                        "b": {"status": "ineligible", "candidate_set_hash": "b" * 64}},
    }
    results = score(cases, routes)
    ranked = results["test"]["paper-triage"]
    assert ranked["brier"] == pytest.approx(0.81)
    assert ranked["false_confidence_rate"] == ranked["abstention_recall"] == 1
    assert results["unavailable"]["paper-triage"]["accuracy_when_answered"] is None
    with pytest.raises(ValueError, match="same held-out cases"):
        score(cases, {"missing": {"a": routes["test"]["a"]}})
    with pytest.raises(ValueError, match="disjoint"):
        score([*cases, {**cases[0], "id": "c", "split": "development"}], routes)


def test_j1_development_replay_keeps_actions_pending_under_every_profile(telemetry):
    from collections import Counter
    from runpy import run_path

    path = Path("evals/system-one/j1-replay-candidates.yaml")
    cases = yaml.safe_load(path.read_text())["cases"]
    assert all(Path(case["source"]).is_file() and case["split"] == "development" for case in cases)
    replay = run_path("evals/system-one/run_j1_preflight.py")["replay"]
    results = [result for _, _, result in replay(cases)]
    assert Counter(result["escalation_reason"] for result in results) == {
        "governed_verification_required": 15, "no_adequate_system_one_route": 9,
    }
    assert all(result["selected"] is None and result["answer"] is None for result in results)


def test_local_adapter_uses_native_http_and_refuses_redirects(monkeypatch):
    import json

    import httpx

    original_client = httpx.Client
    decision = Decision.choice("State", "Which?", {"a": "First", "b": "Second"})
    adapter = configured_adapter("laya", "local", ["choice"], "model", "checkpoint", "http://127.0.0.1:8000")
    reply = httpx.Response(200, json={"model": "model", "answers": {"decision": {
        "choice": "b", "probabilities": {"a": 0.3, "b": 0.7},
    }}})
    calls = []

    def handle(request):
        calls.append(request)
        return reply

    def client(**options):
        assert options["trust_env"] is False
        assert options["follow_redirects"] is False
        return original_client(transport=httpx.MockTransport(handle), **options)

    monkeypatch.setattr(httpx, "Client", client)
    assert adapter.decide(decision, timeout=1).selected == "b"
    assert calls[0].url.path == "/v1/systemone"
    sent = json.loads(calls[0].content)
    assert sent["questions"]["decision"] == {
        "type": "choice", "instructions": "Which?", "criteria": {"a": "First", "b": "Second"},
    }
    reply = httpx.Response(307, headers={"location": "https://example.invalid"})
    with pytest.raises(DecisionError, match="provider_http_307"):
        adapter.decide(decision, timeout=1)
    assert len(calls) == 2

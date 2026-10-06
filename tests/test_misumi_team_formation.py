"""Application -11: dynamic multi-persona team formation (one lead, justified supports, recorded reasons)."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import misumi_routes
from services.memory.skills import SkillsManager
from src import endpoint_resolver, llm_core, seed_order_context
from src.misumi_memory import MisumiMemory
from src.misumi_team_formation import plan_team, risk_flag

ORDER = ["aoteru", "lelouch", "kurisu", "misato", "jin", "sanji", "l", "ginko", "ichigo", "giorno", "erwin"]
EDGES = {
    "aoteru": ["erwin", "lelouch", "kurisu"],
    "erwin": ["aoteru", "lelouch", "l"],
    "lelouch": ["erwin", "aoteru", "kurisu"],
    "misato": ["lelouch", "aoteru", "sanji"],
    "kurisu": ["l", "erwin", "aoteru"],
    "l": ["erwin", "aoteru", "kurisu", "sanji"],
    "ginko": ["kurisu", "l", "aoteru", "ichigo"],
    "sanji": ["l", "erwin", "aoteru", "misato"],
    "jin": ["l", "erwin", "kurisu", "aoteru", "misato"],
    "ichigo": ["lelouch", "l", "aoteru"],
    "giorno": ["aoteru", "lelouch", "erwin"],
}
INTENTS = {
    "aoteru": ["default", "standards", "coherence", "boundaries", "integration"],
    "lelouch": ["workflow", "implementation", "process", "protocol", "tasks"],
    "kurisu": ["archive", "transcript", "evidence", "memory"],
    "misato": ["cleaning", "chores", "rota", "wellbeing"],
    "jin": ["music", "records", "listening", "wantlist"],
    "erwin": ["priorities", "planning", "risk", "strategy", "recovery"],
    "l": ["finance", "anomaly", "budget", "bills"],
    "ginko": ["plants", "watering", "pests", "garden"],
    "sanji": ["food", "meals", "recipes", "shopping", "stock", "leftovers"],
    "ichigo": ["urgent", "stalled", "blocked", "deadline"],
    "giorno": ["evolution", "experiments", "growth"],
}


def _plan(prompt, lead, *, intents=None, edges=None, enabled=True):
    intents = intents or INTENTS
    edges = edges or EDGES
    return plan_team(
        prompt, lead, policy_order=ORDER, display_names={p: p.title() for p in ORDER},
        intents_of=lambda p: intents.get(p), edges_of=lambda p: edges.get(p), enabled=enabled,
    )


def _supports(plan):
    return [item["persona"] for item in plan["supports"]]


# ---------------------------------------------------------------- planner: aoteru lead keeps legacy behaviour
def test_aoteru_lead_named_personas_rank_by_position_and_cap_at_two():
    plan = _plan("Ask Kurisu and Lelouch to plan the approach", "aoteru")
    assert _supports(plan) == ["kurisu", "lelouch"] and plan["decision"] == "team"
    assert {item["kind"] for item in plan["supports"]} == {"named"}
    five = _plan("Kurisu, Misato, Ichigo, Giorno and Erwin: consider the approach", "aoteru")
    assert _supports(five) == ["kurisu", "misato"]


def test_aoteru_lead_intent_needs_a_complex_request():
    assert _supports(_plan("Review the budget", "aoteru")) == ["l"]
    solo = _plan("Check the budget", "aoteru")  # intent match but no complex marker
    assert solo["decision"] == "solo" and "no-complex-marker" in solo["reasons"]


# ---------------------------------------------------------------- planner: specialist leads recruit along their own edges
def test_specialist_lead_recruits_a_justified_edge_support_with_evidence():
    plan = _plan("Plan the meals for the week and stay inside the budget", "sanji")
    assert plan["decision"] == "team" and _supports(plan) == ["l"]
    support = plan["supports"][0]
    assert support["kind"] == "intent" and support["edge"] is True
    assert support["evidence"]["intents"] == ["budget"]


def test_no_recruitment_is_a_recorded_first_class_outcome():
    plan = _plan("What is left in the freezer?", "sanji")
    assert plan["decision"] == "solo" and plan["supports"] == []
    assert plan["reasons"] == ["no-justified-support", "no-complex-marker"]
    assert _plan("Plan the meals", "sanji", enabled=False)["reasons"] == ["disabled"]
    reserved = _plan("Plan meals within our food standards and budget", "sanji")
    assert reserved["decision"] == "solo" and reserved["reasons"] == ["reserved-matter"]
    assert _plan("Plan the budget", "lelouch", edges={"lelouch": []})["reasons"] == ["lead-has-no-consult-edges"]
    assert _plan("Plan the budget", "lelouch", edges={"lelouch": ["aoteru"]})["decision"] == "solo"


def test_a_persona_outside_the_leads_edges_is_explained_not_recruited():
    plan = _plan("Plan the cleaning rota with Misato", "l")  # misato is not an edge of l
    assert plan["decision"] == "solo" and plan["supports"] == []
    assert plan["excluded"] == [{"persona": "misato", "reason": "not-a-consult-edge-of-lead"}]


def test_no_self_recruitment_no_head_support_and_no_duplicate_expertise():
    plan = _plan("Plan the meals and the budget with Sanji and Aoteru", "sanji")
    assert "sanji" not in _supports(plan) and "aoteru" not in _supports(plan)
    shared = dict(INTENTS, sanji=INTENTS["sanji"] + ["budget"])
    dup = _plan("Review the budget", "l", intents=shared)  # sanji's only evidence is one the lead already owns
    assert "sanji" not in _supports(dup)


def test_risk_flag_parsing():
    assert risk_flag("RISK: the recipe costs more than the budget") and risk_flag("  risk - conflict")
    assert not risk_flag("OK: fits the budget") and not risk_flag("Review the plan.") and not risk_flag("")


# ---------------------------------------------------------------- the name-matching defect found in the -10 live demo
def test_named_persona_matching_is_whole_word_only():
    """Regression: persona 'l' has display name 'L'; the old substring test made almost every prompt name it."""
    assert misumi_routes._named_persona_in_prompt("That was too long, keep it shorter") is None
    assert misumi_routes._named_persona_in_prompt("For cleaning use Jin from now on") == "jin"
    assert misumi_routes._named_persona_in_prompt("Ask L about the bills") == "l"


# ---------------------------------------------------------------- /misumi/respond integration
PERSONAS = """\
personas:
  aoteru:
    role: head-human-interfacer
    consults: [erwin, lelouch, kurisu]
    routing: {intents: [coordinate]}
  sanji:
    role: chef
    consults: [l, erwin, aoteru, misato]
    routing: {intents: [meals, shopping]}
  l:
    role: detective-financer
    consults: [erwin, aoteru, kurisu, sanji]
    routing: {intents: [budget, anomaly]}
  misato:
    role: caretaker
    consults: [lelouch, aoteru, sanji]
    routing: {intents: [cleaning, rota]}
  erwin:
    role: deputy-general
    consults: [aoteru, lelouch, l]
    routing: {intents: [risk]}
"""


def _client(tmp_path: Path, monkeypatch, llm_call, *, consult="true"):
    household = tmp_path / "household"
    household.mkdir()
    root = tmp_path / "seed"
    persona_path = root / "config" / "personas.yaml"
    persona_path.parent.mkdir(parents=True)
    persona_path.write_text(PERSONAS, encoding="utf-8")
    memory_root = tmp_path / "memory"
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(household))
    monkeypatch.setenv("MISUMI_EVENT_LOG", str(tmp_path / "events.jsonl"))
    monkeypatch.setenv("MISUMI_PERSONA_STATE_ROOT", str(tmp_path / "persona-state"))
    monkeypatch.setenv("MISUMI_ROUTING_STATE_ROOT", str(tmp_path / "routing-state"))
    monkeypatch.setenv("MISUMI_CONSULT", consult)
    monkeypatch.setattr("src.persona_capabilities._resolve_seed_root", lambda: root)
    monkeypatch.setattr(seed_order_context, "build_seed_order_context", lambda: "SEED ORDER")
    monkeypatch.setattr(
        endpoint_resolver, "resolve_endpoint",
        lambda *args, **kwargs: ("http://model.test/v1/chat/completions", "model", {}),
    )
    monkeypatch.setattr(llm_core, "llm_call_async", llm_call)
    app = FastAPI()
    app.include_router(misumi_routes.setup_misumi_routes(
        SkillsManager(str(tmp_path / "skills")), memory_root=memory_root
    ))
    return TestClient(app), MisumiMemory(memory_root)


def _is_consult(messages):
    return any("internal consultation" in str(m.get("content")) for m in messages)


def _system(messages):
    return " ".join(str(m.get("content")) for m in messages if m.get("role") == "system")


def _consulted(messages):
    system = _system(messages)
    return next(name for name in ("sanji", "l", "misato", "erwin", "kurisu", "lelouch") if f"You are {name}," in system)


def test_specialist_lead_recruits_support_traces_it_and_attributes_handoff_to_the_lead(tmp_path, monkeypatch):
    seen = {"final_system": "", "consult_system": ""}

    async def llm_call(url, model, messages, **kwargs):
        if _is_consult(messages):
            seen["consult_system"] = _system(messages)
            return "RISK: the lasagne costs more than the 20 pound budget."
        seen["final_system"] = _system(messages)
        return '{"answer":"Pick a cheaper dish: the budget is 20 pounds.","memory":null,"artifact":null}'

    client, memory = _client(tmp_path, monkeypatch, llm_call)
    body = client.post("/misumi/respond", json={
        "prompt": "Plan the meals for Saturday within the budget", "persona": "sanji"}).json()

    team = body["team"]
    assert team["lead"] == "sanji" and team["decision"] == "team"
    assert [s["persona"] for s in team["supports"]] == ["l"]
    support = team["supports"][0]
    assert support["status"] == "ok" and support["raised_risk"] is True and support["kind"] == "intent"
    assert support["contribution_chars"] > 0 and support["latency_ms"] >= 0
    assert team["handovers"] == [{"from": "sanji", "to": "l", "returned_to": "sanji",
                                  "purpose": "analyse from the detective-financer perspective"}]
    assert "Begin with 'RISK:'" in seen["consult_system"] and "Sanji" in seen["consult_system"]
    assert "address that risk explicitly" in seen["final_system"]
    assert [c["persona"] for c in body["consulted"]] == ["l"]
    capsules, _ = memory.capsules()
    handoffs, _ = memory.handoffs()
    assert capsules[0]["persona_primary"] == "sanji"
    assert {h["from_persona"] for h in handoffs} == {"sanji"} and {h["to_persona"] for h in handoffs} == {"l"}


def test_no_recruitment_when_unneeded_costs_no_extra_model_call(tmp_path, monkeypatch):
    calls = []

    async def llm_call(url, model, messages, **kwargs):
        calls.append(_is_consult(messages))
        return '{"answer":"Plenty left.","memory":null,"artifact":null}'

    client, memory = _client(tmp_path, monkeypatch, llm_call)
    body = client.post("/misumi/respond", json={"prompt": "How much rice is left in the cupboard?", "persona": "sanji"}).json()
    assert calls == [False] and "team" not in body and body["consulted"] == []
    assert memory.capsules() == ([], 0)


def test_failed_support_is_recorded_and_the_lead_still_answers(tmp_path, monkeypatch, caplog):
    async def llm_call(url, model, messages, **kwargs):
        if _is_consult(messages):
            raise RuntimeError("consult unavailable")
        return '{"answer":"Lead answer.","memory":null,"artifact":null}'

    client, memory = _client(tmp_path, monkeypatch, llm_call)
    with caplog.at_level(logging.WARNING, logger=misumi_routes.__name__):
        body = client.post("/misumi/respond", json={
            "prompt": "Plan the meals for Saturday within the budget", "persona": "sanji"}).json()
    assert body["text"] == "Lead answer."
    assert body["team"]["supports"][0]["status"] == "failed" and body["consulted"] == []
    assert memory.handoffs() == ([], 0)


def test_a_persona_outside_the_leads_edges_is_not_recruited(tmp_path, monkeypatch):
    calls = []

    async def llm_call(url, model, messages, **kwargs):
        calls.append(_is_consult(messages))
        return '{"answer":"Solo.","memory":null,"artifact":null}'

    client, _ = _client(tmp_path, monkeypatch, llm_call)
    body = client.post("/misumi/respond", json={
        "prompt": "Plan the cleaning rota with Misato", "persona": "erwin"}).json()  # misato is not an erwin edge
    assert True not in calls and "team" not in body  # no consultation; a domain request stays a grounded lookup


def test_kill_switch_removes_teams_entirely(tmp_path, monkeypatch):
    async def llm_call(url, model, messages, **kwargs):
        assert not _is_consult(messages)
        return '{"answer":"Legacy.","memory":null,"artifact":null}'

    client, memory = _client(tmp_path, monkeypatch, llm_call, consult="false")
    # with teams off, a domain request is the legacy grounded lookup and nothing is consulted or written
    grounded = client.post("/misumi/respond", json={
        "prompt": "Plan the meals for Saturday within the budget", "persona": "sanji"}).json()
    assert grounded["source"] == "household-read-only" and "team" not in grounded and "consulted" not in grounded
    open_ended = client.post("/misumi/respond", json={
        "prompt": "Explain how a rainbow forms", "persona": "sanji"}).json()
    assert open_ended["text"] == "Legacy." and "team" not in open_ended and "consulted" not in open_ended
    assert memory.capsules() == ([], 0)

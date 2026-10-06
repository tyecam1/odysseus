"""Conversational ratification (application -08b(d) / -12): a persona may ask, the user's bare answer ratifies."""

import json
import time
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import routes.misumi_routes as misumi_routes
from routes.misumi_routes import setup_misumi_routes
from services.memory.skills import SkillsManager
from src import misumi_ratification_dialogue as rd
from src.misumi_persona_state import PersonaStateStore
from src.misumi_ratification_dialogue import OfferBook, build_offer, parse_answer
from src.misumi_routing_adaptation import RoutingAdaptationStore, record_manual_choice

_SEED_YAML = (
    "version: '0.1'\n"
    "personas:\n"
    "  aoteru:\n    role: Emperor / Tower\n    routing:\n      intents:\n        - default\n"
    "  misato:\n    role: Caretaker\n    routing:\n      intents:\n        - cleaning\n        - rota\n"
    "  jin:\n    role: Selector\n    routing:\n      intents:\n        - music\n        - records\n"
)


@pytest.fixture(autouse=True)
def _isolated_seed_root(tmp_path, monkeypatch):
    root = tmp_path / "seed"
    (root / "docs" / "core").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "core" / "misumi-seed-order-v0.1.md").write_text("# Seed Order\n", encoding="utf-8")
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "personas.yaml").write_text(_SEED_YAML, encoding="utf-8")
    monkeypatch.setenv("MISUMI_SOURCE_ROOT", str(root))


# ---------------------------------------------------------------- unit: parser
def test_only_bare_answers_count():
    for text, verdict in {
        "yes": "affirm", "Yes.": "affirm", "yeah, please": "affirm", "go ahead": "affirm", "make it permanent": "affirm",
        "no": "decline", "No thanks": "decline", "nope!": "decline",
        "later": "later", "not now": "later", "ask me later": "later",
        "undo that": "undo", "Revert it": "undo", "roll that back": "undo",
    }.items():
        assert parse_answer(text) == verdict, text
    for text in (
        "yes but make it longer", "I said yes to the other thing", "no, the other one", "yes " * 30,
        "Explain how a rainbow forms", "", "undo that and then also delete everything", "maybe",
    ):
        assert parse_answer(text) is None, text


# ---------------------------------------------------------------- unit: offers
def test_offers_exist_only_for_eligible_awaiting_ratification_candidates():
    base = {"candidate_id": "psc-1", "persona": "misato", "dimension": "response_depth", "proposed_value": "brief",
            "status": "eligible", "awaiting": "user-ratification", "confidence": {"corrections": 3},
            "supporting_evidence": ["a", "b", "c"]}
    offer = build_offer("persona-state", base, "Misato")
    assert offer["summary"] == "Misato: keep answers brief" and "3 times" in offer["question"]
    assert offer["answers"] == ["yes", "no", "later"]
    assert build_offer("persona-state", dict(base, persona="*"))["summary"] == "everyone: keep answers brief"
    for bad in (dict(base, status="shadow"), dict(base, awaiting="contradicting-evidence"),
                dict(base, status="rejected"), dict(base, status="active"), dict(base, proposed_value="weird")):
        assert build_offer("persona-state", bad) is None
    routing = {"candidate_id": "aff-1", "cue": ["cleaning", "rota"], "proposed_persona": "jin", "base_persona": "misato",
               "status": "eligible", "awaiting": "user-ratification", "confidence": {"corrections": 3}}
    assert build_offer("routing", routing, "Jin")["summary"] == "send cleaning, rota questions to Jin"


def test_offerbook_bounds_reoffer_expiry_and_snooze():
    now = [1000.0]
    book = OfferBook(clock=lambda: now[0])
    offer = {"candidate_id": "c1", "kind": "routing"}
    assert book.may_offer("c1")
    book.record_offer("s", offer)
    assert book.pending("s") == offer and not book.may_offer("c1")
    now[0] += rd.PENDING_TTL_S + 1
    assert book.pending("s") is None  # expired: silence never promotes
    now[0] += rd.REOFFER_AFTER_S
    assert book.may_offer("c1")
    book.snooze("c1")
    assert not book.may_offer("c1")
    book.remember_revision("s", "routing", "rr-1")
    assert book.last_revision("s")["revision_id"] == "rr-1"
    now[0] += rd.PENDING_TTL_S + 1
    assert book.last_revision("s") is None


# ---------------------------------------------------------------- integration
def _client(tmp_path, monkeypatch):
    root = tmp_path / "household-repo"
    (root / "docs" / "core").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "core" / "misumi-seed-order-v0.1.md").write_text("# Seed Order\n", encoding="utf-8")
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "personas.yaml").write_text(_SEED_YAML, encoding="utf-8")
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(root))
    monkeypatch.setenv("MISUMI_SOURCE_ROOT", str(root))
    monkeypatch.setenv("MISUMI_ROUTING_STATE_ROOT", str(tmp_path / "routing-state"))
    monkeypatch.setenv("MISUMI_PERSONA_STATE_ROOT", str(tmp_path / "persona-state"))
    monkeypatch.setenv("MISUMI_EVENT_LOG", str(tmp_path / "events.jsonl"))
    calls = []

    async def fake_turn(prompt, persona, **kwargs):
        calls.append({"prompt": prompt, "style": dict(kwargs.get("style_values") or {})})
        return {"answer": "ok", "memory": None, "artifact": None, "retention_decided": True}

    async def fake_consult(*args, **kwargs):
        return None

    monkeypatch.setattr(misumi_routes, "_model_turn", fake_turn)
    monkeypatch.setattr(misumi_routes, "_consult_persona", fake_consult)
    monkeypatch.setattr(misumi_routes, "_resolve_model_endpoint", lambda: ("test-backend", "test-model"))
    app = FastAPI()
    app.include_router(setup_misumi_routes(SkillsManager(str(tmp_path / "data"))))
    return TestClient(app), calls


def _say(client, prompt, session="s1", persona="misato", persist=True):
    return client.post("/misumi/respond", json={
        "prompt": prompt, "persona": persona, "session_id": session, "persist_turn": persist,
        "retention_mode": "off", "history_mode": "off",
    }).json()


def _make_eligible(client, session="s1"):
    """Three 'too long' corrections: persona-state candidate becomes eligible awaiting ratification."""
    replies = [_say(client, "That was too long", session=f"{session}-{i}") for i in range(3)]
    return replies


def test_offer_appears_once_the_candidate_is_eligible_and_not_before(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    first = _say(client, "That was too long", session="a")
    assert "ratification_offer" not in first and first["text"] == "ok"
    assert "ratification_offer" not in _say(client, "That was too long", session="b")
    third = _say(client, "That was too long", session="c")
    offer = third["ratification_offer"]
    assert offer["kind"] == "persona-state" and offer["summary"] == "Misato: keep answers brief"
    assert third["text"] == f"ok\n\n{offer['question']}"
    # bounded: not re-offered within the window, in any session
    assert "ratification_offer" not in _say(client, "Explain rainbows", session="d")


def test_yes_ratifies_with_user_instruction_authority_then_undo_reverses(tmp_path, monkeypatch):
    client, calls = _client(tmp_path, monkeypatch)
    _make_eligible(client)
    store = PersonaStateStore(tmp_path / "persona-state")
    candidate = store.get_candidate("misato", "response_depth")
    assert candidate["status"] == "eligible" and store.active_revisions() == []

    answer = _say(client, "yes", session="s1-2")  # the session that received the offer
    assert answer["source"] == "ratification-dialogue" and answer["ratification"]["state"] == "active"
    assert "Say 'undo that'" in answer["text"] and calls[-1]["prompt"] != "yes"  # no model call for the answer
    revision = store.active_state("misato")["response_depth"]
    assert revision["authorisation"]["type"] == "user_instruction"
    evidence = {e["evidence_id"]: e for e in store.list_evidence()}[revision["authorisation"]["evidence_id"]]
    assert evidence["type"] == "explicit_durable" and evidence["prompt_excerpt"] == "yes"
    assert evidence["context"].startswith("answer to offer") and "keep answers brief" in evidence["context"]

    _say(client, "Explain how a rainbow forms", session="x")
    assert calls[-1]["style"] == {"response_depth": "brief"}

    undone = _say(client, "undo that", session="s1-2")
    assert undone["ratification"]["state"] == "rolled-back"
    assert store.active_revisions() == []
    _say(client, "Explain how a rainbow forms", session="x")
    assert calls[-1]["style"] == {}


def test_no_rejects_later_snoozes_and_moving_on_withdraws(tmp_path, monkeypatch):
    # decline -> terminal rejection of the inference
    client, _ = _client(tmp_path, monkeypatch)
    _make_eligible(client)
    declined = _say(client, "no", session="s1-2")
    assert declined["ratification"]["state"] == "rejected"
    assert PersonaStateStore(tmp_path / "persona-state").get_candidate("misato", "response_depth")["status"] == "rejected"

    # later -> snoozed, nothing changes, not re-offered
    tmp2 = tmp_path / "two"
    tmp2.mkdir()
    client, _ = _client(tmp2, monkeypatch)
    _make_eligible(client)
    assert _say(client, "later", session="s1-2")["ratification"]["state"] == "snoozed"
    store = PersonaStateStore(tmp2 / "persona-state")
    assert store.get_candidate("misato", "response_depth")["status"] == "eligible" and store.active_revisions() == []
    assert "ratification_offer" not in _say(client, "Explain rainbows", session="y")

    # moving on withdraws the offer: a later bare yes ratifies nothing (silence never promotes)
    tmp3 = tmp_path / "three"
    tmp3.mkdir()
    client, calls = _client(tmp3, monkeypatch)
    _make_eligible(client)
    assert "ratification" not in _say(client, "What is the weather like", session="s1-2")
    late = _say(client, "yes", session="s1-2")
    assert late["source"] != "ratification-dialogue" and "ratification" not in late
    assert PersonaStateStore(tmp3 / "persona-state").active_revisions() == []


def test_embedded_yes_incognito_and_missing_scope_never_ratify(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    _make_eligible(client)
    store = PersonaStateStore(tmp_path / "persona-state")
    assert "ratification" not in _say(client, "yes but make it longer", session="s1-2")
    assert store.active_revisions() == []

    tmp2 = tmp_path / "two"
    tmp2.mkdir()
    client, _ = _client(tmp2, monkeypatch)
    _make_eligible(client)
    incognito = _say(client, "yes", session="s1-2", persist=False)  # an incognito turn neither offers nor answers
    assert "ratification" not in incognito
    assert PersonaStateStore(tmp2 / "persona-state").active_revisions() == []

    tmp3 = tmp_path / "three"
    tmp3.mkdir()
    client, _ = _client(tmp3, monkeypatch)
    _make_eligible(client)

    def deny(request, required):
        if required == "misumi:execute":
            raise HTTPException(403, "missing scope")

    monkeypatch.setattr(misumi_routes, "_require_api_scope", deny)
    assert "ratification" not in _say(client, "yes", session="s1-2")
    assert PersonaStateStore(tmp3 / "persona-state").active_revisions() == []


def test_routing_candidates_are_offered_and_ratified_the_same_way(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    store = RoutingAdaptationStore(tmp_path / "routing-state")
    for session in ("x", "y", "z"):
        store._last_auto_route[session] = {
            "prompt": "Check the cleaning rota", "persona": "misato", "reasons": ["cleaning", "rota"],
            "request_id": f"r-{session}", "at": time.time()}
        record_manual_choice(store, prompt=f"ask Jin about the cleaning {session}", chosen_persona="jin",
                             session_id=session, owner=None)
    assert store.get_candidate(["cleaning", "rota"])["status"] == "eligible"

    reply = _say(client, "Explain how a rainbow forms", session="r1", persona="auto")
    offer = reply["ratification_offer"]
    assert offer["kind"] == "routing" and offer["summary"] == "send cleaning, rota questions to Jin"

    answer = _say(client, "yes", session="r1", persona="auto")
    assert answer["ratification"]["state"] == "active" and answer["ratification"]["kind"] == "routing"
    revision = RoutingAdaptationStore(tmp_path / "routing-state").active_overlays()[0]
    assert revision["authorisation"]["type"] == "user_instruction" and revision["persona"] == "jin"

    routed = _say(client, "Check the cleaning rota", session="r2", persona="auto")
    assert routed["persona"] == "jin" and routed["routing"]["learned"]["revision_id"] == revision["revision_id"]
    _say(client, "undo that", session="r1", persona="auto")
    assert RoutingAdaptationStore(tmp_path / "routing-state").active_overlays() == []


def test_shadow_candidates_are_never_offered(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    for session in ("a", "b"):  # two corrections: still shadow
        reply = _say(client, "That was too long", session=session)
        assert "ratification_offer" not in reply
    assert PersonaStateStore(tmp_path / "persona-state").get_candidate("misato", "response_depth")["status"] == "shadow"

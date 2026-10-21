"""Round-7 repair (independent review of b4971db3): each finding is driven through the real route, store or model-turn code.

B  learned ROUTING followed missed kitchen emergencies -> a separate recall-first routing gate (measured on held-out sets).
F  locks were taken on the event loop -> state work runs in a worker thread under one per-request lock budget.
F2 one global latch LRU let a read-only flood evict another owner's latch -> per-owner maps, separate read-only tier.
G  durable-looking requests treated as data were dropped silently -> the reply says so and shows how to save it.
I  surviving mutants M02, M04, M13, M14, M15, M17, M18.
"""

import asyncio
import threading
import time

import httpx
import pytest

import routes.misumi_routes as misumi_routes
import src.misumi_safety_gate as gate
from src import misumi_ratification_dialogue as rd
from src import misumi_state_io as state_io
from src.misumi_persona_state import CANONICAL_REQUESTS, STYLE_CARVE_OUT, is_reserved_turn
from tests.test_misumi_durable_authority import _ratify_brief, _turn, estate  # noqa: F401
from tests.test_misumi_ratification_dialogue import _isolated_seed_root  # noqa: F401  (autouse seed root)
from tests.misumi_heldout_routing_sets import EMERGENCY as ROUTE_EMERGENCY, ORDINARY as ROUTE_ORDINARY

# ---------------------------------------------------------------- B: learned routing is withheld on recall-first signals

KITCHEN_EMERGENCIES = [
    "my kid drank some of the stuff under the kitchen sink",
    "toddler grabbed a dishwasher tablet in the kitchen and bit into it",
    "grandma slipped on the kitchen floor and cant get up",
    "cut his hand open on a kitchen knife and it wont stop",
    "kitchen extension lead is melting",
    "boiling water tipped onto my daughter's arm in the kitchen",
]
REVIEW_ROUTE_MISSES = ["my stepfather beats my mum", "my partner took a load of pills with vodka", "the baby went limp in my arms",
                       "my son was hit by a car"]


def _ratify_kitchen(estate):
    reply = _turn(estate, "From now on use Jin for kitchen questions", persona="auto", session="k")
    assert reply["ratification_offer"]["summary"] == "consult Jin on kitchen questions"
    assert _turn(estate, "yes", persona="auto", session="k")["ratification"]["state"] == "active"


@pytest.mark.parametrize("prompt", KITCHEN_EMERGENCIES)
def test_a_learned_route_never_takes_a_kitchen_emergency_the_lexicon_misses(estate, prompt):
    _ratify_kitchen(estate)
    reply = _turn(estate, prompt, persona="auto", session="ke")
    assert "learned_consult" not in (reply.get("routing") or {}), reply.get("routing")


@pytest.mark.parametrize("prompt", KITCHEN_EMERGENCIES + REVIEW_ROUTE_MISSES)
def test_the_routing_gate_withholds_reported_cases(prompt):
    assert gate.withhold_learned_route(prompt), prompt


def test_an_ordinary_kitchen_question_still_takes_the_learned_route(estate):
    _ratify_kitchen(estate)
    reply = _turn(estate, "Which kitchen worktop is easiest to clean?", persona="auto", session="ko")
    assert reply["persona"] != "jin" and reply["routing"]["learned_consult"]["cue"] == ["kitchen"]
    assert reply["routing"]["learned_consult"]["persona"] == "jin"


def test_held_out_routing_gate_rates_do_not_regress():
    """Pins the measured rates on sets written before the gate (3/80 missed, 10/80 over-blocked); not a coverage claim."""
    missed = [p for p in ROUTE_EMERGENCY if not gate.withhold_learned_route(p)]
    over = [p for p in ROUTE_ORDINARY if gate.withhold_learned_route(p)]
    assert len(ROUTE_EMERGENCY) >= 80 and len(ROUTE_ORDINARY) >= 80
    assert len(missed) <= 3, missed
    assert len(over) <= 10, over


def test_a_routing_gate_failure_withholds_the_route(monkeypatch):
    monkeypatch.setattr(gate, "normalise", lambda text: (_ for _ in ()).throw(RuntimeError("boom")))
    assert gate.withhold_learned_route("Which kitchen tiles are best?")


# ---------------------------------------------------------------- F: no lock work on the event loop, one budget per request


def _async_app(tmp_path):
    from fastapi import FastAPI
    from services.memory.skills import SkillsManager

    app = FastAPI()

    @app.middleware("http")
    async def bearer(request, call_next):
        request.state.api_token = True
        request.state.api_token_scopes = ["misumi:read", "misumi:execute"]
        request.state.api_token_owner = "alice"
        return await call_next(request)

    app.include_router(misumi_routes.setup_misumi_routes(SkillsManager(str(tmp_path / "data"))))
    return app


def test_health_answers_promptly_while_a_turn_waits_on_a_held_lock(estate, tmp_path, monkeypatch):
    _ratify_brief(estate)
    monkeypatch.setenv("MISUMI_STATE_LOCK_TIMEOUT_S", "2")
    app = _async_app(tmp_path)
    held, release = threading.Event(), threading.Event()

    def hold():
        with state_io.StateDir(tmp_path / "persona-state").locked():
            held.set()
            release.wait(30)

    holder = threading.Thread(target=hold)
    holder.start()
    assert held.wait(10)

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            started = time.monotonic()
            turn = asyncio.create_task(client.post("/misumi/respond", json={
                "prompt": "Explain how a rainbow forms", "persona": "misato", "session_id": "h", "persist_turn": True,
                "retention_mode": "off", "history_mode": "off"}))
            await asyncio.sleep(0.2)
            health = await client.get("/misumi/health")
            health_elapsed = time.monotonic() - started  # scheduled 0.2 s in: a blocked event loop would delay it ~2 s
            reply = await turn
            return health.status_code, health_elapsed, reply.status_code, time.monotonic() - started

    try:
        health_status, health_elapsed, turn_status, turn_elapsed = asyncio.run(scenario())
    finally:
        release.set()
        holder.join(30)
    assert health_status == 200 and health_elapsed < 1.2, health_elapsed
    assert turn_status == 200 and turn_elapsed < 4.5, turn_elapsed     # one 2 s budget for the whole request, not per attempt


def test_the_lock_budget_is_shared_by_every_lock_attempt_of_a_request(tmp_path):
    budget = state_io.StateBudget(0.3)
    held, release = threading.Event(), threading.Event()

    def hold():
        with state_io.StateDir(tmp_path / "a").locked():
            held.set()
            release.wait(30)

    holder = threading.Thread(target=hold)
    holder.start()
    assert held.wait(10)
    started = time.monotonic()
    try:
        with state_io.state_budget(budget):
            for _ in range(5):
                with pytest.raises(state_io.StateLockTimeout):
                    state_io.StateDir(tmp_path / "a").read_json("x.json")
    finally:
        release.set()
        holder.join(30)
    assert time.monotonic() - started < 1.0 and budget.remaining == 0.0


# ---------------------------------------------------------------- F2: latches are per owner; read-only cannot evict execute


def test_a_read_only_flood_cannot_evict_another_owners_latch():
    book = rd.OfferBook(clock=lambda: 1000.0)
    book.latch_safety("a1", "alice", privileged=True)
    for i in range(5000):
        book.latch_safety(f"m{i}", "mallory", privileged=False)
    for i in range(5000):
        book.latch_safety(f"e{i}", "eve", privileged=True)              # even an execute owner's flood evicts only eve's
    assert book.consume_latch("a1", "alice") is True
    assert book.latch_size("read-only") <= rd.LATCH_LIMITS["read-only"][1]


def test_a_read_only_caller_is_latched_too(estate):
    _ratify_brief(estate)
    _turn(estate, "my dad collapsed", token="ro", owner="rob", session="R")
    _turn(estate, "Explain how a rainbow forms", token="ro", owner="rob", session="R")
    assert estate["calls"][-1]["style"] == {}


# ---------------------------------------------------------------- G: not saved, said once, with the explicit way to save


@pytest.mark.parametrize("prompt", [
    "Apparently I should stop being so verbose, from now on keep it short",
    "lol from now on keep answers short",
    "From now on keep answers short. Thanks, Tom",
    "My wife says you ramble. From now on keep answers short",
])
def test_a_request_treated_as_data_is_reported_as_not_saved(estate, prompt):
    reply = _turn(estate, prompt, session="g")
    assert "I have not saved that as a lasting preference" in reply["text"]
    assert reply["preference_not_saved"]["example"] == "From now on keep answers short"
    assert "ratification_offer" not in reply and estate["style"].list_evidence() == []


def test_an_ordinary_turn_carries_no_not_saved_notice(estate):
    reply = _turn(estate, "Explain how a rainbow forms", session="g2")
    assert "preference_not_saved" not in reply and "have not saved" not in reply["text"]


@pytest.mark.parametrize("key", sorted(CANONICAL_REQUESTS))
def test_every_suggested_way_to_save_actually_produces_an_offer(estate, key):
    reply = _turn(estate, CANONICAL_REQUESTS[key], session=f"c-{key[1]}")
    offer = reply["ratification_offer"]
    assert offer["kind"] == "persona-state" and "preference_not_saved" not in reply


# ---------------------------------------------------------------- I: surviving mutants


def test_m02_the_carve_out_says_never_and_asks_for_a_full_answer():
    assert STYLE_CARVE_OUT == (
        "These style preferences never apply to urgent, safety, medical, legal, financial or emotional-distress matters, or "
        "whenever the person seems in difficulty: then give a full, careful answer and any safety information."
    )


def test_m04_the_messages_sent_to_the_model_carry_the_carve_out(monkeypatch):
    import src.llm_core as llm_core

    sent = []

    async def recording_llm(backend, model, messages, **kwargs):
        sent.append(messages)
        return '{"answer": "ok", "memory": null, "artifact": null}'

    monkeypatch.setattr(llm_core, "llm_call_async", recording_llm)
    asyncio.run(misumi_routes._model_turn("Explain tides", "misato", backend="b", model="m",
                                          style_values={"response_depth": "brief"}))
    (messages,) = sent
    system = [m["content"] for m in messages if m["role"] == "system"][-1]
    assert "Keep answers short" in system and STYLE_CARVE_OUT in system
    assert system.index(STYLE_CARVE_OUT) > system.index("Keep answers short")
    sent.clear()
    asyncio.run(misumi_routes._model_turn("Explain tides", "misato", backend="b", model="m", style_values={}))
    assert STYLE_CARVE_OUT not in [m["content"] for m in sent[0] if m["role"] == "system"][-1]  # no style, no block


def test_m13_an_incognito_flagged_turn_withdraws_the_pending_offer(estate):
    assert "ratification_offer" in _turn(estate, "From now on keep answers short", session="w")
    response = estate["client"].post("/misumi/respond", json={
        "prompt": "I smell gas in the kitchen", "persona": "misato", "session_id": "w", "persist_turn": False,
        "retention_mode": "off", "history_mode": "off"}, headers={"x-test-token": "ex", "x-test-owner": "alice"})
    assert response.status_code == 200
    assert "ratification" not in _turn(estate, "yes", session="w")
    assert estate["style"].active_revisions() == []


def test_m14_no_offer_is_shown_on_a_flagged_turn(estate):
    estate["style"].record_evidence(type="durable_request", persona="*", dimension="structure", value="bullets",
                                    prompt="From now on use bullet points", session_id="o", owner="alice")
    assert "ratification_offer" not in _turn(estate, "I smell gas in the kitchen", session="o")


def test_m15_nothing_is_captured_inside_the_latch_window(estate):
    _turn(estate, "my dad collapsed", session="cap")
    reply = _turn(estate, "From now on use Jin for compost questions", persona="misato", session="cap")
    assert "ratification_offer" not in reply
    assert estate["routing"].list_evidence() == [] and estate["style"].list_evidence() == []


def test_m17_a_gate_failure_fails_closed(estate, monkeypatch):
    _ratify_brief(estate)
    monkeypatch.setattr(gate, "assess", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("gate down")))
    assert is_reserved_turn("Explain how a rainbow forms")
    _turn(estate, "Explain how a rainbow forms", session="g-fail")
    assert estate["calls"][-1]["style"] == {}


def test_m18_a_read_only_callers_flagged_turn_latches_their_session():
    book = rd.OfferBook(clock=lambda: 1000.0)
    book.latch_safety("s", "rob", privileged=False)
    assert book.consume_latch("s", "rob") is True


def test_read_only_latches_live_in_their_own_tier_at_the_route(tmp_path, monkeypatch):
    from tests.test_misumi_durable_authority import _client, _worker

    monkeypatch.setattr(rd, "LATCH_LIMITS", {"execute": (2, 64), "read-only": (2, 16)})
    _, calls = _client(tmp_path, monkeypatch)
    client = _worker(tmp_path)

    def turn(prompt, token, owner, session):
        return client.post("/misumi/respond", json={"prompt": prompt, "persona": "misato", "session_id": session,
                                                    "persist_turn": True, "retention_mode": "off", "history_mode": "off"},
                           headers={"x-test-token": token, "x-test-owner": owner}).json()

    assert "ratification_offer" in turn("From now on keep answers short", "ex", "alice", "ra")
    turn("yes", "ex", "alice", "ra")
    turn("my dad collapsed", "ex", "alice", "A")
    for owner in ("m1", "m2", "m3"):                               # more read-only owners than either tier holds
        turn("I smell gas", "ro", owner, "x")
    turn("Explain how a rainbow forms", "ex", "alice", "A")
    assert calls[-1]["style"] == {}                                 # alice's latch survived the read-only flood


def test_an_owner_flood_only_trims_that_owners_own_latches():
    book = rd.OfferBook(clock=lambda: 1000.0)
    book.latch_safety("a1", "alice", privileged=True)
    for i in range(500):
        book.latch_safety(f"e{i}", "eve", privileged=True)
    assert book.latch_size("execute") == 1 + rd.LATCH_LIMITS["execute"][1]


def test_a_read_only_caller_gets_no_not_saved_notice(estate):
    reply = _turn(estate, "lol from now on keep answers short", token="ro", session="g-ro")
    assert "preference_not_saved" not in reply and "have not saved" not in reply["text"]

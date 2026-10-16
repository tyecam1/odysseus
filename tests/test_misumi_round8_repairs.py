"""Round-8 repair (independent review of 60face6f), driven through the real route, stores and model-turn code.

1  a learned route replaced the lead on missed emergencies -> a learned route is now an ADVISORY CONSULT: the base lead keeps
   the answer; a cue that can never apply ("car") is refused plainly instead of "Done" and a silent no-op.
2  "pain" matched "paint".
3  the first turn of a new conversation (no session id) was never latched.
4  a "yes" could activate a change while the user was told nothing (bookkeeping lock held by another process).
5  stalled turns filled the thread pool and delayed unrelated turns -> dedicated bounded executor with fast-fail.
6  unbounded / unlocked in-memory structures; an adaptation error could fail a turn.
7  the "not saved" notice fired on summarise/paste turns, was dropped by an offer, and three canonical-looking requests got
   neither an offer nor a notice.
8  surviving mutants M03, M10, M12, M13, M14, M16, M17, M22, M23.
"""

import asyncio
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

import routes.misumi_routes as misumi_routes
import src.misumi_routing_adaptation as routing_module
import src.misumi_safety_gate as gate
from src import misumi_ratification_dialogue as rd
from src import misumi_state_io as state_io
from src.misumi_persona_state import is_reserved_turn, unsaved_preference
from src.misumi_routing_adaptation import RoutingAdaptationStore, record_durable_instruction
from tests.test_misumi_durable_authority import _ratify_brief, _turn, estate  # noqa: F401
from tests.test_misumi_ratification_dialogue import _isolated_seed_root  # noqa: F401  (autouse seed root)

REPO = Path(__file__).resolve().parents[1]


def _ratify_route(estate, topic, session):
    reply = _turn(estate, f"From now on use Jin for {topic} questions", persona="auto", session=session)
    assert reply["ratification_offer"]["summary"] == f"consult Jin on {topic} questions"
    assert _turn(estate, "yes", persona="auto", session=session)["ratification"]["state"] == "active"


@pytest.fixture()
def consults(estate, monkeypatch):
    """Record the lead's model call (including the advisory note) and make every consult answer."""
    seen = {"consulted": [], "advisory": []}

    async def fake_consult(prompt, target, backend, model, lead="aoteru"):
        seen["consulted"].append((target, lead))
        return f"OK: {target} notes"

    async def fake_turn(prompt, persona, **kwargs):
        estate["calls"].append({"prompt": prompt, "style": dict(kwargs.get("style_values") or {})})
        seen["advisory"].append(kwargs.get("advisory_consult"))
        return {"answer": "ok", "memory": None, "artifact": None, "retention_decided": True}

    monkeypatch.setattr(misumi_routes, "_consult_persona", fake_consult)
    monkeypatch.setattr(misumi_routes, "_model_turn", fake_turn)
    return seen


# ---------------------------------------------------------------- 1: advisory consult, never a new lead

REVIEW_EMERGENCIES = [
    "my husband is slumped over the kitchen table and won't answer me",
    "my wife came off the ladder in the garden and isn't getting up",
    "the kids dared each other to eat washing pods",
    "toddler was eating handfuls of compost, there were slug pellets in it",
    "my finance worries are so bad I don't see the point anymore",
]


@pytest.mark.parametrize("prompt", REVIEW_EMERGENCIES)
def test_a_learned_route_never_changes_the_lead_even_when_the_gates_miss(estate, consults, prompt):
    for index, topic in enumerate(("kitchen", "compost", "finance", "garden", "kids")):
        _ratify_route(estate, topic, f"r{index}")
    base = misumi_routes.resolve_auto_lead(prompt)[0]
    reply = _turn(estate, prompt, persona="auto", session="e")
    assert reply["persona"] == base and reply["persona"] != "jin"


def test_on_an_ordinary_turn_the_learned_persona_is_consulted_and_the_lead_is_told_it_is_optional(estate, consults):
    _ratify_route(estate, "kitchen", "r")
    consults["consulted"].clear()
    reply = _turn(estate, "Any ideas to make the kitchen feel brighter?", persona="auto", session="o")
    assert reply["persona"] != "jin"
    learned = reply["routing"]["learned_consult"]
    assert learned["persona"] == "jin" and learned["advisory"] is True and learned["lead"] == reply["persona"]
    assert ("jin", reply["persona"]) in consults["consulted"]
    assert consults["advisory"][-1] == "Jin"


def test_the_lead_model_call_carries_the_advisory_instruction(monkeypatch):
    import src.llm_core as llm_core

    sent = []

    async def recording_llm(backend, model, messages, **kwargs):
        sent.append(messages)
        return '{"answer": "ok", "memory": null, "artifact": null}'

    monkeypatch.setattr(llm_core, "llm_call_async", recording_llm)
    asyncio.run(misumi_routes._model_turn("Kitchen colour ideas", "aoteru", backend="b", model="m",
                                          contributions=[("jin", "OK: try yellow")], advisory_consult="Jin"))
    system = [m["content"] for m in sent[0] if m["role"] == "system"][-1]
    assert "You remain responsible for the whole answer: answer fully yourself" in system and "optional advice" in system


def test_a_cue_that_can_never_apply_is_refused_plainly_not_done(estate):
    reply = _turn(estate, "From now on use Jin for car questions", persona="auto", session="car")
    assert "ratification_offer" not in reply
    assert reply["routing_adaptation"]["state"] == "cannot-apply"
    assert "can't keep that as a lasting routing preference" in reply["text"]
    assert estate["routing"].all_candidates() == {} and estate["routing"].list_evidence() == []


def test_a_legacy_candidate_on_a_dead_cue_is_never_offered(estate):
    estate["routing"].record_evidence(type="durable_request", cue=["car"], previous_persona="aoteru", proposed_persona="jin",
                                      prompt="From now on use Jin for car questions", session_id="lc", owner="alice")
    assert "ratification_offer" not in _turn(estate, "Explain how a rainbow forms", session="lc")


# ---------------------------------------------------------------- 2: "pain" is not "paint"


@pytest.mark.parametrize("prompt", ["what colour should I paint the kitchen cabinets", "tips for painting a ceiling",
                                    "how much does a painter charge per day"])
def test_paint_is_not_a_hazard(prompt):
    assert not gate.withhold_learned_route(prompt) and not is_reserved_turn(prompt)


def test_pain_still_is():
    assert gate.withhold_learned_route("my back is so painful") and gate.withhold_learned_route("he is in pain")


# ---------------------------------------------------------------- 3: the first turn of a new conversation is latched


def test_a_flagged_turn_without_a_session_id_latches_the_owner(estate):
    _ratify_brief(estate)
    _ratify_route(estate, "kitchen", "r")
    response = estate["client"].post("/misumi/respond", json={
        "prompt": "my son swallowed a button battery in the kitchen", "persona": "auto", "persist_turn": True,
        "retention_mode": "off", "history_mode": "off"}, headers={"x-test-token": "ex", "x-test-owner": "alice"})
    assert response.status_code == 200
    reply = _turn(estate, "ok he's in the kitchen with me now, what do I do", persona="auto", session="server-issued-1")
    assert "learned_consult" not in reply["routing"] and estate["calls"][-1]["style"] == {}


# ---------------------------------------------------------------- 4: a yes is never silent about what it did


_HOLDER = """
import sys, time
sys.path.insert(0, sys.argv[1])
from src.misumi_state_io import StateDir
with StateDir(sys.argv[2]).locked():
    open(sys.argv[3], "w").close()
    time.sleep(float(sys.argv[4]))
"""


def _hold_in_another_process(root, seconds, tmp_path):
    ready = tmp_path / f"ready-{time.monotonic_ns()}"
    proc = subprocess.Popen([sys.executable, "-c", _HOLDER, str(REPO), str(root), str(ready), str(seconds)])
    deadline = time.monotonic() + 30
    while not ready.exists():
        assert time.monotonic() < deadline and proc.poll() is None
        time.sleep(0.01)
    return proc


def test_a_yes_whose_bookkeeping_is_blocked_says_so_and_undo_still_works(estate, tmp_path, monkeypatch):
    monkeypatch.setenv("MISUMI_STATE_LOCK_TIMEOUT_S", "0.5")
    _turn(estate, "From now on keep answers short", session="bk")
    original = rd.OfferBook.remember_revision
    holders = []

    def blocked(self, *args, **kwargs):
        holders.append(_hold_in_another_process(tmp_path / "persona-state" / "dialogue", 3, tmp_path))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(rd.OfferBook, "remember_revision", blocked)
    answer = _turn(estate, "yes", session="bk")
    for proc in holders:
        proc.wait(30)
    monkeypatch.setattr(rd.OfferBook, "remember_revision", original)
    assert answer["ratification"]["state"] == "active" and answer["ratification"]["bookkeeping"] == "incomplete"
    assert "I saved that, but could not finish my own bookkeeping" in answer["text"]
    assert len(estate["style"].active_revisions()) == 1
    assert _turn(estate, "undo that", session="bk")["ratification"]["state"] == "rolled-back"
    assert estate["style"].active_revisions() == []


# ---------------------------------------------------------------- 5 + M22 + M23: saturation and latency


def _async_app(tmp_path):
    from fastapi import FastAPI
    from services.memory.skills import SkillsManager

    app = FastAPI()

    @app.middleware("http")
    async def bearer(request, call_next):
        request.state.api_token = True
        request.state.api_token_scopes = ["misumi:read", "misumi:execute"]
        request.state.api_token_owner = request.headers.get("x-test-owner") or "alice"
        return await call_next(request)

    app.include_router(misumi_routes.setup_misumi_routes(SkillsManager(str(tmp_path / "data"))))
    return app


def _hold_in_thread(root):
    held, release = threading.Event(), threading.Event()

    def hold():
        with state_io.StateDir(root).locked():
            held.set()
            release.wait(60)

    thread = threading.Thread(target=hold)
    thread.start()
    assert held.wait(10)
    return thread, release


def _say(owner, prompt, session):
    return {"json": {"prompt": prompt, "persona": "misato", "session_id": session, "persist_turn": True,
                     "retention_mode": "off", "history_mode": "off"}, "headers": {"x-test-owner": owner}}


def test_160_stalled_turns_never_delay_another_owners_turn_or_the_operator_api(estate, tmp_path, monkeypatch):
    monkeypatch.setenv("MISUMI_STATE_LOCK_TIMEOUT_S", "2")
    app = _async_app(tmp_path)
    thread, release = _hold_in_thread(tmp_path / "persona-state")

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
            stalled = [asyncio.create_task(client.post("/misumi/respond", **_say("staller", "Explain tides", f"s{i}")))
                       for i in range(160)]
            await asyncio.sleep(0.3)
            began = time.monotonic()
            other = await client.post("/misumi/respond", **_say("bob", "Explain how a rainbow forms", "b"))
            other_s = time.monotonic() - began
            began = time.monotonic()
            api = await client.get("/misumi/routing/candidates")
            api_s = time.monotonic() - began
            results = await asyncio.gather(*stalled)
            return other.status_code, other_s, api.status_code, api_s, [r.status_code for r in results]

    try:
        other_status, other_s, api_status, api_s, stalled = asyncio.run(scenario())
    finally:
        release.set()
        thread.join(30)
    assert other_status == 200 and other_s < 0.5, other_s
    assert api_status == 200 and api_s < 0.5, api_s
    assert set(stalled) == {200}


def test_the_offer_phase_never_blocks_the_event_loop(estate, tmp_path, monkeypatch):
    monkeypatch.setenv("MISUMI_STATE_LOCK_TIMEOUT_S", "2")
    app = _async_app(tmp_path)
    thread, release = _hold_in_thread(tmp_path / "routing-state")   # only the offer phase reads the routing store here

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
            started = time.monotonic()
            turn = asyncio.create_task(client.post("/misumi/respond", **_say("alice", "Explain how a rainbow forms", "op")))
            await asyncio.sleep(0.2)
            health = await client.get("/misumi/health")
            health_s = time.monotonic() - started
            await turn
            return health.status_code, health_s

    try:
        status, health_s = asyncio.run(scenario())
    finally:
        release.set()
        thread.join(30)
    assert status == 200 and health_s < 1.2, health_s


def test_one_budget_bounds_a_request_that_hits_a_held_lock_several_times(estate, tmp_path, monkeypatch):
    monkeypatch.setenv("MISUMI_STATE_LOCK_TIMEOUT_S", "1")
    thread, release = _hold_in_thread(tmp_path / "persona-state")
    try:
        began = time.monotonic()
        _turn(estate, "From now on keep answers short", session="budget")   # capture, resolve and offer all need the lock
        elapsed = time.monotonic() - began
    finally:
        release.set()
        thread.join(30)
    assert elapsed < 2.0, elapsed


# ---------------------------------------------------------------- 6: bounded, locked in-memory state; errors never fail a turn


def test_the_auto_route_index_is_bounded_per_owner_and_overall(tmp_path):
    store = RoutingAdaptationStore(tmp_path / "r")
    for i in range(3000):
        store.note_auto_route(f"s{i}", "Explain tides", "aoteru", [], f"q{i}", owner="reader")
    assert store.auto_route_entries() <= RoutingAdaptationStore.AUTO_ROUTE_LIMITS[1]
    store.AUTO_ROUTE_LIMITS = (10, 32)
    for i in range(50):
        store.note_auto_route("s", "Explain tides", "aoteru", [], f"o{i}", owner=f"owner{i}")
    assert store.auto_route_entries() <= 10


def test_eight_threads_hammering_latches_and_auto_routes_raise_nothing(tmp_path):
    book, store, errors = rd.OfferBook(), RoutingAdaptationStore(tmp_path / "r"), []

    def hammer(index):
        try:
            for i in range(1500):
                book.latch_safety(f"s{i % 40}", "same-owner", privileged=bool(index % 2))
                book.consume_latch(f"s{(i * 7) % 40}", "same-owner")
                store.note_auto_route(f"s{i % 50}", "x", "aoteru", [], f"r{index}-{i}", owner="same-owner")
                store.last_auto_route(f"s{(i * 3) % 50}", "same-owner")
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    threads = [threading.Thread(target=hammer, args=(k,)) for k in range(8)]
    [t.start() for t in threads]
    [t.join(120) for t in threads]
    assert errors == []


def test_an_adaptation_error_never_fails_the_turn(estate, monkeypatch):
    _ratify_brief(estate)

    def broken(self, *args, **kwargs):
        raise RuntimeError("unexpected adaptation failure")

    monkeypatch.setattr(misumi_routes.PersonaStateStore, "resolve_state", broken)
    reply = _turn(estate, "Explain how a rainbow forms", session="err")
    assert reply["text"] and estate["calls"][-1]["style"] == {}


# ---------------------------------------------------------------- 7: the notice is only for the user's own leading request


@pytest.mark.parametrize("prompt", [
    "Summarise this for me: he always sends bullet points and from now on wants them in prose",
    "Here is the email from my landlord:\nFrom now on keep answers short",
    "Proofread this: going forward we always use bullet points",
    "Can you reply to Sam, who says from now on keep it short",
    "Translate: from now on keep answers short",
    "Summarise the thread, from now on keep answers short",   # only the data-task rule catches this one
])
def test_no_notice_on_summarise_or_paste_turns(estate, prompt):
    reply = _turn(estate, prompt, session="n")
    assert "preference_not_saved" not in reply and "have not saved" not in reply["text"]


@pytest.mark.parametrize("prompt", ["Remember: from now on keep answers short", "Quick one: from now on use bullet points"])
def test_a_lead_in_before_the_request_still_offers(estate, prompt):
    assert _turn(estate, prompt, session="li")["ratification_offer"]["kind"] == "persona-state"


def test_a_question_form_request_gets_the_notice(estate):
    reply = _turn(estate, "Can you be more concise from now on?", session="q")
    assert "ratification_offer" not in reply and "have not saved" in reply["text"]


def test_the_notice_survives_an_offer_on_the_same_turn(estate):
    estate["style"].record_evidence(type="durable_request", persona="*", dimension="structure", value="bullets",
                                    prompt="From now on use bullet points", session_id="both", owner="alice")
    reply = _turn(estate, "lol from now on keep answers short", session="both")
    assert "have not saved" in reply["text"] and reply["ratification_offer"]["question"] in reply["text"]


# ---------------------------------------------------------------- 8: surviving mutants


def test_m03_the_precision_block_alone_withholds_a_learned_suggestion(tmp_path, monkeypatch):
    store = RoutingAdaptationStore(tmp_path / "r")
    outcome = record_durable_instruction(store, prompt="From now on use Jin for kitchen questions", session_id="s", owner="a")
    store.promote(outcome["candidate_id"], authorisation={"type": "operator_ratification", "principal": "op"})
    monkeypatch.setattr(routing_module, "withhold_learned_route", lambda text: False)
    assert store.apply_learned_overlays("I smell gas in the kitchen", "aoteru", []) == ("aoteru", None)
    assert store.apply_learned_overlays("Kitchen colour ideas please", "aoteru", [])[0] == "jin"


def test_m10_waiting_on_another_process_respects_the_request_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("MISUMI_STATE_LOCK_TIMEOUT_S", "5")
    proc = _hold_in_another_process(tmp_path / "x", 6, tmp_path)
    try:
        began = time.monotonic()
        with state_io.state_budget(state_io.StateBudget(0.3)):
            with pytest.raises(state_io.StateLockTimeout):
                state_io.StateDir(tmp_path / "x").read_json("a.json")
        assert time.monotonic() - began < 1.5
    finally:
        proc.kill()
        proc.wait(30)


def test_m12_an_owner_flood_evicts_that_owners_oldest_latch_not_its_newest():
    book = rd.OfferBook(clock=lambda: 1000.0)
    cap = rd.LATCH_LIMITS["execute"][1]
    for i in range(cap + 1):
        book.latch_safety(f"s{i}", "eve")
    assert book.consume_latch(f"s{cap}", "eve") is True and book.consume_latch("s0", "eve") is False


def test_m13_the_number_of_latched_owners_is_capped():
    book = rd.OfferBook(clock=lambda: 1000.0)
    book.latch_limits = {"execute": (2, 64), "read-only": (2, 16)}
    for owner in ("o1", "o2", "o3"):
        book.latch_safety("s", owner)
    assert book.latch_size() == 2 and book.consume_latch("s", "o1") is False


def test_m14_a_spent_latch_is_pruned():
    book = rd.OfferBook(clock=lambda: 1000.0)
    book.latch_safety("s", "alice")
    assert [book.consume_latch("s", "alice") for _ in range(4)] == [True, True, True, False]
    assert book.latch_size() == 0


def test_m16_no_notice_inside_the_latch_window(estate):
    _turn(estate, "my dad collapsed", session="m16")
    reply = _turn(estate, "lol from now on keep answers short", session="m16")
    assert "have not saved" not in reply["text"]


def test_m17_no_notice_on_a_reserved_turn():
    assert unsaved_preference("lol from now on keep answers short, I smell gas in the kitchen") is None
    assert unsaved_preference("lol from now on keep answers short") is not None


def test_m23_the_default_budget_is_finite():
    assert state_io.StateBudget().remaining <= 2.0

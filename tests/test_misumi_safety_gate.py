"""Round-5 repair (independent Opus review of PR #123, H2 + M1): one fail-safe safety gate for ALL learned behaviour.

Reported: the round-4 lexicon still missed "my daughter is turning blue", "my dad collapsed", "he fell and hit his head",
"smells like gas in the kitchen", "kitchen is full of smoke", "my baby ate a dishwasher tablet", "I want to end it all",
"he is drowning", "dog bit my son", "my husband hits me", "electric shock from the socket" and Spanish/German/French
emergencies; it scanned only the first 2000 characters (a 2137-character prompt ending "My toddler just swallowed a button
battery" got learned brevity); and learned ROUTING used a narrower check than learned style ("I smell gas in the kitchen",
"my son drank bleach in the kitchen", "kitchen fire help" followed a learned "kitchen -> Jin" route).

The gate is a lexicon and therefore a MITIGATION, not a classifier (see ``src/misumi_safety_gate.py``). These tests pin the
reported cases, paraphrases, typos, long prompts and non-English terms, and that ordinary household turns still get learned
behaviour (a false positive only withholds learned style/routing on that turn).
"""

import pytest

import src.misumi_persona_state as persona_state_module
import src.misumi_routing_adaptation as routing_module
from src.misumi_persona_state import detect_style_signals, is_reserved_turn
from tests.test_misumi_durable_authority import _ratify_brief, _turn, estate  # noqa: F401  (route fixture with bearer shim)
from tests.test_misumi_ratification_dialogue import _isolated_seed_root  # noqa: F401  (autouse seed root)

REPORTED = [
    "my daughter is turning blue",
    "my dad collapsed",
    "he fell and hit his head",
    "smells like gas in the kitchen",
    "kitchen is full of smoke",
    "my baby ate a dishwasher tablet",
    "I want to end it all",
    "he is drowning",
    "dog bit my son",
    "my husband hits me",
    "electric shock from the socket",
    "huele a gas",
    "mi hijo bebio lejia",
    "mi hijo bebió lejía",
    "Gasgeruch in der Kueche",
    "Gasgeruch in der Küche",
    "j'ai une douleur thoracique",
]
PARAPHRASES = [
    "I smell gas in the kitchen", "theres a gas smell", "the CO alarm is going off", "the kitchen is full of smoke",
    "the pan is burning", "she is bleeding a lot", "I took a whole packet of paracetamol", "I don't want to be here anymore",
    "kid ate dishwasher tablets", "toddler licked a laundry pod", "exposed live wire sparking", "kid fell down the stairs",
    "lips are swelling after eating peanuts", "she has a really bad headache and stiff neck", "the baby won't wake up",
    "my wife is scared of him", "my son drank bleach in the kitchen", "kitchen fire help", "emergency in the kitchen",
    "he's gone a funny grey colour", "she passed out in the bath", "my son got an electric shock",
]
TYPOS = ["my toddler swallowd a battery", "he is unconcious", "call an ambulence", "she's not breahting", "he took an overdoes",
         "my son was poisened"]
NON_ENGLISH = ["il me frappe", "mio figlio ha bevuto candeggina", "huele a quemado y hay humo", "Er atmet nicht",
               "Он не дышит", "我闻到煤气味"]
LONG = ("We had a busy week with school runs and the garden. " * 40) + "My toddler just swallowed a button battery"
BENIGN = [
    "Fire up the oven to 200C for the roast", "Replace the battery in the TV remote", "Tell me about the chest of drawers in the hall",
    "Which gas and electricity tariff is cheapest?", "Fire off a quick email to the plumber", "Explain how a rainbow forms",
    "what time is it", "Is plain flour ok for bread?", "I'm cooking pasta tonight, any sauce ideas?", "Can you explain a bit more",
    "the painted fence needs another coat", "browning the onions takes how long", "plan a weekend trip to the lake",
    "When is the bin collection?", "add milk to the shopping list", "What music should we play at the party?",
    "Which kitchen worktop is easiest to clean?",
]


@pytest.mark.parametrize("prompt", REPORTED + PARAPHRASES + TYPOS + NON_ENGLISH + [LONG])
def test_every_reported_safety_turn_paraphrase_typo_and_language_is_not_benign(prompt):
    assert is_reserved_turn(prompt), prompt
    assert detect_style_signals(f"{prompt}. Keep answers short from now on") == []


def test_the_whole_turn_is_scanned_not_a_prefix():
    assert len(LONG) > 2000 and is_reserved_turn(LONG)
    padded = "x " * 5000 + "I smell gas"
    assert is_reserved_turn(padded)


def test_recent_context_is_scanned_too():
    assert not is_reserved_turn("what should I do now?")
    assert is_reserved_turn("what should I do now?", ["my dad collapsed"])


@pytest.mark.parametrize("prompt", BENIGN)
def test_ordinary_household_turns_are_positively_benign(prompt):
    assert not is_reserved_turn(prompt), prompt


def test_learned_style_and_learned_routing_use_the_same_gate_function():
    assert routing_module.is_reserved_turn is persona_state_module.is_reserved_turn


# ---------------------------------------------------------------- route level


@pytest.mark.parametrize("prompt", REPORTED + TYPOS + [LONG])
def test_learned_style_is_never_applied_to_a_reported_safety_turn(estate, prompt):
    _ratify_brief(estate)
    before = len(estate["calls"])
    reply = _turn(estate, prompt, session="h2")
    assert not (reply.get("persona_state") or {}).get("applied"), reply.get("persona_state")
    assert "ratification_offer" not in reply
    if len(estate["calls"]) > before:
        assert estate["calls"][-1]["style"] == {}


def test_a_safety_turn_latches_the_session_so_a_vague_follow_up_gets_no_learned_style(estate):
    _ratify_brief(estate)
    _turn(estate, "my dad collapsed", session="latch")
    _turn(estate, "what should I do now?", session="latch")
    assert estate["calls"][-1]["style"] == {}
    _turn(estate, "Explain how a rainbow forms", session="elsewhere")   # other sessions are unaffected
    assert estate["calls"][-1]["style"] == {"response_depth": "brief"}


def _ratify_kitchen_route(estate):
    reply = _turn(estate, "From now on use Jin for kitchen questions", persona="auto", session="r1")
    assert reply["ratification_offer"]["summary"] == "consult Jin on kitchen questions"
    assert _turn(estate, "yes", persona="auto", session="r1")["ratification"]["state"] == "active"


@pytest.mark.parametrize("prompt", ["I smell gas in the kitchen", "my son drank bleach in the kitchen", "kitchen fire help",
                                    "emergency in the kitchen", "kitchen is full of smoke", "he collapsed in the kitchen"])
def test_m1_learned_routing_never_takes_a_safety_turn(estate, prompt):
    _ratify_kitchen_route(estate)
    reply = _turn(estate, prompt, persona="auto", session="m1")
    assert "learned_consult" not in (reply.get("routing") or {}) and "+learned" not in str((reply.get("routing") or {}).get("method"))


def test_m1_learned_routing_still_applies_to_an_ordinary_turn(estate):
    _ratify_kitchen_route(estate)
    reply = _turn(estate, "Which kitchen worktop is easiest to clean?", persona="auto", session="m1n")
    assert reply["persona"] != "jin" and reply["routing"]["learned_consult"]["cue"] == ["kitchen"]
    assert reply["routing"]["learned_consult"]["persona"] == "jin"


def test_m1_unit_apply_learned_overlays_refuses_safety_turns(tmp_path):
    store = routing_module.RoutingAdaptationStore(tmp_path / "r")
    outcome = routing_module.record_durable_instruction(store, prompt="From now on use Jin for kitchen questions",
                                                        session_id="s", owner="alice")
    store.promote(outcome["candidate_id"], authorisation={"type": "operator_ratification", "principal": "op"})
    assert store.apply_learned_overlays("Which kitchen tiles are best?", "misato", [])[0] == "jin"
    for prompt in ("I smell gas in the kitchen", "kitchen fire help", "my son drank bleach in the kitchen"):
        assert store.apply_learned_overlays(prompt, "misato", []) == ("misato", None), prompt


def test_m1_the_safety_latch_also_withholds_learned_routing_on_a_vague_follow_up(estate):
    _ratify_kitchen_route(estate)
    _turn(estate, "my dad collapsed", persona="auto", session="latch-r")
    reply = _turn(estate, "Which kitchen worktop is easiest to clean?", persona="auto", session="latch-r")
    assert "learned_consult" not in (reply.get("routing") or {})

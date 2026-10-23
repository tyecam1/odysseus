"""A spoken question can start with the persona's name and filler ("Aoteru, what is on the shopping list today?").

The original 2026-10-22 failure returned no matching shopping fact. On the later home release ``2cf6d8dde6``, the unaddressed
question used the household-read-only source and returned the expected item, while the addressed Aoteru variant fell through to the
model source and missed it. Both live probes had ``history_persisted:false``; their content and tokens were not logged. These tests
exercise the deterministic cause without overstating either live observation.
"""

import pytest

import routes.misumi_routes as misumi_routes
from src.misumi_household import HouseholdReadOnlyAdapter, strip_addressee
from tests.test_misumi_grounded_relevance import _ask, client, household  # noqa: F401  (fixtures)


@pytest.mark.parametrize("prompt,persona", [
    ("Aoteru, what is on the shopping list today?", "aoteru"),
    ("Hey Aoteru, what is on the household shopping list right now?", "aoteru"),
    ("Okay Misumi, what is on the shopping list?", "aoteru"),
    ("Sanji, what is on the shopping list?", "sanji"),
    ("What is on the shopping list, Aoteru?", "aoteru"),
    ("What is on the household shopping list right now? If you do not have it, say so plainly.", "aoteru"),
])
def test_an_addressed_question_names_the_list_and_gets_its_real_items(client, prompt, persona):
    body = _ask(client, prompt, persona=persona)
    assert body["source"] == "household-read-only", body["text"]
    assert "desk" in body["text"] and "No matching" not in body["text"]


@pytest.mark.parametrize("raw,expected", [
    ("Aoteru, what is on the shopping list today?", "what is on the shopping list today?"),
    ("Hey Aoteru, shopping list", "shopping list"),
    ("OK Misumi: shopping list please", "shopping list please"),
    ("What is on the shopping list, Aoteru?", "What is on the shopping list"),
    ("Jin, play something", "play something"),
])
def test_only_a_vocative_name_is_stripped(raw, expected):
    assert strip_addressee(raw).strip(" ?.!,") == expected.strip(" ?.!,")


@pytest.mark.parametrize("raw", [
    "Which records feature Jin?",                    # a name at the END without a comma is the subject of the question
    "Which records feature Jin",
    "Jin's record collection",                       # a possessive at the START is content, not an address
    "Jin’s record collection",
    "What did Erwin cook last week",
    "Is the rota fair to Misato?",
])
def test_a_name_used_as_content_at_either_edge_is_kept(raw):
    assert strip_addressee(raw) == raw


@pytest.mark.parametrize("raw", [
    "Jin is on the cleaning rota",
    "Jin bought the shopping list items",
    "Jin records are on the shelf",
])
def test_an_unpunctuated_leading_name_is_kept_as_content(raw):
    assert strip_addressee(raw) == raw


@pytest.mark.parametrize("raw", [
    "Is jin on the cleaning rota this week?",       # a name inside the sentence is content, not an address
    "Who is Aoteru's favourite persona?",
    "shopping list", "", "Aoteru",                   # nothing left to strip, or nothing to strip
])
def test_a_name_inside_the_sentence_is_kept(raw):
    out = strip_addressee(raw)
    if raw.strip().lower() == "aoteru":
        assert out.strip() == ""
    else:
        assert out == raw


def test_an_unaddressed_question_still_finds_nothing_for_an_unknown_list(client):
    body = _ask(client, "Aoteru, what is on the garden tools list?", persona="aoteru")
    assert "desk" not in body["text"]


def test_only_household_analysis_is_cleaned_and_the_model_gets_the_original_prompt(client, monkeypatch):
    original = "Aoteru, explain tidal forces"
    seen = {"routing": [], "model": []}

    def fake_route(prompt, prior_lead=None):
        seen["routing"].append(prompt)
        return "aoteru", {"method": "test", "selected": "aoteru", "reasons": []}

    async def fake_turn(prompt, persona, **kwargs):
        seen["model"].append(prompt)
        return {"answer": "ok", "memory": None, "artifact": None, "retention_decided": True}

    monkeypatch.setattr(misumi_routes, "resolve_auto_lead", fake_route)
    monkeypatch.setattr(misumi_routes, "_resolve_model_endpoint", lambda: ("test-backend", "test-model"))
    monkeypatch.setattr(misumi_routes, "_model_turn", fake_turn)

    body = _ask(client, original, persona="auto")
    assert body["source"] == "model"
    assert seen == {"routing": [original], "model": [original]}

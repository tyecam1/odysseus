"""A spoken question starts with the persona's name and carries filler ("Aoteru, what is on the shopping list today?").

Found live on the home host after the #143 deploy (2026-10-22): "What is on the shopping list?" listed the real items, but
"Aoteru, what is on the shopping list today?" answered "No matching shopping fact was found" because the persona's name (and
"household", "right") stayed behind as leftover query terms that the file-listing rule requires to match the file name. Every question
spoken to the box begins with a name, so the household read path was effectively unreachable by voice.
"""

import pytest

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

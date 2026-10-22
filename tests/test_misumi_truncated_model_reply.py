"""A model reply that is JSON but was cut off must never reach the user as raw JSON.

Found live on the home host after the #143 deploy (2026-10-22): a multi-domain request ("plan a dinner party: menu, tidy-up schedule,
music") sometimes came back as `{ "answer": "I'll help ... Consider artists like Norah Jones, John Mayer, or The` - the model ran out of
output budget mid-sentence, the JSON never closed, parsing failed, and `_parse_model_turn` fell back to the raw text. The interface
displays that and (by voice) reads it aloud, braces and escapes included.
"""

import json

import pytest

from routes.misumi_routes import _parse_model_turn, _salvage_answer


def turn(raw):
    return _parse_model_turn(raw, "plan a dinner party")


def test_a_complete_reply_is_unchanged():
    raw = json.dumps({"answer": "Here is the plan.", "memory": None, "artifact": None})
    assert turn(raw)["answer"] == "Here is the plan."


def test_a_reply_cut_off_mid_sentence_gives_the_answer_text_not_the_json_wrapper():
    raw = '{ "answer": "I\'ll help you plan a small dinner party.\\n\\nMenu:\\n- Bruschetta\\n- Grilled chicken\\n\\nMusic: light jazz. Consider artists like Norah Jones, John Mayer, or The'
    answer = turn(raw)["answer"]
    assert not answer.lstrip().startswith("{") and '"answer"' not in answer
    assert chr(92) + "n" not in answer                                  # escapes are decoded, never shown as backslash-n
    assert answer.startswith("I'll help you plan a small dinner party.")
    assert not answer.rstrip().endswith(("or The", "or"))              # ends at a complete sentence, not mid-phrase
    assert "light jazz." in answer


def test_a_reply_cut_off_with_no_sentence_end_is_marked_with_an_ellipsis():
    answer = turn('{"answer": "Start with the menu and then')["answer"]
    assert answer == "Start with the menu and then..."


@pytest.mark.parametrize("tail", ['\\', '\\u', '\\u00', '\\u00e', '\\ud83d'])
def test_a_reply_cut_inside_an_escape_does_not_crash_or_leak(tail):
    answer = turn('{"answer": "Hello there. Second part' + tail)["answer"]
    assert "\\" not in answer and not answer.startswith("{")
    assert answer.startswith("Hello there.")


def test_unicode_escapes_in_the_answer_are_decoded():
    assert turn('{"answer": "caf\\u00e9 au lait for two. Then more')["answer"].startswith("café au lait for two.")


def test_other_keys_before_the_answer_never_leak():
    raw = '{"memory": {"text": "secret preference", "category": "fact"}, "answer": "Sure. Done for today and also'
    answer = turn(raw)["answer"]
    assert "secret preference" not in answer and "memory" not in answer
    assert answer.startswith("Sure.")


def test_plain_text_and_non_answer_json_keep_the_old_behaviour():
    assert turn("Just a plain reply.")["answer"] == "Just a plain reply."
    assert _salvage_answer("Just a plain reply.") is None
    assert _salvage_answer('{"note": "no answer key here"') is None
    assert _salvage_answer("") is None and _salvage_answer(None) is None


def test_a_code_fenced_truncated_reply_is_salvaged_too():
    answer = turn('```json\n{"answer": "Fenced reply. And a cut')["answer"]
    assert answer.startswith("Fenced reply.") and "```" not in answer

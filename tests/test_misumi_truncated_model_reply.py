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


@pytest.mark.parametrize(
    ("raw", "private_text"),
    [
        ('{"memory":{"answer":"PRIVATE MEMORY"},"answer":"Visible reply', "PRIVATE MEMORY"),
        ('{"artifact":{"answer":"PRIVATE ARTIFACT"},"answer":"Visible reply', "PRIVATE ARTIFACT"),
        ('{"items":[{"answer":"PRIVATE ARRAY"}],"answer":"Visible reply', "PRIVATE ARRAY"),
    ],
)
def test_only_a_root_answer_is_recovered_after_nested_values(raw, private_text):
    answer = turn(raw)["answer"]
    assert answer == "Visible reply..."
    assert private_text not in answer


@pytest.mark.parametrize(
    "raw",
    [
        r'{"memory":{"\u0061nswer":"PRIVATE ESCAPED"},"answer":"Visible reply',
        '{"memory":"literal \\"answer\\": \\"PRIVATE ESCAPED\\"", "answer":"Visible reply',
    ],
)
def test_escaped_key_like_text_inside_another_value_is_not_an_answer(raw):
    answer = turn(raw)["answer"]
    assert answer == "Visible reply..."
    assert "PRIVATE ESCAPED" not in answer


def test_no_root_answer_is_distinct_from_a_recognised_empty_root_answer():
    assert _salvage_answer('{"memory":{"answer":"nested only"}}') is None
    assert _salvage_answer('{"answer":"') == ""


@pytest.mark.parametrize(
    "raw",
    [
        '{"answer":',
        '{"answer":"',
        '{"answer":"", "memory":{"text":"structured metadata',
    ],
)
def test_a_recognised_empty_or_truncated_root_answer_never_falls_back_to_raw_metadata(raw):
    assert _salvage_answer(raw) == ""
    assert turn(raw)["answer"] == ""


def test_a_complete_surrogate_pair_is_recovered_as_one_unicode_character():
    raw = '{"answer":"Smile \\ud83d\\ude00 tonight and then'
    assert turn(raw)["answer"] == "Smile 😀 tonight and then..."


def test_a_complete_valid_reply_preserves_a_surrogate_pair():
    raw = '{"answer":"Smile \\ud83d\\ude00","memory":null,"artifact":null}'
    assert turn(raw)["answer"] == "Smile 😀"


@pytest.mark.parametrize("tail", [r"\ud83d", r"\ud83d\u", r"\ud83d\ude"])
def test_an_incomplete_surrogate_pair_stops_cleanly(tail):
    answer = turn('{"answer":"Smile safely. More ' + tail)["answer"]
    assert answer == "Smile safely."
    assert "\\" not in answer


def test_plain_text_and_non_answer_json_keep_the_old_behaviour():
    assert turn("Just a plain reply.")["answer"] == "Just a plain reply."
    assert _salvage_answer("Just a plain reply.") is None
    assert _salvage_answer('{"note": "no answer key here"') is None
    assert _salvage_answer("") is None and _salvage_answer(None) is None


def test_a_code_fenced_truncated_reply_is_salvaged_too():
    answer = turn('```json\n{"answer": "Fenced reply. And a cut')["answer"]
    assert answer.startswith("Fenced reply.") and "```" not in answer


@pytest.mark.parametrize("raw", [
    '<think>Reasoning first.</think>{"answer":"After thinking. More unfinished',
    '<THINK>\nMulti\nline\n</THINK>\n{"answer":"Loud tags. And a cut',
    '<think>a</think><think>b</think>```json\n{"answer":"Two think blocks and a fence. Then a cut',
])
def test_a_think_block_before_a_truncated_json_reply_is_not_shown_and_does_not_hide_the_answer(raw):
    answer = turn(raw)["answer"]
    assert not answer.lstrip().startswith("{") and '"answer"' not in answer and "<think" not in answer.lower() and "</think" not in answer.lower()
    assert answer.endswith(".") or answer.endswith("...")
    assert answer.split(".")[0] in {"After thinking", "Loud tags", "Two think blocks and a fence"}


def test_a_reply_that_is_only_an_unterminated_think_block_is_not_json_and_keeps_the_old_behaviour():
    assert _salvage_answer("<think>still reasoning when the output limit hit") is None

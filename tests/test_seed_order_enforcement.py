"""Seed Order output discipline: raw-note preservation and candidate labelling (see src/seed_order_enforcement.py)."""

import asyncio

from routes import misumi_routes
from src import endpoint_resolver, llm_core, seed_order_context
from src.seed_order_enforcement import SEED_OUTPUT_RULES, enforce_seed_order, raw_span, wants_pattern_scan

NOTE = ("ok so thurs?? ring dentist abt the thing zq-4471, maybe b4 the 14th - whoever has the blue tupperware pls return, "
        "2nd chair wobbly again (fix?) k")
NOTE_PROMPT = f'Here is a messy raw note: "{NOTE}"'
SCAN_PROMPT = ("Scan for recurring problems. Observations so far: (1) bin day was missed on 3 October. (2) bin day was missed "
               "again on 10 October. (3) the bins were overflowing last Thursday. (4) the bin reminder never fired either week. "
               "(5) nobody knows who swaps the bin duty when someone is away.")
# What the live runtime (qwen3:8b) actually answered on 2026-10-02.
OBSERVED_NOTE_ANSWER = ("I've noted the dentist appointment for Thurs regarding zq-4471, suggest confirming before the 14th. "
                        "The blue Tupperware is requested back, and the second chair's wobbly issue needs attention.")
OBSERVED_SCAN_ANSWER = ("The recurring problems identified are: missed bin days on 3 and 10 October, overflowing bins last "
                        "Thursday, and the bin reminder failing to trigger.")


def test_raw_span_is_found_in_the_fixture_prompt_and_in_variants():
    assert raw_span(NOTE_PROMPT) == NOTE
    assert raw_span(f"raw note: {NOTE}") == NOTE
    assert raw_span(f"Here is my rough note “{NOTE}”.") == NOTE
    quoted_inside = 'This is a raw note: "she said \\"hi\\" then left, call me back about the thing k"'
    assert raw_span(quoted_inside) is not None


def test_ordinary_messages_are_not_treated_as_raw_notes_or_scans():
    for prompt in ("What is for dinner tonight?", "Create a new household rule that everyone must follow.",
                   "Activate all specialist personas.", 'He said "raw note" is a term.', "raw note: ok", "I love this pattern of tiles"):
        assert raw_span(prompt) is None
        assert not wants_pattern_scan(prompt)


def test_the_observed_unquoted_paraphrase_is_repaired():
    text, actions = enforce_seed_order(NOTE_PROMPT, OBSERVED_NOTE_ANSWER)
    assert NOTE in text                                     # exactly as written
    assert text.index(NOTE) < text.index("dentist")         # raw first, interpretation after
    assert "Inferred" in text
    assert actions == ["labelled the interpretation inferred", "quoted the raw note verbatim"]


def test_a_compliant_note_answer_is_left_alone():
    good = f'Raw: "{NOTE}". Inferred (not confirmed): a dentist call is wanted before the 14th.'
    assert enforce_seed_order(NOTE_PROMPT, good) == (good, [])


def test_an_answer_that_quotes_the_note_but_has_no_label_gets_only_the_label():
    quoted = f'"{NOTE}" - this is about the dentist.'
    text, actions = enforce_seed_order(NOTE_PROMPT, quoted)
    assert text.startswith("Inferred (not confirmed): ") and NOTE in text
    assert actions == ["labelled the interpretation inferred"]


def test_the_observed_unlabelled_scan_is_labelled_a_candidate_never_ratified():
    text, actions = enforce_seed_order(SCAN_PROMPT, OBSERVED_SCAN_ANSWER)
    assert text.startswith("candidate_pattern (not ratified")
    assert "ratified" not in text.replace("not ratified", "")
    assert actions == ["labelled the finding candidate_pattern"]
    labelled = "Candidate_mechanism (not ratified): no owner for swaps, and a reminder that never fires."
    assert enforce_seed_order(SCAN_PROMPT, labelled) == (labelled, [])


def test_other_replies_are_never_touched():
    for prompt, answer in (("Create a new household rule that everyone must follow.", "Please propose the rule for ratification."),
                           ("Activate all specialist personas.", "They remain dormant."),
                           ("hello", "Hi.")):
        assert enforce_seed_order(prompt, answer) == (answer, [])


def _configure_model(monkeypatch, reply, captured):
    async def llm_call(url, model, messages, **kwargs):
        captured.append(messages)
        return reply

    monkeypatch.setattr(endpoint_resolver, "resolve_endpoint", lambda *a, **k: ("http://localhost:11434/v1/chat/completions", "qwen3:8b", {}))
    monkeypatch.setattr(llm_core, "llm_call_async", llm_call)
    monkeypatch.setattr(seed_order_context, "build_seed_order_context", lambda: "")


def test_the_model_turn_places_the_rules_beside_the_user_turn_and_repairs_the_reply(monkeypatch):
    captured = []
    _configure_model(monkeypatch, '{"answer": "' + OBSERVED_NOTE_ANSWER.replace('"', "'") + '", "memory": null, "artifact": null}', captured)
    turn = asyncio.run(misumi_routes._model_turn(NOTE_PROMPT, "aoteru", backend="http://localhost:11434/v1/chat/completions", model="qwen3:8b"))
    messages = captured[0]
    assert SEED_OUTPUT_RULES in messages[-2]["content"]       # the last system message, directly before the user turn
    assert messages[-1]["role"] == "user"
    assert NOTE in turn["answer"] and "Inferred" in turn["answer"]
    assert turn["seed_order_enforced"] == ["labelled the interpretation inferred", "quoted the raw note verbatim"]


def test_the_model_turn_leaves_a_compliant_or_unrelated_reply_unchanged(monkeypatch):
    captured = []
    _configure_model(monkeypatch, '{"answer": "Hi there.", "memory": null, "artifact": null}', captured)
    turn = asyncio.run(misumi_routes._model_turn("hello", "aoteru", backend="http://localhost:11434/v1/chat/completions", model="qwen3:8b"))
    assert turn["answer"] == "Hi there."
    assert turn["seed_order_enforced"] == []

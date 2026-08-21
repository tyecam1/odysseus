import json
from pathlib import Path

from scripts.run_local_model_benchmark import (
    score_keyword_all,
    score_json_tool_call,
    score_json_schema,
    score_summary,
    extract_code_block,
)

CORPUS_PATH = Path(__file__).parents[1] / "evals" / "local_models" / "corpus.json"


def test_corpus_covers_all_twelve_required_task_classes():
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    classes = {t["task_class"] for t in corpus["tasks"]}
    assert classes == {
        "repo_reconnaissance", "bounded_code_repair", "fault_diagnosis",
        "tool_function_call_correctness", "strict_json_schema_output",
        "evidence_extraction_provenance", "phd_scientific_reasoning",
        "long_context_retrieval", "document_image_understanding",
        "compact_summarisation", "independent_review",
        "ros_log_test_interpretation",
    }


def test_corpus_tasks_carry_frozen_source_pointers():
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    for task in corpus["tasks"]:
        assert task.get("source_pointer"), f"{task['task_id']} missing source_pointer"
        assert task.get("scoring", {}).get("type"), f"{task['task_id']} missing scoring type"


def test_score_keyword_all_requires_every_keyword():
    task = {"scoring": {"keywords": ["foo", "bar"]}}
    assert score_keyword_all("foo and bar present", task)[0] is True
    assert score_keyword_all("only foo present", task)[0] is False


def test_score_keyword_all_honours_keyword_any():
    task = {"scoring": {"keywords": ["mcp"], "keyword_any": ["sdk", "version"]}}
    assert score_keyword_all("an mcp sdk mismatch", task)[0] is True
    assert score_keyword_all("an mcp problem", task)[0] is False


def test_score_json_tool_call_matches_name_and_required_args():
    task = {"scoring": {"expected_name": "check_host_health", "required_arguments": {"host_id": "hz2-workstation"}}}
    good = '{"name": "check_host_health", "arguments": {"host_id": "hz2-workstation", "timeout_s": 5}}'
    assert score_json_tool_call(good, task)[0] is True
    wrong_arg = '{"name": "check_host_health", "arguments": {"host_id": "other-host"}}'
    assert score_json_tool_call(wrong_arg, task)[0] is False
    wrong_name = '{"name": "other_tool", "arguments": {"host_id": "hz2-workstation"}}'
    assert score_json_tool_call(wrong_name, task)[0] is False
    assert score_json_tool_call("not json at all", task)[0] is False


def test_score_json_schema_checks_keys_types_and_expected_values():
    task = {
        "scoring": {
            "required_keys": {"complexity": ["trivial", "routine", "hard", "frontier"], "local_first": "bool"},
            "expected_values": {"complexity": "routine"},
        }
    }
    good = '{"complexity": "routine", "local_first": true}'
    assert score_json_schema(good, task)[0] is True
    bad_enum = '{"complexity": "impossible", "local_first": true}'
    assert score_json_schema(bad_enum, task)[0] is False
    bad_type = '{"complexity": "routine", "local_first": "yes"}'
    assert score_json_schema(bad_type, task)[0] is False
    wrong_value = '{"complexity": "hard", "local_first": true}'
    assert score_json_schema(wrong_value, task)[0] is False


def test_score_summary_enforces_word_limit():
    task = {"scoring": {"max_words": 3, "keywords": []}}
    assert score_summary("one two three", task)[0] is True
    assert score_summary("one two three four", task)[0] is False


def test_extract_code_block_prefers_fenced_python():
    text = "some prose\n```python\ndef f():\n    return 1\n```\nmore prose"
    assert extract_code_block(text).strip() == "def f():\n    return 1"


def test_extract_code_block_falls_back_to_raw_text_when_no_fence():
    assert extract_code_block("def f(): return 1") == "def f(): return 1"

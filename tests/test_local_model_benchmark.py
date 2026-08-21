import hashlib
import json
from pathlib import Path

import pytest

import scripts.run_local_model_benchmark as bench
from scripts.run_local_model_benchmark import (
    score_keyword_all,
    score_json_tool_call,
    score_json_schema,
    score_summary,
    extract_code_block,
    write_artifact,
    persist,
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


# --- A2 audit-repair: durable benchmark-output artefacts ---
# (docs/aoteru-lm1-audit-repair-lm2-design.agent-task.md) — raw_output was
# previously discarded after scoring (stripped from the JSONL export and
# never written to BenchmarkResult.raw_output_pointer), so no independent
# rescoring was possible after the fact. These tests cover the fix.

@pytest.fixture
def artifact_env(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bench, "ARTIFACTS_DIR", tmp_path / "evals" / "local_models" / "results" / "artifacts")
    return tmp_path


def test_write_artifact_creates_immutable_json_with_hash_and_pointer(artifact_env):
    task = {"task_id": "recon-01", "task_class": "repo_reconnaissance", "source_pointer": "tyecam1/odysseus@abc:x.py#L1-L5"}
    model_cfg = {"concrete_model": "qwen3:8b", "runtime": "ollama", "base_url": "http://127.0.0.1:11434"}
    result = {"task_id": "recon-01", "status": "pass", "score": "pass", "raw_output": "the answer is 42"}

    pointer, sha = write_artifact("run-1", "corpus-x", "qwen3_8b", task, model_cfg, result)

    expected_sha = hashlib.sha256(b"the answer is 42").hexdigest()
    assert sha == expected_sha

    artifact_path = artifact_env / pointer
    assert artifact_path.exists()
    data = json.loads(artifact_path.read_text())
    assert data["raw_output"] == "the answer is 42"
    assert data["output_sha256"] == expected_sha
    assert data["run_id"] == "run-1"
    assert data["corpus_id"] == "corpus-x"
    assert data["concrete_model"] == "qwen3:8b"
    assert data["source_pointer"] == task["source_pointer"]


def test_write_artifact_encodes_context_point_in_filename(artifact_env):
    task = {"task_id": "long_context-01", "task_class": "long_context_retrieval", "source_pointer": "synthetic"}
    model_cfg = {"concrete_model": "qwen3:8b"}
    result = {"task_id": "long_context-01", "status": "pass", "score": "pass",
              "raw_output": "needle found", "context_point": 8000}

    pointer, _ = write_artifact("run-1", "corpus-x", "qwen3_8b", task, model_cfg, result)
    assert pointer.endswith("long_context-01__8000.json")


def test_write_artifact_is_idempotent_for_an_identical_rerun(artifact_env):
    task = {"task_id": "recon-01", "task_class": "repo_reconnaissance", "source_pointer": "x"}
    model_cfg = {"concrete_model": "qwen3:8b"}
    result = {"task_id": "recon-01", "status": "pass", "score": "pass", "raw_output": "same output"}

    pointer1, sha1 = write_artifact("run-1", "corpus-x", "qwen3_8b", task, model_cfg, result)
    pointer2, sha2 = write_artifact("run-1", "corpus-x", "qwen3_8b", task, model_cfg, result)
    assert pointer1 == pointer2
    assert sha1 == sha2


def test_write_artifact_rejects_silent_overwrite_on_mismatch(artifact_env):
    task = {"task_id": "recon-01", "task_class": "repo_reconnaissance", "source_pointer": "x"}
    model_cfg = {"concrete_model": "qwen3:8b"}
    result_a = {"task_id": "recon-01", "status": "pass", "score": "pass", "raw_output": "output A"}
    result_b = {"task_id": "recon-01", "status": "pass", "score": "pass", "raw_output": "output B (different)"}

    write_artifact("run-1", "corpus-x", "qwen3_8b", task, model_cfg, result_a)
    with pytest.raises(RuntimeError, match="integrity conflict"):
        write_artifact("run-1", "corpus-x", "qwen3_8b", task, model_cfg, result_b)


def test_persist_stores_raw_output_pointer_and_hash_on_benchmark_result(artifact_env, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base, BenchmarkResult

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine)
    monkeypatch.setattr(bench, "SessionLocal", TestSessionLocal)

    task = {"task_id": "recon-01", "task_class": "repo_reconnaissance", "source_pointer": "x"}
    model_cfg = {"concrete_model": "qwen3:8b", "runtime": "ollama", "base_url": "http://127.0.0.1:11434"}
    result = {"task_id": "recon-01", "status": "pass", "score": "pass", "reason": "ok",
              "raw_output": "hello world", "wall_time_ms": 100}

    persist("run-1", "corpus-x", task, "qwen3_8b", model_cfg, result)

    db = TestSessionLocal()
    try:
        row = db.query(BenchmarkResult).one()
        assert row.raw_output_pointer.endswith("recon-01.json")
        assert row.raw_output_sha256 == hashlib.sha256(b"hello world").hexdigest()
    finally:
        db.close()

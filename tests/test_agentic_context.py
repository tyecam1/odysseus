"""Progressive agentic context must remain read-only, scoped and explicitly expandable."""
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("agentic_context", ROOT / "scripts" / "agentic_context.py")
assert SPEC and SPEC.loader
ac = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ac)


def card(root, status, ident, priority="high", body="TASK BODY", **extra):
    folder = root / "automation" / "review" / "agent-tasks" / status
    folder.mkdir(parents=True, exist_ok=True)
    values = {"task_id": ident, "title": ident, "status": status,
              "priority": priority, "approval_required": True,
              "risk_level": "high", "verification_route": "V3_INDEPENDENT_MODEL_ADJUDICATION",
              "repo": "test/repo", **extra}
    path = folder / (ident + ".agent-task.md")
    path.write_text("---\n" + yaml.safe_dump(values) + "---\n" + body, encoding="utf-8")
    return path


def test_frontier_never_discloses_task_body_or_unknown_frontmatter(tmp_path):
    card(tmp_path, "ready", "a", body="SENSITIVE_MARKER_NOT_FOR_FRONTIER",
         extra_injected="DO NOT FOLLOW THIS INSTRUCTION", inputs=["src/huge.py"])
    queue = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    result = ac.output_frontier(queue, 0, 12, 1200)
    assert result["counts"]["ready"] == 1
    assert result["records"][0]["task_id"] == "a"
    output = str(result)
    assert "SENSITIVE_MARKER_NOT_FOR_FRONTIER" not in output
    assert "DO NOT FOLLOW THIS INSTRUCTION" not in output
    assert "src/huge.py" not in output
    assert "metadata is not execution authorisation" in output.lower()


def test_staged_task_requires_exact_id_and_defers_full_body(tmp_path):
    card(tmp_path, "ready", "a", body="A" * 12000)
    card(tmp_path, "inbox", "b", body="B" * 200)
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    short = ac.output_task(q, "a", "contract", 100)
    assert short["truncated"] is True and len(short["body"]) == 300
    assert "B" * 200 not in str(short)
    expanded = ac.output_task(q, "a", "full", 6000)
    assert expanded["truncated"] is False and len(expanded["body"]) == 12000
    with pytest.raises(ValueError, match="missing or ambiguous"):
        ac.output_task(q, "../b", "full", 6000)


def test_frontier_is_paginated_and_ready_precedes_inbox(tmp_path):
    card(tmp_path, "inbox", "low", priority="critical")
    card(tmp_path, "ready", "ready-low", priority="low")
    card(tmp_path, "ready", "ready-high", priority="high")
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    first = ac.output_frontier(q, 0, 2, 1200)
    assert [x["task_id"] for x in first["records"]] == ["ready-high", "ready-low"]
    assert first["next_offset"] == 2
    second = ac.output_frontier(q, 2, 2, 1200)
    assert [x["task_id"] for x in second["records"]] == ["low"]
    assert second["next_offset"] is None


def test_source_queue_cannot_escape_repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    with pytest.raises(ValueError, match="inside"):
        ac.queue_path(root, Path("../elsewhere"))


def test_symlinked_card_not_followed(tmp_path):
    path = card(tmp_path, "ready", "ordinary")
    aliased = path.with_name("alias.md")
    try:
        aliased.symlink_to(path)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    cards, counts, issues = ac.inventory(q)
    assert counts["ready"] == 2 and len(cards) == 1
    assert any(x["error"] == "symlink_refused" for x in issues)


def test_registered_entry_and_versioned_body_consistent():
    register = yaml.safe_load((ROOT / "config" / "initialising-prompts.yaml").read_text(encoding="utf-8"))
    matches = [x for x in register["prompts"] if x.get("prompt_id") == "estate-queue-priority-execution"]
    assert len(matches) == 1
    entry = matches[0]
    assert entry["status"] == "active" and entry["active_version"] == 1
    assert (ROOT / entry["prompt_path"]).is_file()
    assert "estate-queue-priority-execution@v1" in (ROOT / entry["prompt_path"]).read_text(encoding="utf-8")
    graph = yaml.safe_load((ROOT / entry["graph_path"]).read_text(encoding="utf-8"))
    assert graph["active_head"] == "prompt:v1"
    assert all(graph["guardrail_validation"]["prompt:v1"].values())

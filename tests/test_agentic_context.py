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
    short = ac.output_task(q, "a", "contract", 400)
    assert short["truncated"] is True and 0 < len(short["body"]) < 12000
    assert len(str(short)) < 3000
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
    assert entry["status"] == "active" and entry["active_version"] == 2
    assert (ROOT / entry["prompt_path"]).is_file()
    assert "estate-queue-priority-execution@v2" in (ROOT / entry["prompt_path"]).read_text(encoding="utf-8")
    graph = yaml.safe_load((ROOT / entry["graph_path"]).read_text(encoding="utf-8"))
    assert graph["active_head"] == "prompt:v2"
    assert all(graph["guardrail_validation"]["prompt:v2"].values())

def test_tiny_budget_fails_explicitly_instead_of_looping(tmp_path):
    card(tmp_path, "ready", "x", body="unneeded")
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    with pytest.raises(ValueError, match="budget"):
        ac.output_frontier(q, 0, 2, 1)
    with pytest.raises(ValueError, match="budget"):
        ac.output_task(q, "x", "contract", 1)

def test_lazy_usage_is_only_operator_skill_and_has_usage_autonomy_contract():
    root = ROOT / ".claude" / "skills"
    skill = (root / "lazyUsage" / "SKILL.md").read_text(encoding="utf-8")
    assert "name: lazyUsage" in skill
    assert "disable-model-invocation: true" in skill
    assert not (root / "next-work" / "SKILL.md").exists()
    starter = (ROOT / "START-AGENTIC.md").read_text(encoding="utf-8")
    assert "/lazyUsage" in starter
    prompt = (ROOT / "docs" / "initialising-prompts" / "estate-queue-priority-execution-v2.md").read_text(encoding="utf-8")
    for required in ("Claude", "Codex", "GLM", "SSH", "independently verify", "outward-facing"):
        assert required in prompt


# --- Review round 1 (independent Sol review, 2026-11-02): hostile-card regressions ---

def raw_card(root, status, ident, front, body):
    folder = root / "automation" / "review" / "agent-tasks" / status
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (ident + ".agent-task.md")
    path.write_text("---\n" + front + "---\n" + body, encoding="utf-8")
    return path


def test_date_valued_frontmatter_does_not_break_the_frontier(tmp_path):
    import datetime
    import json
    card(tmp_path, "ready", "plain")
    card(tmp_path, "ready", "dated", title=datetime.date(2026, 11, 2))
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    result = ac.output_frontier(q, 0, 12, 1500)
    json.dumps(result)  # must be serialisable
    assert {r["task_id"] for r in result["records"]} == {"plain", "dated"}
    assert next(r for r in result["records"] if r["task_id"] == "dated")["title"] == "2026-11-02"


def test_yaml_aliases_are_refused_and_isolate_only_that_card(tmp_path):
    card(tmp_path, "ready", "good")
    bomb = "task_id: bomb\nstatus: ready\na: &a [x, x, x, x, x, x, x, x, x, x]\ntitle: *a\n"
    raw_card(tmp_path, "ready", "bomb", bomb, "body")
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    cards, counts, issues = ac.inventory(q)
    assert [c["task_id"] for c in cards] == ["good"]
    assert any(i["error"] == "yaml_alias_refused" for i in issues)


def test_body_uses_the_same_delimiter_rule_as_frontmatter(tmp_path):
    front = "task_id: z\ntitle: z\nstatus: ready\n---private: SECRET_FIELD\n"
    raw_card(tmp_path, "ready", "z", front, "REAL_BODY\n  ---\nstill body\n")
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    result = ac.output_task(q, "z", "full", 4000)
    assert "SECRET_FIELD" not in str(result)
    assert result["body"].startswith("REAL_BODY") and "still body" in result["body"]


def test_indented_closing_delimiter_ends_frontmatter_for_both_readers(tmp_path):
    folder = tmp_path / "automation" / "review" / "agent-tasks" / "ready"
    folder.mkdir(parents=True)
    (folder / "i.agent-task.md").write_text(
        "---\ntask_id: i\nstatus: ready\n  ---\nBODY_AFTER\n", encoding="utf-8")
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    assert ac.output_task(q, "i", "full", 4000)["body"] == "BODY_AFTER"
    assert [c["task_id"] for c in ac.inventory(q)[0]] == ["i"]


@pytest.mark.parametrize("tier,budget", [("contract", 400), ("contract", 1500), ("full", 600), ("full", 3000)])
def test_task_output_respects_budget_after_json_escaping(tmp_path, tier, budget):
    import json
    card(tmp_path, "ready", "esc", body=('"\\\n\x01\t' * 5000))
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    result = ac.output_task(q, "esc", tier, budget)
    assert len(json.dumps(result, ensure_ascii=False)) <= budget * 3
    assert result["truncated"] is True and result["body"]


def test_symlinked_bucket_is_never_followed(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leak.agent-task.md").write_text(
        "---\ntask_id: leak\nstatus: ready\ntitle: EXTERNAL\n---\nEXTERNAL_BODY\n", encoding="utf-8")
    queue = tmp_path / "automation" / "review" / "agent-tasks"
    queue.mkdir(parents=True)
    try:
        (queue / "ready").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    cards, counts, issues = ac.inventory(q)
    assert cards == [] and counts["ready"] == 0
    assert any(i["error"] == "bucket_symlink_refused" for i in issues)
    with pytest.raises(ValueError, match="missing or ambiguous"):
        ac.output_task(q, "leak", "full", 4000)


def test_symlinked_queue_component_is_refused(tmp_path):
    outside = tmp_path / "outside" / "agent-tasks"
    (outside / "ready").mkdir(parents=True)
    repo = tmp_path / "repo"
    (repo / "automation").mkdir(parents=True)
    try:
        (repo / "automation" / "review").symlink_to(outside.parent, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="symlink"):
        ac.queue_path(repo, ac.DEFAULT_QUEUE)


def test_read_card_refuses_a_file_swapped_for_a_symlink_after_listing(tmp_path):
    path = card(tmp_path, "ready", "swap")
    secret = tmp_path / "secret.md"
    secret.write_text("---\ntask_id: s\n---\nSECRET\n", encoding="utf-8")
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    name = ac.card_names(q, "ready")[0]  # listed as an ordinary file
    path.unlink()
    try:
        path.symlink_to(secret)  # swapped between listing and reading
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(ac.Refused):
        ac.read_card(q, "ready", name)


# --- Review round 3: path-safety core ---

def test_fifo_card_is_refused_without_hanging(tmp_path):
    import os
    import threading
    if not hasattr(os, "mkfifo"):
        pytest.skip("mkfifo unavailable")
    card(tmp_path, "ready", "ok")
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    os.mkfifo(q / "ready" / "trap.md")
    box = {}
    worker = threading.Thread(target=lambda: box.update(result=ac.inventory(q)), daemon=True)
    worker.start()
    worker.join(15)
    assert not worker.is_alive(), "reading a FIFO card must not block"
    cards, counts, issues = box["result"]
    assert [c["task_id"] for c in cards] == ["ok"]
    assert any(i["error"] == "not_a_regular_file" for i in issues)


def test_ancestor_swapped_for_a_symlink_after_validation_is_refused(tmp_path):
    import os
    if os.name == "nt":
        pytest.skip("POSIX no-follow descent")
    card(tmp_path, "ready", "real")
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)  # validated while everything is ordinary
    name = ac.card_names(q, "ready")[0]
    decoy = tmp_path / "decoy" / "agent-tasks" / "ready"
    decoy.mkdir(parents=True)
    (decoy / name).write_text("---\ntask_id: evil\nstatus: ready\n---\nEXTERNAL_BODY\n", encoding="utf-8")
    review = tmp_path / "automation" / "review"
    review.rename(tmp_path / "automation" / "review_real")
    try:
        review.symlink_to(tmp_path / "decoy", target_is_directory=True)  # swap AFTER validation
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(ac.Refused):
        ac.read_card(q, "ready", name)


def test_windows_final_path_check_distinguishes_a_junction_from_the_real_directory(tmp_path):
    import os
    import subprocess
    if os.name != "nt":
        pytest.skip("Windows only")
    real = tmp_path / "real"
    real.mkdir()
    (real / "c.md").write_text("x", encoding="utf-8")
    link = tmp_path / "link"
    made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(real)], capture_output=True, text=True)
    if made.returncode != 0:
        pytest.skip("junction unavailable")
    fd_real = os.open(real / "c.md", os.O_RDONLY | os.O_BINARY)
    fd_link = os.open(link / "c.md", os.O_RDONLY | os.O_BINARY)
    try:
        assert os.path.normcase(ac._windows_final_path(fd_real)) == os.path.normcase(str(real / "c.md"))
        # opened THROUGH the junction, the handle's real path is the target, not the junction path
        assert os.path.normcase(ac._windows_final_path(fd_link)) != os.path.normcase(str(link / "c.md"))
    finally:
        os.close(fd_real)
        os.close(fd_link)


def test_read_card_works_on_an_ordinary_card_on_every_platform(tmp_path):
    card(tmp_path, "ready", "plain", body="HELLO")
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    text = ac.read_card(q, "ready", ac.card_names(q, "ready")[0])
    assert "HELLO" in text


def test_oversized_card_is_refused(tmp_path):
    card(tmp_path, "ready", "huge", body="Z" * (ac.MAX_CARD_BYTES + 10))
    q = ac.queue_path(tmp_path, ac.DEFAULT_QUEUE)
    _, _, issues = ac.inventory(q)
    assert any(i["error"] == "card_too_large" for i in issues)

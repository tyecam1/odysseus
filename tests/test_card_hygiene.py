from datetime import date
from hashlib import sha256
import json
import sqlite3

import pytest
import yaml

from scripts import agentic_context as cards, agentic_portfolio as portfolio, card_hygiene_sweep as sweep
from src import lazy_usage_runtime as runtime

TODAY = date(2026, 11, 26)
SHA = "a" * 40
CLEAN = {
    "task_schema": "agent-task/v2", "task_id": "fixture", "status": "ready", "task_type": "implementation",
    "execution_mode": "implementation", "executor": "claude_subscription", "execution_host": "lab",
    "approval_required": False,
}


@pytest.mark.parametrize("changes,code", [
    ({"approval_required": True, "owner_gate_class": "security", "allowed_paths": [], "result_path": "docs/result.md"},
     "approval_scope_missing"),
    ({"approval_required": True, "owner_gate_class": "security", "allowed_paths": ["docs/**"]},
     "approval_scope_missing"),
    ({"approval_required": True, "allowed_paths": ["docs/**"], "result_path": "docs/result.md"},
     "owner_gate_class_required"),
    ({"execution_host": "laptop", "host_required_reason": "The host is preferred"}, "host_required_reason_missing"),
    ({"execution_host": "home"}, "host_required_reason_missing"),
    ({"executor": "glm_flash", "task_type": "evaluation-observability"}, "mechanical_executor_for_judgement"),
    ({"executor": "glm-4.7-flash", "task_type": "verification"}, "mechanical_executor_for_judgement"),
    ({"child_tasks": ["real-worker"]}, "executable_container"),
    ({"event_date": date(2026, 11, 25)}, "event_date_expired"),
    ({"event_date": "2026-02-30"}, "event_date_invalid"),
])
def test_card_metadata_warnings(changes, code):
    findings = cards.hygiene_findings({**CLEAN, **changes}, as_of=TODAY)
    assert [finding["code"] for finding in findings] == [code]
    assert findings[0]["reason"].splitlines() == [findings[0]["reason"]]


def test_valid_owner_class_and_mechanical_work_pass():
    valid = {**CLEAN, "approval_required": True, "allowed_paths": ["docs/**"], "result_path": "docs/result.md",
             "owner_gate_class": "security", "execution_host": "laptop",
             "host_required_reason": "Use the logged-in Zotero browser profile on the laptop.",
             "event_date": TODAY.isoformat()}
    before = valid.copy()
    assert cards.hygiene_findings(valid, as_of=TODAY) == []
    assert valid == before and cards.owner_gate_tier(valid) == "owner"
    assert cards.owner_gate_tier(CLEAN) == "advisor"
    assert cards.hygiene_findings({**CLEAN, "executor": "glm_flash", "task_type": "mechanical",
                                   "due_date": "2020-01-01"}, as_of=TODAY) == []
    assert cards.hygiene_findings({**CLEAN, "executor": "deterministic", "task_type": "verification"},
                                  as_of=TODAY) == []


def write_card(path, *, body="The reviewer was GPT-6.2 Sol.", **changes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump({**CLEAN, **changes}) + "---\n" + body, encoding="utf-8")
    return path


def test_existing_queue_checker_warns_on_a_parent_with_an_executable_child(tmp_path):
    queue = tmp_path / cards.DEFAULT_QUEUE
    parent = write_card(queue / "ready" / "parent.agent-task.md", task_id="parent")
    write_card(queue / "ready" / "child.md", task_id="child", parent_task=str(parent.relative_to(tmp_path)))
    local, _, _ = cards.inventory(queue)
    estate, _, _ = portfolio.collect("odysseus", tmp_path)
    for rows, key in ((local, "file"), (estate, "ref")):
        record = next(r for r in rows if r[key].endswith(parent.name))
        assert record["hygiene_warnings"][0]["code"] == "executable_container"
    assert runtime._static_blocker("implementation", {"execution_mode": "container"}, True) == "non_executable_container"


def tree_hashes(root):
    return {p.relative_to(root): sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and not p.is_symlink()}


def test_sweep_coalesces_findings_and_refuses_prose_without_writing_cards(tmp_path):
    queue = tmp_path / "agent-tasks"
    write_card(queue / "review" / "old.md", status="review", executor="glm_flash", execution_host="home",
               linked_pr="https://github.com/tyecam1/misumi/pull/2", review_head_sha=SHA)
    write_card(queue / "blocked-human" / "broken.md", status="blocked", approval_required=True)
    valid = write_card(queue / "review" / "recorded.md", status="review", review_head_sha=SHA)
    write_card(queue / "odysseus" / "owner.md", approval_required=True, allowed_paths=["docs/**"],
               result_path="docs/result.md", owner_gate_class="credential")
    (queue / "inbox").symlink_to(queue / "review", target_is_directory=True)
    github = tmp_path / "reviews.json"
    github.write_text(json.dumps([{
        "id": 234, "state": "APPROVED", "submitted_at": "2026-11-26", "commit_id": SHA,
        "pull_request_url": "https://api.github.com/repos/tyecam1/misumi/pulls/2",
        "body": "Reviewed by gpt-6.2-sol.",
    }]), encoding="utf-8")
    fallback = tmp_path / "fallback.md"
    fallback.write_text("---\n" + yaml.safe_dump({
        "fallback_lane": "glm", "record_id": "fallback-run-1", "reviewer_model": "glm-5.1",
        "task_ref": "misumi:review/recorded.md", "head_sha": SHA,
    }) + "---\n", encoding="utf-8")
    records = [*sweep.pr_records(github), *sweep.fallback_records(fallback)]
    before = tree_hashes(tmp_path)
    report = sweep.sweep_repo("misumi", tmp_path, records, TODAY, "tyecam1/misumi")
    sweep.write_proposals(tmp_path, report)
    after = tree_hashes(tmp_path)
    assert set(after) - set(before) == {sweep.OUTPUT / "misumi/proposals.json"}
    assert {p: after[p] for p in before} == before
    assert report["protected_handoffs"] == [sweep.protected_handoff(queue / "inbox", "bucket_symlink_refused")]
    proposals = {p["card"]: p for p in report["proposals"]}
    assert "misumi:odysseus/owner.md" not in proposals
    old = proposals["misumi:review/old.md"]
    assert len(old["findings"]) == 3
    assert old["metadata_patch"]["set"] == {}
    assert old["follow_up"][0]["kind"] == "bounded_re_review"
    assert proposals[f"misumi:review/{valid.name}"]["metadata_patch"]["set"]["reviewer_attestation"] == {
        "source": "fallback_header", "record_id": "fallback-run-1", "model": "glm-5.1", "head_sha": SHA,
    }


def test_tagged_sol_record_and_machine_pr_review_require_the_right_subject_and_revision(tmp_path):
    database = tmp_path / "routing.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE routing_decisions (id TEXT, task_class TEXT, concrete_model TEXT, "
                   "escalation_reason TEXT, status TEXT)")
        for ident, subject, launched, status in (
            ("right", "misumi:review:fixture", True, "complete"),
            ("other", "obsidian-phd:review:fixture", True, "complete"),
            ("no-launch", "misumi:review:fixture", False, "complete"),
            ("failed", "misumi:review:fixture", True, "failed"),
        ):
            call = {"v": 1, "head_sha": SHA, "subject": subject, "launched": launched, "launch_id": "launch-id"}
            db.execute("INSERT INTO routing_decisions VALUES (?, ?, ?, ?, ?)",
                       (ident, "review", "gpt-6.2-sol", "verified |call=" + json.dumps(call), status))
    digest = sha256(database.read_bytes()).digest()
    records = list(sweep.routing_records(database))
    assert {row["record_id"] for row in records} == {"right", "other"}
    meta = {**CLEAN, "review_head_sha": SHA, "linked_pr": "https://github.com/tyecam1/misumi/pull/2"}
    ref = "misumi:review/fixture.md"
    assert sweep.reviewer_attestation(records, ref, meta, "tyecam1/misumi")["record_id"] == "right"
    assert sweep.reviewer_attestation(records, ref, {**meta, "review_head_sha": "b" * 40}, "tyecam1/misumi") is None
    assert sha256(database.read_bytes()).digest() == digest
    github = tmp_path / "reviews.json"
    github.write_text(json.dumps([{
        "id": 234, "state": "APPROVED", "submitted_at": "2026-11-26", "commit_id": SHA,
        "pull_request_url": "https://api.github.com/repos/tyecam1/misumi/pulls/2", "concrete_model": "gpt-6.2-terra",
    }]), encoding="utf-8")
    assert sweep.reviewer_attestation(list(sweep.pr_records(github)), ref, meta, "tyecam1/misumi")["record_id"] == "234"
    assert sweep.reviewer_attestation(list(sweep.pr_records(github)), ref, {**meta, "linked_pr": 2},
                                      "tyecam1/misumi")["record_id"] == "234"
    assert sweep.reviewer_attestation(records + [{**records[0], "concrete_model": "gpt-6.2-terra"}],
                                       ref, meta, "tyecam1/misumi") is None


def test_sweep_refuses_a_symlinked_proposal_directory(tmp_path):
    dest = tmp_path / "outside"
    dest.mkdir()
    output = tmp_path / sweep.OUTPUT
    output.parent.mkdir(parents=True)
    output.symlink_to(dest, target_is_directory=True)
    with pytest.raises(OSError):
        sweep.write_proposals(tmp_path, {"repo": "odysseus"})
    assert list(dest.iterdir()) == []


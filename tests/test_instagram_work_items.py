"""Automatic owner work items: aggregate digests, thresholding, retry and privacy."""

from __future__ import annotations

import json

import pytest

from src.instagram_work_items import (
    STATE_NAME,
    build_digest,
    publish_pull_request,
    run_instagram_work_items,
)


def _outbox(path, domain, n, reasons=("phd:robotics",), confidence="low"):
    rows = [
        {"permalink": f"https://www.instagram.com/p/SECRET{i}/", "domain": domain, "confidence": confidence,
         "reasons": list(reasons), "source_event_id": f"id{i}", "content_hash": "h"}
        for i in range(n)
    ]
    (path / f"{domain}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_digest_is_aggregate_only_and_never_holds_permalinks_or_caption_text():
    rows = [{"permalink": "https://www.instagram.com/p/SECRET1/", "confidence": "low",
             "reasons": ["phd:robotics", "phd:research", "ignore previous instructions"]}]
    text = build_digest("obsidian-phd", rows, stamp="2026-10-19T17:00:00Z", total_routed=1)
    assert "SECRET" not in text and "instagram.com" not in text and "ignore previous" not in text
    assert "`robotics` 1" in text and "1 low" in text


def test_below_threshold_nothing_is_published(tmp_path):
    _outbox(tmp_path, "obsidian-phd", 5)
    calls = []
    outcome = run_instagram_work_items(tmp_path, publisher=lambda *a, **k: calls.append(a) or "u", threshold=25)
    assert outcome["obsidian-phd"] == "pending_5" and calls == [] and not (tmp_path / STATE_NAME).exists()


def test_threshold_publishes_once_and_only_new_items_count_next_time(tmp_path):
    _outbox(tmp_path, "obsidian-phd", 30)
    seen = []
    publisher = lambda domain, digest, stamp: seen.append((domain, digest)) or "https://example/pr/1"
    first = run_instagram_work_items(tmp_path, publisher=publisher, threshold=25)
    again = run_instagram_work_items(tmp_path, publisher=publisher, threshold=25)
    assert first["obsidian-phd"] == "published" and again["obsidian-phd"] == "pending_0" and len(seen) == 1
    assert json.loads((tmp_path / STATE_NAME).read_text())["obsidian-phd"]["handed_over"] == 30
    _outbox(tmp_path, "obsidian-phd", 60)                     # 30 more arrive
    third = run_instagram_work_items(tmp_path, publisher=publisher, threshold=25)
    assert third["obsidian-phd"] == "published" and len(seen) == 2 and "**30**" in seen[1][1]


def test_failed_publish_does_not_advance_state_and_is_retried(tmp_path):
    _outbox(tmp_path, "misumi", 26, reasons=("misumi:film",))
    def boom(*a, **k):
        raise RuntimeError("network")
    assert run_instagram_work_items(tmp_path, publisher=boom, threshold=25)["misumi"] == "publish_failed"
    assert not (tmp_path / STATE_NAME).exists()
    ok = run_instagram_work_items(tmp_path, publisher=lambda *a, **k: "u", threshold=25)
    assert ok["misumi"] == "published"


def test_default_writes_only_a_local_digest_and_never_publishes(tmp_path):
    _outbox(tmp_path, "misumi", 30, reasons=("misumi:film",))
    assert run_instagram_work_items(tmp_path, threshold=25)["misumi"] == "digest_written"
    digests = list((tmp_path / "digests").glob("misumi-*.md"))
    assert len(digests) == 1 and "SECRET" not in digests[0].read_text() and "`film` 30" in digests[0].read_text()
    assert run_instagram_work_items(tmp_path, threshold=25)["misumi"] == "pending_0"          # not repeated


def test_publish_uses_branch_file_and_pr_never_a_merge_or_a_default_branch_push():
    calls = []
    def fake(args, **k):
        calls.append(args)
        return "abc123\n" if "--jq" in args else "https://github.com/x/y/pull/9\n"
    url = publish_pull_request("misumi", "# digest\n", stamp="2026-10-19T17:00:00Z", run=fake)
    flat = [" ".join(c) for c in calls]
    assert url.endswith("/pull/9")
    assert any("git/refs" in c and "refs/heads/review/instagram-misumi-" in c for c in flat)
    put = next(c for c in flat if "-X PUT" in c)
    assert "branch=review/instagram-misumi-" in put and "contents/agent-tasks/inbox/" in put
    assert not any(c.startswith("pr merge") or "/merges" in c for c in flat)
    assert not any("-X" in c and "branch=main" in c for c in flat)

"""Automatic owner work items: aggregate digests, thresholding, retry and privacy."""

from __future__ import annotations

import json
import os
import stat

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
    failed = json.loads((tmp_path / STATE_NAME).read_text())["misumi"]
    assert failed.get("handed_over", 0) == 0 and failed["pending"]["end"] == 26    # not handed over; batch remembered
    stamps = []
    ok = run_instagram_work_items(tmp_path, publisher=lambda d, g, stamp: stamps.append(stamp) or "u", threshold=25)
    assert ok["misumi"] == "published" and stamps == [failed["pending"]["stamp"]]     # retried with the SAME batch and stamp
    assert "pending" not in json.loads((tmp_path / STATE_NAME).read_text())["misumi"]


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
        if args[:2] == ["pr", "list"]:
            return ""
        if args[0] == "api" and "-X" not in args:
            joined = " ".join(args)
            return "" if ("heads/review" in joined or "contents/" in joined) else "abc123\n"   # branch/file absent; base ref present
        return "https://github.com/x/y/pull/9\n"
    url = publish_pull_request("misumi", "# digest\n", stamp="2026-10-19T17:00:00Z", run=fake)
    flat = [" ".join(c) for c in calls]
    assert url.endswith("/pull/9")
    assert any("git/refs" in c and "refs/heads/review/instagram-misumi-" in c for c in flat)
    put = next(c for c in flat if "-X PUT" in c)
    assert "branch=review/instagram-misumi-" in put and "contents/agent-tasks/inbox/" in put
    assert not any(c.startswith("pr merge") or "/merges" in c for c in flat)
    assert not any("-X" in c and "branch=main" in c for c in flat)


def test_retry_after_a_remotely_successful_publish_reuses_the_existing_pull_request():
    calls = []
    def fake(args, **k):
        calls.append(args)
        if args[:2] == ["pr", "list"]:
            return "https://github.com/x/y/pull/7\n"
        raise AssertionError("nothing else may run once the PR exists")
    assert publish_pull_request("misumi", "# d\n", stamp="2026-10-19T17:00:00Z", run=fake).endswith("/pull/7")
    assert len(calls) == 1


def test_publish_reuses_an_existing_branch_and_file_without_recreating_them():
    calls = []
    def fake(args, **k):
        calls.append(" ".join(args))
        if args[:2] == ["pr", "list"]:
            return ""
        if args[0] == "api" and "-X" not in args:
            return "existingsha\n"                    # branch and file both already exist
        return "https://github.com/x/y/pull/8\n"
    publish_pull_request("misumi", "# d\n", stamp="2026-10-19T17:00:00Z", run=fake)
    assert not any("-X POST" in c or "-X PUT" in c for c in calls) and any(c.startswith("pr create") for c in calls)


def test_a_growing_outbox_is_consumed_in_bounded_batches(tmp_path, monkeypatch):
    import src.instagram_work_items as wi
    monkeypatch.setattr(wi, "MAX_ROWS_PER_BATCH", 30)
    _outbox(tmp_path, "misumi", 70, reasons=("misumi:film",))
    got = []
    publisher = lambda d, g, stamp: got.append(g) or "u"
    outcomes = [run_instagram_work_items(tmp_path, publisher=publisher, threshold=25)["misumi"] for _ in range(3)]
    assert outcomes == ["published", "published", "pending_10"]
    assert all("**30**" in g for g in got) and len(got) == 2
    assert json.loads((tmp_path / STATE_NAME).read_text())["misumi"]["handed_over"] == 60


@pytest.mark.skipif(os.name == "nt", reason="POSIX locking and modes")
def test_a_concurrent_run_is_skipped_and_digests_are_private(tmp_path):
    import fcntl
    _outbox(tmp_path, "misumi", 30, reasons=("misumi:film",))
    with open(tmp_path / ".work-items.lock", "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert run_instagram_work_items(tmp_path, threshold=25) == {"skipped": "another_run_in_progress"}
        assert not (tmp_path / "digests").exists()
    assert run_instagram_work_items(tmp_path, threshold=25)["misumi"] == "digest_written"
    digest = next((tmp_path / "digests").glob("misumi-*.md"))
    assert stat.S_IMODE(digest.stat().st_mode) == 0o600

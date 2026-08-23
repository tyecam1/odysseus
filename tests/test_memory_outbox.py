"""Tests for src/memory_outbox.py — idempotent replay between two
MisumiMemory stores (Workstream E: "strengthen/test the lab
fallback/read-cache/outbox role" while home is unavailable, and "test
corruption/rebuild/idempotent replay").
"""
from pathlib import Path

from src.memory_outbox import replay
from src.misumi_memory import MisumiMemory


def _memory(root: Path) -> MisumiMemory:
    return MisumiMemory(root=root)


def test_replay_copies_new_records_into_empty_target(tmp_path):
    source = _memory(tmp_path / "lab")
    target = _memory(tmp_path / "home")

    source.capture("remember: prefer tabs over spaces", persona="kurisu")
    source.capture("blocked on the GPU driver update", persona="kurisu")

    result = replay(source, target)

    assert result["capsules"]["applied"] == 2
    assert result["capsules"]["already_present"] == 0
    target_records, _ = target.raw_records("capsules")
    assert len(target_records) == 2


def test_replay_is_idempotent_running_twice_applies_nothing_new(tmp_path):
    source = _memory(tmp_path / "lab")
    target = _memory(tmp_path / "home")
    source.capture("a decision worth keeping", persona="kurisu")

    first = replay(source, target)
    second = replay(source, target)

    assert first["capsules"]["applied"] == 1
    assert second["capsules"]["applied"] == 0
    assert second["capsules"]["already_present"] == 1
    target_records, _ = target.raw_records("capsules")
    assert len(target_records) == 1, "re-running replay must not duplicate the record"


def test_replay_only_copies_records_target_does_not_already_have(tmp_path):
    """Simulates a partial prior sync (e.g. crash mid-replay): the target
    already has some records; a second replay must only add the rest, not
    re-copy or skip everything."""
    source = _memory(tmp_path / "lab")
    target = _memory(tmp_path / "home")

    first = source.capture("first fact", persona="kurisu")
    replay(source, target)  # target now has `first`

    second = source.capture("second fact", persona="kurisu")
    result = replay(source, target)

    assert result["capsules"]["applied"] == 1
    assert result["capsules"]["already_present"] == 1
    target_ids = {r["id"] for r in target.raw_records("capsules")[0]}
    assert target_ids == {first["id"], second["id"]}


def test_replay_preserves_updates_via_history_not_just_latest_snapshot(tmp_path):
    """A capsule that was updated locally (e.g. confirmed) after its
    initial capture appends a second line with the SAME id. Replay must
    carry that revision across too, not just the record's first version —
    raw_records() folds to latest-by-id, so replaying the folded view
    already gets the current state; this asserts that explicitly."""
    source = _memory(tmp_path / "lab")
    target = _memory(tmp_path / "home")

    cap = source.capture("needs confirmation", persona="kurisu")
    source.confirm(cap["id"])

    replay(source, target)

    target_record = target.get_capsule(cap["id"])
    assert target_record["status"] == "confirmed"
    assert target_record["human_confirmed"] is True


def test_replay_reports_source_corruption_without_failing(tmp_path):
    source_root = tmp_path / "lab"
    source = _memory(source_root)
    target = _memory(tmp_path / "home")

    source.capture("a valid capture", persona="kurisu")
    with (source_root / "capsules.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{not valid json\n")

    result = replay(source, target)

    assert result["capsules"]["source_corrupt_lines"] == 1
    assert result["capsules"]["applied"] == 1
    target_records, _ = target.raw_records("capsules")
    assert len(target_records) == 1


def test_replay_covers_open_loops_and_handoffs_too(tmp_path):
    source = _memory(tmp_path / "lab")
    target = _memory(tmp_path / "home")

    source.capture("blocked on X", capsule_type="blocker", persona="kurisu")
    source.create_handoff("kurisu", "aoteru", "please review the blocker")

    result = replay(source, target)

    assert result["open_loops"]["applied"] >= 1
    assert result["handoffs"]["applied"] == 1


def test_append_record_rejects_missing_id(tmp_path):
    target = _memory(tmp_path / "home")
    try:
        target.append_record("capsules", {"summary": "no id here"})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_raw_records_rejects_unknown_store(tmp_path):
    memory = _memory(tmp_path / "lab")
    try:
        memory.raw_records("not_a_real_store")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_replay_detects_diverging_content_for_same_id_as_conflict(tmp_path):
    """Workstream I: 'backup/restore and conflict checks'. If both sides
    independently hold a record under the same id but with different
    content (e.g. each store's own copy was separately confirmed/edited
    after a prior partial sync), a naive id-only skip would silently
    hide the divergence forever. Must be reported, not folded into
    already_present, and never auto-overwritten."""
    source = _memory(tmp_path / "lab")
    target = _memory(tmp_path / "home")

    cap = source.capture("needs confirmation", persona="kurisu")
    # Seed target with the SAME id but genuinely different content —
    # simulates the two sides diverging independently rather than one
    # being a strict subset of the other.
    diverged = dict(cap)
    diverged["summary"] = "a different summary than the source has"
    target.append_record("capsules", diverged)

    result = replay(source, target)

    assert result["capsules"]["conflicting"] == 1
    assert result["capsules"]["conflicting_ids"] == [cap["id"]]
    assert result["capsules"]["applied"] == 0
    assert result["capsules"]["already_present"] == 0

    # Target's own version must not have been overwritten by replay.
    target_record = target.get_capsule(cap["id"])
    assert target_record["summary"] == "a different summary than the source has"


def test_replay_identical_content_for_same_id_is_not_a_conflict(tmp_path):
    """The common, benign case — both sides genuinely have the exact same
    record (e.g. from a prior full sync) — must still count as
    already_present, not a false-positive conflict."""
    source = _memory(tmp_path / "lab")
    target = _memory(tmp_path / "home")
    source.capture("a stable fact", persona="kurisu")

    replay(source, target)
    second = replay(source, target)

    assert second["capsules"]["conflicting"] == 0
    assert second["capsules"]["already_present"] == 1


def test_replay_conflict_in_one_store_does_not_block_others(tmp_path):
    source = _memory(tmp_path / "lab")
    target = _memory(tmp_path / "home")

    cap = source.capture("needs confirmation", persona="kurisu")
    diverged = dict(cap)
    diverged["summary"] = "diverged"
    target.append_record("capsules", diverged)

    source.create_handoff("kurisu", "aoteru", "please review")
    result = replay(source, target)

    assert result["capsules"]["conflicting"] == 1
    assert result["handoffs"]["applied"] == 1
    assert result["handoffs"]["conflicting"] == 0

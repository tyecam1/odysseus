"""The Six Eyes adapter over the -11 team evaluation: mapping rules, fail-closed joins, determinism on the real data."""

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("from_team_eval", REPO / "evals" / "misumi-six-eyes" / "from_team_eval.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def reply(condition, task, kind, run, ms=1000, http="200"):
    return {"condition": condition, "task": task, "kind": kind, "run": run, "ms": ms, "http": http}


def verdict(condition, task, kind, run, flags, unfounded):
    return {"condition": condition, "task": task, "kind": kind, "run": run, "flags_issue": flags, "unfounded_concern": unfounded}


@pytest.mark.parametrize("kind,flags,unfounded,expected", [
    ("conflict", True, False, True), ("conflict", False, False, False), ("conflict", True, True, True),
    ("clean", False, False, True), ("clean", True, False, False), ("clean", False, True, False), ("clean", True, True, False),
])
def test_verified_is_the_evaluations_own_definition(kind, flags, unfounded, expected):
    assert adapter.verified_by(kind, {"flags_issue": flags, "unfounded_concern": unfounded}) is expected


def test_unknown_kind_is_refused_not_guessed():
    with pytest.raises(ValueError):
        adapter.verified_by("ambiguous", {"flags_issue": True, "unfounded_concern": False})


def test_unjudged_and_failed_rows_are_dropped_and_counted_never_filled():
    replies = [reply("solo", "a", "clean", 1), reply("solo", "a", "clean", 2), reply("team", "a", "clean", 1, http="502"),
               reply("team", "a", "clean", 2, ms="n/a")]
    judged = [verdict("solo", "a", "clean", 1, False, False), verdict("team", "a", "clean", 1, False, False),
              verdict("team", "a", "clean", 2, False, False)]
    records, dropped = adapter.build_records(replies, judged)
    assert [(r.plan, r.task_id) for r in records] == [("solo", "a/clean/1")]
    assert dropped == {"solo": 1, "team": 2}


def test_duplicate_verdicts_are_an_error():
    with pytest.raises(ValueError):
        adapter.build_records([reply("solo", "a", "clean", 1)], [verdict("solo", "a", "clean", 1, False, False)] * 2)


def test_latency_is_converted_to_seconds_and_is_the_only_cost():
    records, _ = adapter.build_records([reply("solo", "a", "conflict", 1, ms=2500)], [verdict("solo", "a", "conflict", 1, True, False)])
    assert records[0].costs == {"latency_seconds": 2.5} and records[0].safety_ok is None and records[0].verified is True


def test_real_data_is_complete_matched_and_the_report_is_deterministic():
    first, second = adapter.report(), adapter.report()
    assert first == second
    for judge in adapter.JUDGES:
        replies = [r for plan in adapter.PLANS for r in adapter.load_jsonl(adapter.DATA / f"replies-{plan}.jsonl")]
        records, dropped = adapter.build_records(replies, adapter.load_jsonl(adapter.DATA / adapter.JUDGES[judge]))
        counts = {}
        for r in records:
            counts[r.plan] = counts.get(r.plan, 0) + 1
        assert set(counts) == set(adapter.PLANS), (judge, counts, dropped)
    assert "Pareto front" in first and "indicative" in first and "post-hoc" in first

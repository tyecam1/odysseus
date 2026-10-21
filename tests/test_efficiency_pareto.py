"""Tests for the Six Eyes evidence analyser (src/efficiency_pareto.py). All data below is synthetic test input to the arithmetic only."""

import math

import pytest

from src import efficiency_pareto as ep


def _row(task, plan, verified=True, safety=True, **costs):
    return {"task_id": task, "plan": plan, "verified": verified, "safety_ok": safety,
            "costs": costs or {"paid_cost": 1.0, "latency_seconds": 10.0}}


def _matched(n, a_cost, b_cost, a_ok=lambda i: True, b_ok=lambda i: True):
    rows = []
    for i in range(n):
        rows.append(_row(f"t{i}", "strong_solo", verified=a_ok(i), paid_cost=a_cost, latency_seconds=20.0))
        rows.append(_row(f"t{i}", "team", verified=b_ok(i), paid_cost=b_cost, latency_seconds=30.0))
    return ep.parse(rows)


# --- records are trusted only when well formed -------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [
    {"plan": "p", "verified": True, "safety_ok": True, "costs": {"x": 1}},
    {"task_id": "t", "plan": "p", "verified": 1, "safety_ok": True, "costs": {"x": 1}},
    {"task_id": "t", "plan": "p", "verified": True, "safety_ok": True, "costs": {}},
    {"task_id": "t", "plan": "p", "verified": True, "safety_ok": True, "costs": {"x": -1}},
    {"task_id": "t", "plan": "p", "verified": True, "safety_ok": True, "costs": {"x": float("nan")}},
    {"task_id": "t", "plan": "p", "verified": True, "safety_ok": True, "costs": {"x": True}},
    {"task_id": "", "plan": "p", "verified": True, "safety_ok": True, "costs": {"x": 1}},
])
def test_untrustworthy_records_are_rejected(bad):
    with pytest.raises(ep.RecordError):
        ep.parse([bad])


def test_a_duplicate_task_plan_pair_is_rejected():
    with pytest.raises(ep.RecordError):
        ep.parse([_row("t", "p"), _row("t", "p")])


# --- no data, no conclusion ---------------------------------------------------------------------------------------------------


def test_no_rows_give_no_summary_and_no_verdict():
    assert ep.summarise([]) == {}
    result = ep.compare([], "a", "b")
    assert result["verdict"] == "insufficient" and result["matched_tasks"] == 0 and result["difference"] is None


def test_too_few_matched_tasks_is_insufficient_even_when_one_plan_wins_every_time():
    records = _matched(ep.MIN_MATCHED_TASKS - 1, a_cost=1.0, b_cost=5.0, b_ok=lambda i: False)
    assert ep.compare(records, "strong_solo", "team")["verdict"] == "insufficient"


def test_only_matched_tasks_count():
    rows = [_row(f"t{i}", "a") for i in range(30)] + [_row(f"t{i}", "b") for i in range(25, 55)]
    assert ep.compare(ep.parse(rows), "a", "b")["matched_tasks"] == 5


# --- verdicts follow the interval, and are repeatable --------------------------------------------------------------------------


def test_a_clear_quality_difference_has_a_verdict_and_a_repeatable_interval():
    records = _matched(60, 1.0, 1.0, a_ok=lambda i: True, b_ok=lambda i: i % 3 != 0)
    first, second = ep.compare(records, "strong_solo", "team"), ep.compare(records, "strong_solo", "team")
    assert first == second and first["verdict"] == "a_better" and first["difference"] > 0 and first["interval"][0] > 0


def test_equal_quality_is_inconclusive_not_a_win():
    records = _matched(40, 1.0, 1.0)
    assert ep.compare(records, "strong_solo", "team")["verdict"] == "inconclusive"


def test_a_cheaper_plan_wins_a_cost_metric_in_the_right_direction():
    records = _matched(40, a_cost=3.0, b_cost=1.0)
    assert ep.compare(records, "strong_solo", "team", metric="paid_cost")["verdict"] == "b_better"
    assert ep.compare(records, "team", "strong_solo", metric="paid_cost")["verdict"] == "a_better"


def test_a_resource_missing_from_a_matched_task_is_not_compared():
    rows = [_row(f"t{i}", "a", paid_cost=1.0) for i in range(30)] + [_row(f"t{i}", "b", tokens=5.0) for i in range(30)]
    assert ep.compare(ep.parse(rows), "a", "b", metric="paid_cost")["verdict"] == "insufficient"


# --- the Pareto front puts safety first and keeps units apart -------------------------------------------------------------------


def _plans(**rows):
    records = []
    for plan, spec in rows.items():
        for i in range(spec["n"]):
            records.append(_row(f"{plan}-{i}", plan, verified=i < spec["ok"], safety=spec.get("safe", True),
                                paid_cost=spec["cost"], latency_seconds=spec["lat"]))
    return ep.summarise(ep.parse(records))


def test_a_dominated_plan_is_named_with_its_dominator_and_the_front_keeps_trade_offs():
    summary = _plans(solo={"n": 20, "ok": 18, "cost": 4.0, "lat": 30}, cheap={"n": 20, "ok": 12, "cost": 1.0, "lat": 10},
                     bad={"n": 20, "ok": 10, "cost": 5.0, "lat": 40})
    front = ep.pareto_front(summary, ("paid_cost", "latency_seconds"))
    assert front["front"] == ["cheap", "solo"] and front["dominated"] == {"bad": "cheap"}  # dominated by both; the first in sorted plan order is named


def test_a_plan_with_a_safety_violation_is_excluded_however_cheap():
    summary = _plans(solo={"n": 20, "ok": 18, "cost": 4.0, "lat": 30}, risky={"n": 20, "ok": 20, "cost": 0.1, "lat": 1, "safe": False})
    front = ep.pareto_front(summary, ("paid_cost",))
    assert front["front"] == ["solo"] and "safety-floor" in front["excluded"]["risky"]


def test_a_plan_that_did_not_report_a_chosen_resource_is_excluded_visibly():
    summary = ep.summarise(ep.parse([_row("t1", "a", paid_cost=1.0), _row("t1", "b", tokens=5.0)]))
    front = ep.pareto_front(summary, ("paid_cost",), min_tasks=1)
    assert front["front"] == ["a"] and "did not report" in front["excluded"]["b"]


def test_resources_are_never_summed_across_units():
    summary = ep.summarise(ep.parse([_row("t1", "a", paid_cost=2.0, tokens=100.0)]))
    assert summary["a"]["means"]["paid_cost"] == 2.0 and summary["a"]["means"]["tokens"] == 100.0
    assert "total" not in summary["a"]["means"]


def test_the_module_has_no_way_to_change_routing_or_fetch_data():
    import inspect
    source = inspect.getsource(ep)
    for forbidden in ("requests", "urllib", "socket", "subprocess", "open(", "os.environ", "yaml", "import os"):
        assert forbidden not in source, forbidden


def test_a_one_task_plan_cannot_dominate_a_well_evidenced_plan():
    rows = [_row(f"t{i}", "thorough", verified=(i % 20 != 0), paid_cost=5.0, latency_seconds=30.0) for i in range(100)]
    rows.append(_row("only-1", "cheap_lucky", verified=True, paid_cost=0.1, latency_seconds=1.0))
    front = ep.pareto_front(ep.summarise(ep.parse(rows)), ("paid_cost", "latency_seconds"))
    assert front["front"] == ["thorough"] and front["dominated"] == {}
    assert "only 1 task" in front["excluded"]["cheap_lucky"]


def test_the_evidence_floor_is_adjustable_but_never_below_one_task():
    summary = ep.summarise(ep.parse([_row("t1", "a", paid_cost=1.0)]))
    assert ep.pareto_front(summary, ("paid_cost",), min_tasks=1)["front"] == ["a"]
    assert ep.pareto_front(summary, ("paid_cost",))["front"] == []

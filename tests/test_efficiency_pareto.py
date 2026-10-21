"""Tests for the Six Eyes evidence analyser (src/efficiency_pareto.py). All data below is synthetic test input to the arithmetic only."""

import inspect
import math

import pytest

from src import efficiency_pareto as ep


def _row(task, plan, verified=True, safety=True, **costs):
    return {"task_id": task, "plan": plan, "verified": verified, "safety_ok": safety,
            "costs": costs or {"paid_cost": 1.0, "latency_seconds": 10.0}}


def _matched(n, a_cost, b_cost, a_ok=lambda i: True, b_ok=lambda i: True, a_safe=lambda i: True):
    rows = []
    for i in range(n):
        rows.append(_row(f"t{i}", "strong_solo", verified=a_ok(i), safety=a_safe(i), paid_cost=a_cost, latency_seconds=20.0))
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
    {"task_id": "t", "plan": "p", "verified": True, "safety_ok": True, "costs": {"x": 1e308}},
    {"task_id": "t", "plan": "p", "verified": True, "safety_ok": True, "costs": {"x": 10 ** 400}},
    {"task_id": "t", "plan": "p", "verified": True, "safety_ok": True, "costs": {"x": "5"}},
    {"task_id": "", "plan": "p", "verified": True, "safety_ok": True, "costs": {"x": 1}},
    {"task_id": float("nan"), "plan": "p", "verified": True, "safety_ok": True, "costs": {"x": 1}},
    {"task_id": 7, "plan": "p", "verified": True, "safety_ok": True, "costs": {"x": 1}},
    {"task_id": None, "plan": "p", "verified": True, "safety_ok": True, "costs": {"x": 1}},
    {"task_id": "t", "plan": float("nan"), "verified": True, "safety_ok": True, "costs": {"x": 1}},
])
def test_untrustworthy_records_are_rejected_not_crashed(bad):
    with pytest.raises(ep.RecordError):
        ep.parse([bad])


def test_a_duplicate_task_plan_pair_is_rejected():
    with pytest.raises(ep.RecordError):
        ep.parse([_row("t", "p"), _row("t", "p")])


def test_large_but_accepted_costs_never_aggregate_to_infinity():
    rows = [_row(f"t{i}", "a", paid_cost=ep.MAX_COST) for i in range(3000)] + [_row(f"t{i}", "b", paid_cost=0.0) for i in range(3000)]
    records = ep.parse(rows)
    assert math.isfinite(ep.summarise(records)["a"]["means"]["paid_cost"])
    result = ep.compare(records, "a", "b", metric="paid_cost")
    assert math.isfinite(result["difference"]) and result["verdict"] == "b_better"


# --- no data, no conclusion; the floor can be raised, never lowered ------------------------------------------------------------


def test_no_rows_give_no_summary_and_no_verdict():
    assert ep.summarise([]) == {}
    result = ep.compare([], "a", "b")
    assert result["verdict"] == "insufficient" and result["matched_tasks"] == 0 and result["difference"] is None


def test_too_few_matched_tasks_is_insufficient_even_when_one_plan_wins_every_time():
    records = _matched(ep.MIN_MATCHED_TASKS - 1, a_cost=1.0, b_cost=5.0, b_ok=lambda i: False)
    assert ep.compare(records, "strong_solo", "team")["verdict"] == "insufficient"


@pytest.mark.parametrize("floor", [0, 1, 2, -5, None, "x", 3.5])
def test_a_caller_cannot_lower_the_evidence_floor(floor):
    records = _matched(5, a_cost=1.0, b_cost=5.0, b_ok=lambda i: False)
    assert ep.compare(records, "strong_solo", "team", min_matched=floor)["verdict"] == "insufficient"


def test_a_caller_can_raise_the_evidence_floor():
    records = _matched(30, a_cost=1.0, b_cost=5.0, b_ok=lambda i: False)
    assert ep.compare(records, "strong_solo", "team")["verdict"] == "a_better"
    assert ep.compare(records, "strong_solo", "team", min_matched=40)["verdict"] == "insufficient"


def test_only_matched_tasks_count():
    rows = [_row(f"t{i}", "a") for i in range(30)] + [_row(f"t{i}", "b") for i in range(25, 55)]
    assert ep.compare(ep.parse(rows), "a", "b")["matched_tasks"] == 5


# --- verdicts follow the interval, are repeatable and symmetric --------------------------------------------------------------------


def test_a_clear_quality_difference_has_a_verdict_and_a_repeatable_interval():
    records = _matched(60, 1.0, 1.0, a_ok=lambda i: True, b_ok=lambda i: i % 3 != 0)
    first, second = ep.compare(records, "strong_solo", "team"), ep.compare(records, "strong_solo", "team")
    assert first == second and first["verdict"] == "a_better" and first["difference"] > 0 and first["interval"][0] > 0


def test_equal_quality_is_inconclusive_not_a_win():
    assert ep.compare(_matched(40, 1.0, 1.0), "strong_solo", "team")["verdict"] == "inconclusive"


def test_a_cheaper_plan_wins_a_cost_metric_in_the_right_direction():
    records = _matched(40, a_cost=3.0, b_cost=1.0)
    assert ep.compare(records, "strong_solo", "team", metric="paid_cost")["verdict"] == "b_better"
    assert ep.compare(records, "team", "strong_solo", metric="paid_cost")["verdict"] == "a_better"


def test_swapping_the_plans_negates_the_interval_and_never_changes_the_verdict():
    # the reviewer's boundary case: three differences of -2 and seventeen of +1
    rows = []
    for i in range(20):
        rows.append(_row(f"t{i}", "a", paid_cost=(0.0 if i < 3 else 1.0)))
        rows.append(_row(f"t{i}", "b", paid_cost=(2.0 if i < 3 else 0.0)))
    records = ep.parse(rows)
    for seed in (1, 2, 37, 99):
        forward = ep.compare(records, "a", "b", metric="paid_cost", seed=seed)
        backward = ep.compare(records, "b", "a", metric="paid_cost", seed=seed)
        assert forward["interval"][0] == -backward["interval"][1] and forward["interval"][1] == -backward["interval"][0]
        flip = {"a_better": "b_better", "b_better": "a_better", "inconclusive": "inconclusive"}
        assert backward["verdict"] == flip[forward["verdict"]], (seed, forward, backward)


def test_a_resource_missing_from_a_matched_task_is_not_compared():
    rows = [_row(f"t{i}", "a", paid_cost=1.0) for i in range(30)] + [_row(f"t{i}", "b", tokens=5.0) for i in range(30)]
    assert ep.compare(ep.parse(rows), "a", "b", metric="paid_cost")["verdict"] == "insufficient"


# --- safety comes first, in compare and in the front ----------------------------------------------------------------------------


def test_compare_never_calls_an_unsafe_plan_better_whatever_it_saves():
    records = _matched(20, a_cost=0.0, b_cost=10.0, a_safe=lambda i: i != 5)
    result = ep.compare(records, "strong_solo", "team", metric="paid_cost")
    assert result["verdict"] == "safety_violation" and result["safety_violations"] == {"strong_solo": 1, "team": 0}
    assert ep.compare(records, "team", "strong_solo", metric="paid_cost")["verdict"] == "safety_violation"
    assert ep.compare(records, "strong_solo", "team")["verdict"] == "safety_violation"


def _front_records(**plans):
    rows = []
    for plan, spec in plans.items():
        for i in range(spec["n"]):
            rows.append(_row(f"t{i}", plan, verified=i < spec["ok"], safety=spec.get("safe", True),
                             paid_cost=spec["cost"], latency_seconds=spec["lat"]))
    return ep.parse(rows)


def test_a_dominated_plan_is_named_with_its_dominator_and_the_front_keeps_trade_offs():
    records = _front_records(solo={"n": 20, "ok": 18, "cost": 4.0, "lat": 30}, cheap={"n": 20, "ok": 12, "cost": 1.0, "lat": 10},
                             bad={"n": 20, "ok": 10, "cost": 5.0, "lat": 40})
    front = ep.pareto_front(records, ("paid_cost", "latency_seconds"))
    assert front["front"] == ["cheap", "solo"] and front["dominated"] == {"bad": "cheap"}  # first dominator in sorted order
    assert front["common_tasks"] == 20 and front["insufficient"] is False


def test_a_plan_with_a_safety_violation_is_excluded_however_cheap():
    records = _front_records(solo={"n": 20, "ok": 18, "cost": 4.0, "lat": 30}, risky={"n": 20, "ok": 20, "cost": 0.1, "lat": 1, "safe": False})
    front = ep.pareto_front(records, ("paid_cost",))
    assert front["front"] == ["solo"] and "safety-floor" in front["excluded"]["risky"]


def test_a_plan_that_did_not_report_a_chosen_resource_is_excluded_visibly():
    rows = [_row(f"t{i}", "a", paid_cost=1.0) for i in range(20)] + [_row(f"t{i}", "b", tokens=5.0) for i in range(20)]
    front = ep.pareto_front(ep.parse(rows), ("paid_cost",))
    assert front["front"] == ["a"] and "did not report" in front["excluded"]["b"]


def test_a_one_task_plan_cannot_join_or_dominate_and_the_floor_cannot_be_lowered():
    rows = [_row(f"t{i}", "thorough", verified=(i % 20 != 0), paid_cost=5.0, latency_seconds=30.0) for i in range(100)]
    rows.append(_row("only-1", "cheap_lucky", verified=True, paid_cost=0.1, latency_seconds=1.0))
    for floor in (20, 1, 0, None):
        front = ep.pareto_front(ep.parse(rows), ("paid_cost", "latency_seconds"), min_tasks=floor)
        assert front["front"] == ["thorough"] and front["dominated"] == {}
        assert "only 1 task" in front["excluded"]["cheap_lucky"]


def test_the_front_is_judged_on_shared_tasks_so_a_plan_cannot_win_with_easier_tasks():
    # X runs 100 tasks; its overall rate is dragged down by 80 hard tasks the other plan never saw.
    # Y runs only the first 20 (easy) tasks and looks better in a plan-wide average but is WORSE on those same 20 tasks.
    rows = []
    for i in range(100):
        rows.append(_row(f"t{i}", "X", verified=(i < 20) or False, paid_cost=1.0, latency_seconds=10.0))
    for i in range(20):
        rows.append(_row(f"t{i}", "Y", verified=(i < 10), paid_cost=2.0, latency_seconds=20.0))
    front = ep.pareto_front(ep.parse(rows), ("paid_cost", "latency_seconds"))
    assert front["common_tasks"] == 20 and front["front"] == ["X"] and front["dominated"] == {"Y": "X"}
    assert ep.compare(ep.parse(rows), "X", "Y")["verdict"] == "a_better"   # the pairwise comparison agrees


def test_survivors_that_share_too_few_tasks_give_no_front_at_all():
    rows = [_row(f"a{i}", "A", paid_cost=1.0) for i in range(25)] + [_row(f"b{i}", "B", paid_cost=2.0) for i in range(25)]
    front = ep.pareto_front(ep.parse(rows), ("paid_cost",))
    assert front["front"] == [] and front["insufficient"] is True and front["common_tasks"] == 0


def test_resources_are_never_summed_across_units():
    summary = ep.summarise(ep.parse([_row("t1", "a", paid_cost=2.0, tokens=100.0)]))
    assert summary["a"]["means"]["paid_cost"] == 2.0 and summary["a"]["means"]["tokens"] == 100.0
    assert "total" not in summary["a"]["means"]


def test_the_module_has_no_way_to_change_routing_or_fetch_data():
    source = inspect.getsource(ep)
    for forbidden in ("requests", "urllib", "socket", "subprocess", "open(", "os.environ", "yaml", "import os"):
        assert forbidden not in source, forbidden


def test_nan_or_missing_task_ids_cannot_manufacture_matched_evidence():
    rows = [_row(f"t{i}", "a") for i in range(19)] + [_row(f"t{i}", "b") for i in range(19)]
    rows += [dict(_row("x", "a"), task_id=float("nan")), dict(_row("x", "b"), task_id=float("nan"))]
    with pytest.raises(ep.RecordError):
        ep.parse(rows)


def test_a_resource_named_rate_cannot_overwrite_quality_in_the_front():
    rows = []
    for i in range(20):
        rows.append(_row(f"t{i}", "better", verified=True, rate=1.0))
        rows.append(_row(f"t{i}", "worse", verified=(i < 10), rate=2.0))
    front = ep.pareto_front(ep.parse(rows), ("rate",))
    assert front["front"] == ["better"] and front["dominated"] == {"worse": "better"}


@pytest.mark.parametrize("floor", [20.5, 20.0001, 21.0, 25])
def test_a_fractional_floor_is_rounded_up_never_truncated(floor):
    records = _matched(20, a_cost=1.0, b_cost=5.0, b_ok=lambda i: False)
    assert ep.compare(records, "strong_solo", "team", min_matched=floor)["verdict"] == "insufficient"
    front = ep.pareto_front(records, ("paid_cost",), min_tasks=floor)
    assert front["front"] == [] and all("only 20 task" in reason for reason in front["excluded"].values())


@pytest.mark.parametrize("floor", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_floor_falls_back_to_the_module_floor(floor):
    records = _matched(5, a_cost=1.0, b_cost=5.0, b_ok=lambda i: False)
    assert ep.compare(records, "strong_solo", "team", min_matched=floor)["verdict"] == "insufficient"


@pytest.mark.parametrize("dims", [(), [], ("paid_cost", "paid_cost"), ("",), (None,)])
def test_the_front_fails_closed_without_a_real_resource_dimension(dims):
    with pytest.raises(ValueError):
        ep.pareto_front(_front_records(a={"n": 20, "ok": 18, "cost": 1.0, "lat": 1}), dims)


def test_a_huge_integer_floor_is_honoured_not_silently_lowered():
    records = _matched(20, a_cost=1.0, b_cost=5.0, b_ok=lambda i: False)
    assert ep.compare(records, "strong_solo", "team", min_matched=10 ** 400)["verdict"] == "insufficient"
    assert ep.pareto_front(records, ("paid_cost",), min_tasks=10 ** 400)["front"] == []


@pytest.mark.parametrize("dims", [(" ",), ("\t",), (" paid_cost",), ("paid_cost ",)])
def test_whitespace_dimensions_are_not_named_dimensions(dims):
    with pytest.raises(ValueError):
        ep.pareto_front(_front_records(a={"n": 20, "ok": 18, "cost": 1.0, "lat": 1}), dims)

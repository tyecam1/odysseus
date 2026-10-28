"""Cluster-aware Six Eyes inference: repeated runs are not independent tasks; unmeasured safety is not a pass.

Synthetic input exercises the arithmetic; the regression test compares against the original evaluation's own hierarchical
re-analysis (evals/misumi-team/eval-v2/reanalyse_hierarchical.py) on its real data.
"""

import importlib.util
from pathlib import Path

import pytest

from src import efficiency_pareto as ep

REPO = Path(__file__).resolve().parent.parent


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adapter = _load("from_team_eval", "evals/misumi-six-eyes/from_team_eval.py")
reference = _load("reanalyse_hierarchical", "evals/misumi-team/eval-v2/reanalyse_hierarchical.py")


def _clustered(tasks, runs, a_ok, b_ok, safety=None):
    rows = []
    for t in range(tasks):
        for r in range(runs):
            for plan, ok in (("a", a_ok(t, r)), ("b", b_ok(t, r))):
                rows.append({"task_id": f"t{t}/{r}", "cluster": f"t{t}", "plan": plan, "verified": ok, "safety_ok": safety,
                             "costs": {"latency_seconds": 1.0}})
    return ep.parse(rows)


def test_repeated_runs_do_not_count_toward_the_evidence_floor():
    # 8 tasks x 12 runs = 96 paired runs, far above 20, but only 8 distinct tasks
    records = _clustered(8, 12, lambda t, r: True, lambda t, r: t >= 4)
    result = ep.compare(records, "a", "b")
    assert result["matched_tasks"] == 8 and result["matched_runs"] == 96
    assert result["verdict"] == "insufficient" and result["interval"] is None
    assert result["indicative"]["note"].startswith("8 distinct task(s) is below the floor of 20")


def test_twenty_distinct_tasks_with_repeats_reach_the_floor():
    records = _clustered(20, 3, lambda t, r: True, lambda t, r: False)
    result = ep.compare(records, "a", "b")
    assert result["matched_tasks"] == 20 and result["verdict"] == "a_better" and result["indicative"] is None


def test_hierarchical_interval_is_wider_than_flat_when_runs_cluster_by_task():
    # b fails entirely on 3 of 8 tasks: the 12 runs of a task are perfectly correlated. Treated flat (96 "tasks") the floor is met.
    clustered = ep.compare(_clustered(8, 12, lambda t, r: True, lambda t, r: t >= 3), "a", "b")["indicative"]
    flat_rows = ep.parse([{"task_id": f"t{t}/{r}", "plan": p, "verified": (True if p == "a" else t >= 3), "safety_ok": None,
                           "costs": {"latency_seconds": 1.0}} for t in range(8) for r in range(12) for p in ("a", "b")])
    flat = ep.compare(flat_rows, "a", "b")
    assert flat["matched_tasks"] == 96 and flat["verdict"] == "a_better"  # the overstated claim
    assert clustered["difference"] == flat["difference"] and clustered["direction"] == "a_better"
    width = lambda interval: interval[1] - interval[0]
    assert width(clustered["interval"]) > 2 * width(flat["interval"])


def test_singleton_clusters_reproduce_the_flat_bootstrap_exactly():
    plain = [{"task_id": f"t{i}", "plan": p, "verified": (i % 3 != 0) if p == "a" else (i % 2 == 0), "safety_ok": True,
              "costs": {"latency_seconds": 1.0 + i}} for i in range(30) for p in ("a", "b")]
    named = [{**row, "cluster": row["task_id"]} for row in plain]
    assert ep.compare(ep.parse(plain), "a", "b") == ep.compare(ep.parse(named), "a", "b")


def test_unmeasured_safety_is_not_a_pass_and_not_a_violation():
    records = _clustered(20, 2, lambda t, r: True, lambda t, r: True, safety=None)
    assert ep.summarise(records)["a"]["safety_measured"] == "unmeasured"
    assert ep.summarise(records)["a"]["safety_violations"] == 0
    result = ep.compare(records, "a", "b")
    assert result["safety_measured"] == "unmeasured"
    front = ep.pareto_front(records, ("latency_seconds",))
    assert front["safety_measured"] == {"a": "unmeasured", "b": "unmeasured"}


def test_measured_safety_failures_still_exclude_and_block():
    rows = [{"task_id": f"t{i}", "plan": p, "verified": True, "safety_ok": not (p == "a" and i == 0),
             "costs": {"latency_seconds": 1.0}} for i in range(25) for p in ("a", "b")]
    records = ep.parse(rows)
    assert ep.compare(records, "a", "b")["verdict"] == "safety_violation"
    assert "safety-floor" in ep.pareto_front(records, ("latency_seconds",))["excluded"]["a"]
    assert ep.summarise(records)["a"]["safety_measured"] == "measured"


def test_mixed_safety_is_reported_as_partial():
    rows = [{"task_id": f"t{i}", "plan": "a", "verified": True, "safety_ok": True if i % 2 else None, "costs": {"x": 1}} for i in range(4)]
    assert ep.summarise(ep.parse(rows), ("x",))["a"]["safety_measured"] == "partial"


@pytest.mark.parametrize("bad", [1, 0, "yes"])
def test_safety_must_be_a_real_boolean_or_none(bad):
    with pytest.raises(ep.RecordError):
        ep.parse([{"task_id": "t", "plan": "p", "verified": True, "safety_ok": bad, "costs": {"x": 1}}])


@pytest.mark.parametrize("bad", [7, None, " padded ", ["t"]])
def test_cluster_must_be_a_clean_string(bad):
    with pytest.raises(ep.RecordError):
        ep.parse([{"task_id": "t", "plan": "p", "verified": True, "safety_ok": None, "costs": {"x": 1}, "cluster": bad}])


def test_front_counts_distinct_tasks_not_runs():
    front = ep.pareto_front(_clustered(8, 12, lambda t, r: True, lambda t, r: False), ("latency_seconds",))
    assert front["front"] == [] and set(front["excluded"]) == {"a", "b"}
    assert all("96 runs of 8 distinct" in why for why in front["excluded"].values())


def test_front_places_plans_that_cover_enough_distinct_tasks():
    front = ep.pareto_front(_clustered(20, 2, lambda t, r: True, lambda t, r: False), ("latency_seconds",))
    assert front["common_tasks"] == 20 and front["common_runs"] == 40 and front["front"] == ["a"] and front["dominated"] == {"b": "a"}


# --- regression against the original evaluation's hierarchical re-analysis ---------------------------------------------------------


@pytest.mark.parametrize("judge", ["qwen", "llama"])
@pytest.mark.parametrize("kind", ["conflict", "clean"])
@pytest.mark.parametrize("plan", ["team", "teamfix", "teamdrop"])
def test_matches_the_original_hierarchical_reanalysis_on_the_real_data(judge, kind, plan):
    judged_rows = adapter.load_jsonl(adapter.DATA / adapter.JUDGES[judge])
    table = reference.cell_table(judged_rows, kind)
    point = reference.point(table, plan, "solo")
    low, high = reference.hierarchical(table, plan, "solo")
    replies = [r for p in adapter.PLANS for r in adapter.load_jsonl(adapter.DATA / f"replies-{p}.jsonl")]
    records, _ = adapter.build_records(replies, judged_rows, kind)
    mine = ep.compare(records, plan, "solo", "verified", adapter.SEED)
    assert mine["matched_tasks"] == 8 and mine["verdict"] == "insufficient"
    got = mine["indicative"]
    # verified is detection on conflict prompts and the complement of a false alarm on clean ones
    sign = 1 if kind == "conflict" else -1
    assert 100 * got["difference"] == pytest.approx(sign * point, abs=1e-6)
    lo, hi = sorted((sign * low, sign * high))
    assert 100 * got["interval"][0] == pytest.approx(lo, abs=4.5)
    assert 100 * got["interval"][1] == pytest.approx(hi, abs=4.5)


def test_the_flat_bootstrap_would_have_overstated_the_old_result():
    """The old report called qwen team-vs-solo verified 'solo better' on 192 'tasks'; with 8 distinct tasks it is indicative only."""
    replies = [r for p in adapter.PLANS for r in adapter.load_jsonl(adapter.DATA / f"replies-{p}.jsonl")]
    records, _ = adapter.build_records(replies, adapter.load_jsonl(adapter.DATA / adapter.JUDGES["qwen"]), "conflict")
    result = ep.compare(records, "team", "solo", "verified", adapter.SEED)
    assert result["indicative"]["interval"][0] < 0 < result["indicative"]["interval"][1]
    assert result["indicative"]["direction"] == "inconclusive"


# --- adapter reporting ------------------------------------------------------------------------------------------------------------


def test_report_separates_views_and_states_unmeasured_safety_and_distinct_tasks():
    text = adapter.report()
    for heading in ("### composite", "### conflict", "### clean", "## Judge disagreement", "Safety was not measured"):
        assert heading in text
    assert "| distinct tasks | task-runs |" in text and "post-hoc" in text
    assert "no verdict is established here" in text


def test_judge_agreement_arithmetic():
    def rec(task, ok):
        return ep.parse([{"task_id": task, "plan": "p", "verified": ok, "safety_ok": None, "costs": {"x": 1}}])[0]
    a = [rec("1", True), rec("2", True), rec("3", False), rec("4", False)]
    same = adapter.agreement(a, a, "p")
    assert same["agreement"] == 1.0 and same["kappa"] == pytest.approx(1.0)
    flipped = [rec("1", False), rec("2", False), rec("3", True), rec("4", True)]
    assert adapter.agreement(a, flipped, "p")["kappa"] == pytest.approx(-1.0)
    constant = [rec(str(i), True) for i in range(1, 5)]
    assert adapter.agreement(constant, constant, "p")["kappa"] is None
    assert adapter.agreement(a, a, "missing") is None

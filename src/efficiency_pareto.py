"""Evidence analyser for effective-intelligence efficiency ("Six Eyes"): verified outcomes per total resources, by plan.

Design 2026-10-16 (``docs/misumi-intelligence-and-demonstration-ambition-2026-10-16.md`` section 2, PR #91): compare execution plans
(strong solo, cheap-first, skill-complementary team, an evidence-based optimiser, a deterministic tool) on the SAME real tasks, count
the whole lifecycle (coordination, verification, rework, human correction) and report where each plan sits on a Pareto front.

This module is only the arithmetic over records someone else collected from completed work:

* It never generates, fills or simulates data. No rows, too few matched tasks, or a safety-floor failure gives "insufficient" or an
  exclusion, never a guess.
* Quality and safety come first: a plan with any safety-floor violation is excluded from the front whatever it saves.
* Resource units stay distinct (paid cost, tokens, local compute seconds, latency, human corrections); nothing is summed across
  units. A caller chooses which dimensions to compare.
* Comparisons use matched tasks only (a task counts for a pair only when both plans ran it) and a seeded task-level bootstrap, so
  the same records always give the same interval.
* It only evidences. It cannot change a route, promote a plan or touch policy; promotion stays with the governed owner.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

MIN_MATCHED_TASKS = 20  # below this a pairwise comparison is "insufficient", never a verdict
BOOTSTRAP_RESAMPLES = 2000
CONFIDENCE = 0.95
DEFAULT_COST_DIMENSIONS = ("paid_cost", "tokens", "compute_seconds", "latency_seconds", "corrections")


class RecordError(ValueError):
    """A record that cannot be trusted as evidence (missing field, non-finite or negative resource, bad type)."""


@dataclass(frozen=True)
class Record:
    task_id: str
    plan: str
    verified: bool            # an independent check says the outcome is correct and complete
    safety_ok: bool           # the safety/quality floor was respected on this task
    costs: Dict[str, float]   # resource units, each already the TOTAL for the task (coordination, verification, rework included)


def parse(rows: Iterable[dict]) -> List[Record]:
    records: List[Record] = []
    seen: set = set()
    for index, row in enumerate(rows):
        try:
            task_id, plan = str(row["task_id"]).strip(), str(row["plan"]).strip()
            verified, safety_ok, costs = row["verified"], row["safety_ok"], row["costs"]
        except (KeyError, TypeError) as exc:
            raise RecordError(f"row {index}: missing {exc}") from exc
        if not task_id or not plan:
            raise RecordError(f"row {index}: empty task_id or plan")
        if not isinstance(verified, bool) or not isinstance(safety_ok, bool):
            raise RecordError(f"row {index}: verified and safety_ok must be booleans")
        if not isinstance(costs, dict) or not costs:
            raise RecordError(f"row {index}: costs must be a non-empty mapping")
        clean: Dict[str, float] = {}
        for unit, value in costs.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise RecordError(f"row {index}: cost {unit!r} must be a finite number >= 0")
            clean[str(unit)] = float(value)
        if (task_id, plan) in seen:
            raise RecordError(f"row {index}: duplicate task/plan {task_id!r}/{plan!r}")
        seen.add((task_id, plan))
        records.append(Record(task_id, plan, verified, safety_ok, clean))
    return records


def _interval(samples: Sequence[float]) -> Tuple[float, float]:
    ordered = sorted(samples)
    low = ordered[int((1 - CONFIDENCE) / 2 * (len(ordered) - 1))]
    high = ordered[int((1 + CONFIDENCE) / 2 * (len(ordered) - 1))]
    return low, high


def _bootstrap(values: Sequence[float], seed: int) -> Tuple[float, float]:
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    return _interval(means)


def summarise(records: Sequence[Record], dimensions: Sequence[str] = DEFAULT_COST_DIMENSIONS, seed: int = 1) -> Dict[str, dict]:
    """Per plan: task count, verified rate with an interval, safety violations, and the mean of each resource it reported."""
    by_plan: Dict[str, List[Record]] = {}
    for record in records:
        by_plan.setdefault(record.plan, []).append(record)
    summary: Dict[str, dict] = {}
    for plan in sorted(by_plan):
        rows = by_plan[plan]
        verified = [1.0 if r.verified else 0.0 for r in rows]
        entry = {
            "tasks": len(rows), "verified_rate": sum(verified) / len(rows),
            "verified_interval": _bootstrap(verified, seed) if len(rows) >= 2 else None,
            "safety_violations": sum(1 for r in rows if not r.safety_ok), "means": {},
        }
        for unit in dimensions:
            observed = [r.costs[unit] for r in rows if unit in r.costs]
            if len(observed) == len(rows):  # a unit is reported only when every task of the plan has it
                entry["means"][unit] = sum(observed) / len(observed)
        summary[plan] = entry
    return summary


def compare(records: Sequence[Record], plan_a: str, plan_b: str, metric: str = "verified", seed: int = 1,
            min_matched: int = MIN_MATCHED_TASKS) -> dict:
    """Matched-task difference ``a - b`` of one metric with a seeded task-level bootstrap interval.

    ``metric`` is ``verified`` (higher is better) or a resource unit (lower is better). Verdict: ``a_better`` / ``b_better`` when the
    interval excludes zero in that direction, ``inconclusive`` when it spans zero, ``insufficient`` below ``min_matched`` tasks.
    """
    a = {r.task_id: r for r in records if r.plan == plan_a}
    b = {r.task_id: r for r in records if r.plan == plan_b}
    shared = sorted(set(a) & set(b))
    result = {"a": plan_a, "b": plan_b, "metric": metric, "matched_tasks": len(shared), "difference": None, "interval": None,
              "verdict": "insufficient"}
    if len(shared) < max(2, min_matched):
        return result
    if metric == "verified":
        diffs = [(1.0 if a[t].verified else 0.0) - (1.0 if b[t].verified else 0.0) for t in shared]
    else:
        if any(metric not in a[t].costs or metric not in b[t].costs for t in shared):
            return result  # a resource that is not reported on every matched task is not compared
        diffs = [a[t].costs[metric] - b[t].costs[metric] for t in shared]
    mean = sum(diffs) / len(diffs)
    low, high = _bootstrap(diffs, seed)
    result.update(difference=mean, interval=(low, high))
    better_when_positive = metric == "verified"
    if low > 0:
        result["verdict"] = "a_better" if better_when_positive else "b_better"
    elif high < 0:
        result["verdict"] = "b_better" if better_when_positive else "a_better"
    else:
        result["verdict"] = "inconclusive"
    return result


def pareto_front(summary: Dict[str, dict], dimensions: Sequence[str]) -> dict:
    """Plans not dominated on (verified rate up, each chosen resource down). A plan with a safety violation is excluded first.

    ``front`` lists the survivors; ``dominated`` maps each loser to a plan that dominates it; ``excluded`` maps a plan to why it was
    left out (safety violation, or a chosen resource it did not report), so nothing silently disappears.
    """
    excluded: Dict[str, str] = {}
    candidates: Dict[str, dict] = {}
    for plan, entry in summary.items():
        if entry["safety_violations"]:
            excluded[plan] = f"{entry['safety_violations']} safety-floor violation(s)"
        elif any(unit not in entry["means"] for unit in dimensions):
            excluded[plan] = "did not report every chosen resource"
        else:
            candidates[plan] = entry

    def dominates(x: dict, y: dict) -> bool:
        no_worse = x["verified_rate"] >= y["verified_rate"] and all(x["means"][u] <= y["means"][u] for u in dimensions)
        better = x["verified_rate"] > y["verified_rate"] or any(x["means"][u] < y["means"][u] for u in dimensions)
        return no_worse and better

    dominated: Dict[str, str] = {}
    for plan, entry in candidates.items():
        for other, other_entry in candidates.items():
            if other != plan and dominates(other_entry, entry):
                dominated[plan] = other
                break
    front = sorted(plan for plan in candidates if plan not in dominated)
    return {"front": front, "dominated": dominated, "excluded": excluded, "dimensions": list(dimensions)}

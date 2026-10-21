"""Evidence analyser for effective-intelligence efficiency ("Six Eyes"): verified outcomes per total resources, by plan.

Design 2026-10-16 (``docs/misumi-intelligence-and-demonstration-ambition-2026-10-16.md`` section 2, PR #91): compare execution plans
(strong solo, cheap-first, skill-complementary team, an evidence-based optimiser, a deterministic tool) on the SAME real tasks, count
the whole lifecycle (coordination, verification, rework, human correction) and report where each plan sits on a Pareto front.

This module is only the arithmetic over records someone else collected from completed work:

* It never generates, fills or simulates data. No rows, too few matched tasks, or a safety-floor failure gives "insufficient" or an
  exclusion, never a guess.
* Quality and safety come first: a plan with any safety-floor violation is never called better, and is excluded from the front,
  whatever it saves.
* Everything is judged on MATCHED tasks: a pairwise comparison uses only tasks both plans ran, and the front uses only tasks every
  surviving plan ran, so a plan cannot win by having run easier or fewer tasks.
* The evidence floor (``MIN_MATCHED_TASKS``) can be RAISED by a caller, never lowered.
* Resource units stay distinct (paid cost, tokens, local compute seconds, latency, human corrections); nothing is summed across
  units. Values are bounded so aggregation can never overflow into infinity.
* The bootstrap is seeded and symmetric: swapping the two plans negates the interval and cannot change the verdict.
* It only evidences. It cannot change a route, promote a plan or touch policy.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

MIN_MATCHED_TASKS = 20  # the evidence floor: a caller may raise it, never lower it
BOOTSTRAP_RESAMPLES = 2000
CONFIDENCE = 0.95
MAX_COST = 1e12  # per-task resource ceiling; far above any real value, far below overflow in sums of thousands of rows
DEFAULT_COST_DIMENSIONS = ("paid_cost", "tokens", "compute_seconds", "latency_seconds", "corrections")


class RecordError(ValueError):
    """A record that cannot be trusted as evidence (missing field, non-finite, negative or absurd resource, bad type)."""


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
            try:
                number = float(value) if not isinstance(value, bool) and isinstance(value, (int, float)) else None
            except OverflowError:
                number = None
            if number is None or not math.isfinite(number) or number < 0 or number > MAX_COST:
                raise RecordError(f"row {index}: cost {unit!r} must be a finite number from 0 to {MAX_COST:g}")
            clean[str(unit)] = number
        if (task_id, plan) in seen:
            raise RecordError(f"row {index}: duplicate task/plan {task_id!r}/{plan!r}")
        seen.add((task_id, plan))
        records.append(Record(task_id, plan, verified, safety_ok, clean))
    return records


def _floor(requested: int) -> int:
    """The evidence floor in force: whatever the caller asks for, but never below the module's own."""
    try:
        return max(MIN_MATCHED_TASKS, int(requested))
    except (TypeError, ValueError, OverflowError):
        return MIN_MATCHED_TASKS


def _mean(values: Sequence[float]) -> float:
    return math.fsum(values) / len(values)


def _interval(samples: Sequence[float]) -> Tuple[float, float]:
    """Symmetric percentile interval: the same number of samples is trimmed from each end, so negating every sample negates
    the interval (the verdict for A-versus-B and B-versus-A can never differ)."""
    ordered = sorted(samples)
    trim = int(((1 - CONFIDENCE) / 2) * (len(ordered) - 1))
    return ordered[trim], ordered[len(ordered) - 1 - trim]


def _bootstrap(values: Sequence[float], seed: int) -> Tuple[float, float]:
    rng = random.Random(seed)
    n = len(values)
    return _interval([math.fsum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(BOOTSTRAP_RESAMPLES)])


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
            "tasks": len(rows), "verified_rate": _mean(verified),
            "verified_interval": _bootstrap(verified, seed) if len(rows) >= 2 else None,
            "safety_violations": sum(1 for r in rows if not r.safety_ok), "means": {},
        }
        for unit in dimensions:
            observed = [r.costs[unit] for r in rows if unit in r.costs]
            if len(observed) == len(rows):  # a unit is reported only when every task of the plan has it
                entry["means"][unit] = _mean(observed)
        summary[plan] = entry
    return summary


def compare(records: Sequence[Record], plan_a: str, plan_b: str, metric: str = "verified", seed: int = 1,
            min_matched: int = MIN_MATCHED_TASKS) -> dict:
    """Matched-task difference ``a - b`` of one metric with a seeded task-level bootstrap interval.

    ``metric`` is ``verified`` (higher is better) or a resource unit (lower is better). Verdict: ``a_better`` / ``b_better`` when the
    interval excludes zero in that direction, ``inconclusive`` when it spans zero, ``insufficient`` below the evidence floor, and
    ``safety_violation`` when either plan broke the safety floor on any matched task (then nothing is called better).
    """
    a = {r.task_id: r for r in records if r.plan == plan_a}
    b = {r.task_id: r for r in records if r.plan == plan_b}
    shared = sorted(set(a) & set(b))
    result = {"a": plan_a, "b": plan_b, "metric": metric, "matched_tasks": len(shared), "difference": None, "interval": None,
              "verdict": "insufficient"}
    if len(shared) < _floor(min_matched):
        return result
    unsafe = {plan: sum(1 for t in shared if not rows[t].safety_ok) for plan, rows in ((plan_a, a), (plan_b, b))}
    if any(unsafe.values()):
        result.update(verdict="safety_violation", safety_violations=unsafe)
        return result
    if metric == "verified":
        diffs = [(1.0 if a[t].verified else 0.0) - (1.0 if b[t].verified else 0.0) for t in shared]
    else:
        if any(metric not in a[t].costs or metric not in b[t].costs for t in shared):
            return result  # a resource that is not reported on every matched task is not compared
        diffs = [a[t].costs[metric] - b[t].costs[metric] for t in shared]
    mean = _mean(diffs)
    low, high = _bootstrap(diffs, seed)
    if not all(math.isfinite(x) for x in (mean, low, high)):
        return result
    result.update(difference=mean, interval=(low, high))
    better_when_positive = metric == "verified"
    if low > 0:
        result["verdict"] = "a_better" if better_when_positive else "b_better"
    elif high < 0:
        result["verdict"] = "b_better" if better_when_positive else "a_better"
    else:
        result["verdict"] = "inconclusive"
    return result


def pareto_front(records: Sequence[Record], dimensions: Sequence[str], min_tasks: int = MIN_MATCHED_TASKS, seed: int = 1) -> dict:
    """Plans not dominated on (verified rate up, each chosen resource down), judged ONLY on the tasks every surviving plan ran.

    Excluded first, each with a visible reason: a plan with any safety-floor violation; a plan with fewer tasks than the evidence
    floor; a plan that did not report a chosen resource on every task. The survivors are then compared on the tasks they ALL ran;
    if those are fewer than the floor the result is ``insufficient`` with an empty front (a plan never wins by running easier or
    fewer tasks). ``dominated`` maps a loser to the first dominating plan in sorted order.
    """
    floor = _floor(min_tasks)
    by_plan: Dict[str, List[Record]] = {}
    for record in records:
        by_plan.setdefault(record.plan, []).append(record)
    excluded: Dict[str, str] = {}
    candidates: Dict[str, Dict[str, Record]] = {}
    for plan in sorted(by_plan):
        rows = by_plan[plan]
        violations = sum(1 for r in rows if not r.safety_ok)
        if violations:
            excluded[plan] = f"{violations} safety-floor violation(s)"
        elif len(rows) < floor:
            excluded[plan] = f"only {len(rows)} task(s); fewer than the {floor} needed to be placed on the front"
        elif any(unit not in r.costs for r in rows for unit in dimensions):
            excluded[plan] = "did not report every chosen resource"
        else:
            candidates[plan] = {r.task_id: r for r in rows}
    common = sorted(set.intersection(*(set(rows) for rows in candidates.values()))) if candidates else []
    out = {"front": [], "dominated": {}, "excluded": excluded, "dimensions": list(dimensions), "common_tasks": len(common),
           "insufficient": False}
    if len(common) < floor:
        out["insufficient"] = bool(candidates)
        return out
    stats = {}
    for plan, rows in candidates.items():
        stats[plan] = {"rate": _mean([1.0 if rows[t].verified else 0.0 for t in common]),
                       **{u: _mean([rows[t].costs[u] for t in common]) for u in dimensions}}

    def dominates(x: dict, y: dict) -> bool:
        no_worse = x["rate"] >= y["rate"] and all(x[u] <= y[u] for u in dimensions)
        better = x["rate"] > y["rate"] or any(x[u] < y[u] for u in dimensions)
        return no_worse and better

    for plan in sorted(stats):
        for other in sorted(stats):
            if other != plan and dominates(stats[other], stats[plan]):
                out["dominated"][plan] = other
                break
    out["front"] = sorted(plan for plan in stats if plan not in out["dominated"])
    return out

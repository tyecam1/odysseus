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
* Repeated trials of one underlying task are CLUSTERED, not independent. A record may name its ``cluster`` (the underlying task);
  records without one are their own cluster. When any cluster holds more than one trial, intervals use a paired hierarchical
  bootstrap (resample clusters, then trials within each chosen cluster), and the evidence floor counts distinct clusters, never
  trials. Flat resampling of repeated runs understates uncertainty (see ``evals/misumi-team/eval-v2/RESULTS.md``, "Correction").
* Safety may be UNMEASURED (``safety_ok`` None). That is not a pass: it is never counted as a violation and never reported as
  safe; results carry ``safety_measured`` so a reader can tell "no violations seen" from "not measured".
* It only evidences. It cannot change a route, promote a plan or touch policy.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

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
    safety_ok: Optional[bool]  # the safety/quality floor was respected on this task; None = not measured (NOT a pass)
    costs: Dict[str, float]   # resource units, each already the TOTAL for the task (coordination, verification, rework included)
    cluster: str = ""         # the underlying task this trial repeats; empty = the task_id is its own cluster

    @property
    def group(self) -> str:
        return self.cluster or self.task_id


def parse(rows: Iterable[dict]) -> List[Record]:
    records: List[Record] = []
    seen: set = set()
    for index, row in enumerate(rows):
        try:
            raw_task, raw_plan = row["task_id"], row["plan"]
            verified, safety_ok, costs = row["verified"], row["safety_ok"], row["costs"]
        except (KeyError, TypeError) as exc:
            raise RecordError(f"row {index}: missing {exc}") from exc
        if not isinstance(raw_task, str) or not isinstance(raw_plan, str):
            raise RecordError(f"row {index}: task_id and plan must be strings")
        task_id, plan = raw_task.strip(), raw_plan.strip()
        if not task_id or not plan:
            raise RecordError(f"row {index}: empty task_id or plan")
        if not isinstance(verified, bool) or not (safety_ok is None or isinstance(safety_ok, bool)):
            raise RecordError(f"row {index}: verified must be a boolean and safety_ok a boolean or None (unmeasured)")
        cluster = row.get("cluster", "")
        if not isinstance(cluster, str) or cluster != cluster.strip():
            raise RecordError(f"row {index}: cluster must be a string without surrounding whitespace")
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
        records.append(Record(task_id, plan, verified, safety_ok, clean, cluster))
    return records


def _floor(requested: int) -> int:
    """The evidence floor in force: whatever the caller asks for, but never below the module's own."""
    if isinstance(requested, bool):
        return MIN_MATCHED_TASKS
    if isinstance(requested, int):  # exact, whatever its size: a huge floor stays huge (and so stays "insufficient")
        return max(MIN_MATCHED_TASKS, requested)
    if isinstance(requested, float) and math.isfinite(requested):
        return max(MIN_MATCHED_TASKS, math.ceil(requested))
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


def _clusters(pairs: Sequence[Tuple[str, float]]) -> List[List[float]]:
    """Group (cluster, value) pairs into one list of trial values per cluster, in first-seen order (so singleton clusters keep the
    caller's row order and reproduce the earlier flat bootstrap exactly)."""
    grouped: Dict[str, List[float]] = {}
    for name, value in pairs:
        grouped.setdefault(name, []).append(value)
    return list(grouped.values())


def _cluster_bootstrap(groups: Sequence[Sequence[float]], seed: int) -> Tuple[float, float]:
    """Interval for the mean over all trials. When every cluster has one trial this is exactly the flat bootstrap; otherwise it is
    the hierarchical one: draw clusters with replacement, then draw each chosen cluster's trials with replacement."""
    if all(len(g) == 1 for g in groups):
        return _bootstrap([g[0] for g in groups], seed)
    rng = random.Random(seed)
    k = len(groups)
    samples = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        totals, count = [], 0
        for _ in range(k):
            trials = groups[rng.randrange(k)]
            m = len(trials)
            totals.append(math.fsum(trials[rng.randrange(m)] for _ in range(m)))
            count += m
        samples.append(math.fsum(totals) / count)
    return _interval(samples)


def _safety_state(rows: Sequence[Record]) -> str:
    measured = sum(1 for r in rows if r.safety_ok is not None)
    return "measured" if measured == len(rows) else "unmeasured" if measured == 0 else "partial"


def summarise(records: Sequence[Record], dimensions: Sequence[str] = DEFAULT_COST_DIMENSIONS, seed: int = 1) -> Dict[str, dict]:
    """Per plan: task count, verified rate with an interval, safety violations, and the mean of each resource it reported."""
    by_plan: Dict[str, List[Record]] = {}
    for record in records:
        by_plan.setdefault(record.plan, []).append(record)
    summary: Dict[str, dict] = {}
    for plan in sorted(by_plan):
        rows = by_plan[plan]
        verified = [1.0 if r.verified else 0.0 for r in rows]
        groups = _clusters([(r.group, v) for r, v in zip(rows, verified)])
        entry = {
            "tasks": len(rows), "unique_tasks": len(groups), "verified_rate": _mean(verified),
            "verified_interval": _cluster_bootstrap(groups, seed) if len(groups) >= 2 else None,
            "safety_violations": sum(1 for r in rows if r.safety_ok is False), "safety_measured": _safety_state(rows), "means": {},
        }
        for unit in dimensions:
            observed = [r.costs[unit] for r in rows if unit in r.costs]
            if len(observed) == len(rows):  # a unit is reported only when every task of the plan has it
                entry["means"][unit] = _mean(observed)
        summary[plan] = entry
    return summary


def compare(records: Sequence[Record], plan_a: str, plan_b: str, metric: str = "verified", seed: int = 1,
            min_matched: int = MIN_MATCHED_TASKS) -> dict:
    """Matched difference ``a - b`` of one metric with a seeded, cluster-aware bootstrap interval.

    ``matched_tasks`` counts distinct underlying tasks (clusters) both plans ran; ``matched_runs`` counts the paired trials.
    Only distinct tasks count toward the evidence floor. Below the floor the verdict is ``insufficient`` and the interval is
    withheld, but an ``indicative`` entry (difference, interval, direction) is given for reading only: it never sets the verdict.

    ``metric`` is ``verified`` (higher is better) or a resource unit (lower is better). Verdict: ``a_better`` / ``b_better`` when the
    interval excludes zero in that direction, ``inconclusive`` when it spans zero, ``insufficient`` below the evidence floor, and
    ``safety_violation`` when either plan broke the safety floor on any matched task (then nothing is called better).
    """
    a = {r.task_id: r for r in records if r.plan == plan_a}
    b = {r.task_id: r for r in records if r.plan == plan_b}
    shared = sorted(set(a) & set(b))
    unique = {a[t].group for t in shared}
    result = {"a": plan_a, "b": plan_b, "metric": metric, "matched_tasks": len(unique), "matched_runs": len(shared),
              "difference": None, "interval": None, "verdict": "insufficient", "indicative": None,
              "safety_measured": _safety_state([a[t] for t in shared] + [b[t] for t in shared]) if shared else "unmeasured",
              "safety_by_plan": {plan_a: _safety_state([a[t] for t in shared]) if shared else "unmeasured",
                                 plan_b: _safety_state([b[t] for t in shared]) if shared else "unmeasured"},
              "safety_caveat": None}
    if not shared:
        return result
    if any(a[t].group != b[t].group for t in shared):
        result["error"] = "cluster identity differs between the plans for a matched task"  # never guess which grouping is right
        return result
    unsafe = {plan: sum(1 for t in shared if rows[t].safety_ok is False) for plan, rows in ((plan_a, a), (plan_b, b))}
    enough = len(unique) >= _floor(min_matched)
    if any(unsafe.values()):
        # a measured safety failure is reported at any evidence level and no direction is offered, indicative or otherwise
        result.update(safety_violations=unsafe)
        if enough:
            result["verdict"] = "safety_violation"
        else:
            result["indicative"] = {"difference": None, "interval": None, "direction": "withheld",
                                    "note": "a safety-floor violation was measured; no direction is offered below the evidence floor"}
        return result
    unmeasured = [plan for plan, state in result["safety_by_plan"].items() if state != "measured"]
    if unmeasured:
        result["safety_caveat"] = ("safety was not fully measured for " + ", ".join(unmeasured) +
                                   ": a verdict here says nothing about safety, and the absence of a violation is not evidence of safety")
    if metric == "verified":
        diffs = [(a[t].group, (1.0 if a[t].verified else 0.0) - (1.0 if b[t].verified else 0.0)) for t in shared]
    else:
        if any(metric not in a[t].costs or metric not in b[t].costs for t in shared):
            return result  # a resource that is not reported on every matched task is not compared
        diffs = [(a[t].group, a[t].costs[metric] - b[t].costs[metric]) for t in shared]
    groups = _clusters(diffs)
    mean = _mean([v for _, v in diffs])
    low, high = _cluster_bootstrap(groups, seed) if len(groups) >= 2 else (float("nan"), float("nan"))
    if not all(math.isfinite(x) for x in (mean, low, high)):
        return result
    better_when_positive = metric == "verified"
    if low > 0:
        direction = "a_better" if better_when_positive else "b_better"
    elif high < 0:
        direction = "b_better" if better_when_positive else "a_better"
    else:
        direction = "inconclusive"
    if not enough:
        result["indicative"] = {"difference": mean, "interval": (low, high), "direction": direction,
                                "note": f"{len(unique)} distinct task(s) is below the floor of {_floor(min_matched)}: for reading only"}
        return result
    result.update(difference=mean, interval=(low, high), verdict=direction)
    return result


def pareto_front(records: Sequence[Record], dimensions: Sequence[str], min_tasks: int = MIN_MATCHED_TASKS, seed: int = 1) -> dict:
    """Plans not dominated on (verified rate up, each chosen resource down), judged ONLY on the tasks every surviving plan ran.

    Excluded first, each with a visible reason: a plan with any safety-floor violation; a plan with fewer tasks than the evidence
    floor; a plan that did not report a chosen resource on every task. The survivors are then compared on the tasks they ALL ran;
    if those are fewer than the floor the result is ``insufficient`` with an empty front (a plan never wins by running easier or
    fewer tasks). ``dominated`` maps a loser to the first dominating plan in sorted order.
    """
    if not dimensions or any(not isinstance(unit, str) or not unit.strip() or unit != unit.strip() for unit in dimensions) or len(set(dimensions)) != len(dimensions):
        raise ValueError("choose at least one distinct, named resource dimension: an efficiency comparison without a resource is not one")
    floor = _floor(min_tasks)
    by_plan: Dict[str, List[Record]] = {}
    for record in records:
        by_plan.setdefault(record.plan, []).append(record)
    excluded: Dict[str, str] = {}
    candidates: Dict[str, Dict[str, Record]] = {}
    for plan in sorted(by_plan):
        rows = by_plan[plan]
        violations = sum(1 for r in rows if r.safety_ok is False)
        distinct = len({r.group for r in rows})
        if violations:
            excluded[plan] = f"{violations} safety-floor violation(s)"
        elif distinct < floor:
            repeats = f" ({len(rows)} runs of {distinct} distinct)" if len(rows) != distinct else ""
            excluded[plan] = f"only {distinct} task(s){repeats}; fewer than the {floor} needed to be placed on the front"
        elif any(unit not in r.costs for r in rows for unit in dimensions):
            excluded[plan] = "did not report every chosen resource"
        else:
            candidates[plan] = {r.task_id: r for r in rows}
    common = sorted(set.intersection(*(set(rows) for rows in candidates.values()))) if candidates else []
    first = next(iter(candidates.values()), {})
    if any(len({rows[t].group for rows in candidates.values()}) > 1 for t in common):
        out = {"front": [], "dominated": {}, "excluded": excluded, "dimensions": list(dimensions), "common_tasks": 0, "common_runs": len(common),
               "insufficient": True, "error": "cluster identity differs between plans for a matched task", "safety_measured": {}}
        return out
    distinct_common = len({first[t].group for t in common}) if candidates else 0
    out = {"front": [], "dominated": {}, "excluded": excluded, "dimensions": list(dimensions), "common_tasks": distinct_common,
           "common_runs": len(common), "insufficient": False,
           "safety_measured": {plan: _safety_state(list(rows.values())) for plan, rows in candidates.items()}}
    out["safety_caveat"] = ("safety was not fully measured for " + ", ".join(sorted(p for p, s in out["safety_measured"].items() if s != "measured")) +
                            ": a place on the front says nothing about safety") if any(s != "measured" for s in out["safety_measured"].values()) else None
    if distinct_common < floor:
        out["insufficient"] = bool(candidates)
        return out
    stats = {}
    for plan, rows in candidates.items():
        stats[plan] = {"rate": _mean([1.0 if rows[t].verified else 0.0 for t in common]),
                       "costs": {u: _mean([rows[t].costs[u] for t in common]) for u in dimensions}}

    def dominates(x: dict, y: dict) -> bool:
        no_worse = x["rate"] >= y["rate"] and all(x["costs"][u] <= y["costs"][u] for u in dimensions)
        better = x["rate"] > y["rate"] or any(x["costs"][u] < y["costs"][u] for u in dimensions)
        return no_worse and better

    for plan in sorted(stats):
        for other in sorted(stats):
            if other != plan and dominates(stats[other], stats[plan]):
                out["dominated"][plan] = other
                break
    out["front"] = sorted(plan for plan in stats if plan not in out["dominated"])
    return out

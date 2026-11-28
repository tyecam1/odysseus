"""Score paired, source-traceable held-out decisions from captured route outputs.

This scorer never calls providers or promotes bindings. Cases and adjudication
live with the research owner, while the route captures contain only option
indices and bounded measurements.
"""
import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean


def score(cases, routes, *, high_confidence=0.8):
    if not cases or not routes or not 0 <= high_confidence <= 1:
        raise ValueError("Cases, route captures and a valid confidence cutoff are required")
    indexed, seen_ids = {}, set()
    development_units = set()
    held_out_units = set()
    for case in cases:
        if not all(isinstance(case.get(key), str) and case[key].strip()
                   for key in ("id", "task_class", "research_unit", "source", "adjudication")):
            raise ValueError("Cases need stable IDs, research units, sources and adjudication")
        if case["id"] in seen_ids:
            raise ValueError("Expected unique decision IDs")
        seen_ids.add(case["id"])
        if case["split"] == "development":
            development_units.add(case["research_unit"])
            continue
        if case["split"] != "held-out":
            raise ValueError("Expected a known split label")
        if not re.fullmatch(r"[0-9a-f]{64}", case.get("candidate_set_hash", "")):
            raise ValueError("Held-out decisions must pin the ordered candidate set")
        count, expected = case["candidate_count"], case["expected"]
        if type(count) is not int or count < 2 or (expected is not None
                and (type(expected) is not int or not 0 <= expected < count)):
            raise ValueError("Invalid adjudicated response space")
        held_out_units.add(case["research_unit"])
        indexed[case["id"]] = case
    if not indexed or held_out_units & development_units:
        raise ValueError("A held-out research unit must be disjoint from development")
    return {name: _score_route(indexed, observations, high_confidence)
            for name, observations in routes.items()}


def _score_route(cases, observations, high_confidence):
    if set(observations) != set(cases):
        raise ValueError("Every route must account for the same held-out cases")
    grouped = defaultdict(list)
    for case_id, case in cases.items():
        row = observations[case_id]
        expected, count = case["expected"], case["candidate_count"]
        probabilities = row.get("probabilities")
        selected = row.get("selected")
        status = row["status"]
        if status not in {"answered", "abstained", "ineligible", "error"}:
            raise ValueError("Unexpected route outcome")
        if status == "answered" and (type(selected) is not int or not 0 <= selected < count):
            raise ValueError("Answered rows need a selected candidate")
        if status != "answered" and selected is not None:
            raise ValueError("Only answered rows may select a candidate")
        if row.get("candidate_set_hash") != case["candidate_set_hash"]:
            raise ValueError("Candidate set must match the pinned decision")
        if status in {"ineligible", "error"} and probabilities is not None:
            raise ValueError("A failed or ineligible route cannot supply a scored distribution")
        if probabilities is not None:
            if (len(probabilities) != count
                    or any(type(p) not in (int, float) or not 0 <= p <= 1 for p in probabilities)
                    or not math.isclose(math.fsum(probabilities), 1, abs_tol=1e-6)):
                raise ValueError("Invalid captured distribution")
        elif status == "answered":
            raise ValueError("Answered rows need a closed probability distribution")
        for measurement in ("latency_ms", "cost_usd", "input_tokens", "correction_minutes"):
            value = row.get(measurement)
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                raise ValueError(f"Invalid captured measurement {measurement}")
        grouped[case["task_class"]].append((expected, row))
    return {task_class: _summarise(rows, high_confidence) for task_class, rows in grouped.items()}


def _summarise(rows, high_confidence):
    answered = [(expected, row) for expected, row in rows if row["status"] == "answered"]
    distribution_rows = [(expected, row["probabilities"]) for expected, row in rows
                         if expected is not None and row.get("probabilities") is not None]
    confident = [(expected, row) for expected, row in answered
                 if row["probabilities"][row["selected"]] >= high_confidence]

    def metric(values):
        values = list(values)
        return mean(values) if values else None

    latencies = sorted(row["latency_ms"] for _, row in rows if row.get("latency_ms") is not None)
    return {
        "cases": len(rows),
        "outcomes": dict(Counter(row["status"] for _, row in rows)),
        "accuracy_when_answered": metric(row["selected"] == expected for expected, row in answered),
        "top_2": metric(expected in sorted(range(len(p)), key=p.__getitem__, reverse=True)[:2]
                        for expected, p in distribution_rows),
        "brier": metric(0.5 * sum((p - (i == expected)) ** 2 for i, p in enumerate(distribution))
                        for expected, distribution in distribution_rows),
        "distribution_count": len(distribution_rows),
        "false_confidence_rate": metric(row["selected"] != expected for expected, row in confident),
        "high_confidence_count": len(confident),
        "abstention_recall": metric(row["status"] == "abstained" for expected, row in rows if expected is None),
        "unnecessary_abstention_rate": metric(row["status"] == "abstained"
                                              for expected, row in rows if expected is not None),
        "latency_ms_mean": metric(latencies),
        "latency_ms_p95": latencies[math.ceil(len(latencies) * 0.95) - 1] if latencies else None,
        "cost_usd_mean": metric(row["cost_usd"] for _, row in rows if row.get("cost_usd") is not None),
        "input_tokens_mean": metric(row["input_tokens"] for _, row in rows if row.get("input_tokens") is not None),
        "correction_minutes_mean": metric(row["correction_minutes"] for _, row in rows
                                          if row.get("correction_minutes") is not None),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="JSON containing cases and route captures")
    capture = json.loads(parser.parse_args().capture.read_text())
    print(json.dumps(score(capture["cases"], capture["routes"]), indent=2, sort_keys=True))

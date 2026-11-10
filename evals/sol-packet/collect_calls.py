"""Read-only collector for the call telemetry (`|call=` suffix on routing_decisions.escalation_reason).

Run on the host that owns the database, with the service's Python:
    python evals/sol-packet/collect_calls.py [path/to/app.db] [--csv]
Opens the database read-only, prints one row per recorded call and a per-subject summary: calls, distinct reviewed
heads, and calls whose head equals the previous call's on the same subject (the 'repeat on an unchanged head' signal
the packet-calibration protocol needs), and, for write-lane submissions, the execution's final state from `estate_executions`
(a submission that failed, was interrupted or never started is not a completed review). It never writes, never reads any configuration file, and prints no free text.
"""
import csv
import json
import sqlite3
import sys
from collections import defaultdict


def load(db_path):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = con.execute("SELECT id, escalation_reason FROM routing_decisions WHERE instr(escalation_reason, '|call=') > 0")
    calls = []
    for decision_id, reason in rows:
        try:
            record = json.loads(reason.split("|call=", 1)[1])
        except ValueError:
            continue                                  # malformed suffix: skipped, never repaired
        if record.get("v") != 1 or not (record.get("launched") is True or record.get("submitted") is True):
            continue                                  # refusals and reuse are not calls
        calls.append({"decision_id": decision_id, "subject": record.get("subject"), "head_sha": record.get("head_sha"),
                      "function": record.get("function"), "started_at": record.get("started_at"),
                      "kind": "submitted" if record.get("submitted") else "launched", "execution_id": record.get("execution_id")})
    states = dict(con.execute("SELECT id, lifecycle_state FROM estate_executions"))    # exactness for write-lane submissions
    for call in calls:
        call["state"] = states.get(call["execution_id"]) if call["kind"] == "submitted" else "launched"
    return sorted(calls, key=lambda c: (c["subject"] or "", c["started_at"] or "", c["decision_id"]))


def summarise(calls):
    by_subject = defaultdict(list)
    for call in calls:
        by_subject[call["subject"]].append(call)
    summary = []
    for subject, items in by_subject.items():
        heads = [c["head_sha"] for c in items]
        repeats = sum(1 for a, b in zip(heads, heads[1:]) if a is not None and a == b)
        done = [c["head_sha"] for c in items if c["state"] in ("launched", "succeeded")]      # completed calls only
        done_repeats = sum(1 for a, b in zip(done, done[1:]) if a is not None and a == b)
        summary.append({"subject": subject, "calls": len(items), "distinct_heads": len({h for h in heads if h}),
                        "unchanged_head_repeats": repeats, "untagged_calls": sum(1 for h in heads if h is None),
                        "succeeded": len(done), "unchanged_head_repeats_among_succeeded": done_repeats})
    return summary


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    calls = load(args[0] if args else "data/app.db")
    out = csv.writer(sys.stdout)
    if "--csv" in sys.argv:
        out.writerow(["decision_id", "subject", "head_sha", "function", "started_at", "kind", "execution_id", "state"])
        for c in calls:
            out.writerow([c[k] for k in ("decision_id", "subject", "head_sha", "function", "started_at", "kind", "execution_id", "state")])
    else:
        print(f"recorded calls: {len(calls)}")
        for row in summarise(calls):
            print(row)

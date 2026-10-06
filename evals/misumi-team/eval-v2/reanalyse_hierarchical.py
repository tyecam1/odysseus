#!/usr/bin/env python3
"""-11 evaluation v2: hierarchical re-analysis of the paired differences (added after the independent Sol review of 2026-10-06).

PREREGISTRATION.md says the 95% intervals for team-minus-solo differences use a "paired bootstrap (resampling tasks and runs)".
analyse.py / compare3.py resample the flat list of 96 task x run cells as if they were independent, which treats the 12 repeated runs of
one task as 12 independent pieces of task evidence and so understates the uncertainty (there are only 8 tasks). This script resamples
TASKS with replacement, then RUNS within each chosen task (paired across conditions: the same run index), which is the pre-registered
reading. The original outputs (data/analysis-*.txt) are kept unchanged; this script's output is data/analysis-hierarchical.txt.

Usage: python reanalyse_hierarchical.py data/judged-qwen.jsonl [data/judged-llama.jsonl ...] > data/analysis-hierarchical.txt
"""
import json
import random
import sys
from collections import defaultdict

REPS = 4000
SEED = 7
PAIRS = (("team", "solo"), ("teamfix", "solo"), ("teamdrop", "solo"), ("teamdrop", "team"), ("teamdrop", "teamfix"), ("teamfix", "team"))


def read_jsonl(path):
    with open(path, encoding="utf-8-sig") as handle:
        return [json.loads(line.strip().lstrip("﻿")) for line in handle if line.strip()]


def cell_table(rows, kind):
    """{task: {run: {condition: 0/1}}} for usable verdicts of one prompt kind."""
    table = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        if row["kind"] != kind or row["flags_issue"] is None:
            continue
        value = bool(row["flags_issue"]) if kind == "conflict" else bool(row["flags_issue"] or row["unfounded_concern"])
        table[row["task"]][row["run"]][row["condition"]] = 1 if value else 0
    return table


def point(table, a, b):
    diffs = [cond[a] - cond[b] for runs in table.values() for cond in runs.values() if a in cond and b in cond]
    return 100 * sum(diffs) / len(diffs) if diffs else None


def hierarchical(table, a, b, reps=REPS, seed=SEED):
    tasks = [t for t, runs in table.items() if any(a in c and b in c for c in runs.values())]
    paired = {t: [c[a] - c[b] for c in table[t].values() if a in c and b in c] for t in tasks}
    rng = random.Random(seed)
    draws = []
    for _ in range(reps):
        total = n = 0
        for t in (tasks[rng.randrange(len(tasks))] for _ in tasks):
            runs = paired[t]
            for _ in runs:
                total += runs[rng.randrange(len(runs))]
                n += 1
        draws.append(100 * total / n)
    draws.sort()
    return draws[int(0.025 * reps)], draws[int(0.975 * reps)]


def flat(table, a, b, reps=REPS, seed=7):
    diffs = [c[a] - c[b] for runs in table.values() for c in runs.values() if a in c and b in c]
    rng = random.Random(seed)
    draws = sorted(100 * sum(diffs[rng.randrange(len(diffs))] for _ in diffs) / len(diffs) for _ in range(reps))
    return draws[int(0.025 * reps)], draws[int(0.975 * reps)]


def main():
    for path in sys.argv[1:]:
        rows = read_jsonl(path)
        print(f"\n### {path}: {len(rows)} judged rows")
        for kind, label in (("conflict", "detection on CONFLICT prompts"), ("clean", "false alarm on CLEAN prompts")):
            table = cell_table(rows, kind)
            print(f"- {label} ({len(table)} tasks x runs per task: {sorted({len(r) for r in table.values()})})")
            for a, b in PAIRS:
                p = point(table, a, b)
                if p is None:
                    continue
                hl, hh = hierarchical(table, a, b)
                fl, fh = flat(table, a, b)
                print(f"  {a} minus {b}: {p:+.1f} pts | hierarchical (tasks, then runs) 95% CI {hl:+.1f} to {hh:+.1f} | flat cells CI {fl:+.1f} to {fh:+.1f}")


if __name__ == "__main__":
    main()

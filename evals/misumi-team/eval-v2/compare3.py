#!/usr/bin/env python3
"""-11 evaluation v2 follow-up: solo vs team vs team-after-fix (teamfix: OK summarised) vs teamdrop (OK dropped) on the SAME pre-registered task set (not a replacement for the
pre-registered verdict; a documented follow-up measured after a fix aimed at the false-alarm mechanism the evaluation exposed).

Usage: python compare3.py --judged name=path.jsonl [name=path.jsonl ...] --rows solo.jsonl team.jsonl teamfix.jsonl
Per judge: detection on CONFLICT prompts and false alarm on CLEAN prompts per condition (Wilson 95%), paired-bootstrap differences
teamfix-solo and teamfix-team, and the supports' RISK-flag rate. Condition names come from the rows' `condition` field.
"""
import argparse
import json
import random
import statistics
from collections import defaultdict
from importlib.machinery import SourceFileLoader
from pathlib import Path

ORDER = ["solo", "team", "teamfix", "teamdrop"]
an = SourceFileLoader("analyse", str(Path(__file__).with_name("analyse.py"))).load_module()


def paired(cells, a, b, reps=4000, seed=11):
    pairs = [(c[a], c[b]) for c in cells.values() if a in c and b in c]
    if not pairs:
        return None
    rng = random.Random(seed)
    diffs = sorted(100 * sum(x - y for x, y in (pairs[rng.randrange(len(pairs))] for _ in pairs)) / len(pairs) for _ in range(reps))
    return 100 * sum(x - y for x, y in pairs) / len(pairs), diffs[int(0.025 * reps)], diffs[int(0.975 * reps)], len(pairs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judged", nargs="+", required=True)
    ap.add_argument("--rows", nargs="+", required=True)
    args = ap.parse_args()
    rows = [r for p in args.rows for r in an.read_jsonl(p)]
    conditions = sorted({r["condition"] for r in rows}, key=lambda c: ORDER.index(c) if c in ORDER else 9)
    for spec in args.judged:
        name, path = spec.split("=", 1)
        judged = an.read_jsonl(path)
        print(f"\n### judge: {name} ({len(judged)} rows, {sum(1 for r in judged if r['flags_issue'] is None)} unusable)")
        detect = an.cells(judged, "conflict", "flag")
        alarm = an.cells(judged, "clean", "flag")
        for c in conditions:
            dk, dn = an.rate(detect, c)
            fk, fn = an.rate(alarm, c)
            print(f"- {c}: detection {an.fmt(dk, dn)}; false alarm on clean {an.fmt(fk, fn)}")
        for a, b in (("teamfix", "solo"), ("teamfix", "team"), ("teamdrop", "solo"), ("teamdrop", "team"), ("teamdrop", "teamfix")):
            if a in conditions and b in conditions:
                d, f = paired(detect, a, b), paired(alarm, a, b)
                if d and f:
                    print(f"- {a} minus {b}: detection {d[0]:+.1f} pts (95% CI {d[1]:+.1f} to {d[2]:+.1f}); false alarm {f[0]:+.1f} pts (95% CI {f[1]:+.1f} to {f[2]:+.1f})")
    print("\n### supports' own RISK flag and latency")
    for c in conditions:
        if c == "solo":
            ms = [r["ms"] for r in rows if r["condition"] == c and r["http"] == 200]
            print(f"- solo: median latency {statistics.median(ms):.0f} ms")
            continue
        for kind in ("conflict", "clean"):
            flags = [s["raised_risk"] for r in rows if r["condition"] == c and r["kind"] == kind for s in r["supports"] if s["status"] == "ok"]
            print(f"- {c} {kind}: RISK opened in {an.fmt(sum(flags), len(flags))} ok consults")
        ms = [r["ms"] for r in rows if r["condition"] == c and r["http"] == 200]
        print(f"- {c}: median latency {statistics.median(ms):.0f} ms; non-model replies {sum(1 for r in rows if r['condition'] == c and r['source'] != 'model')}")


if __name__ == "__main__":
    main()

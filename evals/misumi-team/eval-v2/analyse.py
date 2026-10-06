#!/usr/bin/env python3
"""-11 evaluation v2, step 3: statistics and the PRE-REGISTERED decision rule (see PREREGISTRATION.md).

Usage: python analyse.py --rows solo.jsonl team.jsonl --primary judged-aoteru.jsonl --secondary judged-ollama.jsonl [--json out.json]

Reports per judge: detection on CONFLICT prompts and false-alarm on CLEAN prompts per condition (Wilson 95% intervals), the
team-minus-solo differences with paired-bootstrap 95% intervals (resampling task x run cells), the supports' own RISK-flag rate on
conflict vs clean, per-task detection, median latency, and Cohen's kappa between the two judges. Unjudged rows (judge failure) are
excluded and counted, never guessed.
"""
import argparse
import json
import math
import random
import statistics
from collections import defaultdict


def read_jsonl(path):
    out = []
    with open(path, encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip().lstrip("﻿")
            if line:
                out.append(json.loads(line))
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def fmt(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.0f}% (95% CI {100 * lo:.0f}-{100 * hi:.0f}%)" if n else "0/0"


def kappa(pairs):
    if not pairs:
        return float("nan")
    n = len(pairs)
    po = sum(1 for a, b in pairs if a == b) / n
    pa = sum(1 for a, _ in pairs if a) / n
    pb = sum(1 for _, b in pairs if b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def cells(judged, kind, metric):
    """{(task, run): {condition: 0/1}} for rows of this kind with a usable verdict."""
    out = defaultdict(dict)
    for row in judged:
        if row["kind"] != kind:
            continue
        if kind == "conflict":
            value = row["flags_issue"]
        else:  # clean: a false alarm is flagging a non-issue OR raising an unfounded concern
            value = None if row["flags_issue"] is None else bool(row["flags_issue"] or row["unfounded_concern"])
        if metric == "concern":
            value = row["unfounded_concern"]
        if value is None:
            continue
        out[(row["task"], row["run"])][row["condition"]] = 1 if value else 0
    return out


def rate(cell_map, condition):
    vals = [c[condition] for c in cell_map.values() if condition in c]
    return sum(vals), len(vals)


def paired_diff(cell_map, reps=4000, seed=7):
    pairs = [(c["team"], c["solo"]) for c in cell_map.values() if "team" in c and "solo" in c]
    if not pairs:
        return None
    rng = random.Random(seed)
    diffs = []
    for _ in range(reps):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        diffs.append(100 * (sum(t for t, _ in sample) - sum(s for _, s in sample)) / len(sample))
    diffs.sort()
    point = 100 * (sum(t for t, _ in pairs) - sum(s for _, s in pairs)) / len(pairs)
    return point, diffs[int(0.025 * reps)], diffs[int(0.975 * reps)], len(pairs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", nargs="+", required=True)
    ap.add_argument("--primary", required=True)
    ap.add_argument("--secondary", required=True)
    ap.add_argument("--json", default="")
    ap.add_argument("--primary-label", default="PRIMARY (independent family)")
    ap.add_argument("--secondary-label", default="SECONDARY (same family as subject)")
    args = ap.parse_args()
    rows = [r for p in args.rows for r in read_jsonl(p)]
    result = {"judges": {}}
    lines = []
    for label, path in ((args.primary_label, args.primary), (args.secondary_label, args.secondary)):
        judged = read_jsonl(path)
        unjudged = sum(1 for r in judged if r["flags_issue"] is None)
        lines.append(f"\n### {label}: {len(judged)} judged rows, {unjudged} unusable verdicts excluded")
        block = {}
        for condition in ("solo", "team"):
            ck, cn = rate(cells(judged, "conflict", "flag"), condition)
            fk, fn = rate(cells(judged, "clean", "flag"), condition)
            uk, un = rate(cells(judged, "conflict", "concern"), condition)
            lines.append(f"- {condition}: detection on CONFLICT prompts {fmt(ck, cn)}; false alarm on CLEAN prompts {fmt(fk, fn)}; unfounded-concern on CONFLICT prompts {fmt(uk, un)}")
            block[condition] = {"detection": [ck, cn], "false_alarm": [fk, fn], "unfounded_on_conflict": [uk, un]}
        d = paired_diff(cells(judged, "conflict", "flag"))
        f = paired_diff(cells(judged, "clean", "flag"))
        if d:
            lines.append(f"- detection, team minus solo: {d[0]:+.1f} points (95% bootstrap CI {d[1]:+.1f} to {d[2]:+.1f}, {d[3]} paired cells)")
            block["detection_diff"] = d
        if f:
            lines.append(f"- false alarm on clean, team minus solo: {f[0]:+.1f} points (95% bootstrap CI {f[1]:+.1f} to {f[2]:+.1f}, {f[3]} paired cells)")
            block["false_alarm_diff"] = f
        per_task = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        for row in judged:
            if row["kind"] == "conflict" and row["flags_issue"] is not None:
                per_task[row["task"]][row["condition"]][1] += 1
                per_task[row["task"]][row["condition"]][0] += 1 if row["flags_issue"] else 0
        lines.append("- per task detection team/solo: " + ", ".join(
            f"{t} {per_task[t]['team'][0]}/{per_task[t]['team'][1]} vs {per_task[t]['solo'][0]}/{per_task[t]['solo'][1]}" for t in sorted(per_task)))
        result["judges"][label] = block
        if label == args.primary_label:
            primary = block
        result.setdefault("_judged", {})[label[:7]] = judged
    # supports' RISK flag
    lines.append("\n### Supports' own RISK flag (team condition only)")
    for kind in ("conflict", "clean"):
        flags = [s["raised_risk"] for r in rows if r["condition"] == "team" and r["kind"] == kind for s in r["supports"] if s["status"] == "ok"]
        lines.append(f"- {kind} prompts: RISK opened by the support in {fmt(sum(flags), len(flags))} ok consults")
    for condition in ("solo", "team"):
        ms = [r["ms"] for r in rows if r["condition"] == condition and r["http"] == 200]
        formed = sum(1 for r in rows if r["condition"] == condition and r["team_decision"] == "team")
        degraded = sum(1 for r in rows if r["condition"] == condition and r["source"] != "model")
        lines.append(f"- {condition}: median latency {statistics.median(ms):.0f} ms over {len(ms)} replies; teams formed {formed}; non-model replies {degraded}")
    # judge agreement
    prim = {(r["condition"], r["task"], r["kind"], r["run"]): r for r in read_jsonl(args.primary)}
    sec = {(r["condition"], r["task"], r["kind"], r["run"]): r for r in read_jsonl(args.secondary)}
    agree_flag = [(prim[k]["flags_issue"], sec[k]["flags_issue"]) for k in prim if k in sec and prim[k]["flags_issue"] is not None and sec[k]["flags_issue"] is not None]
    agree_concern = [(prim[k]["unfounded_concern"], sec[k]["unfounded_concern"]) for k in prim if k in sec and prim[k]["unfounded_concern"] is not None and sec[k]["unfounded_concern"] is not None]
    k_flag, k_con = kappa(agree_flag), kappa(agree_concern)
    lines.append(f"\n### Judge agreement: kappa(flags_issue) = {k_flag:.2f} over {len(agree_flag)} rows; kappa(unfounded_concern) = {k_con:.2f} over {len(agree_concern)} rows")
    # pre-registered verdict (PRIMARY judge)
    det, fa = primary.get("detection_diff"), primary.get("false_alarm_diff")
    verdict = "no verdict (missing data)"
    if det and fa:
        helps = det[0] >= 15 and det[1] > 0
        fa_ok = fa[0] <= 5 and fa[2] <= 10
        if helps and fa_ok:
            verdict = "SHOWN TO HELP (detection up by >=15 points, CI excludes 0, and false-alarm increase within the limit)"
        elif det[0] > 0 and det[1] > 0 and not fa_ok:
            verdict = "SENSITIVITY GAINED AT THE PRICE OF FALSE ALARMS (not a net improvement)"
        elif det[0] > 0 and det[1] > 0:
            verdict = "detection up but below the pre-registered 15-point bar: NOT SHOWN to help enough"
        else:
            verdict = "NOT SHOWN"
        if min(k_flag, k_con) < 0.6:
            verdict += "; judges disagree materially (kappa < 0.6): conclusion capped at INDICATIVE"
    lines.append(f"\n### Pre-registered verdict: {verdict}")
    print("\n".join(lines))
    if args.json:
        result.pop("_judged", None)
        result["kappa"] = {"flags_issue": k_flag, "unfounded_concern": k_con}
        result["verdict"] = verdict
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=1, default=list)


if __name__ == "__main__":
    main()

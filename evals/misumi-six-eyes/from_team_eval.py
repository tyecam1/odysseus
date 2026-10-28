#!/usr/bin/env python3
"""Six Eyes on real completed-task evidence: the -11 team evaluation v2 (solo vs team vs teamfix vs teamdrop).

Feeds ``src/efficiency_pareto.py`` (arithmetic only) from records someone else collected: the 192 replies per condition in
``evals/misumi-team/eval-v2/data`` with their blind judge verdicts and measured turn latency. It generates nothing and fills
nothing: a reply with no verdict from the chosen judge is dropped and counted, never guessed.

Definition of "verified" (the evaluation's own, per judge): on a planted-conflict prompt the reply explicitly flags the issue; on its
clean twin it neither flags an issue nor raises an unfounded concern. Cost: turn latency in seconds (``ms``), which already includes
the support consultations. The evaluation recorded no token or paid cost, and no safety floor beyond correctness, so those units are
absent rather than invented (``safety_ok`` is True for every row because this evaluation defined no separate floor).

    python evals/misumi-six-eyes/from_team_eval.py [--out report.md]
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src import efficiency_pareto as ep  # noqa: E402

DATA = REPO / "evals" / "misumi-team" / "eval-v2" / "data"
PLANS = ("solo", "team", "teamfix", "teamdrop")
JUDGES = {"qwen": "judged-qwen.jsonl", "llama": "judged-llama.jsonl"}  # qwen3:8b validated better (94% vs 58% agreement with the audit)
SEED = 1


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def key(row):
    return (row["condition"], row["task"], row["kind"], int(row["run"]))


def verified_by(kind, verdict):
    """The evaluation's own correctness definition for one judged reply."""
    if kind == "conflict":
        return bool(verdict["flags_issue"])
    if kind == "clean":
        return not verdict["flags_issue"] and not verdict["unfounded_concern"]
    raise ValueError(f"unknown prompt kind {kind!r}")


def build_records(replies, judged):
    """Records for one judge. Returns (records, dropped) where dropped counts replies with no verdict, per plan."""
    verdicts = {}
    for row in judged:
        if key(row) in verdicts:
            raise ValueError(f"duplicate verdict for {key(row)}")
        verdicts[key(row)] = row
    rows, dropped = [], {}
    for reply in replies:
        k = key(reply)
        verdict = verdicts.get(k)
        latency = reply.get("ms")
        if str(reply.get("http")) != "200":
            latency = None
        if verdict is None or not isinstance(latency, (int, float)) or isinstance(latency, bool):
            dropped[reply["condition"]] = dropped.get(reply["condition"], 0) + 1
            continue
        rows.append({
            "task_id": f"{reply['task']}/{reply['kind']}/{int(reply['run'])}",
            "plan": reply["condition"],
            "verified": verified_by(reply["kind"], verdict),
            "safety_ok": True,
            "costs": {"latency_seconds": latency / 1000.0},
        })
    return ep.parse(rows), dropped


def words(plan, verdict):
    """Plain wording: compare() calls the plan 'a' and solo 'b'."""
    return {"a_better": f"{plan} better", "b_better": "solo better", "inconclusive": "inconclusive",
            "insufficient": "insufficient evidence", "safety_violation": "safety violation"}[verdict]


def verdicts(records):
    return {(plan, metric): words(plan, ep.compare(records, plan, "solo", metric, SEED)["verdict"])
            for plan in PLANS[1:] for metric in ("verified", "latency_seconds")}


def pct(x):
    return f"{100 * x:.1f}%"


def judge_section(name, replies, judged):
    records, dropped = build_records(replies, judged)
    dims = ("latency_seconds",)
    summary = ep.summarise(records, dims, SEED)
    lines = [f"### Judge: {name}", "",
             "| plan | matched rows | verified | 95% interval | mean latency (s) | dropped (no verdict) |", "|---|---|---|---|---|---|"]
    for plan in PLANS:
        s = summary.get(plan)
        if s is None:
            lines.append(f"| {plan} | 0 | n/a | n/a | n/a | {dropped.get(plan, 0)} |")
            continue
        lo, hi = s["verified_interval"]
        lines.append(f"| {plan} | {s['tasks']} | {pct(s['verified_rate'])} | {pct(lo)} to {pct(hi)} | "
                     f"{s['means'].get('latency_seconds', float('nan')):.2f} | {dropped.get(plan, 0)} |")
    lines += ["", "Matched-task differences versus `solo` (task-level seeded bootstrap; positive verified = plan better):", "",
              "| plan | metric | difference | 95% interval | verdict |", "|---|---|---|---|---|"]
    for plan in PLANS[1:]:
        for metric in ("verified", "latency_seconds"):
            c = ep.compare(records, plan, "solo", metric, SEED)
            if c["interval"] is None:
                lines.append(f"| {plan} | {metric} | n/a | n/a | {words(plan, c['verdict'])} ({c['matched_tasks']} matched) |")
            else:
                scale = 100 if metric == "verified" else 1
                unit = " pts" if metric == "verified" else " s"
                lines.append(f"| {plan} | {metric} | {c['difference'] * scale:+.2f}{unit} | {c['interval'][0] * scale:+.2f} to "
                             f"{c['interval'][1] * scale:+.2f} | {words(plan, c['verdict'])} ({c['matched_tasks']} matched) |")
    front = ep.pareto_front(records, dims, seed=SEED)
    lines += ["", f"Pareto front on (verified up, latency down), {front['common_tasks']} tasks common to all surviving plans: "
              f"**{', '.join(front['front']) or 'none'}**; dominated: {front['dominated'] or 'none'}; excluded: {front['excluded'] or 'none'}.", ""]
    return "\n".join(lines)


def report():
    replies = []
    for plan in PLANS:
        replies += load_jsonl(DATA / f"replies-{plan}.jsonl")
    per_judge = {name: verdicts(build_records(replies, load_jsonl(DATA / filename))[0]) for name, filename in JUDGES.items()}
    out = ["# Six Eyes on the -11 team evaluation v2 (real completed-task evidence)", "",
           "Generated by `evals/misumi-six-eyes/from_team_eval.py` from `evals/misumi-team/eval-v2/data/` (192 replies per condition, "
           "8 conflict/clean prompt pairs x 12 runs). Deterministic: the bootstrap is seeded.", "",
           "## What this can and cannot say", "",
           "- Only a solo-versus-team question over one task family (household planning) with turn latency as the only recorded cost. "
           "No tokens, paid cost or compute seconds were recorded, so none are compared; nothing is summed across units.",
           "- `teamfix` and `teamdrop` were chosen after seeing the `team` data (post-hoc) on the same tasks: not independent confirmation.",
           "- The two blind judges agree poorly (kappa 0.34 and 0.14 in RESULTS.md), and the more accurate one (qwen3:8b, 94% agreement "
           "with the 48-row AI audit) is the same model family as the subject. Every conclusion is therefore indicative, and the verdict "
           "should be read only where both judges agree.",
           "- Not covered: a cheap-first escalating baseline, a strong-solo-plus-verifier baseline, a deterministic-tool plan and the "
           "optimiser itself; there are no real matched records for them yet. Team size is not a success metric.", "",
           "## Results", ""]
    out += ["### Where the two judges agree (versus `solo`)", "", "| plan | verified quality | latency |", "|---|---|---|"]
    names = list(JUDGES)
    for plan in PLANS[1:]:
        cells = []
        for metric in ("verified", "latency_seconds"):
            seen = {per_judge[n][(plan, metric)] for n in names}
            cells.append(next(iter(seen)) if len(seen) == 1 else "judges disagree: " + " / ".join(f"{n}: {per_judge[n][(plan, metric)]}" for n in names))
        out.append(f"| {plan} | {cells[0]} | {cells[1]} |")
    out.append("")
    for name, filename in JUDGES.items():
        out.append(judge_section(name, replies, load_jsonl(DATA / filename)))
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    text = report()
    if args.out:
        args.out.write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

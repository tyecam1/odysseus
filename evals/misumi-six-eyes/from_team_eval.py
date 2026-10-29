#!/usr/bin/env python3
"""Six Eyes on real completed-task evidence: the -11 team evaluation v2 (solo vs team vs teamfix vs teamdrop).

Feeds ``src/efficiency_pareto.py`` (arithmetic only) from records someone else collected: the 192 replies per condition in
``evals/misumi-team/eval-v2/data`` with their blind judge verdicts and measured turn latency. It generates nothing and fills
nothing: a reply with no verdict from the chosen judge is dropped and counted, never guessed.

Definition of "verified" (the evaluation's own, per judge): on a planted-conflict prompt the reply explicitly flags the issue; on its
clean twin it neither flags an issue nor raises an unfounded concern. Cost: turn latency in seconds (``ms``), which already includes
the support consultations. The evaluation recorded no token or paid cost, and measured no safety dimension, so those units are
absent rather than invented and ``safety_ok`` is None (UNMEASURED, not a pass).

Inference (corrected 2026-10-28): the 192 replies per condition are 12 repeated runs of 8 underlying tasks, so every record names its
task as its ``cluster``. Intervals are paired hierarchical bootstraps (tasks, then runs) and the evidence floor counts the 8 distinct
tasks, never the 192 runs, as ``evals/misumi-team/eval-v2/reanalyse_hierarchical.py`` established. Detection on conflict prompts,
false alarms on clean prompts and the pooled composite are reported separately. The earlier report
(``results/2026-10-28-team-eval-v2.md``) is kept as provenance and is superseded by the one this script writes.

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
VIEWS = (("composite", None, "pooled composite (detection on conflict prompts and no false alarm on clean ones)"),
         ("conflict", "conflict", "conflict detection (the reply flags the planted issue)"),
         ("clean", "clean", "clean-task false-alarm avoidance (no issue and no unfounded concern raised)"))


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


def build_records(replies, judged, kind=None):
    """Records for one judge. Returns (records, dropped) where dropped counts replies with no verdict, per plan.
    ``kind`` restricts to "conflict" or "clean" prompts; None keeps both (the pooled composite)."""
    verdicts = {}
    for row in judged:
        if key(row) in verdicts:
            raise ValueError(f"duplicate verdict for {key(row)}")
        verdicts[key(row)] = row
    rows, dropped = [], {}
    for reply in replies:
        if kind is not None and reply["kind"] != kind:
            continue
        verdict = verdicts.get(key(reply))
        latency = reply.get("ms")
        if str(reply.get("http")) != "200":
            latency = None
        if verdict is None or verdict.get("flags_issue") is None or not isinstance(latency, (int, float)) or isinstance(latency, bool):
            dropped[reply["condition"]] = dropped.get(reply["condition"], 0) + 1
            continue
        rows.append({
            "task_id": f"{reply['task']}/{reply['kind']}/{int(reply['run'])}",
            "cluster": str(reply["task"]),
            "plan": reply["condition"],
            "verified": verified_by(reply["kind"], verdict),
            "safety_ok": None,  # this evaluation measured no safety dimension: unmeasured, not a pass
            "costs": {"latency_seconds": latency / 1000.0},
        })
    return ep.parse(rows), dropped


def words(plan, verdict):
    """Plain wording: compare() calls the plan 'a' and solo 'b'."""
    return {"a_better": f"{plan} better", "b_better": "solo better", "inconclusive": "inconclusive",
            "insufficient": "insufficient evidence", "safety_violation": "safety violation"}[verdict]


def indicative_words(plan, c):
    """Below the distinct-task floor every verdict is 'insufficient'; the cluster-aware interval is still shown, labelled indicative."""
    if c["verdict"] != "insufficient":
        return words(plan, c["verdict"])
    if c["indicative"] is None:
        return "insufficient evidence"
    return f"indicative only: {words(plan, c['indicative']['direction'])}"


def interval_cells(c, scale, unit):
    cell = c["indicative"] if c["interval"] is None else {"difference": c["difference"], "interval": c["interval"]}
    if cell is None:
        return "n/a", "n/a"
    return (f"{cell['difference'] * scale:+.2f}{unit}", f"{cell['interval'][0] * scale:+.2f} to {cell['interval'][1] * scale:+.2f}")


def verdicts(records):
    return {(plan, metric): indicative_words(plan, ep.compare(records, plan, "solo", metric, SEED))
            for plan in PLANS[1:] for metric in ("verified", "latency_seconds")}


def pct(x):
    return f"{100 * x:.1f}%"


def agreement(records_a, records_b, plan):
    """Raw agreement and Cohen's kappa between two judges' verified labels for one plan, over the replies both judged."""
    a = {r.task_id: r.verified for r in records_a if r.plan == plan}
    b = {r.task_id: r.verified for r in records_b if r.plan == plan}
    shared = sorted(set(a) & set(b))
    if not shared:
        return None
    n = len(shared)
    observed = sum(a[t] == b[t] for t in shared) / n
    pa, pb = sum(a[t] for t in shared) / n, sum(b[t] for t in shared) / n
    chance = pa * pb + (1 - pa) * (1 - pb)
    return {"n": n, "agreement": observed, "kappa": None if chance >= 1 else (observed - chance) / (1 - chance)}


def judge_section(name, replies, judged, kind, label):
    records, dropped = build_records(replies, judged, kind)
    dims = ("latency_seconds",)
    summary = ep.summarise(records, dims, SEED)
    lines = [f"#### Judge {name}: {label}", "",
             "| plan | distinct tasks | task-runs | verified | 95% interval (hierarchical) | mean latency (s) | dropped (no verdict) |",
             "|---|---|---|---|---|---|---|"]
    for plan in PLANS:
        s = summary.get(plan)
        if s is None:
            lines.append(f"| {plan} | 0 | 0 | n/a | n/a | n/a | {dropped.get(plan, 0)} |")
            continue
        lo, hi = s["verified_interval"]
        lines.append(f"| {plan} | {s['unique_tasks']} | {s['tasks']} | {pct(s['verified_rate'])} | {pct(lo)} to {pct(hi)} | "
                     f"{s['means'].get('latency_seconds', float('nan')):.2f} | {dropped.get(plan, 0)} |")
    lines += ["", "Paired differences versus `solo` (resampling tasks, then runs; positive verified = plan better). "
              f"The evidence floor is {ep.MIN_MATCHED_TASKS} distinct tasks, so every reading below is indicative only:", "",
              "| plan | metric | difference | 95% interval | reading |", "|---|---|---|---|---|"]
    for plan in PLANS[1:]:
        for metric in ("verified", "latency_seconds"):
            c = ep.compare(records, plan, "solo", metric, SEED)
            scale, unit = (100, " pts") if metric == "verified" else (1, " s")
            diff, interval = interval_cells(c, scale, unit)
            lines.append(f"| {plan} | {metric} | {diff} | {interval} | {indicative_words(plan, c)} ({c['matched_tasks']} tasks, {c['matched_runs']} runs) |")
    front = ep.pareto_front(records, dims, seed=SEED)
    verdict = "insufficient evidence, no front" if front["insufficient"] else ", ".join(front["front"]) or "none"
    lines += ["", f"Pareto front on (verified up, latency down): {front['common_tasks']} distinct tasks ({front['common_runs']} runs) common to all "
              f"surviving plans; **{verdict}**; dominated: {front['dominated'] or 'none'}; excluded: {front['excluded'] or 'none'}.", ""]
    return "\n".join(lines)


def report():
    replies = []
    for plan in PLANS:
        replies += load_jsonl(DATA / f"replies-{plan}.jsonl")
    judged = {name: load_jsonl(DATA / filename) for name, filename in JUDGES.items()}
    names = list(JUDGES)
    out = ["# Six Eyes on the -11 team evaluation v2 (real completed-task evidence), cluster-aware", "",
           "Generated by `evals/misumi-six-eyes/from_team_eval.py` from `evals/misumi-team/eval-v2/data/` (192 replies per condition = "
           "8 distinct conflict/clean task pairs x 12 repeated runs x 2 prompt kinds). Deterministic: the bootstrap is seeded. "
           "Supersedes `2026-10-28-team-eval-v2.md`, which resampled the runs as if each were an independent task.", "",
           "## What this can and cannot say", "",
           "- **8 distinct tasks, many runs.** Repeated runs of one task are clustered. Intervals resample tasks and then runs; the "
           f"evidence floor counts distinct tasks and {ep.MIN_MATCHED_TASKS} are required, so no verdict is established here. Readings "
           "labelled indicative are for orientation and never a basis for a routing or policy change.",
           "- Only a solo-versus-team question over one task family (household planning) with turn latency as the only recorded cost. "
           "No tokens, paid cost or compute seconds were recorded, so none are compared; nothing is summed across units.",
           "- **Safety was not measured.** The evaluation defined no safety floor beyond correctness, so safety is unmeasured "
           "(`safety_ok` is None). The absence of a violation count here is not evidence of safety.",
           "- `teamfix` and `teamdrop` were chosen after seeing the `team` data (post-hoc) on the same tasks: not independent confirmation.",
           "- The two blind judges agree poorly (kappa 0.34 and 0.14 in RESULTS.md), and the more accurate one (qwen3:8b, 94% agreement "
           "with the 48-row AI audit) is the same model family as the subject. Treat a reading as stable only where both judges give the "
           "same one; the disagreement is tabulated at the end.",
           "- Not covered: a cheap-first escalating baseline, a strong-solo-plus-verifier baseline, a deterministic-tool plan and the "
           "optimiser itself; there are no real matched records for them yet. Team size is not a success metric.", "",
           "## Results", ""]
    for view, kind, label in VIEWS:
        per_judge = {n: verdicts(build_records(replies, judged[n], kind)[0]) for n in names}
        out += [f"### {view}: {label}", "", "Where the two judges agree (versus `solo`, indicative):", "",
                "| plan | verified quality | latency |", "|---|---|---|"]
        for plan in PLANS[1:]:
            cells = []
            for metric in ("verified", "latency_seconds"):
                seen = {per_judge[n][(plan, metric)] for n in names}
                cells.append(next(iter(seen)) if len(seen) == 1 else "judges disagree: " + " / ".join(f"{n}: {per_judge[n][(plan, metric)]}" for n in names))
            out.append(f"| {plan} | {cells[0]} | {cells[1]} |")
        out.append("")
        for name in names:
            out.append(judge_section(name, replies, judged[name], kind, label))
    out += ["## Judge disagreement", "",
            "Raw agreement and Cohen's kappa between the two judges' verified labels, over the replies both judged "
            "(kappa is undefined where chance agreement is total):", "",
            "| view | plan | replies | agreement | kappa |", "|---|---|---|---|---|"]
    for view, kind, _ in VIEWS:
        recs = {n: build_records(replies, judged[n], kind)[0] for n in names}
        for plan in PLANS:
            a = agreement(recs[names[0]], recs[names[1]], plan)
            kappa = "n/a" if a is None or a["kappa"] is None else f"{a['kappa']:.2f}"
            out.append(f"| {view} | {plan} | {a['n'] if a else 0} | {pct(a['agreement']) if a else 'n/a'} | {kappa} |")
    out.append("")
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

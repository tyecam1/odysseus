#!/usr/bin/env python3
"""Offline allocation-decision evaluation: production routing + team formation vs baselines vs the shadow candidate.

Deterministic, no model or tool calls. Reads the ratified persona registry from a path (never copied into this repository), so the
canon used is identified by its SHA-256 in the report. See PREREGISTRATION.md for the question, rubric and acceptance rules; the
held-out corpus is meant to be run once after the candidate is frozen against the dev corpus.

    python evals/misumi-allocation/run_eval.py --personas PATH/personas.yaml [--corpus dev|heldout] [--out report.md]

Production's decision is derived from the real ``resolve_lead`` (v0.2) and ``plan_team`` with the real persona policy order.
"""

import argparse
import hashlib
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src import efficiency_pareto as ep  # noqa: E402
from src import misumi_allocation_shadow as shadow  # noqa: E402
from src.misumi_persona_routing import RESERVED  # noqa: E402
from src.misumi_policy import load_persona_policy  # noqa: E402
from src.misumi_routing_v02 import resolve_lead  # noqa: E402
from src.misumi_team_formation import plan_team  # noqa: E402

HERE = Path(__file__).resolve().parent
CORPORA = {"dev": "corpus-dev-v1.yaml", "heldout": "corpus-heldout-v1.yaml"}
POLICIES = ("production", "always_solo", "max_team", "candidate")
SEED = 1
# Rubric amendment 1 (2026-10-28, made after the dev run and BEFORE the held-out run; the frozen corpus file and its hash are untouched):
# a team needs a ratified consult edge, so these held-out cases, labelled `team` in error, cannot be teams. The report shows the
# corpus as frozen AND with these decisions amended to `solo`, and the as-frozen reading is the pre-registered one.
AMENDMENT_1 = {"h-res-4": "solo", "h-anom-7": "solo"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_cases(name):
    return yaml.safe_load((HERE / CORPORA[name]).read_text(encoding="utf-8"))["cases"]


class World:
    def __init__(self, personas_path):
        raw = yaml.safe_load(Path(personas_path).read_text(encoding="utf-8"))
        self.personas = raw.get("personas", raw)
        self.order = list(load_persona_policy())
        self.names = {p: str(self.personas[p].get("name") or p).split()[0] for p in self.order if p in self.personas}

    def edges(self, persona):
        return list((self.personas.get(persona) or {}).get("consults") or [])

    def intents(self, persona):
        return list(((self.personas.get(persona) or {}).get("routing") or {}).get("intents") or [])


def production(world, case):
    lead, routing = resolve_lead(case["prompt"], world.personas, case.get("prior_lead"))
    plan = plan_team(case["prompt"], lead, policy_order=world.order, display_names=world.names,
                     intents_of=world.intents, edges_of=world.edges)
    if "reserved:aoteru" in routing.get("reasons", []) or "reserved-matter" in plan["reasons"]:
        decision = "escalate"
    elif plan["supports"]:
        decision = "team"
    elif lead == shadow.HEAD:
        decision = "abstain"
    else:
        decision = "solo"
    return {"decision": decision, "lead": lead, "supports": [s["persona"] for s in plan["supports"]], "plan": plan}


def always_solo(world, case):
    out = production(world, case)
    if out["decision"] == "team":
        out.update(decision="solo", supports=[])
    return out


def max_team(world, case):
    out = production(world, case)
    if out["decision"] in ("solo", "team") and out["lead"] != shadow.HEAD:
        edges = {e.lower() for e in world.edges(out["lead"])}
        evidence = shadow.domain_evidence(case["prompt"], world.personas)
        supports = [p for p in world.order if p in edges and p in evidence and p not in (shadow.HEAD, out["lead"])][:2]
        if supports:
            out.update(decision="team", supports=supports)
    return out


def candidate(world, case):
    plan = production(world, case)["plan"]
    p = shadow.propose(case["prompt"], world.personas, prior_lead=case.get("prior_lead"), policy_order=world.order,
                       display_names=world.names, production_plan=plan)
    return {"decision": p["decision"], "lead": p["lead"], "supports": [s["persona"] for s in p["supports"]], "proposal": p}


RUNNERS = {"production": production, "always_solo": always_solo, "max_team": max_team, "candidate": candidate}


def score(case, got):
    exp = case["expect"]
    support_ok = got["decision"] != "team" or not exp.get("supports") or all(s in exp["supports"] for s in got["supports"])
    return {
        "decision": got["decision"] == exp["decision"] and (exp["decision"] != "team" or support_ok),
        "team_axis": (got["decision"] == "team") == (exp["decision"] == "team"),
        "lead": got["lead"] in exp["lead"],
    }


def compare_rows(results, cases, metric, a, b):
    rows = []
    for case in cases:
        for plan in (a, b):
            rows.append({"task_id": case["id"], "plan": plan, "verified": results[plan][case["id"]]["score"][metric], "safety_ok": None,
                         "costs": {"extra_model_calls": float(len(results[plan][case["id"]]["got"]["supports"]))}})
    return ep.compare(ep.parse(rows), a, b, "verified", SEED)


def pct(x):
    return f"{100 * x:.1f}%"


def fmt_interval(c):
    cell = c["interval"] and {"difference": c["difference"], "interval": c["interval"]} or c["indicative"]
    return "n/a" if not cell else f"{100 * cell['difference']:+.1f} pts ({100 * cell['interval'][0]:+.1f} to {100 * cell['interval'][1]:+.1f})"


def evaluate(world, cases):
    results = {p: {} for p in POLICIES}
    for plan, run in RUNNERS.items():
        for case in cases:
            got = run(world, case)
            results[plan][case["id"]] = {"got": got, "score": score(case, got)}
    return results


def amended(cases):
    out = []
    for case in cases:
        if case["id"] in AMENDMENT_1:
            case = {**case, "expect": {**case["expect"], "decision": AMENDMENT_1[case["id"]], "supports": []}}
        out.append(case)
    return out


def report(personas_path, corpus):
    world = World(personas_path)
    cases = load_cases(corpus)
    text = section(world, personas_path, corpus, cases, "as frozen (pre-registered reading)")
    if any(c["id"] in AMENDMENT_1 for c in cases):
        text += "\n" + section(world, personas_path, corpus, amended(cases), "rubric amendment 1 applied (sensitivity)", header=False)
    return text


def section(world, personas_path, corpus, cases, title, header=True):
    results = evaluate(world, cases)
    comparable = [c for c in cases if c["expect"].get("authority") != "blocked"]
    lines = [f"# Allocation-decision evaluation: {corpus} corpus, {title}", "",
             f"- corpus `{CORPORA[corpus]}` sha256 `{sha256(HERE / CORPORA[corpus])}` ({len(cases)} cases; {len(comparable)} comparable with production)",
             f"- persona registry `{Path(personas_path).name}` sha256 `{sha256(personas_path)}`",
             f"- candidate `{shadow.METHOD}`, live effect `{shadow.LIVE_EFFECT}`; offline, no model or tool calls",
             "- labels are the author's; an independent blinded relabel and a human audit are owed (PREREGISTRATION.md)", "",
             "## Accuracy by policy (comparable cases)", "", "| policy | A1 team-axis | A2 four-way decision | A3 lead | proposed extra model calls |", "|---|---|---|---|---|"]
    for plan in POLICIES:
        n = len(comparable)
        sc = {m: sum(results[plan][c["id"]]["score"][m] for c in comparable) / n for m in ("team_axis", "decision", "lead")}
        calls = sum(len(results[plan][c["id"]]["got"]["supports"]) for c in comparable)
        lines.append(f"| {plan} | {pct(sc['team_axis'])} | {pct(sc['decision'])} | {pct(sc['lead'])} | {calls} |")
    lines += ["", "## Candidate minus production (paired over distinct cases; positive = candidate better)", "",
              "| metric | difference (95% interval) | verdict at the pre-registered floor |", "|---|---|---|"]
    for metric, label in (("team_axis", "A1 team-axis"), ("decision", "A2 four-way decision"), ("lead", "A3 lead")):
        c = compare_rows(results, comparable, metric, "candidate", "production")
        lines.append(f"| {label} | {fmt_interval(c)} | {c['verdict']} ({c['matched_tasks']} cases) |")
    reserved = [c for c in cases if c["category"] == "reserved_tool"]
    s1 = all(results["candidate"][c["id"]]["got"]["decision"] == "escalate" for c in reserved)
    bad_support = [c["id"] for c in cases if RESERVED.search(c["prompt"]) and results["candidate"][c["id"]]["got"]["supports"]]
    lines += ["", "## Safety floor S1 (candidate)", "",
              f"- every reserved/tool-action case escalated: **{'yes' if s1 else 'NO'}** ({sum(results['candidate'][c['id']]['got']['decision'] == 'escalate' for c in reserved)}/{len(reserved)})",
              f"- supports proposed on a reserved matter: **{len(bad_support)}** {bad_support or ''}",
              "- authority invariance under persona choice: checked by `tests/test_misumi_allocation_shadow.py`", "",
              "## By category (A2 four-way decision)", "", "| category | n | " + " | ".join(POLICIES) + " |", "|---|---|" + "---|" * len(POLICIES)]
    for cat in sorted({c["category"] for c in cases}):
        group = [c for c in cases if c["category"] == cat]
        lines.append(f"| {cat} | {len(group)} | " + " | ".join(
            f"{sum(results[p][c['id']]['score']['decision'] for c in group)}/{len(group)}" for p in POLICIES) + " |")
    lines += ["", "## Cases where the candidate decision was wrong", "", "| id | prompt | expected | candidate | production |", "|---|---|---|---|---|"]
    for c in cases:
        if not results["candidate"][c["id"]]["score"]["decision"]:
            e, g, p = c["expect"], results["candidate"][c["id"]]["got"], results["production"][c["id"]]["got"]
            lines.append(f"| {c['id']} | {c['prompt']} | {e['decision']} | {g['decision']} {g['supports'] or ''} (lead {g['lead']}) | {p['decision']} {p['supports'] or ''} (lead {p['lead']}) |")
    lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--personas", required=True)
    ap.add_argument("--corpus", choices=sorted(CORPORA), default="dev")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    text = report(args.personas, args.corpus)
    if args.out:
        args.out.write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

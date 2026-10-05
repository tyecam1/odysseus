#!/usr/bin/env python3
"""Measure lead-persona routers against the labelled Misumi routing corpus (application -09).

Reports, per directive category and overall, how often each router picks the persona a sensible
household user would intend (``intended``; ``--lenient`` also accepts ``acceptable``), a mechanical
failure taxonomy for the baseline, and the regressions a candidate would introduce.

Routers measured:
  * ``baseline``  - src.misumi_persona_routing.resolve_auto_lead (ratified contract v0.1, what runs today)
  * ``candidate`` - src.misumi_routing_candidates.resolve_candidate_lead (PROPOSAL, never wired)

This script writes nothing; it only prints (text, or JSON with ``--json``).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.misumi_persona_routing import resolve_auto_lead  # noqa: E402
from src.misumi_routing_candidates import resolve_candidate_lead  # noqa: E402

CORPUS_DIR = ROOT / "evals" / "misumi-routing"
SPLITS = {"dev": "corpus-dev-v1.yaml", "heldout": "corpus-heldout-v1.yaml"}


def load_corpus(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    ids = [item["id"] for item in data["items"]]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate item ids in {path.name}")
    return data


def manifest_from(corpus: dict[str, Any]) -> dict[str, Any]:
    return {
        pid: {"routing": {"intents": [w.strip() for w in intents.split(",")]}}
        for pid, intents in corpus["reference_intents"].items()
    }


def _matched_personas(prompt: str, manifest: dict[str, Any]) -> list[str]:
    from src.misumi_persona_routing import _keyword_present

    hits = []
    for pid, persona in manifest.items():
        intents = persona["routing"]["intents"]
        if any(i != "default" and _keyword_present(prompt, i) for i in intents):
            hits.append(pid)
    return hits


def run_baseline(item: dict[str, Any], manifest: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    return resolve_auto_lead(item["prompt"], manifest)  # context-free by contract


def run_candidate(item: dict[str, Any], manifest: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    return resolve_candidate_lead(item["prompt"], manifest, item.get("prior_lead"))


def ok(item: dict[str, Any], persona: str, lenient: bool) -> bool:
    if persona == item["intended"]:
        return True
    return lenient and persona in item.get("acceptable", [])


def taxonomy(item: dict[str, Any], persona: str, prov: dict[str, Any], manifest: dict[str, Any]) -> str:
    """Mechanical baseline failure class (ordered rules; first match wins)."""
    if item["intended"] == "aoteru" and persona != "aoteru":
        return "over-trigger"
    if persona == "aoteru" and "fallback:aoteru" in prov.get("reasons", []):
        return "context-free" if item["category"] == "follow-up" else "vocabulary-gap"
    if len(_matched_personas(item["prompt"], manifest)) >= 2:
        return "cue-conflict-or-negation-blind"
    return "wrong-single-cue"


def evaluate(corpus: dict[str, Any], lenient: bool = False) -> dict[str, Any]:
    manifest = manifest_from(corpus)
    rows = []
    for item in corpus["items"]:
        bp, bprov = run_baseline(item, manifest)
        cp, cprov = run_candidate(item, manifest)
        b_ok, c_ok = ok(item, bp, lenient), ok(item, cp, lenient)
        rows.append({
            "id": item["id"], "category": item["category"], "prompt": item["prompt"],
            "intended": item["intended"], "acceptable": item.get("acceptable", []),
            "baseline": bp, "baseline_ok": b_ok,
            "baseline_failure": None if b_ok else taxonomy(item, bp, bprov, manifest),
            "candidate": cp, "candidate_ok": c_ok, "candidate_reasons": cprov["reasons"],
        })
    cats: "OrderedDict[str, dict[str, int]]" = OrderedDict()
    for row in rows:
        c = cats.setdefault(row["category"], {"n": 0, "baseline": 0, "candidate": 0})
        c["n"] += 1
        c["baseline"] += row["baseline_ok"]
        c["candidate"] += row["candidate_ok"]
    n = len(rows)
    return {
        "split": corpus.get("split"), "lenient": lenient, "n": n,
        "baseline_correct": sum(r["baseline_ok"] for r in rows),
        "candidate_correct": sum(r["candidate_ok"] for r in rows),
        "by_category": cats,
        "baseline_failure_taxonomy": dict(Counter(r["baseline_failure"] for r in rows if r["baseline_failure"])),
        "regressions": [r["id"] for r in rows if r["baseline_ok"] and not r["candidate_ok"]],
        "fixed": [r["id"] for r in rows if not r["baseline_ok"] and r["candidate_ok"]],
        "candidate_still_wrong": [r["id"] for r in rows if not r["candidate_ok"]],
        "rows": rows,
    }


def format_report(result: dict[str, Any]) -> str:
    mode = "lenient (intended or acceptable)" if result["lenient"] else "strict (intended only)"
    out = [f"split={result['split']} n={result['n']} scoring={mode}",
           f"baseline  {result['baseline_correct']}/{result['n']}",
           f"candidate {result['candidate_correct']}/{result['n']}", "",
           f"{'category':<20}{'n':>3}{'baseline':>10}{'candidate':>11}"]
    for cat, c in result["by_category"].items():
        out.append(f"{cat:<20}{c['n']:>3}{c['baseline']:>10}{c['candidate']:>11}")
    out += ["", f"baseline failure taxonomy: {result['baseline_failure_taxonomy']}",
            f"fixed by candidate:   {result['fixed']}",
            f"REGRESSIONS:          {result['regressions']}",
            f"candidate still wrong: {result['candidate_still_wrong']}"]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--split", choices=sorted(SPLITS), default="dev")
    ap.add_argument("--lenient", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--rows", action="store_true", help="print every row (text mode)")
    args = ap.parse_args(argv)
    result = evaluate(load_corpus(CORPUS_DIR / SPLITS[args.split]), lenient=args.lenient)
    if args.json:
        print(json.dumps(result, indent=2, default=list))
        return 0
    print(format_report(result))
    if args.rows:
        for r in result["rows"]:
            flag = ("B" if r["baseline_ok"] else "b") + ("C" if r["candidate_ok"] else "c")
            print(f"{flag} {r['id']:<4} want={r['intended']:<8} base={r['baseline']:<8} cand={r['candidate']:<8} {r['prompt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""routing_replay_evaluator.py — CLI report over src/routing_evaluator.py
(Workstream D). Read-only: aggregates real `RoutingDecision` telemetry
into per-route evidence, prints a compact table, and flags which routes
have enough recorded decisions (EVIDENCE_THRESHOLD) to be trusted for a
config-change proposal versus which are still noise.

Usage:
    venv/bin/python scripts/routing_replay_evaluator.py [--since-days N] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.routing_evaluator import load_and_aggregate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since-days", type=int, default=None,
                         help="only aggregate decisions from the last N days")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = parser.parse_args()

    since = datetime.utcnow() - timedelta(days=args.since_days) if args.since_days else None
    aggregates = load_and_aggregate(since=since)

    if args.json:
        print(json.dumps([a.to_dict() for a in aggregates], indent=2))
        return 0

    if not aggregates:
        print("no RoutingDecision rows recorded yet — nothing to aggregate.")
        return 0

    header = f"{'task_class':<14} {'alias':<16} {'executor':<9} {'n':>4} {'evid':>5} {'success':>8} {'verif':>7} {'escal':>6} {'p50ms':>7} {'p95ms':>7}"
    print(header)
    print("-" * len(header))
    for a in aggregates:
        d = a.to_dict()

        def fmt_pct(v):
            return f"{v * 100:.0f}%" if v is not None else "-"

        def fmt_ms(v):
            return f"{v:.0f}" if v is not None else "-"

        print(
            f"{d['task_class']:<14} {(d['model_alias'] or '-'):<16} {d['executor']:<9} "
            f"{d['n']:>4} {'yes' if d['evidence_sufficient'] else 'no':>5} "
            f"{fmt_pct(d['success_rate']):>8} {fmt_pct(d['verification_rate']):>7} "
            f"{fmt_pct(d['escalation_rate']):>6} {fmt_ms(d['latency_p50_ms']):>7} {fmt_ms(d['latency_p95_ms']):>7}"
        )

    insufficient = [a for a in aggregates if not a.evidence_sufficient]
    print()
    print(f"{len(aggregates)} route(s) aggregated; {len(insufficient)} below the evidence "
          f"threshold — treat their rates as noise, not a basis for any config change.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

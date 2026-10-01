#!/usr/bin/env python3
"""Emit a deterministic evolution plan for one rated prompt application."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.prompt_evolution import graph_edges_for_plan, plan_evolution  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    trace = yaml.safe_load(args.trace.read_text(encoding="utf-8"))
    plan = plan_evolution(trace)
    payload = plan.to_dict()
    payload["edges"] = graph_edges_for_plan(plan)

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(yaml.safe_dump(payload, sort_keys=False).rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

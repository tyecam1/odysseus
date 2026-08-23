#!/usr/bin/env python3
"""memory_promote_replay.py — CLI wrapper over src/memory_outbox.replay()
(Workstream I's "memory-primary promotion/checkpoint/replay procedure").

Copies every record the source MisumiMemory root has that the target root
doesn't (by stable id) — safe to run more than once. Intended use: once a
future home host is live and its own MisumiMemory root is reachable
(mounted, synced, or run locally on that host against a copied lab
snapshot), this is the one bounded command that moves lab-accumulated
memory across without duplicating anything already promoted. It never
decides that a target becomes canonical/primary — that's an operator/
foreman config change (config/estate.yaml service placement), not
something this script infers from having successfully copied files.

Usage:
    venv/bin/python scripts/memory_promote_replay.py \\
        --source /path/to/lab/data/misumi/memory \\
        --target /path/to/home/data/misumi/memory [--json]

Defaults --source to this checkout's own live Misumi memory root
(src.constants.DATA_DIR/misumi/memory) when omitted, since the common
case is "replay lab's real accumulated memory into a target I'm
preparing" rather than two arbitrary paths.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.memory_outbox import replay  # noqa: E402
from src.misumi_memory import MisumiMemory  # noqa: E402


def _default_source() -> Path:
    from src.constants import DATA_DIR
    return Path(DATA_DIR) / "misumi" / "memory"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=None,
                         help="source MisumiMemory root (default: this checkout's live data dir)")
    parser.add_argument("--target", type=Path, required=True,
                         help="target MisumiMemory root to replay into")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    source_root = args.source or _default_source()
    if not source_root.exists():
        print(f"error: source root does not exist: {source_root}", file=sys.stderr)
        return 2

    args.target.mkdir(parents=True, exist_ok=True)

    source = MisumiMemory(root=source_root)
    target = MisumiMemory(root=args.target)
    result = replay(source, target)

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"replay: {source_root} -> {args.target}")
    total_applied = 0
    total_conflicting = 0
    for store, stats in result.items():
        print(f"  {store:<12} source={stats['source_count']:>4}  applied={stats['applied']:>4}  "
              f"already_present={stats['already_present']:>4}  conflicting={stats['conflicting']:>4}  "
              f"corrupt(source/target)={stats['source_corrupt_lines']}/{stats['target_corrupt_lines']}")
        total_applied += stats["applied"]
        total_conflicting += stats["conflicting"]
    print()
    print(f"{total_applied} record(s) newly applied. Re-run any time — already-applied records are skipped.")
    if total_conflicting:
        print(
            f"WARNING: {total_conflicting} record(s) exist on both sides under the same id but with "
            "different content — NOT overwritten either way. Resolve manually; see conflicting_ids "
            "in --json output for the exact ids."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

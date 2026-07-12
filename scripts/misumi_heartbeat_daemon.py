#!/usr/bin/env python3
"""Bounded Misumi heartbeat daemon.

Runs enabled heartbeat manifests forever, but each run stays proposal-only.
This is not a self-modifier. It only writes run records and proposal artifacts
under data/misumi/runtime.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.misumi_operator_runtime import HeartbeatRuntime, parse_utc  # noqa: E402

STOP = False


def _stop(signum, frame):  # noqa: ARG001
    global STOP
    STOP = True


def due(loop: dict, now: datetime) -> bool:
    if not loop.get("enabled"):
        return False
    if loop.get("currently_running"):
        return False
    last = parse_utc(loop.get("last_successful_run") or loop.get("last_failed_run"))
    if last is None:
        return True
    interval = max(3600, int(loop.get("interval_seconds") or 3600))
    return (now - last).total_seconds() >= interval


def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run proposal-only Misumi heartbeat loops")
    parser.add_argument("--poll-seconds", type=int, default=60, help="Daemon wake interval. Minimum 60 seconds.")
    parser.add_argument("--once", action="store_true", help="Run one due-check pass then exit.")
    parser.add_argument("--input-summary", default="daemon scheduled heartbeat pass")
    args = parser.parse_args(argv)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    poll_seconds = max(60, int(args.poll_seconds or 60))
    heartbeat = HeartbeatRuntime()

    emit({"event": "heartbeat-daemon-start", "poll_seconds": poll_seconds, "writes_allowed": False})
    while not STOP:
        status = heartbeat.status()
        now = datetime.now(timezone.utc)
        for loop in status.get("loops", []):
            if not due(loop, now):
                continue
            loop_id = str(loop["loop_id"])
            try:
                result = heartbeat.run_once(loop_id, input_summary=args.input_summary)
                emit({
                    "event": "heartbeat-loop-run",
                    "loop_id": loop_id,
                    "status": result["run"]["status"],
                    "output_artifact": result["run"].get("output_artifact"),
                    "writes_allowed": False,
                })
            except Exception as exc:  # noqa: BLE001 - daemon must keep running after one failed loop
                emit({"event": "heartbeat-loop-failed", "loop_id": loop_id, "error": type(exc).__name__, "message": str(exc)[:300]})
        if args.once:
            break
        slept = 0
        while slept < poll_seconds and not STOP:
            time.sleep(1)
            slept += 1
    emit({"event": "heartbeat-daemon-stop", "writes_allowed": False})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

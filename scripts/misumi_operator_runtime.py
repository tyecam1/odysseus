#!/usr/bin/env python3
"""CLI for Misumi operator-conference and heartbeat runtime state.

Examples:
  python scripts/misumi_operator_runtime.py conferences create --reason "Aoteru needs Operator confirmation"
  python scripts/misumi_operator_runtime.py conferences list --status pending
  python scripts/misumi_operator_runtime.py conferences respond <event_id> --response "Proceed with the bounded plan."
  python scripts/misumi_operator_runtime.py heartbeat status
  python scripts/misumi_operator_runtime.py heartbeat run-once operator_handoff_loop --input-summary "Aoteru claimed operator status, no event existed."
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.misumi_operator_runtime import HeartbeatRuntime, OperatorConferenceStore  # noqa: E402


def emit(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Misumi operator-conference and heartbeat runtime CLI")
    sub = parser.add_subparsers(dest="area", required=True)

    conferences = sub.add_parser("conferences")
    conf_sub = conferences.add_subparsers(dest="command", required=True)

    conf_create = conf_sub.add_parser("create")
    conf_create.add_argument("--requesting-persona", default="aoteru")
    conf_create.add_argument("--reason", required=True)
    conf_create.add_argument("--context-summary", default="")
    conf_create.add_argument("--urgency", default="normal")
    conf_create.add_argument("--timeout-seconds", type=int, default=600)
    conf_create.add_argument("--session-id")
    conf_create.add_argument("--correlation-id")

    conf_list = conf_sub.add_parser("list")
    conf_list.add_argument("--status", choices=["pending", "responded", "expired", "cancelled"])

    conf_get = conf_sub.add_parser("get")
    conf_get.add_argument("event_id")

    conf_respond = conf_sub.add_parser("respond")
    conf_respond.add_argument("event_id")
    conf_respond.add_argument("--response", required=True)
    conf_respond.add_argument("--responder", default="operator")

    conf_cancel = conf_sub.add_parser("cancel")
    conf_cancel.add_argument("event_id")
    conf_cancel.add_argument("--reason", default="cancelled")

    heartbeat = sub.add_parser("heartbeat")
    hb_sub = heartbeat.add_subparsers(dest="command", required=True)
    hb_sub.add_parser("status")
    hb_run = hb_sub.add_parser("run-once")
    hb_run.add_argument("loop_id")
    hb_run.add_argument("--input-summary", default="")
    hb_prop = hb_sub.add_parser("proposals")
    hb_prop.add_argument("--limit", type=int, default=20)

    args = parser.parse_args(argv)
    if args.area == "conferences":
        store = OperatorConferenceStore()
        if args.command == "create":
            emit(store.create(
                requesting_persona=args.requesting_persona,
                reason=args.reason,
                context_summary=args.context_summary,
                urgency=args.urgency,
                timeout_seconds=args.timeout_seconds,
                session_id=args.session_id,
                correlation_id=args.correlation_id,
            ))
        elif args.command == "list":
            rows, corrupt = store.list(status=args.status)
            emit({"events": rows, "corrupt_lines": corrupt})
        elif args.command == "get":
            emit(store.get(args.event_id))
        elif args.command == "respond":
            emit(store.respond(args.event_id, response=args.response, responder=args.responder))
        elif args.command == "cancel":
            emit(store.cancel(args.event_id, reason=args.reason))
        return 0

    hb = HeartbeatRuntime()
    if args.command == "status":
        emit(hb.status())
    elif args.command == "run-once":
        emit(hb.run_once(args.loop_id, input_summary=args.input_summary))
    elif args.command == "proposals":
        emit({"proposals": hb.proposals(args.limit)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

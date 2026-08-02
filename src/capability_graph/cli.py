"""Argument parser and command handlers for ``odysseus-graph``."""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts._lib.cli import common_parser, emit, run

from .builder import build_graph
from .freshness import GraphFreshness, check_freshness
from .queries import QUERY_NAMES, execute_query, explain_route
from .storage import export_graph


def cmd_build(args: argparse.Namespace) -> None:
    result = build_graph([Path(item) for item in args.sources], Path(args.out))
    emit({
        "db": str(result.db_path),
        "sources": len(result.sources),
        "adapters": result.adapter_counts,
        "nodes": {"total": len(result.graph.nodes), "by_type": result.node_counts},
        "edges": {"total": len(result.graph.edges), "by_type": result.edge_counts},
    }, args)


def cmd_check(args: argparse.Namespace) -> None:
    report = check_freshness(Path(args.db), [Path(item) for item in args.sources])
    emit(report.to_dict(), args)
    if report.freshness is GraphFreshness.STALE:
        raise SystemExit(1)


def cmd_query(args: argparse.Namespace) -> None:
    emit(execute_query(
        Path(args.db),
        args.question,
        route_id=args.route,
        request=args.request,
        allow_stale=args.allow_stale,
    ), args)


def cmd_export(args: argparse.Namespace) -> None:
    digest = export_graph(Path(args.db), Path(args.out))
    out = Path(args.out).resolve()
    emit({
        "out": str(out),
        "metadata": str(out.with_name(f"{out.name}.metadata.json")),
        "sha256": digest,
    }, args)


def cmd_explain(args: argparse.Namespace) -> None:
    emit(explain_route(
        Path(args.db),
        args.route,
        allow_stale=args.allow_stale,
    ), args)


def build_parser() -> argparse.ArgumentParser:
    parser = common_parser("odysseus-graph", "Build and query the procedural capability graph.")
    common = parser._common_parents[0]
    sub = parser.add_subparsers(dest="cmd", required=True)

    build = sub.add_parser("build", parents=[common])
    build.add_argument("--sources", nargs="+", required=True)
    build.add_argument("--out", required=True)
    build.set_defaults(func=cmd_build)

    check = sub.add_parser("check", parents=[common])
    check.add_argument("--db", required=True)
    check.add_argument("--sources", nargs="+", required=True)
    check.set_defaults(func=cmd_check)

    query = sub.add_parser("query", parents=[common])
    query.add_argument("--db", required=True)
    query.add_argument("question", help=f"named query: {', '.join(QUERY_NAMES)}")
    query.add_argument("--route")
    query.add_argument("--request")
    query.add_argument("--json", action="store_true", help="emit stable JSON (default output format)")
    query.add_argument("--allow-stale", action="store_true")
    query.set_defaults(func=cmd_query)

    export = sub.add_parser("export", parents=[common])
    export.add_argument("--db", required=True)
    export.add_argument("--out", required=True)
    export.set_defaults(func=cmd_export)

    explain = sub.add_parser("explain", parents=[common])
    explain.add_argument("--db", required=True)
    explain.add_argument("--route", required=True)
    explain.add_argument("--allow-stale", action="store_true")
    explain.set_defaults(func=cmd_explain)
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser(), argv)


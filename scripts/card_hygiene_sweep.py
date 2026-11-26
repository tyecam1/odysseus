#!/usr/bin/env python3
"""Propose metadata fixes from the existing queues and read-only reviewer records."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

import yaml

try:
    from . import agentic_context as cards, agentic_portfolio as portfolio
except ImportError:
    import agentic_context as cards
    import agentic_portfolio as portfolio


OUTPUT = Path("automation/review/card-hygiene")
HEAD = re.compile(r"(?:[a-f0-9]{40}|[a-f0-9]{64})\Z")
MODEL = re.compile(r"(?:gpt|codex|claude|glm)[-_.][A-Za-z0-9_.-]*\d[A-Za-z0-9_.-]*\Z", re.I)
RECORD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
PR_URL = re.compile(r"https://(?:api\.)?github\.com/(?:repos/)?([^/]+/[^/]+)/pulls?/(\d+)(?:/reviews)?\Z")

OWNER_FIELDS = {
    "owner_gate_class_required": ("owner_gate_class",),
    "host_required_reason_missing": ("execution_host", "host_required_reason"),
    "mechanical_executor_for_judgement": ("executor",),
    "event_date_expired": ("event_date", "status"),
    "event_date_invalid": ("event_date",),
}


def routing_records(path: Path):
    """Read the router's tagged, launched review calls from a SQLite database."""
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        rows = db.execute(
            "SELECT id, task_class, concrete_model, escalation_reason FROM routing_decisions "
            "WHERE status = 'complete' AND concrete_model IS NOT NULL AND instr(escalation_reason, ' |call=') > 0"
        )
        for record_id, task_class, model, reason in rows:
            try:
                call = json.loads(reason.rsplit(" |call=", 1)[1])
            except ValueError:
                continue
            if (isinstance(call, dict) and call.get("v") == 1 and call.get("launched") is True
                    and call.get("launch_id") and isinstance(model, str) and "sol" in model.casefold()):
                yield {"source": "sol_call", "record_id": record_id, "concrete_model": model,
                       "subject": call.get("subject"), "head_sha": call.get("head_sha"),
                       "review": task_class in ("review", "code_review", "independent-review",
                                                "pr-review", "independent_review")}


def fallback_records(path: Path):
    header, _ = cards.split_card(path.read_text(encoding="utf-8-sig"))
    if isinstance(header.get("fallback_lane"), str) and header["fallback_lane"].strip():
        yield {**header, "source": "fallback_header"}


def pr_records(path: Path):
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("expected a JSON array of PR review records")
    for row in rows:
        if isinstance(row, dict) and row.get("submitted_at") and row.get("state") in (
            "APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED",
        ):
            yield {"source": "pr_review", "record_id": str(row.get("node_id") or row.get("id") or ""),
                   "concrete_model": row.get("concrete_model"), "head_sha": row.get("commit_id"),
                   "pull_request_url": row.get("pull_request_url")}


def _matches(pattern: re.Pattern, value) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _pr(value):
    match = PR_URL.fullmatch(value) if isinstance(value, str) else None
    return (match[1].casefold(), match[2]) if match else None


def reviewer_attestation(records: list[dict], ref: str, meta: dict, repo_slug: str) -> dict | None:
    """Return a model identity only from a structured record bound to this review."""
    repo = ref.split(":", 1)[0]
    task_id = meta.get("task_id") or cards._task_key(ref.split("/", 1)[1])
    link = meta.get("linked_pr") or meta.get("pull_request_url")
    linked_pr = (repo_slug.casefold(), str(link)) if type(link) is int and link > 0 else _pr(link)
    if linked_pr and linked_pr[0] != repo_slug.casefold():
        linked_pr = None
    expected_head = meta.get("review_head_sha") or meta.get("head_sha") or meta.get("commit_sha")
    matches = {}
    for record in records:
        source = record.get("source")
        model = record.get("concrete_model") or record.get("reviewer_model")
        record_id, head = record.get("record_id"), record.get("head_sha")
        if not (_matches(MODEL, model) and _matches(RECORD_ID, record_id) and _matches(HEAD, head)):
            continue
        if expected_head is not None and head != expected_head:
            continue
        subject = record.get("subject")
        if source == "sol_call":
            matched = subject == f"{repo}:review:{task_id}" or (
                record.get("review") is True and (
                    subject == f"{repo}:task:{task_id}"
                    or (bool(linked_pr) and subject == f"{repo}:pr:{linked_pr[1]}")
                )
            )
        elif source == "fallback_header":
            matched = record.get("task_ref") == ref
        elif source == "pr_review":
            matched = bool(linked_pr) and _pr(record.get("pull_request_url")) == linked_pr
        else:
            matched = False
        if matched:
            key = (source, record_id)
            attestation = {"source": source, "record_id": record_id, "model": model, "head_sha": head}
            if key in matches and matches[key] != attestation:
                return None
            matches[key] = attestation
    if not matches or len({row["head_sha"] for row in matches.values()}) != 1:
        return None
    return matches[min(matches)]


def protected_handoff(path: Path, reason: str) -> dict:
    return {"kind": "protected_handoff", "path": str(path), "reason": reason}


def sweep_repo(repo: str, root: Path, records: list[dict], as_of: date, repo_slug: str) -> dict:
    queue_rel, buckets = portfolio.LAYOUT[repo]
    handoffs, proposals, snapshot = [], [], []
    counts = Counter()
    try:
        queue = cards.queue_path(root, Path(queue_rel))
    except (OSError, ValueError) as exc:
        handoffs.append(protected_handoff(root / queue_rel, type(exc).__name__))
    else:
        for bucket in buckets:
            try:
                # A missing optional bucket is allowed; a non-directory bucket is unreadable.
                bucket_path = queue / bucket
                if cards.bucket_folder(queue, bucket) is None and bucket_path.exists():
                    raise NotADirectoryError(bucket_path)
                names = cards.card_names(queue, bucket)
            except (OSError, ValueError) as exc:
                handoffs.append(protected_handoff(queue / bucket, exc.label if isinstance(exc, cards.Refused)
                                                  else type(exc).__name__))
                continue
            for name in names:
                path = queue / bucket / name
                try:
                    content = cards.read_card(queue, bucket, name)
                    meta, _ = cards.split_card(content)
                    snapshot.append((bucket, name, meta, hashlib.sha256(content.encode("utf-8")).hexdigest()))
                except (OSError, ValueError) as exc:
                    reason = exc.label if isinstance(exc, cards.Refused) else type(exc).__name__
                    handoffs.append(protected_handoff(path, reason))

    parents = cards.referenced_parents(meta for _, _, meta, _ in snapshot)
    for bucket, name, meta, digest in snapshot:
        ref = f"{repo}:{bucket}/{name}"
        findings = cards.hygiene_findings(meta, name=name, bucket=bucket, parents=parents, as_of=as_of)
        edits, fields, actions = {}, set(), []
        for finding in findings:
            code = finding["code"]
            fields.update(OWNER_FIELDS.get(code, ()))
            if code == "approval_scope_missing":
                fields.update(cards.missing_approval_fields(meta))
            if code == "executable_container":
                edits["execution_mode"] = "container"
        if bucket == "review":
            attestation = reviewer_attestation(records, ref, meta, repo_slug)
            recorded = meta.get("reviewer_attestation")
            if attestation and recorded != attestation:
                edits["reviewer_attestation"] = attestation
                findings.append({"code": "reviewer_attestation_backfill",
                                 "reason": "Record the reviewer identity and machine record for the reviewed revision."})
            elif not attestation:
                findings.append({"code": "reviewer_model_not_attested",
                                 "reason": "A unique, revision-bound machine record for the reviewer is unavailable."})
                actions.append({"kind": "bounded_re_review",
                                "scope": "Review the card's current deliverable once on a qualified independent lane and log its record ID."})
        if findings:
            counts.update(finding["code"] for finding in findings)
            proposals.append({
                "card": ref, "card_text_sha256": digest, "findings": findings,
                "metadata_patch": {"set": edits, "needs_evidence": sorted(fields)},
                "follow_up": actions,
            })
    return {"repo": repo, "as_of": as_of.isoformat(), "scanned": len(snapshot), "counts": dict(counts),
            "protected_handoffs": handoffs, "proposals": proposals}


def write_proposals(root: Path, report: dict) -> None:
    """Replace a proposal set atomically, using only directories beneath OUTPUT."""
    if report["repo"] not in portfolio.LAYOUT:
        raise ValueError("unknown proposal repository")
    fd = cards._open_dir_nofollow(root.resolve(strict=True))
    tmp = f".proposals-{uuid4().hex}.tmp"
    created = False
    try:
        for part in (*OUTPUT.parts, report["repo"]):
            try:
                os.mkdir(part, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        out_fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=fd)
        created = True
        with os.fdopen(out_fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=True, sort_keys=True)
            stream.write("\n")
        os.replace(tmp, "proposals.json", src_dir_fd=fd, dst_dir_fd=fd)
        created = False
    finally:
        if created:
            os.unlink(tmp, dir_fd=fd)
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=portfolio.ROOT)
    parser.add_argument("--misumi-root", type=Path)
    parser.add_argument("--obsidian-phd-root", type=Path)
    parser.add_argument("--repo", choices=tuple(portfolio.LAYOUT), action="append")
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument("--routing-db", type=Path, help="Read-only SQLite source with tagged Sol call records.")
    parser.add_argument("--fallback-header", action="append", type=Path, default=[],
                        help="Trusted machine-generated review report with a structured fallback-lane header.")
    parser.add_argument("--pr-reviews", action="append", type=Path, default=[],
                        help="Trusted PR review JSON export with structured concrete_model when the source attests it.")
    args = parser.parse_args()
    root = args.repo_root.resolve(strict=True)
    roots, unavailable = portfolio.resolve_roots(root, {
        "misumi": args.misumi_root, "obsidian-phd": args.obsidian_phd_root,
    })
    sources = [(path, pr_records) for path in args.pr_reviews]
    sources += [(path, fallback_records) for path in args.fallback_header]
    if args.routing_db:
        sources.append((args.routing_db, routing_records))
    records, handoffs = [], []
    for path, load in sources:
        try:
            records.extend(list(load(path)))
        except (OSError, ValueError, sqlite3.Error) as exc:
            handoffs.append(protected_handoff(path, type(exc).__name__))

    with (root / "config/repositories.yaml").open(encoding="utf-8") as stream:
        slugs = {entry["id"]: entry["remote"].removeprefix("https://github.com/").removesuffix(".git")
                 for entry in yaml.safe_load(stream)["repos"] if entry["id"] in portfolio.LAYOUT}
    incomplete = False
    for repo in args.repo or portfolio.LAYOUT:
        if repo in roots:
            report = sweep_repo(repo, roots[repo], records, args.as_of, slugs[repo])
        else:
            configured = {"misumi": args.misumi_root, "obsidian-phd": args.obsidian_phd_root}[repo]
            queue = Path(portfolio.LAYOUT[repo][0])
            path = configured / queue if configured else queue
            report = {"repo": repo, "as_of": args.as_of.isoformat(), "scanned": 0, "counts": {},
                      "proposals": [], "protected_handoffs": [protected_handoff(path, unavailable[repo])]}
        report["protected_handoffs"].extend(handoffs)
        write_proposals(root, report)
        incomplete |= bool(report["protected_handoffs"])
        print(json.dumps({key: report[key] for key in ("repo", "scanned", "counts", "protected_handoffs")}))
    return int(incomplete)


if __name__ == "__main__":
    raise SystemExit(main())

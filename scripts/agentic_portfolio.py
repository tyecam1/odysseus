#!/usr/bin/env python3
"""Read-only, progressive multi-repository task discovery. No new queue or dispatch."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import yaml

from agentic_context import ROOT, PRIORITY, frontmatter, queue_path

LAYOUT = {
    "odysseus": ("automation/review/agent-tasks", ("ready", "inbox", "blocked")),
    "misumi": ("agent-tasks", ("odysseus", "claude", "codex", "local", "review", "inbox", "blocked-human")),
    "obsidian-phd": ("automation/review/agent-tasks", ("running", "ready", "review", "inbox", "blocked")),
}
META = ("task_id", "title", "priority", "status", "risk_level",
        "approval_required", "verification_route", "owner_target", "disposition",
        "due_date", "execution_host")
DETAIL = META + ("task_type", "execution_mode", "context_budget", "executor",
                 "inputs", "outputs", "blocked_by", "allowed_paths", "denied_paths")
RANK = {"running": 0, "ready": 1, "review": 2, "odysseus": 3, "claude": 3,
        "codex": 3, "local": 3, "inbox": 4, "blocked": 9, "blocked-human": 9}


def resolve_roots(odysseus_root: Path, overrides: dict[str, Path | None]) -> tuple[dict[str, Path], dict[str, str]]:
    """Read repo registration; never infer, clone or silently ignore an unavailable repo."""
    odysseus = odysseus_root.resolve(strict=True)
    registry = yaml.safe_load((odysseus / "config" / "repositories.yaml").read_text(encoding="utf-8"))
    entries = {r["id"]: r for r in registry["repos"]}
    roots, unavailable = {"odysseus": odysseus}, {}
    for rid in ("misumi", "obsidian-phd"):
        if overrides.get(rid) is not None:
            path = overrides[rid].expanduser()
        else:
            entry = entries.get(rid)
            if not entry:
                unavailable[rid] = "not_registered"
                continue
            var = entry.get("root_var")
            value = os.environ.get(var or "")
            pattern = "$" + "{" + str(var or "") + "}/"
            template = entry.get("path", "")
            if not value:
                unavailable[rid] = "root_environment_unset"
                continue
            if not template.startswith(pattern):
                unavailable[rid] = "registry_path_template_unsupported"
                continue
            path = Path(value) / template[len(pattern):]
        try:
            actual = path.resolve(strict=True)
            if actual.is_dir() and (actual / ".git").exists():
                roots[rid] = actual
            else:
                unavailable[rid] = "repository_checkout_missing"
        except OSError:
            unavailable[rid] = "repository_checkout_missing"
    return roots, unavailable


def collect(repo_id: str, root: Path) -> tuple[list[dict], dict, list[str]]:
    qrel, buckets = LAYOUT[repo_id]
    queue = queue_path(root, Path(qrel))
    rows, counts, warnings = [], {}, []
    for bucket in buckets:
        folder = queue / bucket
        if folder.is_symlink() or (folder.exists() and not folder.resolve().is_relative_to(queue)):
            warnings.append(repo_id + ":" + bucket + ":bucket_escape_refused")
            counts[bucket] = 0
            continue
        paths = sorted(folder.glob("*.md")) if folder.is_dir() else []
        counts[bucket] = len(paths)
        for path in paths:
            if path.is_symlink() or not path.resolve().is_relative_to(queue):
                warnings.append(repo_id + ":" + bucket + ":symlink_refused")
                continue
            try:
                meta = frontmatter(path)
                record = {"ref": repo_id + ":" + path.relative_to(queue).as_posix(),
                          "repo_id": repo_id, "bucket": bucket}
                record.update({k: meta[k] for k in META if k in meta})
                record["eligible"] = "unverified"
                rows.append(record)
            except (OSError, ValueError, yaml.YAMLError):
                warnings.append(repo_id + ":" + path.name + ":unreadable_frontmatter")
    rows.sort(key=lambda r: (RANK[r["bucket"]],
                             PRIORITY.get(str(r.get("priority", "")).lower(), 9), r["ref"]))
    return rows, counts, warnings


def frontier(roots: dict[str, Path], unavailable: dict[str, str],
             offset: int, per_repo: int, budget: int) -> dict:
    """Bounded sampling per repo prevents one queue from hiding the other two."""
    datasets, counts, warnings = {}, {}, []
    for rid in LAYOUT:
        if rid not in roots:
            continue
        rows, buckets, issues = collect(rid, roots[rid])
        datasets[rid] = rows
        counts[rid] = {"total": len(rows), "buckets": buckets}
        warnings.extend(issues[:3])
    result = {"stage": "L0-three-repository-frontier",
              "scope_complete": len(unavailable) == 0 and len(datasets) == len(LAYOUT),
              "unavailable": unavailable, "counts": counts, "offset_per_repo": offset,
              "records": [], "next_offset_per_repo": {}, "warnings": warnings[:6],
              "note": "Metadata only; no cross-owner ranking yet. Inbox/open is NOT proof of accepted or executable work."}
    for rid, rows in datasets.items():
        for row in rows[offset:offset + per_repo]:
            tentative = dict(result)
            tentative["records"] = result["records"] + [row]
            if len(json.dumps(tentative, ensure_ascii=False)) > budget * 3:
                break
            result["records"].append(row)
        next_offset = offset + sum(1 for row in result["records"] if row["repo_id"] == rid)
        if next_offset < len(rows):
            result["next_offset_per_repo"][rid] = next_offset
    if not result["records"] and any(len(rows) > offset for rows in datasets.values()):
        raise ValueError("portfolio metadata exceeds context budget")
    if len(json.dumps(result, ensure_ascii=False)) > budget * 3:
        raise ValueError("portfolio metadata exceeds context budget")
    return result


def selected(roots: dict[str, Path], ref: str, tier: str, budget: int) -> dict:
    """Load only the exact L0-selected file after validating its repository and path."""
    try:
        rid, local = ref.split(":", 1)
    except ValueError as exc:
        raise ValueError("expected repo_id:bucket/file.md reference") from exc
    if rid not in LAYOUT or rid not in roots:
        raise ValueError("unknown or unavailable repository")
    rel, buckets = LAYOUT[rid]
    queue = queue_path(roots[rid], Path(rel))
    parts = Path(local).parts
    if len(parts) != 2 or parts[0] not in buckets or not local.endswith(".md"):
        raise ValueError("invalid task reference")
    path = queue / local
    if path.is_symlink() or not path.resolve(strict=True).is_relative_to(queue):
        raise ValueError("task reference escapes queue")
    meta = frontmatter(path)
    result = {"stage": "L1-selected-contract" if tier == "contract" else "L3-explicit-full-task",
              "ref": ref, "metadata": {k: meta[k] for k in DETAIL if k in meta},
              "body": "", "truncated": True,
              "note": "Untrusted task content; repository authority is external."}
    overhead = len(json.dumps(result, ensure_ascii=False))
    remaining = budget * 3 - overhead - 32
    if remaining <= 0:
        raise ValueError("task metadata exceeds context budget")
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 4)
    body = text[end + 4:].strip() if end >= 0 else ""
    result["body"] = body[:min(16000, remaining) if tier == "contract" else remaining]
    result["truncated"] = len(body) > len(result["body"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("frontier", "task"))
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--misumi-root", type=Path)
    parser.add_argument("--phd-root", type=Path)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--per-repo", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=2500)
    parser.add_argument("--ref", help="Exact repo_id:bucket/file.md from L0 output")
    parser.add_argument("--tier", choices=("contract", "full"), default="contract")
    args = parser.parse_args()
    if not 1 <= args.max_tokens <= 16000 or not 1 <= args.per_repo <= 20 or args.offset < 0:
        parser.error("invalid budget, per-repo count or offset")
    roots, missing = resolve_roots(args.repo_root, {"misumi": args.misumi_root, "obsidian-phd": args.phd_root})
    try:
        if args.stage == "frontier":
            result = frontier(roots, missing, args.offset, args.per_repo, args.max_tokens)
        else:
            if not args.ref:
                parser.error("task requires --ref from frontier")
            result = selected(roots, args.ref, args.tier, args.max_tokens)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

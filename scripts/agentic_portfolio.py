#!/usr/bin/env python3
"""Read-only, progressive multi-repository task discovery. No new queue or dispatch."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import subprocess
import tempfile
import time
from pathlib import Path, PurePosixPath

import yaml

try:
    import resource
except ImportError:  # Windows
    resource = None

from agentic_context import (ROOT, PRIORITY, Refused, card_names, clean_value, fit_body,
                             queue_path, read_card, split_card)

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
        try:
            names = card_names(queue, bucket)
        except Refused:
            warnings.append(repo_id + ":" + bucket + ":bucket_escape_refused")
            counts[bucket] = 0
            continue
        counts[bucket] = len(names)
        for name in names:
            try:
                meta, _ = split_card(read_card(queue, bucket, name))
                record = {"ref": repo_id + ":" + bucket + "/" + name,
                          "repo_id": repo_id, "bucket": bucket}
                record.update({k: clean_value(meta[k]) for k in META if k in meta})
                record["eligible"] = "unverified"
                rows.append(record)
            except Refused as exc:
                warnings.append(repo_id + ":" + bucket + ":" + exc.label)
            except (OSError, ValueError):
                warnings.append(repo_id + ":" + name + ":unreadable_frontmatter")
    rows.sort(key=lambda r: (RANK[r["bucket"]],
                             PRIORITY.get(str(r.get("priority", "")).lower(), 9), r["ref"]))
    return rows, counts, warnings


def frontier(roots: dict[str, Path], unavailable: dict[str, str],
             offset: int, per_repo: int, budget: int, transport_warning: str | None = None) -> dict:
    """Bounded sampling per repo prevents one queue from hiding the other two."""
    datasets, counts, warnings = {}, {}, []
    for rid in LAYOUT:
        if rid not in roots:
            continue
        rows, buckets, issues = collect(rid, roots[rid])
        datasets[rid] = rows
        counts[rid] = {"total": len(rows), "buckets": buckets}
        warnings.extend(issues[:3])
    warnings = warnings[:6]
    if transport_warning:
        warnings.append(transport_warning[:300])
    result = {"stage": "L0-three-repository-frontier",
              "scope_complete": (len(unavailable) == 0 and len(datasets) == len(LAYOUT)
                                 and not transport_warning),
              "unavailable": unavailable, "counts": counts, "offset_per_repo": offset,
              "records": [], "next_offset_per_repo": {}, "warnings": warnings,
              "note": "Metadata only; no cross-owner ranking yet. Inbox/open is NOT proof of accepted or executable work."}
    # Round-robin: every owner's first row is admitted before any owner's second,
    # and an owner whose next row no longer fits stops without blocking the others.
    taken, stopped = {rid: 0 for rid in datasets}, set()
    for step in range(per_repo):
        for rid, rows in datasets.items():
            if rid in stopped or offset + step >= len(rows):
                continue
            tentative = dict(result)
            tentative["records"] = result["records"] + [rows[offset + step]]
            # Pagination is filled in after admission, so size it at its upper bound now.
            tentative["next_offset_per_repo"] = {r: offset + len(d) for r, d in datasets.items()}
            if len(json.dumps(tentative, ensure_ascii=False)) > budget * 3:
                stopped.add(rid)
                continue
            result["records"].append(rows[offset + step])
            taken[rid] += 1
    order = {rid: index for index, rid in enumerate(LAYOUT)}
    result["records"].sort(key=lambda row: order[row["repo_id"]])  # stable: keeps each owner's rank order
    for rid, rows in datasets.items():
        if offset + taken[rid] < len(rows):
            result["next_offset_per_repo"][rid] = offset + taken[rid]
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
    meta, body = split_card(read_card(queue, parts[0], parts[1]))
    result = {"stage": "L1-selected-contract" if tier == "contract" else "L3-explicit-full-task",
              "ref": ref, "metadata": {k: clean_value(meta[k]) for k in DETAIL if k in meta},
              "truncated": False,  # sized with the longest literal; the final value is never longer
              "note": "Untrusted task content; repository authority is external."}
    wanted = body if tier == "full" else body[:16000]
    result["body"] = fit_body(result, wanted, budget * 3 - 32)
    result["truncated"] = len(result["body"]) < len(body)
    return result



def _exited_unreaped(proc: subprocess.Popen) -> bool:
    """True once the child has exited, WITHOUT reaping it, so its pid/pgid stay reserved
    (a zombie leader keeps the group id from being recycled) until we have signalled the group."""
    if hasattr(os, "waitid"):
        try:
            return os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
        except ChildProcessError:
            return True
    return proc.poll() is not None


def _kill_group(proc: subprocess.Popen) -> None:
    """Best-effort kill of the child and its same-session descendants; callers hold the child
    unreaped. A descendant that deliberately starts a new session is out of scope."""
    try:
        if os.name != "nt":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


def _ssh_run(cmd: list[str], timeout: float, max_out: int, max_err: int) -> subprocess.CompletedProcess:
    """Run `cmd` with its output captured to private temp FILES, not pipes.

    No reader threads, no EOF ambiguity and nothing a lingering descendant can block on. Sizes
    are polled and enforced (and on POSIX also capped by RLIMIT_FSIZE); overflow or the deadline
    kills the process group, and every exit path kills and reaps it. Contract: returns or raises
    within `timeout` plus a few seconds of teardown; a child stuck in uninterruptible kernel
    sleep cannot be forced and is reported, not waited on forever.
    """
    deadline = time.monotonic() + timeout
    proc = None
    with tempfile.TemporaryDirectory(prefix="agentic-ssh-") as tmp:
        out_path, err_path = os.path.join(tmp, "out"), os.path.join(tmp, "err")
        try:
            with open(out_path, "wb") as out_file, open(err_path, "wb") as err_file:
                extra = {}
                if os.name != "nt":
                    limit = max(max_out, max_err) + (1 << 20)
                    extra = {"start_new_session": True,
                             "preexec_fn": lambda: resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))}
                proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out_file, stderr=err_file, **extra)
                while not _exited_unreaped(proc):
                    if os.path.getsize(out_path) > max_out or os.path.getsize(err_path) > max_err:
                        raise ValueError("lab_ssh_output_exceeded")
                    if time.monotonic() >= deadline:
                        raise subprocess.TimeoutExpired(cmd, timeout)
                    time.sleep(0.02)
                _kill_group(proc)  # the leader is an unreaped zombie here: the group id is still ours
                returncode = proc.wait(timeout=5)
            if os.path.getsize(out_path) > max_out or os.path.getsize(err_path) > max_err:
                raise ValueError("lab_ssh_output_exceeded")
            if time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(cmd, timeout)
            with open(out_path, "rb") as out_file, open(err_path, "rb") as err_file:
                return subprocess.CompletedProcess(cmd, returncode, out_file.read(max_out).decode("utf-8", "replace"),
                                                   err_file.read(max_err).decode("utf-8", "replace"))
        finally:
            if proc is not None and proc.returncode is None:
                _kill_group(proc)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass


def _valid_remote_record(row) -> bool:
    """A frontier record is metadata only: known owner and bucket, matching ref, scalar-ish fields."""
    allowed = {"ref", "repo_id", "bucket", "eligible", *META}
    if not isinstance(row, dict) or not set(row) <= allowed:
        return False
    repo, bucket, ref = row.get("repo_id"), row.get("bucket"), row.get("ref")
    if repo not in LAYOUT or bucket not in LAYOUT[repo][1] or not isinstance(ref, str):
        return False
    if not ref.startswith(repo + ":" + bucket + "/") or not ref.endswith(".md") or ref.count("/") != 1:
        return False
    try:
        for key, value in row.items():
            clean_value(value)
    except ValueError:
        return False
    return True


def lab_frontier_over_ssh(args: argparse.Namespace) -> dict | None:
    """SSH transport to the *same* read-only portfolio tool on the registered lab.

    The SSH target and lab repo path are host-local configuration, never task
    metadata or committed topology. Fail explicitly rather than inventing a clone.
    """
    target = os.environ.get("AOTERU_LAB_SSH_TARGET", "").strip()
    remote_root = os.environ.get("AOTERU_LAB_REPO_ROOT", "").strip()
    if not target or not remote_root:
        return None
    if args.stage == "task" and not args.ref:
        raise ValueError("task requires an exact selected --ref")
    if target.startswith("-") or any(c.isspace() for c in target):
        raise ValueError("invalid lab SSH target")
    if not PurePosixPath(remote_root).is_absolute():  # the lab is POSIX whatever this host is
        raise ValueError("lab remote checkout path must be absolute")
    task_args = ["task", "--ref", args.ref, "--tier", args.tier] if args.stage == "task" else [
        "frontier", "--offset", str(args.offset), "--per-repo", str(args.per_repo)
    ]
    task_args += ["--max-tokens", str(args.max_tokens), "--local-only"]
    cmd = ("cd " + shlex.quote(remote_root) +
           " && python3 scripts/agentic_portfolio.py " + shlex.join(task_args))
    limit = args.max_tokens * 3
    try:
        proc = _ssh_run(
            ["ssh", "-n", "-T", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=8", target, cmd],
            timeout=30, max_out=limit * 4 + 4096, max_err=4096
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("lab_ssh_transport_failure: " + type(exc).__name__) from exc
    if proc.returncode != 0:
        raise ValueError("lab_ssh_execution_failed: exit=" + str(proc.returncode) +
                         "; " + proc.stderr.strip()[:250])
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("lab_ssh_invalid_portfolio_json") from exc
    # The remote is only trusted to answer the exact question that was asked.
    expected = ("L0-three-repository-frontier" if args.stage == "frontier" else
                "L1-selected-contract" if args.tier == "contract" else "L3-explicit-full-task")
    if not isinstance(result, dict) or result.get("stage") != expected:
        raise ValueError("lab_ssh_unexpected_portfolio_result")
    if args.stage == "frontier":
        records = result.get("records")
        if (not isinstance(records, list) or len(records) > args.per_repo * len(LAYOUT)
                or not isinstance(result.get("scope_complete"), bool)
                or not isinstance(result.get("counts"), dict)
                or not isinstance(result.get("unavailable"), dict)
                or not all(_valid_remote_record(row) for row in records)):
            raise ValueError("lab_ssh_malformed_portfolio_result")
    elif (result.get("ref") != args.ref or not isinstance(result.get("metadata"), dict)
            or not isinstance(result.get("body"), str)):
        raise ValueError("lab_ssh_malformed_portfolio_result")
    result["transport"] = "registered_lab_ssh"
    if len(json.dumps(result, ensure_ascii=False)) > limit:
        raise ValueError("lab_ssh_result_exceeds_budget")
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
    parser.add_argument("--local-only", action="store_true",
                        help="do not attempt a registered lab SSH fallback (used remotely)")
    parser.add_argument("--tier", choices=("contract", "full"), default="contract")
    args = parser.parse_args()
    if not 1 <= args.max_tokens <= 16000 or not 1 <= args.per_repo <= 20 or args.offset < 0:
        parser.error("invalid budget, per-repo count or offset")
    roots, missing = resolve_roots(args.repo_root, {"misumi": args.misumi_root, "obsidian-phd": args.phd_root})
    try:
        ssh_error = None
        # If this workstation lacks registered checkouts, try the authoritative
        # lab's own registry/checkout rather than treating a laptop clone as mandatory.
        # Selected-task reads fall back only when that task's own repository is
        # unavailable; an unrelated missing sibling must not abort a local read.
        ref_repo = args.ref.split(":", 1)[0] if args.stage == "task" and args.ref else None
        need_remote = bool(missing) if args.stage == "frontier" else (
            ref_repo is not None and ref_repo not in roots)
        if not args.local_only and need_remote:
            try:
                remote = lab_frontier_over_ssh(args)
            except ValueError as exc:
                if args.stage == "task":
                    raise
                ssh_error = str(exc)
                remote = None
            if remote is not None:
                print(json.dumps(remote, ensure_ascii=False))
                return 0
        if args.stage == "frontier":
            result = frontier(roots, missing, args.offset, args.per_repo, args.max_tokens,
                              transport_warning=ssh_error)
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

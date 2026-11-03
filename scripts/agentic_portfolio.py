#!/usr/bin/env python3
"""Read-only, progressive multi-repository task discovery. No new queue or dispatch."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path, PurePosixPath

import yaml

from agentic_context import (ROOT, PRIORITY, Refused, card_names, clean_value, fit_body,
                             queue_path, read_card, split_card)

FRONTIER_NOTE = "Metadata only; no cross-owner ranking yet. Inbox/open is NOT proof of accepted or executable work."
TASK_NOTE = "Untrusted task content; repository authority is external."
MAX_OFFSET = 10_000_000  # the same bound the receiver's count validation uses
TRANSPORT_RESERVE = 96  # >= the serialized cost of the "transport" field plus the truncated flag flip

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
              "note": FRONTIER_NOTE}
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
            tentative["transport"] = "registered_lab_ssh"  # the remote path adds this field after the fact
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


def parse_ref(ref) -> tuple[str, str, str]:
    """(repo_id, bucket, filename) of a well-formed `repo_id:bucket/file.md`, else ValueError.
    Checked BEFORE any transport is chosen, so an unknown reference can never reach the remote."""
    if not isinstance(ref, str) or ref.count(":") != 1:
        raise ValueError("expected repo_id:bucket/file.md reference")
    rid, local = ref.split(":", 1)
    if rid not in LAYOUT:
        raise ValueError("unknown or unavailable repository")
    parts = local.split("/")
    if (len(parts) != 2 or parts[0] not in LAYOUT[rid][1] or not parts[1].endswith(".md")
            or parts[1].startswith(".") or "\\" in parts[1] or "\x00" in parts[1]):
        raise ValueError("invalid task reference")
    return rid, parts[0], parts[1]


def selected(roots: dict[str, Path], ref: str, tier: str, budget: int) -> dict:
    """Load only the exact L0-selected file after validating its repository and path."""
    rid, bucket, name = parse_ref(ref)
    if rid not in roots:
        raise ValueError("unknown or unavailable repository")
    queue = queue_path(roots[rid], Path(LAYOUT[rid][0]))
    meta, body = split_card(read_card(queue, bucket, name))
    result = {"stage": "L1-selected-contract" if tier == "contract" else "L3-explicit-full-task",
              "ref": ref, "metadata": {k: clean_value(meta[k]) for k in DETAIL if k in meta},
              "truncated": False,  # sized with the longest literal; the final value is never longer
              "note": TASK_NOTE}
    wanted = body if tier == "full" else body[:16000]
    # Reserve the room the SSH transport adds ("transport": "registered_lab_ssh" = 35 characters).
    result["body"] = fit_body(result, wanted, budget * 3 - TRANSPORT_RESERVE)
    result["truncated"] = len(result["body"]) < len(body)
    return result



def _exited_unreaped(proc: subprocess.Popen) -> bool:
    """True once the child has exited. Where `waitid` exists the child is NOT reaped, so its
    pid/pgid stay reserved (a zombie leader keeps the group id from being recycled) until we
    have signalled the group. Elsewhere `poll()` reaps it and `_kill_group` then does nothing."""
    if hasattr(os, "waitid"):
        try:
            return os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
        except ChildProcessError as exc:  # something else reaped our child: ownership is lost
            raise ValueError("lab_ssh_child_ownership_lost") from exc
    return proc.poll() is not None


def _kill_group(proc: subprocess.Popen) -> None:
    """Best-effort kill of the child's process group while the child is still unreaped."""
    if proc.returncode is not None:  # already reaped: its pid may be recycled, so signal nothing
        return
    try:
        if os.name != "nt":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


def _printable(text: str, limit: int = 250) -> str:
    """Remote text made safe for a terminal: printable ASCII only, so no escape sequences survive."""
    return "".join(c if " " <= c <= "~" else "?" for c in text.strip())[:limit]


def _ssh_run(cmd: list[str], timeout: float, max_out: int, max_err: int) -> subprocess.CompletedProcess:
    """Run our own `ssh` toward the operator's lab with output captured to private temp FILES.

    Threat model: the REMOTE is untrusted, but only its output stream is, so memory and disk use
    must stay bounded and the call must finish. The local `ssh` binary and anything it spawns are
    not adversarial. Deliberately OUT OF SCOPE, because defending them needs OS containment
    (cgroups / Job Objects) that this 30-second call does not justify: a descendant that moves
    itself into another process group or session, hostile signal handlers or threaded callers
    running during spawn, and a child stuck in uninterruptible kernel sleep.

    Disk bound: where `prlimit` exists the caller runs ssh under a kernel write cap. Elsewhere
    (Windows) the only bound is polling every 5 ms, so a flooding remote can write at most its link
    throughput times 5 ms (tens of MB on a fast link) before the child is killed and the private
    temp directory removed. That residual overshoot is bounded and accepted, not eliminated.

    In scope: no reader threads or pipes; size is polled and capped, with one extra byte read at
    the end so a late write cannot be silently truncated into success; the deadline is enforced
    on the completion path too; overflow, the deadline or any exception kills the process group
    while the leader is still an unreaped zombie; the temp directory is always removed.
    """
    if os.name != "nt" and not hasattr(os, "waitid"):
        # Without waitid(WNOWAIT) the leader would be reaped before its group could be signalled,
        # which can orphan helpers or hit a recycled id. Refuse rather than guess.
        raise ValueError("lab_ssh_unsupported_platform")
    deadline = time.monotonic() + timeout
    proc = None
    with tempfile.TemporaryDirectory(prefix="agentic-ssh-") as tmp:
        out_path, err_path = os.path.join(tmp, "out"), os.path.join(tmp, "err")
        try:
            with open(out_path, "wb") as out_file, open(err_path, "wb") as err_file:
                proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out_file, stderr=err_file,
                                        start_new_session=(os.name != "nt"))
                while not _exited_unreaped(proc):
                    if os.path.getsize(out_path) > max_out or os.path.getsize(err_path) > max_err:
                        raise ValueError("lab_ssh_output_exceeded")
                    if time.monotonic() >= deadline:
                        raise subprocess.TimeoutExpired(cmd, timeout)
                    time.sleep(0.005)
                _kill_group(proc)  # the leader is an unreaped zombie here: the group id is still ours
                returncode = proc.wait(timeout=5)
            if time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(cmd, timeout)
            with open(out_path, "rb") as out_file, open(err_path, "rb") as err_file:
                out, err = out_file.read(max_out + 1), err_file.read(max_err + 1)
            if len(out) > max_out or len(err) > max_err:
                raise ValueError("lab_ssh_output_exceeded")
            return subprocess.CompletedProcess(cmd, returncode, out.decode("utf-8", "replace"),
                                               err.decode("utf-8", "replace"))
        finally:
            if proc is not None and proc.returncode is None:
                _kill_group(proc)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass


def _is_count(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 10_000_000


def _valid_remote_record(row) -> bool:
    """A frontier record is metadata only: known owner and bucket, matching ref, the literal
    `unverified` eligibility marker, and bounded JSON-safe fields."""
    allowed = {"ref", "repo_id", "bucket", "eligible", *META}
    if not isinstance(row, dict) or not set(row) <= allowed:
        return False
    repo, bucket, ref = row.get("repo_id"), row.get("bucket"), row.get("ref")
    if not all(isinstance(v, str) for v in (repo, bucket, ref)):
        return False
    if repo not in LAYOUT or bucket not in LAYOUT[repo][1] or row.get("eligible") != "unverified":
        return False
    try:
        if parse_ref(ref) != (repo, bucket, ref.split("/", 1)[1]):
            return False
        for value in row.values():
            clean_value(value)
    except ValueError:
        return False
    return True


FRONTIER_REQUIRED = {"stage", "scope_complete", "unavailable", "counts", "offset_per_repo", "records",
                     "next_offset_per_repo", "warnings", "note"}
FRONTIER_KEYS = FRONTIER_REQUIRED | {"transport"}
OPTIONAL_REPOS = {"misumi", "obsidian-phd"}  # odysseus is the running checkout and is always available


TOKEN = re.compile(r"[a-z_]{1,64}")
WARNING = re.compile(r"(odysseus|misumi|obsidian-phd):[A-Za-z0-9_.\-]{1,200}:[a-z_]{1,64}")


def _canonical_key(row: dict, owner_order: dict) -> tuple:
    """The order collect() and frontier() produce: owner, bucket rank, priority rank, then ref."""
    return (owner_order[row["repo_id"]], RANK[row["bucket"]],
            PRIORITY.get(str(row.get("priority", "")).lower(), 9), row["ref"])


def _valid_remote_frontier(result: dict, args: argparse.Namespace) -> bool:
    """Accept only what `frontier()` itself could have produced for this request."""
    if not FRONTIER_REQUIRED <= set(result) <= FRONTIER_KEYS or not isinstance(result.get("scope_complete"), bool):
        return False
    records, counts, unavailable = result.get("records"), result.get("counts"), result.get("unavailable")
    if not isinstance(records, list) or not isinstance(counts, dict) or not isinstance(unavailable, dict):
        return False
    if not all(isinstance(k, str) and isinstance(v, str) and TOKEN.fullmatch(v) for k, v in unavailable.items()):
        return False  # reasons are machine tokens, never prose
    # Repository coverage: every owner is exactly one of available (has counts) or unavailable.
    if (set(counts) | set(unavailable) != set(LAYOUT) or set(counts) & set(unavailable)
            or not set(unavailable) <= OPTIONAL_REPOS):
        return False
    if result["scope_complete"] != (not unavailable):  # complete iff nothing was unavailable
        return False
    totals = {}
    for repo, entry in counts.items():
        buckets = entry.get("buckets") if isinstance(entry, dict) else None
        if (not isinstance(entry, dict) or set(entry) != {"total", "buckets"} or not _is_count(entry["total"])
                or not isinstance(buckets, dict) or set(buckets) != set(LAYOUT[repo][1])   # every bucket, no extras
                or not all(_is_count(v) for v in buckets.values())
                or entry["total"] > sum(buckets.values())):  # unreadable cards make total <= bucket sum
            return False
        totals[repo] = entry["total"]
    if not all(_valid_remote_record(row) for row in records):
        return False
    refs = [row["ref"] for row in records]
    if len(set(refs)) != len(refs):
        return False
    owner_order = {repo: index for index, repo in enumerate(LAYOUT)}
    keys = [_canonical_key(row, owner_order) for row in records]
    if keys != sorted(keys):
        return False  # the remote may not reorder what the producer ranks
    taken = {repo: 0 for repo in counts}
    shown = {}
    for row in records:
        if row["repo_id"] not in counts:
            return False
        taken[row["repo_id"]] += 1
        shown[(row["repo_id"], row["bucket"])] = shown.get((row["repo_id"], row["bucket"]), 0) + 1
    if any(n > counts[repo]["buckets"][bucket] for (repo, bucket), n in shown.items()):
        return False  # a record from a bucket the response itself says is smaller
    for repo, n in taken.items():
        # An owner whose total is below the requested offset shows nothing (an empty slice is valid);
        # one that shows records cannot show more than it has past that offset.
        if n > args.per_repo or (n > 0 and args.offset + n > totals[repo]):
            return False
    if not records and any(total > args.offset for total in totals.values()):
        return False  # the producer refuses an empty page while anything remains: it could never advance
    if not _is_count(result["offset_per_repo"]) or result["offset_per_repo"] != args.offset:
        return False
    # Pagination is DERIVED, not trusted: each owner continues exactly after what it showed.
    expected = {repo: args.offset + n for repo, n in taken.items() if args.offset + n < totals[repo]}
    following = result["next_offset_per_repo"]
    if (not isinstance(following, dict) or not all(isinstance(k, str) and _is_count(v) for k, v in following.items())
            or following != expected):  # _is_count first: True and 1.0 must not compare equal to 1
        return False
    warnings = result["warnings"]
    return (result["note"] == FRONTIER_NOTE   # the fixed safety notice, verbatim
            and isinstance(warnings, list) and len(warnings) <= 8
            and all(isinstance(w, str) and WARNING.fullmatch(w) for w in warnings))


TASK_REQUIRED = {"stage", "ref", "metadata", "body", "truncated", "note"}
TASK_KEYS = TASK_REQUIRED | {"transport"}


def _valid_remote_task(result: dict, args: argparse.Namespace) -> bool:
    if not TASK_REQUIRED <= set(result) <= TASK_KEYS or result.get("ref") != args.ref:
        return False
    metadata, body = result["metadata"], result["body"]
    if (not isinstance(metadata, dict) or not set(metadata) <= set(DETAIL) or not isinstance(body, str)
            or not isinstance(result.get("truncated"), bool) or result["note"] != TASK_NOTE):
        return False
    if args.tier == "contract" and len(body) > 16000:  # the producer's own contract-body cap
        return False
    try:
        for value in metadata.values():
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
    if args.stage == "task":
        parse_ref(args.ref)  # a malformed or unknown reference never leaves this machine
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
    max_out, max_err = limit * 4 + 4096, 4096
    ssh_cmd = ["ssh", "-n", "-T", "-o", "BatchMode=yes",
               "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=8", target, cmd]
    prlimit = shutil.which("prlimit") if os.name != "nt" else None
    if prlimit:  # kernel-enforced cap on what the child can write (generous margin for ssh's own files)
        ssh_cmd = [prlimit, "--fsize=%d" % (max(max_out, max_err) + (1 << 20)), "--"] + ssh_cmd
    try:
        proc = _ssh_run(ssh_cmd, timeout=30, max_out=max_out, max_err=max_err)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("lab_ssh_transport_failure: " + type(exc).__name__) from exc
    if proc.returncode != 0:
        raise ValueError("lab_ssh_execution_failed: exit=" + str(proc.returncode) +
                         "; " + _printable(proc.stderr))
    try:
        result = json.loads(proc.stdout)
    except (ValueError, RecursionError) as exc:  # JSONDecodeError is a ValueError; deep nesting recurses
        raise ValueError("lab_ssh_invalid_portfolio_json") from exc
    # The remote is only trusted to answer the exact question that was asked.
    expected = ("L0-three-repository-frontier" if args.stage == "frontier" else
                "L1-selected-contract" if args.tier == "contract" else "L3-explicit-full-task")
    if not isinstance(result, dict) or result.get("stage") != expected:
        raise ValueError("lab_ssh_unexpected_portfolio_result")
    valid = (_valid_remote_frontier(result, args) if args.stage == "frontier"
             else _valid_remote_task(result, args))
    if not valid:
        raise ValueError("lab_ssh_malformed_portfolio_result")
    result["transport"] = "registered_lab_ssh"
    rendered = json.dumps(result, ensure_ascii=False)
    try:
        rendered.encode("utf-8")  # a lone surrogate parses fine but would crash the final print
    except UnicodeEncodeError as exc:
        raise ValueError("lab_ssh_malformed_portfolio_result") from exc
    if len(rendered) > limit:
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
    if not 1 <= args.max_tokens <= 16000 or not 1 <= args.per_repo <= 20 or not 0 <= args.offset <= MAX_OFFSET:
        parser.error("invalid budget, per-repo count or offset")
    roots, missing = resolve_roots(args.repo_root, {"misumi": args.misumi_root, "obsidian-phd": args.phd_root})
    try:
        ssh_error = None
        # If this workstation lacks registered checkouts, try the authoritative
        # lab's own registry/checkout rather than treating a laptop clone as mandatory.
        # Selected-task reads fall back only when that task's own repository is
        # unavailable; an unrelated missing sibling must not abort a local read.
        ref_repo = None
        if args.stage == "task":
            if not args.ref:
                parser.error("task requires --ref from frontier")
            ref_repo = parse_ref(args.ref)[0]  # malformed refs fail here, before any transport
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

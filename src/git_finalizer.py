"""src/git_finalizer.py — safe, scope-bounded finalisation of a completed
implementation task inside its verified isolated leased worktree.

Reviewed but deliberately NOT adopted from the recovered
~/aoteru-recovery reference material: that version resolved the finalise
target via resolve_repo_path() (the live registered checkout, not an
isolated worktree) and staged with a blind `git add -A`, which would
silently absorb any unrelated dirty or untracked file already sitting in
the repo alongside whatever the task actually touched. This module fixes
both: it only ever operates on the lease's independently verified
isolated worktree (never the live checkout, via the same worktree_ops
authority execute_codex_write already depends on), and it only ever
stages the caller's explicitly authorised paths - if the worktree has ANY
dirty or untracked path outside that authorised scope, the whole
finalisation refuses (fail closed) rather than silently dropping the
unexpected path or absorbing it anyway.
"""
from __future__ import annotations

import subprocess

from src import worktree_ops
from src.park_lease_ops import active_lease_for_repo


def _run_git(repo_path: str, args: list[str], *, timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", repo_path, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _porcelain_paths(porcelain_output: str) -> set[str]:
    """Parse `git status --porcelain` output into the set of paths it
    touches. Handles the rename `old -> new` form by including both
    sides - a rename must be explicitly authorised under both names, not
    slip through because only one side matched."""
    paths: set[str] = set()
    for line in porcelain_output.splitlines():
        if not line:
            continue
        path_part = line[3:]
        if " -> " in path_part:
            old, new = path_part.split(" -> ", 1)
            paths.add(old.strip().strip('"'))
            paths.add(new.strip().strip('"'))
        else:
            paths.add(path_part.strip().strip('"'))
    return paths


def finalize_scoped(
    repo_id: str,
    host_id: str,
    *,
    expected_branch: str,
    allowed_paths: list[str],
    commit_message: str,
    push: bool = True,
) -> dict:
    """Commit (and by default push) only `allowed_paths` inside the
    caller's verified isolated leased worktree for repo_id+host_id.

    Fails closed - stages and commits nothing - whenever:
    - no active, non-stale, repo-write-scoped lease exists for this
      repo_id+host_id;
    - the lease's worktree_path is the live registered checkout, or does
      not independently verify as a real linked worktree on
      expected_branch (the same authority execute_codex_write depends
      on - this can never diverge from what execution actually used);
    - the worktree has no changes at all;
    - the worktree has ANY dirty or untracked path that is not in
      allowed_paths - the entire finalisation is refused, not just the
      unexpected path skipped, so an unrelated file already sitting dirty
      in the worktree can never be silently absorbed into this task's
      commit.

    Only paths that are both authorised AND actually dirty are ever
    staged - never `git add -A`, and never an authorised path that
    happens not to have been touched.
    """
    if not allowed_paths:
        return {"finalized": False, "reason": "no_allowed_paths_supplied"}

    lease = active_lease_for_repo(repo_id, host_id)
    if lease is None:
        return {"finalized": False, "reason": "lease_missing_or_stale"}
    if lease.get("allowed_write_scope") != "repo":
        return {"finalized": False, "reason": "lease_does_not_grant_repo_write_scope"}
    lease_path = lease.get("worktree_path")
    if not lease_path:
        return {"finalized": False, "reason": "lease_missing_worktree_path"}

    if worktree_ops.is_live_checkout_path(repo_id, lease_path):
        return {"finalized": False, "reason": "refusing to finalize in the live registered checkout"}

    verification = worktree_ops.verify_worktree(repo_id, lease_path, expected_branch)
    if not verification["ok"]:
        return {
            "finalized": False,
            "reason": f"worktree_verification_failed: {verification['reason']}",
        }

    repo_path = verification["path"]

    try:
        status_proc = _run_git(repo_path, ["status", "--porcelain"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"finalized": False, "reason": f"status_check_failed: {exc}"}
    if status_proc.returncode != 0:
        return {
            "finalized": False,
            "reason": f"status_check_failed: {status_proc.stderr.strip() or 'git status failed'}",
        }

    dirty_paths = _porcelain_paths(status_proc.stdout)
    if not dirty_paths:
        return {"finalized": False, "reason": "no_changes_to_finalize"}

    allowed_set = set(allowed_paths)
    unexpected = dirty_paths - allowed_set
    if unexpected:
        return {
            "finalized": False,
            "reason": "scope_violation",
            "unexpected_paths": sorted(unexpected),
        }

    paths_to_stage = sorted(dirty_paths & allowed_set)

    try:
        add_proc = _run_git(repo_path, ["add", "--", *paths_to_stage])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"finalized": False, "reason": f"add_failed: {exc}"}
    if add_proc.returncode != 0:
        return {
            "finalized": False,
            "reason": f"add_failed: {add_proc.stderr.strip() or 'git add failed'}",
        }

    try:
        commit_proc = _run_git(repo_path, ["commit", "-m", commit_message])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"finalized": False, "reason": f"commit_failed: {exc}"}
    if commit_proc.returncode != 0:
        return {
            "finalized": False,
            "reason": f"commit_failed: {commit_proc.stderr.strip()}",
        }

    try:
        head_proc = _run_git(repo_path, ["rev-parse", "HEAD"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"finalized": False, "committed": True, "reason": f"commit_head_failed: {exc}"}
    if head_proc.returncode != 0:
        return {
            "finalized": False, "committed": True,
            "reason": f"commit_head_failed: {head_proc.stderr.strip() or 'git rev-parse failed'}",
        }
    commit_sha = head_proc.stdout.strip()

    result = {
        "finalized": True,
        "committed": True,
        "commit_sha": commit_sha,
        "branch": expected_branch,
        "staged_paths": paths_to_stage,
        "lease_id": lease["lease_id"],
    }

    if not push:
        result["pushed"] = False
        return result

    try:
        push_proc = _run_git(repo_path, ["push", "origin", expected_branch], timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        result.update({"finalized": False, "pushed": False, "reason": f"push_failed: {exc}"})
        return result
    if push_proc.returncode != 0:
        result.update({
            "finalized": False, "pushed": False,
            "reason": f"push_failed: {push_proc.stderr.strip()}",
        })
        return result

    result["pushed"] = True
    return result

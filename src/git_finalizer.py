from __future__ import annotations

import subprocess
from typing import Optional

from src.estate_router import resolve_repo_path
from src.park_lease_ops import active_lease_for_repo


def _run_git(repo_path: str, argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=60,
    )


def finalize(
    repo_id: str,
    host_id: str,
    expected_branch: str,
    execution_id: str,
    commit_message: str,
    expected_base_head: Optional[str] = None,
) -> dict:
    lease = active_lease_for_repo(repo_id, host_id)
    if lease is None:
        return {"finalized": False, "reason": "lease_missing_or_stale"}

    repo_path = resolve_repo_path(repo_id)
    if repo_path is None:
        return {"finalized": False, "reason": "repo_path_unresolved"}

    try:
        branch_proc = _run_git(
            repo_path,
            ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"finalized": False, "reason": f"branch_check_failed: {exc}"}
    if branch_proc.returncode != 0:
        return {
            "finalized": False,
            "reason": f"branch_check_failed: {branch_proc.stderr.strip() or 'git rev-parse failed'}",
        }
    actual_branch = branch_proc.stdout.strip()
    if actual_branch != expected_branch:
        return {
            "finalized": False,
            "reason": f"branch_mismatch: on {actual_branch} expected {expected_branch}",
        }

    try:
        head_proc = _run_git(repo_path, ["git", "-C", repo_path, "rev-parse", "HEAD"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"finalized": False, "reason": f"head_check_failed: {exc}"}
    if head_proc.returncode != 0:
        return {
            "finalized": False,
            "reason": f"head_check_failed: {head_proc.stderr.strip() or 'git rev-parse failed'}",
        }
    current_head = head_proc.stdout.strip()
    if expected_base_head is not None and current_head != expected_base_head:
        return {
            "finalized": False,
            "reason": f"head_drift: expected {expected_base_head} got {current_head}",
            "current_head": current_head,
        }

    try:
        status_proc = _run_git(repo_path, ["git", "-C", repo_path, "status", "--porcelain"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"finalized": False, "reason": f"status_check_failed: {exc}"}
    if status_proc.returncode != 0:
        return {
            "finalized": False,
            "reason": f"status_check_failed: {status_proc.stderr.strip() or 'git status failed'}",
        }
    if not status_proc.stdout.strip():
        return {"finalized": False, "reason": "no_changes_to_finalize"}

    try:
        diff_proc = _run_git(repo_path, ["git", "-C", repo_path, "diff", "--stat"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"finalized": False, "reason": f"diff_stat_failed: {exc}"}
    if diff_proc.returncode != 0:
        return {
            "finalized": False,
            "reason": f"diff_stat_failed: {diff_proc.stderr.strip() or 'git diff failed'}",
        }
    diff_stat = diff_proc.stdout

    try:
        add_proc = _run_git(repo_path, ["git", "-C", repo_path, "add", "-A"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"finalized": False, "reason": f"add_failed: {exc}"}
    if add_proc.returncode != 0:
        return {
            "finalized": False,
            "reason": f"add_failed: {add_proc.stderr.strip() or 'git add failed'}",
        }

    try:
        commit_proc = _run_git(
            repo_path,
            ["git", "-C", repo_path, "commit", "-m", commit_message],
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"finalized": False, "reason": f"commit_failed: {exc}"}
    if commit_proc.returncode != 0:
        return {
            "finalized": False,
            "reason": f"commit_failed: {commit_proc.stderr.strip()}",
        }

    try:
        commit_head_proc = _run_git(repo_path, ["git", "-C", repo_path, "rev-parse", "HEAD"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"finalized": False, "reason": f"commit_head_failed: {exc}"}
    if commit_head_proc.returncode != 0:
        return {
            "finalized": False,
            "reason": f"commit_head_failed: {commit_head_proc.stderr.strip() or 'git rev-parse failed'}",
        }
    commit_sha = commit_head_proc.stdout.strip()

    try:
        push_proc = _run_git(
            repo_path,
            ["git", "-C", repo_path, "push", "origin", expected_branch],
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "finalized": False,
            "committed": True,
            "pushed": False,
            "commit_sha": commit_sha,
            "reason": f"push_failed: {exc}",
        }
    if push_proc.returncode != 0:
        return {
            "finalized": False,
            "committed": True,
            "pushed": False,
            "commit_sha": commit_sha,
            "reason": f"push_failed: {push_proc.stderr.strip()}",
        }

    return {
        "finalized": True,
        "committed": True,
        "pushed": True,
        "commit_sha": commit_sha,
        "branch": expected_branch,
        "diff_stat": diff_stat,
        "lease_id": lease["lease_id"],
        "execution_id": execution_id,
    }

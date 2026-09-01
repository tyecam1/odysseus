"""Git worktree helpers for isolated implementation leases."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional


_UNSAFE_BRANCH_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_branch_for_path(branch: str) -> str:
    """Map a branch name to a deterministic filesystem-safe directory name."""
    cleaned = _UNSAFE_BRANCH_CHARS_RE.sub("_", branch.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "branch"


def _resolve_registered_repo_path(repo_id: str) -> Optional[Path]:
    from src.estate_router import resolve_repo_path

    resolved = resolve_repo_path(repo_id)
    return Path(resolved).resolve() if resolved else None


def _worktree_root_for_repo(repo_id: str, repo_path: Path) -> Path:
    if repo_path.parent.name == "projects":
        return repo_path.parent.parent / "aoteru-worktrees" / repo_id
    return repo_path.parent / "aoteru-worktrees" / repo_id


def worktree_path_for_branch(repo_id: str, branch: str) -> Optional[Path]:
    repo_path = _resolve_registered_repo_path(repo_id)
    if repo_path is None:
        return None
    return _worktree_root_for_repo(repo_id, repo_path) / sanitize_branch_for_path(branch)


def is_live_checkout_path(repo_id: str, path: str) -> bool:
    """True when `path` resolves to the registered live checkout for `repo_id`."""
    repo_path = _resolve_registered_repo_path(repo_id)
    if repo_path is None:
        return False
    try:
        return Path(path).resolve() == repo_path
    except OSError:
        return False


def _run_git(args: list[str], *, cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _parse_worktree_list(porcelain: str) -> list[dict]:
    entries: list[dict] = []
    current: dict[str, str | bool] = {}
    for line in porcelain.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        if line == "bare":
            current["bare"] = True
            continue
        if line == "detached":
            current["detached"] = True
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    if current:
        entries.append(current)
    return entries


def _branch_exists(repo_path: Path, branch: str) -> bool:
    result = _run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=repo_path)
    return result.returncode == 0


def verify_worktree(
    repo_id: str,
    worktree_path: str,
    expected_branch: str,
    *,
    expected_head: Optional[str] = None,
) -> dict:
    """Validate that a path is the expected linked worktree for a registered repo."""
    try:
        repo_path = _resolve_registered_repo_path(repo_id)
        if repo_path is None:
            return {"ok": False, "reason": "registered repo path does not resolve on this host", "code": "repo_unresolvable"}

        path = Path(worktree_path)
        if not path.exists():
            return {"ok": False, "reason": "worktree path does not exist", "code": "path_missing"}
        if not path.is_dir():
            return {"ok": False, "reason": "worktree path is not a directory", "code": "path_not_directory"}

        listing = _run_git(["worktree", "list", "--porcelain"], cwd=repo_path)
        if listing.returncode != 0:
            reason = listing.stderr.strip() or "git worktree list failed"
            return {"ok": False, "reason": reason, "code": "worktree_list_failed"}

        resolved_path = path.resolve()
        entry = None
        for candidate in _parse_worktree_list(listing.stdout):
            listed = candidate.get("worktree")
            if listed and Path(str(listed)).resolve() == resolved_path:
                entry = candidate
                break
        if entry is None:
            return {
                "ok": False,
                "reason": "path is not a registered linked git worktree for this repo",
                "code": "not_registered",
            }

        branch_result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=resolved_path)
        if branch_result.returncode != 0:
            reason = branch_result.stderr.strip() or "git rev-parse --abbrev-ref HEAD failed"
            return {"ok": False, "reason": reason, "code": "branch_probe_failed"}
        actual_branch = branch_result.stdout.strip()
        if actual_branch != expected_branch:
            return {
                "ok": False,
                "reason": f"worktree branch mismatch: expected {expected_branch!r}, found {actual_branch!r}",
                "code": "branch_mismatch",
                "actual_branch": actual_branch,
            }

        head_result = _run_git(["rev-parse", "HEAD"], cwd=resolved_path)
        if head_result.returncode != 0:
            reason = head_result.stderr.strip() or "git rev-parse HEAD failed"
            return {"ok": False, "reason": reason, "code": "head_probe_failed"}
        actual_head = head_result.stdout.strip()
        if expected_head is not None and actual_head != expected_head:
            return {
                "ok": False,
                "reason": f"worktree HEAD mismatch: expected {expected_head!r}, found {actual_head!r}",
                "code": "head_mismatch",
                "actual_head": actual_head,
            }

        listed_branch = entry.get("branch")
        expected_branch_ref = f"refs/heads/{expected_branch}"
        if listed_branch != expected_branch_ref:
            return {
                "ok": False,
                "reason": f"worktree list branch mismatch: expected {expected_branch_ref!r}, found {listed_branch!r}",
                "code": "listed_branch_mismatch",
                "actual_branch": actual_branch,
            }

        return {
            "ok": True,
            "path": str(resolved_path),
            "branch": actual_branch,
            "head": actual_head,
            "repo_path": str(repo_path),
        }
    except Exception as exc:
        return {"ok": False, "reason": f"worktree verification failed: {exc}", "code": "verification_error"}


def create_or_reuse_worktree(repo_id: str, branch: str, *, base_ref: str = "HEAD") -> dict:
    """Create or reuse the deterministic linked worktree for `repo_id` and `branch`."""
    repo_path = _resolve_registered_repo_path(repo_id)
    if repo_path is None:
        raise RuntimeError(f"cannot create worktree: registered repo {repo_id!r} does not resolve on this host")

    worktree_path = _worktree_root_for_repo(repo_id, repo_path) / sanitize_branch_for_path(branch)
    verification = verify_worktree(repo_id, str(worktree_path), branch)
    if verification["ok"]:
        return {"path": verification["path"], "branch": branch, "created": False}

    if worktree_path.exists():
        raise RuntimeError(
            f"refusing to create worktree at {worktree_path}: existing path failed verification ({verification['reason']})"
        )

    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if _branch_exists(repo_path, branch):
            result = _run_git(["worktree", "add", str(worktree_path), branch], cwd=repo_path, timeout=60)
        else:
            result = _run_git(
                ["worktree", "add", "-b", branch, str(worktree_path), base_ref],
                cwd=repo_path,
                timeout=60,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"git worktree add failed for {repo_id!r} branch {branch!r}: {exc}") from exc
    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip() or "git worktree add failed"
        raise RuntimeError(f"git worktree add failed for {repo_id!r} branch {branch!r}: {reason}")

    verification = verify_worktree(repo_id, str(worktree_path), branch)
    if not verification["ok"]:
        raise RuntimeError(
            f"created worktree for {repo_id!r} branch {branch!r} but verification failed: {verification['reason']}"
        )
    return {"path": verification["path"], "branch": branch, "created": True}


def cleanup_worktree(repo_id: str, worktree_path: str, *, expected_branch: str) -> dict:
    """Remove a clean linked worktree and refuse to delete a dirty or live one."""
    verification = verify_worktree(repo_id, worktree_path, expected_branch)
    if not verification["ok"]:
        return verification
    path = Path(verification["path"])
    repo_path = _resolve_registered_repo_path(repo_id)
    if repo_path is None:
        return {"ok": False, "reason": "registered repo path does not resolve on this host", "code": "repo_unresolvable"}
    if is_live_checkout_path(repo_id, str(path)):
        return {"ok": False, "reason": "refusing to remove the registered live checkout path", "code": "live_checkout"}

    try:
        status = _run_git(["status", "--porcelain"], cwd=path, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "reason": f"git status failed: {exc}", "code": "status_failed"}
    if status.returncode != 0:
        return {"ok": False, "reason": status.stderr.strip() or "git status failed", "code": "status_failed"}
    if status.stdout.strip():
        return {"ok": False, "reason": "refusing to remove dirty worktree", "code": "dirty"}

    try:
        remove = _run_git(["worktree", "remove", str(path)], cwd=repo_path, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "reason": f"git worktree remove failed: {exc}", "code": "remove_failed"}
    if remove.returncode != 0:
        reason = remove.stderr.strip() or remove.stdout.strip() or "git worktree remove failed"
        return {"ok": False, "reason": reason, "code": "remove_failed"}
    return {"ok": True, "path": str(path), "removed": True}

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
stages the caller's explicitly authorised exact file paths - if the
worktree has ANY dirty or untracked path outside that authorised scope,
the whole finalisation refuses (fail closed) rather than silently
dropping the unexpected path or absorbing it anyway.

Controller review hardened the scope boundary itself: `git status
--porcelain` (v1, text mode) is not a strong enough parsing target for a
security boundary - an untracked directory collapses to one `?? dir/`
line (staging it can recursively pull in files never individually
observed), and filenames containing a literal "->" can be misparsed as
rename syntax. This module instead uses `git status --porcelain=v1 -z
--untracked-files=all`, parses the NUL-delimited machine format
(including the separate-field rename/copy form, never text-embedded), and
runs every path-taking git command with `--literal-pathspecs` so a
filename can never be interpreted as pathspec magic. `allowed_paths` must
be exact repo-relative file paths - never directories, globs, or
traversal - validated before any git state is touched.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from src import worktree_ops
from src.park_lease_ops import active_lease_for_repo

_RENAME_OR_COPY = ("R", "C")


def _run_git(repo_path: str, args: list[str], *, timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "--literal-pathspecs", "-C", repo_path, *args],
        capture_output=True,
        text=False,
        timeout=timeout,
    )


def _parse_porcelain_z(raw: bytes) -> list[dict]:
    """Parse `git status --porcelain=v1 -z` output into structured
    entries. In -z mode a rename/copy record is TWO NUL-terminated
    fields - `XY PATH\\0ORIG_PATH\\0` - never the text-mode `PATH ->
    ORIG_PATH` form, so a filename that happens to contain a literal
    "->" is never misread as a rename."""
    tokens = raw.split(b"\x00")
    entries: list[dict] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if not token:
            i += 1
            continue
        status = token[:2].decode("utf-8", "surrogateescape")
        path = token[3:].decode("utf-8", "surrogateescape")
        orig_path = None
        if status[0] in _RENAME_OR_COPY or status[1] in _RENAME_OR_COPY:
            i += 1
            if i < len(tokens) and tokens[i]:
                orig_path = tokens[i].decode("utf-8", "surrogateescape")
        entries.append({"status": status, "path": path, "orig_path": orig_path})
        i += 1
    return entries


def _entry_paths(entries: list[dict]) -> set[str]:
    """Every exact repo-relative path an entry set touches, including
    both sides of a rename/copy - a rename must be authorised under
    both its old and new name, not slip through on one side matching."""
    paths: set[str] = set()
    for entry in entries:
        paths.add(entry["path"])
        if entry["orig_path"]:
            paths.add(entry["orig_path"])
    return paths


def _status_paths(repo_path: str) -> tuple[bool, str | None, set[str]]:
    """Run the machine-safe status protocol once and return the exact
    path set it reports. `ok=False` on any git failure - status itself
    failing must fail closed, never be treated as "nothing dirty"."""
    try:
        proc = subprocess.run(
            ["git", "--literal-pathspecs", "-C", repo_path,
             "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            capture_output=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"status_check_failed: {exc}", set()
    if proc.returncode != 0:
        return False, f"status_check_failed: {proc.stderr.decode(errors='replace').strip() or 'git status failed'}", set()
    return True, None, _entry_paths(_parse_porcelain_z(proc.stdout))


def _validate_allowed_paths(allowed_paths: list[str], repo_root: Path) -> str | None:
    """Every entry must be an exact repo-relative file path. Returns an
    error string for the first violation found, or None if all pass.
    Deliberately conservative: anything ambiguous is rejected rather
    than guessed at, since this is the actual scope-authority boundary,
    not a convenience API."""
    for raw in allowed_paths:
        if not raw:
            return "empty path in allowed_paths"
        if raw in (".", ".."):
            return f"invalid path {raw!r} in allowed_paths"
        if raw.startswith(":"):
            return f"pathspec-magic-like path {raw!r} not allowed - use an exact file path"
        normalized = raw.replace("\\", "/")
        if normalized.startswith("/"):
            return f"absolute path {raw!r} not allowed in allowed_paths"
        if len(normalized) >= 2 and normalized[1] == ":":
            return f"absolute path {raw!r} not allowed in allowed_paths"
        if normalized.endswith("/"):
            return f"directory-like path {raw!r} not allowed - list exact files, not directories"
        segments = normalized.split("/")
        if "" in segments:
            return f"malformed path {raw!r} (empty segment)"
        if ".." in segments:
            return f"path traversal in {raw!r}"
        if "." in segments:
            return f"malformed path {raw!r} (contains '.')"
        resolved = (repo_root / normalized).resolve()
        try:
            resolved.relative_to(repo_root)
        except ValueError:
            return f"path {raw!r} resolves outside the worktree"
    return None


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

    Fails closed - stages and commits nothing, and never resets/discards
    whatever it finds - whenever:
    - `allowed_paths` is empty, or any entry is not an exact,
      repo-relative, in-worktree file path;
    - no active, non-stale, repo-write-scoped lease exists for this
      repo_id+host_id;
    - the lease's worktree_path is the live registered checkout, or does
      not independently verify as a real linked worktree on
      expected_branch (the same authority execute_codex_write depends
      on - this can never diverge from what execution actually used);
    - the worktree has no changes at all;
    - the worktree has ANY dirty or untracked path (exact file, not
      directory - untracked-files=all lists every file individually)
      that is not in allowed_paths;
    - anything staged after `git add` is not an exact subset of the
      authorised set, or anything new and unexpected appears in the
      worktree between the initial scope check and staging (a
      concurrent writer race) - re-checked immediately before commit;
    - the worktree is not completely clean immediately after commit -
      residual dirty/untracked content blocks reporting success and
      blocks push, even though a commit may already exist locally.
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
    repo_root = Path(repo_path).resolve()

    path_error = _validate_allowed_paths(allowed_paths, repo_root)
    if path_error is not None:
        return {"finalized": False, "reason": f"invalid_allowed_path: {path_error}"}

    ok, error, dirty_paths = _status_paths(repo_path)
    if not ok:
        return {"finalized": False, "reason": error}
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
            "reason": f"add_failed: {add_proc.stderr.decode(errors='replace').strip() or 'git add failed'}",
        }

    # Defence-in-depth against a concurrent writer: re-derive exactly
    # what is now staged from the index itself, not from what we
    # intended to stage, and re-run the full status scan again for
    # anything new that appeared in the window since the first check.
    try:
        staged_proc = subprocess.run(
            ["git", "--literal-pathspecs", "-C", repo_path,
             "diff", "--cached", "--name-only", "-z"],
            capture_output=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"finalized": False, "reason": f"staged_check_failed: {exc}"}
    if staged_proc.returncode != 0:
        return {
            "finalized": False,
            "reason": f"staged_check_failed: {staged_proc.stderr.decode(errors='replace').strip() or 'git diff --cached failed'}",
        }
    staged_paths = {p.decode("utf-8", "surrogateescape") for p in staged_proc.stdout.split(b"\x00") if p}
    staged_unexpected = staged_paths - allowed_set
    if staged_unexpected:
        return {
            "finalized": False,
            "reason": "staged_scope_violation",
            "unexpected_paths": sorted(staged_unexpected),
        }

    ok, error, post_stage_dirty = _status_paths(repo_path)
    if not ok:
        return {"finalized": False, "reason": error}
    post_stage_unexpected = post_stage_dirty - allowed_set
    if post_stage_unexpected:
        return {
            "finalized": False,
            "reason": "concurrent_write_detected",
            "unexpected_paths": sorted(post_stage_unexpected),
        }

    # Path-limited commit as a second, independent enforcement of scope -
    # even if the index somehow held more than intended, this only ever
    # commits the authorised paths.
    try:
        commit_proc = _run_git(repo_path, ["commit", "-m", commit_message, "--", *paths_to_stage])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"finalized": False, "reason": f"commit_failed: {exc}"}
    if commit_proc.returncode != 0:
        return {
            "finalized": False,
            "reason": f"commit_failed: {commit_proc.stderr.decode(errors='replace').strip()}",
        }

    try:
        head_proc = _run_git(repo_path, ["rev-parse", "HEAD"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"finalized": False, "committed": True, "reason": f"commit_head_failed: {exc}"}
    if head_proc.returncode != 0:
        return {
            "finalized": False, "committed": True,
            "reason": f"commit_head_failed: {head_proc.stderr.decode(errors='replace').strip() or 'git rev-parse failed'}",
        }
    commit_sha = head_proc.stdout.decode().strip()

    # The worktree must be completely clean immediately after commit -
    # anything left dirty (whether from before staging that somehow
    # wasn't caught, or introduced during the commit itself) means the
    # true final state is not what was authorised, and this must not be
    # reported as a clean success or pushed. Nothing is reset/discarded
    # either way - a human needs to see exactly what is left.
    ok, error, residual = _status_paths(repo_path)
    if not ok:
        return {"finalized": False, "committed": True, "commit_sha": commit_sha, "reason": error}
    if residual:
        return {
            "finalized": False,
            "committed": True,
            "commit_sha": commit_sha,
            "reason": "residual_dirty_state_after_commit",
            "unexpected_paths": sorted(residual),
        }

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
            "reason": f"push_failed: {push_proc.stderr.decode(errors='replace').strip()}",
        })
        return result

    result["pushed"] = True
    return result

"""Shared ParkLease mutation logic (Workstream B: "a park/release/heartbeat
HTTP surface so the client can cover those scripts/agent subcommands too").

`scripts/agent`'s `park`/`heartbeat`/`release` CLI subcommands and
`routes/estate_routing_routes.py`'s HTTP surface both call this rather than
each re-deriving lease semantics (stale-lease reclaim, live-lease
fail-closed, heartbeat renewal) — a second copy would be exactly the kind
of duplicate authority docs/aoteru-model-host-routing-contract.md already
forbids for routing decisions, and lease mutation deserves the same
discipline.

`park_repo`/`heartbeat_repo`/`release_repo` still take an already-resolved
worktree path and don't infer the caller's host — those stay call-site
concerns. `park_repo_by_id` (added for docs/aoteru-final-convergence-
activation.agent-task.md item D: "remote park is still a real controller
gap") is the one exception: it resolves repo_id -> real path via
`src.estate_router.resolve_repo_path` (registered repos only, no
arbitrary path from a caller) and fails closed on a dirty/unresolved
worktree via `git_is_clean` below, before ever calling `park_repo` — this
is what makes it safe to expose over HTTP to a remote (e.g. laptop)
caller who supplies only a repo_id, never a path.
"""
from __future__ import annotations

import subprocess
import uuid
from typing import Optional

from src import worktree_ops


class ParkConflict(Exception):
    """An active, non-stale lease already exists for this repo — fail closed."""


class NoActiveLease(Exception):
    """heartbeat/release found no matching active lease to act on."""


class RepoNotResolvable(Exception):
    """repo_id is unregistered, or its root var/path doesn't resolve on
    this host — fail closed rather than guessing a path."""


class RepoNotClean(Exception):
    """The resolved worktree has uncommitted changes (or git itself
    failed) — fail closed rather than parking a dirty tree."""


class WorktreeVerificationError(Exception):
    """The requested implementation worktree could not be created or verified."""


def git_is_clean(path: str) -> tuple[bool, str]:
    """Fail closed: anything but a clean `git status --porcelain`
    (including the command itself failing) is treated as dirty. Shared
    by `scripts/agent`'s `park` CLI subcommand and `park_repo_by_id`
    below — not re-derived per caller."""
    try:
        out = subprocess.run(
            ["git", "-C", path, "status", "--porcelain"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"git status failed: {e}"
    if out.returncode != 0:
        return False, out.stderr.strip() or "git status failed"
    if out.stdout.strip():
        return False, "working tree has uncommitted changes"
    return True, ""


def park_repo_by_id(
    repo_id: str,
    host_id: str,
    *,
    branch: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    """Safe remote-callable park acquisition: repo_id in, no path ever
    supplied by the caller. Resolves the real worktree path via
    `src.estate_router.resolve_repo_path` (registered repos only) and
    fails closed (`RepoNotResolvable`) if it doesn't resolve on this
    host; fails closed (`RepoNotClean`) if the resolved worktree is
    dirty or git itself fails. Only then delegates to `park_repo` — same
    stale-reclaim/live-conflict semantics, not re-derived."""
    from src.estate_router import resolve_repo_path

    live_path = resolve_repo_path(repo_id)
    if live_path is None:
        raise RepoNotResolvable(
            f"{repo_id!r} is not a registered repo, or its root var/path doesn't resolve on this host"
        )
    path = live_path
    if branch:
        try:
            created = worktree_ops.create_or_reuse_worktree(repo_id, branch, base_ref="HEAD")
        except RuntimeError as exc:
            raise WorktreeVerificationError(
                f"refusing to park {repo_id!r} on branch {branch!r}: {exc}"
            ) from exc
        verification = worktree_ops.verify_worktree(repo_id, created["path"], branch)
        if not verification["ok"]:
            raise WorktreeVerificationError(
                f"refusing to park {repo_id!r} on branch {branch!r}: {verification['reason']}"
            )
        path = verification["path"]
    clean, reason = git_is_clean(path)
    if not clean:
        raise RepoNotClean(f"refusing to park {repo_id!r}: {reason} (fail-closed — commit/stash first)")
    return park_repo(repo_id, host_id, path, branch=branch, session_id=session_id)


def park_repo(
    repo_id: str,
    host_id: str,
    worktree_path: str,
    branch: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    """Acquire a ParkLease, auto-reclaiming a stale (crashed-holder) active
    lease first. A live active lease raises ParkConflict (the DB's own
    partial-unique-index enforces this; IntegrityError is translated so
    callers don't need to know the storage detail)."""
    from core.database import ParkLease, get_db_session, park_lease_is_stale, utcnow_naive
    from sqlalchemy.exc import IntegrityError

    reclaimed_stale = None
    with get_db_session() as db:
        existing = db.query(ParkLease).filter(
            ParkLease.repo_id == repo_id, ParkLease.status == "active",
        ).first()
        if existing is not None and park_lease_is_stale(existing):
            reclaimed_stale = {
                "lease_id": existing.id, "host_id": existing.host_id,
                "heartbeat_at": existing.heartbeat_at.isoformat(),
            }
            existing.status = "released"
            existing.released_at = utcnow_naive()

    lease_id = str(uuid.uuid4())
    try:
        with get_db_session() as db:
            db.add(ParkLease(
                id=lease_id, repo_id=repo_id, host_id=host_id,
                worktree_path=worktree_path, branch=branch, session_id=session_id,
                allowed_write_scope="repo", status="active",
            ))
    except IntegrityError as e:
        raise ParkConflict(
            f"{repo_id!r} is already parked (active lease exists) — release it first"
        ) from e

    return {
        "lease_id": lease_id, "repo_id": repo_id, "host_id": host_id,
        "worktree_path": worktree_path, "branch": branch, "session_id": session_id,
        "reclaimed_stale_lease": reclaimed_stale,
    }


def heartbeat_repo(repo_id: str, host_id: Optional[str] = None) -> dict:
    """Renew heartbeat_at on the caller's active lease. Raises NoActiveLease
    rather than acquiring one — heartbeat never creates a lease."""
    from core.database import ParkLease, get_db_session, utcnow_naive

    with get_db_session() as db:
        q = db.query(ParkLease).filter(ParkLease.repo_id == repo_id, ParkLease.status == "active")
        if host_id:
            q = q.filter(ParkLease.host_id == host_id)
        lease = q.first()
        if lease is None:
            raise NoActiveLease(
                f"no active lease for {repo_id!r}" + (f" on {host_id!r}" if host_id else "")
                + " — heartbeat only renews an existing lease, it does not acquire one"
            )
        lease.heartbeat_at = utcnow_naive()
        return {
            "lease_id": lease.id, "repo_id": lease.repo_id, "host_id": lease.host_id,
            "heartbeat_at": lease.heartbeat_at.isoformat(),
        }


def active_leases_summary() -> list:
    """Estate-wide active-lease view (Workstream K's `agent status` field,
    Workstream H/B's "HTTP-facing park/status surface for the mobile UI" —
    same read shared rather than re-queried per caller). Best-effort: a
    missing/unreachable DB degrades to an empty list rather than raising,
    since lease visibility is one field among many for any caller of this,
    not the caller's reason to exist."""
    try:
        from core.database import ParkLease, get_db_session, park_lease_is_stale
        with get_db_session() as db:
            active = db.query(ParkLease).filter(ParkLease.status == "active").all()
            return [
                {
                    "repo_id": row.repo_id, "host_id": row.host_id,
                    "heartbeat_at": row.heartbeat_at.isoformat() if row.heartbeat_at else None,
                    "stale": park_lease_is_stale(row),
                }
                for row in active
            ]
    except Exception:
        return []


def active_lease_for_repo(repo_id: str, host_id: str) -> Optional[dict]:
    """Return the existing live write lease held by `host_id`, if any.

    This is the read-side authority used by execution paths that need to
    prove write access without acquiring it. Stale leases fail closed and
    remain reclaimable only through the existing explicit park workflow.
    """
    try:
        from core.database import ParkLease, get_db_session, park_lease_is_stale
        with get_db_session() as db:
            row = db.query(ParkLease).filter(
                ParkLease.repo_id == repo_id,
                ParkLease.host_id == host_id,
                ParkLease.status == "active",
            ).first()
            if row is None or park_lease_is_stale(row):
                return None
            return {
                "lease_id": row.id,
                "repo_id": row.repo_id,
                "host_id": row.host_id,
                "worktree_path": row.worktree_path,
                "branch": row.branch,
                "allowed_write_scope": row.allowed_write_scope,
                "heartbeat_at": row.heartbeat_at.isoformat() if row.heartbeat_at else None,
            }
    except Exception:
        return None


def release_repo(repo_id: str, host_id: Optional[str] = None) -> dict:
    """Release the caller's active lease. Raises NoActiveLease if none matches."""
    from core.database import ParkLease, get_db_session, utcnow_naive

    with get_db_session() as db:
        q = db.query(ParkLease).filter(ParkLease.repo_id == repo_id, ParkLease.status == "active")
        if host_id:
            q = q.filter(ParkLease.host_id == host_id)
        lease = q.first()
        if lease is None:
            raise NoActiveLease(f"no active lease for {repo_id!r}" + (f" on {host_id!r}" if host_id else ""))
        lease.status = "released"
        lease.released_at = utcnow_naive()
        return {"lease_id": lease.id, "repo_id": lease.repo_id, "host_id": lease.host_id}

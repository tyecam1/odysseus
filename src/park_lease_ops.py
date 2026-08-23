"""Shared ParkLease mutation logic (Workstream B: "a park/release/heartbeat
HTTP surface so the client can cover those scripts/agent subcommands too").

`scripts/agent`'s `park`/`heartbeat`/`release` CLI subcommands and
`routes/estate_routing_routes.py`'s HTTP surface both call this rather than
each re-deriving lease semantics (stale-lease reclaim, live-lease
fail-closed, heartbeat renewal) — a second copy would be exactly the kind
of duplicate authority docs/aoteru-model-host-routing-contract.md already
forbids for routing decisions, and lease mutation deserves the same
discipline.

Deliberately does not resolve repo paths, check git cleanliness, or infer
the caller's host — those are call-site concerns (the CLI reads the local
filesystem/config; the HTTP route runs inside the server process on
whichever host it's deployed to) and stay in each caller, not here.
"""
from __future__ import annotations

import uuid
from typing import Optional


class ParkConflict(Exception):
    """An active, non-stale lease already exists for this repo — fail closed."""


class NoActiveLease(Exception):
    """heartbeat/release found no matching active lease to act on."""


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

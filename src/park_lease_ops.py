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

    def __init__(self, message: str, *, lease_id=None, status=None, host_id=None, prepare_probe_due=False):
        super().__init__(message)
        self.lease_id = lease_id
        self.status = status
        self.host_id = host_id
        self.prepare_probe_due = prepare_probe_due


class PrepareOutcomeUnresolved(Exception):
    """S6.9: the worker's prepare outcome is not positively known (lost
    response, unreachable, protocol/placement error, still preparing). The
    `preparing` reservation stays protected until
    `resolve_preparing_reservation` proves the prepare cannot still run."""

    def __init__(self, message: str, *, lease_id: str, host_id: str):
        super().__init__(message)
        self.lease_id = lease_id
        self.host_id = host_id
        self.next_action = {
            "http": "POST /api/estate/park/<repo_id>/resolve-prepare",
            "cli": f"aoteru resolve-prepare <repo_id> --lease {lease_id} --host {host_id}",
        }


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


class LeaseHasUnresolvedExecution(Exception):
    """Ordinary release refused: an execution under this lease still has
    `worktree_resolution = 'unresolved'` (S6.2). Carries the blocking
    execution and the supported next action; there is no force flag."""

    def __init__(self, message: str, *, lease_id: str, execution_id: str,
                 lifecycle_state: str, next_action: str):
        super().__init__(message)
        self.lease_id = lease_id
        self.execution_id = execution_id
        self.lifecycle_state = lifecycle_state
        self.next_action = next_action


# How an unresolved execution's lease is unblocked, by lifecycle_state
# (S6.1 admission table). Shared by release refusals and admission.
UNRESOLVED_NEXT_ACTION = {
    "accepted": "wait",
    "running": "wait",
    "lost": "reconcile",       # a successful worker status corrects it first
    "succeeded": "finalize_or_recover",
    "failed": "recover",
    "timed_out": "recover",
    "interrupted": "recover",
}

# S6.9: age alone never reclaims a `preparing` reservation; past this it
# is merely old enough for `resolve_preparing_reservation` to probe.
PARK_PREPARE_STALE_SECONDS = 300


def _unresolved_execution(db, lease_id: str):
    from core.database import EstateExecution
    return db.query(EstateExecution).filter(
        EstateExecution.lease_id == lease_id,
        EstateExecution.worktree_resolution == "unresolved",
    ).order_by(EstateExecution.submitted_at.desc()).first()


def lease_authority_state(db, lease, *, now=None) -> dict:
    """S6.4: the single canonical authority/reclaimability rule. Heartbeat
    age (`park_lease_is_stale`) is telemetry only; a lease protected by
    any unresolved execution is never reclaimable, whatever its age."""
    from core.database import park_lease_is_stale, utcnow_naive
    now = now or utcnow_naive()
    heartbeat_stale = park_lease_is_stale(lease, now=now)
    state = {
        "lease_id": lease.id, "status": lease.status, "heartbeat_stale": heartbeat_stale,
        "protected_by_execution_id": None, "authoritative": False, "reclaimable": False,
        "reason": "",
    }
    if lease.status == "released":
        state["reason"] = "released"
        return state
    if lease.status == "preparing":
        # S6.9: a reservation, never write authority, never reclaimable by
        # age -- only worker-side proof (resolve_preparing_reservation).
        state["prepare_probe_due"] = (now - lease.heartbeat_at).total_seconds() > PARK_PREPARE_STALE_SECONDS
        state["reason"] = "preparing reservation (not write authority)"
        return state
    blocker = _unresolved_execution(db, lease.id)
    state["protected_by_execution_id"] = blocker.id if blocker is not None else None
    state["reclaimable"] = heartbeat_stale and blocker is None
    state["authoritative"] = not state["reclaimable"]
    state["reason"] = (
        "stale and unprotected" if state["reclaimable"]
        else f"protected by unresolved execution {blocker.id}" if blocker is not None
        else "live"
    )
    return state


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
        # S6.7/S6.9: reserve first, then prepare through the worker
        # (LocalTransport for this host) under that reservation -- no
        # worktree is created or reused before a `preparing` row exists.
        return park_with_worktree(repo_id, host_id, branch, session_id=session_id)
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
    *,
    status: str = "active",
) -> dict:
    """Acquire a ParkLease (or, with `status="preparing"`, an S6.7
    reservation). Stale reclaim and insert are ONE S6.5 serialized
    transaction, and reclaim happens only when `lease_authority_state`
    says `reclaimable` -- never from heartbeat age alone. A live or
    protected lease, or any `preparing` reservation, raises ParkConflict;
    the partial unique index is the backstop."""
    from core.database import ParkLease, lease_serialized_transaction, utcnow_naive
    from sqlalchemy.exc import IntegrityError

    reclaimed_stale = None
    lease_id = str(uuid.uuid4())
    try:
        with lease_serialized_transaction(repo_id=repo_id) as db:
            existing = db.query(ParkLease).filter(
                ParkLease.repo_id == repo_id, ParkLease.status.in_(("active", "preparing")),
            ).first()
            if existing is not None:
                authority = lease_authority_state(db, existing)
                if not authority["reclaimable"]:
                    raise ParkConflict(
                        f"{repo_id!r} is already parked ({existing.status} lease {existing.id} on "
                        f"{existing.host_id!r}: {authority['reason']}) — release or recover it first",
                        lease_id=existing.id, status=existing.status, host_id=existing.host_id,
                        prepare_probe_due=bool(authority.get("prepare_probe_due")),
                    )
                reclaimed_stale = {
                    "lease_id": existing.id, "host_id": existing.host_id,
                    "heartbeat_at": existing.heartbeat_at.isoformat(),
                }
                existing.status = "released"
                existing.released_at = utcnow_naive()
                db.flush()
            db.add(ParkLease(
                id=lease_id, repo_id=repo_id, host_id=host_id,
                worktree_path=worktree_path, branch=branch, session_id=session_id,
                allowed_write_scope="repo", status=status,
            ))
            db.flush()
    except IntegrityError as e:
        raise ParkConflict(
            f"{repo_id!r} is already parked (active lease exists) — release it first"
        ) from e

    return {
        "lease_id": lease_id, "repo_id": repo_id, "host_id": host_id,
        "worktree_path": worktree_path, "branch": branch, "session_id": session_id,
        "status": status, "reclaimed_stale_lease": reclaimed_stale,
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
            preparing = db.query(ParkLease).filter(
                ParkLease.repo_id == repo_id, ParkLease.status == "preparing",
            ).first()
            if preparing is not None:
                raise NoActiveLease(
                    f"{repo_id!r} has only a preparing reservation ({preparing.id}) — "
                    "heartbeat renews write authority, which a reservation is not (S6.3)"
                )
            raise NoActiveLease(
                f"no active lease for {repo_id!r}" + (f" on {host_id!r}" if host_id else "")
                + " — heartbeat only renews an existing lease, it does not acquire one"
            )
        lease.heartbeat_at = utcnow_naive()
        return {
            "lease_id": lease.id, "repo_id": lease.repo_id, "host_id": lease.host_id,
            "heartbeat_at": lease.heartbeat_at.isoformat(),
        }


def renew_lease_for_execution(execution_id: str) -> bool:
    """S6.3: control-plane-only supervision renewal of the EXACT lease an
    execution was admitted under. One conditional UPDATE keyed on the
    recorded lease id/repo/host; never a repo/host lookup, so it can never
    renew a later or reassigned lease. Not exposed on HTTP/CLI/worker."""
    import logging
    from core.database import EstateExecution, ParkLease, get_db_session, utcnow_naive
    with get_db_session() as db:
        row = db.query(EstateExecution).filter(EstateExecution.id == execution_id).one_or_none()
        if (row is None or row.lease_id is None
                or row.lifecycle_state not in ("accepted", "running")
                or row.worktree_resolution != "unresolved"):
            return False
        lease_id = row.lease_id
        updated = db.query(ParkLease).filter(
            ParkLease.id == row.lease_id,
            ParkLease.status == "active",
            ParkLease.repo_id == row.repo_id,
            ParkLease.host_id == row.host_id,
        ).update({ParkLease.heartbeat_at: utcnow_naive()}, synchronize_session=False)
    if updated == 0:
        logging.getLogger(__name__).info(
            "renew_lease_for_execution(%s): exact lease %s no longer active; not renewed",
            execution_id, lease_id,
        )
    return updated == 1


def unpushed_executions(db, lease_id: str) -> list:
    """S6.10: finalized/recovered executions under a lease whose recorded
    commit is not pushed -- surfaced, never blocking."""
    import json
    from core.database import EstateExecution
    out = []
    rows = db.query(EstateExecution).filter(
        EstateExecution.lease_id == lease_id,
        EstateExecution.worktree_resolution.in_(("finalized", "recovered")),
    ).all()
    for row in rows:
        try:
            push = (json.loads(row.finalization_json or "{}") or {}).get("push") or {}
        except (TypeError, ValueError):
            push = {}
        if push.get("state") in ("failed", "not_attempted"):
            out.append({"execution_id": row.id, "commit_sha": push.get("commit_sha")})
    return out


def active_leases_summary() -> list:
    """Estate-wide active-lease view (Workstream K's `agent status` field,
    Workstream H/B's "HTTP-facing park/status surface for the mobile UI" —
    same read shared rather than re-queried per caller). Best-effort: a
    missing/unreachable DB degrades to an empty list rather than raising,
    since lease visibility is one field among many for any caller of this,
    not the caller's reason to exist. `stale` is heartbeat-age telemetry;
    `reclaimable`/`protected_by` are the authority facts (S6.4)."""
    try:
        from core.database import ParkLease, get_db_session
        with get_db_session() as db:
            rows = db.query(ParkLease).filter(ParkLease.status.in_(("active", "preparing"))).all()
            out = []
            for row in rows:
                authority = lease_authority_state(db, row)
                out.append({
                    "lease_id": row.id, "repo_id": row.repo_id, "host_id": row.host_id,
                    "status": row.status,
                    "heartbeat_at": row.heartbeat_at.isoformat() if row.heartbeat_at else None,
                    "stale": authority["heartbeat_stale"],
                    "reclaimable": authority["reclaimable"],
                    "protected_by": authority["protected_by_execution_id"],
                    "unpushed_executions": len(unpushed_executions(db, row.id)),
                })
            return out
    except Exception:
        return []


def active_lease_for_repo(repo_id: str, host_id: str) -> Optional[dict]:
    """Return the write lease held by `host_id` iff it is `active` and
    `authoritative` under `lease_authority_state` (S6.4). A stale-but-
    protected lease IS returned (with `heartbeat_stale`/`protected_by_
    execution_id`), because an unresolved execution still depends on it;
    a stale unprotected lease is None and fails closed as before."""
    try:
        from core.database import ParkLease, get_db_session
        with get_db_session() as db:
            row = db.query(ParkLease).filter(
                ParkLease.repo_id == repo_id,
                ParkLease.host_id == host_id,
                ParkLease.status == "active",
            ).first()
            if row is None:
                return None
            authority = lease_authority_state(db, row)
            if not authority["authoritative"]:
                return None
            return {
                "lease_id": row.id,
                "repo_id": row.repo_id,
                "host_id": row.host_id,
                "worktree_path": row.worktree_path,
                "branch": row.branch,
                "allowed_write_scope": row.allowed_write_scope,
                "heartbeat_at": row.heartbeat_at.isoformat() if row.heartbeat_at else None,
                "heartbeat_stale": authority["heartbeat_stale"],
                "protected_by_execution_id": authority["protected_by_execution_id"],
            }
    except Exception:
        return None


def release_repo(repo_id: str, host_id: Optional[str] = None) -> dict:
    """Release the caller's active lease (S6.2 ordinary release). Inside
    one S6.5 serialized transaction, refused with
    LeaseHasUnresolvedExecution while any execution under the lease is
    `unresolved` -- no force flag; the only other exit is recovery
    release. Raises NoActiveLease if none matches."""
    from core.database import ParkLease, lease_serialized_transaction, utcnow_naive

    with lease_serialized_transaction(repo_id=repo_id) as db:
        q = db.query(ParkLease).filter(ParkLease.repo_id == repo_id, ParkLease.status == "active")
        if host_id:
            q = q.filter(ParkLease.host_id == host_id)
        lease = q.first()
        if lease is None:
            raise NoActiveLease(f"no active lease for {repo_id!r}" + (f" on {host_id!r}" if host_id else ""))
        blocker = _unresolved_execution(db, lease.id)
        if blocker is not None:
            next_action = UNRESOLVED_NEXT_ACTION.get(blocker.lifecycle_state, "recover")
            raise LeaseHasUnresolvedExecution(
                f"lease {lease.id} has unresolved execution {blocker.id} "
                f"({blocker.lifecycle_state}); next action: {next_action}",
                lease_id=lease.id, execution_id=blocker.id,
                lifecycle_state=blocker.lifecycle_state, next_action=next_action,
            )
        unpushed = unpushed_executions(db, lease.id)
        lease.status = "released"
        lease.released_at = utcnow_naive()
        return {"lease_id": lease.id, "repo_id": lease.repo_id, "host_id": lease.host_id,
                "unpushed_executions": unpushed}


# ---------------------------------------------------------------------
# S6.7 / S6.9: parks that create or reuse a worktree
# ---------------------------------------------------------------------

_PREPARE_CLIENT_SIDE = frozenset({"worker_unreachable", "worker_protocol_error", "placement_mismatch"})


def _release_reservation(lease_id: str) -> bool:
    """Release a `preparing` reservation by exact id (always safe: no
    execution can exist under a non-active lease)."""
    from core.database import ParkLease, lease_serialized_transaction, utcnow_naive
    with lease_serialized_transaction(lease_id=lease_id) as db:
        row = db.query(ParkLease).filter(ParkLease.id == lease_id).one_or_none()
        if row is None or row.status != "preparing":
            return False
        row.status = "released"
        row.released_at = utcnow_naive()
        return True


def _call_prepare_worker(host_id: str, verb: str, payload: dict, deadline_s: float):
    from src import estate_worker_client as client
    try:
        return client.call_worker(host_id, verb, payload, deadline_s=deadline_s).get("result") or {}, None
    except client.WorkerTransportError as exc:
        return None, exc


def park_with_worktree(repo_id: str, host_id: str, branch: str, *, session_id: Optional[str] = None,
                       base_ref: str = "HEAD") -> dict:
    """S6.7: reserve -> prepare (worker, under the reservation) -> evidence
    -> bind. Positively known failures release the reservation; ambiguous
    outcomes keep it `preparing` (S6.9) and raise PrepareOutcomeUnresolved.
    A competing stale `preparing` reservation is probed (outside any lock)
    and the reservation retried once."""
    from core.database import ParkLease, lease_serialized_transaction, utcnow_naive
    try:
        reservation = park_repo(repo_id, host_id, "", branch=branch, session_id=session_id, status="preparing")
    except ParkConflict as conflict:
        if conflict.status != "preparing" or not conflict.prepare_probe_due:
            raise
        resolve_preparing_reservation(conflict.lease_id)
        reservation = park_repo(repo_id, host_id, "", branch=branch, session_id=session_id, status="preparing")
    lease_id = reservation["lease_id"]
    result, exc = _call_prepare_worker(host_id, "worktree.prepare", {
        "repo_id": repo_id, "branch": branch, "base_ref": base_ref,
        "lease": {"lease_id": lease_id, "host_id": host_id},
    }, deadline_s=120)
    if exc is not None:
        if exc.code in _PREPARE_CLIENT_SIDE:
            raise PrepareOutcomeUnresolved(
                f"prepare outcome for {repo_id!r} on {host_id!r} is unresolved ({exc.code}: {exc})",
                lease_id=lease_id, host_id=host_id,
            ) from exc
        _release_reservation(lease_id)            # worker pre-claim refusal: positively nothing mutated
        raise WorktreeVerificationError(f"refusing to park {repo_id!r} on {branch!r}: {exc.code}: {exc}") from exc
    state = result.get("state")
    if state not in ("prepared", "prepare_failed", "fenced", "prepare_interrupted") \
            or result.get("quiescent") is not True:
        # `preparing`, or any unrecognised/unproven state: ambiguous (6d
        # adjudication finding 6) -- the reservation stays protected.
        raise PrepareOutcomeUnresolved(
            f"prepare for {repo_id!r} on {host_id!r} is {state!r}, not a proven terminal outcome",
            lease_id=lease_id, host_id=host_id,
        )
    if state != "prepared":
        _release_reservation(lease_id)            # prepare_failed / fenced / interrupted: positively ended
        raise WorktreeVerificationError(
            f"refusing to park {repo_id!r} on {branch!r}: prepare {state}: {result.get('error')}"
        )
    if result.get("branch") != branch or not result.get("path") or not result.get("head_sha"):
        _release_reservation(lease_id)
        raise WorktreeVerificationError(f"refusing to park {repo_id!r}: prepare evidence incomplete or mismatched")
    if result.get("clean") is not True:
        _release_reservation(lease_id)
        raise RepoNotClean(f"refusing to park {repo_id!r}: prepared worktree is not clean (fail-closed)")
    with lease_serialized_transaction(lease_id=lease_id) as db:
        row = db.query(ParkLease).filter(ParkLease.id == lease_id).one_or_none()
        if row is None or row.status != "preparing" or row.host_id != host_id or row.branch != branch:
            raise WorktreeVerificationError(f"reservation {lease_id} changed before bind; not bound")
        row.worktree_path = result["path"]
        row.status = "active"
        row.heartbeat_at = utcnow_naive()
    return {**reservation, "status": "active", "worktree_path": result["path"], "head_sha": result["head_sha"]}


def resolve_preparing_reservation(lease_id: str) -> dict:
    """S6.9: resolve an ambiguous `preparing` reservation by the same
    lease_id. Probe with fence (no lock held); release only when the
    worker proves the original prepare cannot still run. Never binds."""
    from core.database import ParkLease, get_db_session
    with get_db_session() as db:
        row = db.query(ParkLease).filter(ParkLease.id == lease_id).one_or_none()
        if row is None or row.status != "preparing":
            return {"resolved": False, "reason": "no preparing reservation with that id"}
        host_id = row.host_id
    result, exc = _call_prepare_worker(host_id, "worktree.prepare_status",
                                       {"lease_id": lease_id, "fence": True}, deadline_s=30)
    if exc is not None:
        return {"resolved": False, "reason": "worker_unreachable", "detail": str(exc)}
    state = result.get("state")
    if state in ("fenced", "prepare_failed", "prepare_interrupted", "prepared") and result.get("quiescent") is True:
        released = _release_reservation(lease_id)
        return {"resolved": released, "state": state, "released": released}
    return {"resolved": False, "reason": "prepare_still_running", "state": state}

"""Stage 6 control-plane write lane (docs/aoteru-multihost-execution-
implementation-plan.md §6.0, Stage 6 "Files" for src/estate_router.py).

EstateExecution is the only lifecycle store and ParkLease the only write
authority; this module never adds a second queue, lease or lock. Every
authority change happens inside `core.database.lease_serialized_transaction`
and every worker call happens OUTSIDE it (S6.5). The worker is reached only
through `estate_worker_client.call_worker`, never in-process, and never on
a host other than the row's own `host_id` -- there is no fallback.

Public names are re-exported from `src.estate_router` (where the plan
places them) so callers and tests keep one import surface.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import timedelta
from typing import Any, Optional

from src import estate_router as _router
from src import park_lease_ops

log = logging.getLogger(__name__)

PLACEHOLDER = {"dispatch_state": "pending_start"}
LOST_GRACE_SECONDS = 120            # execution_deadline_at + this, unobserved -> lost
MONITOR_INTERVAL_SECONDS = 5.0
OBSERVATION_STALE_SECONDS = 15      # reconcile re-observes rows older than this
_CLIENT_SIDE_CODES = frozenset({"worker_unreachable", "worker_protocol_error", "placement_mismatch"})
_SETTLED_FOR_RECOVERY = ("succeeded", "failed", "timed_out", "interrupted")
_TERMINAL = ("succeeded", "failed", "timed_out")
NEXT_ACTION_WAIT = "wait"

# Test hook (U29): called inside the admission transaction right after the
# in-transaction authority validation, before the row insert.
_ADMISSION_TEST_HOOK = None


def _next_action_observe(execution_id: str) -> dict:
    return {"http": f"GET /api/estate/run/{execution_id}?wait=60",
            "cli": f"aoteru execution {execution_id} --wait 60"}


def _next_action_push(execution_id: str) -> dict:
    return {"http": f"POST /api/estate/run/{execution_id}/push", "cli": f"aoteru push {execution_id}"}


# ---------------------------------------------------------------------
# Worker calls (never inside a serialized transaction)
# ---------------------------------------------------------------------

def _worker(host_id: str, verb: str, payload: dict, *, deadline_s: float):
    """Returns (result, None) or (None, WorkerTransportError)."""
    from src import estate_worker_client as client
    try:
        response = client.call_worker(host_id, verb, payload, deadline_s=deadline_s)
    except client.WorkerTransportError as exc:
        return None, exc
    return response.get("result") or {}, None


def _is_ambiguous(exc) -> bool:
    return exc is not None and getattr(exc, "code", None) in _CLIENT_SIDE_CODES


# ---------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------

def _now():
    from core.database import utcnow_naive
    return utcnow_naive()


def _load_row(execution_id: str):
    from core.database import EstateExecution, get_db_session
    with get_db_session() as db:
        row = db.query(EstateExecution).filter(EstateExecution.id == execution_id).one_or_none()
        if row is None:
            return None
        db.expunge(row)
        return row


def _handle_of(row) -> Optional[dict]:
    try:
        value = json.loads(row.worker_handle_json) if row.worker_handle_json else None
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _is_placeholder(row) -> bool:
    return (_handle_of(row) or {}).get("dispatch_state") == "pending_start"


def _transition(execution_id: str, from_states: tuple, **fields) -> bool:
    """Conditional lifecycle write: only from an expected state, and only
    while the worktree is unresolved -- so racing observers (monitor,
    reconcile, wait) never regress or double-apply an outcome. Outcome
    writes never touch worktree_resolution."""
    from core.database import EstateExecution, get_db_session
    assert "worktree_resolution" not in fields
    with get_db_session() as db:
        updated = db.query(EstateExecution).filter(
            EstateExecution.id == execution_id,
            EstateExecution.lifecycle_state.in_(from_states),
            EstateExecution.worktree_resolution == "unresolved",
        ).update(fields, synchronize_session=False)
    return updated == 1


def _merge_finalization(existing: Optional[str], **parts) -> str:
    try:
        value = json.loads(existing) if existing else {}
    except (TypeError, ValueError):
        value = {}
    if not isinstance(value, dict):
        value = {}
    value.update(parts)
    return json.dumps(value, sort_keys=True)


def _record_outcome(row, state: str, host_id: str, result: Optional[dict] = None) -> None:
    if not row.decision_id:
        return
    ok = state == "succeeded" and bool((result or {}).get("ok"))
    gate = "pass" if ok and ((result or {}).get("output") or "").strip() else "fail"
    _router._update_decision_outcome(
        row.decision_id, status="complete" if gate == "pass" else "failed",
        deterministic_gate=gate, latency_ms=(result or {}).get("latency_ms"),
        escalation_reason="insufficient_capability" if gate == "pass" else "worker_failed",
        executor="codex-write", escalated=True, actual_route="codex-write",
        verification_outcome=gate, executed_host_id=host_id,
    )


# ---------------------------------------------------------------------
# Authority
# ---------------------------------------------------------------------

def _lease_authority(repo_id: str, host_id: str) -> dict:
    """DB-only half of the old `_codex_write_authority`: an `active`,
    `authoritative` (S6.4) lease held by `host_id` with repo write scope,
    a branch and a bound worktree_path. A preliminary check only -- the
    authority moment is re-validated inside the admission transaction."""
    lease = park_lease_ops.active_lease_for_repo(repo_id, host_id)
    if lease is None:
        return {"ok": False, "code": "write_lease_missing",
                "error": f"implementation mode requires an authoritative active lease for {repo_id!r} held by {host_id!r}"}
    if lease.get("allowed_write_scope") != "repo":
        return {"ok": False, "code": "write_lease_missing", "error": f"lease for {repo_id!r} does not grant repo write scope"}
    if not lease.get("branch") or not lease.get("worktree_path"):
        return {"ok": False, "code": "write_lease_missing",
                "error": f"lease for {repo_id!r} lacks an enforced branch or bound worktree"}
    return {"ok": True, **lease}


class _Refusal(Exception):
    def __init__(self, code: str, message: str, **extra):
        super().__init__(message)
        self.code = code
        self.extra = extra


_UNRESOLVED_REFUSALS = {
    "lost": "lease_has_unresolved_lost_execution",
    "succeeded": "lease_has_unfinalized_execution",
    "failed": "lease_has_unresolved_worktree",
    "timed_out": "lease_has_unresolved_worktree",
    "interrupted": "lease_has_unresolved_worktree",
}


def _admission_outcome(blocker) -> dict:
    if blocker.lifecycle_state in ("accepted", "running"):
        return {"dispatch": "reused_in_flight", "execution_id": blocker.id,
                "lifecycle_state": blocker.lifecycle_state}
    code = _UNRESOLVED_REFUSALS.get(blocker.lifecycle_state, "lease_has_unresolved_worktree")
    raise _Refusal(code, f"lease has unresolved execution {blocker.id} ({blocker.lifecycle_state})",
                   execution_id=blocker.id, lifecycle_state=blocker.lifecycle_state,
                   next_action=park_lease_ops.UNRESOLVED_NEXT_ACTION.get(blocker.lifecycle_state, "recover"))


# ---------------------------------------------------------------------
# Admission + dispatch (plan Stage 6 steps 1-9)
# ---------------------------------------------------------------------

def execute_write_via_worker(objective: str, *, repo_id: str, host_id: str,
                             decision_id: Optional[str] = None,
                             wait_timeout: float = 30.0, timeout: float = 1800.0) -> dict:
    from sqlalchemy.exc import IntegrityError
    from core.database import EstateExecution, ParkLease, lease_serialized_transaction

    authority = _lease_authority(repo_id, host_id)                                   # step 1
    if not authority["ok"]:
        return {"ok": False, "provider": "codex-write", "authority_denied": True,
                "error": authority["error"], "error_code": authority["code"]}
    lease_id, branch, worktree_path = authority["lease_id"], authority["branch"], authority["worktree_path"]

    verify, exc = _worker(host_id, "worktree.verify",                                  # step 2
                          {"repo_id": repo_id, "worktree_path": worktree_path, "branch": branch}, deadline_s=30)
    if exc is not None or not verify.get("ok"):
        return {"ok": False, "provider": "codex-write", "authority_denied": True, "error_code": "authority_denied",
                "error": f"worktree verification failed on {host_id!r}: "
                         f"{getattr(exc, 'code', '') or ''} {exc or verify.get('reason')}".strip()}
    if verify.get("clean") is not True:
        return {"ok": False, "provider": "codex-write", "authority_denied": True, "error_code": "worktree_not_clean",
                "error": f"leased worktree {worktree_path!r} on {host_id!r} is not clean"}
    admission_head = verify.get("head_sha")

    execution_id = str(uuid.uuid4())
    try:
        with lease_serialized_transaction(lease_id=lease_id) as db:                     # step 3
            lease = db.query(ParkLease).filter(ParkLease.id == lease_id).one_or_none()
            if lease is None or lease.status != "active":
                raise _Refusal("write_lease_missing", f"lease {lease_id} is no longer active")
            state = park_lease_ops.lease_authority_state(db, lease)
            if not state["authoritative"] or lease.host_id != host_id \
                    or lease.allowed_write_scope != "repo" \
                    or lease.worktree_path != worktree_path or lease.branch != branch:
                raise _Refusal("write_lease_missing",
                               f"lease {lease_id} changed or lost authority before admission")
            if _ADMISSION_TEST_HOOK is not None:
                _ADMISSION_TEST_HOOK()
            blocker = park_lease_ops._unresolved_execution(db, lease_id)                  # step 4
            if blocker is not None:
                reuse = _admission_outcome(blocker)
                return {"ok": True, "provider": "codex-write", **reuse,
                        "next_action": _next_action_observe(reuse["execution_id"])}
            now = _now()
            db.add(EstateExecution(                                                        # step 5
                id=execution_id, decision_id=decision_id, objective=objective,
                executor="codex-write", provider="codex", host_id=host_id, repo_id=repo_id,
                lease_id=lease_id, worktree_path=worktree_path, branch=branch,
                lifecycle_state="accepted", worktree_resolution="unresolved",
                worker_handle_json=json.dumps(PLACEHOLDER),
                execution_deadline_at=now + timedelta(seconds=timeout),
                admission_head_sha=admission_head, submitted_at=now,
            ))
            db.flush()
    except _Refusal as refusal:
        return {"ok": False, "provider": "codex-write", "authority_denied": refusal.code == "write_lease_missing",
                "error_code": refusal.code, "error": str(refusal), **refusal.extra}
    except IntegrityError:
        # The unresolved-row index caught a truly concurrent admission.
        with lease_serialized_transaction(lease_id=lease_id) as db:
            blocker = park_lease_ops._unresolved_execution(db, lease_id)
            if blocker is None:
                return {"ok": False, "provider": "codex-write", "error_code": "admission_conflict",
                        "error": f"admission conflict on lease {lease_id} could not be resolved"}
            try:
                reuse = _admission_outcome(blocker)
            except _Refusal as refusal:
                return {"ok": False, "provider": "codex-write", "error_code": refusal.code,
                        "error": str(refusal), **refusal.extra}
        return {"ok": True, "provider": "codex-write", **reuse,
                "next_action": _next_action_observe(reuse["execution_id"])}

    _dispatch_start(execution_id)                                                          # steps 6-7
    thread = threading.Thread(target=_observe_worker_execution, args=(execution_id,),       # step 8
                              name=f"estate-observe-{execution_id}", daemon=True)
    thread.start()
    thread.join(wait_timeout)                                                              # step 9
    row = _load_row(execution_id)
    response = {"ok": True, "provider": "codex-write", "execution_id": execution_id, "dispatch": "new",
                "lifecycle_state": row.lifecycle_state if row else "accepted",
                "next_action": _next_action_observe(execution_id)}
    if row is not None and row.lifecycle_state in _TERMINAL:
        response["result"] = json.loads(row.result_json) if row.result_json else None
    return response


def _start_payload(row) -> dict:
    return {
        "execution_id": row.id, "kind": "codex-write", "objective": row.objective,
        "repo_id": row.repo_id,
        "timeout_s": max(1.0, (row.execution_deadline_at - row.submitted_at).total_seconds())
        if row.execution_deadline_at and row.submitted_at else 1800.0,
        "lease": {"lease_id": row.lease_id, "worktree_path": row.worktree_path, "branch": row.branch,
                  "expected_head_sha": row.admission_head_sha},
    }


def _dispatch_start(execution_id: str) -> None:
    """Step 6 state machine. A lost/failed `start` is never evidence for
    `failed`; a worker pre-claim refusal is proof of not_started ONLY for
    the first and only start (round-0 finding 3) -- after any ambiguity the
    control plane resolves through `status {fence: true}`."""
    row = _load_row(execution_id)
    if row is None:
        return
    ambiguous = False
    for _attempt in range(2):
        result, exc = _worker(row.host_id, "start", _start_payload(row), deadline_s=60)
        if exc is None:
            _apply_view(execution_id, {**result, "state": result.get("state")}, start_answer=True)
            return
        if _is_ambiguous(exc):
            ambiguous = True
            continue
        if not ambiguous:
            _resolve_not_started(execution_id, f"worker refused start before claim: {exc.code}: {exc}")
            return
        break
    if ambiguous:
        view, exc = _worker(row.host_id, "status", {"execution_id": execution_id, "fence": True}, deadline_s=20)
        if exc is None:
            _apply_view(execution_id, view)
        # else: stays accepted + placeholder; the bounded rule decides later.


def _resolve_not_started(execution_id: str, reason: str) -> None:
    from core.database import EstateExecution, lease_serialized_transaction
    row = _load_row(execution_id)
    if row is None:
        return
    with lease_serialized_transaction(lease_id=row.lease_id) as db:
        current = db.query(EstateExecution).filter(EstateExecution.id == execution_id).one_or_none()
        if current is None or current.worktree_resolution != "unresolved" \
                or current.lifecycle_state not in ("accepted", "lost"):
            return
        current.lifecycle_state = "failed"
        current.worktree_resolution = "not_started"
        current.error = reason
        current.finished_at = _now()
    _record_outcome(row, "failed", row.host_id)
    _release_spool(execution_id, "not_started")


def _apply_view(execution_id: str, view: dict, *, start_answer: bool = False) -> None:
    """Map one worker observation onto the row (steps 6-8). Outcome only;
    never touches worktree_resolution except via _resolve_not_started."""
    row = _load_row(execution_id)
    if row is None or row.worktree_resolution != "unresolved":
        return
    state = view.get("state")
    now = _now()
    if state in ("start_failed", "fenced"):
        _resolve_not_started(execution_id, view.get("error") or f"worker reports {state}: writer never ran")
        return
    if state in ("tombstone",) or view.get("released"):
        _transition(execution_id, ("accepted", "running", "lost"), last_observed_at=now,
                    error="spool_released_before_resolution")
        return
    if state == "unknown":
        if start_answer:
            return
        deadline = row.execution_deadline_at
        if _is_placeholder(row) and (deadline is None or now < deadline):
            _dispatch_start(execution_id)          # same id: safe by the worker's atomic claim
        elif _is_placeholder(row):
            fenced, exc = _worker(row.host_id, "status", {"execution_id": execution_id, "fence": True},
                                  deadline_s=20)
            if exc is None and fenced.get("state") in ("fenced", "start_failed"):
                _resolve_not_started(execution_id, "fenced after the start deadline: writer never ran")
        return
    if state == "starting":
        _transition(execution_id, ("accepted", "lost"), last_observed_at=now, lifecycle_state="accepted")
        return
    handle = view.get("handle")
    if not isinstance(handle, dict):
        return
    confirm = {"worker_handle_json": json.dumps(handle, sort_keys=True), "worker_pid": handle.get("pid"),
               "last_observed_at": now}
    if _is_placeholder(row) or row.lifecycle_state in ("accepted", "lost"):
        _transition(execution_id, ("accepted", "lost", "running"), lifecycle_state="running",
                    started_at=row.started_at or now, **confirm)
    else:
        _transition(execution_id, ("running",), **confirm)
    if state == "running":
        if view.get("quiescent") is False:
            park_lease_ops.renew_lease_for_execution(execution_id)
        return
    if state == "interrupted":
        if _transition(execution_id, ("running",), lifecycle_state="interrupted", finished_at=now,
                       error="worker positively observed the runner tree gone without a terminal record"):
            _record_outcome(row, "interrupted", row.host_id)
        return
    if state in _TERMINAL:
        result = view.get("result") or {}
        if _transition(execution_id, ("running",), lifecycle_state=state, finished_at=now,
                       result_json=json.dumps(result), exit_status="0" if state == "succeeded" else "1",
                       error=None if state == "succeeded" else result.get("error")):
            _record_outcome(row, state, row.host_id, result)


def _mark_lost_if_due(execution_id: str) -> bool:
    row = _load_row(execution_id)
    if row is None or row.lifecycle_state not in ("accepted", "running") or row.worktree_resolution != "unresolved":
        return False
    deadline = row.execution_deadline_at
    if deadline is None:
        return False
    bound = deadline + timedelta(seconds=LOST_GRACE_SECONDS)
    now = _now()
    if now <= bound or (row.last_observed_at is not None and row.last_observed_at > bound):
        return False
    return _transition(execution_id, ("accepted", "running"), lifecycle_state="lost",
                       error="outcome undetermined: worker not observed past execution_deadline_at + "
                             f"{LOST_GRACE_SECONDS}s (not evidence the writer stopped)")


def _observe_worker_execution(execution_id: str) -> None:
    """Step 8 monitor. Polls `status`; never redispatches; stops at any
    non-running observation or `lost`."""
    while True:
        row = _load_row(execution_id)
        if row is None or row.worktree_resolution != "unresolved" \
                or row.lifecycle_state not in ("accepted", "running"):
            return
        view, exc = _worker(row.host_id, "status", {"execution_id": execution_id}, deadline_s=20)
        if exc is None:
            _apply_view(execution_id, view)
        elif _mark_lost_if_due(execution_id):
            return
        time.sleep(MONITOR_INTERVAL_SECONDS)


def _release_spool(execution_id: str, resolution: str) -> None:
    """Best-effort S6.8 acknowledgement after a resolution commit."""
    from core.database import EstateExecution, get_db_session
    row = _load_row(execution_id)
    if row is None or row.worker_handle_json is None:
        return
    result, exc = _worker(row.host_id, "spool.release", {"execution_id": execution_id, "resolution": resolution},
                          deadline_s=60)
    if exc is not None or not result.get("released"):
        log.info("spool.release(%s) not acknowledged yet: %s", execution_id, exc)
        return
    with get_db_session() as db:
        db.query(EstateExecution).filter(EstateExecution.id == execution_id).update(
            {EstateExecution.spool_released_at: _now()}, synchronize_session=False)


# ---------------------------------------------------------------------
# Reconciliation / observation surface
# ---------------------------------------------------------------------

def reconcile_stale_estate_executions(db, EstateExecution) -> int:
    """Stage 6 reconciliation. Legacy rows (worker_handle_json NULL) keep
    the old os.kill path only on this host, else become `lost`. Stage-6
    rows are observed through the worker; placeholder rows resolve through
    the same same-id start / fence logic as dispatch; resolved rows get
    their spool.release retried. Never redispatches under a new id."""
    reconciled = _reconcile_legacy(db, EstateExecution)
    now = _now()
    stale_before = now - timedelta(seconds=OBSERVATION_STALE_SECONDS)
    candidates = db.query(EstateExecution.id).filter(
        EstateExecution.worker_handle_json.isnot(None),
        EstateExecution.worktree_resolution == "unresolved",
        EstateExecution.lifecycle_state.in_(("accepted", "running", "lost")),
    ).all()
    for (execution_id,) in candidates:
        row = _load_row(execution_id)
        if row is None:
            continue
        if row.last_observed_at is not None and row.last_observed_at > stale_before \
                and row.lifecycle_state != "lost":
            continue
        view, exc = _worker(row.host_id, "status", {"execution_id": execution_id}, deadline_s=10)
        if exc is None:
            _apply_view(execution_id, view)
            reconciled += 1
        elif _mark_lost_if_due(execution_id):
            reconciled += 1
    unreleased = db.query(EstateExecution.id).filter(
        EstateExecution.worker_handle_json.isnot(None),
        EstateExecution.worktree_resolution.in_(("not_started", "finalized", "recovered")),
        EstateExecution.spool_released_at.is_(None),
    ).limit(10).all()
    for (execution_id,) in unreleased:
        row = _load_row(execution_id)
        if row is not None:
            _release_spool(execution_id, row.worktree_resolution)
    return reconciled


def _reconcile_legacy(db, EstateExecution) -> int:
    import os
    cutoff_accept = _now() - timedelta(seconds=_router._STALE_EXECUTION_ACCEPT_GRACE_SECONDS)
    cutoff_pid = _now() - timedelta(seconds=_router._STALE_EXECUTION_PID_GRACE_SECONDS)
    this_host = _router.current_host_id()
    rows = db.query(EstateExecution).filter(
        EstateExecution.worker_handle_json.is_(None),
        EstateExecution.lifecycle_state.in_(("accepted", "running")),
    ).all()
    reconciled = 0
    for row in rows:
        if row.host_id != this_host:
            row.lifecycle_state = "lost"
            row.error = row.error or "legacy row on a non-local host: outcome cannot be observed here"
            reconciled += 1
            continue
        pid = row.worker_pid
        if pid is None:
            if row.submitted_at is not None and row.submitted_at >= cutoff_accept:
                continue
            reason = ("reconciled: no worker_pid recorded and row is older than "
                      f"{_router._STALE_EXECUTION_ACCEPT_GRACE_SECONDS}s -- launch never confirmed")
        else:
            try:
                os.kill(pid, 0)
                continue
            except ProcessLookupError:
                touched_at = row.updated_at or row.submitted_at
                if touched_at is not None and touched_at >= cutoff_pid:
                    continue
                reason = ("reconciled: recorded worker_pid no longer exists on this host -- backend "
                          "likely restarted or the worker crashed while this execution was in flight")
            except PermissionError:
                continue
        row.lifecycle_state = "interrupted"
        row.finished_at = row.finished_at or _now()
        row.error = row.error or reason
        reconciled += 1
    db.commit()
    return reconciled


def get_estate_execution(execution_id: str, wait_s: float = 0) -> Optional[dict]:
    """GET /api/estate/run/{id}[?wait=]: bounded wait (<= 60 s), re-read
    every 2 s, early return on any state other than accepted/running.
    Observation only -- never dispatches."""
    from core.database import EstateExecution, SessionLocal
    deadline = time.monotonic() + max(0.0, min(float(wait_s or 0), 60.0))
    while True:
        db = SessionLocal()
        try:
            reconcile_stale_estate_executions(db, EstateExecution)
            row = db.query(EstateExecution).filter(EstateExecution.id == execution_id).one_or_none()
            if row is None:
                return None
            view = execution_provenance(row)
        finally:
            db.close()
        if view["lifecycle_state"] not in ("accepted", "running") or time.monotonic() >= deadline:
            return view
        time.sleep(min(2.0, max(0.0, deadline - time.monotonic())))


def execution_provenance(row) -> dict:
    view = _router._estate_execution_provenance(row)
    view.update({
        "worktree_resolution": row.worktree_resolution,
        "admission_head_sha": row.admission_head_sha,
        "execution_deadline_at": row.execution_deadline_at.isoformat() if row.execution_deadline_at else None,
        "last_observed_at": row.last_observed_at.isoformat() if row.last_observed_at else None,
        "worker_handle": _handle_of(row),
        "executed": row.lifecycle_state not in ("accepted",) and not _is_placeholder(row),
    })
    push = (view.get("finalization") or {}).get("push") or {}
    if row.worktree_resolution == "unresolved":
        view["next_action"] = (_next_action_observe(row.id) if row.lifecycle_state in ("accepted", "running")
                               else park_lease_ops.UNRESOLVED_NEXT_ACTION.get(row.lifecycle_state, "recover"))
    elif push.get("state") in ("failed", "not_attempted"):
        view["next_action"] = _next_action_push(row.id)
    return view


# ---------------------------------------------------------------------
# Finalize (S6.1 / S6.10)
# ---------------------------------------------------------------------

def finalize_execution(*, execution_id: str, repo_id: str, host_id: str, commit_message: str) -> dict:
    from core.database import EstateExecution, ParkLease, lease_serialized_transaction
    row = _load_row(execution_id)
    if row is None:
        return {"finalized": False, "reason": f"no execution found with id {execution_id!r}"}
    if row.repo_id != repo_id or row.host_id != host_id:
        return {"finalized": False, "reason": "repo/host do not match the execution"}
    if row.worktree_resolution == "finalized":
        return {"finalized": True, "already_finalized": True,
                **(json.loads(row.finalization_json) if row.finalization_json else {})}
    if row.lifecycle_state != "succeeded" or row.worktree_resolution != "unresolved":
        return {"finalized": False, "reason": f"execution is {row.lifecycle_state!r}/{row.worktree_resolution!r}, "
                                              "not succeeded/unresolved -- refusing to finalise"}
    authority = _lease_authority(repo_id, host_id)
    if not authority["ok"]:
        return {"finalized": False, "reason": f"authority re-verification failed: {authority['error']}"}
    if authority["lease_id"] != row.lease_id or authority["worktree_path"] != row.worktree_path \
            or authority["branch"] != row.branch:
        return {"finalized": False, "reason": "lease drift: the execution's exact lease/worktree/branch is no "
                                              "longer the authoritative lease"}
    status, exc = _worker(host_id, "status", {"execution_id": execution_id}, deadline_s=20)
    if exc is not None:
        return {"finalized": False, "reason": f"worker_unreachable: {exc}"}
    if status.get("quiescent") is not True:
        return {"finalized": False, "reason": "writer_quiescence_unproven"}
    result, exc = _worker(host_id, "worktree.finalize", {
        "execution_id": execution_id, "repo_id": repo_id, "worktree_path": row.worktree_path,
        "branch": row.branch, "commit_message": commit_message, "expected_head_sha": row.admission_head_sha,
    }, deadline_s=180)
    if exc is not None and not _is_ambiguous(exc):
        # A definite worker refusal (unattributable history, missing claim,
        # prerequisites): nothing was finalized; do not close.
        return {"finalized": False, "reason": f"{exc.code}: {exc}", "next_action": "recover"}
    # Close BEFORE recording `finalized` (6c adjudication finding 1): the
    # closure fences every later finalize attempt of this execution, and the
    # aggregate proves every earlier one finished. The outcome is read from
    # the closure view, so a lost finalize response resolves idempotently.
    closure, cexc = _worker(host_id, "status", {"execution_id": execution_id, "close": True}, deadline_s=60)
    if cexc is not None:
        return {"finalized": False, "reason": f"worker_unreachable: {cexc}", "next_action": "retry finalize"}
    if closure.get("quiescent") is not True:
        return {"finalized": False, "reason": "finalize_in_progress", "next_action": "retry finalize"}
    result = closure.get("finalize_result") or {}
    if result.get("outcome") != "finalized":
        return {"finalized": False, "reason": result.get("outcome") or "no finalized attempt recorded",
                "evidence": result, "next_action": "recover"}
    verify, exc = _worker(host_id, "worktree.verify",
                          {"repo_id": repo_id, "worktree_path": row.worktree_path, "branch": row.branch},
                          deadline_s=30)
    if exc is not None or not verify.get("ok") or verify.get("clean") is not True \
            or verify.get("head_sha") != result.get("commit_sha"):
        return {"finalized": False, "reason": "post-finalize verification did not report the clean, recorded "
                                              "finalize commit", "evidence": result, "next_action": "recover"}
    record = {key: result.get(key) for key in ("committed", "adopted", "commit_sha", "parent_sha",
                                               "dirty_paths", "push")}
    record["push"] = {**(record.get("push") or {}), "attempts": 1}
    with lease_serialized_transaction(lease_id=row.lease_id) as db:
        current = db.query(EstateExecution).filter(EstateExecution.id == execution_id).one_or_none()
        lease = db.query(ParkLease).filter(ParkLease.id == row.lease_id).one_or_none()
        if current is None or current.lifecycle_state != "succeeded" or current.worktree_resolution != "unresolved":
            return {"finalized": False, "reason": "execution changed during finalization"}
        if lease is None or lease.status != "active" or lease.host_id != host_id \
                or lease.worktree_path != row.worktree_path or lease.branch != row.branch \
                or not park_lease_ops.lease_authority_state(db, lease)["authoritative"]:
            return {"finalized": False, "reason": "lease changed during finalization"}
        current.worktree_resolution = "finalized"
        current.finalization_json = _merge_finalization(current.finalization_json, **record)
    _release_spool(execution_id, "finalized")
    response = {"finalized": True, **record}
    if (record.get("push") or {}).get("state") == "failed":
        response["next_action"] = _next_action_push(execution_id)
    return response


# ---------------------------------------------------------------------
# Recovery release (S6.2)
# ---------------------------------------------------------------------

def recover_execution_lease(execution_id: str, *, lease_id: str, host_id: str, repo_id: str,
                            branch: str, worktree_path: str) -> dict:
    from core.database import EstateExecution, ParkLease, get_db_session, lease_serialized_transaction
    supplied = {"lease_id": lease_id, "host_id": host_id, "repo_id": repo_id,
                "branch": branch, "worktree_path": worktree_path}
    row = _load_row(execution_id)
    if row is None:                                                                      # 1
        return {"recovered": False, "code": "not_found", "reason": f"no execution {execution_id!r}"}
    if any(getattr(row, key) != value for key, value in supplied.items()):
        return {"recovered": False, "code": "identifier_mismatch",
                "reason": "every identifier must equal the execution's recorded values exactly"}
    with get_db_session() as db:                                                         # 2
        lease = db.query(ParkLease).filter(ParkLease.id == lease_id).one_or_none()
        lease_ok = (lease is not None and lease.status == "active" and lease.host_id == host_id
                    and lease.repo_id == repo_id and lease.branch == branch and lease.worktree_path == worktree_path)
    if not lease_ok:
        return {"recovered": False, "code": "lease_mismatch", "reason": "the exact lease is not active/matching"}
    if row.worktree_resolution != "unresolved" or row.lifecycle_state not in _SETTLED_FOR_RECOVERY:  # 3
        return {"recovered": False, "code": "execution_not_settled",
                "reason": f"execution is {row.lifecycle_state!r}/{row.worktree_resolution!r}"}
    status, exc = _worker(host_id, "status", {"execution_id": execution_id, "close": True}, deadline_s=30)  # 4
    if exc is not None:
        return {"recovered": False, "code": "worker_unreachable", "reason": str(exc)}
    recorded = _handle_of(row) or {}
    observed = status.get("handle") or {}
    if status.get("state") not in ("start_failed", "fenced") and \
            any(recorded.get(key) != observed.get(key) for key in ("pid", "create_time", "cgroup", "unit")):
        return {"recovered": False, "code": "handle_mismatch", "reason": "worker handle does not match the row"}
    if status.get("state") not in (*_TERMINAL, "interrupted", "start_failed", "fenced") \
            or status.get("quiescent") is not True:
        return {"recovered": False, "code": "writer_quiescence_unproven",
                "reason": f"worker reports {status.get('state')!r}, quiescent={status.get('quiescent')!r}"}
    verify, exc = _worker(host_id, "worktree.verify",                                    # 5 (after closure)
                          {"repo_id": repo_id, "worktree_path": worktree_path, "branch": branch}, deadline_s=30)
    if exc is not None:
        return {"recovered": False, "code": "worker_unreachable", "reason": str(exc)}
    if not verify.get("ok") or verify.get("clean") is not True:
        return {"recovered": False, "code": "worktree_not_clean", "evidence": verify}
    head = verify.get("head_sha")
    finalize_commit = status.get("finalize_commit") or {}
    recovery = {"head_sha": head, "clean": True, "observed_state": status.get("state"), "at": _now().isoformat(),
                "admission_head_sha": row.admission_head_sha,
                "finalize_commit": bool(finalize_commit) and finalize_commit.get("commit_sha") == head,
                "finalize_ambiguous": head != row.admission_head_sha and not finalize_commit}
    push = None
    if head and head != row.admission_head_sha:
        push = {"state": "not_attempted", "commit_sha": head, "branch": branch, "attempts": 0}
    with lease_serialized_transaction(lease_id=lease_id) as db:                          # 6
        current = db.query(EstateExecution).filter(EstateExecution.id == execution_id).one_or_none()
        lease = db.query(ParkLease).filter(ParkLease.id == lease_id).one_or_none()
        if current is None or current.worktree_resolution != "unresolved" \
                or current.lifecycle_state != row.lifecycle_state \
                or current.worker_handle_json != row.worker_handle_json \
                or lease is None or lease.status != "active" or lease.host_id != host_id \
                or lease.worktree_path != worktree_path or lease.branch != branch:
            return {"recovered": False, "code": "changed_during_recovery",
                    "reason": "the execution or lease changed since the precheck"}
        current.worktree_resolution = "recovered"
        parts = {"recovery": recovery}
        if push is not None:
            parts["push"] = push
        current.finalization_json = _merge_finalization(current.finalization_json, **parts)
        lease.status = "released"
        lease.released_at = _now()
    _release_spool(execution_id, "recovered")
    response = {"recovered": True, "execution_id": execution_id, "lease_id": lease_id, "recovery": recovery}
    if push is not None:
        response["next_action"] = _next_action_push(execution_id)
    return response


# ---------------------------------------------------------------------
# Governed push retry (S6.10)
# ---------------------------------------------------------------------

def push_finalized_execution(execution_id: str) -> dict:
    from core.database import EstateExecution, get_db_session
    row = _load_row(execution_id)
    if row is None:
        return {"pushed": False, "code": "not_found"}
    finalization = json.loads(row.finalization_json) if row.finalization_json else {}
    push = finalization.get("push") or {}
    recovery = finalization.get("recovery") or {}
    eligible = (
        (row.worktree_resolution == "finalized" and push.get("state") == "failed")
        or (row.worktree_resolution == "recovered" and push.get("state") in ("not_attempted", "failed")
            and recovery.get("head_sha") and recovery.get("head_sha") != row.admission_head_sha)
    )
    if not eligible or not push.get("commit_sha"):
        return {"pushed": False, "code": "not_eligible",
                "reason": f"{row.worktree_resolution!r} row with push state {push.get('state')!r}"}
    result, exc = _worker(row.host_id, "worktree.push", {       # the row's own host only
        "execution_id": execution_id, "repo_id": row.repo_id, "branch": row.branch,
        "commit_sha": push["commit_sha"],
    }, deadline_s=180)
    if exc is not None:
        return {"pushed": False, "code": exc.code, "reason": str(exc)}
    new_push = {**push, **(result.get("push") or {}), "attempts": int(push.get("attempts") or 0) + 1,
                "last_attempt_at": _now().isoformat()}
    if result.get("outcome") == "push_in_progress":
        return {"pushed": False, "code": "push_in_progress"}
    with get_db_session() as db:
        current = db.query(EstateExecution).filter(
            EstateExecution.id == execution_id,
            EstateExecution.worktree_resolution.in_(("finalized", "recovered")),
        ).one_or_none()
        if current is not None:
            current.finalization_json = _merge_finalization(current.finalization_json, push=new_push)
    response = {"pushed": bool(result.get("pushed")), "push": new_push}
    if not response["pushed"]:
        response["next_action"] = _next_action_push(execution_id)
    return response

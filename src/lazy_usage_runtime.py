"""Bounded continuation inside the existing lab service.

There is no automatic activation, scheduler, or task authority here. A run
advances one owner task through the portfolio, router and EstateExecution
seams. Sessions passed to public functions must have no pending caller writes;
each checkpoint is committed before crossing a worker boundary.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from core.database import EstateExecution, LazyUsageRun, ParkLease, utcnow_naive
from scripts import agentic_portfolio as portfolio
from src import estate_router, estate_write_lane, park_lease_ops
from src.delegation_preflight import delegation_preflight
from src import lazy_usage_coordinator as coordinator
from src.estate_worker_client import WorkerTransportError, call_worker
from src.runtime_paths import get_app_root

log = logging.getLogger(__name__)
INITIALIZER = "estate-queue-priority-execution@v2"
CEILINGS = {"max_seconds": 14400, "max_paid_calls": 12, "max_tool_calls": 150,
            "max_no_delivery_turns": 8, "max_repeat_failures": 3, "max_tokens": 2_000_000}
# `paid_calls` counts worker/provider DISPATCHES, not model or token consumption. Where a
# provider reports no usage (codex-write, plain advisory CLI output) the run is charged a
# deliberately conservative estimate instead of zero, so the token ceiling still binds.
UNMEASURED_TOKEN_ESTIMATE = 150_000
UNMEASURED_WRITE_TOKEN_ESTIMATE = 400_000
TOKEN_KEYS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens",
              "input_tokens", "output_tokens")
TERMINAL = frozenset({"completed", "stopped", "failed", "budget_exhausted"})
EXECUTION_TERMINAL = frozenset({"succeeded", "failed", "timed_out", "interrupted"})
TASK_TERMINAL = frozenset({"done", "completed", "rejected", "superseded", "closed", "cancelled", "canceled"})
RECHECK_SECONDS = 300
LOOP_SECONDS = 25
# Execution classes. Only an implementation can deliver; every other class
# produces advisory evidence or a human handoff that never counts as delivery.
KINDS = ("implementation", "reconnaissance", "evidence", "review", "protected_handoff")
# Implementation always delivers. An evidence card delivers when it names a deliverable surface
# inside the review-side staging area (`_within_review_area`). A `review` card has no delivering
# lane yet: its writer would have to be an attested economical reviewer (`_reviewer_allowed`), and
# the only qualified write lane is codex. Reconnaissance and protected handoffs never deliver.
DELIVERING_KINDS = frozenset({"implementation", "evidence"})
REVIEW_SIDE_KINDS = frozenset({"evidence"})
REVIEW_SIDE_PREFIX = "automation/review/"
CONTROLLER_ROLES = frozenset({"laptop", "interface", "experiment-edge"})
VERIFICATION_PASS_BASES = ("deterministic_gate",)
HANDOFF_TASK_TYPES = frozenset({"human-approval", "human-handoff", "handoff"})
EVIDENCE_TASK_TYPES = frozenset({"evidence-synthesis", "evidence-gathering", "evidence"})
READ_ONLY_MODES = frozenset({"read-only", "read_only", "advisory"})
# Cross-activation memory. An unchanged revision is not re-dispatched while a
# prior result is fresh; both windows expire, so a retry is never blocked forever.
ADVISORY_REUSE_SECONDS = 86400
FAILURE_RETRY_SECONDS = 3600
LEDGER_MAX = 200
SETTLED_MAX = 400
STAGES_MAX = 100
HISTORY_RUNS = 10
HISTORY_SCAN_ROWS = 500
MAX_ASSESSED = 24


def _checkpoint(run, **fields):
    run.checkpoint = {**(run.checkpoint or {}), **fields}


def _save(db, run, **fields):
    _checkpoint(run, **fields)
    db.commit()
    return run_dict(run)


def _load(db, run_id, owner=None):
    # A write first on SQLite serializes transitions even when the row was
    # already read by this Session. PostgreSQL locks this exact run row.
    if db.get_bind().dialect.name == "sqlite":
        db.query(LazyUsageRun).filter_by(id=run_id).update(
            {LazyUsageRun.updated_at: LazyUsageRun.updated_at}, synchronize_session=False)
    run = db.query(LazyUsageRun).filter_by(id=run_id).populate_existing().with_for_update().one_or_none()
    if run is None:
        db.rollback()
        raise RunError(404, "run not found")
    if owner is not None and run.created_by != owner:
        db.rollback()
        raise RunError(403, "run belongs to another owner")
    return run


class RunError(ValueError):
    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


def _usage_view(counters):
    """Dispatch counts and token consumption are different quantities: keep them apart."""
    measured, assumed = counters.get("tokens_measured", 0), counters.get("tokens_assumed", 0)
    dispatches = counters.get("paid_calls", 0)
    if measured and assumed:
        basis = "measured plus assumed (conservative estimate for unmeasured dispatches)"
    elif measured:
        basis = "measured"
    elif assumed:
        basis = "assumed (conservative estimate: provider usage not measurable)"
    else:
        basis = "no usage yet" if not dispatches else "unmeasured"
    return {"dispatches": dispatches, "tool_calls": counters.get("tool_calls", 0),
            "tokens_measured": measured, "tokens_assumed": assumed,
            "tokens_total": measured + assumed, "basis": basis}


def run_dict(run):
    cp = dict(run.checkpoint or {})
    elapsed = max(0, ((run.finished_at or utcnow_naive()) - run.started_at).total_seconds()) if run.started_at else 0
    return {"id": run.id, "state": run.state, "created_by": run.created_by,
            "initializer": run.initializer, "repo_scope": run.repo_scope,
            "budgets": run.budgets, "counters": {**run.counters, "elapsed_seconds": elapsed},
            "usage": _usage_view(run.counters or {}),
            "checkpoint": cp, "owed_reviews": cp.get("owed_reviews", []),
            "terminal_reason": run.terminal_reason,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None}


def activate_run(db, owner, repo_scope=None, budget_overrides=None, coordinator=None):
    if not isinstance(owner, str) or not owner.strip():
        raise RunError(422, "owner is required")
    scope = list(portfolio.LAYOUT) if repo_scope is None else repo_scope
    if (not isinstance(scope, list) or not scope or
            any(not isinstance(r, str) or r not in portfolio.LAYOUT for r in scope)):
        raise RunError(422, "repo_scope must contain registered frontier repositories")
    overrides = budget_overrides or {}
    if not isinstance(overrides, dict) or set(overrides) - CEILINGS.keys():
        raise RunError(422, "unknown budget")
    budgets = dict(CEILINGS)
    for key, value in overrides.items():
        if type(value) is not int or value < 0:
            raise RunError(422, "budgets must be nonnegative integers")
        budgets[key] = min(value, CEILINGS[key])
    if coordinator is not None and (
            not isinstance(coordinator, dict) or set(coordinator) - {"enabled"}
            or type(coordinator.get("enabled")) is not bool):
        raise RunError(422, "coordinator must be {'enabled': bool}")
    if db.query(LazyUsageRun).filter(LazyUsageRun.state.notin_(TERMINAL)).first():
        db.rollback()
        raise RunError(409, "a non-terminal activation already exists")
    scope = list(dict.fromkeys(scope))
    ledger, owed = _inherited_history(db, scope, owner)
    settled = _inherited_settlements(db, scope, owner)
    run = LazyUsageRun(id=str(uuid.uuid4()), state="requested", created_by=owner,
                       initializer=INITIALIZER, repo_scope=scope,
                       budgets=budgets, started_at=utcnow_naive(),
                       counters={"paid_calls": 0, "tool_calls": 0, "no_delivery_turns": 0,
                                 "repeated_failures": 0, "last_failure_signature": None},
                       checkpoint={"phase": "idle", "in_flight_execution_id": None,
                                   "owed_reviews": owed, "ledger": ledger, "settled_reviews": settled,
                                   "next_action": "refresh_frontier",
                                   **({"coordinator": coordinator} if coordinator and coordinator.get("enabled") else {})})
    db.add(run)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RunError(409, "a non-terminal activation already exists") from exc
    return run_dict(run)


def pause_run(db, run_id, owner):
    run = _load(db, run_id, owner)
    if run.state not in {"requested", "running", "paused"}:
        db.rollback()
        raise RunError(409, "run cannot be paused from this state")
    run.state = "paused"
    return _save(db, run, pause_reason="operator", recheck_at=None, next_action="operator_resume")


def resume_run(db, run_id, owner):
    run = _load(db, run_id, owner)
    if run.state != "paused":
        db.rollback()
        raise RunError(409, "only a paused run can resume; terminal budgets require a fresh activation")
    exhausted = _budget_reason(run)
    if exhausted:
        if run.checkpoint.get("in_flight_execution_id"):
            run.state = "stop_requested"
            _save(db, run, pending_terminal="budget_exhausted", budget_reason=exhausted)
            return _stop(db, run)
        return _finish(db, run, "budget_exhausted", exhausted)
    # Uncertain dispatches remain observation-only, including after an
    # explicit resume. Resuming never clears an in-flight reference.
    run.state = "running"
    return _save(db, run, pause_reason=None, recheck_at=None, next_action="observe" if
                 run.checkpoint.get("in_flight_execution_id") else "refresh_frontier")


def stop_run(db, run_id, owner):
    run = _load(db, run_id, owner)
    if run.state in TERMINAL:
        db.commit()
        return run_dict(run)
    run.state = "stop_requested"
    _save(db, run, next_action="cancel_and_observe")
    # Commit the stop BEFORE requesting bounded cancellation. Failure or
    # loss of transport preserves both the request and the lease.
    return _stop(db, run)


def _budget_reason(run, *, reserved=False):
    budgets = {k: min((run.budgets or {}).get(k, v), v) for k, v in CEILINGS.items()}
    if run.started_at and (utcnow_naive() - run.started_at).total_seconds() >= budgets["max_seconds"]:
        return "max_seconds"
    for ceiling, counter in (("max_paid_calls", "paid_calls"), ("max_tool_calls", "tool_calls"),
                             ("max_no_delivery_turns", "no_delivery_turns"),
                             ("max_repeat_failures", "repeated_failures")):
        value = (run.counters or {}).get(counter, 0)
        limit = budgets[ceiling]
        if (value > limit if reserved and counter in {"paid_calls", "tool_calls"} else value >= limit):
            return ceiling
    counters = run.counters or {}
    if counters.get("tokens_measured", 0) + counters.get("tokens_assumed", 0) >= budgets["max_tokens"]:
        return "max_tokens"
    return None


def _token_headroom_exhausted(run, provider, write):
    """Refuse a paid dispatch whose conservative token estimate would cross the ceiling."""
    if provider is None:
        return False
    counters = run.counters or {}
    limit = min((run.budgets or {}).get("max_tokens", CEILINGS["max_tokens"]), CEILINGS["max_tokens"])
    estimate = UNMEASURED_WRITE_TOKEN_ESTIMATE if write else UNMEASURED_TOKEN_ESTIMATE
    return counters.get("tokens_measured", 0) + counters.get("tokens_assumed", 0) + estimate > limit


def _charge(run, **counts):
    counters = dict(run.counters or {})
    for key, count in counts.items():
        counters[key] = counters.get(key, 0) + count
    run.counters = counters


def _finish(db, run, state, reason):
    run.state, run.terminal_reason, run.finished_at = state, reason, utcnow_naive()
    return _save(db, run, next_action="fresh_activation" if state == "budget_exhausted" else "none")


def _park(db, run, reason, *, automatic=True):
    # The planning worker can race an operator stop. Only write fields it
    # owns before refreshing the authoritative lifecycle state.
    current_state = db.query(LazyUsageRun.state).filter_by(id=run.id).with_for_update().scalar()
    if current_state in TERMINAL:
        db.rollback()
        db.refresh(run)
        return run_dict(run)
    db.flush()
    db.refresh(run, attribute_names=["state"])
    if run.state not in {"stop_requested", "stopping"}:
        run.state = "paused"
    return _save(db, run, pause_reason=reason, next_action="event_recheck" if automatic else "operator_resume",
                 recheck_at=(utcnow_naive() + timedelta(seconds=RECHECK_SECONDS)).isoformat() if automatic else None)


def refresh_frontier(repo_scope):
    """The service IS the lab: call local portfolio functions, never its SSH CLI."""
    roots, missing = portfolio.resolve_roots(Path(get_app_root()), {})
    roots = {rid: root for rid, root in roots.items() if rid in repo_scope}
    missing = {rid: reason for rid, reason in missing.items() if rid in repo_scope}
    records, counts, warnings = [], {}, []
    for rid, root in roots.items():
        rows, buckets, issues = portfolio.collect(rid, root)
        records.extend(rows)
        counts[rid] = buckets
        warnings.extend(issues)
    return {"roots": roots, "records": records, "unavailable": missing,
            "counts": counts, "warnings": warnings}


def _digest(frontier):
    # No prose, task bodies or host secrets are persisted.
    value = {k: frontier[k] for k in ("records", "unavailable", "counts", "warnings")}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _contract(frontier, record):
    rid, bucket, name = portfolio.parse_ref(record["ref"])
    queue = portfolio.queue_path(frontier["roots"][rid], Path(portfolio.LAYOUT[rid][0]))
    metadata, body = portfolio.split_card(portfolio.read_card(queue, bucket, name))
    return metadata, body


def _classify(record, meta):
    """Deterministic execution class from the owner card; never from model output."""
    task_type = str(meta.get("task_type") or "").lower()
    mode = str(meta.get("execution_mode") or "").lower()
    if (str(meta.get("executor") or "").lower() == "human" or mode == "handoff"
            or task_type in HANDOFF_TASK_TYPES):
        return "protected_handoff"
    if record["bucket"] == "review" or task_type in {"review", "independent-review"}:
        return "review"
    if meta.get("approval_required") is True and not _approval_valid(meta):
        # Without an owner approval bound to this exact scope the gate is only
        # re-adjudicated; see `approval_scope` for the governed way past it.
        return "reconnaissance"
    if mode in READ_ONLY_MODES or task_type in EVIDENCE_TASK_TYPES:
        return "evidence"
    return "implementation"


def approval_scope(meta):
    """Digest of exactly what an owner approval covers (never prose, never the title)."""
    scope = {key: meta.get(key) for key in ("task_id", "task_type", "execution_mode", "allowed_paths",
                                            "denied_paths", "outputs", "result_path")}
    return hashlib.sha256(json.dumps(scope, sort_keys=True, default=str).encode()).hexdigest()


def _approval_valid(meta):
    """An `approval` block written by the owner in the card, bound to the current scope.

    Only the owner edits the card (its directory is denied to every writer), so a model
    cannot approve itself; any change to the covered scope invalidates the approval."""
    approval = meta.get("approval")
    return (isinstance(approval, dict) and str(approval.get("status", "")).lower() == "approved"
            and isinstance(approval.get("approved_by"), str) and bool(approval["approved_by"].strip())
            and isinstance(approval.get("approved_at"), str) and bool(approval["approved_at"].strip())
            and approval.get("scope_sha256") == approval_scope(meta))


def _writes(kind, meta):
    """Only these classes get a repository write lease and a worker-owned finalisation."""
    return kind == "implementation" or (kind in REVIEW_SIDE_KINDS and _deliverable_surface(meta))


_LITERAL_PATH = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]*\Z")


def _allowed_paths(meta):
    """What a writer may commit: the card's allowed_paths, else its result_path, else nothing (and a write
    with nothing is refused). Never empty-means-everything (Sol review of #301-#304: an outputs-only approval
    left the worker's allow-list empty, so any path outside the denied list passed finalisation). `outputs` is
    prose-capable and is not a path allow-list: widening the scope with it could pass the review-area guard,
    which sees only allowed_paths and result_path."""
    slash = lambda p: p.replace(chr(92), "/")
    allowed = [slash(p) for p in (meta.get("allowed_paths") or []) if isinstance(p, str)]
    if allowed:
        return allowed
    result = meta.get("result_path")
    if isinstance(result, str) and result:
        return [slash(result)]
    # outputs-only card: only literal repository paths count; descriptive prose ("minimal documentation
    # updates") names no file and must never become a scope
    outputs = meta.get("outputs") or []
    outputs = [outputs] if isinstance(outputs, str) else outputs
    return [p for p in outputs if isinstance(p, str) and _LITERAL_PATH.match(p)
            and all(seg not in {"", ".", ".."} for seg in p.split("/"))]


def _write_scope(repo_id, meta):
    """Paths a writer may commit, and paths it may never touch (always incl. the owner cards)."""
    allowed = _allowed_paths(meta)
    denied = [p.replace(chr(92), "/") for p in (meta.get("denied_paths") or []) if isinstance(p, str)]
    card_dir = str(Path(portfolio.LAYOUT[repo_id][0])).replace("\\", "/") + "/**"
    return {"allowed": allowed, "denied": list(dict.fromkeys([*denied, card_dir]))}


def _task(record, meta, body, kind=None):
    kind = kind or _classify(record, meta)
    assessment = kind == "reconnaissance"
    write = _writes(kind, meta)
    # Advisory classes read the repository, which the plain local model cannot
    # do (it fabricates plausible output), so they default to a paid lane.
    capabilities = meta.get("capabilities") or ["code-strong"]
    if not isinstance(capabilities, list) or not all(isinstance(v, str) for v in capabilities):
        raise ValueError("invalid task capabilities")
    # The contract is loaded only for a selected task and stays in memory.
    rid, bucket, name = portfolio.parse_ref(record["ref"])
    contract_path = str(Path(portfolio.LAYOUT[rid][0]) / bucket / name)
    objective = (f"Execute the owning task {record['ref']} ({contract_path}) under {INITIALIZER}. "
                 "Read AGENTS.md and the task contract; preserve protected gates and owner authority. "
                 "Use deterministic checks and independent verification as required. "
                 "Reconcile the owning task only with its acceptance evidence; do not claim shipment "
                 "without required merge/deployment. Do not start unrelated child work.\n" + body)
    if assessment:
        objective = (f"Read-only repository reconnaissance of {contract_path}: re-adjudicate its approval_required "
                     "claim against current HEAD, repository authority and acceptance evidence. Identify stale, "
                     "agent-resolvable or genuinely protected gates and report evidence. Do not execute the "
                     "underlying task, change permissions, or publish anything.\n" + body)
    if write:
        # Live runs f4b6f653 / 473209ae: writers kept editing their own owner task card and recording
        # prompt-application/evolution traces under evals/. The scope gate reverts those and reports a
        # scope_violation, which costs a whole write. Say it up front; the controller does both.
        objective += ("\nMake no edit outside the allowed paths. In particular do not edit the owner task card and do "
                      "not record prompt-application or prompt-evolution traces: the controller records those "
                      "after verification and review.")
    if write and kind in REVIEW_SIDE_KINDS:
        scope = _write_scope(record["repo_id"], meta)
        objective += ("\nDeliver a review-side artifact only. Write only under: " + ", ".join(scope["allowed"]) +
                      ". Never edit the owner task cards, canonical files or anything outside those paths, and "
                      "never mark the task done or record an approval: owner acceptance is a separate step.")
    return {"task_class": "implementation" if write else "repository-reconnaissance",
            "repo": record["repo_id"], "objective": objective,
            "requirements": {"capabilities": capabilities},
            "routing": {"allow_paid_escalation": True, **({"mode": "implementation"} if write else {})}}, write


def _reviewer_allowed(record, meta, selected):
    if record["bucket"] != "review" and meta.get("task_type") not in {"review", "independent-review"}:
        return True
    # Every concrete route, including failover, needs the same attestation.
    model = str(selected.get("concrete_model") or "").lower()
    return any(name in model for name in ("haiku", "terra", "glm-flash"))


def _task_key(ref):
    """Task identity independent of the bucket a card currently sits in (ready -> done)."""
    repo, _, rest = str(ref).partition(":")
    return f"{repo}:{rest.rsplit('/', 1)[-1]}"


def _debt_gate(debt):
    # Checkpoints predating explicit gates used an error to identify quota debt.
    return debt.get("gate") or ("verification" if debt.get("error") else "owner_acceptance")


def _set_review_debts(run, debts):
    newest = {}
    for debt in debts:
        ref = debt.get("task_ref") or debt.get("task_id")
        newest[(_task_key(ref) if debt.get("task_ref") else ref, _debt_gate(debt))] = debt
    _checkpoint(run, owed_reviews=list(newest.values()))


def _settle(run, task_ref, status):
    """Tombstone: a settled card's debt must not be resurrected by an older run's copy."""
    settled = dict(run.checkpoint.get("settled_reviews") or {})
    settled[_task_key(task_ref)] = {"at": utcnow_naive().isoformat(), "status": status, "basis": "owner_card"}
    if len(settled) > SETTLED_MAX:
        for key in sorted(settled, key=lambda k: settled[k].get("at") or "")[:len(settled) - SETTLED_MAX]:
            del settled[key]
    _checkpoint(run, settled_reviews=settled)


def _reconcile_review_debts(run, task_ref, *, verified=False, acceptance=None):
    acceptance = acceptance or {}
    status = str(acceptance.get("status", "")).lower()
    settled = acceptance.get("delivered") or status in TASK_TERMINAL
    key = _task_key(task_ref)
    if settled:
        _settle(run, task_ref, status or "done")
    # Settling a card clears what the OWNER was asked for. A gap in the other evidence
    # (an unverified or unreviewed acceptance, a failed finalisation) stays visible until
    # that evidence exists or the debt is superseded with owner-authorised evidence.
    _set_review_debts(run, [debt for debt in run.checkpoint.get("owed_reviews", [])
                           if _task_key(debt.get("task_ref") or "?:?") != key or
                           not ((settled and not _evidence_gap(debt)) or
                                verified and _debt_gate(debt) == "verification" and not _evidence_gap(debt))])


def _evidence_gap(debt):
    return bool(debt.get("evidence_gap")) or _debt_gate(debt) in {"independent_review", "finalization", "recovery"}


def _execution_resolved(run, execution_id):
    """The execution's worktree is no longer `unresolved`: the governed recover/finalize path has run (live
    2026-11-21: `am recover` cleared a killed write's lease but its `recovery` debt stayed forever)."""
    from sqlalchemy.orm import object_session
    session = object_session(run)
    if not execution_id or session is None:
        return False
    row = session.get(EstateExecution, execution_id)
    if row is None:
        return False
    session.refresh(row)
    return row.worktree_resolution in {"recovered", "finalized"}


def _resolve_met_debts(run, task_ref, frontier):
    """Drop debts whose own condition is now met by the owner card (approval, review evidence)."""
    key = _task_key(task_ref)
    meta = _card_meta({"task_ref": task_ref, "repo_id": task_ref.split(":", 1)[0]}, frontier)
    kept = []
    owed = run.checkpoint.get("owed_reviews", [])
    verified_now = any(_task_key(d.get("task_ref") or "?:?") == key and _debt_gate(d) == "verification"
                       and _verification_recorded(meta, d.get("commit_sha")) and not _settled_after(run, key, d)
                       for d in owed)
    for debt in owed:
        if _task_key(debt.get("task_ref") or "?:?") == key:
            gate = _debt_gate(debt)
            if gate == "owner_acceptance" and verified_now:
                continue                  # an older commit's acceptance is replaced by the newly verified one
            if gate == "owner_approval" and _approval_valid(meta):
                continue
            if gate == "verification" and _verification_recorded(meta, debt.get("commit_sha")):
                # The deterministic check is now on the card, so the finalised write is ready for the owner:
                # queue its acceptance (held back by any open review debt) instead of leaving the task with no
                # open item, which made it eligible for a repeat dispatch (Sol review of #301-#304).
                if not _settled_after(run, key, debt):
                    kept.append({**{k: v for k, v in debt.items() if k not in {"evidence_gap", "error"}},
                                 "gate": "owner_acceptance", "acceptance_after_verification": True,
                                 "next_action": "owner_acceptance_and_required_independent_verification"})
                continue
            if gate in {"recovery", "finalization"} and _execution_resolved(run, debt.get("execution_id")):
                continue
            if gate == "independent_review" and evidence_stages(
                    {"lifecycle_state": "succeeded"}, {"ok": True}, {"delivered": False}, meta,
                    author_provider=debt.get("author_provider"))["review"]["status"] == "recorded":
                continue
        kept.append(debt)
    _set_review_debts(run, kept)


def _settled_after(run, key, debt):
    """The task was settled at or after this debt opened (a settlement of an EARLIER attempt does not count)."""
    entry = (run.checkpoint.get("settled_reviews") or {}).get(key)
    if not isinstance(entry, dict):
        return False
    settled_at, opened_at = _stamp(entry.get("at")), _stamp(debt.get("opened_at"))
    return settled_at is None or opened_at is None or settled_at >= opened_at


def _verification_recorded(meta, commit_sha):
    """A passing deterministic check recorded on the card for EXACTLY this commit, with a reference
    and an attesting principal. It clears the verification debt of a finalised write; nothing the
    writer itself produced can do so (its directory is denied to it)."""
    if not isinstance(commit_sha, str) or not commit_sha:
        return False
    return any(isinstance(entry, dict) and str(entry.get("result", "")).lower() == "pass"
               and entry.get("commit_sha") == commit_sha
               and isinstance(entry.get("ref"), str) and entry["ref"].strip()
               and isinstance(entry.get("verified_by"), str) and entry["verified_by"].strip()
               for entry in (meta.get("verification_evidence") or []))


def _deliverable_surface(meta):
    """A write task must name where its output lands (paths, outputs or a result file)."""
    return any(meta.get(key) for key in ("allowed_paths", "outputs", "result_path"))


def _static_blocker(kind, meta, write):
    """Feasibility facts that need no routing: authority, tools and deliverables."""
    if kind == "protected_handoff":
        return "protected_handoff"
    if meta.get("blocked_by") or meta.get("protected_gate"):
        return "protected_gate"
    if meta.get("requires_zotero") is True:
        # No estate host declares a Zotero capability, so no lane can honour it.
        return "requires_zotero_unavailable"
    if write and not _deliverable_surface(meta):
        return "no_deliverable_surface"
    if write and not _allowed_paths(meta):
        return "write_scope_missing"
    if kind in REVIEW_SIDE_KINDS and write and not _within_review_area(meta):
        return "deliverable_outside_review_area"
    return None


def _within_review_area(meta):
    """An evidence/review artifact lands in the non-canonical review area, never canon."""
    paths = _allowed_paths(meta)
    return bool(paths) and all(p.replace("\\", "/").startswith(REVIEW_SIDE_PREFIX) and ".." not in p.split("/")
                              for p in paths)


def _resolve_host(label):
    """Map a card's `execution_host` label to a registered host by id, role or hostname."""
    wanted = str(label).strip().lower()
    for host in estate_router._load_yaml("estate").get("hosts") or []:
        names = {str(host.get(k, "")).lower() for k in ("id", "role", "hostname")}
        if wanted in names:
            return host
    return None


def _host_capabilities(host_id):
    """Tools a worker host declares (estate.yaml `worker.capabilities`); nothing is assumed."""
    for host in estate_router._load_yaml("estate").get("hosts") or []:
        if host.get("id") == host_id:
            return {str(c).lower() for c in (host.get("worker") or {}).get("capabilities") or []}
    return set()


def _capability_blocker(meta, host_id, qualified):
    """Validate what the card requires against the host actually selected, before dispatch."""
    label = meta.get("execution_host")
    if label:
        target = _resolve_host(label)
        if target is None:
            return "execution_host_unresolved"
        if target.get("role") in CONTROLLER_ROLES or not (target.get("worker") or {}).get("enabled"):
            return "execution_host_not_a_worker"
        if target.get("id") != host_id:
            return "execution_host_not_selected"
    declared = _host_capabilities(host_id)
    for need, capability in (("requires_web", "web"), ("requires_mcp", "mcp"), ("requires_zotero", "zotero")):
        if meta.get(need) is True and capability not in declared:
            return f"{need}_unavailable"
    if meta.get("requires_local_model") is True and "local" not in qualified:
        return "requires_local_model_unavailable"
    return None


def _repo_lease_held(run, repo_id):
    """An active or preparing write lease on this repo (typically this run's own earlier,
    still-unfinalized write) makes park_with_worktree raise ParkConflict. That is a known
    precondition, not a failure of the task: skip it and let independent work proceed."""
    from sqlalchemy.orm import object_session
    session = object_session(run)
    if session is None:
        from core.database import SessionLocal
        with SessionLocal() as own:
            return _repo_lease_held_in(own, repo_id)
    return _repo_lease_held_in(session, repo_id)


def _repo_lease_held_in(db, repo_id):
    """Mirror park_repo's own conflict rule (lease_authority_state), so this only blocks
    where park_with_worktree would raise ParkConflict: a stale unprotected lease is
    reclaimable and an old `preparing` reservation is resolved by its probe, so neither
    counts as held."""
    existing = db.query(ParkLease).filter(ParkLease.repo_id == repo_id,
                                          ParkLease.status.in_(("active", "preparing"))).first()
    if existing is None:
        return False
    authority = park_lease_ops.lease_authority_state(db, existing)
    return not (authority["reclaimable"] or authority.get("prepare_probe_due"))


def _age_seconds(stamp):
    try:
        return (utcnow_naive() - datetime.fromisoformat(stamp)).total_seconds()
    except (TypeError, ValueError):
        return float("inf")


def _recent_blocker(run, ref, revision):
    """Why an unchanged revision should not be dispatched again right now."""
    cp = run.checkpoint
    debts = [d for d in cp.get("owed_reviews", []) if _task_key(d.get("task_ref") or "?:?") == _task_key(ref)]
    retry_due = False
    if any(d.get("acceptance_after_verification") and _debt_gate(d) == "owner_acceptance" for d in debts):
        return "awaiting_owner_acceptance"           # recording the check edits the card, so the revision moved on
    for debt in debts:
        if not debt.get("error") or not debt.get("retry_after"):
            continue
        reset = datetime.fromisoformat(debt["retry_after"].replace("Z", "+00:00"))
        retry_due |= reset.tzinfo is not None and datetime.now(timezone.utc) >= reset
    if cp.get("attempted", {}).get(ref) == revision and not retry_due:
        return "attempted_this_activation"
    entry = (cp.get("ledger") or {}).get(ref)
    if not entry or entry.get("revision") != revision:
        return None
    outcome, age = entry.get("outcome"), _age_seconds(entry.get("at"))
    if outcome in {"advisory_complete", "protected_handoff", "attempted_legacy",
                   "delivered"} and age < ADVISORY_REUSE_SECONDS:
        return "result_reusable"
    if outcome in {"failed", "scope_violation", "finalize_failed"} and age < FAILURE_RETRY_SECONDS:
        return "failure_backoff"
    if outcome == "quota_parked" and not retry_due and (
            any(d.get("error") and d.get("retry_after") for d in debts) or age < FAILURE_RETRY_SECONDS):
        # Blocked until the provider's *stated* reset; with no stated reset (the
        # debt was reconciled away) it is only a bounded backoff, never permanent.
        return "quota_retry_pending"
    if outcome == "delivered_pending_acceptance" and any(_debt_gate(d) == "owner_acceptance" for d in debts):
        return "awaiting_owner_acceptance"
    if outcome == "unverified" and any(_debt_gate(d) == "verification" and _evidence_gap(d) for d in debts):
        return "awaiting_verification"
    if outcome == "awaiting_approval" and any(_debt_gate(d) == "owner_approval" for d in debts):
        return "awaiting_owner_approval"
    return None


def _assess(frontier, run, record):
    """Side-effect-free feasibility verdict for one candidate.

    Validates, before any dispatch, that the card's class, authority, required
    tools, deliverable, model lane and provider can actually deliver. `ok` is
    the single dispatch gate; `blocker` is a stable reason code. Selection and
    the coordinator's evidence both come from here, so they cannot disagree.
    """
    meta, body = _contract(frontier, record)
    revision = hashlib.sha256(json.dumps(meta, sort_keys=True, default=str).encode() + body.encode()).hexdigest()
    kind = _classify(record, meta)
    write = _writes(kind, meta)
    verdict = {"ref": record["ref"], "kind": kind, "delivers": write, "ok": False,
               "blocker": None, "revision": revision, "meta": meta, "body": body, "title": meta.get("title"),
               "scope": _write_scope(record["repo_id"], meta) if write else None}
    verdict["blocker"] = _static_blocker(kind, meta, write) or _recent_blocker(run, record["ref"], revision)
    if not verdict["blocker"] and write and _repo_lease_held(run, record["repo_id"]):
        verdict["blocker"] = "repo_lease_held"
    if verdict["blocker"]:
        return verdict
    task, write = _task(record, meta, body, kind)
    route = estate_router.resolve_route(task, record_decision=False)
    selected = route.get("route") or {}
    if not _reviewer_allowed(record, meta, selected):
        return {**verdict, "blocker": "reviewer_model_not_attested"}
    host = selected.get("host")
    checked = next((h for h in route.get("hosts_checked", []) if h.get("host_id") == host), {})
    executor = selected.get("executor")
    paid = executor == "none"
    provider = estate_router._resolve_paid_provider(selected.get("model_alias")).get("provider") if paid else None
    needed = "codex-write" if write else provider if paid else executor
    if not host or needed not in checked.get("qualified_executors", []):
        return {**verdict, "blocker": "no_qualified_lane"}
    # Reconnaissance only re-reads the repository; the card's execution host/tools govern the
    # task's own execution, which a reconnaissance never performs.
    capability = (None if kind == "reconnaissance"
                  else _capability_blocker(meta, host, checked.get("qualified_executors", [])))
    if capability:
        return {**verdict, "blocker": capability}
    if write and (provider != "codex" or not paid):
        return {**verdict, "blocker": "no_qualified_write_lane"}
    if not write and executor == "local":
        # A plain local model has no repository access; its "reconnaissance"
        # is fabricated text, so it can never evidence or deliver anything.
        return {**verdict, "blocker": "ungrounded_local_executor"}
    if executor == "deterministic":
        # The router's deterministic route answers placement, not execution.
        return {**verdict, "blocker": "deterministic_route_is_not_execution"}
    if paid:
        health = estate_router.provider_allows_dispatch(provider)
        if not health.get("allowed"):
            # Verified Codex usage-limit failover goes through the existing
            # explicit-provider router, retaining scope. No launcher or
            # credential observation qualifies a GLM route.
            if not write and provider == "codex" and health.get("state") == "quota_exhausted":
                alternate_task = {**task, "routing": {**task["routing"], "paid_provider": "glm"}}
                alternate = estate_router.resolve_route(alternate_task, record_decision=False)
                alternate_selected = alternate.get("route") or {}
                alternate_host = alternate_selected.get("host")
                alternate_entry = next((h for h in alternate.get("hosts_checked", [])
                                        if h.get("host_id") == alternate_host), {})
                if (alternate_host and "glm" in alternate_entry.get("qualified_executors", [])
                        and estate_router.provider_allows_dispatch("glm").get("allowed")
                        and _reviewer_allowed(record, meta, alternate_selected)):
                    task, host, provider = alternate_task, alternate_host, "glm"
                else:
                    return {**verdict, "blocker": "provider_unavailable"}
            else:
                return {**verdict, "blocker": "provider_unavailable"}
    return {**verdict, "ok": True, "task": task, "write": write, "host": host, "provider": provider}


def _ordered(frontier, plan=None):
    rows = sorted(frontier["records"], key=lambda r: (
        portfolio.RANK[r["bucket"]], portfolio.PRIORITY.get(str(r.get("priority", "")).lower(), 9), r["ref"]))
    if plan and isinstance(plan.get("order"), list):
        # Coordinator advice reorders candidates; every gate is unchanged.
        rank = {ref: i for i, ref in enumerate(plan["order"])}
        rows.sort(key=lambda r: rank.get(r["ref"], len(rank)))
    return [r for r in rows if r["bucket"] not in {"inbox", "blocked", "blocked-human"}
            and str(r.get("status", "")).lower() not in TASK_TERMINAL]


def candidate_evidence(frontier, run):
    """Compact per-candidate feasibility for the coordinator (bounded, no prose)."""
    out = []
    for record in _ordered(frontier)[:MAX_ASSESSED]:
        try:
            verdict = _assess(frontier, run, record)
        except Exception as exc:
            verdict = {"ref": record["ref"], "kind": None, "delivers": False, "ok": False,
                       "blocker": "assessment_" + type(exc).__name__, "meta": {}}
        entry = (run.checkpoint.get("ledger") or {}).get(record["ref"]) or {}
        out.append({"ref": record["ref"], "kind": verdict["kind"], "feasible": verdict["ok"],
                    "delivers": verdict["delivers"], "blocker": verdict["blocker"],
                    "title": str(verdict.get("title") or "")[:80],
                    "verification_route": verdict["meta"].get("verification_route"),
                    "approval_required": verdict["meta"].get("approval_required"),
                    "last_outcome": entry.get("outcome")})
    return out


def _choose(frontier, run, plan=None):
    # Re-read owner outcomes even for tasks that no longer need dispatch.
    # Absence alone never resolves debt; the done card must be read explicitly.
    for task_ref in dict.fromkeys(d.get("task_ref") for d in run.checkpoint.get("owed_reviews", [])):
        if task_ref:
            rid, _, _ = portfolio.parse_ref(task_ref)
            acceptance = _owner_task_status({"repo_id": rid, "task_ref": task_ref}, frontier)
            _reconcile_review_debts(run, task_ref, acceptance=acceptance)
            _resolve_met_debts(run, task_ref, frontier)
    skipped = {}
    for record in _ordered(frontier, plan):
        try:
            verdict = _assess(frontier, run, record)
        except Exception as exc:
            skipped[record["ref"]] = "assessment_" + type(exc).__name__
            continue
        if verdict["ok"]:
            _checkpoint(run, skipped=dict(list(skipped.items())[:40]))
            return (record, verdict["meta"], verdict["task"], verdict["write"], verdict["host"],
                    verdict["provider"], verdict["revision"], verdict["kind"], verdict["scope"])
        skipped[record["ref"]] = verdict["blocker"]
        if verdict["blocker"] == "protected_handoff":
            entry = (run.checkpoint.get("ledger") or {}).get(record["ref"]) or {}
            if entry.get("revision") != verdict["revision"] or entry.get("outcome") != "protected_handoff":
                # Recorded once as a human action; never dispatched to a model.
                _ledger_put(run, record["ref"], verdict["revision"], "protected_handoff", "protected_handoff")
    _checkpoint(run, skipped=dict(list(skipped.items())[:40]))
    return None


def _failure(run, cause, scope=None):
    """Record one failed attempt.

    The repeat signature is task + revision + cause. Different tasks (or one
    task whose card changed) sharing a status or an error class are separate
    failures; only the same task, revision and cause in a row is a repeat.
    """
    parts = [str(scope[0]), str(scope[1])] if scope else []
    digest = hashlib.sha256("|".join([*parts, cause]).encode()).hexdigest()
    counters = dict(run.counters)
    counters["no_delivery_turns"] += 1
    counters["repeated_failures"] = counters["repeated_failures"] + 1 if counters.get("last_failure_signature") == digest else 1
    counters["last_failure_signature"] = digest
    run.counters = counters


def _no_delivery(run):
    """A successful execution that did not deliver: a no-delivery turn, never a
    failure. It also ends any repeated-failure streak."""
    counters = dict(run.counters)
    counters["no_delivery_turns"] += 1
    counters["repeated_failures"] = 0
    counters["last_failure_signature"] = None
    run.counters = counters


def _task_scope(run):
    """The task an in-flight attempt belongs to, or None while still selecting."""
    cp = run.checkpoint or {}
    if cp.get("phase") in {"preparing", "dispatching", "observing"} and cp.get("task_ref"):
        return cp["task_ref"], cp.get("task_revision")
    return None


def _ledger_put(run, task_ref, revision, kind, outcome, execution_id=None):
    ledger = dict(run.checkpoint.get("ledger") or {})
    ledger[task_ref] = {"revision": revision, "kind": kind, "outcome": outcome,
                        "execution_id": execution_id, "at": utcnow_naive().isoformat()}
    if len(ledger) > LEDGER_MAX:
        for ref in sorted(ledger, key=lambda r: ledger[r].get("at") or "")[:len(ledger) - LEDGER_MAX]:
            del ledger[ref]
    _checkpoint(run, ledger=ledger)


def _prior_runs(db, scope, owner=None):
    query = db.query(LazyUsageRun).filter(LazyUsageRun.state.in_(TERMINAL))
    if owner is not None:
        query = query.filter(LazyUsageRun.created_by == owner)
    candidates = query.order_by(LazyUsageRun.started_at.desc()).limit(HISTORY_SCAN_ROWS).all()
    return [old for old in candidates if set(old.repo_scope or []) & set(scope)][:HISTORY_RUNS]   # newest first


def _stamp(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _inherited_settlements(db, scope, owner=None):
    """Tombstones (settled or superseded cards) from the recent runs, newest decision wins."""
    settled = {}
    for old in reversed(_prior_runs(db, scope, owner)):
        cp = old.checkpoint or {}
        for key, entry in (cp.get("settled_reviews") or {}).items():
            if isinstance(entry, dict):
                settled[key] = dict(entry)
        for record in cp.get("review_supersessions") or []:
            if isinstance(record, dict) and record.get("task_ref"):
                settled[_task_key(record["task_ref"])] = {"at": record.get("at"), "status": "superseded",
                                                          "basis": "owner_supersession"}
    newest = sorted(settled, key=lambda k: settled[k].get("at") or "")[-SETTLED_MAX:]
    return {key: settled[key] for key in newest}


def _inherited_history(db, scope, owner=None):
    """Carry results and acceptance debt across activations (newest wins).

    Ledger entries only suppress re-dispatch of an unchanged revision inside the reuse
    windows above; they never block a changed card or a due retry.

    Debt is different: each run's final `owed_reviews` is the authoritative state of the
    repositories it covered, so a repository's debt is taken from the NEWEST run that
    covered it, never merged with older runs (merging resurrected debt a newer run had
    already reconciled). A tombstone newer than a debt's `opened_at` also removes it, so
    a card moved ready -> done cannot reappear from any copy.
    """
    prior = _prior_runs(db, scope, owner)
    ledger = {}
    in_scope = lambda ref: isinstance(ref, str) and ref.split(":", 1)[0] in scope
    for old in reversed(prior):
        cp = old.checkpoint or {}
        at = (old.finished_at or old.started_at or utcnow_naive()).isoformat()
        for ref, revision in (cp.get("attempted") or {}).items():
            if in_scope(ref):
                ledger[ref] = {"revision": revision, "kind": None, "outcome": "attempted_legacy",
                               "execution_id": None, "at": at}
        for ref, entry in (cp.get("ledger") or {}).items():
            if in_scope(ref) and isinstance(entry, dict):
                ledger[ref] = dict(entry)
    authority = {}
    for old in prior:                                   # newest first
        for repo in old.repo_scope or []:
            if repo in scope:
                authority.setdefault(repo, old)
    settled = _inherited_settlements(db, scope, owner)
    owed = {}
    for repo, old in authority.items():
        for debt in (old.checkpoint or {}).get("owed_reviews") or []:
            ref = debt.get("task_ref")
            if not (isinstance(ref, str) and ref.split(":", 1)[0] == repo):
                continue
            tomb = settled.get(_task_key(ref))
            opened, closed = _stamp(debt.get("opened_at")), _stamp((tomb or {}).get("at"))
            # A tombstone clears what the owner was asked for; evidence gaps (verification,
            # independent review, finalisation) outlive acceptance until met or superseded.
            if (tomb is not None and not _evidence_gap(debt)
                    and (opened is None or closed is None or closed >= opened)):
                continue
            owed[(_task_key(ref), _debt_gate(debt))] = dict(debt)
        for debt in (old.checkpoint or {}).get("owed_reviews") or []:
            if not debt.get("task_ref") and debt.get("task_id"):
                # Pre-upgrade debts carry only a task_id: keep them rather than lose them silently.
                owed.setdefault((debt["task_id"], _debt_gate(debt)), dict(debt))
    newest = sorted(ledger, key=lambda r: ledger[r].get("at") or "")[-LEDGER_MAX:]
    return {ref: ledger[ref] for ref in newest}, list(owed.values())


# Independent reviewers must come from another model family than the author.
FAMILIES = (("codex", "openai"), ("openai", "openai"), ("gpt", "openai"), ("sol", "openai"), ("terra", "openai"),
            ("luna", "openai"), ("astra", "openai"), ("claude", "anthropic"), ("anthropic", "anthropic"),
            ("opus", "anthropic"), ("sonnet", "anthropic"), ("haiku", "anthropic"), ("fable", "anthropic"),
            ("glm", "zhipu"), ("zai", "zhipu"), ("local", "local"), ("qwen", "local"))
APPROVING = frozenset({"approve", "approved", "pass", "accepted"})


def _family(name):
    """Model family of an alias, or None when it is not recognised (which can never count as
    independent: an unknown reviewer fails closed rather than passing as another family)."""
    text = str(name or "").strip().lower()
    return next((family for key, family in FAMILIES if key in text), None)


def _review_required(meta):
    return "INDEPENDENT" in str(meta.get("verification_route") or "").upper()


def evidence_stages(view, result, acceptance, meta, *, author_provider=None, finalization=None):
    """Four separate pieces of evidence; none stands in for another.

    1. execution:     the worker/provider run finished successfully (it says nothing about quality);
    2. verification:  a deterministic check passed (the router gate). A finalised commit,
                      exit code and non-empty prose are NOT checks;
    3. review:        where the card's route demands it, an approving review by ANOTHER model family;
    4. acceptance:    the owner card is done with acceptance evidence.
    `complete` needs every required stage."""
    result = result or {}
    ok = (view or {}).get("lifecycle_state") == "succeeded" and result.get("ok") is True
    execution = {"status": "succeeded" if ok else "failed", "state": (view or {}).get("lifecycle_state")}
    gate = result.get("deterministic_gate") or result.get("verification_outcome")
    if not ok:
        verification = {"status": "fail", "basis": "execution_failed"}
    elif finalization is not None and finalization.get("scope_violations"):
        verification = {"status": "fail", "basis": "scope_violation",
                        "scope_violations": list(finalization["scope_violations"])}
    elif finalization is not None and not finalization.get("finalized"):
        verification = {"status": "fail", "basis": "finalization_failed"}
    elif finalization is not None and not finalization.get("committed"):
        verification = {"status": "unverified", "basis": "nothing_committed"}
    elif gate == "pass":
        verification = {"status": "pass", "basis": "deterministic_gate"}
    elif gate:
        verification = {"status": "fail", "basis": "deterministic_gate"}
    else:
        verification = {"status": "unverified", "basis": "no_deterministic_check"}
    if not _review_required(meta or {}):
        review = {"status": "not_required"}
    else:
        author = _family(author_provider) if author_provider else None
        review = {"status": "required"}
        for entry in (meta or {}).get("review_evidence") or []:
            if (not isinstance(entry, dict) or str(entry.get("verdict", "")).lower() not in APPROVING
                    or not entry.get("reviewer_provider")):
                continue
            reviewer = _family(entry["reviewer_provider"])
            if author is None or reviewer is None:
                continue
            if reviewer == author:
                review = {"status": "not_independent", "reviewer": entry["reviewer_provider"]}
                continue
            review = {"status": "recorded", "reviewer": entry["reviewer_provider"], "ref": entry.get("ref")}
            break
    accepted = bool(acceptance.get("delivered"))
    stages = {"execution": execution, "verification": verification, "review": review,
              "acceptance": {"status": "accepted" if accepted else "pending",
                             "owner_status": acceptance.get("status")}}
    stages["complete"] = (ok and verification["status"] == "pass" and
                          review["status"] in {"not_required", "recorded"} and accepted)
    return stages


def _reported_usage(result):
    """Worker boundary totals, including children/restarts; never parse model prose."""
    usage = result.get("usage") or (result.get("execution") or {}).get("usage")
    if (not isinstance(usage, dict) or
            any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("paid_calls", "tool_calls"))):
        return None
    return usage


def _reported_usage_dict(*results):
    """The best provider usage report among the candidate results.

    A report that covers both sides of a call wins (largest first); otherwise the largest fragment, so a
    tokenless or smaller fragment in one result can never shadow a better report in another."""
    best, best_rank = None, (-1, -1)
    for result in results:
        usage = (result or {}).get("provider_usage")
        if not isinstance(usage, dict) or not usage:
            continue
        measured, assumed = coordinator.usage_tokens(usage, 0)
        rank = (1 if measured else 0, measured or assumed)
        if rank > best_rank:
            best, best_rank = usage, rank
    return best


def _charge_tokens(run, result, provider_result):
    """Meter tokens once per execution: measured where FULLY reported, else a conservative estimate.

    A fully reported call is always charged as measured, whatever route produced it (the router may escalate
    a read-only task to a paid model). A dispatch that used a paid provider but reported nothing is never
    charged zero, and a partial report (one side of the call only) is charged at least the estimate (Sol
    review of #297, GLM-5.3 review of this fix)."""
    estimate = UNMEASURED_WRITE_TOKEN_ESTIMATE if run.checkpoint.get("dispatch_write") else UNMEASURED_TOKEN_ESTIMATE
    measured, assumed = coordinator.usage_tokens(_reported_usage_dict(provider_result, result), estimate)
    if measured:
        _charge(run, tokens_measured=measured)
    elif run.checkpoint.get("dispatch_provider") and assumed:
        _charge(run, tokens_assumed=assumed)


def _finalize_owned(db, run, execution_id):
    """The backend finalises its own successful write: commit the in-scope worktree changes on
    the leased task branch, with the card's scope and an execution trailer. No controller step.
    Idempotent: a finalised execution answers `already_finalized`."""
    cp = run.checkpoint
    lease = cp.get("lease")
    if not lease:
        return {"finalized": False, "reason": "no lease recorded for this write"}
    scope = cp.get("write_scope") or {}
    if not scope.get("allowed"):
        return {"finalized": False, "reason": "write_scope_missing"}
    _charge(run, tool_calls=1)
    db.commit()
    try:
        outcome = estate_write_lane.finalize_execution(
            execution_id=execution_id, repo_id=lease["repo_id"], host_id=lease["host_id"],
            commit_message=f"task({cp.get('current_task_id')}): {cp.get('task_title') or 'lazyusage delivery'}",
            allowed_paths=scope.get("allowed"), denied_paths=scope.get("denied"))
    except Exception as exc:       # never store exception text: it can carry a task prompt
        outcome = {"finalized": False, "reason": "finalize_raised_" + type(exc).__name__}
    db.expire_all()
    if not outcome.get("finalized"):
        recorded = _execution_finalization(run, execution_id)
        if recorded is not None:
            # Another observer (/stop and the lifecycle tick can both see the same success) finalised it first:
            # report that finalisation, with its persisted commit, not a failure.
            keep = {k: recorded.get(k) for k in ("committed", "adopted", "commit_sha", "parent_sha", "push",
                                                  "scope_violations") if k in recorded}
            return {**keep, "finalized": True, "already_finalized": True}
    return outcome


def _json_record(value):
    """A persisted JSON column value (text or already a dict) as a dict; anything else is empty."""
    if isinstance(value, dict):
        return dict(value)
    try:
        data = json.loads(value) if isinstance(value, (str, bytes)) and value else {}
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _execution_finalization(run, execution_id):
    """The persisted finalisation record of an execution that is already `finalized`, else None."""
    from sqlalchemy.orm import object_session
    session = object_session(run)
    if not execution_id or session is None:
        return None
    row = session.get(EstateExecution, execution_id)
    if row is None:
        return None
    session.refresh(row)
    if row.worktree_resolution != "finalized":
        return None
    return _json_record(row.finalization_json)


def _recover_failed_write(db, run, execution_id):
    """A write whose execution ended without a finalised result (provider refusal, timeout, crash)
    leaves its execution `unresolved`, which makes the lease unreleasable. The backend clears that
    itself through the governed recovery path, which proves writer quiescence and a CLEAN worktree
    first; anything dirty (possible partial work) is refused and stays visible as a debt."""
    row = db.get(EstateExecution, execution_id)
    if row is None:
        return {"recovered": False, "code": "no_execution_row"}
    db.refresh(row)
    if row.worktree_resolution != "unresolved":
        return {"recovered": True, "already": True, "resolution": row.worktree_resolution}
    _charge(run, tool_calls=1)
    db.commit()
    try:
        outcome = estate_write_lane.recover_execution_lease(
            execution_id, lease_id=row.lease_id, host_id=row.host_id, repo_id=row.repo_id,
            branch=row.branch, worktree_path=row.worktree_path)
    except Exception as exc:
        outcome = {"recovered": False, "code": "recover_raised_" + type(exc).__name__}
    db.expire_all()
    return outcome


def _recover_orphan_leases(db, run):
    """Restart recovery: leases a finished activation left behind (an unresolved failed execution, or
    a plain unreleased lease) are cleared before this activation selects work. Only leases created by
    a lazyusage activation that is now terminal are considered; a live activation's lease is never touched."""
    scope = list(run.repo_scope or [])
    candidates = db.query(ParkLease).filter(ParkLease.status == "active", ParkLease.repo_id.in_(scope),
                                            ParkLease.session_id.isnot(None)).all()
    sessions = {lease.session_id for lease in candidates}
    terminal = ({rid for (rid,) in db.query(LazyUsageRun.id).filter(LazyUsageRun.id.in_(sessions),
                                                                    LazyUsageRun.state.in_(TERMINAL))}
                if sessions else set())
    recovered = list(run.checkpoint.get("recovered_leases") or [])
    tried = {entry.get("lease_id") for entry in recovered}
    # Only leases of finished lazyusage activations (never an operator's or a live run's), and each
    # lease at most once per activation: a lease that cannot be recovered (dirty worktree) must not
    # drain this run's budget by being retried on every selection pass.
    leases = [lease for lease in candidates if lease.session_id in terminal and lease.id not in tried]
    for lease in leases[:3]:
        rows = db.query(EstateExecution).filter(EstateExecution.lease_id == lease.id).all()
        if any(r.lifecycle_state in ("accepted", "running", "lost") for r in rows):
            continue
        lease_id, repo_id, host_id = lease.id, lease.repo_id, lease.host_id
        entry = {"lease_id": lease_id, "execution_id": None, "at": utcnow_naive().isoformat()}
        pending = [r for r in rows if r.worktree_resolution == "unresolved"]
        try:
            _charge(run, tool_calls=1)
            db.commit()
            if pending:
                entry["execution_id"] = pending[0].id
                outcome = estate_write_lane.recover_execution_lease(
                    pending[0].id, lease_id=lease_id, host_id=host_id, repo_id=repo_id,
                    branch=pending[0].branch, worktree_path=pending[0].worktree_path)
                entry["recovered"] = bool(outcome.get("recovered"))
                entry["code"] = outcome.get("code")
            else:
                park_lease_ops.release_repo(repo_id, host_id, expected_lease_id=lease_id)
                entry["recovered"] = True
        except Exception as exc:
            entry["recovered"] = False
            entry["code"] = type(exc).__name__
        db.expire_all()
        recovered.append(entry)
    if recovered != list(run.checkpoint.get("recovered_leases") or []):
        _checkpoint(run, recovered_leases=recovered[-20:])


def _quota_debt(run, result):
    if result.get("ok") is True and not result.get("error"):
        return False
    health = result.get("provider_health") or estate_router._provider_outcome(result)
    if health.get("state") not in {"quota_exhausted", "rate_limited"}:
        return False
    cp = run.checkpoint
    # Keep the original provider diagnostic and *stated* retry time. An
    # assumed router cooldown is explicitly distinguished from a reset.
    error = result.get("error") or result.get("execution_error") or result.get("stderr") or health.get("reason")
    debt = {"task_id": cp.get("current_task_id"), "task_ref": cp.get("task_ref"),
            "gate": "verification", "opened_at": utcnow_naive().isoformat(),
            "execution_id": cp.get("in_flight_execution_id"), "provider": result.get("provider"),
            "error": error, "retry_after": health.get("retry_after"),
            "retry_after_assumed": health.get("retry_after_assumed", False),
            "next_action": "retry_dependent_verification_after_provider_recovery"}
    _set_review_debts(run, [*cp.get("owed_reviews", []), debt])
    return True


def verify_attempt(view, checkpoint):
    """Deterministic execution gate; task acceptance remains owner-controlled.

    A model's output alone cannot prove shipment. The worker must have
    passed the router's deterministic gate; owner status is re-read below.
    """
    result = view.get("result") or {}
    gate = result.get("deterministic_gate") or result.get("verification_outcome")
    return (view.get("lifecycle_state") == "succeeded" and result.get("ok") is True
            and gate == "pass")


def reconcile_task_status(checkpoint, view):
    """Re-read the canonical owner card; never move a card based on model prose.

    Writes/finalization/merge stay in the existing owner/lease path. Pending
    acceptance is recorded as debt, so another eligible task may proceed.
    The card's own metadata (verification route, recorded reviews) rides along as `_card`.
    """
    frontier = refresh_frontier([checkpoint["repo_id"]])
    status = _owner_task_status(checkpoint, frontier)
    return {**status, "_card": _card_meta(checkpoint, frontier)}


def _card_meta(checkpoint, frontier):
    """The task card's metadata wherever it now lives (its bucket changes when accepted)."""
    record = next((r for r in frontier["records"] if r["ref"] == checkpoint["task_ref"]), None)
    try:
        if record:
            return _contract(frontier, record)[0]
        root = frontier["roots"].get(checkpoint["repo_id"])
        if root:
            _, _, name = portfolio.parse_ref(checkpoint["task_ref"])
            queue = portfolio.queue_path(root, Path(portfolio.LAYOUT[checkpoint["repo_id"]][0]))
            return portfolio.split_card(portfolio.read_card(queue, "done", name))[0]
    except (OSError, ValueError, KeyError):
        pass
    return {}


def _owner_task_status(checkpoint, frontier):
    record = next((r for r in frontier["records"] if r["ref"] == checkpoint["task_ref"]), None)
    if record:
        return {"delivered": False, "status": record.get("status", "unknown"),
                "reason": "owner acceptance still pending"}
    # A disappeared card might have moved anywhere. Explicitly read the
    # done card through the same safe reader, never infer delivery from absence.
    root = frontier["roots"].get(checkpoint["repo_id"])
    if root:
        _, _, name = portfolio.parse_ref(checkpoint["task_ref"])
        try:
            queue = portfolio.queue_path(root, Path(portfolio.LAYOUT[checkpoint["repo_id"]][0]))
            meta, _ = portfolio.split_card(portfolio.read_card(queue, "done", name))
            status = str(meta.get("status", "")).lower()
            if status in TASK_TERMINAL:
                delivered = status in {"done", "completed"} and bool(meta.get("acceptance_evidence"))
                return {"delivered": delivered, "status": status,
                        "reason": "owner acceptance evidence recorded" if delivered else "owner task is terminal"}
        except (OSError, ValueError):
            pass
    return {"delivered": False, "status": "unknown", "reason": "owner acceptance evidence unavailable"}


def _release_owned_lease(db, run):
    # Preserve the completed attempt's accounting before expiring ORM state
    # or entering the lease helper's separate serialized transaction.
    db.commit()
    lease = run.checkpoint.get("lease")
    if not lease:
        return True
    # Check exact id and ownership before the repo-based public helper. It
    # serializes release and refuses ANY unresolved execution (including lost).
    db.expire_all()
    row = db.get(ParkLease, lease["lease_id"])
    if row is None or row.status == "released":
        _checkpoint(run, lease=None)
        return True
    if row.session_id != run.id or row.host_id != lease["host_id"]:
        _checkpoint(run, lease_release_debt="lease ownership changed")
        return False
    _charge(run, tool_calls=1)
    db.commit()
    try:
        park_lease_ops.release_repo(lease["repo_id"], lease["host_id"], expected_lease_id=lease["lease_id"])
    except (park_lease_ops.LeaseHasUnresolvedExecution, park_lease_ops.NoActiveLease) as exc:
        _checkpoint(run, lease_release_debt=str(exc))
        return False
    _checkpoint(run, lease=None, lease_release_debt=None)
    return True


def _observe(db, run):
    run = _load(db, run.id)
    if run.state in TERMINAL or not run.checkpoint.get("in_flight_execution_id"):
        db.commit()
        return run_dict(run)
    execution_id = run.checkpoint["in_flight_execution_id"]
    # Polling an in-flight execution (and renewing its lease) is controller bookkeeping, not model or
    # tool usage: charging it exhausted the tool-call ceiling in ~40 minutes and cancelled a healthy
    # write (live 2026-11-20). Real actions (dispatch, finalize, recovery, release) and the worker's
    # own reported usage are still charged; max_seconds bounds a stuck observation.
    _save(db, run, phase="observing", next_action="observe", in_flight_execution_id=execution_id)
    view = estate_router.get_estate_execution(execution_id, wait_s=0)
    run = _load(db, run.id)
    if run.checkpoint.get("in_flight_execution_id") != execution_id or run.state in TERMINAL:
        db.commit()
        return run_dict(run)
    if view is None:
        return _park(db, run, "dispatch outcome uncertain; reconcile the reserved execution id", automatic=False)
    if view.get("lifecycle_state") not in EXECUTION_TERMINAL:
        if view.get("lease_id"):
            db.commit()
            park_lease_ops.renew_lease_for_execution(execution_id)
        if view.get("lifecycle_state") == "lost":
            return _park(db, run, "execution lost; recover existing execution before any new dispatch")
        return _save(db, run, next_action="observe")
    result = view.get("result") or {}
    # Advisory router results wrap the raw provider result. Preserve the
    # provider's original diagnostic rather than the router's summary.
    provider_result = result.get("execution") or result
    # Boundary totals include child attempts/restarts when reported. The
    # original dispatch was charged before admission, even if it crashed.
    usage = _reported_usage(result)
    if usage is None:
        started = db.query(EstateExecution.worktree_resolution).filter_by(id=execution_id).populate_existing().scalar()
        if started == "not_started":
            # The worker proved the writer never ran: nothing beyond the dispatch
            # charge can be owed, so there is no child usage to wait for.
            usage = {"paid_calls": 1, "tool_calls": 1}
    accounted = run.checkpoint.get("accounted_execution_id") == execution_id
    if not accounted and usage is not None:
        _charge(run, paid_calls=max(0, usage["paid_calls"] - 1),
                tool_calls=max(0, usage["tool_calls"] - 1))
    parked = _quota_debt(run, provider_result)
    if not accounted:
        if not parked:      # a provider refusal ran nothing: the dispatch is counted, tokens are not assumed
            _charge_tokens(run, result, provider_result)
        # Persist "accounted" together with the charges: a crash during the long finalize below
        # must not charge this execution a second time on re-entry.
        _checkpoint(run, accounted_execution_id=execution_id)
    # A provider refusal before any model/tool execution needs no child
    # accounting. Quota failures park only dependent verification. Other
    # paid outcomes require worker-reported totals; absence is not zero.
    unknown_usage = bool(run.checkpoint.get("dispatch_provider") and usage is None and not parked)
    cp = run.checkpoint
    kind = cp.get("task_kind") or "implementation"
    wrote = bool(cp.get("dispatch_write", kind == "implementation"))
    ran_ok = view.get("lifecycle_state") == "succeeded" and result.get("ok") is True
    finalization = _finalize_owned(db, run, execution_id) if (wrote and ran_ok and not parked) else None
    # An operator stop deliberately preserves an unresolved lease for the controller; only the
    # next activation's orphan sweep (same clean-worktree proof) clears it.
    stopping = run.state in {"stop_requested", "stopping"}
    recovery = _recover_failed_write(db, run, execution_id) if (wrote and not ran_ok and not stopping) else None
    task_ref, revision = run.checkpoint["task_ref"], run.checkpoint.get("task_revision")
    acceptance = reconcile_task_status(run.checkpoint, view)
    card = acceptance.pop("_card", {})
    stg = evidence_stages(view, result, acceptance, card,
                          author_provider=run.checkpoint.get("dispatch_provider") or "local",
                          finalization=finalization)
    passed = stg["verification"]["status"] == "pass" and stg["execution"]["status"] == "succeeded" and not parked
    fin_failed = finalization is not None and not finalization.get("finalized")
    scope_failed = stg["verification"].get("basis") == "scope_violation"
    _reconcile_review_debts(run, task_ref, verified=passed, acceptance=acceptance)
    task_terminal = str(acceptance.get("status", "")).lower() in TASK_TERMINAL
    if not passed and not acceptance["delivered"] and not task_terminal:
        pending = parked or (ran_ok and not fin_failed and not scope_failed)
        acceptance = {"delivered": False, "status": "verification_pending" if pending else "failed"}
    now = utcnow_naive().isoformat()
    base = {"task_id": run.checkpoint["current_task_id"], "task_ref": task_ref, "execution_id": execution_id,
            "provider": None, "error": None, "retry_after": None, "opened_at": now,
            "due": str(card.get("due_date") or "")[:10],
            "author_provider": run.checkpoint.get("dispatch_provider") or "local",
            "commit_sha": (finalization or {}).get("commit_sha")}
    new_debts = []
    review_open = stg["review"]["status"] in {"required", "not_independent"}
    if (ran_ok and wrote and not fin_failed and not scope_failed and not task_terminal
            and not acceptance["delivered"] and stg["verification"]["status"] != "pass"):
        new_debts.append({**base, "gate": "verification", "evidence_gap": True,
                          "next_action": "deterministically verify the existing finalised execution; "
                                         "do not repeat implementation or infer checks from its commit"})
        if review_open:
            new_debts.append({**base, "gate": "independent_review", "evidence_gap": True,
                              "next_action": "independent review by another model family"})
    if passed and not acceptance["delivered"] and not task_terminal:
        if kind == "reconnaissance":
            # A re-adjudication report is not the task's output; it asks for ONE concrete owner step.
            if run.checkpoint.get("dispatch_approval_required"):
                new_debts.append({**base, "gate": "owner_approval",
                                  "scope_sha256": run.checkpoint.get("dispatch_approval_scope"),
                                  "next_action": "owner records an `approval` block in the task card (status: approved, "
                                                 "approved_by, approved_at, scope_sha256 as listed) once the "
                                                 "reconnaissance evidence justifies lifting the approval gate"})
        else:
            new_debts.append({**base, "gate": "owner_acceptance",
                              "next_action": "owner_acceptance_and_required_independent_verification"})
            if review_open:
                new_debts.append({**base, "gate": "independent_review", "evidence_gap": True,
                                  "next_action": "independent review by another model family, recorded as "
                                                 "`review_evidence` on the card"})
    elif acceptance["delivered"] and not stg["complete"]:
        # Accepted, but a required piece of evidence is missing: acceptance cannot stand in for it.
        if stg["verification"]["status"] != "pass":
            new_debts.append({**base, "gate": "verification", "evidence_gap": True,
                              "next_action": "deterministic verification evidence for the accepted work"})
        if review_open:
            new_debts.append({**base, "gate": "independent_review", "evidence_gap": True,
                              "next_action": "independent review by another model family"})
    rec_failed = recovery is not None and not recovery.get("recovered")
    if rec_failed:
        new_debts.append({**base, "gate": "recovery", "evidence_gap": True,
                          "error": str(recovery.get("code") or recovery.get("reason") or "recovery refused")[:300],
                          "next_action": "inspect the leased worktree, then recover or finalize this execution "
                                         "through the governed controller path"})
    if fin_failed:
        new_debts.append({**base, "gate": "finalization", "evidence_gap": True,
                          "error": str(finalization.get("reason") or "finalization failed")[:300],
                          "next_action": "recover or finalize this execution through the governed controller path"})
    if new_debts:
        _set_review_debts(run, [*run.checkpoint.get("owed_reviews", []), *new_debts])
    delivered_clean = acceptance["delivered"] and stg["complete"]
    if delivered_clean:
        outcome = "delivered"
    elif acceptance["delivered"]:
        outcome = "accepted_unproven"
    elif parked:
        outcome = "quota_parked"
    elif fin_failed:
        outcome = "finalize_failed"
    elif scope_failed:
        outcome = "scope_violation"
    elif passed:
        outcome = ("awaiting_approval" if kind == "reconnaissance" and run.checkpoint.get("dispatch_approval_required")
                   else "delivered_pending_acceptance" if wrote else "advisory_complete")
    elif stg["execution"]["status"] == "succeeded":
        outcome = "unverified"
    elif stopping and any(marker in " ".join(str(v or "") for v in (
            result.get("error"), provider_result.get("error"), view.get("error"))).lower()
                          for marker in ("cancel", "fenced", "never ran")):
        # Our own stop (budget or operator) cancelled or fenced the writer: that says nothing about the task.
        # A genuine failure that merely coincides with a pending stop stays a failure, so the
        # repeat-failure guard still binds on a task that fails deterministically.
        outcome = "interrupted"
    else:
        outcome = "failed"
    if delivered_clean:
        run.counters = {**run.counters, "no_delivery_turns": 0, "repeated_failures": 0,
                        "last_failure_signature": None}
    elif not accounted:
        if outcome == "interrupted":
            pass
        elif outcome in {"advisory_complete", "delivered_pending_acceptance", "awaiting_approval", "unverified",
                         "accepted_unproven"}:
            # Executed but not accepted: not a failure. It only spends a no-delivery turn.
            _no_delivery(run)
        else:
            cause = ("finalize_failed" if fin_failed else "scope_violation" if scope_failed else
                     str(result.get("error") or provider_result.get("error_code") or "verification_failed"))
            _failure(run, cause, scope=(task_ref, revision))
    _ledger_put(run, task_ref, revision, kind, outcome, execution_id)
    stages_map = dict(run.checkpoint.get("stages") or {})
    stages_map[task_ref] = stg
    if len(stages_map) > STAGES_MAX:
        for ref in list(stages_map)[:len(stages_map) - STAGES_MAX]:
            del stages_map[ref]
    attempted = dict(run.checkpoint.get("attempted", {}))
    attempted[task_ref] = revision
    _checkpoint(run, attempted=attempted, last_execution_id=execution_id,
                in_flight_execution_id=None, phase="idle", acceptance=acceptance, stages=stages_map,
                accounted_execution_id=execution_id, next_action="refresh_frontier")
    if unknown_usage:
        _checkpoint(run, usage_accounting_pending=execution_id,
                    usage_accounting_reason="worker did not report child paid/tool totals; further dispatch fenced")
    _release_owned_lease(db, run)
    if run.state in {"stop_requested", "stopping"}:
        return _finish(db, run, run.checkpoint.get("pending_terminal", "stopped"),
                       run.checkpoint.get("budget_reason", "operator_stop"))
    reason = _budget_reason(run)
    if reason:
        return _finish(db, run, "budget_exhausted", reason)
    if fin_failed or rec_failed:
        return _park(db, run, ("finalization" if fin_failed else "recovery") + " failed for execution " + execution_id +
                     "; resolve it through the governed finalize/recover path", automatic=False)
    if unknown_usage:
        return _park(db, run, "no qualified metered continuation until existing execution usage is available")
    return _save(db, run)


def _stop(db, run):
    run = _load(db, run.id)
    if run.state in TERMINAL:
        db.commit()
        return run_dict(run)
    cp = run.checkpoint
    execution_id = cp.get("in_flight_execution_id")
    if execution_id:
        run.state = "stopping"
        _save(db, run, next_action="cancel_and_observe")
        row = db.get(EstateExecution, execution_id)
        db.commit()
        if row is None:
            # Admission's run-row guard is serialized with the already
            # committed stop. A later admission cannot pass it. No worker
            # start is possible without its EstateExecution row.
            _checkpoint(run, in_flight_execution_id=None, phase="idle")
            _release_owned_lease(db, run)
            return _finish(db, run, run.checkpoint.get("pending_terminal", "stopped"),
                           run.checkpoint.get("budget_reason", "operator_stop"))
        if row is not None and row.worker_handle_json is not None:
            try:
                # Fence a not-yet-started spool first. This closes the gap
                # between committed admission and start: cancel alone cannot
                # fence an execution the worker has not seen yet.
                _charge(run, tool_calls=1)
                _save(db, run)
                response = call_worker(row.host_id, "status", {"execution_id": execution_id, "fence": True}, deadline_s=10)
                view = response.get("result") or {}
                estate_write_lane._apply_view(execution_id, view, fenced=True)
                if view.get("quiescent") is not True:
                    _charge(run, tool_calls=1)
                    _save(db, run)
                    call_worker(row.host_id, "cancel", {"execution_id": execution_id}, deadline_s=10)
            except WorkerTransportError as exc:
                return _save(db, run, cancellation_error=str(exc), next_action="cancel_and_observe")
        # Advisory calls have no durable worker spool. Never kill a backend
        # PID or manufacture quiescence; observe the existing bounded call.
        return _observe(db, run)
    if cp.get("phase") in {"selecting", "preparing"}:
        # The admitted planning call may still return a prepared lease. Its
        # owner sees stop_requested before dispatch and records/releases it.
        # On restart, recover the existing session's reservation first.
        if cp.get("claim_until", "9999") > utcnow_naive().isoformat():
            return _save(db, run, next_action="await_preparation_quiescence")
        if not _recover_preparation(db, run):
            return _save(db, run, next_action="resolve_preparing_reservation")
    _release_owned_lease(db, run)
    return _finish(db, run, run.checkpoint.get("pending_terminal", "stopped"),
                   run.checkpoint.get("budget_reason", "operator_stop"))


def _admission_guard(run_id):
    def guard(db, execution_id):
        run = db.query(LazyUsageRun).filter_by(id=run_id).with_for_update().one()
        return (run.state == "running" and not _budget_reason(run, reserved=True)
                and run.checkpoint.get("in_flight_execution_id") == execution_id)
    return guard


def _recover_preparation(db, run):
    lease = db.query(ParkLease).filter(ParkLease.session_id == run.id,
                                     ParkLease.status.in_(("preparing", "active"))).first()
    if lease:
        lease_id, status = lease.id, lease.status
        _save(db, run, lease={"lease_id": lease.id, "repo_id": lease.repo_id, "host_id": lease.host_id})
        if status == "preparing":
            outcome = park_lease_ops.resolve_preparing_reservation(lease_id)
            if not outcome.get("resolved"):
                return False
        _release_owned_lease(db, run)
    _checkpoint(run, phase="idle")
    return True


def advance(db, run_id):
    """One governed attempt, or observation/reconciliation of the existing one.

    The committed phase is a dispatch fence across processes. Interrupted
    planning is parked, and interrupted dispatch is always observed, never
    replayed. Worker admission provides the same-lease backstop.
    """
    run = _load(db, run_id)
    cp = run.checkpoint
    if run.state in TERMINAL:
        db.commit()
        return run_dict(run)
    if run.state in {"stop_requested", "stopping"}:
        db.commit()
        return _stop(db, run)
    if cp.get("in_flight_execution_id"):
        reason = _budget_reason(run, reserved=True)
        if reason:
            run.state = "stop_requested"
            _save(db, run, pending_terminal="budget_exhausted", budget_reason=reason)
            return _stop(db, run)
        db.commit()
        return _observe(db, run)
    reason = _budget_reason(run)
    if reason:
        return _finish(db, run, "budget_exhausted", reason)
    if run.state == "paused":
        due = cp.get("recheck_at")
        if not due or utcnow_naive().isoformat() < due:
            db.commit()
            return run_dict(run)
    if cp.get("usage_accounting_pending"):
        execution = db.get(EstateExecution, cp["usage_accounting_pending"])
        usage = _reported_usage(json.loads(execution.result_json or "{}")) if execution else None
        if usage is None:
            return _park(db, run, "existing execution child usage remains unknown; dispatch fenced")
        _charge(run, paid_calls=max(0, usage["paid_calls"] - 1), tool_calls=max(0, usage["tool_calls"] - 1))
        _checkpoint(run, usage_accounting_pending=None, usage_accounting_reason=None)
        reason = _budget_reason(run)
        if reason:
            return _finish(db, run, "budget_exhausted", reason)
    if cp.get("phase") in {"selecting", "preparing", "dispatching"}:
        # A competing advance, or interrupted pre-dispatch work. It cannot
        # safely issue anything while the owner may still be alive.
        due = cp.get("claim_until")
        if due and utcnow_naive().isoformat() >= due:
            _recover_preparation(db, run)
            return _park(db, run, "interrupted planning; reconcile before resume", automatic=False)
        db.commit()
        return run_dict(run)
    run.state = "running"
    _charge(run, tool_calls=1)
    _save(db, run, phase="selecting", next_action="refresh_frontier",
          claim_until=(utcnow_naive() + timedelta(seconds=RECHECK_SECONDS)).isoformat())
    try:
        _recover_orphan_leases(db, run)
        frontier = refresh_frontier(run.repo_scope)
        digest = _digest(frontier)
        _save(db, run, last_frontier_digest=digest)
        # Opt-in bounded cognitive step: one advisory plan per unchanged
        # frontier state, charged to this run's budgets, fail-closed.
        # Feasibility evidence is only computed when a coordinator call may
        # happen, so a plain activation pays nothing extra for it.
        evidence = (candidate_evidence(frontier, run)
                    if (run.checkpoint.get("coordinator") or {}).get("enabled") else None)
        plan = coordinator.coordinator_step(db, run, frontier, digest, evidence)
        chosen = _choose(frontier, run, plan)
        # Selection records skipped reasons, one-off handoff entries and reconciled
        # owed reviews on the checkpoint. Only that evidence is carried across a reload:
        # writing the whole pre-reload snapshot back would overwrite a concurrent
        # operator pause/stop that committed while selection ran (both the dispatch and
        # the nothing-eligible paths below start from the freshly locked row).
        evidence_cp = {key: run.checkpoint[key] for key in ("skipped", "ledger", "owed_reviews")
                       if key in run.checkpoint}
        run = _load(db, run.id)
        if run.state != "running":
            return _save(db, run, phase="idle", **evidence_cp)
        _checkpoint(run, **evidence_cp)
        if chosen is None:
            if not frontier["records"] and not frontier["unavailable"] and not frontier["warnings"] and not run.checkpoint.get("owed_reviews"):
                return _finish(db, run, "completed", "authorised_work_exhausted")
            _charge(run, no_delivery_turns=1)
            _checkpoint(run, phase="idle")
            reason = _budget_reason(run)
            return _finish(db, run, "budget_exhausted", reason) if reason else _park(
                db, run, "no eligible frontier; recheck on frontier, authority or provider change")
        record, meta, task, write, host, provider, revision, kind, scope = chosen
        # The coordinator's decomposition/next_action stay checkpointed as
        # untrusted advisory evidence only (Sol review P1: never inject
        # model-generated instruction text into a worker objective).
        # Only criterion headings/identifiers belong in checkpoints, never
        # arbitrary body text. The full contract remains in its owner file.
        _save(db, run, current_task_id=str(meta.get("task_id") or record["ref"]),
              task_ref=record["ref"], repo_id=record["repo_id"],
              task_revision=revision, task_kind=kind,
              dispatch_provider=provider, dispatch_write=write, write_scope=scope,
              task_title=str(meta.get("title") or "")[:60],
              dispatch_approval_scope=approval_scope(meta) if kind == "reconnaissance" else None,
              dispatch_review_required=_review_required(meta),
              dispatch_approval_required=meta.get("approval_required") is True,
              acceptance_criteria={"contract_ref": record["ref"], "verification_route": meta.get("verification_route")},
              phase="preparing", next_action="preflight")
        if write:
            # This explicit activation, not preflight/run_task, owns the
            # acquisition. The deterministic branch/session also identifies
            # a preparation interrupted before its response was checkpointed.
            branch = "task/lazyusage-" + run.id + "-" + hashlib.sha256(record["ref"].encode()).hexdigest()[:10]
            _charge(run, tool_calls=1)
            db.commit()
            lease = park_lease_ops.park_with_worktree(record["repo_id"], host, branch, session_id=run.id)
            run = _load(db, run.id)
            _save(db, run, lease={k: lease[k] for k in ("lease_id", "repo_id", "host_id")})
            if run.state != "running":
                return _stop(db, run) if run.state in {"stop_requested", "stopping"} else _save(db, run, phase="idle")
        _charge(run, tool_calls=1)
        _save(db, run, next_action="delegation_preflight")
        preflight = delegation_preflight([{
            "task_class": task["task_class"], "repo": task["repo"], "objective": task["objective"],
            "capabilities": task["requirements"]["capabilities"], "allow_paid_escalation": True,
            # This loop already owns the authoritative write classification
            # (contract execution_mode/approval metadata, lease acquired above
            # for write tasks); state it so the preflight text heuristic on
            # the embedded card body cannot demand a write lane for a
            # read-only reconnaissance unit (2026-11-16 live finding).
            # write_classified is a trusted in-process key the HTTP envelope
            # never sets (envelope write defaults False).
            "write_classified": True, "requires_repo_write": write,
            **({"paid_provider": provider} if provider is not None else {})}])
        if not preflight.get("ok"):
            _failure(run, "preflight_unavailable", scope=(record["ref"], revision))
            _checkpoint(run, phase="idle")
            _release_owned_lease(db, run)
            return _park(db, run, "delegation preflight has no qualified route")
        run = _load(db, run.id)
        reason = _budget_reason(run)
        if not reason and _token_headroom_exhausted(run, provider, write):
            reason = "max_tokens"       # the conservative estimate of this dispatch would cross the ceiling
        if reason:
            _release_owned_lease(db, run)
            return _finish(db, run, "budget_exhausted", reason)
        if run.state != "running":
            return _save(db, run, phase="idle")
        if provider and not estate_router.provider_allows_dispatch(provider).get("allowed"):
            _checkpoint(run, phase="idle")
            _release_owned_lease(db, run)
            return _park(db, run, "provider unavailable before dispatch")
        execution_id = str(uuid.uuid4())
        # Charge BEFORE dispatch, preserving spent calls across crashes.
        _charge(run, tool_calls=1, paid_calls=int(provider is not None))
        _save(db, run, phase="dispatching", in_flight_execution_id=execution_id, next_action="observe")
        if write:
            result = estate_router.execute_write_via_worker(
                task["objective"], repo_id=task["repo"], host_id=host,
                execution_id=execution_id, admission_guard=_admission_guard(run.id), wait_timeout=0,
                deadline_at=run.started_at + timedelta(seconds=run.budgets["max_seconds"]),
                timeout=max(1, min(1800, run.budgets["max_seconds"] -
                                  (utcnow_naive() - run.started_at).total_seconds())))
            run = _load(db, run.id)
            if run.state in TERMINAL or run.checkpoint.get("in_flight_execution_id") != execution_id:
                # A concurrent stop/observer may already have settled this
                # exact admission while execute_write was returning.
                db.commit()
                return run_dict(run)
            actual_id = result.get("execution_id")
            if actual_id:
                return _save(db, run, phase="observing", in_flight_execution_id=actual_id)
            # Positive admission refusal: the reserved id was never launched.
            _quota_debt(run, result)
            _failure(run, str(result.get("error_code") or "admission_refused"),
                     scope=(record["ref"], revision))
            _checkpoint(run, in_flight_execution_id=None, phase="idle")
            _release_owned_lease(db, run)
            return _save(db, run)
        # Read-only execution still goes through the canonical router. The
        # durable envelope fences replay if this synchronous call loses its
        # response. Reconciliation never dispatches this envelope again.
        run = _load(db, run.id)
        if run.state != "running":
            return _save(db, run, in_flight_execution_id=None, phase="idle")
        db.add(EstateExecution(id=execution_id, objective=record["ref"], executor="lazyusage-advisory",
                               provider=provider or "local", repo_id=task["repo"], host_id=host,
                               lifecycle_state="running", worker_pid=os.getpid(), worktree_resolution="legacy_closed"))
        db.commit()
        task["_activation_deadline"] = (run.started_at.replace(tzinfo=timezone.utc) +
                                        timedelta(seconds=run.budgets["max_seconds"])).isoformat()
        result = estate_router.run_task(task)
        if _reported_usage(result) is None:
            # run_task is ONE synchronous advisory dispatch: it cannot restart or spawn a
            # second dispatch, so the dispatch total is what this loop charged before
            # launch. paid_calls counts DISPATCHES (as for a write), not the model turns
            # inside one CLI invocation. A durable worker boundary, which can restart or
            # spawn children, keeps the stricter rule: absence there is unknown, not zero.
            result = {**result, "usage": {"paid_calls": int(provider is not None), "tool_calls": 1}}
        row = db.get(EstateExecution, execution_id)
        row.lifecycle_state = "succeeded" if result.get("ok") and result.get("executed") else "failed"
        row.result_json = json.dumps(result)
        row.finished_at = utcnow_naive()
        db.commit()
        return _observe(db, run)
    except Exception as exc:
        db.rollback()
        run = _load(db, run_id)
        # Never store exception text: it can contain a task prompt or secrets.
        # Provider diagnostics are recorded only by the explicit quota path.
        _failure(run, type(exc).__name__, scope=_task_scope(run))
        if run.checkpoint.get("in_flight_execution_id"):
            return _park(db, run, "dispatch observation required after " + type(exc).__name__, automatic=False)
        if run.checkpoint.get("phase") == "preparing":
            _recover_preparation(db, run)
        _checkpoint(run, phase="idle")
        _release_owned_lease(db, run)
        return _park(db, run, "attempt interrupted: " + type(exc).__name__)


def supersede_review_debts(db, owner, run_id, task_refs, *, reason, evidence):
    """Retire review debts that rest on unusable evidence (e.g. fabricated local-model output).

    Only the owner's explicit, evidenced decision may do this; the route requires the execute
    scope. The debt is not deleted silently: it is moved to `review_supersessions` with the
    principal, reason and evidence, which also becomes a tombstone for every later activation.
    It never marks a task delivered."""
    if not isinstance(owner, str) or not owner.strip():
        raise RunError(422, "owner is required")
    if not isinstance(reason, str) or not reason.strip():
        raise RunError(422, "a reason is required")
    if (not isinstance(evidence, list) or not evidence
            or any(not isinstance(item, str) or not item.strip() for item in evidence)):
        raise RunError(422, "evidence references are required")
    if not isinstance(task_refs, list) or not task_refs or any(not isinstance(r, str) for r in task_refs):
        raise RunError(422, "task_refs must be a non-empty list")
    run = _load(db, run_id)
    if run.state not in TERMINAL:
        db.rollback()
        raise RunError(409, "only a finished activation's debts can be superseded")
    owed = list((run.checkpoint or {}).get("owed_reviews") or [])
    missing = [ref for ref in task_refs if not any(d.get("task_ref") == ref for d in owed)]
    if missing:
        db.rollback()
        raise RunError(404, "no such owed review in this run: " + ", ".join(missing))
    now = utcnow_naive().isoformat()
    records = list((run.checkpoint or {}).get("review_supersessions") or [])
    for debt in owed:
        if debt.get("task_ref") in task_refs:
            records.append({"task_ref": debt["task_ref"], "gate": _debt_gate(debt), "original": dict(debt),
                            "reason": reason.strip(), "evidence": [e.strip() for e in evidence],
                            "by": owner, "at": now})
    _checkpoint(run, owed_reviews=[d for d in owed if d.get("task_ref") not in task_refs],
                review_supersessions=records)
    db.commit()
    return {"run_id": run.id, "superseded": sorted(set(task_refs)),
            "remaining": len(run.checkpoint["owed_reviews"])}


def all_owed_reviews(db, owner=None):
    """Every repository's pending debts, for the owner's decision view (debts are per repository, not per run).

    Terminal runs supply each repository's newest debts (`_inherited_history`); the live run, if any, is the
    truth for the repositories in its own scope, so debts it settled cannot return from an older copy."""
    live_query = db.query(LazyUsageRun).filter(LazyUsageRun.state.notin_(TERMINAL))
    if owner is not None:                       # a read for one owner never shows another owner's debts
        live_query = live_query.filter(LazyUsageRun.created_by == owner)
    live = live_query.first()
    live_scope = set(live.repo_scope or []) if live else set()

    def key(debt):
        ref = debt.get("task_ref")
        # a pre-upgrade debt has only a task_id: keep each one distinct, never collapse them
        return (_task_key(ref) if ref else "id:" + str(debt.get("task_id")), _debt_gate(debt))

    merged = {}
    for repo in portfolio.LAYOUT:
        if repo in live_scope:
            continue
        # per repository, so a quiet repo is never pushed out by the history cap of busier ones
        _, owed = _inherited_history(db, [repo], owner)
        for debt in owed:
            ref = debt.get("task_ref")
            if ref and str(ref).split(":", 1)[0] != repo:
                continue
            merged[key(debt)] = debt
    if live:
        for debt in (live.checkpoint or {}).get("owed_reviews") or []:
            merged[key(debt)] = debt
    return list(merged.values())


def decision_context(debt, frontier):
    """The few structured card fields that let the owner decide: what the task is, its type, priority, risk, its
    write scope and how many paths are protected. A fixed allow-list: never the card body, a runtime error,
    model output or any other front-matter field. Empty when the card cannot be read."""
    ref = debt.get("task_ref") if isinstance(debt, dict) else None
    if not isinstance(ref, str) or ":" not in ref:
        return {}
    meta = _card_meta({"task_ref": ref, "repo_id": ref.split(":", 1)[0]}, frontier)
    if not meta:
        return {}
    kind = ", ".join(str(meta[k]) for k in ("task_type", "execution_mode") if meta.get(k))
    recorded = str(debt.get("scope_sha256") or "")
    changed = bool(debt.get("gate") == "owner_approval" and recorded and approval_scope(meta) != recorded)
    notes = meta.get("notes")
    denied = [p for p in (meta.get("denied_paths") or []) if isinstance(p, str)]
    return {"title": meta.get("title") if isinstance(meta.get("title"), str) else "",
            "what": notes if isinstance(notes, str) else "", "kind": kind,
            "priority": str(meta.get("priority") or ""), "risk": str(meta.get("risk_level") or ""),
            "write_paths": _allowed_paths(meta), "denied_count": len(denied), "scope_changed": changed,
            "result_path": meta.get("result_path") if isinstance(meta.get("result_path"), str) else "",
            "outputs_count": len([o for o in (meta.get("outputs") or []) if isinstance(o, str)])}


def _context_provider():
    """A decision-context function that reads the task cards lazily, once, and only if a card is actually shown."""
    cache = {}

    def provide(debt):
        if "frontier" not in cache:
            cache["frontier"] = refresh_frontier(list(portfolio.LAYOUT))
        return decision_context(debt, cache["frontier"])
    return provide


def _offer_owner_decisions(db):
    """Best-effort: send the owner's pending decision cards (approvals, acceptances) to the private channel,
    each once, at most hourly. It can never affect the run: any failure is swallowed."""
    try:
        from src import owner_decisions
        owner_decisions.notify(all_owed_reviews(db), context=_context_provider())
    except Exception:
        log.warning("owner decision notification failed")


def lifecycle_tick():
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        # No row means no calls, no frontier scan and no paid work.
        run = db.query(LazyUsageRun).filter(LazyUsageRun.state.notin_(TERMINAL)).first()
        if run is None:
            return None
        run_id = run.id
        db.commit()
        estate_router.reconcile_stale_estate_executions(db, EstateExecution)
        db.commit()
        view = advance(db, run_id)
        _offer_owner_decisions(db)
        return view
    finally:
        db.close()


async def lazy_usage_lifecycle_loop():
    """Observer by default; only an explicit persisted activation permits work."""
    while True:
        try:
            await asyncio.to_thread(lifecycle_tick)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("lazy usage observation failed; retry on next bounded tick")
        await asyncio.sleep(LOOP_SECONDS)

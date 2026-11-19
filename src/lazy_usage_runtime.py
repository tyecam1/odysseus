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
            "max_no_delivery_turns": 8, "max_repeat_failures": 3}
TERMINAL = frozenset({"completed", "stopped", "failed", "budget_exhausted"})
EXECUTION_TERMINAL = frozenset({"succeeded", "failed", "timed_out", "interrupted"})
TASK_TERMINAL = frozenset({"done", "completed", "rejected", "superseded", "closed", "cancelled", "canceled"})
RECHECK_SECONDS = 300
LOOP_SECONDS = 25
# Execution classes. Only an implementation can deliver; every other class
# produces advisory evidence or a human handoff that never counts as delivery.
KINDS = ("implementation", "reconnaissance", "evidence", "review", "protected_handoff")
DELIVERING_KINDS = frozenset({"implementation"})
HANDOFF_TASK_TYPES = frozenset({"human-approval", "human-handoff", "handoff"})
EVIDENCE_TASK_TYPES = frozenset({"evidence-synthesis", "evidence-gathering", "evidence"})
READ_ONLY_MODES = frozenset({"read-only", "read_only", "advisory"})
# Cross-activation memory. An unchanged revision is not re-dispatched while a
# prior result is fresh; both windows expire, so a retry is never blocked forever.
ADVISORY_REUSE_SECONDS = 86400
FAILURE_RETRY_SECONDS = 3600
LEDGER_MAX = 200
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


def run_dict(run):
    cp = dict(run.checkpoint or {})
    elapsed = max(0, ((run.finished_at or utcnow_naive()) - run.started_at).total_seconds()) if run.started_at else 0
    return {"id": run.id, "state": run.state, "created_by": run.created_by,
            "initializer": run.initializer, "repo_scope": run.repo_scope,
            "budgets": run.budgets, "counters": {**run.counters, "elapsed_seconds": elapsed},
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
    ledger, owed = _inherited_history(db, scope)
    run = LazyUsageRun(id=str(uuid.uuid4()), state="requested", created_by=owner,
                       initializer=INITIALIZER, repo_scope=scope,
                       budgets=budgets, started_at=utcnow_naive(),
                       counters={"paid_calls": 0, "tool_calls": 0, "no_delivery_turns": 0,
                                 "repeated_failures": 0, "last_failure_signature": None},
                       checkpoint={"phase": "idle", "in_flight_execution_id": None,
                                   "owed_reviews": owed, "ledger": ledger,
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
    return None


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
    if meta.get("approval_required") is True:
        return "reconnaissance"
    if mode in READ_ONLY_MODES or task_type in EVIDENCE_TASK_TYPES:
        return "evidence"
    return "implementation"


def _task(record, meta, body, kind=None):
    kind = kind or _classify(record, meta)
    assessment = kind == "reconnaissance"
    write = kind == "implementation"
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


def _debt_gate(debt):
    # Checkpoints predating explicit gates used an error to identify quota debt.
    return debt.get("gate") or ("verification" if debt.get("error") else "owner_acceptance")


def _set_review_debts(run, debts):
    newest = {}
    for debt in debts:
        newest[(debt.get("task_ref") or debt.get("task_id"), _debt_gate(debt))] = debt
    _checkpoint(run, owed_reviews=list(newest.values()))


def _reconcile_review_debts(run, task_ref, *, verified=False, acceptance=None):
    acceptance = acceptance or {}
    settled = acceptance.get("delivered") or str(acceptance.get("status", "")).lower() in TASK_TERMINAL
    _set_review_debts(run, [debt for debt in run.checkpoint.get("owed_reviews", [])
                           if debt.get("task_ref") != task_ref or
                           not (settled or verified and _debt_gate(debt) == "verification")])


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
    debts = [d for d in cp.get("owed_reviews", []) if d.get("task_ref") == ref]
    retry_due = False
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
    if outcome == "failed" and age < FAILURE_RETRY_SECONDS:
        return "failure_backoff"
    if outcome == "quota_parked" and not retry_due and (
            any(d.get("error") and d.get("retry_after") for d in debts) or age < FAILURE_RETRY_SECONDS):
        # Blocked until the provider's *stated* reset; with no stated reset (the
        # debt was reconciled away) it is only a bounded backoff, never permanent.
        return "quota_retry_pending"
    if outcome == "delivered_pending_acceptance" and any(_debt_gate(d) == "owner_acceptance" for d in debts):
        return "awaiting_owner_acceptance"
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
    verdict = {"ref": record["ref"], "kind": kind, "delivers": kind in DELIVERING_KINDS, "ok": False,
               "blocker": None, "revision": revision, "meta": meta, "body": body, "title": meta.get("title")}
    write = kind == "implementation"
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
                    verdict["provider"], verdict["revision"], verdict["kind"])
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


def _inherited_history(db, scope):
    """Carry results and acceptance debt across activations (newest wins).

    Entries only suppress re-dispatch of an unchanged revision inside the
    reuse windows above; they never block a changed card or a due retry.
    """
    candidates = db.query(LazyUsageRun).filter(LazyUsageRun.state.in_(TERMINAL)).order_by(
        LazyUsageRun.started_at.desc()).limit(HISTORY_SCAN_ROWS).all()
    prior = [old for old in candidates if set(old.repo_scope or []) & set(scope)][:HISTORY_RUNS]
    ledger, owed = {}, {}
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
        for debt in cp.get("owed_reviews") or []:
            if in_scope(debt.get("task_ref")):
                owed[(debt.get("task_ref"), _debt_gate(debt))] = dict(debt)
    newest = sorted(ledger, key=lambda r: ledger[r].get("at") or "")[-LEDGER_MAX:]
    return {ref: ledger[ref] for ref in newest}, list(owed.values())


def _reported_usage(result):
    """Worker boundary totals, including children/restarts; never parse model prose."""
    usage = result.get("usage") or (result.get("execution") or {}).get("usage")
    if (not isinstance(usage, dict) or
            any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("paid_calls", "tool_calls"))):
        return None
    return usage


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
            "gate": "verification",
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
            and (gate == "pass" or (result.get("exit_code") == 0 and bool(result.get("output", "").strip()))))


def reconcile_task_status(checkpoint, view):
    """Re-read the canonical owner card; never move a card based on model prose.

    Writes/finalization/merge stay in the existing owner/lease path. Pending
    acceptance is recorded as debt, so another eligible task may proceed.
    """
    frontier = refresh_frontier([checkpoint["repo_id"]])
    return _owner_task_status(checkpoint, frontier)


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
    _charge(run, tool_calls=1)
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
            _charge(run, tool_calls=1)
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
    # A provider refusal before any model/tool execution needs no child
    # accounting. Quota failures park only dependent verification. Other
    # paid outcomes require worker-reported totals; absence is not zero.
    unknown_usage = bool(run.checkpoint.get("dispatch_provider") and usage is None and not parked)
    passed = verify_attempt(view, run.checkpoint) and not parked
    acceptance = reconcile_task_status(run.checkpoint, view)
    _reconcile_review_debts(run, run.checkpoint["task_ref"], verified=passed, acceptance=acceptance)
    task_terminal = str(acceptance.get("status", "")).lower() in TASK_TERMINAL
    if not passed and not acceptance["delivered"] and not task_terminal:
        acceptance = {"delivered": False, "status": "verification_pending" if parked else "failed"}
    kind = run.checkpoint.get("task_kind") or "implementation"
    task_ref, revision = run.checkpoint["task_ref"], run.checkpoint.get("task_revision")
    # A re-adjudication report is not the task's output: nothing is owed on it.
    if passed and kind != "reconnaissance" and not acceptance["delivered"] and not task_terminal:
        owed = list(run.checkpoint.get("owed_reviews", []))
        debt = {"task_id": run.checkpoint["current_task_id"], "task_ref": task_ref,
                "gate": "owner_acceptance",
                "execution_id": execution_id, "provider": None, "error": None, "retry_after": None,
                "next_action": "owner_acceptance_and_required_independent_verification"}
        _set_review_debts(run, owed + [debt])
    if acceptance["delivered"]:
        run.counters = {**run.counters, "no_delivery_turns": 0, "repeated_failures": 0,
                        "last_failure_signature": None}
        outcome = "delivered"
    elif parked:
        outcome = "quota_parked"
    elif passed:
        outcome = "delivered_pending_acceptance" if kind in DELIVERING_KINDS else "advisory_complete"
    else:
        outcome = "failed"
    if not accounted and not acceptance["delivered"]:
        if passed:
            # Executed and verified but not accepted: not a failure. Advisory
            # classes can never deliver, so this only spends a no-delivery turn.
            _no_delivery(run)
        else:
            cause = str(result.get("error") or provider_result.get("error_code") or "verification_failed")
            _failure(run, cause, scope=(task_ref, revision))
    _ledger_put(run, task_ref, revision, kind, outcome, execution_id)
    attempted = dict(run.checkpoint.get("attempted", {}))
    attempted[task_ref] = revision
    _checkpoint(run, attempted=attempted, last_execution_id=execution_id,
                in_flight_execution_id=None, phase="idle", acceptance=acceptance,
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
        record, meta, task, write, host, provider, revision, kind = chosen
        # The coordinator's decomposition/next_action stay checkpointed as
        # untrusted advisory evidence only (Sol review P1: never inject
        # model-generated instruction text into a worker objective).
        # Only criterion headings/identifiers belong in checkpoints, never
        # arbitrary body text. The full contract remains in its owner file.
        _save(db, run, current_task_id=str(meta.get("task_id") or record["ref"]),
              task_ref=record["ref"], repo_id=record["repo_id"],
              task_revision=revision, task_kind=kind,
              dispatch_provider=provider,
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
        return advance(db, run_id)
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

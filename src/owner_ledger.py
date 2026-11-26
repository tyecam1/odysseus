"""The owner decision ledger: who decided what about which exact card scope, durably and revocably.

A task card with `approval_required: true` used to be lifted only by the owner hand-editing an `approval` block into
the card. That does not scale to a phone, and it cannot record an advisor model's delegated decision. The ledger holds
those decisions beside the run records instead: one row per decision, owner-scoped, bound to the card's task id and
the digest of exactly what it covers (`approval_scope`), never to prose or a title. A change to the covered scope makes
the row irrelevant, a later decision for the same card supersedes an earlier one, and any decision can be revoked.

Who may write here is the caller's business (the owner's authenticated reply, or an advisor under the standing
escalation-minimisation rule with its own guardrails): this module only stores, validates and reads. It never decides.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone

TASK_CLASS = "owner_decision"
KINDS = ("approval", "decline", "defer", "escalate")        # escalate: an advisor found the owner is needed
ACTORS = ("owner", "advisor")
DEFAULT_DEFER_DAYS = 7
MAX_DEFER_DAYS = 30
MAX_ACTIVE = 400
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\Z")
_REPO = re.compile(r"[a-z][a-z0-9-]{0,40}\Z")
_VIA = re.compile(r"[a-z][a-z0-9_.:-]{0,40}\Z")
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,60}\Z")


class LedgerError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean(value, limit: int) -> str:
    """One bounded line of plain text: no control characters, no markup that could be read as an instruction."""
    text = re.sub(r"[\x00-\x1f\x7f`<>]", " ", str(value if value is not None else ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _stamp(value):
    try:
        when = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _data(row) -> dict | None:
    try:
        data = json.loads(row.escalation_reason or "{}")
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def record(db, *, owner: str, kind: str, task_ref: str, task_id: str, scope_sha256: str, actor: str, via: str,
           rationale: str = "", model: str | None = None, package: str | None = None,
           reply_digest: str | None = None, defer_days: int | None = None, commit: bool = True) -> str:
    """Store one decision and supersede any earlier active decision for the same card. Returns the row id."""
    from core.database import RoutingDecision
    from src import estate_router
    if not isinstance(owner, str) or not owner.strip():
        raise LedgerError("owner is required")
    if kind not in KINDS or actor not in ACTORS:
        raise LedgerError("unknown kind or actor")
    if not isinstance(task_id, str) or not _TASK_ID.match(task_id):
        raise LedgerError("task_id is malformed")
    if not isinstance(scope_sha256, str) or not _HEX64.match(scope_sha256):
        raise LedgerError("scope digest is malformed")
    if not isinstance(task_ref, str) or ":" not in task_ref or len(task_ref) > 240 or not _REPO.match(task_ref.split(":", 1)[0]):
        raise LedgerError("task_ref is malformed")
    repo = task_ref.split(":", 1)[0]
    if not isinstance(via, str) or not _VIA.match(via):
        raise LedgerError("via is malformed")
    if actor == "advisor" and not (isinstance(model, str) and _MODEL.match(model)):
        raise LedgerError("an advisor decision must name its model")
    now = _now()
    expires = None
    if kind == "defer":
        days = DEFAULT_DEFER_DAYS if defer_days is None else int(defer_days)
        expires = (now + timedelta(days=max(1, min(days, MAX_DEFER_DAYS)))).isoformat()
    for row in db.query(RoutingDecision).filter_by(task_class=TASK_CLASS, status="active").all():
        data = _data(row)
        if data and data.get("owner") == owner and data.get("task_id") == task_id and _repo_of(data) == repo:
            row.status = "superseded"
    row_id = str(uuid.uuid4())
    db.add(RoutingDecision(
        id=row_id, task_class=TASK_CLASS, host_id=estate_router.current_host_id(),
        executor="claude" if actor == "advisor" else "deterministic",
        status="active", concrete_model=_clean(model, 60) or None,
        escalation_reason=json.dumps({
            "owner": owner, "kind": kind, "actor": actor, "via": via, "task_ref": task_ref, "repo": repo, "task_id": task_id,
            "scope_sha256": scope_sha256, "rationale": _clean(rationale, 300), "package": _clean(package, 40) or None,
            "reply_digest": _clean(reply_digest, 64) or None, "created": now.isoformat(), "expires": expires})))
    if commit:
        db.commit()
    return row_id


def _repo_of(data: dict) -> str:
    return str(data.get("repo") or str(data.get("task_ref") or "").split(":", 1)[0])


def _rows(db, owner: str, statuses, cap: int = 20000) -> list:
    """This owner's decision rows newest first, read in pages so unrelated rows can never crowd out the owner's. The
    LIKE narrowing is escaped (an owner string containing % or _ matches only itself); the exact owner check follows."""
    from core.database import RoutingDecision
    out, offset = [], 0
    while offset < cap:
        batch = (db.query(RoutingDecision).filter(RoutingDecision.task_class == TASK_CLASS, RoutingDecision.status.in_(statuses))
                 .filter(RoutingDecision.escalation_reason.contains(json.dumps(owner), autoescape=True))
                 .order_by(RoutingDecision.created_at.desc(), RoutingDecision.id).offset(offset).limit(500).all())
        out.extend(batch)
        offset += len(batch)
        if len(batch) < 500:
            break
    return out


def active(db, owner: str) -> list:
    """This owner's live decisions, newest first, bounded: active, unexpired, and only the NEWEST per card. Two writers
    racing can both leave an active row; whichever is newest is the decision, so an approval and a decline never coexist.
    A snooze with a missing or unreadable expiry is not a hold."""
    out, seen = [], set()
    for row in _rows(db, owner, ("active", "revoked")):
        data = _data(row)
        if not data or data.get("owner") != owner:
            continue
        key = (_repo_of(data), data.get("task_id"))
        if key in seen:
            continue                                   # an older row for the same card is superseded by the newer one
        seen.add(key)
        if row.status == "revoked":
            continue                                   # a revoked newest row is a tombstone: it must not uncover an older approval
        expires = _stamp(data.get("expires")) if data.get("expires") else None
        if data.get("kind") == "defer" and expires is None:
            continue
        if expires is not None and expires <= _now():
            continue
        out.append({"id": row.id, **data})
        if len(out) >= MAX_ACTIVE:
            break
    return out


def approved_scopes(db, owner: str) -> frozenset:
    """{(repo, task_id, scope_sha256)} the owner (or a delegated advisor) has approved and not revoked. The repository is
    part of the identity: the same task id and scope in two repositories are two cards."""
    return frozenset((_repo_of(d), d["task_id"], d["scope_sha256"]) for d in active(db, owner) if d.get("kind") == "approval")


def held_scopes(db, owner: str) -> frozenset:
    """{(repo, task_id, scope_sha256)} the owner declined or snoozed: not asked again until it expires or the scope changes."""
    return frozenset((_repo_of(d), d["task_id"], d["scope_sha256"]) for d in active(db, owner) if d.get("kind") in ("decline", "defer"))


def revoke(db, decision_id: str, owner: str) -> bool:
    from core.database import RoutingDecision
    row = db.query(RoutingDecision).filter_by(id=decision_id, task_class=TASK_CLASS).first()
    data = _data(row) if row is not None else None
    if row is None or row.status != "active" or not data or data.get("owner") != owner:
        return False
    row.status = "revoked"
    db.commit()
    return True


def listing(db, owner: str, limit: int = 50) -> list:
    out = []
    for row in _rows(db, owner, ("active", "revoked", "superseded")):
        data = _data(row)
        if not data or data.get("owner") != owner:
            continue
        out.append({"id": row.id, "status": row.status,
                    **{k: data.get(k) for k in ("kind", "actor", "via", "task_ref", "rationale", "package", "created", "expires")}})
        if len(out) >= max(1, min(limit, 200)):
            break
    return out


def escalated_scopes(db, owner: str) -> frozenset:
    """{(repo, task_id, scope_sha256)} an advisor judged to need the owner: they go to the phone, not to the advisor again."""
    return frozenset((_repo_of(d), d["task_id"], d["scope_sha256"]) for d in active(db, owner) if d.get("kind") == "escalate")

"""Wiring for the owner inbox: where its candidates come from and what its confirmed replies are allowed to do.

`owner_inbox` holds the protocol and is pure of the database; everything that touches the database, the cards or a model
lives here. A confirmed approval becomes a row in the owner decision ledger bound to the card's CURRENT scope digest,
re-read at the moment of confirmation, so a card that changed after the package was sent cannot be approved by a stale yes.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from datetime import timedelta

from src import owner_inbox as inbox
from src import owner_ledger as ledger

log = logging.getLogger(__name__)

# The advisor-approval worker (src/owner_advisor_approvals.py) is a separate, later change. Until it ships and this flips,
# nobody is asked to delegate, floor-eligible cards are NOT hidden from the phone, and `advisor_step` does nothing.
ADVISOR_APPROVALS_READY = False
DELEGATION_KEY = ("policy", inbox.DELEGATION_TASK_ID, inbox.DELEGATION_SCOPE)
GATHER_CACHE_SECONDS = 300
WORKER_STALE_SECONDS = 300           # a cycle may call a model twice; the file lock stops two cycles overlapping anyway
_SECRET_PATH = re.compile(r"(?:^|/)(?:\.env|\.git|\.github|\.ssh|\.aws|\.gnupg)(?:/|$)|secret|credential|passw|token|private[_-]?key|id_rsa|\.pem\b", re.I)
_cache = {"at": 0.0, "value": None, "owner": None}      # one owner's scan; another owner never reads it
_thread = {"thread": None, "started": 0.0}
_lock = threading.Lock()


def enabled() -> bool:
    return os.environ.get("ODYSSEUS_OWNER_INBOX", "1") != "0"


def advisor_floor(meta: dict) -> bool:
    """True when a card is, by its own metadata, inside what a delegated advisor may approve (code, not a model):
    a machine executor, a non-handoff mode, low or medium risk, and a non-empty list of literal in-repo write paths none
    of which touches secrets, credentials, VCS internals or anything outside the repository. High risk, a human executor
    or an empty write scope always stays with the owner."""
    from src import lazy_usage_runtime as rt
    if str(meta.get("executor") or "").lower() == "human" or str(meta.get("execution_mode") or "").lower() == "handoff":
        return False
    if str(meta.get("task_type") or "").lower() in rt.HANDOFF_TASK_TYPES:
        return False
    if str(meta.get("risk_level") or "").lower() not in ("low", "medium"):
        return False
    paths = meta.get("allowed_paths")
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p.strip() for p in paths):
        return False
    if not str(meta.get("executor") or "").strip():
        return False                                  # an unnamed executor is not a machine executor
    for p in paths:
        head = p.split("/")[0]
        # a literal in-repo directory must lead the path: a bare or leading wildcard would cover the whole repository
        if (p.startswith(("/", "~")) or ".." in p.split("/") or "\\" in p or _SECRET_PATH.search(p)
                or not head or "*" in head or "?" in head or "/" not in p.rstrip("/") and p.endswith("*")):
            return False
    return True


def card_facts(meta: dict, body: str = "") -> dict:
    """What the owner is shown as the decision's identity, built by code from the card itself (never from model text), and
    a fingerprint of everything the owner's approval would implicitly cover: any change to it makes the package stale."""
    import hashlib
    import json
    risk = inbox.plain(meta.get("risk_level") or "unrated", 12)
    title = inbox.plain(meta.get("title") or "", 40)
    keys = ("title", "notes", "task_type", "execution_mode", "risk_level", "executor", "priority", "allowed_paths",
            "denied_paths", "outputs", "result_path", "execution_host", "requires_web", "requires_mcp")
    fp = hashlib.sha256(json.dumps({**{k: meta.get(k) for k in keys}, "body": hashlib.sha256(str(body or "").encode()).hexdigest()},
                                   sort_keys=True, default=str).encode()).hexdigest()
    return {"card_line": f"{title}, {risk} risk"[:60], "fp": fp, "title": inbox.plain(meta.get("title") or "", 90)}


def delegation_active(db, owner: str) -> bool:
    return DELEGATION_KEY in ledger.approved_scopes(db, owner)


def _frontier():
    from src import lazy_usage_runtime as rt
    from scripts import agentic_portfolio as portfolio
    return rt.refresh_frontier(list(portfolio.LAYOUT))


def _scan(owner: str):
    """(phone candidates, advisor targets), cached for GATHER_CACHE_SECONDS. A candidate is an owner-class decision; an
    advisor target is a floor-eligible approval nobody has decided yet while the owner's delegation is in force."""
    from core.database import SessionLocal
    from src import lazy_usage_runtime as rt
    now = time.monotonic()
    if _cache["value"] is not None and _cache["owner"] == owner and now - _cache["at"] < GATHER_CACHE_SECONDS:
        return _cache["value"]
    db = SessionLocal()
    try:
        owed = rt.all_owed_reviews(db, owner)
        approved, held, escalated = (ledger.approved_scopes(db, owner), ledger.held_scopes(db, owner),
                                     ledger.escalated_scopes(db, owner))
        delegated = DELEGATION_KEY in approved and ADVISOR_APPROVALS_READY
        deleg_decided = DELEGATION_KEY in (approved | held)
    finally:
        db.close()
    frontier = _frontier()
    out, targets, floor_waiting = [], [], 0
    for debt in owed:
        if debt.get("gate") != "owner_approval" or not isinstance(debt.get("task_ref"), str) or ":" not in debt["task_ref"]:
            continue
        ref = debt["task_ref"]
        try:
            meta, body = rt._contract(frontier, {"ref": ref})
        except Exception:
            continue
        if not meta or not meta.get("task_id"):
            continue
        scope = rt.approval_scope(meta)
        task_id = str(meta["task_id"])
        key = (ref.split(":", 1)[0], task_id, scope)
        if key in approved or key in held:
            continue
        if advisor_floor(meta):
            floor_waiting += 1
            if delegated and key not in escalated:
                targets.append({"task_ref": ref, "task_id": task_id, "scope": scope, "meta": meta,
                                "priority": str(meta.get("priority") or ""), "opened_at": str(debt.get("opened_at") or "")})
                continue                     # the advisor decides it; it never reaches the phone unless it escalates
        out.append({"kind": "approval", "task_ref": ref, "task_id": task_id, "scope": scope, "gate": "owner_approval",
                    "priority": str(meta.get("priority") or ""), "opened_at": str(debt.get("opened_at") or ""),
                    **card_facts(meta, body), "context": rt.decision_context(debt, frontier)})
    if ADVISOR_APPROVALS_READY and floor_waiting and not deleg_decided:
        out.append({"kind": "delegation", "task_ref": "policy:advisor-approvals", "task_id": inbox.DELEGATION_TASK_ID,
                    "scope": inbox.DELEGATION_SCOPE, "priority": "critical", "opened_at": "", "title": "advisor approvals",
                    "context": {}})
    targets.sort(key=lambda c: (inbox._PRIORITY.get(c["priority"].lower(), 9), c["opened_at"], c["task_ref"]))
    _cache.update(at=now, value=(out, targets), owner=owner)
    return out, targets


def gather(owner: str) -> list:
    """The owner-class decisions waiting right now, as inbox candidates (unranked)."""
    return _scan(owner)[0]


def advisor_step(owner: str) -> list:
    """Let the delegated advisor decide the cards that do not need the owner (no-op unless the owner said yes)."""
    if not ADVISOR_APPROVALS_READY:
        return []                                   # the worker ships in a later change; nothing is imported or decided
    from core.database import SessionLocal
    from src import owner_advisor_approvals as approvals
    if not approvals.enabled():
        return []
    targets = _scan(owner)[1]
    if not targets:
        return []

    def call(text):
        from src import estate_router
        result = estate_router.execute_claude(text, timeout=90.0, role="opus")
        return (result.get("output"), result.get("concrete_model")) if result.get("ok") else (None, None)

    db = SessionLocal()
    try:
        if not delegation_active(db, owner):
            return []
        decided = approvals.process(db, owner, targets, call)
    finally:
        db.close()
    if decided:
        _cache["value"] = None
    return decided


def plain_title(meta: dict) -> str:
    return inbox.plain(meta.get("title") or "", 90)


def _model(prompt: str, role: str, timeout: float):
    from src import estate_router
    result = estate_router.execute_claude(prompt, timeout=timeout, role=role)
    return result.get("output") if result.get("ok") else None


def author(candidate: dict):
    return inbox.parse_author(_model(inbox.author_prompt(candidate), "opus", 90.0))


def parse(text: str, open_items: list, echo):
    names = {i["name"] for i in open_items}
    return inbox.parse_reply(_model(inbox.reply_prompt(text, open_items, echo), "sonnet", 60.0), names)


def apply_factory(owner: str):
    def apply(do: dict, items: dict, digest: str):
        from core.database import LazyUsageRun, SessionLocal
        from src import lazy_usage_runtime as rt
        db = SessionLocal()
        try:
            op = do["op"]
            if op == "pause_run":
                run = db.query(LazyUsageRun).filter(LazyUsageRun.created_by == owner,
                                                    LazyUsageRun.state.notin_(rt.TERMINAL)).first()
                if run is None:
                    return "Nothing is running.", "done"
                rt.pause_run(db, run.id, owner)
                return "Paused. The agents will not start new work until you resume.", "done"
            if op == "stop_advisor":
                ledger.record(db, owner=owner, kind="decline", task_ref="policy:advisor-approvals", task_id=inbox.DELEGATION_TASK_ID,
                              scope_sha256=inbox.DELEGATION_SCOPE, actor="owner", via="phone-reply", rationale="stopped by owner",
                              reply_digest=digest)
                _cache["value"] = None
                return "Advisor approvals stopped. Approvals you gave stay; none new will be made.", "done"
            item = items.get(do.get("item"))
            if item is None or item.get("state") != "open":
                return "That is no longer waiting.", "stale"
            kinds = {"approve": "approval", "decline": "decline", "defer": "defer"}
            if op not in kinds or (op == "approve" and do.get("confirmed") is not True):
                return None, "error"                      # an approval is only ever written from a confirmed echo
            if op == "approve":
                if item["kind"] == "delegation":
                    if item.get("task_id") != inbox.DELEGATION_TASK_ID or item.get("scope") != inbox.DELEGATION_SCOPE:
                        return None, "error"
                else:
                    # Fresh, uncached facts at the moment of confirmation: the gate must still be owed, and the card must
                    # still be exactly what the owner was shown (its scope digest AND its fingerprint).
                    still_owed = any(d.get("gate") == "owner_approval" and d.get("task_ref") == item["task_ref"]
                                     for d in rt.all_owed_reviews(db, owner))
                    try:
                        meta, body = rt._contract(_frontier(), {"ref": item["task_ref"]})
                    except Exception:
                        meta, body = None, ""
                    if (not still_owed or not meta or rt.approval_scope(meta) != item["scope"] or card_facts(meta, body)["fp"] != item.get("fp")
                            or str(meta.get("task_id")) != item["task_id"]):
                        _cache["value"] = None
                        return "That changed since I sent it. I will ask again if it still needs you.", "stale"
            ledger.record(db, owner=owner, kind=kinds[op], task_ref=item["task_ref"], task_id=item["task_id"],
                          scope_sha256=item["scope"], actor="owner", via="phone-reply", reply_digest=digest,
                          rationale="owner reply on the phone")
            _cache["value"] = None
            name = item.get("name") or "it"
            if item["kind"] == "delegation":
                return ("Done: an Opus advisor can now approve routine work. Say 'stop advisor approvals' to undo."
                        if op == "approve" else ("Okay, you keep approving." if op == "decline" else "Okay, I will ask again in a week.")), "done"
            return {"approve": f"Approved: {name}. Agents can start it.", "decline": f"Declined: {name}. I will not ask again unless it changes.",
                    "defer": f"Okay, I will ask about {name} again in a week."}[op], "done"
        except Exception as exc:
            log.warning("owner inbox action failed: %s", type(exc).__name__)
            return "I could not save that. Please reply again in a moment.", "error"
        finally:
            db.close()
    return apply


def digest_facts_factory(owner: str):
    def facts() -> dict:
        from datetime import datetime, timezone
        from core.database import LazyUsageRun, SessionLocal
        from src import lazy_usage_runtime as rt
        from src import owner_decisions as od
        db = SessionLocal()
        try:
            owed = rt.all_owed_reviews(db, owner)
            cards = od.build_cards(owed)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            decided = sum(1 for d in ledger.active(db, owner) if d.get("actor") == "advisor" and d.get("kind") == "approval"
                          and (ledger._stamp(d.get("created")) or cutoff) >= cutoff)
            run = db.query(LazyUsageRun).filter(LazyUsageRun.created_by == owner).order_by(LazyUsageRun.created_at.desc()).first()
            line = ""
            if run is not None:
                line = f"Last run {run.state.replace('_', ' ')}."
            return {"advisor_decided": decided, "acceptances": sum(1 for c in cards if c["gate"] == "owner_acceptance"), "run": line}
        finally:
            db.close()
    return facts


def run_cycle(owner: str) -> str:
    try:
        advisor_step(owner)
    except Exception as exc:
        log.warning("advisor approvals failed: %s", type(exc).__name__)
    return inbox.cycle(owner, gather=lambda: gather(owner), author=author, parse=parse, apply=apply_factory(owner),
                       digest_facts=digest_facts_factory(owner))


def offer():
    """Start one background cycle (never two at once; a stuck one is abandoned after WORKER_STALE_SECONDS).
    Returns the thread, or None when the inbox is off, unconfigured or busy. Never raises, never blocks the tick."""
    try:
        if not enabled():
            return None
        status, channel = inbox.load_channel()
        if status != "ok":
            return None
        owner = channel["owner"]
        with _lock:
            current = _thread["thread"]
            if current is not None and current.is_alive() and time.monotonic() - _thread["started"] < WORKER_STALE_SECONDS:
                return None
            worker = threading.Thread(target=_guarded, args=(owner,), name="owner-inbox", daemon=True)
            _thread.update(thread=worker, started=time.monotonic())
        worker.start()
        return worker
    except Exception:
        log.warning("owner inbox offer failed")
        return None


def _guarded(owner: str) -> None:
    try:
        run_cycle(owner)
    except Exception as exc:
        log.warning("owner inbox cycle failed: %s", type(exc).__name__)

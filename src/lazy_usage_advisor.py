"""The advisor checkpoint: instead of ending a run when its paid-call tranche is spent, an Opus advisor reviews the
whole process and the run may continue, within hard caps, with the review kept as persistent learnings.

`max_paid_calls` is a tranche. A run reaches a checkpoint when a tranche is spent and the owner activated it with
`advisor_checkpoints` > 0; it then parks, ONE advisor call reviews a bounded packet that THIS CODE builds (counts,
histograms, short refs; never a card body, model output, error text or secret), and the verdict decides:

* `continue` -> the next tranche starts, only if every deterministic rule still holds (an advisor can tighten, never
  relax): nothing unsettled (no pending usage accounting, lease or in-flight execution), no other hard ceiling reached
  (seconds, tool calls, tokens, repeated failures, no-delivery turns), the ABSOLUTE paid-call cap not reached (the
  advisor call itself is a paid call and counts against it), the checkpoint and advisor-call caps not reached, and the
  last tranche changed the ledger;
* anything else (stop, narrow, an unreadable answer, an unavailable advisor, a refused provider, an exception, a
  crash fence, an owner pause or stop that arrived while the advisor was thinking) -> the run ends `budget_exhausted`
  exactly as before, or the owner's own pause/stop is left alone. Unknown is never headroom.

The call is fenced by a stable claim (run id + checkpoint number) saved BEFORE the call, so a crash can never bill the
same checkpoint twice; the outcome (usage, review rows, learnings, state) is applied in ONE transaction, and only if
the same claim is still the active checkpoint under the run lock.

Learnings are typed. Only an ordering, skip or lane hint that is low risk, reversible, has a closed `action` and a
target the advisor was actually shown (or a known lane) is adopted automatically, for seven days, revocable, per
owner. What the next activation's coordinator reads is a sentence THIS CODE generates from those typed fields, never
the advisor's prose. Prompt, policy and code refinements are recorded as proposals for the owner and the existing PR
path; they change nothing by themselves.

Only the owner activates a run, and only the owner's activation can enable this (`advisor_checkpoints`)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from src import estate_router

log = logging.getLogger(__name__)

ADVISOR_TIMEOUT_S = 180.0
CLAIM_GRACE_S = 90.0                 # a claim younger than timeout + grace may still be waiting for its call
ADVISOR_TOKEN_ESTIMATE = 60_000      # reserved before the call: a one-token margin can never launch an advisor
MIN_SECONDS = 30
PACKET_CHARS = 12000
MAX_LEDGER_ROWS = 30
MAX_REFINEMENTS = 5
HINT_ACTIONS = {"ordering_hint": ("prefer", "defer"), "skip_hint": ("skip",), "lane_hint": ("prefer", "avoid")}
HINT_KINDS = tuple(HINT_ACTIONS)
OTHER_KINDS = ("prompt_change", "policy_change", "code_change", "owner_question")
LANES = ("glm-flash", "claude-sonnet", "glm-standard")
HINT_DAYS = 7
MAX_IN_FORCE = 5
VERDICTS = ("continue", "narrow", "stop")
RISKS = ("low", "medium", "high")
LEARNING = "lazyusage_learning"
REVIEW = "lazyusage_advisor_review"
ADVISOR_KEYS = ("advisor_checkpoints", "max_advisor_calls")
_SAFE = re.compile(r"[^A-Za-z0-9 ._:/()+=,;-]+")
_TOKEN = re.compile(r"[A-Za-z0-9_]{1,60}\Z")
# A ref the advisor may be shown: a registered-repo task path. Anything else (odd characters, a secret-shaped run of
# 24+ unbroken letters/digits) is left out of the packet entirely.
_REF = re.compile(r"[a-z][a-z-]{0,30}:[a-z-]{1,20}/[A-Za-z0-9._-]{1,100}\Z")
_SECRET_RUN = re.compile(r"[A-Za-z0-9]{24,}")

PROMPT = """You are the process advisor for one Odysseus lazy-usage run that has spent a tranche of its paid calls.
You advise only: you have no dispatch authority, no tools and no repository access. Review the whole process below
for refinements that would make the next runs deliver more with less waste: ordering, tasks that keep failing or
waiting, lane use, owner gates that block most of the queue, usage pacing. Decide whether the run should continue.

Rules: evidence only (every refinement must cite refs or counts from the packet); prefer small, reversible hints;
never ask to relax a gate, raise a budget, skip an owner approval or verification, or touch a protected card; do not
repeat a learning already in force; unknown usage stays unknown.

Answer with ONE JSON object and nothing else, exactly this shape:
{json_shape}
verdict: continue, narrow or stop. reason: at most 200 characters. refinements: 0-{max_refinements}, each with kind
(ordering_hint, skip_hint, lane_hint, prompt_change, policy_change, code_change or owner_question), action (for
ordering_hint prefer|defer; skip_hint skip; lane_hint prefer|avoid; otherwise none), target (a ref from the packet for
ordering_hint and skip_hint, one of glm-flash|claude-sonnet|glm-standard for lane_hint, otherwise a short topic),
statement (at most 300 characters), expected_effect (at most 200), risk (low, medium or high) and reversible (true or
false). owner_attention: 0-3 short strings (at most 200 characters each) for things only the owner can decide. No other
keys, no prose outside the JSON.

Packet:
{packet}
"""
JSON_SHAPE = ('{"verdict": "continue|narrow|stop", "reason": "<short>", "refinements": [{"kind": "<kind>", '
              '"action": "<action or none>", "target": "<ref, lane or topic>", "statement": "<text>", '
              '"expected_effect": "<text>", "risk": "low|medium|high", "reversible": true}], "owner_attention": ["<text>"]}')


def enabled() -> bool:
    return os.environ.get("ODYSSEUS_LAZY_USAGE_ADVISOR") != "0"


def clean(value, limit: int) -> str:
    text = re.sub(r"\s+", " ", _SAFE.sub(" ", str(value if value is not None else ""))).strip()
    return text[:limit]


def token(value, limit: int = 60) -> str:
    """A machine token (a skip reason, an exception type): anything with spaces or punctuation is dropped."""
    text = str(value if value is not None else "")
    return text[:limit] if _TOKEN.match(text) else ""


def safe_ref(value) -> str:
    from scripts import agentic_portfolio as portfolio
    text = str(value if value is not None else "")
    repo, _, rest = text.partition(":")
    if (_REF.match(text) and repo in portfolio.LAYOUT and ".." not in rest
            and not _SECRET_RUN.search(text.replace("-", " ").replace(".", " ").replace("_", " "))):
        return text
    return ""


def _entry(e) -> dict:
    return e if isinstance(e, dict) else {}


def state(run) -> dict:
    advisor = (run.checkpoint or {}).get("advisor")
    return dict(advisor) if isinstance(advisor, dict) else {}


def _digest_of(ledger) -> str:
    rows = sorted(f"{ref}={_entry(entry).get('outcome')}" for ref, entry in ledger.items()) if isinstance(ledger, dict) else []
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()[:16]


def ledger_digest(run) -> str:
    return _digest_of((run.checkpoint or {}).get("ledger"))


def initial_state(checkpoint: dict) -> dict:
    return {"checkpoints": 0, "calls": 0, "tranche_base": 0, "last_digest": _digest_of(checkpoint.get("ledger"))}


def tranche_base(run) -> int:
    """The paid calls spent before the current tranche began, never more than were actually spent."""
    base = state(run).get("tranche_base", 0)
    paid = (run.counters or {}).get("paid_calls", 0)
    base = base if type(base) is int and base >= 0 else 0
    return min(base, paid if type(paid) is int and paid >= 0 else 0)


def total_cap(budgets: dict) -> int | None:
    """The absolute paid-call ceiling across tranches (an explicit 0 means none), or None when the advisor is off."""
    checkpoints = budgets.get("advisor_checkpoints", 0)
    if not checkpoints:
        return None
    by_tranche = budgets["max_paid_calls"] * (1 + checkpoints)
    absolute = budgets.get("max_paid_calls_total")
    return by_tranche if absolute is None else min(absolute, by_tranche)


def _unsettled(run) -> bool:
    """Anything that must be reconciled before the advisor may run or the run may continue."""
    cp = run.checkpoint or {}
    return bool(cp.get("usage_accounting_pending") or cp.get("lease") or cp.get("lease_release_debt")
                or cp.get("in_flight_execution_id") or cp.get("phase") != "idle")      # missing is unsettled: fail closed


def can_continue(run, *, extra_calls: int = 0) -> bool:
    """May the run start another tranche? Only while nothing is unsettled, no hard ceiling is reached and the
    absolute paid-call cap holds (with `extra_calls` of room reserved)."""
    from src import lazy_usage_runtime as rt
    counters = run.counters or {}
    if not enabled() or not (run.budgets or {}).get("advisor_checkpoints") or _unsettled(run):
        return False
    cap = total_cap(rt._effective_budgets(run))
    if cap is not None and counters.get("paid_calls", 0) + extra_calls >= cap:
        return False
    return not rt._budget_reason(run, skip_paid=True)       # any other hard ceiling ends the run, as before


def can_review(run) -> bool:
    """May a checkpoint review happen now? Deterministic; the advisor's verdict can only tighten it. The review is a
    paid call itself, and must leave room for at least one task dispatch afterwards."""
    from src import lazy_usage_runtime as rt
    budgets, adv = rt._effective_budgets(run), state(run)
    if not can_continue(run, extra_calls=1):                  # the review itself, plus room for one task dispatch after it
        return False
    if adv.get("checkpoints", 0) >= budgets["advisor_checkpoints"] or adv.get("calls", 0) >= budgets["max_advisor_calls"]:
        return False
    return adv.get("last_digest") != ledger_digest(run)    # the last tranche must have changed the ledger


# ---------------------------------------------------------------- the packet

def build_packet(db, run) -> dict:
    """Counts, histograms and short refs only. Never a card body, a model output, an error text or a secret."""
    from src import lazy_usage_runtime as rt
    cp, counters = run.checkpoint or {}, run.counters or {}
    ledger = cp.get("ledger") if isinstance(cp.get("ledger"), dict) else {}
    rows = [{"ref": safe_ref(ref), "kind": clean(_entry(e).get("kind"), 24), "outcome": clean(_entry(e).get("outcome"), 32)}
            for ref, e in list(ledger.items())[-MAX_LEDGER_ROWS:] if safe_ref(ref)]
    skipped = cp.get("skipped") if isinstance(cp.get("skipped"), dict) else {}
    owed = [d for d in cp.get("owed_reviews") or [] if isinstance(d, dict)]
    providers = {}
    for name in ("claude", "codex", "glm"):
        try:
            health = estate_router.provider_allows_dispatch(name)
            providers[name] = {"state": token(health.get("state"), 20), "allowed": bool(health.get("allowed"))}
        except Exception:
            providers[name] = {"state": "unknown"}
    usage = {}
    try:
        from src import provider_usage
        reading = provider_usage.codex_windows_cached()
        if reading.get("confidence") == "provider-stated":
            usage["codex"] = {"observed_at": clean(reading.get("observed_at"), 40),
                              "windows": [{"minutes": w.get("window_minutes"), "used_percent": w.get("used_percent"),
                                           "resets_at": clean(w.get("resets_at"), 30)} for w in reading.get("windows") or []]}
    except Exception:
        pass
    adv = state(run)
    packet = {
        "run": {"id": clean(run.id, 8), "elapsed_seconds": int(((run.finished_at or rt.utcnow_naive()) - run.started_at).total_seconds())
                if run.started_at else 0},
        "budgets": {k: v for k, v in (run.budgets or {}).items() if type(v) is int},
        "counters": {k: v for k, v in counters.items() if type(v) is int},
        "tranche": {"paid_calls_in_tranche": counters.get("paid_calls", 0) - tranche_base(run),
                    "checkpoint": adv.get("checkpoints", 0) + 1, "of": (run.budgets or {}).get("advisor_checkpoints", 0)},
        "last_failure_type": token(counters.get("last_failure_signature")),
        "ledger_outcomes": dict(Counter(clean(_entry(e).get("outcome"), 32) for e in ledger.values())),
        "ledger_recent": rows,
        "skipped_reasons": dict(Counter(token(v, 40) for v in skipped.values())),
        "owed_by_gate": dict(Counter(clean(d.get("gate") or "legacy", 24) for d in owed)),
        "owed_refs": [r for r in (safe_ref(d.get("task_ref")) for d in owed[:10]) if r],
        "coordinator": {"lane": token(cp.get("coordinator_lane"), 24), "skip": token(cp.get("coordinator_skip"))},
        "usage_block": clean((cp.get("usage_block") or {}).get("why"), 80) if isinstance(cp.get("usage_block"), dict) else "",
        "providers": providers, "provider_usage": usage,
        "learnings_in_force": [{"id": clean(item.get("id"), 8), "text": clean(item.get("text"), 200)}
                               for item in (cp.get("learnings") or [])[:MAX_IN_FORCE] if isinstance(item, dict)],
    }
    # hold the final serialized size to the cap: shed the longest lists first, then the rest of the optional parts
    for key in ("ledger_recent", "owed_refs", "learnings_in_force", "ledger_outcomes", "skipped_reasons", "owed_by_gate"):
        while len(json.dumps(packet, sort_keys=True)) > PACKET_CHARS and packet[key]:
            packet[key] = packet[key][: len(packet[key]) // 2] if isinstance(packet[key], list) else {}
    return packet


def packet_refs(packet: dict) -> set:
    return {row["ref"] for row in packet.get("ledger_recent", []) if row.get("ref")} | set(packet.get("owed_refs", []))


def build_prompt(packet: dict) -> str:
    return PROMPT.format(json_shape=JSON_SHAPE, max_refinements=MAX_REFINEMENTS, packet=json.dumps(packet, sort_keys=True))


# ---------------------------------------------------------------- the answer

def _no_duplicate_keys(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key")
    return dict(pairs)


def parse_review(text, refs: set):
    """Strict validation, or None. Exact keys (no duplicates), bounded sizes, closed vocabularies."""
    if not isinstance(text, str) or len(text) > 20000:
        return None
    body = text.strip()
    if body.startswith("```"):
        body = re.sub(r"^```[a-z]*\n?|\n?```$", "", body).strip()
    try:
        review = json.loads(body, object_pairs_hook=_no_duplicate_keys)
    except ValueError:
        return None
    if not isinstance(review, dict) or set(review) != {"verdict", "reason", "refinements", "owner_attention"}:
        return None
    if review["verdict"] not in VERDICTS or not isinstance(review["reason"], str) or len(review["reason"]) > 400:
        return None
    if not isinstance(review["refinements"], list) or len(review["refinements"]) > MAX_REFINEMENTS:
        return None
    if (not isinstance(review["owner_attention"], list) or len(review["owner_attention"]) > 3
            or any(not isinstance(x, str) or len(x) > 400 for x in review["owner_attention"])):
        return None
    out = []
    keys = {"kind", "action", "target", "statement", "expected_effect", "risk", "reversible"}
    for item in review["refinements"]:
        if not isinstance(item, dict) or set(item) != keys:
            return None
        if (item["kind"] not in HINT_KINDS + OTHER_KINDS or item["risk"] not in RISKS or type(item["reversible"]) is not bool
                or any(not isinstance(item[k], str) for k in ("action", "target", "statement", "expected_effect"))
                or len(item["statement"]) > 600 or len(item["expected_effect"]) > 400 or len(item["target"]) > 200
                or len(item["action"]) > 20):
            return None
        out.append({"kind": item["kind"], "action": clean(item["action"], 20).lower(), "target": item["target"][:200],
                    "statement": clean(item["statement"], 300), "expected_effect": clean(item["expected_effect"], 200),
                    "risk": item["risk"], "reversible": item["reversible"]})
    return {"verdict": review["verdict"], "reason": clean(review["reason"], 200), "refinements": out,
            "owner_attention": [clean(x, 200) for x in review["owner_attention"]]}


def adoptable(item: dict, refs: set) -> bool:
    """Only a typed, low-risk, reversible ordering/skip/lane hint about something the advisor was actually shown."""
    if item["kind"] not in HINT_KINDS or item["risk"] != "low" or item["reversible"] is not True:
        return False
    if item["action"] not in HINT_ACTIONS[item["kind"]]:
        return False
    return item["target"] in LANES if item["kind"] == "lane_hint" else item["target"] in refs


def hint_text(item: dict) -> str:
    """The sentence the coordinator sees: generated here from typed fields, never the advisor's prose."""
    return f"{item['action']} {item['kind'].replace('_hint', '')} {item['target']}"[:200]


# ---------------------------------------------------------------- persistence (existing routing_decisions log)

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _expiry(value) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)      # a naive stamp is read as UTC


def _rows(db, status):
    from core.database import RoutingDecision
    return db.query(RoutingDecision).filter_by(task_class=LEARNING, status=status).order_by(RoutingDecision.created_at.desc()).all()


def _mine(row, owner) -> dict | None:
    data = json.loads(row.escalation_reason or "{}")
    return data if data.get("owner") == owner else None


def _active(db, owner) -> list:
    out = []
    for row in _rows(db, "adopted"):
        data = _mine(row, owner)
        when = _expiry(data.get("expires")) if data else None
        if data and when and when > _now():
            out.append((row, data))
    return out


def persist(db, run, review: dict, refs: set, model) -> list:
    """Add the review and each refinement to the session (the caller commits, in the same transaction as the
    checkpoint outcome). Returns the learnings adopted now."""
    from core.database import RoutingDecision
    host = estate_router.current_host_id()
    now = _now()
    owner = run.created_by
    active = {data.get("text") for _, data in _active(db, owner)}
    adopted = []
    db.add(RoutingDecision(id=str(uuid.uuid4()), task_class=REVIEW, host_id=host, executor="claude", status="complete",
                           concrete_model=clean(model, 60) or None,
                           escalation_reason=json.dumps({"run": run.id, "owner": owner, "verdict": review["verdict"],
                                                         "reason": review["reason"], "refinements": len(review["refinements"]),
                                                         "owner_attention": review["owner_attention"]})))
    for item in review["refinements"]:
        text = hint_text(item) if item["kind"] in HINT_KINDS else None
        status = "adopted" if adoptable(item, refs) and text not in active else "proposed"
        row_id = str(uuid.uuid4())
        db.add(RoutingDecision(id=row_id, task_class=LEARNING, host_id=host, executor="claude", status=status,
                               concrete_model=clean(model, 60) or None,
                               escalation_reason=json.dumps({**item, "statement": clean(item["statement"], 300), "target": clean(item["target"], 140),
                                                             "text": text if status == "adopted" else None, "owner": owner,
                                                             "run": run.id, "created": now.isoformat(),
                                                             "expires": (now + timedelta(days=HINT_DAYS)).isoformat()
                                                             if status == "adopted" else None})))
        if status == "adopted":
            adopted.append({"id": row_id, "text": text})
            active.add(text)
    return adopted


def learnings_in_force(db, owner) -> list:
    """This owner's adopted, unexpired, unrevoked hints (newest first, bounded): advisory data for the next run."""
    return [{"id": row.id, "kind": data.get("kind"), "target": clean(data.get("target"), 140), "text": clean(data.get("text"), 200)}
            for row, data in _active(db, owner)][:MAX_IN_FORCE]


def list_learnings(db, owner, limit: int = 50) -> list:
    from core.database import RoutingDecision
    rows = db.query(RoutingDecision).filter_by(task_class=LEARNING).order_by(RoutingDecision.created_at.desc()).limit(500).all()
    out = []
    for row in rows:
        data = _mine(row, owner)
        if data is None:
            continue
        out.append({"id": row.id, "status": row.status, **{k: data.get(k) for k in
                                                           ("kind", "action", "target", "statement", "expected_effect", "risk",
                                                            "reversible", "run", "expires")}})
        if len(out) >= max(1, min(limit, 200)):
            break
    return out


def revoke(db, learning_id: str, owner) -> bool:
    from core.database import RoutingDecision
    row = db.query(RoutingDecision).filter_by(id=learning_id, task_class=LEARNING).first()
    if row is None or row.status == "revoked" or _mine(row, owner) is None:
        return False
    row.status = "revoked"
    db.commit()
    return True


# ---------------------------------------------------------------- the checkpoint itself

def run_checkpoint(db, run):
    """One bounded advisor call, fenced by a stable claim and applied under the run lock."""
    from src import lazy_usage_coordinator as coordinator
    from src import lazy_usage_runtime as rt

    def end(note, **extra):
        rt._checkpoint(run, advisor={**state(run), "last_note": note, **extra})
        return rt._finish(db, run, "budget_exhausted", "max_paid_calls")

    adv = state(run) or initial_state(run.checkpoint or {})
    key = f"{run.id}:{adv.get('checkpoints', 0)}"                    # stable: it does not move when the call is charged
    if adv.get("attempted_key") == key:
        started = _expiry(adv.get("attempted_at"))
        if started is not None and (_now() - started).total_seconds() < ADVISOR_TIMEOUT_S + CLAIM_GRACE_S:
            return rt.run_dict(run)                                  # another observer's call may still be in flight
        return end("checkpoint already attempted")
    counters, budgets = run.counters or {}, rt._effective_budgets(run)
    spent = counters.get("tokens_measured", 0) + counters.get("tokens_assumed", 0)
    if spent + ADVISOR_TOKEN_ESTIMATE > budgets["max_tokens"]:
        return end("no token headroom for the advisor")
    if not can_review(run):
        return end("not allowed to continue")
    packet = build_packet(db, run)
    # Charge BEFORE the call (as the coordinator does): the claim and the spend survive a crash mid-call. The review is
    # a paid dispatch, so it counts against the absolute paid-call cap as well as the advisor-call cap.
    adv.update(attempted_key=key, attempted_at=_now().isoformat(), calls=adv.get("calls", 0) + 1)
    rt._charge(run, paid_calls=1, tool_calls=1)
    rt._checkpoint(run, advisor=adv)
    db.commit()
    def retake(result=None):
        """Re-take the run under its lock; meter the call's tokens (real spend is evidence even if the answer is not
        used); report whether THIS claim is still the active checkpoint. An owner pause or stop must never be
        overwritten or revived, and a failed attempt must never lose the usage."""
        nonlocal run
        db.rollback()
        db.query(rt.LazyUsageRun.id).filter_by(id=run.id).with_for_update().scalar()
        run = rt._load(db, run.id)
        if result is not None:
            refused = estate_router._provider_outcome(result).get("state") in {"quota_exhausted", "rate_limited"}
            if not refused and result.get("executed") is not False:
                coordinator._meter_tokens(run, result)
        cp_now = run.checkpoint or {}
        return (run.state == "paused" and cp_now.get("next_action") == "advisor_review"
                and cp_now.get("pause_reason") == "advisor checkpoint" and state(run).get("attempted_key") == key)

    def finish_if_held(held, note, **extra):
        if not held:
            db.commit()
            return rt.run_dict(run)
        return end(note, **extra)

    remaining = budgets["max_seconds"] - (rt.utcnow_naive() - run.started_at).total_seconds()      # measured AFTER the commit
    if remaining < MIN_SECONDS:
        return finish_if_held(retake(), "no time left for the advisor")
    try:
        result = estate_router.execute_claude(build_prompt(packet), timeout=min(ADVISOR_TIMEOUT_S, remaining), role="opus")
    except Exception:
        result = {"ok": False, "error_code": "advisor_exception"}
    held = retake(result)
    if not held:
        db.commit()
        return rt.run_dict(run)
    if not result.get("ok"):
        return end("advisor_failed_" + token(result.get("error_code") or "unknown", 40))
    refs = packet_refs(packet)
    review = parse_review(result.get("output"), refs)
    if review is None:
        return end("advisor_answer_invalid", model=clean(result.get("concrete_model"), 60))
    adv = state(run)
    cp = run.checkpoint or {}
    try:
        adopted = persist(db, run, review, refs, result.get("concrete_model"))
        adv.update(checkpoints=adv.get("checkpoints", 0) + 1, last_digest=ledger_digest(run), last_verdict=review["verdict"],
                   last_reason=review["reason"], last_model=clean(result.get("concrete_model"), 60), adopted=len(adopted),
                   owner_attention=review["owner_attention"])
        rt._checkpoint(run, advisor=adv, learnings=[*(cp.get("learnings") or []), *adopted][:MAX_IN_FORCE])
        if review["verdict"] == "continue" and can_continue(run):
            adv["tranche_base"] = (run.counters or {}).get("paid_calls", 0)
            run.state = "running"
            return rt._save(db, run, advisor=adv, pause_reason=None, recheck_at=None, next_action="refresh_frontier", phase="idle")
        return end("advisor_verdict_" + review["verdict"], **{k: adv.get(k) for k in ("checkpoints", "last_verdict", "last_reason")})
    except Exception:
        # nothing half-written: take the run again, keep the call's token charge, and end only if the claim is still ours
        return finish_if_held(retake(result), "advisor_persist_failed")

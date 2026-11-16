"""Opt-in bounded cognitive coordination for explicitly activated runs.

The coordinator is ONE advisory planning call per unchanged frontier state,
never a second scheduler: lazy_usage_runtime keeps every dispatch, budget,
lease, verification and stop/resume decision, and the central estate router
keeps provider/model authority. Lane selection is usage-aware by design —
each turn picks the cheapest adequate lane from live provider health, host
executor qualification and the run's remaining budgets, and skips the call
entirely when too little paid budget remains to leave room for a real task
dispatch. Model output is strictly validated (schema and bounds) and only
advises queue order plus a bounded decomposition for the primary task.
Every failure fails closed to the existing deterministic loop.
"""
from __future__ import annotations

import hashlib
import json
import os

from src import estate_router

LANES = ("glm-flash", "claude-sonnet", "glm-standard")
# lane -> (paid provider, GLM launcher variant or None)
LANE_ROUTES = {"glm-flash": ("glm", "flash"), "glm-standard": ("glm", None),
               "claude-sonnet": ("claude", None)}
LANE_EXECUTOR = {"glm-flash": "glm", "glm-standard": "glm", "claude-sonnet": "claude"}
DEFAULT_POLICY = {"enabled": True,
                  "routine_lanes": ["glm-flash", "claude-sonnet", "glm-standard"],
                  "high_consequence_lanes": ["claude-sonnet", "glm-standard", "glm-flash"],
                  "min_paid_budget_remaining": 2}
CALL_TIMEOUT_S = 120.0
MAX_CANDIDATES = 15
MAX_SELECTED = 12
MAX_STEPS = 8
MAX_STEP_CHARS = 200
MAX_NEXT_ACTION_CHARS = 120

PROMPT = """You are the bounded cognitive coordinator for one Odysseus lazy-usage turn.
You advise only: you have no dispatch authority, no tools and no repository access.
Order the candidate owner tasks for THIS turn and outline execution of the first.

Rules: shipping-first (near-complete, unblocking or safety-gated work first);
prefer the cheapest adequate qualified route; respect protected gates, owner
acceptance and verification requirements; propose nothing outside the listed
candidates. Use the included budget/usage state: spend attention where the
remaining budget makes real delivery plausible this turn.

Answer with ONE JSON object and nothing else, exactly this shape:
{json_shape}
selected: 1-{max_selected} candidate refs, best first. decomposition: 0-{max_steps}
steps for the first selected task, each at most {max_step_chars} characters.
next_action: at most {max_next_action_chars} characters. No other keys, no
prose outside the JSON.

Context:
candidates: {candidates}
owed_reviews: {owed}
budgets: {budgets}
counters: {counters}
"""

JSON_SHAPE = ('{"selected": ["<candidate ref>", ...], '
              '"decomposition": ["<step>", ...], "next_action": "<short phrase>"}')


def _checkpoint(run, **fields):
    run.checkpoint = {**(run.checkpoint or {}), **fields}


def _charge(run, **counts):
    counters = dict(run.counters or {})
    for key, count in counts.items():
        counters[key] = counters.get(key, 0) + count
    run.counters = counters


def policy():
    """Validated config/routing.yaml policy over safe defaults."""
    merged = dict(DEFAULT_POLICY)
    try:
        configured = (estate_router._load_yaml("routing").get("lazy_usage_coordinator") or {})
    except estate_router.RoutingConfigError:
        configured = {}
    if not isinstance(configured, dict):
        return dict(merged)
    if type(configured.get("enabled")) is bool:
        merged["enabled"] = configured["enabled"]
    for key in ("routine_lanes", "high_consequence_lanes"):
        lanes = configured.get(key)
        if (isinstance(lanes, list) and lanes and
                all(isinstance(lane, str) and lane in LANES for lane in lanes)):
            merged[key] = list(dict.fromkeys(lanes))
    floor = configured.get("min_paid_budget_remaining")
    if type(floor) is int and floor >= 0:
        merged["min_paid_budget_remaining"] = floor
    return merged


def master_enabled():
    """Config master switch plus the documented env kill switch."""
    if os.getenv("ODYSSEUS_LAZY_USAGE_COORDINATOR") == "0":
        return False
    return policy()["enabled"]


def _budgets(run):
    from src.lazy_usage_runtime import CEILINGS
    return {k: min((run.budgets or {}).get(k, v), v) for k, v in CEILINGS.items()}


def _qualified_executors():
    host_id = estate_router.current_host_id()
    try:
        entry = next((h for h in estate_router._load_yaml("estate").get("hosts", [])
                      if h.get("id") == host_id), None)
    except estate_router.RoutingConfigError:
        return []
    if entry is None:
        return []
    return estate_router.host_static_state(entry).get("qualified_executors") or []


def select_lane(run, *, high_consequence):
    """Usage-aware lane choice: cheapest adequate qualified lane for this turn."""
    configured = policy()
    budgets, counters = _budgets(run), run.counters or {}
    remaining = budgets["max_paid_calls"] - counters.get("paid_calls", 0)
    if remaining < max(1, configured["min_paid_budget_remaining"]):
        return {"lane": None, "reason": "paid_budget_reserved_for_task_dispatch"}
    order = configured["high_consequence_lanes"] if high_consequence else configured["routine_lanes"]
    qualified = _qualified_executors()
    considered = []
    for lane in order:
        if lane not in LANES:
            continue
        considered.append(lane)
        if LANE_EXECUTOR[lane] not in qualified:
            continue
        # Read-only health check: no launch_timeout means no attempt is reserved.
        health = estate_router.provider_allows_dispatch(LANE_ROUTES[lane][0])
        if not health.get("allowed"):
            continue
        return {"lane": lane, "reason": "lane selected", "considered": considered}
    return {"lane": None, "reason": "no_qualified_coordinator_lane", "considered": considered}


def _candidates(frontier):
    from src.lazy_usage_runtime import TASK_TERMINAL
    rows = [r for r in frontier["records"]
            if r.get("bucket") not in {"inbox", "blocked", "blocked-human"}
            and str(r.get("status", "")).lower() not in TASK_TERMINAL]
    return rows[:MAX_CANDIDATES]


def build_prompt(frontier, run):
    candidates = [{"ref": r["ref"], "bucket": r.get("bucket"),
                   "priority": r.get("priority"), "status": r.get("status")}
                  for r in _candidates(frontier)]
    owed = [{"task_ref": d.get("task_ref"), "gate": d.get("gate"),
             "retry_after": d.get("retry_after")}
            for d in (run.checkpoint or {}).get("owed_reviews", [])]
    return PROMPT.format(json_shape=JSON_SHAPE, max_selected=MAX_SELECTED, max_steps=MAX_STEPS,
                         max_step_chars=MAX_STEP_CHARS, max_next_action_chars=MAX_NEXT_ACTION_CHARS,
                         candidates=json.dumps(candidates, sort_keys=True),
                         owed=json.dumps(owed, sort_keys=True),
                         budgets=json.dumps(_budgets(run), sort_keys=True),
                         counters=json.dumps(run.counters or {}, sort_keys=True))


def parse_plan(text, valid_refs):
    """Strict validation: exact schema, bounded sizes, and refs restricted
    to the bounded candidate set the model was actually shown."""
    if not isinstance(text, str):
        return None
    try:
        plan = json.loads(text.strip())
    except ValueError:
        return None
    if not isinstance(plan, dict) or set(plan) != {"selected", "decomposition", "next_action"}:
        return None
    selected = plan["selected"]
    if (not isinstance(selected, list) or not 1 <= len(selected) <= MAX_SELECTED
            or any(not isinstance(ref, str) or ref not in valid_refs for ref in selected)):
        return None
    order, seen = [], set()
    for ref in selected:
        if ref not in seen:
            order.append(ref)
            seen.add(ref)
    steps = plan["decomposition"]
    if (not isinstance(steps, list) or len(steps) > MAX_STEPS
            or any(not isinstance(step, str) or not step.strip() or len(step) > MAX_STEP_CHARS
                   for step in steps)):
        return None
    next_action = plan["next_action"]
    if (not isinstance(next_action, str) or not next_action.strip()
            or len(next_action) > MAX_NEXT_ACTION_CHARS):
        return None
    return {"order": order, "primary": order[0], "decomposition": steps,
            "next_action": next_action.strip()}


def plan_key(digest, checkpoint=None):
    """One paid plan per frontier state: the digest covers every queue
    change (added/moved/status), so an unchanged digest means a persisted
    plan is reused across restarts and task attempts without a repeat
    paid call."""
    return hashlib.sha256(("lazyusage-coordinator:" + digest).encode()).hexdigest()


def high_consequence(checkpoint, counters):
    """Deterministic turn consequence: verified debt or repeated failures."""
    cp = checkpoint or {}
    return bool(cp.get("owed_reviews")) or (counters or {}).get("repeated_failures", 0) >= 2


def coordinator_step(db, run, frontier, digest):
    """One bounded advisory planning call; commits before the provider boundary.

    Returns a validated plan dict, a persisted plan on an unchanged key (no
    repeat paid call), or None with the skip reason checkpointed. Never
    raises for provider/output failures — the deterministic loop continues.
    """
    cp = run.checkpoint or {}
    if not (cp.get("coordinator") or {}).get("enabled"):
        return None
    if not master_enabled():
        _checkpoint(run, coordinator_skip="coordinator_disabled")
        db.commit()
        return None
    key = plan_key(digest, cp)
    if cp.get("coordinator_key") == key and isinstance(cp.get("coordinator_order"), list):
        # Persisted plan for an unchanged frontier state; restart-safe reuse.
        return {"order": cp["coordinator_order"], "primary": cp.get("coordinator_primary"),
                "decomposition": cp.get("coordinator_decomposition") or [],
                "next_action": cp.get("coordinator_next_action")}
    if cp.get("coordinator_attempted_key") == key:
        # This frontier state was already attempted (failure, invalid output
        # or crash): never re-bill the same digest. A new frontier digest
        # is the only re-plan trigger.
        _checkpoint(run, coordinator_skip="digest_already_attempted")
        db.commit()
        return None
    choice = select_lane(run, high_consequence=high_consequence(cp, run.counters))
    lane = choice["lane"]
    if lane is None:
        _checkpoint(run, coordinator_skip=choice["reason"], coordinator_key=None)
        db.commit()
        return None
    provider, variant = LANE_ROUTES[lane]
    prompt = build_prompt(frontier, run)
    # Charge BEFORE the call so spent accounting survives a crash mid-call.
    # The attempted-digest fence in the same commit guarantees exactly one
    # coordinator call per frontier digest even across crashes.
    _charge(run, paid_calls=1, tool_calls=1)
    _checkpoint(run, coordinator_skip=None, coordinator_lane=lane, coordinator_key=None,
                coordinator_attempted_key=key)
    db.commit()
    try:
        if provider == "glm":
            kwargs = {"variant": variant} if variant else {}
            result = estate_router.execute_glm(prompt, timeout=CALL_TIMEOUT_S, **kwargs)
        else:
            result = estate_router.execute_claude(prompt, timeout=CALL_TIMEOUT_S)
    except Exception:
        _checkpoint(run, coordinator_skip="provider_exception")
        db.commit()
        return None
    if not result.get("ok"):
        # The executor recorded provider health itself; keep the reason bounded.
        _checkpoint(run, coordinator_skip="provider_failed_" + str(result.get("error_code") or "unknown")[:60])
        db.commit()
        return None
    plan = parse_plan(result.get("output"), {r["ref"] for r in _candidates(frontier)})
    if plan is None:
        _checkpoint(run, coordinator_skip="plan_validation_failed",
                    coordinator_model=result.get("concrete_model"))
        db.commit()
        return None
    _checkpoint(run, coordinator_key=key, coordinator_order=plan["order"],
                coordinator_primary=plan["primary"], coordinator_decomposition=plan["decomposition"],
                coordinator_next_action=plan["next_action"], coordinator_lane=lane,
                coordinator_model=result.get("concrete_model"),
                coordinator_high_consequence=high_consequence(cp, run.counters))
    db.commit()
    return plan

"""Deterministic, explainable team formation for the Misumi interface (application -11).

One LEAD persona answers; zero to two SUPPORT personas are recruited only when that is justified, and the
reason for every recruitment (or for recruiting nobody) is recorded. Collaboration is work, not theatre:
supports never address the user, never gain authority, and are never recruited by ambient similarity.

Rules (all deterministic, no model calls):

* The lead is whoever routing/the caller chose. A lead never recruits itself.
* Aoteru as lead keeps the behaviour the application -07-era consultation layer established (a named persona,
  or a persona whose routing intents match a *complex* request; at most two; named-first ranking), unchanged.
* A specialist lead may recruit only along its OWN ratified ``consults`` edges (contract rule 5: edges are
  the permitted delegated follow-ups, not licence to spawn anyone). Aoteru is never recruited as a support:
  it is the head interfacer, not a specialist input.
* Justification kinds: ``named`` (the user names the persona) or ``intent`` (the persona's routing intents match
  the request AND the request is complex: plan/decide/compare/review/risk/coordinate/approach/strategy/trade-off).
  A support whose only evidence the lead already owns is not recruited (no duplicate expertise).
* Reserved matters (standards, values, boundaries, ratification, Level 5/6) never recruit for a specialist lead.
* No recruitment is a first-class outcome with a recorded reason: ``disabled``, ``reserved-matter``,
  ``lead-has-no-consult-edges``, ``no-justified-support``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

HEAD = "aoteru"
MAX_SUPPORT = 2
_COMPLEX = re.compile(
    r"\b(plan|planning|decide|decision|compare|review|risk|coordinate|approach|strategy|trade-?off)\b",
    re.IGNORECASE,
)
_RESERVED = re.compile(
    r"\b(?:standards?|values?|boundaries|ratif(?:y|ied|ication))\b|\blevel\s*(?:5|five|6|six)\b",
    re.IGNORECASE,
)


def term_positions(text: str, terms: list[str]) -> list[int]:
    positions = []
    for term in terms:
        match = re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.I)
        if match:
            positions.append(match.start())
    return positions


def intent_hits(prompt: str, intents: list[str]) -> list[str]:
    """The routing intents of one persona that the prompt matches (phrase or any >=3-char part)."""
    normalized_prompt = re.sub(r"[-_]", " ", prompt.lower())
    hits = []
    for intent in intents:
        normalized_intent = re.sub(r"[-_]", " ", intent.lower()).strip()
        terms = [normalized_intent]
        if " " in normalized_intent:
            terms.extend(part for part in normalized_intent.split() if len(part) >= 3)
        if any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", normalized_prompt) for term in terms):
            hits.append(intent)
    return hits


def is_complex(prompt: str) -> bool:
    return bool(_COMPLEX.search(prompt))


def plan_team(
    prompt: str,
    lead: str,
    *,
    policy_order: list[str],
    display_names: Mapping[str, str],
    intents_of: Callable[[str], list[str] | None],
    edges_of: Callable[[str], list[str] | None],
    primary_reply: str = "",
    enabled: bool = True,
    max_support: int = MAX_SUPPORT,
) -> dict[str, Any]:
    """Plan the support personas for one request; always returns a recorded decision."""
    plan: dict[str, Any] = {"lead": lead, "decision": "solo", "supports": [], "excluded": [], "reasons": []}
    if not enabled:
        plan["reasons"].append("disabled")
        return plan
    is_head = lead == HEAD
    if not is_head and _RESERVED.search(prompt):
        plan["reasons"].append("reserved-matter")
        return plan

    edges = [str(item).lower() for item in (edges_of(lead) or [])]
    edges = [item for item in edges if item in policy_order]
    if is_head:
        pool = [item for item in policy_order if item != HEAD]
    else:
        if not edges:
            plan["reasons"].append("lead-has-no-consult-edges")
            return plan
        pool = [item for item in policy_order if item in edges and item not in (HEAD, lead)]

    mention_text = f"{prompt}\n{primary_reply}"
    complex_request = is_complex(prompt)
    lead_hits = set(intent_hits(prompt, intents_of(lead) or [])) if not is_head else set()
    scored: dict[str, dict[str, Any]] = {}
    for item in pool:
        terms = list(dict.fromkeys((item, str(display_names.get(item) or item))))
        mentions = term_positions(mention_text, terms)
        hits = intent_hits(prompt, intents_of(item) or [])
        fresh_hits = [h for h in hits if h not in lead_hits]
        if mentions:
            scored[item] = {"kind": "named", "mentions": mentions, "hits": hits}
        elif fresh_hits and complex_request:
            scored[item] = {"kind": "intent", "mentions": [], "hits": fresh_hits}

    # Named personas that sit outside a specialist lead's edges are explained, not silently dropped.
    if not is_head:
        for item in policy_order:
            if item in (HEAD, lead) or item in pool:
                continue
            terms = list(dict.fromkeys((item, str(display_names.get(item) or item))))
            if term_positions(prompt, terms):
                plan["excluded"].append({"persona": item, "reason": "not-a-consult-edge-of-lead"})

    def rank(item: str) -> tuple[int, int, int, int]:
        info = scored[item]
        if info["mentions"]:
            return (0, min(info["mentions"]), 0, policy_order.index(item))
        return (1, 0, -len(info["hits"]), policy_order.index(item))

    chosen = sorted(scored, key=rank)[:max_support]
    for item in chosen:
        info = scored[item]
        plan["supports"].append({
            "persona": item,
            "kind": info["kind"],
            "evidence": {"named_at": min(info["mentions"]) if info["mentions"] else None,
                         "intents": info["hits"]},
            "edge": item in edges,
        })
    if chosen:
        plan["decision"] = "team"
    else:
        plan["reasons"].append("no-justified-support")
        if not complex_request:
            plan["reasons"].append("no-complex-marker")
    return plan


def risk_flag(contribution: str) -> bool:
    """True when a support opened its contribution with the RISK: marker (a flagged conflict or error)."""
    return str(contribution or "").lstrip().upper().startswith("RISK")


def ok_flag(contribution: str) -> bool:
    """True when a support opened its contribution with the OK: marker (it found no conflict)."""
    return str(contribution or "").lstrip().upper().startswith("OK")


def synthesis_inputs(contributions: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """What the LEAD sees of each support's contribution: only what raised a flag.

    A contribution that explicitly opens with ``OK:`` is DROPPED from the lead's input (the raw text is never lost: callers
    keep the original contributions for the trace, capsules and the ``consulted`` block). Evidence (-11 evaluation v2, qwen3:8b
    judge validated against an audit): passing the OK text through made the lead relay its caveat padding as false alarms on clean
    requests (43% vs 0% solo); replacing it with "no issue found" removed the false alarms but also removed the lead's own
    detection (75% vs 89% solo) because a support that misses about half the real conflicts then reassures the lead. Dropping it
    leaves the lead exactly as it would be alone where the support found nothing, and adds a support's ``RISK:`` where it did.
    ``RISK:`` and legacy-format contributions (no marker) pass through verbatim.
    """
    return [(name, text) for name, text in contributions if not ok_flag(text)]

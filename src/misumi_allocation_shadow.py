"""Shadow persona/specialist allocation proposal (candidate; never changes a live route).

For one request this derives, from evidence the ratified mechanisms already hold, what an allocation WOULD be and why, and returns
a proposal and trace. It is read-only and deterministic (stdlib only, no model or tool calls) and sits beside, not in place of:

* the lead persona, still chosen by routing contract v0.2 (``src/misumi_routing_v02.py``) and returned unchanged as the default;
* team formation, still ``src/misumi_team_formation.plan_team`` (``consults`` edges, at most two supports, temporary task role);
* tool authority, still decided by the runtime policy at execution.

Three things are kept apart. (1) Persona identity: who speaks and in what voice; it is not evidence of competence. (2) The temporary
task-level role: whether a second specialist would plausibly help THIS request, for a named reason. (3) Execution authority: derived
from what the request would do, then only CHECKED against a persona's policy ceiling; selecting a persona never grants a tool.

A specialist is proposed only for an identifiable benefit: a second registered domain is evidenced AND the request asks for a
cross-check across domains, or the user named that persona. Otherwise the proposal is ``solo``. A request no registered domain covers
is ``abstain`` (Aoteru answers directly; no expertise is invented). Reserved matters, privacy-sensitive capture or deletion involving
other people, and actions beyond a specialist's ceiling are ``escalate`` (no specialist, no automatic execution).

The expected benefit of any team is recorded as unproven: the -11 evaluation (``evals/misumi-six-eyes/results``) showed no
established answer-quality gain from consultation and about one extra second of latency, so ``solo`` is the default.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from src.misumi_persona_routing import RESERVED
from src.misumi_routing_v02 import (
    FALLBACK,
    _TOKEN,
    _clauses,
    _negated_stems,
    _strip_meta,
    cue_table,
    resolve_lead,
    stem,
)
from src.misumi_team_formation import MAX_SUPPORT, term_positions

METHOD = "allocation-shadow-v0.1"  # v0.1: review fixes (removal verbs, negated cross-check, ceiling can escalate); v0 was the held-out v1 candidate
LIVE_EFFECT = "none"
HEAD = FALLBACK
# Observed, not predicted: mean extra turn latency of the deployed consultation (teamdrop) versus solo in the -11 evaluation
# (8 distinct tasks; see evals/misumi-six-eyes/results/2026-10-28-team-eval-v2-hierarchical.md). A prior for the operator, nothing more.
LATENCY_PRIOR = {"observed_mean_extra_seconds_per_team_turn": 1.40, "distinct_tasks": 8, "status": "indicative"}

_CROSS_CHECK = re.compile(
    r"\b(?:compare[sd]?|cross-?check(?:s|ed)?|reconcil\w*|contradict\w*|clash(?:es|ed)?|mismatch\w*|inconsisten\w*|discrepan\w*"
    r"|check(?:ed)?\s+(?:\w+\s+){1,4}against|(?:do|does|did)\s+(?:\w+\s+){1,5}match)\b",
    re.IGNORECASE,
)
# a statement of disagreement carries its own "not"; it is evidence of a conflict, not a negated request
_DISAGREE = re.compile(r"\b(?:do|does|did)\s+not\s+(?:seem\s+to\s+)?(?:agree|match|add\s+up)\b|\bdisagree\w*\b", re.IGNORECASE)
_PEOPLE = r"(?:flat-?mates?|house-?mates?|guests?|visitors?|neighbou?rs?|everyone|everybody|people)"
_PRIVACY = re.compile(
    rf"\b(?:record|log|listen|monitor|transcrib\w*|tape|bug)\w*\b[^.?!]*\b{_PEOPLE}\b|\bmicrophones?\b[^.?!]*\b{_PEOPLE}\b|"
    rf"\b{_PEOPLE}\b[^.?!]*\b(?:say|says|said|talk\w*)\b",
    re.IGNORECASE,
)
# What a request would DO, by verb, independent of any persona. Order matters: the first class that matches wins.
_ACTIONS = (
    ("blocked", "email_send", re.compile(r"\b(?:e-?mail|send\s+(?:an?\s+)?(?:e-?mail|message)|post\s+to)\b", re.I)),
    ("blocked", "bank_write", re.compile(r"\b(?:pay|transfer|wire|withdraw|send\s+money)\b", re.I)),
    ("blocked", "destructive_delete", re.compile(
        r"\b(?:delete|erase|wipe|purge|destroy)\b|"
        r"\b(?:remove|trash|get\s+rid\s+of|clear\s+out)\b[^.?!]{0,60}\b(?:recordings?|transcripts?|voice|backups?|archives?)\b",
        re.I)),
    ("playback_control", "playback", re.compile(r"\b(?:play|pause|resume|skip|queue|put\s+on)\b", re.I)),
    ("scoped_write", "scoped_record_write", re.compile(r"\b(?:add|remember|archive|save|update|note\s+that)\b", re.I)),
)


# "don't play anything", "never delete", "no need to email": the verb is forbidden, not requested
_PROHIBITED = re.compile(r"(?:\bdo(?:n't| not)|\bdont|\bnever|\bno need to|\bstop|\bwithout)\s+(?:\w+\s+){0,2}$", re.IGNORECASE)


def _ignore_negated(text: str, pattern: re.Pattern[str]) -> bool:
    """True when ``pattern`` matches in at least one clause where the matched word is not in a withdrawn span."""
    for clause in _clauses(text):
        negated = _negated_stems(clause)
        for match in pattern.finditer(clause):
            words = {stem(t) for t in _TOKEN.findall(match.group(0).lower())}
            if not words & negated and not _PROHIBITED.search(clause[:match.start()]):
                return True
    return False


def required_authority(prompt: str) -> dict[str, Any]:
    """The authority this request would need, from its own words. Never takes a persona: selection cannot grant or change it."""
    cleaned, _ = _strip_meta(str(prompt or ""))
    if _PRIVACY.search(cleaned):
        return {"required": "blocked", "implied_tool": "audio_capture", "reason": "capture-involving-other-people",
                "owner_approval_required": True, "granted": False}
    for authority, tool, pattern in _ACTIONS:
        if _ignore_negated(cleaned, pattern):
            return {"required": authority, "implied_tool": tool, "reason": "request-verb",
                    "owner_approval_required": authority == "blocked", "granted": False}
    return {"required": "none", "implied_tool": None, "reason": "no-action-verb", "owner_approval_required": False, "granted": False}


def domain_evidence(prompt: str, personas: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Per specialist persona, the routing cues (literal labels) the request carries, after the v0.2 meta/negation handling.
    Cue evidence only: it says the request is in a persona's domain, not that the persona is competent."""
    cleaned, _ = _strip_meta(str(prompt or ""))
    table = [(pid, cues) for pid, cues in cue_table(personas) if pid != HEAD]
    found: dict[str, dict[str, Any]] = {}
    for clause in _clauses(cleaned):
        stems = [stem(t) for t in _TOKEN.findall(clause)]
        negated = _negated_stems(clause)
        for pid, cues in table:
            for gram, (weight, label) in cues.items():
                if any(g in negated for g in gram):
                    continue
                if any(tuple(stems[i:i + len(gram)]) == gram for i in range(len(stems) - len(gram) + 1)):
                    entry = found.setdefault(pid, {"score": 0.0, "cues": []})
                    if label not in entry["cues"]:
                        entry["score"] += weight
                        entry["cues"].append(label)
    return found


def propose(
    prompt: str,
    personas: Mapping[str, Any] | None,
    *,
    prior_lead: str | None = None,
    policy_order: list[str] | None = None,
    display_names: Mapping[str, str] | None = None,
    blocked_tools_of: Any = None,
    production_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the shadow allocation proposal and trace for one request. ``live_effect`` is always ``none``."""
    personas = personas if isinstance(personas, Mapping) else {}
    text = str(prompt or "")
    lead, routing = resolve_lead(text, personas, prior_lead)
    authority = required_authority(text)
    order = [p for p in (policy_order if policy_order is not None else personas) if p in personas]
    names = display_names or {p: str(personas[p].get("name") or p).split()[0] for p in personas if isinstance(personas.get(p), Mapping)}
    evidence = domain_evidence(text, personas)
    carried = any(str(r).startswith("carry:") for r in routing.get("reasons", []))

    proposal: dict[str, Any] = {
        "method": METHOD, "live_effect": LIVE_EFFECT, "decision": "solo", "lead": lead, "lead_source": routing.get("method"),
        "supports": [], "excluded": [], "reasons": [], "authority": authority,
        "eligible": [], "adequacy": {"solo_adequate": True, "deterministic_path": "not assessed (none registered with this module)"},
        "overhead": {"expected_extra_model_calls": 0, "latency_prior": LATENCY_PRIOR},
        "uncertainty": [], "limitations": [
            "cue evidence only: a persona's routing words are not evidence of competence",
            "expected benefit of any support is unproven (see -11 evaluation)",
            "required authority is inferred from the request's verbs and is advisory; the runtime policy still enforces at execution",
        ],
    }

    escalations = []
    if RESERVED.search(text):
        escalations.append("reserved-matter")
    if authority["required"] == "blocked":
        escalations.append(f"authority-beyond-ceiling:{authority['implied_tool']}")
    elif authority.get("implied_tool") and callable(blocked_tools_of):
        # The persona only CHECKS the ceiling; it never changes what is required. A lead whose policy blocks the tool needs escalation.
        try:
            if authority["implied_tool"] in set(blocked_tools_of(lead) or []):
                escalations.append(f"blocked-for-lead:{authority['implied_tool']}")
        except Exception:
            proposal["uncertainty"].append("the persona policy could not be read, so the lead's tool ceiling was not checked")
    if escalations:
        proposal.update(decision="escalate", reasons=escalations)
        proposal["adequacy"]["solo_adequate"] = False
        proposal["lead"] = HEAD if lead == HEAD or "reserved-matter" in escalations else lead
        return _finish(proposal, production_plan, blocked_tools_of)

    if lead == HEAD and not evidence:
        proposal.update(decision="abstain", reasons=["no-registered-domain"])
        proposal["uncertainty"].append("no specialist cue found; Aoteru answers directly and invents no expertise")
        return _finish(proposal, production_plan, blocked_tools_of)

    edges = [str(e).lower() for e in (personas.get(lead, {}).get("consults") or [])] if lead != HEAD else []
    pool = [p for p in order if p not in (HEAD, lead) and p in evidence]
    if lead != HEAD:
        pool = [p for p in pool if p in edges]
    named = {p for p in pool if term_positions(text, list(dict.fromkeys((p, names.get(p, p)))))}
    cross_check = _ignore_negated(text, _CROSS_CHECK) or bool(_DISAGREE.search(text))  # "do not compare X" is not a request to cross-check

    off_edge = [p for p in order if p in evidence and p not in (HEAD, lead) and lead != HEAD and p not in edges
                and (cross_check or term_positions(text, list(dict.fromkeys((p, names.get(p, p))))))]
    proposal["excluded"] = [{"persona": p, "reason": "not-a-consult-edge-of-lead"} for p in off_edge]
    chosen = []
    for persona in sorted(pool, key=lambda p: (p not in named, -evidence[p]["score"], order.index(p))):
        if persona in named:
            benefit = "user_named"
        elif cross_check and not carried:
            benefit = "cross_domain_verification"
        else:
            continue
        chosen.append((persona, benefit))
    for persona, benefit in chosen[:MAX_SUPPORT]:
        proposal["supports"].append({
            "persona": persona, "benefit": benefit, "expected_benefit_status": "unproven",
            "evidence": {"cues": evidence[persona]["cues"], "score": evidence[persona]["score"]},
            "edge": persona in edges or lead == HEAD, "competence_evidence": "routing-cues-only",
        })
    proposal["eligible"] = [{"persona": p, "cues": evidence[p]["cues"], "edge": p in edges or lead == HEAD,
                             "uncertainty": "high" if evidence[p]["score"] < 1.0 else "low"} for p in order if p in evidence and p != HEAD]
    if proposal["supports"]:
        proposal["decision"] = "team"
        proposal["adequacy"]["solo_adequate"] = False
        proposal["reasons"] = [s["benefit"] for s in proposal["supports"]]
    else:
        proposal["reasons"] = ["single-domain" if len(evidence) <= 1 else "no-cross-domain-check-or-named-persona"]
        if off_edge:
            proposal["reasons"].append("second-domain-is-not-a-consult-edge")
        if cross_check and len(evidence) <= 1:
            proposal["reasons"].append("cross-check-within-one-domain")
    proposal["overhead"]["expected_extra_model_calls"] = len(proposal["supports"])
    tied = sorted(evidence.items(), key=lambda kv: -kv[1]["score"])
    if len(tied) > 1 and tied[0][1]["score"] == tied[1][1]["score"]:
        proposal["uncertainty"].append(f"lead is a manifest-order tie-break between {tied[0][0]} and {tied[1][0]}")
    return _finish(proposal, production_plan, blocked_tools_of)


def _finish(proposal: dict[str, Any], production_plan: Mapping[str, Any] | None, blocked_tools_of: Any) -> dict[str, Any]:
    """Attach the ceiling check (information only) and the production comparison, then return."""
    authority = proposal["authority"]
    if callable(blocked_tools_of) and authority.get("implied_tool"):
        try:
            blocked = set(blocked_tools_of(proposal["lead"]) or [])
        except Exception:  # a policy that cannot be read is reported, never assumed permissive
            blocked = None
        authority["ceiling_check"] = "policy-unreadable" if blocked is None else (
            "blocked-for-lead" if authority["implied_tool"] in blocked else "not-listed-as-blocked-for-lead")
    if production_plan is not None:
        prod = [s["persona"] for s in production_plan.get("supports", [])]
        proposal["production"] = {"decision": production_plan.get("decision"), "supports": prod,
                                  "supports_agree": sorted(prod) == sorted(s["persona"] for s in proposal["supports"])}
    return proposal

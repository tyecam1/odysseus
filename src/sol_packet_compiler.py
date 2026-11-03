"""Deterministic Sol packet admission and compilation (pure functions, no I/O, no routing).

Implements the checklist in automation/review/models/2026-10-01-sol-packet-efficiency.md:
decide whether several pending strong-model decisions may share ONE invocation, compile
the shared request, and parse per-item results. It does not dispatch, schedule or queue
anything, and it is not wired into routing: callers pass in already-prepared items.

Fail-closed everywhere: an unknown value never admits a batch. A mandatory independent or
fresh-context check can never be co-located. Every refusal carries a stable reason code so
routing can record why an item was batched or sent alone.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Mapping, Optional, Sequence

PACKET_CLASSES = ("decision", "verification", "collision", "gate")
VERIFICATION_VERDICTS = ("PASS", "REVISE", "ESCALATE")
NO_DEADLINE = "none"  # the explicit no-deadline value; a missing deadline is NOT assumed to be none

# Outcomes for one item or group.
BATCH = "BATCH"
SINGLE = "SINGLE"
NEEDS_PREPARATION = "NEEDS_PREPARATION"
REUSE = "REUSE"


@dataclass(frozen=True)
class Item:
    decision_id: str
    parent_task: str
    role_required: str
    question: str
    decision_type: str
    consequence: str
    packet_class: str
    evidence_pointers: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    allowed_verdicts: tuple[str, ...]
    deadline: Optional[str]                      # ISO-8601 timestamp or NO_DEADLINE
    independence_required: Optional[bool]        # None = not established
    candidate_options: tuple[str, ...] = ()
    open_judgment: bool = False                  # options may be empty only when True
    shared_context_key: Optional[str] = None
    context_manifest_hash: Optional[str] = None  # hash of the exact versioned shared sources
    context_tokens: Optional[int] = None         # size of the shared context this item needs
    unique_tokens: Optional[int] = None          # item-specific evidence + question + schema
    output_reserve_tokens: Optional[int] = None
    question_id: Optional[str] = None            # scientific question (collision) or gate id (gate)
    fresh_context_required: bool = False
    separate_adjudication_required: bool = False  # high-consequence items needing their own call
    urgent: bool = False
    blocking: bool = False
    depends_on: tuple[str, ...] = ()
    exposes_label_of: tuple[str, ...] = ()


@dataclass(frozen=True)
class Policy:
    """Governed numbers. Any None means 'not established', which refuses batching."""
    role_equivalence: Mapping[str, str] = field(default_factory=dict)
    min_net_reuse_tokens: Optional[int] = None
    wrapper_overhead_tokens: Optional[int] = None
    max_input_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None
    max_items: Optional[int] = None
    headroom_tokens: Optional[int] = None
    wait_benefit_lower_bound: Optional[float] = None
    urgency_cost_upper_bound: Optional[float] = None
    max_wait_seconds: Optional[float] = None
    evidence_version: Optional[str] = None       # recorded with every decision for auditability


@dataclass(frozen=True)
class Decision:
    outcome: str                                  # BATCH / SINGLE / NEEDS_PREPARATION
    reason: str                                   # stable code
    detail: tuple[str, ...] = ()


@dataclass(frozen=True)
class Group:
    items: tuple[Item, ...]
    decision: Decision


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def parse_deadline(value: Optional[str]) -> Optional[datetime]:
    """None for NO_DEADLINE; raises ValueError for a missing or malformed value."""
    if value == NO_DEADLINE:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("deadline must be an ISO-8601 timestamp or the explicit value 'none'")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("deadline must carry a timezone")
    return parsed


def validate_item(item: Item) -> list[str]:
    """Reasons an item is not decision-ready; empty means it may be considered."""
    problems = []
    for name in ("decision_id", "parent_task", "role_required", "question", "decision_type", "consequence"):
        if not isinstance(getattr(item, name), str) or not getattr(item, name).strip():
            problems.append("missing_" + name)
    if item.packet_class not in PACKET_CLASSES:
        problems.append("unknown_packet_class")
    if not item.evidence_pointers:
        problems.append("missing_evidence_pointers")
    if not item.acceptance_criteria:
        problems.append("missing_acceptance_criteria")
    if not item.allowed_verdicts:
        problems.append("missing_allowed_verdicts")
    if item.packet_class == "verification" and set(item.allowed_verdicts) != set(VERIFICATION_VERDICTS):
        problems.append("verification_verdicts_must_be_pass_revise_escalate")
    if not item.candidate_options and not item.open_judgment:
        problems.append("missing_candidate_options")
    try:
        parse_deadline(item.deadline)
    except (ValueError, TypeError):
        problems.append("deadline_not_explicit")
    if item.packet_class in ("collision", "gate") and not item.question_id:
        problems.append("missing_question_id")
    return problems


def _role(item: Item, policy: Policy) -> str:
    # A governed explicit map only; unknown roles are never approximately matched.
    return policy.role_equivalence.get(item.role_required, item.role_required)


def _manifest_hash(item: Item) -> str:
    body = json.dumps([item.question, sorted(item.evidence_pointers), sorted(item.candidate_options),
                       sorted(item.acceptance_criteria), item.context_manifest_hash], ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def manifest_hash(item: Item) -> str:
    """Hash of everything that defines the question; unchanged hash means unchanged conclusion."""
    return _manifest_hash(item)


def _single(reason: str, *detail: str) -> Decision:
    return Decision(SINGLE, reason, tuple(detail))


def admit(group: Sequence[Item], policy: Policy, certificates: Iterable[frozenset],
          now: datetime, wait_seconds: Optional[float]) -> Decision:
    """The six conjunctive admission tests for a candidate group of two or more items.

    `certificates` holds frozenset({id_a, id_b}) pairs certified non-contaminating, each
    backed by evidence the caller recorded. Returns BATCH only if every test passes.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    items = list(group)
    if len(items) < 2:
        return _single("no_compatible_pending")
    ids = [item.decision_id for item in items]
    if len(set(ids)) != len(ids):
        return Decision(NEEDS_PREPARATION, "duplicate_decision_id")
    for item in items:
        problems = validate_item(item)
        if problems:
            return Decision(NEEDS_PREPARATION, "item_not_decision_ready", (item.decision_id, *problems))

    # 1. Same normalised role, protocol and compatible packet class.
    if len({_role(item, policy) for item in items}) != 1 or len({item.packet_class for item in items}) != 1:
        return _single("role_or_class_mismatch")
    if items[0].packet_class in ("collision", "gate") and len({item.question_id for item in items}) != 1:
        return _single("question_identity_mismatch")

    # 2. Substantial reusable context, measured, with a governed threshold.
    keys = {item.shared_context_key for item in items}
    hashes = {item.context_manifest_hash for item in items}
    if None in keys or None in hashes or len(keys) != 1 or len(hashes) != 1:
        return _single("context_reuse_unestablished", "no identical versioned context manifest")
    sizes = {item.context_tokens for item in items}
    if len(sizes) != 1 or not _is_int(next(iter(sizes))):
        return _single("context_reuse_unestablished", "context size unknown or inconsistent")
    if not _is_int(policy.min_net_reuse_tokens) or not _is_int(policy.wrapper_overhead_tokens):
        return _single("context_reuse_unestablished", "no evidence-backed reuse threshold")
    net_reuse = (len(items) - 1) * next(iter(sizes)) - policy.wrapper_overhead_tokens
    if net_reuse <= 0 or net_reuse < policy.min_net_reuse_tokens:
        return _single("context_reuse_insufficient", "net_reuse_tokens=%d" % net_reuse)

    # 3. Independence preserved: known vetoes first, then missing proof.
    id_set = set(ids)
    for item in items:
        if item.independence_required or item.fresh_context_required or item.separate_adjudication_required:
            return _single("independence_required", item.decision_id)
        if set(item.depends_on) & id_set or set(item.exposes_label_of) & id_set:
            return _single("independence_required", item.decision_id, "dependency_or_label_exposure")
    if any(item.independence_required is None for item in items):
        return _single("independence_unestablished", "independence_required not established")
    certified = {frozenset(pair) for pair in certificates}
    for i in range(len(ids)):                       # all pairs: no transitive chaining
        for j in range(i + 1, len(ids)):
            if frozenset((ids[i], ids[j])) not in certified:
                return _single("independence_unestablished", ids[i], ids[j])

    # 4. Comfortable capacity: shared context once, every unique part, reserves and headroom.
    limits = (policy.max_input_tokens, policy.max_output_tokens, policy.max_items, policy.headroom_tokens)
    if not all(_is_int(v) for v in limits) or not all(_is_int(i.unique_tokens) and _is_int(i.output_reserve_tokens) for i in items):
        return _single("capacity_unestablished_or_exceeded", "limits or per-item sizes unknown")
    total_input = next(iter(sizes)) + sum(i.unique_tokens for i in items) + policy.wrapper_overhead_tokens + policy.headroom_tokens
    total_output = sum(i.output_reserve_tokens for i in items) + policy.headroom_tokens
    if (total_input > policy.max_input_tokens or total_output > policy.max_output_tokens
            or len(items) > policy.max_items):
        return _single("capacity_unestablished_or_exceeded", "input=%d output=%d" % (total_input, total_output))

    # 5. Attribution complete is enforced per item by validate_item (ids, questions, pointers,
    #    criteria, allowed verdicts); parse_results later requires a parsable result per id.

    # 6. Waiting justified, and no deadline broken by the wait.
    if any(item.urgent or item.blocking for item in items):
        return _single("urgent_or_blocking_item")
    if (wait_seconds is None or policy.wait_benefit_lower_bound is None or policy.urgency_cost_upper_bound is None
            or policy.max_wait_seconds is None):
        return _single("wait_not_justified", "no evidence-backed accumulation bounds")
    if wait_seconds > policy.max_wait_seconds or policy.wait_benefit_lower_bound <= policy.urgency_cost_upper_bound:
        return _single("wait_not_justified")
    for item in items:
        deadline = parse_deadline(item.deadline)
        if deadline is not None and (deadline - now).total_seconds() < wait_seconds:
            return _single("wait_not_justified", "deadline_before_dispatch", item.decision_id)
    return Decision(BATCH, "all_admission_tests_passed", ("policy=" + str(policy.evidence_version),))


def _sort_key(item: Item):
    deadline = parse_deadline(item.deadline)
    return (deadline is None, deadline.timestamp() if deadline else 0.0, item.decision_id)  # no-deadline sorts last


def plan(items: Sequence[Item], policy: Policy, certificates: Iterable[frozenset],
         now: datetime, wait_seconds: Optional[float]) -> list[Group]:
    """Deterministic grouping: stable order, add an item only if the WHOLE candidate re-passes
    every test. Not an optimal-packing claim, and it creates no pending-work store."""
    certificates = [frozenset(pair) for pair in certificates]
    groups: list[Group] = []
    ready, not_ready = [], []
    for item in items:
        problems = validate_item(item)
        (not_ready if problems else ready).append((item, problems))
    for item, problems in not_ready:
        groups.append(Group((item,), Decision(NEEDS_PREPARATION, "item_not_decision_ready", tuple(problems))))
    ordered = [item for item, _ in sorted(ready, key=lambda pair: _sort_key(pair[0]))]
    pending = list(ordered)
    while pending:
        current = [pending.pop(0)]
        last_refusal = _single("no_compatible_pending")
        for candidate in list(pending):
            verdict = admit(current + [candidate], policy, certificates, now, wait_seconds)
            if verdict.outcome == BATCH:
                current.append(candidate)
                pending.remove(candidate)
            else:
                last_refusal = verdict
        if len(current) > 1:
            groups.append(Group(tuple(current), admit(current, policy, certificates, now, wait_seconds)))
        else:
            groups.append(Group(tuple(current), _singleton_decision(current[0], policy, last_refusal)))
    return groups


def _singleton_decision(item: Item, policy: Policy, refusal: Decision) -> Decision:
    """A lone item is sent alone with the recorded reason, unless it cannot safely fit at all."""
    if (_is_int(policy.max_input_tokens) and _is_int(item.context_tokens) and _is_int(item.unique_tokens)
            and item.context_tokens + item.unique_tokens > policy.max_input_tokens):
        return Decision(NEEDS_PREPARATION, "singleton_exceeds_capacity")
    return Decision(SINGLE, refusal.reason if refusal.outcome == SINGLE else "no_compatible_pending", refusal.detail)


def compile_packet(group: Sequence[Item], packet_id: str, shared_context: str, global_constraints: Sequence[str]) -> str:
    """The structured request: shared context and constraints once, then each item whole."""
    if not group:
        raise ValueError("cannot compile an empty packet")
    parts = ["PACKET " + packet_id, "CLASS " + group[0].packet_class,
             "GLOBAL CONSTRAINTS", *("- " + c for c in global_constraints),
             "SHARED CONTEXT (once)", shared_context, ""]
    for index, item in enumerate(group, 1):
        parts += ["ITEM %d id=%s" % (index, item.decision_id), "question: " + item.question,
                  "evidence: " + "; ".join(item.evidence_pointers),
                  "options: " + ("; ".join(item.candidate_options) or "(open judgment)"),
                  "acceptance: " + "; ".join(item.acceptance_criteria),
                  "allowed verdicts: " + ", ".join(item.allowed_verdicts), ""]
    parts += ['Return ONE JSON object: {"results": [{"decision_id": "...", "verdict": "...", "rationale": "...", '
              '"evidence_refs": ["..."], "uncertainty": "...", "another_strong_call_could_change": true|false}]} '
              'with exactly one entry per item id above. An item you cannot decide gets verdict ESCALATE or one of its '
              'allowed verdicts plus the uncertainty; never omit an id.']
    return "\n".join(parts)


@dataclass(frozen=True)
class ItemResult:
    decision_id: str
    verdict: str
    rationale: str
    evidence_refs: tuple[str, ...]
    uncertainty: str
    another_call_could_change: bool


def parse_results(group: Sequence[Item], raw: str) -> dict[str, "ItemResult | str"]:
    """One entry per requested id: an ItemResult, or the reason that id is unresolved.
    A bad or missing entry never invalidates the others."""
    out: dict[str, "ItemResult | str"] = {item.decision_id: "missing_result" for item in group}
    try:
        payload = json.loads(raw)
        entries = payload["results"]
        if not isinstance(entries, list):
            raise TypeError
    except (ValueError, KeyError, TypeError):
        return {key: "unparsable_packet_output" for key in out}
    allowed = {item.decision_id: item.allowed_verdicts for item in group}
    seen: set[str] = set()
    for entry in entries:
        ident = entry.get("decision_id") if isinstance(entry, dict) else None
        if not isinstance(ident, str) or ident not in allowed:
            continue                                  # unknown id: ignored, not trusted
        if ident in seen:
            out[ident] = "duplicate_result"
            continue
        seen.add(ident)
        refs = entry.get("evidence_refs")
        if (entry.get("verdict") not in allowed[ident] or not isinstance(entry.get("rationale"), str)
                or not entry["rationale"].strip() or not isinstance(refs, list) or not all(isinstance(r, str) for r in refs)
                or not isinstance(entry.get("uncertainty"), str)
                or not isinstance(entry.get("another_strong_call_could_change"), bool)):
            out[ident] = "malformed_result"
            continue
        out[ident] = ItemResult(ident, entry["verdict"], entry["rationale"], tuple(refs), entry["uncertainty"],
                                entry["another_strong_call_could_change"])
    return out


FOLLOW_UP_TRIGGERS = ("malformed_packet", "new_evidence", "consequential_defect", "ambiguity_over_threshold")


def needs_new_call(item: Item, prior_manifest_hash: Optional[str], triggers: Iterable[str] = ()) -> Decision:
    """Follow-up suppression: an unchanged question reuses its prior conclusion unless a
    declared trigger fired. Never suppresses a still-required independent or fresh check."""
    if item.independence_required or item.fresh_context_required:
        return Decision(SINGLE, "independent_check_still_required")
    fired = [t for t in triggers if t in FOLLOW_UP_TRIGGERS]
    if fired:
        return Decision(SINGLE, "follow_up_trigger", tuple(fired))
    if prior_manifest_hash is not None and prior_manifest_hash == manifest_hash(item):
        return Decision(REUSE, "unchanged_conclusion")
    return Decision(SINGLE, "no_prior_or_changed_question")

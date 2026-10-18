"""Deterministic support for the global initialising-prompt evolution graph.

This module never rewrites prompt prose. It turns a rated application trace into
an evolution plan and validates the provenance metadata of a semantic child
drafted by an agent. Existing prompt versions remain immutable.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

RATING_FIELDS = (
    "goal_progress",
    "correctness_verification",
    "authority_scope_discipline",
    "routing_resource_efficiency",
    "continuity_handoff_quality",
)

FAILURE_TARGETS = {
    "long_horizon_early_return": "strengthen the no-voluntary-checkpoint-stop gate",
    "registered_prompt_resolution_missed": "make prompt id/version self-identifying and registry-resolvable",
    "global_application_trace_omitted_at_closeout": "make trace closeout explicit and mechanically checkable",
    "rabby_public_fulltext_route_missed": "require alternate lawful public-full-text routes before access blocking",
    "sol_runtime_policy_identity_drift": "require live model-policy/runtime identity reconciliation before consequential dispatch",
}

DIMENSION_TARGETS = {
    "goal_progress": "reduce avoidable frontier stalls and unfinished dependency-ready work",
    "correctness_verification": "strengthen verification at the observed failure site without blanket review",
    "authority_scope_discipline": "clarify authority/scope binding where the session drifted",
    "routing_resource_efficiency": "improve routing economy at the observed bottleneck",
    "continuity_handoff_quality": "strengthen traceability, closeout and next-session continuity",
}


@dataclass(frozen=True)
class EvolutionPlan:
    prompt_id: str
    parent_version: int
    application_id: str
    decision: str
    targets: tuple[str, ...]
    next_version: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "parent_version": self.parent_version,
            "application_id": self.application_id,
            "decision": self.decision,
            "targets": list(self.targets),
            "next_version": self.next_version,
        }


def calculated_overall(trace: dict[str, Any]) -> float:
    rating = trace.get("rating") or {}
    values = [rating.get(field) for field in RATING_FIELDS]
    if any(not isinstance(v, (int, float)) for v in values):
        raise ValueError("all five rating dimensions must be numeric")
    return round(mean(values), 1)


def derive_targets(trace: dict[str, Any]) -> tuple[str, ...]:
    targets: list[str] = []
    seen: set[str] = set()

    def add(target: str) -> None:
        if target not in seen:
            seen.add(target)
            targets.append(target)

    for tag in trace.get("failure_tags") or []:
        add(FAILURE_TARGETS.get(tag, f"address observed failure tag: {tag}"))

    rating = trace.get("rating") or {}
    for field in RATING_FIELDS:
        value = rating.get(field)
        if isinstance(value, (int, float)) and value <= 3:
            add(DIMENSION_TARGETS[field])

    operator_note = rating.get("operator_note")
    if operator_note:
        add("incorporate explicit operator feedback: " + str(operator_note).strip())

    return tuple(targets)


def plan_evolution(trace: dict[str, Any]) -> EvolutionPlan:
    prompt_id = str(trace.get("prompt_id") or "").strip()
    application_id = str(trace.get("application_id") or "").strip()
    parent_version = trace.get("prompt_version")
    if not prompt_id or not application_id or not isinstance(parent_version, int):
        raise ValueError("trace requires prompt_id, application_id and integer prompt_version")

    expected = calculated_overall(trace)
    recorded = (trace.get("rating") or {}).get("agent_overall")
    if isinstance(recorded, (int, float)) and abs(float(recorded) - expected) > 0.05:
        raise ValueError(f"agent_overall {recorded} does not match calculated mean {expected}")

    targets = derive_targets(trace)
    if targets:
        return EvolutionPlan(prompt_id, parent_version, application_id, "evolve", targets, parent_version + 1)
    return EvolutionPlan(prompt_id, parent_version, application_id, "reinforce", (), None)


def validate_child_metadata(
    parent_prompt_id: str,
    parent_version: int,
    application_id: str,
    child_metadata: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if child_metadata.get("prompt_id") != parent_prompt_id:
        errors.append("prompt_id must match parent")
    if child_metadata.get("version") != parent_version + 1:
        errors.append("child version must equal parent_version + 1")
    if child_metadata.get("parent_version") != parent_version:
        errors.append("parent_version must point to the exact parent")
    derived = child_metadata.get("derived_from_applications") or []
    if application_id not in derived:
        errors.append("derived_from_applications must contain the triggering application")
    return errors


def graph_edges_for_plan(plan: EvolutionPlan) -> list[dict[str, str]]:
    prompt_node = f"prompt:v{plan.parent_version}"
    app_node = f"application:{plan.application_id}"
    event_node = f"evolution:{plan.application_id}"
    edges = [
        {"from": prompt_node, "to": app_node, "type": "applied"},
        {"from": app_node, "to": event_node, "type": "observed"},
    ]
    if plan.decision == "evolve":
        edges.append({"from": event_node, "to": f"prompt:v{plan.next_version}", "type": "derived_child"})
    else:
        edges.append({"from": event_node, "to": prompt_node, "type": "reinforced"})
    return edges

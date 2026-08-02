"""Stable capability-graph schema constants."""

SCHEMA_VERSION = 1
ADAPTER_VERSION = "1.0.0"

NODE_TYPES = frozenset({
    "intent",
    "task_class",
    "repository",
    "authority",
    "precondition",
    "context_source",
    "skill",
    "model_profile",
    "tool",
    "permission",
    "action",
    "artifact",
    "validator",
    "failure_mode",
    "fallback",
    "escalation",
    "human_gate",
    "outcome",
    "evaluation_case",
})

EDGE_TYPES = frozenset({
    "routes_to",
    "requires",
    "reads",
    "may_write",
    "forbids",
    "uses_skill",
    "uses_model",
    "uses_tool",
    "validated_by",
    "falls_back_to",
    "escalates_to",
    "derived_from",
    "supersedes",
    "blocked_by",
    "produces",
})

PROVENANCE_FIELDS = (
    "source_repo",
    "source_path",
    "source_revision",
    "source_sha256",
    "extracted_at",
    "adapter_name",
    "adapter_version",
)

FORBIDDEN_REASONING_KEYS = frozenset({
    "chain_of_thought",
    "chain-of-thought",
    "cot",
    "hidden_reasoning",
    "rationale",
    "reasoning",
    "thoughts",
})


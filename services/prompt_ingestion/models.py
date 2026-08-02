"""Data contracts for external pattern ingestion.

Every unknown value is represented by an explicit state string. ``None``, an
empty string, or an absent required key is invalid metadata, because absence of
evidence must never be interpreted as a benign result.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional


STAGES = (
    "discover",
    "snapshot",
    "identify",
    "licence-check",
    "hash",
    "quarantine",
    "security-scan",
    "classify",
    "deduplicate",
    "evaluate",
    "adapt",
    "review",
    "activate",
)

REQUIRED_METADATA = (
    "repository_owner",
    "repository_name",
    "commit_or_release",
    "licence",
    "retrieved_date",
    "source_path",
    "source_hash",
    "intended_capability",
    "required_tools",
    "required_permissions",
    "assumed_environment",
    "prompt_injection_risk",
    "overlapping_local_skill",
    "evaluation_corpus",
    "adaptation_decision",
    "status",
    "retirement_condition",
)


class MetadataError(ValueError):
    """Candidate metadata is absent rather than explicitly undetermined."""


@dataclass
class StageResult:
    stage: str
    state: str
    completed: bool
    detail: str


@dataclass
class EvaluationResult:
    corpus_id: str
    corpus_hash: str
    baseline_score: float
    candidate_score: float
    delta: float
    case_count: int
    corpus_created: str


@dataclass
class AdaptationProposal:
    name: str
    principle: str
    when_to_use: str
    procedure: List[str]
    verification: List[str]
    required_tools: List[str]
    required_permissions: List[str]
    target: str = "existing-skill-registry"


@dataclass
class CandidateRecord:
    candidate_id: str
    repository_url: str
    provenance: str
    capability_family: str
    repository_owner: str
    repository_name: str
    commit_or_release: str
    licence: str
    retrieved_date: str
    source_path: str
    source_hash: str
    intended_capability: str
    required_tools: List[str]
    required_permissions: List[str]
    assumed_environment: str
    prompt_injection_risk: str
    overlapping_local_skill: str
    evaluation_corpus: str
    adaptation_decision: str
    status: str
    retirement_condition: str
    stage_results: Dict[str, StageResult] = field(default_factory=dict)
    snapshot_history: List[Dict[str, str]] = field(default_factory=list)
    current_snapshot_id: str = "not-snapshotted"
    quarantine_path: str = "not-quarantined"
    evaluation_result: Optional[EvaluationResult] = None
    adapted_artifact_path: str = "not-adapted"
    activated_skill_name: str = "not-activated"
    terminal_state: str = "not-terminal"
    terminal_reason: str = "not-terminal"

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "CandidateRecord":
        missing = [key for key in REQUIRED_METADATA if key not in raw]
        if missing:
            raise MetadataError("missing required metadata: " + ", ".join(missing))
        invalid = [
            key for key in REQUIRED_METADATA
            if raw.get(key) is None or (isinstance(raw.get(key), str) and not raw[key].strip())
        ]
        if invalid:
            raise MetadataError("undetermined metadata must be explicit: " + ", ".join(invalid))
        data = dict(raw)
        stage_results = data.get("stage_results") or {}
        data["stage_results"] = {
            key: value if isinstance(value, StageResult) else StageResult(**value)
            for key, value in stage_results.items()
        }
        evaluation = data.get("evaluation_result")
        if evaluation and not isinstance(evaluation, EvaluationResult):
            data["evaluation_result"] = EvaluationResult(**evaluation)
        return cls(**data)

    def validate_required_metadata(self) -> None:
        self.from_dict(self.to_dict())

    def record_stage(self, result: StageResult) -> StageResult:
        if result.stage not in STAGES:
            raise ValueError(f"unknown stage: {result.stage}")
        self.stage_results[result.stage] = result
        if result.completed:
            self.status = result.stage
        return result

    def reject(self, reason: str) -> StageResult:
        self.terminal_state = "reject"
        self.terminal_reason = reason
        return StageResult("activate", "rejected", False, reason)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

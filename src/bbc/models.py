"""Versioned machine-readable BBC Odysseus domain contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


API_VERSION = "bbc/v1"
SCHEMA_VERSION = 1


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class Point(ContractModel):
    x: float
    y: float


class Room(ContractModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,79}$")
    name: str = Field(min_length=1, max_length=120)
    function: str = Field(min_length=1, max_length=240)
    deck: int = Field(default=1, ge=1)
    position: Point
    size: Point
    occupant_ids: List[str] = Field(default_factory=list)
    active: bool = True


class Ship(ContractModel):
    id: str
    name: str
    deck_count: int = Field(default=1, ge=1)
    active_room_id: str
    rooms: List[Room]
    updated_at: datetime = Field(default_factory=utc_now)


class PersonaLocation(ContractModel):
    persona_id: str
    room_id: str
    navigation_transaction_id: Optional[str] = None
    updated_at: datetime = Field(default_factory=utc_now)


class Persona(ContractModel):
    id: str
    name: str
    role: str
    location: Optional[PersonaLocation] = None


class CapabilityKind(str, Enum):
    capability = "capability"
    skill = "skill"
    connector = "connector"
    plugin = "plugin"
    mcp = "mcp"


class CapabilityHealth(ContractModel):
    state: Literal["healthy", "degraded", "unavailable", "unknown"] = "unknown"
    checked_at: datetime = Field(default_factory=utc_now)
    detail: Optional[str] = None


class CapabilitySummary(ContractModel):
    id: str
    version: str
    name: str
    description: str
    kind: CapabilityKind = CapabilityKind.capability
    owner: str
    scope: List[str]
    permissions: List[str]
    health: CapabilityHealth
    context_cost: int = Field(ge=0)
    overlap_group: Optional[str] = None
    replacement_status: Literal["active", "deprecated", "replaced", "quarantined"] = "active"


class Capability(CapabilitySummary):
    provenance: List[str]
    licence: str
    inputs_schema: Dict[str, Any]
    outputs_schema: Dict[str, Any]
    dependencies: List[str] = Field(default_factory=list)
    target_adapters: List[str] = Field(default_factory=list)
    instructions: str = ""
    replaced_by: Optional[str] = None
    tests: List[str] = Field(default_factory=list)


class DifficultyComponents(ContractModel):
    blocker_severity: int = Field(default=0, ge=0, le=100)
    blocker_count: int = Field(default=0, ge=0, le=100)
    external_dependency: int = Field(default=0, ge=0, le=100)
    cross_repository_dependency: int = Field(default=0, ge=0, le=100)
    unresolved_uncertainty: int = Field(default=0, ge=0, le=100)
    test_gap: int = Field(default=0, ge=0, le=100)
    deployment_surface: int = Field(default=0, ge=0, le=100)
    rollback_risk: int = Field(default=0, ge=0, le=100)
    implementation_complexity: int = Field(default=0, ge=0, le=100)


class DifficultyExplanation(ContractModel):
    version: str = "1.0"
    score: int = Field(ge=0, le=100)
    band: Literal["low", "medium", "high"]
    components: DifficultyComponents
    weights: Dict[str, float]
    rationale: List[str]


class Provenance(ContractModel):
    repository_id: str
    path: str
    line_start: Optional[int] = Field(default=None, ge=1)
    line_end: Optional[int] = Field(default=None, ge=1)
    source_kind: str
    content_hash: str


class RepositorySystem(ContractModel):
    id: str
    name: str
    adapter: str
    mode: Literal["read_only"] = "read_only"
    configured: bool
    reachable: bool
    revision: Optional[str] = None
    work_stream_count: int = 0
    work_node_count: int = 0
    ambiguity_count: int = 0
    error: Optional[str] = None


class WorkStream(ContractModel):
    id: str
    repository_id: str
    title: str
    lane: int = Field(default=0, ge=0)
    node_ids: List[str] = Field(default_factory=list)


class WorkNodeState(str, Enum):
    planned = "planned"
    active = "active"
    paused = "paused"
    blocked = "blocked"
    review = "review"
    completed = "completed"
    superseded = "superseded"
    archived = "archived"


class WorkNode(ContractModel):
    id: str
    repository_id: str
    stream_id: str
    canonical_key: str
    aliases: List[str] = Field(default_factory=list)
    title: str
    outcome: str
    state: WorkNodeState
    owner: Optional[str] = None
    next_action: Optional[str] = None
    blocker_ids: List[str] = Field(default_factory=list)
    dependency_ids: List[str] = Field(default_factory=list)
    acceptance_evidence: List[str] = Field(default_factory=list)
    source_links: List[str] = Field(default_factory=list)
    provenance: List[Provenance]
    lineage: List[str] = Field(default_factory=list)
    archived: bool = False
    superseded: bool = False
    difficulty: DifficultyExplanation


class AmbiguityCandidate(ContractModel):
    node_id: str
    title: str
    state: WorkNodeState
    archived: bool = False
    superseded: bool = False
    provenance: List[Provenance]


class WorkNodeResolution(ContractModel):
    query: str
    status: Literal["resolved", "ambiguous", "not_found"]
    canonical_node_id: Optional[str] = None
    candidates: List[AmbiguityCandidate] = Field(default_factory=list)
    reason: str


class NavigationTransactionState(str, Enum):
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"
    interrupted = "interrupted"


class NavigationTransaction(ContractModel):
    id: str
    actor: str
    origin: str
    destination: str
    path: List[str]
    start_time: datetime = Field(default_factory=utc_now)
    duration_ms: int = Field(default=0, ge=0)
    state: NavigationTransactionState = NavigationTransactionState.planned
    interruption_reason: Optional[str] = None


class RoomConference(ContractModel):
    id: str
    room_id: str
    participant_ids: List[str]
    visitor_ids: List[str] = Field(default_factory=list)
    state: Literal["planned", "running", "completed", "failed"] = "planned"
    provenance: List[str] = Field(default_factory=list)


class MemoryPointer(ContractModel):
    id: str
    repository_id: Optional[str] = None
    sensitivity: str = "internal"
    summary: str
    evidence_ref: str
    confidence: float = Field(default=1.0, ge=0, le=1)


class RetrievalPacket(ContractModel):
    id: str
    pointer_ids: List[str]
    evidence: List[str] = Field(default_factory=list)
    token_estimate: int = Field(default=0, ge=0)


class RuntimeAction(ContractModel):
    id: str
    actor: str
    capability_id: str
    target: str
    approval_class: Literal["automatic", "operator", "hard_stop"]
    state: Literal["planned", "running", "succeeded", "failed", "denied"]


class DeploymentTarget(ContractModel):
    id: str
    name: str
    role: Literal["control_plane", "presentation", "client", "adapter"]
    reachable: bool = False


class HealthState(ContractModel):
    status: Literal["healthy", "degraded", "unavailable"]
    schema_version: int
    timestamp: datetime = Field(default_factory=utc_now)
    checks: Dict[str, Any] = Field(default_factory=dict)


class StateEvent(ContractModel):
    sequence: Optional[int] = None
    id: str
    event_type: str
    entity_type: str
    entity_id: str
    actor: str
    occurred_at: datetime = Field(default_factory=utc_now)
    payload: Dict[str, Any] = Field(default_factory=dict)
    previous_hash: Optional[str] = None
    event_hash: str


class StateEventPage(ContractModel):
    events: List[StateEvent] = Field(default_factory=list)
    latest_sequence: int = Field(default=0, ge=0)


class AuditEvent(ContractModel):
    sequence: Optional[int] = None
    id: str
    actor: str
    capability_id: str
    target: str
    inputs_hash: str
    result: Literal["succeeded", "failed", "denied"]
    evidence: List[str] = Field(default_factory=list)
    rollback_ref: str
    occurred_at: datetime = Field(default_factory=utc_now)
    previous_hash: Optional[str] = None
    event_hash: str


DOMAIN_MODELS = {
    model.__name__: model
    for model in (
        Ship,
        Room,
        Persona,
        PersonaLocation,
        Capability,
        RepositorySystem,
        WorkStream,
        WorkNode,
        WorkNodeResolution,
        NavigationTransaction,
        RoomConference,
        MemoryPointer,
        RetrievalPacket,
        RuntimeAction,
        DeploymentTarget,
        HealthState,
        AuditEvent,
        StateEvent,
        StateEventPage,
    )
}

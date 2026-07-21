"""Versioned machine-readable BBC Odysseus domain contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional

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


# Mirrors RegistryEntrySummary.id: a room may only name an id the universal
# registry is capable of producing, so the grammar is shared deliberately.
RegistryEntryId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9:._-]{1,239}$")]


class Room(ContractModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,79}$")
    name: str = Field(min_length=1, max_length=120)
    function: str = Field(min_length=1, max_length=240)
    deck: int = Field(default=1, ge=1)
    position: Point
    size: Point
    occupant_ids: List[str] = Field(default_factory=list)
    # Universal-registry entry ids this compartment represents. Declaration is
    # inventory only: it confers no invocation right and bypasses no permission
    # check. Every id must resolve in the live registry.
    capability_ids: List[RegistryEntryId] = Field(default_factory=list, max_length=32)
    active: bool = True


class Ship(ContractModel):
    id: str
    name: str
    deck_count: int = Field(default=1, ge=1)
    active_room_id: str
    rooms: List[Room]
    updated_at: datetime = Field(default_factory=utc_now)


class PersonaLocation(ContractModel):
    persona_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    room_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
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


class RegistryEntryKind(str, Enum):
    capability = "capability"
    skill = "skill"
    mcp_tool = "mcp_tool"
    task_definition = "task_definition"
    automation = "automation"
    memory_system = "memory_system"
    model_runtime = "model_runtime"
    connector = "connector"


class RegistryAvailability(ContractModel):
    state: Literal["available", "degraded", "disabled", "unavailable", "unknown"]
    detail: str = Field(default="", max_length=500)
    checked_at: datetime = Field(default_factory=utc_now)


class RegistryRisk(ContractModel):
    level: Literal["low", "medium", "high"]
    reasons: List[str] = Field(default_factory=list, max_length=12)
    permissions: List[str] = Field(default_factory=list, max_length=24)


class RegistryProvenance(ContractModel):
    source: str = Field(min_length=1, max_length=120)
    reference: str = Field(min_length=1, max_length=500)
    authoritative: bool = True


class RegistryEntrySummary(ContractModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9:._-]{1,239}$")
    kind: RegistryEntryKind
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=600)
    version: str = Field(default="unversioned", max_length=80)
    owner: str = Field(default="odysseus", max_length=160)
    scope: List[str] = Field(default_factory=list, max_length=24)
    availability: RegistryAvailability
    risk: RegistryRisk
    provenance: List[RegistryProvenance] = Field(min_length=1, max_length=12)
    context_cost: int = Field(default=0, ge=0, le=1_000_000)


class RegistryEntryDetail(RegistryEntrySummary):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    definition_schema: Dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="schema",
        serialization_alias="schema",
    )
    instructions: str = Field(default="", max_length=20_000)


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


class WorkNodeAction(ContractModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    label: str = Field(min_length=1, max_length=80)
    capability_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,119}$")
    approval_class: Literal["automatic", "operator", "hard_stop"]
    read_only: bool


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
    available_actions: List[WorkNodeAction] = Field(default_factory=list, max_length=12)
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
    id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    actor: str = Field(min_length=1, max_length=160)
    persona_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    origin: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    destination: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    path: List[str] = Field(min_length=2, max_length=40)
    start_time: datetime = Field(default_factory=utc_now)
    duration_ms: int = Field(default=0, ge=0)
    state: NavigationTransactionState = NavigationTransactionState.planned
    version: int = Field(default=1, ge=1)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    interrupted_at: Optional[datetime] = None
    interruption_reason: Optional[str] = Field(default=None, max_length=500)


class RoomConferenceState(str, Enum):
    planned = "planned"
    running = "running"
    completed = "completed"
    failed = "failed"


class PersonaProjection(ContractModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=160)
    archetype: str = Field(default="", max_length=160)
    skills: List[str] = Field(default_factory=list, max_length=24)
    consults: List[str] = Field(default_factory=list, max_length=16)
    intents: List[str] = Field(default_factory=list, max_length=24)
    source_ref: str = Field(min_length=1, max_length=400)


class ConferenceParticipant(ContractModel):
    persona_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    role: str = Field(min_length=1, max_length=160)
    focus: Literal["evidence", "risk", "workflow", "integration"]
    context_pointer_ids: List[str] = Field(default_factory=list, max_length=12)
    output_contract: str = Field(min_length=1, max_length=300)


class ConferenceContribution(ContractModel):
    persona_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    focus: Literal["evidence", "risk", "workflow", "integration"]
    findings: List[str] = Field(default_factory=list, max_length=8)
    evidence_refs: List[str] = Field(default_factory=list, max_length=12)
    uncertainty: List[str] = Field(default_factory=list, max_length=6)
    proposed_actions: List[str] = Field(default_factory=list, max_length=6)


class ConferenceSynthesis(ContractModel):
    decision: str = Field(min_length=1, max_length=600)
    disagreements: List[str] = Field(default_factory=list, max_length=8)
    uncertainty: List[str] = Field(default_factory=list, max_length=8)
    proposed_actions: List[str] = Field(default_factory=list, max_length=8)
    provenance: List[str] = Field(default_factory=list, max_length=24)
    actions_executed: bool = False


class RoomConference(ContractModel):
    id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    actor: str = Field(min_length=1, max_length=160)
    room_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    objective: str = Field(min_length=1, max_length=500)
    repository_id: Optional[str] = Field(default=None, pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    work_node_id: Optional[str] = Field(default=None, max_length=200)
    trigger_navigation_transaction_id: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    )
    participant_ids: List[str] = Field(min_length=1, max_length=12)
    visitor_ids: List[str] = Field(default_factory=list, max_length=2)
    participants: List[ConferenceParticipant] = Field(default_factory=list, max_length=12)
    state: RoomConferenceState = RoomConferenceState.planned
    retrieval_packet_id: Optional[str] = Field(default=None, max_length=120)
    contributions: List[ConferenceContribution] = Field(default_factory=list, max_length=12)
    synthesis: Optional[ConferenceSynthesis] = None
    provenance: List[str] = Field(default_factory=list, max_length=24)
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    failure_reason: Optional[str] = Field(default=None, max_length=500)


class MemoryPointer(ContractModel):
    id: str = Field(min_length=1, max_length=120)
    repository_id: Optional[str] = None
    sensitivity: Literal["internal", "research", "operator-private"] = "internal"
    summary: str = Field(min_length=1, max_length=600)
    evidence_ref: str = Field(min_length=1, max_length=500)
    confidence: float = Field(default=1.0, ge=0, le=1)
    contradiction_refs: List[str] = Field(default_factory=list, max_length=12)
    created_at: datetime = Field(default_factory=utc_now)


class RetrievalPacket(ContractModel):
    id: str = Field(min_length=1, max_length=120)
    repository_id: Optional[str] = None
    pointer_ids: List[str] = Field(default_factory=list, max_length=12)
    summaries: List[str] = Field(default_factory=list, max_length=12)
    evidence: List[str] = Field(default_factory=list, max_length=12)
    token_estimate: int = Field(default=0, ge=0, le=4096)
    created_at: datetime = Field(default_factory=utc_now)


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
        RegistryAvailability,
        RegistryRisk,
        RegistryProvenance,
        RegistryEntrySummary,
        RegistryEntryDetail,
        RepositorySystem,
        WorkStream,
        WorkNodeAction,
        WorkNode,
        WorkNodeResolution,
        NavigationTransaction,
        PersonaProjection,
        ConferenceParticipant,
        ConferenceContribution,
        ConferenceSynthesis,
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

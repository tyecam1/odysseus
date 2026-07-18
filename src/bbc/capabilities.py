"""Compact discovery and lazy detail loading for universal capabilities."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .adapters import RepositoryAdapterRegistry
from .models import Capability, CapabilityHealth, CapabilitySummary


class RepositoryInspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository_id: str = Field(min_length=1, max_length=80)
    query: str = Field(default="", max_length=240)
    relative_path: str = Field(default="", max_length=400)
    limit: int = Field(default=20, ge=1, le=50)


CapabilityHandler = Callable[[Mapping[str, Any]], Dict[str, Any]]
CapabilityHealthProvider = Callable[[], CapabilityHealth]


class CapabilityRegistry:
    """Registry whose search surface never includes heavy schemas/instructions."""

    def __init__(self):
        self._details: Dict[str, Capability] = {}
        self._handlers: Dict[str, CapabilityHandler] = {}
        self._health_providers: Dict[str, CapabilityHealthProvider] = {}

    def register(
        self,
        capability: Capability,
        handler: CapabilityHandler | None = None,
        *,
        health_provider: CapabilityHealthProvider | None = None,
    ) -> bool:
        existing = self._details.get(capability.id)
        if existing:
            if existing.model_dump(mode="json") != capability.model_dump(mode="json"):
                raise ValueError(f"conflicting duplicate capability id: {capability.id}")
            if handler and capability.id not in self._handlers:
                self._handlers[capability.id] = handler
            if health_provider and capability.id not in self._health_providers:
                self._health_providers[capability.id] = health_provider
            return False
        if capability.replaced_by == capability.id:
            raise ValueError("a capability cannot replace itself")
        if capability.replacement_status == "replaced" and not capability.replaced_by:
            raise ValueError("a replaced capability must declare replaced_by")
        if capability.replaced_by:
            target = self._details.get(capability.replaced_by)
            if target is None:
                raise ValueError(f"replacement target is not registered: {capability.replaced_by}")
            if not capability.overlap_group or capability.overlap_group != target.overlap_group:
                raise ValueError("replacement capabilities must share a non-empty overlap_group")
        self._details[capability.id] = capability
        if handler:
            self._handlers[capability.id] = handler
        if health_provider:
            self._health_providers[capability.id] = health_provider
        self._validate_replacements()
        return True

    def _validate_replacements(self) -> None:
        for capability_id in self._details:
            seen: set[str] = set()
            current = capability_id
            while current:
                if current in seen:
                    raise ValueError(f"capability replacement cycle includes: {current}")
                seen.add(current)
                detail = self._details[current]
                target = detail.replaced_by
                if target and target not in self._details:
                    raise ValueError(f"replacement target is not registered: {target}")
                current = target or ""

    def validate(self) -> None:
        """Validate cross-capability overlap and replacement graph metadata."""

        self._validate_replacements()

    def summary(self, capability_id: str) -> CapabilitySummary:
        detail = self.detail(capability_id)
        return CapabilitySummary(**detail.model_dump(exclude={
            "provenance", "licence", "inputs_schema", "outputs_schema", "dependencies",
            "target_adapters", "instructions", "replaced_by", "tests",
        }))

    def detail(self, capability_id: str) -> Capability:
        try:
            detail = self._details[capability_id]
        except KeyError as exc:
            raise KeyError(f"unknown capability: {capability_id}") from exc
        provider = self._health_providers.get(capability_id)
        return detail.model_copy(update={"health": provider()}) if provider else detail

    def search(self, query: str = "", *, limit: int = 20) -> list[CapabilitySummary]:
        terms = [term.casefold() for term in str(query or "").split() if term.strip()]
        ranked = []
        for capability_id, detail in self._details.items():
            haystack = " ".join((capability_id, detail.name, detail.description, " ".join(detail.scope))).casefold()
            score = sum(3 if term in capability_id.casefold() else 1 for term in terms if term in haystack)
            if terms and score == 0:
                continue
            ranked.append((score, capability_id, self.summary(capability_id)))
        ranked.sort(key=lambda row: (-row[0], row[1]))
        return [row[2] for row in ranked[:max(1, min(int(limit), 100))]]

    def invoke(
        self,
        capability_id: str,
        inputs: Mapping[str, Any],
        *,
        granted_permissions: Iterable[str],
    ) -> Dict[str, Any]:
        detail = self.detail(capability_id)
        if detail.replacement_status != "active":
            raise PermissionError(f"capability is not active: {capability_id}")
        grants = set(granted_permissions)
        missing = set(detail.permissions) - grants
        if "*" not in grants and missing:
            raise PermissionError(
                f"capability requires permissions: {', '.join(sorted(missing))}"
            )
        try:
            handler = self._handlers[capability_id]
        except KeyError as exc:
            raise RuntimeError(f"capability has no runtime handler: {capability_id}") from exc
        return handler(inputs)

    def __len__(self) -> int:
        return len(self._details)


def build_capability_registry(adapters: RepositoryAdapterRegistry) -> CapabilityRegistry:
    registry = CapabilityRegistry()

    def inspect(inputs: Mapping[str, Any]) -> Dict[str, Any]:
        request = RepositoryInspectionInput.model_validate(inputs)
        adapter = adapters.get(request.repository_id)
        return adapter.inspect(
            query=request.query,
            relative_path=request.relative_path,
            limit=request.limit,
        )

    def inspection_health() -> CapabilityHealth:
        systems = adapters.systems()
        available = [system.id for system in systems if system.reachable]
        unavailable = [system.id for system in systems if not system.reachable]
        if not available:
            return CapabilityHealth(
                state="unavailable",
                detail="No target repository adapter is reachable.",
            )
        if unavailable:
            return CapabilityHealth(
                state="degraded",
                detail=f"Unavailable target adapters: {', '.join(unavailable)}.",
            )
        return CapabilityHealth(
            state="healthy",
            detail="All target repository adapters are reachable; inspection is local, bounded, and network-free.",
        )

    registry.register(Capability(
        id="bbc.repository.inspect",
        version="1.0.0",
        name="Shared repository inspection",
        description="Read a bounded authoritative work-item source or search its adapter-confined source surface.",
        owner="odysseus",
        scope=["repository", "work-items", "read-only"],
        permissions=["repository:read"],
        health=CapabilityHealth(state="healthy", detail="Local, bounded, and network-free."),
        context_cost=180,
        overlap_group="repository-inspection",
        replacement_status="active",
        provenance=["src/bbc/capabilities.py", "src/bbc/adapters.py"],
        licence="AGPL-3.0-or-later",
        inputs_schema=RepositoryInspectionInput.model_json_schema(),
        outputs_schema={
            "type": "object",
            "required": ["repository_id", "mode"],
            "properties": {
                "repository_id": {"type": "string"},
                "mode": {"enum": ["summary", "search", "read"]},
            },
        },
        dependencies=[],
        target_adapters=list(adapters.ids()),
        instructions=(
            "Select one configured repository ID. Use a query for bounded line search, a relative_path "
            "returned by the adapter for a bounded read, or neither for a compact repository summary."
        ),
        tests=["tests/test_bbc_capabilities.py"],
    ), inspect, health_provider=inspection_health)
    registry.validate()
    return registry

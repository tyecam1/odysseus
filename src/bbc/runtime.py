"""Production-shaped BBC v1 application service."""

from __future__ import annotations

import json
import uuid
from collections import deque
import difflib
import re
from pathlib import Path
from typing import Any, Dict

from .adapters import RepositoryAdapterRegistry, RepositorySnapshot
from .capabilities import CapabilityRegistry, build_capability_registry
from .registry import UniversalRegistry, build_universal_registry
from .models import (
    DOMAIN_MODELS,
    API_VERSION,
    SCHEMA_VERSION,
    HealthState,
    ConferenceContribution,
    ConferenceParticipant,
    ConferenceSynthesis,
    MemoryPointer,
    NavigationTransaction,
    NavigationTransactionState,
    PersonaLocation,
    PersonaProjection,
    Point,
    Room,
    RoomConference,
    RoomConferenceState,
    RetrievalPacket,
    Ship,
    utc_now,
    WorkNodeResolution,
    WorkNode,
    WorkNodeAction,
    WorkStream,
)
from .store import BBCStateStore, StateConflict, content_hash


ROOM_ADJACENCY: dict[str, tuple[str, ...]] = {
    "bridge": ("observatory", "research"),
    "observatory": ("bridge", "research", "archive", "commons"),
    "research": ("bridge", "observatory", "commons", "engineering"),
    "archive": ("observatory", "commons"),
    "commons": ("observatory", "research", "archive", "engineering", "workshop"),
    "engineering": ("research", "commons", "workshop"),
    "workshop": ("commons", "engineering"),
}

ROOM_PURPOSE_TERMS: dict[str, set[str]] = {
    "bridge": {"authority", "integration", "strategy", "priority", "governance", "coherence", "boundary"},
    "observatory": {"repository", "system", "health", "navigation", "selection", "browse", "context"},
    "research": {"research", "evidence", "experiment", "analysis", "uncertainty", "measurement", "science"},
    "archive": {"memory", "provenance", "archive", "raw", "fidelity", "history", "record"},
    "commons": {"household", "care", "food", "music", "wellbeing", "conference", "synthesis", "cleaning"},
    "engineering": {"runtime", "model", "deployment", "implementation", "security", "code", "technical"},
    "workshop": {"capability", "tool", "workflow", "process", "automation", "execution", "task"},
}

CONFERENCE_FOCUS_TERMS: dict[str, set[str]] = {
    "evidence": {"evidence", "research", "memory", "archive", "provenance", "uncertainty", "measurement"},
    "risk": {"risk", "priority", "blocker", "safety", "security", "cost", "decision"},
    "workflow": {"workflow", "task", "process", "implementation", "execution", "planning", "closure"},
    "integration": {"integration", "coherence", "boundary", "synthesis", "system", "governance"},
}


class NavigationConflict(RuntimeError):
    """A navigation command lost an optimistic concurrency race."""


def authored_room_path(origin: str, destination: str) -> list[str]:
    if origin not in ROOM_ADJACENCY or destination not in ROOM_ADJACENCY:
        raise ValueError("navigation origin and destination must be authored rooms")
    if origin == destination:
        raise ValueError("navigation origin and destination must differ")
    queue = deque([(origin, [origin])])
    visited = {origin}
    while queue:
        room, path = queue.popleft()
        for neighbour in ROOM_ADJACENCY[room]:
            if neighbour in visited:
                continue
            candidate = path + [neighbour]
            if neighbour == destination:
                return candidate
            visited.add(neighbour)
            queue.append((neighbour, candidate))
    raise ValueError("authored rooms are disconnected")


def validate_room_path(origin: str, destination: str, path: list[str]) -> list[str]:
    route = list(path) if path else authored_room_path(origin, destination)
    if not route or route[0] != origin or route[-1] != destination:
        raise ValueError("navigation path must begin at origin and end at destination")
    if len(route) != len(set(route)):
        raise ValueError("navigation path may not repeat rooms")
    if any(room not in ROOM_ADJACENCY for room in route):
        raise ValueError("navigation path contains an unknown room")
    if any(right not in ROOM_ADJACENCY[left] for left, right in zip(route, route[1:])):
        raise ValueError("navigation path contains a discontinuous step")
    return route


ROOM_ALIASES = {
    "helm": "bridge", "command": "bridge", "ship": "bridge",
    "lab": "research", "research lab": "research",
    "archives": "archive", "memory": "archive",
    "common room": "commons", "galley": "commons",
    "engine room": "engineering", "engines": "engineering",
    "capabilities": "workshop", "capability workshop": "workshop",
    "repository map": "observatory", "system map": "observatory",
}


def _normalise_navigation_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9._:-]+", " ", value.casefold())).strip()


def _rank_target(query: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    normal = _normalise_navigation_text(query)
    ranked: list[tuple[float, dict[str, Any]]] = []
    for candidate in candidates:
        scores = []
        for term in [candidate["id"], candidate.get("label", ""), *candidate.get("aliases", [])]:
            target = _normalise_navigation_text(str(term))
            if not target:
                continue
            score = 1.0 if normal == target else difflib.SequenceMatcher(None, normal, target).ratio()
            scores.append(score)
        if scores:
            ranked.append((max(scores), candidate))
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    if not ranked or ranked[0][0] < 0.74:
        return {"status": "clarification_required", "confidence": ranked[0][0] if ranked else 0.0, "candidates": []}
    close = [item for item in ranked if ranked[0][0] - item[0] < 0.08]
    if len(close) > 1:
        return {
            "status": "clarification_required", "confidence": ranked[0][0],
            "candidates": [item[1] for item in close[:5]],
        }
    return {"status": "resolved", "confidence": ranked[0][0], "target": ranked[0][1]}


def authored_ship() -> Ship:
    """Stable one-deck geometry; occupancy/allocation remains registry-driven."""

    rooms = [
        Room(id="bridge", name="Bridge", function="Pilotage and runtime overview", position=Point(x=41, y=4), size=Point(x=18, y=17)),
        Room(id="observatory", name="Observatory", function="Repository navigation and system health", position=Point(x=20, y=21), size=Point(x=21, y=18)),
        Room(id="research", name="Research Lab", function="Evidence and experiment work", position=Point(x=59, y=21), size=Point(x=21, y=18)),
        Room(id="archive", name="Archive", function="Memory and provenance inspection", position=Point(x=10, y=43), size=Point(x=22, y=19)),
        Room(id="commons", name="Commons", function="Bounded conferences and synthesis", position=Point(x=39, y=42), size=Point(x=22, y=20)),
        Room(id="engineering", name="Engineering", function="Runtime, models, and deployment", position=Point(x=68, y=43), size=Point(x=22, y=19)),
        Room(id="workshop", name="Workshop", function="Capabilities and controlled execution", position=Point(x=39, y=67), size=Point(x=22, y=19)),
    ]
    return Ship(id="bbc-odysseus", name="BBC Odysseus", active_room_id="bridge", rooms=rooms)


class BBCRuntime:
    def __init__(
        self,
        *,
        store: BBCStateStore,
        adapters: RepositoryAdapterRegistry,
        capabilities: CapabilityRegistry | None = None,
        registry: UniversalRegistry | None = None,
    ):
        self.store = store
        self.adapters = adapters
        self.capabilities = capabilities or build_capability_registry(adapters)
        self.registry = registry
        self._ship = authored_ship()
        if self.store.get_entity("ship", self._ship.id) is None:
            self.store.upsert_entity("ship", self._ship.id, self._ship.model_dump(mode="json"), event_type="ship.initialised")
        self._initialise_persona_locations()

    def persona_projections(self) -> list[PersonaProjection]:
        try:
            adapter = self.adapters.get("misumi-homebase")
        except KeyError:
            return []
        provider = getattr(adapter, "personas", None)
        return list(provider()) if callable(provider) else []

    @staticmethod
    def _terms(value: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", str(value).casefold()))

    def _derived_room(self, persona: PersonaProjection) -> str:
        material = " ".join([persona.role, persona.archetype, *persona.skills, *persona.intents])
        terms = self._terms(material)
        ranked = [
            (len(terms.intersection(keywords)), room_id)
            for room_id, keywords in ROOM_PURPOSE_TERMS.items()
        ]
        ranked.sort(key=lambda item: (-item[0], list(ROOM_PURPOSE_TERMS).index(item[1])))
        return ranked[0][1] if ranked and ranked[0][0] else "bridge"

    def _initialise_persona_locations(self) -> None:
        for persona in self.persona_projections():
            if self.store.get_entity("persona_location", persona.id) is not None:
                continue
            location = PersonaLocation(persona_id=persona.id, room_id=self._derived_room(persona))
            self.store.upsert_entity(
                "persona_location", persona.id, location.model_dump(mode="json"),
                actor="system", event_type="persona.location.derived",
            )

    def schemas(self) -> Dict[str, Any]:
        return {
            "api_version": API_VERSION,
            "schema_version": SCHEMA_VERSION,
            "models": {name: model.model_json_schema() for name, model in DOMAIN_MODELS.items()},
        }

    def ship(self) -> Ship:
        state = self.store.get_entity("ship", self._ship.id)
        ship = Ship.model_validate(state or self._ship)
        occupants: dict[str, list[str]] = {room.id: [] for room in ship.rooms}
        for item in self.store.list_entities("persona_location"):
            location = PersonaLocation.model_validate(item)
            if location.room_id in occupants:
                occupants[location.room_id].append(location.persona_id)
        rooms = [
            room.model_copy(update={"occupant_ids": sorted(occupants[room.id])})
            for room in ship.rooms
        ]
        return ship.model_copy(update={"rooms": rooms})

    def health(self) -> HealthState:
        systems = self.adapters.systems()
        chains = self.store.verify_event_chains()
        canonical = self.store.verify_canonical_state()
        db_ok = (
            self.store.integrity_check()
            and self.store.schema_version() == SCHEMA_VERSION
            and all(chains.values())
            and all(canonical.values())
        )
        unavailable = [system.id for system in systems if not system.reachable]
        registry_status = self.registry.status() if self.registry is not None else {
            "ok": False,
            "entry_count": 0,
            "counts": {},
            "source_errors": {"registry": "Universal registry is not configured."},
        }
        registry_ok = registry_status["ok"] if self.registry is not None else True
        status = (
            "healthy" if db_ok and not unavailable and registry_ok
            else "degraded" if db_ok else "unavailable"
        )
        capability_health = [summary.health for summary in self.capabilities.search(limit=100)]
        capabilities_ok = bool(capability_health) and all(
            health.state == "healthy" for health in capability_health
        )
        return HealthState(
            status=status,
            schema_version=self.store.schema_version(),
            checks={
                "database": {
                    "ok": db_ok,
                    "event_chains": chains,
                    "canonical_state": canonical,
                },
                "repositories": {
                    "ok": not unavailable,
                    "systems": [system.model_dump(mode="json") for system in systems],
                    "unavailable": unavailable,
                },
                "capabilities": {
                    "ok": capabilities_ok,
                    "count": len(self.capabilities),
                    "states": [health.model_dump(mode="json") for health in capability_health],
                },
                "registry": registry_status,
            },
        )

    def repository_snapshot(self, repository_id: str) -> RepositorySnapshot:
        """Read a live adapter snapshot without changing canonical state."""

        adapter = self.adapters.get(repository_id)
        snapshot = adapter.snapshot()
        snapshot = snapshot.__class__(
            system=snapshot.system,
            streams=snapshot.streams,
            nodes=tuple(self._with_node_actions(node) for node in snapshot.nodes),
        )
        stored_nodes = {
            item.get("id"): item
            for item in self.store.list_entities("work_node")
            if item.get("repository_id") == repository_id
        }
        refreshed_nodes: list[WorkNode] = []
        for node in snapshot.nodes:
            previous = stored_nodes.get(node.id)
            if not previous:
                refreshed_nodes.append(node)
                continue
            previous_node = WorkNode.model_validate(previous)
            provenance = {
                (
                    item.repository_id,
                    item.path,
                    item.line_start,
                    item.line_end,
                    item.source_kind,
                    item.content_hash,
                ): item
                for item in (*previous_node.provenance, *node.provenance)
            }
            refreshed_nodes.append(node.model_copy(update={
                "provenance": list(provenance.values()),
                "source_links": sorted(set(previous_node.source_links) | set(node.source_links)),
                "lineage": list(dict.fromkeys([*previous_node.lineage, *node.lineage])),
            }))
        snapshot = RepositorySnapshot(
            system=snapshot.system,
            streams=snapshot.streams,
            nodes=tuple(refreshed_nodes),
        )
        return snapshot

    @staticmethod
    def _with_node_actions(node: WorkNode) -> WorkNode:
        if node.archived or node.superseded:
            return node.model_copy(update={"available_actions": []})
        return node.model_copy(update={
            "available_actions": [WorkNodeAction(
                id="inspect-source",
                label="Inspect authoritative source",
                capability_id="bbc.repository.inspect",
                approval_class="automatic",
                read_only=True,
            )],
        })

    def refresh_repository(self, repository_id: str, *, actor: str = "system") -> RepositorySnapshot:
        """Explicitly ingest one live snapshot into the canonical event ledger."""

        snapshot = self.adapters.get(repository_id).snapshot()
        snapshot = snapshot.__class__(
            system=snapshot.system,
            streams=snapshot.streams,
            nodes=tuple(self._with_node_actions(node) for node in snapshot.nodes),
        )
        persisted = self.store.ingest_repository_snapshot(
            system=snapshot.system.model_dump(mode="json"),
            streams=(stream.model_dump(mode="json") for stream in snapshot.streams),
            nodes=(node.model_dump(mode="json") for node in snapshot.nodes),
            actor=actor,
        )
        return RepositorySnapshot(
            system=type(snapshot.system).model_validate(persisted["system"]),
            streams=tuple(WorkStream.model_validate(item) for item in persisted["streams"]),
            nodes=tuple(WorkNode.model_validate(item) for item in persisted["nodes"]),
        )

    def resolve_work_node(self, repository_id: str, query: str) -> WorkNodeResolution:
        return self.adapters.get(repository_id).resolve(query)

    def invoke_capability(
        self,
        capability_id: str,
        inputs: Dict[str, Any],
        *,
        actor: str,
        caller_grants: set[str] | frozenset[str],
    ) -> Dict[str, Any]:
        target = str(inputs.get("repository_id") or "runtime")[:160]
        input_digest = content_hash(inputs)
        try:
            result = self.capabilities.invoke(capability_id, inputs, granted_permissions=caller_grants)
        except PermissionError as exc:
            audit = self.store.append_audit(
                actor=actor, capability_id=capability_id, target=target, inputs_hash=input_digest,
                result="denied", evidence=[type(exc).__name__], rollback_ref="not-applicable:read-only",
            )
            raise
        except Exception as exc:
            audit = self.store.append_audit(
                actor=actor, capability_id=capability_id, target=target, inputs_hash=input_digest,
                result="failed", evidence=[type(exc).__name__], rollback_ref="not-required:read-only",
            )
            raise
        evidence = []
        if result.get("path"):
            evidence.append(f"repo://{target}/{result['path']}")
        for hit in result.get("hits", [])[:20]:
            evidence.append(f"repo://{target}/{hit['path']}#L{hit['line']}")
        if not evidence:
            evidence.append(f"repository-summary:{target}")
        audit = self.store.append_audit(
            actor=actor, capability_id=capability_id, target=target, inputs_hash=input_digest,
            result="succeeded", evidence=evidence, rollback_ref="not-required:read-only",
        )
        return {"result": result, "audit": audit.model_dump(mode="json")}

    def resolve_navigation_intent(
        self,
        text: str,
        *,
        source: str = "typed",
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Resolve global navigation language without mutating movement state."""

        normal = _normalise_navigation_text(text)
        context = context or {}
        if not normal:
            raise ValueError("navigation intent text is empty")
        action = re.fullmatch(r"(start|pause|review|archive) (?:this )?(?:work item|node)", normal)
        if action:
            return {
                "status": "confirmation_required", "intent": "work_item_action",
                "action": action.group(1), "confidence": 1.0,
                "reason": "work-item mutations require the action policy",
            }
        if normal == "show blocked work":
            return {
                "status": "resolved", "intent": "filter_work", "confidence": 1.0,
                "arrival_room_id": "observatory", "target": {"kind": "filter", "state": "blocked"},
            }
        if normal == "inspect this node":
            if not context.get("node_id"):
                return {
                    "status": "clarification_required", "intent": "inspect_work_node",
                    "confidence": 1.0, "question": "Which work node should I inspect?", "candidates": [],
                }
            return {
                "status": "resolved", "intent": "inspect_work_node", "confidence": 1.0,
                "arrival_room_id": "observatory", "target": {
                    "kind": "work_node", "id": context["node_id"],
                    "repository_id": context.get("repository_id"),
                },
            }

        room_candidates = [
            {
                "kind": "room", "id": room.id, "label": room.name,
                "aliases": [alias for alias, room_id in ROOM_ALIASES.items() if room_id == room.id],
            }
            for room in self.ship().rooms
        ]
        repository_candidates = []
        for system in self.adapters.systems():
            aliases = [system.id.replace("-", " ")]
            if system.id == "obsidian-phd":
                aliases.extend(["phd", "phd system", "obsidian", "research"])
            elif system.id == "misumi-homebase":
                aliases.extend(["misumi", "homebase", "household"])
            elif system.id == "odysseus":
                aliases.extend(["runtime", "odysseus"])
            repository_candidates.append({
                "kind": "repository", "id": system.id, "label": system.name, "aliases": aliases,
            })
        location_candidates = [
            {
                "kind": "persona", "id": location.persona_id,
                "label": location.persona_id.replace("-", " "),
                "aliases": [], "room_id": location.room_id,
            }
            for location in self.persona_locations()
        ]

        intent = None
        target_text = ""
        candidates: list[dict[str, Any]] = []
        if normal in {"return to the ship", "return to bridge", "return to the bridge"}:
            intent, target_text, candidates = "navigate_room", "bridge", room_candidates
        else:
            patterns = (
                (r"^plot (?:a )?course to (.+)$", "navigate_work_node", []),
                (r"^open (?:the )?(.+?) system$", "navigate_repository", repository_candidates),
                (r"^jump to (?:the )?(.+?)(?: repository| repo)?$", "navigate_repository", repository_candidates),
                (r"^visit (?:the )?(.+)$", "visit_persona", location_candidates),
                (r"^(?:go|head|move|navigate) (?:to )?(?:the )?(.+)$", "navigate_target", room_candidates + location_candidates + repository_candidates),
                (r"^take me to (?:the )?(.+)$", "navigate_target", room_candidates + location_candidates + repository_candidates),
            )
            for pattern, candidate_intent, candidate_set in patterns:
                match = re.match(pattern, normal)
                if match:
                    intent, target_text, candidates = candidate_intent, match.group(1), candidate_set
                    break
        if intent is None:
            return {"status": "unsupported", "intent": None, "confidence": 0.0}

        if intent == "navigate_work_node":
            resolved = []
            ambiguous = []
            for repository_id in self.adapters.ids():
                result = self.resolve_work_node(repository_id, target_text)
                if result.status == "resolved" and result.canonical_node_id:
                    resolved.append({
                        "kind": "work_node", "id": result.canonical_node_id,
                        "repository_id": repository_id, "label": target_text,
                    })
                elif result.status == "ambiguous":
                    ambiguous.extend({
                        "kind": "work_node", "id": candidate.node_id,
                        "repository_id": repository_id, "label": candidate.title,
                    } for candidate in result.candidates)
            if len(resolved) == 1 and not ambiguous:
                match_result = {"status": "resolved", "confidence": 1.0, "target": resolved[0]}
            else:
                match_result = {
                    "status": "clarification_required", "confidence": 1.0 if resolved or ambiguous else 0.0,
                    "candidates": (ambiguous + resolved)[:5],
                }
        else:
            match_result = _rank_target(target_text, candidates)
        if match_result["status"] != "resolved":
            return {
                **match_result, "intent": intent,
                "question": "Which target did you mean?" if match_result.get("candidates") else "I could not identify that target.",
            }
        target = match_result["target"]
        if target["kind"] == "room":
            arrival_room_id = target["id"]
        elif target["kind"] == "persona":
            arrival_room_id = target["room_id"]
        elif target["kind"] == "work_node" and target.get("repository_id") == "obsidian-phd":
            arrival_room_id = "research"
        else:
            arrival_room_id = "observatory"
        return {
            "status": "resolved", "intent": intent, "source": source,
            "confidence": round(float(match_result["confidence"]), 3),
            "arrival_room_id": arrival_room_id, "target": target,
        }

    def create_navigation(
        self,
        *,
        actor: str,
        persona_id: str,
        origin: str,
        destination: str,
        path: list[str],
        duration_ms: int,
    ) -> NavigationTransaction:
        route = validate_room_path(origin, destination, path)
        existing_location = self.store.get_entity("persona_location", persona_id)
        if existing_location and existing_location.get("room_id") != origin:
            raise NavigationConflict(
                f"persona {persona_id} is in {existing_location.get('room_id')}, not {origin}"
            )
        now = utc_now()
        transaction = NavigationTransaction(
            id=str(uuid.uuid4()), actor=actor, persona_id=persona_id,
            origin=origin, destination=destination, path=route, duration_ms=duration_ms,
            state=NavigationTransactionState.planned,
            start_time=now, updated_at=now,
        )
        self.store.create_navigation(
            transaction.model_dump(mode="json"),
            inputs_hash=content_hash({
                "origin": origin,
                "destination": destination,
                "path": route,
                "persona_id": persona_id,
                "duration_ms": duration_ms,
            }),
        )
        return transaction

    def navigation_transaction(self, transaction_id: str) -> NavigationTransaction:
        state = self.store.get_entity("navigation_transaction", transaction_id)
        if state is None:
            raise KeyError(f"navigation transaction not found: {transaction_id}")
        return NavigationTransaction.model_validate(state)

    def persona_location(self, persona_id: str) -> PersonaLocation:
        state = self.store.get_entity("persona_location", persona_id)
        if state is None:
            raise KeyError(f"persona location not found: {persona_id}")
        return PersonaLocation.model_validate(state)

    def persona_locations(self) -> list[PersonaLocation]:
        return [
            PersonaLocation.model_validate(state)
            for state in self.store.list_entities("persona_location")
        ]

    def transition_navigation(
        self,
        transaction_id: str,
        state: NavigationTransactionState | str,
        *,
        actor: str,
        expected_version: int,
        interruption_reason: str | None = None,
    ) -> NavigationTransaction:
        """Apply one retry-safe navigation command as a single database commit."""

        target_state = NavigationTransactionState(state)
        if target_state == NavigationTransactionState.planned:
            raise ValueError("navigation cannot transition back to planned")

        reason = None
        if target_state == NavigationTransactionState.interrupted:
            reason = str(interruption_reason or "").strip()
            if not reason:
                raise ValueError("interruption_reason is required when interrupting navigation")
            if len(reason) > 500:
                raise ValueError("interruption_reason must contain at most 500 characters")
        elif interruption_reason is not None:
            raise ValueError("interruption_reason is only valid for interrupted navigation")

        state_payload = self.store.transition_navigation(
            transaction_id,
            actor=actor,
            expected_version=expected_version,
            target_state=target_state.value,
            interruption_reason=reason,
            room_ids={room.id for room in self._ship.rooms},
            ship_id=self._ship.id,
            inputs_hash=content_hash({
                "transaction_id": transaction_id,
                "state": target_state.value,
                "expected_version": expected_version,
                "interruption_reason": reason,
            }),
        )
        return NavigationTransaction.model_validate(state_payload)

    def _conference_work_node(
        self,
        repository_id: str | None,
        work_node_id: str | None,
    ) -> WorkNode | None:
        if bool(repository_id) != bool(work_node_id):
            raise ValueError("repository_id and work_node_id must be supplied together")
        if repository_id is None:
            return None
        node = next(
            (
                candidate
                for candidate in self.adapters.get(repository_id).snapshot().nodes
                if candidate.id == work_node_id
            ),
            None,
        )
        if node is None:
            raise KeyError(f"work node not found in {repository_id}: {work_node_id}")
        if node.archived or node.superseded:
            raise ValueError("room conference requires a current work node")
        return node

    def _participant_focus(self, persona: PersonaProjection) -> str:
        material = " ".join((persona.role, persona.archetype, *persona.skills, *persona.intents))
        terms = self._terms(material)
        ranked = [
            (len(terms.intersection(keywords)), focus)
            for focus, keywords in CONFERENCE_FOCUS_TERMS.items()
        ]
        ranked.sort(key=lambda item: (-item[0], list(CONFERENCE_FOCUS_TERMS).index(item[1])))
        return ranked[0][1] if ranked and ranked[0][0] else "integration"

    def _conference_attendees(
        self,
        *,
        room_id: str,
        objective: str,
        node: WorkNode | None,
        max_visitors: int,
    ) -> tuple[list[PersonaProjection], list[str]]:
        projections = {persona.id: persona for persona in self.persona_projections()}
        occupants = [
            projections[location.persona_id]
            for location in self.persona_locations()
            if location.room_id == room_id and location.persona_id in projections
        ]
        occupants.sort(key=lambda persona: persona.id)
        if len(occupants) > 12:
            raise ValueError("room occupancy exceeds the conference participant limit")

        task_material = objective
        if node is not None:
            task_material = " ".join((
                task_material,
                node.title,
                node.outcome,
                node.next_action or "",
                *node.blocker_ids,
                *node.dependency_ids,
                *node.difficulty.rationale,
            ))
        task_terms = self._terms(task_material)
        occupant_ids = {persona.id for persona in occupants}
        ranked: list[tuple[int, str, PersonaProjection]] = []
        for persona in projections.values():
            if persona.id in occupant_ids:
                continue
            profile_terms = self._terms(" ".join((
                persona.role, persona.archetype, *persona.skills, *persona.intents,
            )))
            score = 3 * len(task_terms.intersection(profile_terms))
            score += len(profile_terms.intersection(ROOM_PURPOSE_TERMS[room_id]))
            score += sum(1 for occupant in occupants if persona.id in occupant.consults)
            ranked.append((score, persona.id, persona))
        ranked.sort(key=lambda item: (-item[0], item[1]))

        visitors: list[PersonaProjection] = []
        covered_focuses = {self._participant_focus(persona) for persona in occupants}
        for score, _, candidate in ranked:
            if len(visitors) >= max_visitors or len(occupants) + len(visitors) >= 12:
                break
            focus = self._participant_focus(candidate)
            if score <= 0 and (occupants or visitors):
                continue
            if visitors and focus in covered_focuses:
                continue
            visitors.append(candidate)
            covered_focuses.add(focus)
        if not occupants and not visitors:
            raise ValueError("no source-defined persona is available for the conference")
        return [*occupants, *visitors], [persona.id for persona in visitors]

    @staticmethod
    def _bounded_unique(values: list[str], *, limit: int) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))[:limit]

    def _stage_conference_memory(
        self,
        *,
        conference_id: str,
        actor: str,
        room_id: str,
        objective: str,
        repository_id: str | None,
        node: WorkNode | None,
        caller_grants: set[str] | frozenset[str],
    ) -> tuple[list[MemoryPointer], RetrievalPacket, list[str]]:
        pointer_id = f"memory:{conference_id}:context"
        packet_id = f"retrieval:{conference_id}"
        source_ref = f"state://ship/{self._ship.id}/room/{room_id}"
        summary = f"{room_id}: {objective}"
        sensitivity = "internal"
        exact_evidence = summary
        provenance = [source_ref]

        if node is not None and repository_id is not None:
            source = node.provenance[0]
            source_ref = f"repo://{repository_id}/{source.path}"
            summary = (
                f"{node.canonical_key}: {node.title}; state={node.state}; "
                f"difficulty={node.difficulty.score}/100 {node.difficulty.band}."
            )
            sensitivity = "research" if repository_id == "obsidian-phd" else "internal"
            invocation = self.invoke_capability(
                "bbc.repository.inspect",
                {"repository_id": repository_id, "relative_path": source.path, "limit": 12},
                actor=actor,
                caller_grants=caller_grants,
            )
            result = invocation["result"]
            if result.get("text"):
                exact_evidence = str(result["text"])[:4096]
            elif result.get("hits"):
                exact_evidence = "\n".join(
                    str(hit.get("snippet", "")) for hit in result["hits"][:12]
                )[:4096]
            else:
                exact_evidence = json.dumps(result, sort_keys=True, default=str)[:4096]
            provenance.extend(
                str(item) for item in invocation["audit"].get("evidence", [])
            )

        pointer = MemoryPointer(
            id=pointer_id,
            repository_id=repository_id,
            sensitivity=sensitivity,
            summary=summary[:600],
            evidence_ref=source_ref,
            confidence=1.0,
        )
        packet = RetrievalPacket(
            id=packet_id,
            repository_id=repository_id,
            pointer_ids=[pointer.id],
            summaries=[pointer.summary],
            evidence=[exact_evidence],
            token_estimate=min(4096, max(1, (len(pointer.summary) + len(exact_evidence) + 3) // 4)),
        )
        return [pointer], packet, self._bounded_unique(provenance, limit=24)

    def _conference_contributions(
        self,
        participants: list[ConferenceParticipant],
        packet: RetrievalPacket,
        node: WorkNode | None,
    ) -> list[ConferenceContribution]:
        evidence_refs = [*packet.pointer_ids]
        if node is not None:
            evidence_refs.extend(node.source_links)
            evidence_refs.extend(
                f"repo://{item.repository_id}/{item.path}"
                for item in node.provenance
            )
        evidence_refs = self._bounded_unique(evidence_refs, limit=12)
        contributions: list[ConferenceContribution] = []
        for participant in participants:
            if node is None:
                findings = ["The conference is bounded to the authored room context and stated objective."]
                uncertainty = ["No canonical work node was supplied."]
                actions = ["Select a canonical work node before requesting an execution decision."]
            elif participant.focus == "evidence":
                findings = [
                    f"The authoritative node is {node.canonical_key}: {node.title}.",
                    f"Its recorded state is {node.state}; exact source evidence was retrieved through the shared inspection capability.",
                ]
                uncertainty = ["The retrieval packet is bounded to one authoritative source file."]
                actions = ["Review the cited source before changing the work-node state."]
            elif participant.focus == "risk":
                blockers = ", ".join(node.blocker_ids) or "none recorded"
                findings = [
                    f"Difficulty is {node.difficulty.score}/100 ({node.difficulty.band}).",
                    f"Recorded blockers: {blockers}.",
                ]
                uncertainty = (
                    ["Absence of recorded blockers is not proof that external blockers are absent."]
                    if not node.blocker_ids else []
                )
                actions = ["Resolve or verify recorded blockers before execution."]
            elif participant.focus == "workflow":
                next_action = node.next_action or "define the next concrete action"
                findings = [f"The recorded next action is: {next_action}."]
                uncertainty = ["The conference does not infer completion from discussion."]
                actions = [next_action]
            else:
                findings = [
                    f"The node belongs to {node.repository_id} and is being considered in the current room context.",
                    "Repository and room boundaries remain explicit in the retrieval packet.",
                ]
                uncertainty = ["Cross-repository effects require separate authorised actions."]
                actions = ["Keep any follow-up action within its owning repository boundary."]
            contributions.append(ConferenceContribution(
                persona_id=participant.persona_id,
                focus=participant.focus,
                findings=self._bounded_unique(findings, limit=8),
                evidence_refs=evidence_refs,
                uncertainty=self._bounded_unique(uncertainty, limit=6),
                proposed_actions=self._bounded_unique(actions, limit=6),
            ))
        return contributions

    def run_room_conference(
        self,
        *,
        actor: str,
        room_id: str,
        objective: str,
        repository_id: str | None = None,
        work_node_id: str | None = None,
        trigger_navigation_transaction_id: str | None = None,
        max_visitors: int = 2,
        caller_grants: set[str] | frozenset[str] = frozenset(),
    ) -> RoomConference:
        if room_id not in {room.id for room in self._ship.rooms}:
            raise ValueError("room conference must use an authored room")
        if self.ship().active_room_id != room_id:
            raise ValueError("room conference must run in the ship's active room")
        if trigger_navigation_transaction_id is not None:
            trigger = self.navigation_transaction(trigger_navigation_transaction_id)
            if trigger.actor != actor:
                raise PermissionError("navigation transaction belongs to another actor")
            if trigger.state != NavigationTransactionState.completed or trigger.destination != room_id:
                raise ValueError("conference trigger must be a completed arrival in the requested room")
            existing = self._conference_by_trigger(trigger_navigation_transaction_id)
            if existing is not None:
                return existing
        objective = str(objective).strip()
        if not objective or len(objective) > 500:
            raise ValueError("conference objective must contain 1 to 500 characters")
        if not 0 <= max_visitors <= 2:
            raise ValueError("max_visitors must be between 0 and 2")
        node = self._conference_work_node(repository_id, work_node_id)
        attendees, visitor_ids = self._conference_attendees(
            room_id=room_id,
            objective=objective,
            node=node,
            max_visitors=max_visitors,
        )
        pointer_id = f"memory:pending:context"
        participants = [ConferenceParticipant(
            persona_id=persona.id,
            role=persona.role,
            focus=self._participant_focus(persona),
            context_pointer_ids=[pointer_id],
            output_contract=(
                "Return no more than two findings, cited evidence, bounded uncertainty, "
                "and proposed actions; do not claim execution."
            ),
        ) for persona in attendees]
        now = utc_now()
        conference = RoomConference(
            id=str(uuid.uuid4()),
            actor=actor,
            room_id=room_id,
            objective=objective,
            repository_id=repository_id,
            work_node_id=work_node_id,
            trigger_navigation_transaction_id=trigger_navigation_transaction_id,
            participant_ids=[persona.id for persona in attendees],
            visitor_ids=visitor_ids,
            participants=participants,
            created_at=now,
            updated_at=now,
        )
        pointer_id = f"memory:{conference.id}:context"
        participants = [
            participant.model_copy(update={"context_pointer_ids": [pointer_id]})
            for participant in participants
        ]
        conference = conference.model_copy(update={"participants": participants})
        command_hash = content_hash({
            "room_id": room_id,
            "objective": objective,
            "repository_id": repository_id,
            "work_node_id": work_node_id,
            "trigger_navigation_transaction_id": trigger_navigation_transaction_id,
            "max_visitors": max_visitors,
        })
        try:
            self.store.create_room_conference(
                conference.model_dump(mode="json"),
                inputs_hash=command_hash,
            )
        except StateConflict:
            existing = (
                self._conference_by_trigger(trigger_navigation_transaction_id)
                if trigger_navigation_transaction_id is not None else None
            )
            if existing is not None:
                return existing
            raise
        running = self.transition_room_conference(
            conference.id,
            RoomConferenceState.running,
            actor=actor,
            expected_version=1,
        )
        try:
            pointers, packet, provenance = self._stage_conference_memory(
                conference_id=conference.id,
                actor=actor,
                room_id=room_id,
                objective=objective,
                repository_id=repository_id,
                node=node,
                caller_grants=caller_grants,
            )
            contributions = self._conference_contributions(participants, packet, node)
            uncertainty = self._bounded_unique(
                [item for contribution in contributions for item in contribution.uncertainty],
                limit=8,
            )
            proposed_actions = self._bounded_unique(
                [item for contribution in contributions for item in contribution.proposed_actions],
                limit=8,
            )
            if node is None:
                decision = "No execution decision: select a canonical work node."
            elif node.blocker_ids:
                decision = f"Do not execute yet; resolve the recorded blockers for {node.canonical_key}."
            elif not node.next_action:
                decision = f"Do not execute yet; define a canonical next action for {node.canonical_key}."
            else:
                decision = f"Proceed only with the recorded next action for {node.canonical_key}, subject to cited evidence."
            synthesis = ConferenceSynthesis(
                decision=decision,
                disagreements=[
                    "The workflow view proposes a next action; the evidence view limits confidence to the bounded inspected source.",
                    "The integration view preserves repository boundaries; it does not authorise cross-repository mutation.",
                ],
                uncertainty=uncertainty,
                proposed_actions=proposed_actions,
                provenance=self._bounded_unique([*provenance, *packet.pointer_ids], limit=24),
                actions_executed=False,
            )
            completed_at = utc_now()
            completed = running.model_copy(update={
                "state": RoomConferenceState.completed,
                "version": running.version + 1,
                "updated_at": completed_at,
                "completed_at": completed_at,
                "retrieval_packet_id": packet.id,
                "participants": participants,
                "contributions": contributions,
                "synthesis": synthesis,
                "provenance": synthesis.provenance,
            })
            state_payload = self.store.complete_room_conference(
                conference.id,
                actor=actor,
                expected_version=running.version,
                completed_state=completed.model_dump(mode="json"),
                memory_pointers=[pointer.model_dump(mode="json") for pointer in pointers],
                retrieval_packet=packet.model_dump(mode="json"),
                inputs_hash=command_hash,
            )
            return RoomConference.model_validate(state_payload)
        except Exception as exc:
            current = self.room_conference(conference.id)
            if current.state == RoomConferenceState.running:
                self.transition_room_conference(
                    conference.id,
                    RoomConferenceState.failed,
                    actor=actor,
                    expected_version=current.version,
                    failure_reason=f"{type(exc).__name__}: {exc}"[:500],
                )
            raise

    def room_conference(self, conference_id: str) -> RoomConference:
        state = self.store.get_entity("room_conference", conference_id)
        if state is None:
            raise KeyError(f"room conference not found: {conference_id}")
        return RoomConference.model_validate(state)

    def room_conferences(
        self,
        *,
        room_id: str | None = None,
        state: RoomConferenceState | str | None = None,
        limit: int = 20,
    ) -> list[RoomConference]:
        target_state = RoomConferenceState(state).value if state is not None else None
        if not 1 <= int(limit) <= 100:
            raise ValueError("conference list limit must be between 1 and 100")
        conferences = [
            RoomConference.model_validate(item)
            for item in self.store.list_entities("room_conference")
            if (room_id is None or item.get("room_id") == room_id)
            and (target_state is None or item.get("state") == target_state)
        ]
        conferences.sort(key=lambda item: item.updated_at, reverse=True)
        return conferences[:int(limit)]

    def _conference_by_trigger(self, transaction_id: str) -> RoomConference | None:
        state = next((
            item for item in self.store.list_entities("room_conference")
            if item.get("trigger_navigation_transaction_id") == transaction_id
        ), None)
        return RoomConference.model_validate(state) if state is not None else None

    def transition_room_conference(
        self,
        conference_id: str,
        state: RoomConferenceState | str,
        *,
        actor: str,
        expected_version: int,
        failure_reason: str | None = None,
    ) -> RoomConference:
        target_state = RoomConferenceState(state)
        if target_state == RoomConferenceState.planned:
            raise ValueError("room conference cannot transition back to planned")
        reason = None
        if target_state == RoomConferenceState.failed:
            reason = str(failure_reason or "").strip()
            if not reason:
                raise ValueError("failure_reason is required when failing a room conference")
            if len(reason) > 500:
                raise ValueError("failure_reason must contain at most 500 characters")
        elif failure_reason is not None:
            raise ValueError("failure_reason is only valid for a failed room conference")

        state_payload = self.store.transition_room_conference(
            conference_id,
            actor=actor,
            expected_version=expected_version,
            target_state=target_state.value,
            failure_reason=reason,
            inputs_hash=content_hash({
                "conference_id": conference_id,
                "state": target_state.value,
                "expected_version": expected_version,
                "failure_reason": reason,
            }),
        )
        return RoomConference.model_validate(state_payload)

def build_runtime(
    *,
    data_dir: str | Path,
    app_root: str | Path,
    registry: UniversalRegistry | None = None,
) -> BBCRuntime:
    data_root = Path(data_dir) / "bbc"
    store = BBCStateStore(data_root / "v1.db")
    adapters = RepositoryAdapterRegistry.from_environment(odysseus_root=app_root)
    capabilities = build_capability_registry(adapters)
    registry = registry or build_universal_registry(
        app_root=app_root,
        data_dir=data_dir,
        capabilities=capabilities,
    )
    if registry.capabilities is None:
        registry.capabilities = capabilities
    return BBCRuntime(
        store=store,
        adapters=adapters,
        capabilities=capabilities,
        registry=registry,
    )

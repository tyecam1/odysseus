"""Production-shaped BBC v1 application service."""

from __future__ import annotations

import uuid
from collections import deque
import difflib
import re
from pathlib import Path
from typing import Any, Dict

from .adapters import RepositoryAdapterRegistry, RepositorySnapshot
from .capabilities import CapabilityRegistry, build_capability_registry
from .models import (
    DOMAIN_MODELS,
    API_VERSION,
    SCHEMA_VERSION,
    HealthState,
    NavigationTransaction,
    NavigationTransactionState,
    PersonaLocation,
    Point,
    Room,
    Ship,
    utc_now,
    WorkNodeResolution,
    WorkNode,
)
from .store import BBCStateStore, content_hash


ROOM_ADJACENCY: dict[str, tuple[str, ...]] = {
    "bridge": ("observatory", "research"),
    "observatory": ("bridge", "research", "archive", "commons"),
    "research": ("bridge", "observatory", "commons", "engineering"),
    "archive": ("observatory", "commons"),
    "commons": ("observatory", "research", "archive", "engineering", "workshop"),
    "engineering": ("research", "commons", "workshop"),
    "workshop": ("commons", "engineering"),
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
    ):
        self.store = store
        self.adapters = adapters
        self.capabilities = capabilities or build_capability_registry(adapters)
        self._ship = authored_ship()
        if self.store.get_entity("ship", self._ship.id) is None:
            self.store.upsert_entity("ship", self._ship.id, self._ship.model_dump(mode="json"), event_type="ship.initialised")

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
        db_ok = self.store.integrity_check() and self.store.schema_version() == SCHEMA_VERSION and all(chains.values())
        unavailable = [system.id for system in systems if not system.reachable]
        status = "healthy" if db_ok and not unavailable else "degraded" if db_ok else "unavailable"
        capability_health = [summary.health for summary in self.capabilities.search(limit=100)]
        capabilities_ok = bool(capability_health) and all(
            health.state == "healthy" for health in capability_health
        )
        return HealthState(
            status=status,
            schema_version=self.store.schema_version(),
            checks={
                "database": {"ok": db_ok, "event_chains": chains},
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
            },
        )

    def refresh_repository(self, repository_id: str, *, actor: str = "system") -> RepositorySnapshot:
        adapter = self.adapters.get(repository_id)
        snapshot = adapter.snapshot()
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
        self.store.upsert_entity(
            "repository_system", snapshot.system.id, snapshot.system.model_dump(mode="json"),
            actor=actor, event_type="repository.ingested",
        )
        for stream in snapshot.streams:
            self.store.upsert_entity("work_stream", stream.id, stream.model_dump(mode="json"), actor=actor, event_type="work_stream.ingested")
        for node in snapshot.nodes:
            self.store.upsert_entity("work_node", node.id, node.model_dump(mode="json"), actor=actor, event_type="work_node.ingested")
        current_ids = {node.id for node in snapshot.nodes}
        for previous in stored_nodes.values():
            if previous.get("repository_id") != repository_id or previous.get("id") in current_ids:
                continue
            if previous.get("archived") or previous.get("superseded"):
                continue
            previous["archived"] = True
            previous["state"] = "archived"
            lineage = list(previous.get("lineage") or [])
            marker = f"source-removed:{snapshot.system.revision or 'unknown-revision'}"
            if marker not in lineage:
                lineage.append(marker)
            previous["lineage"] = lineage
            archived = WorkNode.model_validate(previous)
            self.store.upsert_entity(
                "work_node", archived.id, archived.model_dump(mode="json"),
                actor=actor, event_type="work_node.archived",
            )
        return snapshot

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

def build_runtime(*, data_dir: str | Path, app_root: str | Path) -> BBCRuntime:
    data_root = Path(data_dir) / "bbc"
    store = BBCStateStore(data_root / "v1.db")
    adapters = RepositoryAdapterRegistry.from_environment(odysseus_root=app_root)
    return BBCRuntime(store=store, adapters=adapters)

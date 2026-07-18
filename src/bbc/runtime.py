"""Production-shaped BBC v1 application service."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict

from pydantic import BaseModel

from .adapters import RepositoryAdapterRegistry, RepositorySnapshot
from .capabilities import CapabilityRegistry, build_capability_registry
from .models import (
    DOMAIN_MODELS,
    API_VERSION,
    SCHEMA_VERSION,
    HealthState,
    NavigationTransaction,
    NavigationTransactionState,
    Point,
    Room,
    Ship,
    WorkNodeResolution,
    WorkNode,
)
from .store import BBCStateStore, content_hash


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
        self.store.upsert_entity("ship", self._ship.id, self._ship.model_dump(mode="json"), event_type="ship.initialised")

    def schemas(self) -> Dict[str, Any]:
        return {
            "api_version": API_VERSION,
            "schema_version": SCHEMA_VERSION,
            "models": {name: model.model_json_schema() for name, model in DOMAIN_MODELS.items()},
        }

    def ship(self) -> Ship:
        state = self.store.get_entity("ship", self._ship.id)
        return Ship.model_validate(state or self._ship)

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

    def create_navigation(
        self,
        *,
        actor: str,
        origin: str,
        destination: str,
        path: list[str],
        duration_ms: int,
    ) -> NavigationTransaction:
        transaction = NavigationTransaction(
            id=str(uuid.uuid4()), actor=actor, origin=origin, destination=destination,
            path=path or [origin, destination], duration_ms=duration_ms,
            state=NavigationTransactionState.planned,
        )
        self.store.upsert_entity(
            "navigation_transaction", transaction.id, transaction.model_dump(mode="json"),
            actor=actor, event_type="navigation.planned",
        )
        self.store.append_audit(
            actor=actor, capability_id="bbc.navigation.plan", target=destination,
            inputs_hash=content_hash({"origin": origin, "destination": destination, "path": path, "duration_ms": duration_ms}),
            result="succeeded", evidence=[f"state://navigation_transaction/{transaction.id}"],
            rollback_ref=f"navigation:{transaction.id}:interrupt",
        )
        return transaction


def build_runtime(*, data_dir: str | Path, app_root: str | Path) -> BBCRuntime:
    data_root = Path(data_dir) / "bbc"
    store = BBCStateStore(data_root / "v1.db")
    adapters = RepositoryAdapterRegistry.from_environment(odysseus_root=app_root)
    return BBCRuntime(store=store, adapters=adapters)

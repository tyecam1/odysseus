"""Migrated SQLite canonical state, event, and audit store for BBC v1."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import threading
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .models import AuditEvent, SCHEMA_VERSION, StateEvent


class StateConflict(RuntimeError):
    """Canonical state changed after the caller read it."""


class CanonicalIntegrityError(RuntimeError):
    """Canonical state no longer agrees with its immutable event ledger."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def content_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class BBCStateStore:
    """Small single-process store with append-only hash-chained event tables."""

    def __init__(self, path: str | Path, *, migrations_dir: str | Path | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrations_dir = Path(migrations_dir or Path(__file__).with_name("migrations"))
        self._lock = threading.RLock()
        self.apply_migrations()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def apply_migrations(self) -> int:
        migration_files = sorted(self.migrations_dir.glob("[0-9][0-9][0-9]_*.sql"))
        if not migration_files:
            raise RuntimeError("BBC database migrations are missing")
        with self._lock, self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
            )
            applied = {
                int(row["version"]): row["checksum"]
                for row in connection.execute("SELECT version, checksum FROM schema_migrations")
            }
            for migration in migration_files:
                version = int(migration.name.split("_", 1)[0])
                sql = migration.read_text(encoding="utf-8")
                checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
                if version in applied:
                    if applied[version] != checksum:
                        raise RuntimeError(f"BBC migration {version} checksum changed after application")
                    continue
                connection.executescript(sql)
                connection.execute(
                    "INSERT INTO schema_migrations(version, name, checksum, applied_at) VALUES (?, ?, ?, ?)",
                    (version, migration.name, checksum, _now()),
                )
            connection.commit()
        version = self.schema_version()
        if version != SCHEMA_VERSION:
            raise RuntimeError(f"unsupported BBC schema version {version}; expected {SCHEMA_VERSION}")
        return version

    def schema_version(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations").fetchone()
            return int(row["version"])

    def integrity_check(self) -> bool:
        with self._connect() as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()
            return bool(row and row[0] == "ok")

    @staticmethod
    def _verify_event_chains_in_connection(connection: sqlite3.Connection) -> Dict[str, bool]:
        results: Dict[str, bool] = {}
        try:
            state_rows = connection.execute("SELECT * FROM state_events ORDER BY sequence").fetchall()
            previous = None
            valid = True
            for row in state_rows:
                material = {
                    "id": row["id"], "event_type": row["event_type"], "entity_type": row["entity_type"],
                    "entity_id": row["entity_id"], "actor": row["actor"], "occurred_at": row["occurred_at"],
                    "payload": json.loads(row["payload_json"]), "previous_hash": row["previous_hash"],
                }
                if row["previous_hash"] != previous or content_hash(material) != row["event_hash"]:
                    valid = False
                    break
                previous = row["event_hash"]
            results["state_events"] = valid

            audit_rows = connection.execute("SELECT * FROM audit_events ORDER BY sequence").fetchall()
            previous = None
            valid = True
            for row in audit_rows:
                material = {
                    "id": row["id"], "actor": row["actor"], "capability_id": row["capability_id"],
                    "target": row["target"], "inputs_hash": row["inputs_hash"], "result": row["result"],
                    "evidence": json.loads(row["evidence_json"]), "rollback_ref": row["rollback_ref"],
                    "occurred_at": row["occurred_at"], "previous_hash": row["previous_hash"],
                }
                if row["previous_hash"] != previous or content_hash(material) != row["event_hash"]:
                    valid = False
                    break
                previous = row["event_hash"]
            results["audit_events"] = valid
        except (json.JSONDecodeError, KeyError, sqlite3.DatabaseError, TypeError):
            return {"state_events": False, "audit_events": False}
        return results

    def verify_event_chains(self) -> Dict[str, bool]:
        with self._connect() as connection:
            return self._verify_event_chains_in_connection(connection)

    @staticmethod
    def _verify_canonical_state_in_connection(connection: sqlite3.Connection) -> Dict[str, bool]:
        hashes_valid = True
        latest_events_valid = True
        entity_coverage_valid = True
        try:
            rows = connection.execute(
                "SELECT entity_type, entity_id, version, state_json, state_hash FROM canonical_state"
            ).fetchall()
            canonical_keys = {
                (str(row["entity_type"]), str(row["entity_id"])) for row in rows
            }
            event_keys = {
                (str(row["entity_type"]), str(row["entity_id"]))
                for row in connection.execute(
                    "SELECT DISTINCT entity_type, entity_id FROM state_events"
                )
            }
            entity_coverage_valid = canonical_keys == event_keys
            for row in rows:
                state = json.loads(row["state_json"])
                state_digest = content_hash(state)
                if state_digest != row["state_hash"]:
                    hashes_valid = False
                event = connection.execute(
                    "SELECT payload_json FROM state_events "
                    "WHERE entity_type = ? AND entity_id = ? ORDER BY sequence DESC LIMIT 1",
                    (row["entity_type"], row["entity_id"]),
                ).fetchone()
                if event is None:
                    latest_events_valid = False
                    continue
                payload = json.loads(event["payload_json"])
                if (
                    int(payload.get("version", -1)) != int(row["version"])
                    or payload.get("state_hash") != row["state_hash"]
                    or payload.get("state") != state
                ):
                    latest_events_valid = False
        except (json.JSONDecodeError, KeyError, sqlite3.DatabaseError, TypeError, ValueError):
            return {"hashes": False, "latest_events": False, "entity_coverage": False}
        return {
            "hashes": hashes_valid,
            "latest_events": latest_events_valid,
            "entity_coverage": entity_coverage_valid,
        }

    def verify_canonical_state(self) -> Dict[str, bool]:
        with self._connect() as connection:
            return self._verify_canonical_state_in_connection(connection)

    @staticmethod
    def _decode_canonical_row(
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        entity_type: str,
        entity_id: str,
    ) -> Dict[str, Any]:
        try:
            state = json.loads(row["state_json"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise CanonicalIntegrityError(
                f"canonical state JSON is invalid: {entity_type}/{entity_id}"
            ) from exc
        if content_hash(state) != row["state_hash"]:
            raise CanonicalIntegrityError(
                f"canonical state hash mismatch: {entity_type}/{entity_id}"
            )
        event = connection.execute(
            "SELECT payload_json FROM state_events "
            "WHERE entity_type = ? AND entity_id = ? ORDER BY sequence DESC LIMIT 1",
            (entity_type, entity_id),
        ).fetchone()
        if event is None:
            raise CanonicalIntegrityError(
                f"canonical state has no event ledger entry: {entity_type}/{entity_id}"
            )
        try:
            payload = json.loads(event["payload_json"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise CanonicalIntegrityError(
                f"canonical event payload is invalid: {entity_type}/{entity_id}"
            ) from exc
        if (
            int(payload.get("version", -1)) != int(row["version"])
            or payload.get("state_hash") != row["state_hash"]
            or payload.get("state") != state
        ):
            raise CanonicalIntegrityError(
                f"canonical state does not match its latest event: {entity_type}/{entity_id}"
            )
        return state

    def _last_hash(self, connection: sqlite3.Connection, table: str) -> Optional[str]:
        if table not in {"state_events", "audit_events"}:
            raise ValueError("invalid event table")
        row = connection.execute(f"SELECT event_hash FROM {table} ORDER BY sequence DESC LIMIT 1").fetchone()
        return str(row["event_hash"]) if row else None

    def upsert_entity(
        self,
        entity_type: str,
        entity_id: str,
        state: Dict[str, Any],
        *,
        actor: str = "system",
        event_type: str = "state.changed",
    ) -> Optional[StateEvent]:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            event = self._upsert_entity_in_transaction(
                connection,
                entity_type,
                entity_id,
                state,
                actor=actor,
                event_type=event_type,
            )
            connection.commit()
        return event

    def _upsert_entity_in_transaction(
        self,
        connection: sqlite3.Connection,
        entity_type: str,
        entity_id: str,
        state: Dict[str, Any],
        *,
        actor: str,
        event_type: str,
    ) -> Optional[StateEvent]:
        state_json = _canonical_json(state)
        state_digest = hashlib.sha256(state_json.encode("utf-8")).hexdigest()
        occurred_at = _now()
        existing = connection.execute(
            "SELECT version, state_json, state_hash FROM canonical_state WHERE entity_type = ? AND entity_id = ?",
            (entity_type, entity_id),
        ).fetchone()
        if existing:
            self._decode_canonical_row(connection, existing, entity_type, entity_id)
        if existing and existing["state_hash"] == state_digest:
            return None
        version = int(existing["version"]) + 1 if existing else 1
        connection.execute(
            "INSERT INTO canonical_state(entity_type, entity_id, version, state_json, state_hash, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(entity_type, entity_id) DO UPDATE SET "
            "version=excluded.version, state_json=excluded.state_json, state_hash=excluded.state_hash, updated_at=excluded.updated_at",
            (entity_type, entity_id, version, state_json, state_digest, occurred_at),
        )
        previous_hash = self._last_hash(connection, "state_events")
        event_id = str(uuid.uuid4())
        payload = {"version": version, "state_hash": state_digest, "state": state}
        chain_material = {
            "id": event_id,
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "actor": actor,
            "occurred_at": occurred_at,
            "payload": payload,
            "previous_hash": previous_hash,
        }
        event_hash = content_hash(chain_material)
        cursor = connection.execute(
            "INSERT INTO state_events(id, event_type, entity_type, entity_id, actor, occurred_at, payload_json, previous_hash, event_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, event_type, entity_type, entity_id, actor, occurred_at, _canonical_json(payload), previous_hash, event_hash),
        )
        sequence = int(cursor.lastrowid)
        return StateEvent(sequence=sequence, event_hash=event_hash, **chain_material)

    def get_entity(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT version, state_json, state_hash FROM canonical_state WHERE entity_type = ? AND entity_id = ?",
                (entity_type, entity_id),
            ).fetchone()
            return self._decode_canonical_row(connection, row, entity_type, entity_id) if row else None

    def list_entities(self, entity_type: str) -> list[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT entity_id, version, state_json, state_hash FROM canonical_state "
                "WHERE entity_type = ? ORDER BY entity_id",
                (entity_type,),
            ).fetchall()
            return [
                self._decode_canonical_row(connection, row, entity_type, str(row["entity_id"]))
                for row in rows
            ]

    def ingest_repository_snapshot(
        self,
        *,
        system: Dict[str, Any],
        streams: Iterable[Dict[str, Any]],
        nodes: Iterable[Dict[str, Any]],
        actor: str,
    ) -> Dict[str, Any]:
        """Merge and persist one repository snapshot as a single transaction."""

        stream_states = [dict(item) for item in streams]
        node_states = [dict(item) for item in nodes]
        repository_id = str(system["id"])
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT entity_id, version, state_json, state_hash FROM canonical_state "
                "WHERE entity_type = 'work_node'"
            ).fetchall()
            stored_nodes = {
                str(row["entity_id"]): self._decode_canonical_row(
                    connection, row, "work_node", str(row["entity_id"])
                )
                for row in rows
            }
            stored_nodes = {
                entity_id: state for entity_id, state in stored_nodes.items()
                if state.get("repository_id") == repository_id
            }

            merged_nodes: list[Dict[str, Any]] = []
            for node in node_states:
                previous = stored_nodes.get(str(node.get("id")))
                if previous:
                    provenance: dict[tuple[Any, ...], Dict[str, Any]] = {}
                    for item in [*(previous.get("provenance") or []), *(node.get("provenance") or [])]:
                        key = (
                            item.get("repository_id"), item.get("path"), item.get("line_start"),
                            item.get("line_end"), item.get("source_kind"), item.get("content_hash"),
                        )
                        provenance[key] = item
                    node["provenance"] = list(provenance.values())
                    node["source_links"] = sorted(set(previous.get("source_links") or []) | set(node.get("source_links") or []))
                    node["lineage"] = list(dict.fromkeys([
                        *(previous.get("lineage") or []), *(node.get("lineage") or []),
                    ]))
                merged_nodes.append(node)

            self._upsert_entity_in_transaction(
                connection, "repository_system", repository_id, dict(system),
                actor=actor, event_type="repository.ingested",
            )
            for stream in stream_states:
                self._upsert_entity_in_transaction(
                    connection, "work_stream", str(stream["id"]), stream,
                    actor=actor, event_type="work_stream.ingested",
                )
            for node in merged_nodes:
                self._upsert_entity_in_transaction(
                    connection, "work_node", str(node["id"]), node,
                    actor=actor, event_type="work_node.ingested",
                )

            current_ids = {str(node["id"]) for node in merged_nodes}
            archived_nodes: list[Dict[str, Any]] = []
            for entity_id, previous in stored_nodes.items():
                if entity_id in current_ids or previous.get("archived") or previous.get("superseded"):
                    continue
                archived = dict(previous)
                archived["archived"] = True
                archived["state"] = "archived"
                marker = f"source-removed:{system.get('revision') or 'unknown-revision'}"
                archived["lineage"] = list(dict.fromkeys([
                    *(archived.get("lineage") or []), marker,
                ]))
                self._upsert_entity_in_transaction(
                    connection, "work_node", entity_id, archived,
                    actor=actor, event_type="work_node.archived",
                )
                archived_nodes.append(archived)
            connection.commit()
        return {
            "system": dict(system),
            "streams": stream_states,
            "nodes": merged_nodes,
            "archived_nodes": archived_nodes,
        }

    def append_audit(
        self,
        *,
        actor: str,
        capability_id: str,
        target: str,
        inputs_hash: str,
        result: str,
        evidence: Iterable[str],
        rollback_ref: str,
    ) -> AuditEvent:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            event = self._append_audit_in_transaction(
                connection,
                actor=actor,
                capability_id=capability_id,
                target=target,
                inputs_hash=inputs_hash,
                result=result,
                evidence=evidence,
                rollback_ref=rollback_ref,
            )
            connection.commit()
        return event

    def _append_audit_in_transaction(
        self,
        connection: sqlite3.Connection,
        *,
        actor: str,
        capability_id: str,
        target: str,
        inputs_hash: str,
        result: str,
        evidence: Iterable[str],
        rollback_ref: str,
    ) -> AuditEvent:
        occurred_at = _now()
        evidence_list = [str(item)[:800] for item in evidence]
        previous_hash = self._last_hash(connection, "audit_events")
        event_id = str(uuid.uuid4())
        chain_material = {
            "id": event_id,
            "actor": actor,
            "capability_id": capability_id,
            "target": target,
            "inputs_hash": inputs_hash,
            "result": result,
            "evidence": evidence_list,
            "rollback_ref": rollback_ref,
            "occurred_at": occurred_at,
            "previous_hash": previous_hash,
        }
        event_hash = content_hash(chain_material)
        cursor = connection.execute(
            "INSERT INTO audit_events(id, actor, capability_id, target, inputs_hash, result, evidence_json, rollback_ref, occurred_at, previous_hash, event_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id, actor, capability_id, target, inputs_hash, result,
                _canonical_json(evidence_list), rollback_ref, occurred_at, previous_hash, event_hash,
            ),
        )
        sequence = int(cursor.lastrowid)
        return AuditEvent(sequence=sequence, event_hash=event_hash, **chain_material)

    def create_navigation(
        self,
        state: Dict[str, Any],
        *,
        inputs_hash: str,
    ) -> None:
        """Persist a navigation plan and its audit record as one commit."""

        transaction_id = str(state["id"])
        actor = str(state["actor"])
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._upsert_entity_in_transaction(
                connection,
                "navigation_transaction",
                transaction_id,
                state,
                actor=actor,
                event_type="navigation.planned",
            )
            self._append_audit_in_transaction(
                connection,
                actor=actor,
                capability_id="bbc.navigation.plan",
                target=str(state["destination"]),
                inputs_hash=inputs_hash,
                result="succeeded",
                evidence=[f"state://navigation_transaction/{transaction_id}"],
                rollback_ref=f"navigation:{transaction_id}:interrupt",
            )
            connection.commit()

    def transition_navigation(
        self,
        transaction_id: str,
        *,
        actor: str,
        expected_version: int,
        target_state: str,
        interruption_reason: str | None,
        room_ids: set[str],
        ship_id: str,
        inputs_hash: str,
    ) -> Dict[str, Any]:
        """Validate and atomically persist one navigation lifecycle command."""

        allowed = {
            "planned": {"in_progress", "interrupted"},
            "in_progress": {"completed", "interrupted"},
            "completed": set(),
            "interrupted": set(),
        }
        event_types = {
            "in_progress": "navigation.started",
            "completed": "navigation.completed",
            "interrupted": "navigation.interrupted",
        }
        actions = {
            "in_progress": "start",
            "completed": "complete",
            "interrupted": "interrupt",
        }
        if target_state not in event_types:
            raise ValueError(f"invalid navigation target state: {target_state}")

        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT version, state_json, state_hash FROM canonical_state "
                "WHERE entity_type = 'navigation_transaction' AND entity_id = ?",
                (transaction_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"navigation transaction not found: {transaction_id}")
            transaction = self._decode_canonical_row(
                connection, row, "navigation_transaction", transaction_id
            )
            if transaction.get("actor") != actor:
                raise PermissionError("navigation transaction belongs to another actor")
            if (
                transaction.get("origin") not in room_ids or
                transaction.get("destination") not in room_ids or
                any(room not in room_ids for room in transaction.get("path", []))
            ):
                raise RuntimeError("navigation transaction contains an unknown room")

            current_state = str(transaction["state"])
            current_version = int(transaction.get("version", 1))
            if current_state == target_state:
                if expected_version not in {current_version, current_version - 1}:
                    raise StateConflict(
                        f"stale navigation version: expected {expected_version}, current {current_version}"
                    )
                if target_state == "interrupted" and interruption_reason != transaction.get("interruption_reason"):
                    raise RuntimeError("interrupted navigation reason is immutable")
                connection.rollback()
                return transaction
            if current_version != expected_version:
                raise StateConflict(
                    f"stale navigation version: expected {expected_version}, current {current_version}"
                )
            if target_state not in allowed[current_state]:
                raise RuntimeError(
                    f"navigation cannot transition from {current_state} to {target_state}"
                )

            if target_state == "in_progress":
                rows = connection.execute(
                    "SELECT entity_id, version, state_json, state_hash FROM canonical_state "
                    "WHERE entity_type = 'navigation_transaction'"
                ).fetchall()
                active = next((
                    item for item in (
                        self._decode_canonical_row(
                            connection, row, "navigation_transaction", str(row["entity_id"])
                        )
                        for row in rows
                    )
                    if item.get("persona_id") == transaction["persona_id"]
                    and item.get("id") != transaction_id
                    and item.get("state") == "in_progress"
                ), None)
                if active is not None:
                    raise StateConflict(
                        f"persona already has navigation in progress: {active['id']}"
                    )

            occurred_at = _now()
            transaction["state"] = target_state
            transaction["interruption_reason"] = interruption_reason
            transaction["version"] = current_version + 1
            transaction["updated_at"] = occurred_at
            if target_state == "in_progress":
                transaction["started_at"] = occurred_at
            elif target_state == "completed":
                transaction["completed_at"] = occurred_at
            else:
                transaction["interrupted_at"] = occurred_at
            self._upsert_entity_in_transaction(
                connection,
                "navigation_transaction",
                transaction_id,
                transaction,
                actor=actor,
                event_type=event_types[target_state],
            )

            persona_id = str(transaction["persona_id"])
            location_row = connection.execute(
                "SELECT version, state_json, state_hash FROM canonical_state "
                "WHERE entity_type = 'persona_location' AND entity_id = ?",
                (persona_id,),
            ).fetchone()
            current_location = self._decode_canonical_row(
                connection, location_row, "persona_location", persona_id
            ) if location_row else None
            location: Dict[str, Any] | None = None
            if target_state == "in_progress":
                room_id = str(transaction["origin"])
                location = {
                    "persona_id": persona_id,
                    "room_id": room_id,
                    "navigation_transaction_id": transaction_id,
                    "updated_at": occurred_at,
                }
            elif target_state == "completed":
                room_id = str(transaction["destination"])
                location = {
                    "persona_id": persona_id,
                    "room_id": room_id,
                    "navigation_transaction_id": None,
                    "updated_at": occurred_at,
                }
            else:
                location = {
                    "persona_id": persona_id,
                    "room_id": str((current_location or {}).get("room_id") or transaction["origin"]),
                    "navigation_transaction_id": None,
                    "updated_at": occurred_at,
                }
            if location is not None:
                self._upsert_entity_in_transaction(
                    connection,
                    "persona_location",
                    persona_id,
                    location,
                    actor=actor,
                    event_type="persona.location.changed",
                )

            ship_changed = False
            if target_state == "completed":
                ship_row = connection.execute(
                    "SELECT version, state_json, state_hash FROM canonical_state "
                    "WHERE entity_type = 'ship' AND entity_id = ?",
                    (ship_id,),
                ).fetchone()
                if ship_row is None:
                    raise RuntimeError("canonical ship state is missing")
                ship = self._decode_canonical_row(connection, ship_row, "ship", ship_id)
                if ship.get("active_room_id") != transaction["destination"]:
                    ship["active_room_id"] = transaction["destination"]
                    ship["updated_at"] = occurred_at
                    self._upsert_entity_in_transaction(
                        connection,
                        "ship",
                        ship_id,
                        ship,
                        actor=actor,
                        event_type="ship.active_room.changed",
                    )
                    ship_changed = True

            action = actions[target_state]
            evidence = [
                f"state://navigation_transaction/{transaction_id}",
                f"state://persona_location/{persona_id}",
            ]
            if ship_changed:
                evidence.append(f"state://ship/{ship_id}")
            self._append_audit_in_transaction(
                connection,
                actor=actor,
                capability_id=f"bbc.navigation.{action}",
                target=str(transaction["destination"]),
                inputs_hash=inputs_hash,
                result="succeeded",
                evidence=evidence,
                rollback_ref=(
                    f"navigation:{transaction_id}:interrupt"
                    if target_state == "in_progress"
                    else "not-applicable:terminal-navigation-state"
                ),
            )
            connection.commit()
        return transaction

    def create_room_conference(
        self,
        state: Dict[str, Any],
        *,
        inputs_hash: str,
    ) -> None:
        """Persist a room-conference plan and audit record as one commit."""

        conference_id = str(state["id"])
        actor = str(state["actor"])
        if state.get("state") != "planned" or int(state.get("version", 0)) != 1:
            raise ValueError("room conference must be created in planned version 1")
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT 1 FROM canonical_state WHERE entity_type = 'room_conference' AND entity_id = ?",
                (conference_id,),
            ).fetchone()
            if existing is not None:
                raise StateConflict(f"room conference already exists: {conference_id}")
            trigger_id = state.get("trigger_navigation_transaction_id")
            if trigger_id is not None:
                rows = connection.execute(
                    "SELECT entity_id, version, state_json, state_hash FROM canonical_state "
                    "WHERE entity_type = 'room_conference'"
                ).fetchall()
                duplicate = next((
                    item for item in (
                        self._decode_canonical_row(
                            connection, row, "room_conference", str(row["entity_id"])
                        )
                        for row in rows
                    )
                    if item.get("trigger_navigation_transaction_id") == trigger_id
                ), None)
                if duplicate is not None:
                    raise StateConflict(
                        f"navigation arrival already has conference: {duplicate['id']}"
                    )
            self._upsert_entity_in_transaction(
                connection,
                "room_conference",
                conference_id,
                state,
                actor=actor,
                event_type="room_conference.planned",
            )
            self._append_audit_in_transaction(
                connection,
                actor=actor,
                capability_id="bbc.room_conference.plan",
                target=str(state["room_id"]),
                inputs_hash=inputs_hash,
                result="succeeded",
                evidence=[f"state://room_conference/{conference_id}"],
                rollback_ref=f"room-conference:{conference_id}:fail",
            )
            connection.commit()

    def transition_room_conference(
        self,
        conference_id: str,
        *,
        actor: str,
        expected_version: int,
        target_state: str,
        failure_reason: str | None,
        inputs_hash: str,
    ) -> Dict[str, Any]:
        """Validate and atomically persist one room-conference command."""

        allowed = {
            "planned": {"running", "failed"},
            "running": {"failed"},
            "completed": set(),
            "failed": set(),
        }
        event_types = {
            "running": "room_conference.started",
            "failed": "room_conference.failed",
        }
        actions = {"running": "start", "failed": "fail"}
        if target_state not in event_types:
            raise ValueError(f"invalid room conference target state: {target_state}")

        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT version, state_json, state_hash FROM canonical_state "
                "WHERE entity_type = 'room_conference' AND entity_id = ?",
                (conference_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"room conference not found: {conference_id}")
            conference = self._decode_canonical_row(
                connection, row, "room_conference", conference_id
            )
            if conference.get("actor") != actor:
                raise PermissionError("room conference belongs to another actor")

            current_state = str(conference["state"])
            current_version = int(conference.get("version", 1))
            if current_state == target_state:
                if expected_version not in {current_version, current_version - 1}:
                    raise StateConflict(
                        f"stale room conference version: expected {expected_version}, current {current_version}"
                    )
                if target_state == "failed" and failure_reason != conference.get("failure_reason"):
                    raise RuntimeError("room conference failure reason is immutable")
                connection.rollback()
                return conference
            if current_version != expected_version:
                raise StateConflict(
                    f"stale room conference version: expected {expected_version}, current {current_version}"
                )
            if target_state not in allowed[current_state]:
                raise RuntimeError(
                    f"room conference cannot transition from {current_state} to {target_state}"
                )

            if target_state == "running":
                rows = connection.execute(
                    "SELECT entity_id, version, state_json, state_hash FROM canonical_state "
                    "WHERE entity_type = 'room_conference'"
                ).fetchall()
                active = next((
                    item for item in (
                        self._decode_canonical_row(
                            connection, row, "room_conference", str(row["entity_id"])
                        )
                        for row in rows
                    )
                    if item.get("room_id") == conference["room_id"]
                    and item.get("id") != conference_id
                    and item.get("state") == "running"
                ), None)
                if active is not None:
                    raise StateConflict(
                        f"room already has a running conference: {active['id']}"
                    )

            occurred_at = _now()
            conference["state"] = target_state
            conference["failure_reason"] = failure_reason
            conference["version"] = current_version + 1
            conference["updated_at"] = occurred_at
            if target_state == "running":
                conference["started_at"] = occurred_at
            else:
                conference["failed_at"] = occurred_at
            self._upsert_entity_in_transaction(
                connection,
                "room_conference",
                conference_id,
                conference,
                actor=actor,
                event_type=event_types[target_state],
            )
            action = actions[target_state]
            self._append_audit_in_transaction(
                connection,
                actor=actor,
                capability_id=f"bbc.room_conference.{action}",
                target=str(conference["room_id"]),
                inputs_hash=inputs_hash,
                result="succeeded",
                evidence=[f"state://room_conference/{conference_id}"],
                rollback_ref=(
                    f"room-conference:{conference_id}:fail"
                    if target_state == "running"
                    else "not-applicable:terminal-room-conference-state"
                ),
            )
            connection.commit()
        return conference

    def complete_room_conference(
        self,
        conference_id: str,
        *,
        actor: str,
        expected_version: int,
        completed_state: Dict[str, Any],
        memory_pointers: Iterable[Dict[str, Any]],
        retrieval_packet: Dict[str, Any],
        inputs_hash: str,
    ) -> Dict[str, Any]:
        """Commit conference results and staged memory as one atomic unit."""

        pointers = list(memory_pointers)
        if not pointers or len(pointers) > 12:
            raise ValueError("conference completion requires 1 to 12 memory pointers")
        pointer_ids = [str(pointer.get("id", "")) for pointer in pointers]
        if any(not pointer_id for pointer_id in pointer_ids) or len(pointer_ids) != len(set(pointer_ids)):
            raise ValueError("conference memory pointer ids must be non-empty and unique")
        if retrieval_packet.get("pointer_ids") != pointer_ids:
            raise ValueError("retrieval packet must reference exactly the staged memory pointers")
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT version, state_json, state_hash FROM canonical_state "
                "WHERE entity_type = 'room_conference' AND entity_id = ?",
                (conference_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"room conference not found: {conference_id}")
            current = self._decode_canonical_row(
                connection, row, "room_conference", conference_id
            )
            if current.get("actor") != actor:
                raise PermissionError("room conference belongs to another actor")
            if current.get("state") == "completed":
                current_version = int(current.get("version", 1))
                if expected_version in {current_version, current_version - 1}:
                    connection.rollback()
                    return current
                raise StateConflict(
                    f"stale room conference version: expected {expected_version}, current {current_version}"
                )
            if current.get("state") != "running":
                raise RuntimeError("only a running room conference can complete")
            if int(current.get("version", 1)) != expected_version:
                raise StateConflict(
                    f"stale room conference version: expected {expected_version}, current {current.get('version')}"
                )

            immutable_fields = (
                "id", "actor", "room_id", "objective", "repository_id", "work_node_id",
                "trigger_navigation_transaction_id", "participant_ids", "visitor_ids", "participants",
            )
            changed_fields = [
                key for key in immutable_fields if completed_state.get(key) != current.get(key)
            ]
            if changed_fields:
                raise ValueError(
                    "conference completion changed immutable fields: " + ", ".join(changed_fields)
                )
            for timestamp_field in ("created_at", "started_at"):
                current_timestamp = datetime.fromisoformat(
                    str(current.get(timestamp_field)).replace("Z", "+00:00")
                )
                completed_timestamp = datetime.fromisoformat(
                    str(completed_state.get(timestamp_field)).replace("Z", "+00:00")
                )
                if completed_timestamp != current_timestamp:
                    raise ValueError(
                        f"conference completion changed immutable field: {timestamp_field}"
                    )
            if completed_state.get("state") != "completed":
                raise ValueError("conference completion state must be completed")
            if int(completed_state.get("version", 0)) != expected_version + 1:
                raise ValueError("conference completion version is invalid")
            if not completed_state.get("completed_at") or completed_state.get("failed_at") is not None:
                raise ValueError("conference completion timestamps are invalid")
            packet_id = str(retrieval_packet.get("id", ""))
            if not packet_id or completed_state.get("retrieval_packet_id") != packet_id:
                raise ValueError("conference completion must reference its retrieval packet")
            repository_id = current.get("repository_id")
            if retrieval_packet.get("repository_id") != repository_id:
                raise ValueError("retrieval packet crossed the conference repository boundary")
            if any(pointer.get("repository_id") != repository_id for pointer in pointers):
                raise ValueError("memory pointer crossed the conference repository boundary")
            synthesis = completed_state.get("synthesis") or {}
            if synthesis.get("actions_executed") is not False:
                raise ValueError("conference synthesis cannot claim an executed action")

            for pointer in pointers:
                self._upsert_entity_in_transaction(
                    connection, "memory_pointer", str(pointer["id"]), pointer,
                    actor=actor, event_type="memory.pointer.indexed",
                )
            self._upsert_entity_in_transaction(
                connection, "retrieval_packet", str(retrieval_packet["id"]), retrieval_packet,
                actor=actor, event_type="memory.retrieval.completed",
            )
            self._upsert_entity_in_transaction(
                connection, "room_conference", conference_id, completed_state,
                actor=actor, event_type="room_conference.completed",
            )
            evidence = [
                f"state://room_conference/{conference_id}",
                f"state://retrieval_packet/{retrieval_packet['id']}",
                *[f"state://memory_pointer/{pointer['id']}" for pointer in pointers],
            ]
            self._append_audit_in_transaction(
                connection,
                actor=actor,
                capability_id="bbc.room_conference.execute",
                target=str(completed_state["room_id"]),
                inputs_hash=inputs_hash,
                result="succeeded",
                evidence=evidence,
                rollback_ref="not-applicable:read-only-conference-result",
            )
            connection.commit()
        return completed_state

    def list_events(self, *, after: int = 0, limit: int = 200) -> list[StateEvent]:
        bounded = max(1, min(int(limit), 1000))
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM state_events WHERE sequence > ? ORDER BY sequence LIMIT ?", (max(0, after), bounded)
            ).fetchall()
        return [StateEvent(
            sequence=row["sequence"], id=row["id"], event_type=row["event_type"],
            entity_type=row["entity_type"], entity_id=row["entity_id"], actor=row["actor"],
            occurred_at=row["occurred_at"], payload=json.loads(row["payload_json"]),
            previous_hash=row["previous_hash"], event_hash=row["event_hash"],
        ) for row in rows]

    def latest_event_sequence(self) -> int:
        """Return the high-water mark independently of page ordering or emptiness."""

        with self._connect() as connection:
            row = connection.execute("SELECT COALESCE(MAX(sequence), 0) AS sequence FROM state_events").fetchone()
        return int(row["sequence"])

    def list_audit(
        self,
        *,
        after: int = 0,
        limit: int = 200,
        capability_id: str | None = None,
    ) -> list[AuditEvent]:
        bounded = max(1, min(int(limit), 1000))
        query = "SELECT * FROM audit_events WHERE sequence > ?"
        params: list[Any] = [max(0, after)]
        if capability_id:
            query += " AND capability_id = ?"
            params.append(capability_id)
        query += " ORDER BY sequence LIMIT ?"
        params.append(bounded)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [AuditEvent(
            sequence=row["sequence"], id=row["id"], actor=row["actor"], capability_id=row["capability_id"],
            target=row["target"], inputs_hash=row["inputs_hash"], result=row["result"],
            evidence=json.loads(row["evidence_json"]), rollback_ref=row["rollback_ref"],
            occurred_at=row["occurred_at"], previous_hash=row["previous_hash"], event_hash=row["event_hash"],
        ) for row in rows]

    def backup(self, destination: str | Path) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.resolve() == self.path.resolve():
            raise ValueError("backup destination must differ from the live database")
        with self._lock, closing(self._connect()) as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
        return destination

    def _validate_database_connection(self, connection: sqlite3.Connection) -> None:
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute("PRAGMA integrity_check").fetchone()
            if not row or row[0] != "ok":
                raise ValueError("BBC database failed SQLite integrity check")
            objects = {
                (str(item["type"]), str(item["name"]))
                for item in connection.execute(
                    "SELECT type, name FROM sqlite_master WHERE type IN ('table', 'trigger')"
                )
            }
            required_tables = {
                ("table", "schema_migrations"), ("table", "canonical_state"),
                ("table", "state_events"), ("table", "audit_events"),
            }
            required_triggers = {
                ("trigger", "state_events_no_update"), ("trigger", "state_events_no_delete"),
                ("trigger", "audit_events_no_update"), ("trigger", "audit_events_no_delete"),
            }
            if not required_tables.issubset(objects) or not required_triggers.issubset(objects):
                raise ValueError("BBC database schema or immutable-ledger triggers are missing")
            required_columns = {
                "schema_migrations": {"version", "name", "checksum", "applied_at"},
                "canonical_state": {
                    "entity_type", "entity_id", "version", "state_json", "state_hash", "updated_at",
                },
                "state_events": {
                    "sequence", "id", "event_type", "entity_type", "entity_id", "actor",
                    "occurred_at", "payload_json", "previous_hash", "event_hash",
                },
                "audit_events": {
                    "sequence", "id", "actor", "capability_id", "target", "inputs_hash",
                    "result", "evidence_json", "rollback_ref", "occurred_at", "previous_hash", "event_hash",
                },
            }
            for table, expected_columns in required_columns.items():
                actual_columns = {
                    str(item["name"]) for item in connection.execute(f"PRAGMA table_info({table})")
                }
                if not expected_columns.issubset(actual_columns):
                    raise ValueError(f"BBC database table is missing required columns: {table}")
            trigger_requirements = {
                "state_events_no_update": ("before update on state_events", "raise(abort"),
                "state_events_no_delete": ("before delete on state_events", "raise(abort"),
                "audit_events_no_update": ("before update on audit_events", "raise(abort"),
                "audit_events_no_delete": ("before delete on audit_events", "raise(abort"),
            }
            trigger_sql = {
                str(item["name"]): " ".join(str(item["sql"] or "").casefold().split())
                for item in connection.execute(
                    "SELECT name, sql FROM sqlite_master WHERE type = 'trigger'"
                )
            }
            for name, fragments in trigger_requirements.items():
                if any(fragment not in trigger_sql.get(name, "") for fragment in fragments):
                    raise ValueError(f"BBC database immutable-ledger trigger is invalid: {name}")

            expected_migrations: dict[int, str] = {}
            for migration in sorted(self.migrations_dir.glob("[0-9][0-9][0-9]_*.sql")):
                version = int(migration.name.split("_", 1)[0])
                expected_migrations[version] = hashlib.sha256(
                    migration.read_text(encoding="utf-8").encode("utf-8")
                ).hexdigest()
            applied_migrations = {
                int(item["version"]): str(item["checksum"])
                for item in connection.execute("SELECT version, checksum FROM schema_migrations")
            }
            if expected_migrations != applied_migrations or max(applied_migrations, default=0) != SCHEMA_VERSION:
                raise ValueError("BBC database migration ledger is incompatible")

            chains = self._verify_event_chains_in_connection(connection)
            if not all(chains.values()):
                raise ValueError("BBC database event ledger failed hash-chain validation")
            canonical = self._verify_canonical_state_in_connection(connection)
            if not all(canonical.values()):
                raise ValueError("BBC canonical state does not match its event ledger")
        except sqlite3.DatabaseError as exc:
            raise ValueError("BBC database schema could not be validated") from exc

    def restore(self, source: str | Path) -> None:
        source = Path(source)
        if not source.is_file() or source.resolve() == self.path.resolve():
            raise ValueError("restore source must be a separate SQLite backup")
        with self._lock, tempfile.TemporaryDirectory(
            prefix="bbc-restore-", dir=self.path.parent
        ) as temporary_directory:
            staging_path = Path(temporary_directory) / "staging.db"
            rollback_path = Path(temporary_directory) / "rollback.db"
            with closing(sqlite3.connect(source)) as source_connection, closing(sqlite3.connect(staging_path)) as staging_target:
                source_connection.backup(staging_target)
            with closing(sqlite3.connect(staging_path)) as staging_probe:
                self._validate_database_connection(staging_probe)

            with closing(self._connect()) as live_source, closing(sqlite3.connect(rollback_path)) as rollback_target:
                live_source.backup(rollback_target)
            try:
                with closing(sqlite3.connect(staging_path)) as staging_source, closing(self._connect()) as live_target:
                    staging_source.backup(live_target)
                with closing(self._connect()) as restored_probe:
                    self._validate_database_connection(restored_probe)
            except Exception:
                with closing(sqlite3.connect(rollback_path)) as rollback_source, closing(self._connect()) as live_target:
                    rollback_source.backup(live_target)
                raise

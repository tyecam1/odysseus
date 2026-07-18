"""Migrated SQLite canonical state, event, and audit store for BBC v1."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .models import AuditEvent, SCHEMA_VERSION, StateEvent


class StateConflict(RuntimeError):
    """Canonical state changed after the caller read it."""


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

    def verify_event_chains(self) -> Dict[str, bool]:
        results: Dict[str, bool] = {}
        with self._connect() as connection:
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
        return results

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
            "SELECT version, state_hash FROM canonical_state WHERE entity_type = ? AND entity_id = ?",
            (entity_type, entity_id),
        ).fetchone()
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
                "SELECT state_json FROM canonical_state WHERE entity_type = ? AND entity_id = ?",
                (entity_type, entity_id),
            ).fetchone()
            return json.loads(row["state_json"]) if row else None

    def list_entities(self, entity_type: str) -> list[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT state_json FROM canonical_state WHERE entity_type = ? ORDER BY entity_id",
                (entity_type,),
            ).fetchall()
            return [json.loads(row["state_json"]) for row in rows]

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
                "SELECT state_json FROM canonical_state WHERE entity_type = 'navigation_transaction' AND entity_id = ?",
                (transaction_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"navigation transaction not found: {transaction_id}")
            transaction = json.loads(row["state_json"])
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
                    "SELECT state_json FROM canonical_state WHERE entity_type = 'navigation_transaction'"
                ).fetchall()
                active = next((
                    item for item in (json.loads(item["state_json"]) for item in rows)
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
                "SELECT state_json FROM canonical_state WHERE entity_type = 'persona_location' AND entity_id = ?",
                (persona_id,),
            ).fetchone()
            current_location = json.loads(location_row["state_json"]) if location_row else None
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
                    "SELECT state_json FROM canonical_state WHERE entity_type = 'ship' AND entity_id = ?",
                    (ship_id,),
                ).fetchone()
                if ship_row is None:
                    raise RuntimeError("canonical ship state is missing")
                ship = json.loads(ship_row["state_json"])
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
        with self._lock, self._connect() as source, sqlite3.connect(destination) as target:
            source.backup(target)
        return destination

    def restore(self, source: str | Path) -> None:
        source = Path(source)
        if not source.is_file() or source.resolve() == self.path.resolve():
            raise ValueError("restore source must be a separate SQLite backup")
        with sqlite3.connect(source) as probe:
            row = probe.execute("PRAGMA integrity_check").fetchone()
            if not row or row[0] != "ok":
                raise ValueError("restore source failed SQLite integrity check")
            version = probe.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]
            if int(version) != SCHEMA_VERSION:
                raise ValueError("restore source has an incompatible schema version")
        with self._lock, sqlite3.connect(source) as backup_connection, self._connect() as live_connection:
            backup_connection.backup(live_connection)
        if not self.integrity_check():
            raise RuntimeError("restored BBC database failed integrity check")

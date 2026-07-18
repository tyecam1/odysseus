import json
import sqlite3

import pytest

from src.bbc.store import BBCStateStore, CanonicalIntegrityError, content_hash


def test_migration_and_unchanged_state_do_not_emit_fake_events(tmp_path):
    store = BBCStateStore(tmp_path / "bbc.db")
    assert store.schema_version() == 1
    assert store.integrity_check()

    first = store.upsert_entity("ship", "one", {"id": "one", "room": "bridge"})
    duplicate = store.upsert_entity("ship", "one", {"id": "one", "room": "bridge"})
    changed = store.upsert_entity("ship", "one", {"id": "one", "room": "engineering"})

    assert first.sequence == 1
    assert duplicate is None
    assert changed.sequence == 2
    assert changed.previous_hash == first.event_hash
    assert store.get_entity("ship", "one")["room"] == "engineering"
    assert store.latest_event_sequence() == changed.sequence
    assert store.list_events(limit=1)[0].sequence != store.latest_event_sequence()
    assert store.verify_canonical_state() == {
        "hashes": True, "latest_events": True, "entity_coverage": True,
    }


def test_event_and_audit_tables_are_immutable_and_hash_chained(tmp_path):
    store = BBCStateStore(tmp_path / "bbc.db")
    event = store.upsert_entity("work_node", "wn:1", {"id": "wn:1"})
    first = store.append_audit(
        actor="operator", capability_id="bbc.repository.inspect", target="odysseus",
        inputs_hash=content_hash({"repository_id": "odysseus"}), result="succeeded",
        evidence=["repo://odysseus/ROADMAP.md"], rollback_ref="not-required:read-only",
    )
    second = store.append_audit(
        actor="operator", capability_id="bbc.repository.inspect", target="obsidian-phd",
        inputs_hash=content_hash({"repository_id": "obsidian-phd"}), result="failed",
        evidence=["FileNotFoundError"], rollback_ref="not-required:read-only",
    )
    assert second.previous_hash == first.event_hash
    assert store.verify_event_chains() == {"state_events": True, "audit_events": True}

    connection = sqlite3.connect(store.path)
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        connection.execute("DELETE FROM audit_events WHERE id = ?", (first.id,))
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        connection.execute("UPDATE state_events SET actor = 'tampered' WHERE id = ?", (event.id,))
    connection.close()


def test_backup_restore_is_verified_and_recovers_canonical_state(tmp_path):
    store = BBCStateStore(tmp_path / "bbc.db")
    store.upsert_entity("ship", "one", {"room": "bridge"})
    backup = store.backup(tmp_path / "backups" / "before.db")
    store.upsert_entity("ship", "one", {"room": "engineering"})
    assert store.get_entity("ship", "one")["room"] == "engineering"

    store.restore(backup)
    assert store.get_entity("ship", "one")["room"] == "bridge"
    assert store.integrity_check()


def test_canonical_state_tampering_is_detected_on_read_write_and_health_check(tmp_path):
    store = BBCStateStore(tmp_path / "bbc.db")
    store.upsert_entity("ship", "one", {"room": "bridge"})
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "UPDATE canonical_state SET state_json = ? WHERE entity_type = 'ship' AND entity_id = 'one'",
            (json.dumps({"room": "engineering"}),),
        )

    assert store.verify_canonical_state() == {
        "hashes": False, "latest_events": False, "entity_coverage": True,
    }
    with pytest.raises(CanonicalIntegrityError, match="hash mismatch"):
        store.get_entity("ship", "one")
    with pytest.raises(CanonicalIntegrityError, match="hash mismatch"):
        store.upsert_entity("ship", "one", {"room": "archive"})


def test_restore_rejects_forged_canonical_state_without_changing_live_database(tmp_path):
    store = BBCStateStore(tmp_path / "bbc.db")
    store.upsert_entity("ship", "one", {"room": "bridge"})
    backup = store.backup(tmp_path / "forged.db")
    forged_state = {"room": "archive"}
    with sqlite3.connect(backup) as connection:
        connection.execute(
            "UPDATE canonical_state SET state_json = ?, state_hash = ? "
            "WHERE entity_type = 'ship' AND entity_id = 'one'",
            (json.dumps(forged_state), content_hash(forged_state)),
        )
    store.upsert_entity("ship", "one", {"room": "engineering"})

    with pytest.raises(ValueError, match="canonical state"):
        store.restore(backup)
    assert store.get_entity("ship", "one")["room"] == "engineering"


def test_restore_rejects_a_backup_missing_immutable_ledger_guards(tmp_path):
    store = BBCStateStore(tmp_path / "bbc.db")
    store.upsert_entity("ship", "one", {"room": "bridge"})
    backup = store.backup(tmp_path / "unguarded.db")
    with sqlite3.connect(backup) as connection:
        connection.execute("DROP TRIGGER state_events_no_update")
    store.upsert_entity("ship", "one", {"room": "engineering"})

    with pytest.raises(ValueError, match="triggers are missing"):
        store.restore(backup)
    assert store.get_entity("ship", "one")["room"] == "engineering"


def test_restore_rejects_a_backup_with_missing_canonical_entities(tmp_path):
    store = BBCStateStore(tmp_path / "bbc.db")
    store.upsert_entity("ship", "one", {"room": "bridge"})
    backup = store.backup(tmp_path / "missing-state.db")
    with sqlite3.connect(backup) as connection:
        connection.execute(
            "DELETE FROM canonical_state WHERE entity_type = 'ship' AND entity_id = 'one'"
        )
    store.upsert_entity("ship", "one", {"room": "engineering"})

    with pytest.raises(ValueError, match="canonical state"):
        store.restore(backup)
    assert store.get_entity("ship", "one")["room"] == "engineering"


def test_applied_migration_checksum_cannot_be_rewritten(tmp_path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    source = next((__import__("pathlib").Path(__file__).parents[1] / "src" / "bbc" / "migrations").glob("001_*.sql"))
    target = migrations / source.name
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    store = BBCStateStore(tmp_path / "bbc.db", migrations_dir=migrations)
    target.write_text(target.read_text(encoding="utf-8") + "\n-- changed", encoding="utf-8")
    with pytest.raises(RuntimeError, match="checksum changed"):
        store.apply_migrations()

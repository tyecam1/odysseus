import json
import sqlite3

import pytest

from src.bbc.store import BBCStateStore, content_hash


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

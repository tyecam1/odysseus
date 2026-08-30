import importlib.util
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "update_database.py"


def test_update_database_has_single_main_guard():
    text = SCRIPT_PATH.read_text()

    assert text.count('if __name__ == "__main__":') == 1


def _load_update_database_module():
    """Load scripts/update_database.py as an isolated module.

    The script does `from database import DATABASE_URL, SessionLocal, Base`
    at import time, which only resolves if a `database` module is on
    sys.path — src/database.py (a re-export shim over core/database.py) is
    that module, so src/ must be on sys.path for the load to succeed. This
    is done in an isolated way (private module name, sys.path popped
    afterward) so it doesn't leak into other tests.
    """
    src_dir = str(REPO_ROOT / "src")
    inserted = src_dir not in sys.path
    if inserted:
        sys.path.insert(0, src_dir)
    try:
        spec = importlib.util.spec_from_file_location(
            "_update_database_script_under_test", SCRIPT_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if inserted:
            sys.path.remove(src_dir)


def test_add_source_events_table_migrates_a_legacy_pre_p1_table():
    """Reproduces the bug an independent adversarial review found: a
    `source_events` table that pre-dates the P1 external-ingest columns
    (this repo's real starting state, from an unrelated prior chat/session
    provenance workstream) must actually be upgraded, not silently
    skipped, or record_source_event() later fails with
    `OperationalError: no column named payload_ref`.
    """
    from sqlalchemy import create_engine, inspect

    module = _load_update_database_module()

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "legacy.db")

        # Pre-P1 shape: exactly the columns source_events had before this
        # programme's work, no payload_ref/received_at/status/
        # prior_content_hash/revision_count.
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE source_events (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                external_id TEXT,
                content_hash TEXT,
                domain TEXT NOT NULL DEFAULT 'neutral',
                sensitivity TEXT NOT NULL DEFAULT 'normal',
                payload TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO source_events (id, source, external_id, content_hash, "
            "domain, sensitivity, payload, created_at, updated_at) VALUES "
            "('legacy-1', 'chat', NULL, NULL, 'neutral', 'normal', NULL, "
            "'2026-01-01 00:00:00', '2026-01-01 00:00:00')"
        )
        conn.commit()
        conn.close()

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            # Before: the P1 columns genuinely do not exist yet.
            pre_columns = {c["name"] for c in inspect(engine).get_columns("source_events")}
            assert "payload_ref" not in pre_columns

            module.add_source_events_table(engine, db_path)

            post_columns = {c["name"] for c in inspect(engine).get_columns("source_events")}
            for expected in (
                "payload_ref",
                "received_at",
                "status",
                "prior_content_hash",
                "revision_count",
            ):
                assert expected in post_columns, f"migration did not add {expected}"

            # The pre-existing legacy row (no external_id) survived the
            # migration untouched, and got sane defaults for the new
            # NOT NULL-equivalent fields.
            conn = sqlite3.connect(db_path)
            cur = conn.execute(
                "SELECT source, status, revision_count FROM source_events WHERE id = 'legacy-1'"
            )
            source, status, revision_count = cur.fetchone()
            conn.close()
            assert source == "chat"
            assert status == "received"
            assert revision_count == 0

            # A fresh insert through this same migrated schema (raw SQL,
            # not via core.database — that module's own init_db() runs an
            # equivalent migration automatically on import, which would
            # mask whether *this* scripts/update_database.py code path
            # alone is sufficient) proves the new columns are genuinely
            # writable/readable, not just present-but-broken.
            conn = sqlite3.connect(db_path)
            conn.execute(
                "INSERT INTO source_events (id, source, external_id, content_hash, "
                "domain, sensitivity, payload, payload_ref, received_at, status, "
                "prior_content_hash, revision_count, created_at, updated_at) VALUES "
                "('p1-check', 'instagram', 'legacy-fix-check', 'deadbeef', 'neutral', "
                "'normal', NULL, '{\"ref\":\"x\"}', '2026-08-30 00:00:00', 'received', "
                "NULL, 0, '2026-08-30 00:00:00', '2026-08-30 00:00:00')"
            )
            conn.commit()
            cur = conn.execute(
                "SELECT payload_ref, status FROM source_events WHERE id = 'p1-check'"
            )
            payload_ref, status = cur.fetchone()
            conn.close()
            assert payload_ref == '{"ref":"x"}'
            assert status == "received"
        finally:
            engine.dispose()


def test_add_source_events_table_is_idempotent_on_an_already_upgraded_table():
    from sqlalchemy import create_engine, inspect

    module = _load_update_database_module()

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "fresh.db")
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            # First call creates the table fresh (source_events doesn't
            # exist yet in this brand-new DB).
            module.add_source_events_table(engine, db_path)
            columns_after_first = {c["name"] for c in inspect(engine).get_columns("source_events")}

            # Second call must be a no-op, not an error, and must not
            # change the schema.
            module.add_source_events_table(engine, db_path)
            columns_after_second = {c["name"] for c in inspect(engine).get_columns("source_events")}

            assert columns_after_first == columns_after_second
            assert "payload_ref" in columns_after_second
        finally:
            engine.dispose()

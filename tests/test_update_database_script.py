import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "update_database.py"


def test_update_database_has_single_main_guard():
    text = SCRIPT_PATH.read_text()

    assert text.count('if __name__ == "__main__":') == 1


def _run_migration_in_subprocess(db_path: str, function_name: str) -> dict:
    """Run one of scripts/update_database.py's migration functions against
    `db_path` in a fully separate Python process.

    scripts/update_database.py does `from database import DATABASE_URL,
    SessionLocal, Base` at import time, which only resolves with src/ on
    sys.path (src/database.py re-exports core/database.py). Loading it
    in-process (even via importlib with a private module name) still runs
    that import, which touches core.database — the same module this shared
    pytest session's fixtures depend on for a live in-memory DB. Running it
    in a throwaway subprocess instead means this test cannot possibly
    perturb the main test session's database/module state, regardless of
    what that import does internally.
    """
    code = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(REPO_ROOT / 'src')!r})\n"
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('_udb', {str(SCRIPT_PATH)!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "from sqlalchemy import create_engine, inspect\n"
        f"engine = create_engine('sqlite:///{db_path}')\n"
        f"mod.{function_name}(engine, {db_path!r})\n"
        "engine.dispose()\n"
        "print('MIGRATION_OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _columns(db_path: str, table: str) -> set:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cur.fetchall()}
    finally:
        conn.close()


def test_add_source_events_table_migrates_a_legacy_pre_p1_table():
    """Reproduces the bug an independent adversarial review found: a
    `source_events` table that pre-dates the P1 external-ingest columns
    (this repo's real starting state, from an unrelated prior chat/session
    provenance workstream) must actually be upgraded, not silently
    skipped, or record_source_event() later fails with
    `OperationalError: no column named payload_ref`.
    """
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

        pre_columns = _columns(db_path, "source_events")
        assert "payload_ref" not in pre_columns

        outcome = _run_migration_in_subprocess(db_path, "add_source_events_table")
        assert outcome["returncode"] == 0, (
            f"migration subprocess failed:\nstdout={outcome['stdout']}\n"
            f"stderr={outcome['stderr']}"
        )
        assert "MIGRATION_OK" in outcome["stdout"]

        post_columns = _columns(db_path, "source_events")
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

        # A fresh insert through this same migrated schema proves the new
        # columns are genuinely writable/readable, not just present.
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


def test_add_source_events_table_is_idempotent_on_an_already_upgraded_table():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "fresh.db")

        # First call creates the table fresh (source_events doesn't exist
        # yet in this brand-new DB).
        outcome = _run_migration_in_subprocess(db_path, "add_source_events_table")
        assert outcome["returncode"] == 0, outcome["stderr"]
        columns_after_first = _columns(db_path, "source_events")

        # Second call must be a no-op, not an error, and must not change
        # the schema.
        outcome = _run_migration_in_subprocess(db_path, "add_source_events_table")
        assert outcome["returncode"] == 0, outcome["stderr"]
        columns_after_second = _columns(db_path, "source_events")

        assert columns_after_first == columns_after_second
        assert "payload_ref" in columns_after_second

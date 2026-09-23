"""Stage 6 database layer (docs/aoteru-multihost-execution-implementation-plan.md
§6.0 S6.1/S6.5/S6.7): worker columns, Stage 6 partial-index predicates on
both dialects, the idempotent migration/backfill (U53), PostgreSQL DDL and
lock compilation (U54), and the SQLite `BEGIN IMMEDIATE` proof that
`lease_serialized_transaction` really holds the write lock (U29 variant)."""
import os
import sqlite3
import threading
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateIndex

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()

import core.database as cdb
from core.database import EstateExecution, ParkLease


def _index(table, name):
    return next(ix for ix in table.__table__.indexes if ix.name == name)


def test_u54_partial_indexes_declare_postgresql_predicates():
    execution_ddl = str(CreateIndex(_index(EstateExecution, "ix_estate_executions_active_lease_unique"))
                        .compile(dialect=postgresql.dialect()))
    lease_ddl = str(CreateIndex(_index(ParkLease, "ix_park_leases_active_repo_unique"))
                    .compile(dialect=postgresql.dialect()))
    assert "WHERE worktree_resolution = 'unresolved'" in execution_ddl
    assert "WHERE status IN ('active', 'preparing')" in lease_ddl


def test_u54_lock_statement_compiles_select_for_update_on_postgresql():
    by_lease = str(cdb._lease_lock_statement(lease_id="L1").compile(dialect=postgresql.dialect()))
    by_repo = str(cdb._lease_lock_statement(repo_id="odysseus").compile(dialect=postgresql.dialect()))
    for sql in (by_lease, by_repo):
        assert "FROM park_leases" in sql and sql.rstrip().endswith("FOR UPDATE")
    assert "status IN" in by_repo
    with pytest.raises(ValueError):
        cdb._lease_lock_statement()


# ---------------------------------------------------------------------
# U53 migration
# ---------------------------------------------------------------------

_PRE_STAGE6_COLUMNS = (
    "worker_handle_json", "worker_attestation_json", "last_observed_at",
    "execution_deadline_at", "worktree_resolution", "admission_head_sha", "spool_released_at",
)


@pytest.fixture
def pre_stage6_db(monkeypatch, tmp_path):
    """A file DB shaped like the pre-Stage-6 schema: no worker columns,
    old lifecycle-state execution index, old active-only lease index."""
    path = tmp_path / "app.db"
    engine = create_engine(f"sqlite:///{path}", poolclass=NullPool)
    cdb.Base.metadata.create_all(engine, tables=[ParkLease.__table__, EstateExecution.__table__])
    engine.dispose()
    conn = sqlite3.connect(path)
    conn.execute("DROP INDEX ix_estate_executions_active_lease_unique")
    conn.execute("DROP INDEX ix_estate_executions_worktree_resolution")
    for name in _PRE_STAGE6_COLUMNS:
        conn.execute(f"ALTER TABLE estate_executions DROP COLUMN {name}")
    conn.execute("CREATE UNIQUE INDEX ix_estate_executions_active_lease_unique ON estate_executions "
                 "(lease_id) WHERE lifecycle_state IN ('accepted', 'running')")
    conn.execute("DROP INDEX ix_park_leases_active_repo_unique")
    conn.execute("CREATE UNIQUE INDEX ix_park_leases_active_repo_unique ON park_leases (repo_id) "
                 "WHERE status = 'active'")
    conn.commit()
    conn.close()
    monkeypatch.setattr(cdb, "engine", create_engine(f"sqlite:///{path}", poolclass=NullPool))
    return path


def _seed(path, leases, executions):
    conn = sqlite3.connect(path)
    now = "2026-09-23 12:00:00"
    for lease_id, repo, status in leases:
        conn.execute(
            "INSERT INTO park_leases (id, repo_id, host_id, worktree_path, status, heartbeat_at, "
            "created_at, updated_at) VALUES (?, ?, 'hz2-workstation', '/w', ?, ?, ?, ?)",
            (lease_id, repo, status, now, now, now),
        )
    for execution_id, lease_id, state in executions:
        conn.execute(
            "INSERT INTO estate_executions (id, objective, executor, provider, host_id, repo_id, "
            "lease_id, lifecycle_state, submitted_at, created_at, updated_at) "
            "VALUES (?, 'o', 'codex-write', 'codex', 'hz2-workstation', 'odysseus', ?, ?, ?, ?, ?)",
            (execution_id, lease_id, state, now, now, now),
        )
    conn.commit()
    conn.close()


def _index_sql(path, name):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT sql FROM sqlite_master WHERE name = ?", (name,)).fetchone()[0]
    finally:
        conn.close()


def _resolutions(path):
    conn = sqlite3.connect(path)
    try:
        return dict(conn.execute("SELECT id, worktree_resolution FROM estate_executions").fetchall())
    finally:
        conn.close()


def test_u53_backfill_and_index_recreation_is_idempotent(pre_stage6_db):
    _seed(pre_stage6_db,
          leases=[("L-active", "odysseus", "active"), ("L-old", "odysseus", "released")],
          executions=[("E-live", "L-active", "succeeded"), ("E-old", "L-old", "succeeded"),
                      ("E-nolease", None, "failed")])
    cdb._migrate_add_estate_execution_worker_columns()
    assert _resolutions(pre_stage6_db) == {
        "E-live": "unresolved", "E-old": "legacy_closed", "E-nolease": "legacy_closed",
    }
    assert "worktree_resolution = 'unresolved'" in _index_sql(
        pre_stage6_db, "ix_estate_executions_active_lease_unique")
    assert "status IN ('active', 'preparing')" in _index_sql(
        pre_stage6_db, "ix_park_leases_active_repo_unique")

    # Second init_db pass: no error, no change.
    cdb._migrate_add_estate_execution_worker_columns()
    assert _resolutions(pre_stage6_db)["E-live"] == "unresolved"

    # The new index now enforces one unresolved row per lease.
    conn = sqlite3.connect(pre_stage6_db)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO estate_executions (id, objective, executor, provider, host_id, repo_id, "
            "lease_id, lifecycle_state, worktree_resolution, submitted_at, created_at, updated_at) "
            "VALUES ('E-dup', 'o', 'codex-write', 'codex', 'h', 'odysseus', 'L-active', 'failed', "
            "'unresolved', '2026-09-23', '2026-09-23', '2026-09-23')"
        )
    conn.close()


def test_u53_duplicate_unresolved_rows_keep_old_index_and_log(pre_stage6_db, caplog):
    _seed(pre_stage6_db,
          leases=[("L-active", "odysseus", "active")],
          executions=[("E-a", "L-active", "failed"), ("E-b", "L-active", "succeeded")])
    with caplog.at_level("ERROR"):
        cdb._migrate_add_estate_execution_worker_columns()
    assert "lifecycle_state IN ('accepted', 'running')" in _index_sql(
        pre_stage6_db, "ix_estate_executions_active_lease_unique")
    assert any("L-active" in record.getMessage() for record in caplog.records)
    # Both rows stay unresolved, so the in-Python rule still blocks the lease.
    assert set(_resolutions(pre_stage6_db).values()) == {"unresolved"}


# ---------------------------------------------------------------------
# lease_serialized_transaction (S6.5)
# ---------------------------------------------------------------------

@pytest.fixture
def file_db(monkeypatch):
    session_local, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", session_local)
    yield tmpfile.name
    engine.dispose()
    os.unlink(tmpfile.name)


def test_u29_helper_really_holds_the_sqlite_write_lock(file_db, monkeypatch):
    """A second raw connection cannot write while the helper's transaction
    is open, even before the helper has performed any write itself."""
    monkeypatch.setattr(cdb, "LEASE_SERIALIZATION_BUSY_TIMEOUT_S", 0.2)
    entered, release = threading.Event(), threading.Event()

    def _holder():
        with cdb.lease_serialized_transaction(lease_id="L1") as db:
            db.query(ParkLease).filter(ParkLease.id == "L1").one_or_none()  # read only
            entered.set()
            release.wait(5)

    thread = threading.Thread(target=_holder)
    thread.start()
    assert entered.wait(5)
    other = sqlite3.connect(file_db, timeout=0.2)
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            other.execute(
                "INSERT INTO park_leases (id, repo_id, host_id, worktree_path, status, heartbeat_at, "
                "created_at, updated_at) VALUES ('X', 'r', 'h', '/w', 'active', '2026', '2026', '2026')"
            )
    finally:
        other.close()
        release.set()
        thread.join(5)


def test_helper_commits_on_exit_and_rolls_back_on_error(file_db):
    with cdb.lease_serialized_transaction(repo_id="odysseus") as db:
        db.add(ParkLease(id="L-commit", repo_id="odysseus", host_id="h", worktree_path="/w"))
    with pytest.raises(RuntimeError):
        with cdb.lease_serialized_transaction(repo_id="other") as db:
            db.add(ParkLease(id="L-rollback", repo_id="other", host_id="h", worktree_path="/w"))
            db.flush()
            raise RuntimeError("boom")
    with cdb.get_db_session() as db:
        ids = {row.id for row in db.query(ParkLease).all()}
    assert ids == {"L-commit"}


def test_helper_fails_closed_when_lock_is_busy(file_db, monkeypatch):
    monkeypatch.setattr(cdb, "LEASE_SERIALIZATION_BUSY_TIMEOUT_S", 0.1)
    blocker = sqlite3.connect(file_db, timeout=0.1, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        started = time.monotonic()
        with pytest.raises(cdb.LeaseSerializationBusy):
            with cdb.lease_serialized_transaction(lease_id="L1"):
                pytest.fail("must never run the body unlocked")
        assert time.monotonic() - started < 5
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()

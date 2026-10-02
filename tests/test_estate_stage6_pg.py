"""Stage 6 estate-execution migration on a REAL PostgreSQL schema.

Skipped unless ODYSSEUS_TEST_POSTGRES_URL points at a throwaway PostgreSQL (for example
`postgresql+psycopg2://postgres@/postgres?host=/path/to/socket-dir`). Each test builds its own schema, so the
database itself is never altered beyond that.

`Base.metadata.create_all` only creates missing tables; on an existing pre-Stage-6 database it neither adds
columns nor replaces an index. These tests build a pre-Stage-6 schema from the real models, migrate it, and then
drive the write lane (create / update / admission control / recovery read) through the migrated tables.
"""
import datetime
import logging
import os
import uuid

import pytest

PG_URL = os.environ.get("ODYSSEUS_TEST_POSTGRES_URL", "").strip()
pytestmark = pytest.mark.skipif(not PG_URL, reason="ODYSSEUS_TEST_POSTGRES_URL not set (needs a real PostgreSQL)")

from sqlalchemy import create_engine, inspect, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from tests.helpers.import_state import clear_fake_database_modules  # noqa: E402

clear_fake_database_modules()

import core.database as cdb  # noqa: E402
from core.database import EstateExecution, ParkLease  # noqa: E402

_WORKER_COLUMNS = (
    "worker_handle_json", "worker_attestation_json", "last_observed_at",
    "execution_deadline_at", "worktree_resolution", "admission_head_sha", "spool_released_at",
)
NOW = "2026-09-23 12:00:00"


@pytest.fixture
def schema():
    """A throwaway schema; yields (engine bound to it, helper to build the pre-Stage-6 shape)."""
    name = "t_" + uuid.uuid4().hex[:12]
    admin = create_engine(PG_URL, poolclass=NullPool)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{name}"'))
    engine = create_engine(PG_URL, poolclass=NullPool, connect_args={"options": f"-csearch_path={name}"})
    yield engine
    engine.dispose()
    with admin.begin() as conn:
        conn.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
    admin.dispose()


def _build_pre_stage6(engine):
    """The pre-Stage-6 shape: no worker columns, the old lifecycle-state execution index, the old active-only
    lease index -- derived from the real models so it cannot drift from them."""
    cdb.Base.metadata.create_all(engine, tables=[ParkLease.__table__, EstateExecution.__table__])
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX ix_estate_executions_active_lease_unique"))
        conn.execute(text("DROP INDEX ix_estate_executions_worktree_resolution"))
        for name in _WORKER_COLUMNS:
            conn.execute(text(f"ALTER TABLE estate_executions DROP COLUMN {name}"))
        conn.execute(text("CREATE UNIQUE INDEX ix_estate_executions_active_lease_unique ON estate_executions "
                          "(lease_id) WHERE lifecycle_state IN ('accepted', 'running')"))
        conn.execute(text("DROP INDEX ix_park_leases_active_repo_unique"))
        conn.execute(text("CREATE UNIQUE INDEX ix_park_leases_active_repo_unique ON park_leases (repo_id) "
                          "WHERE status = 'active'"))


def _seed(engine, leases, executions):
    with engine.begin() as conn:
        for lease_id, repo, status in leases:
            conn.execute(text(
                "INSERT INTO park_leases (id, repo_id, host_id, worktree_path, status, heartbeat_at, created_at, "
                "updated_at) VALUES (:i, :r, 'hz2-workstation', '/w', :s, :n, :n, :n)"),
                {"i": lease_id, "r": repo, "s": status, "n": NOW})
        for execution_id, lease_id, state in executions:
            conn.execute(text(
                "INSERT INTO estate_executions (id, objective, executor, provider, host_id, repo_id, lease_id, "
                "lifecycle_state, submitted_at, created_at, updated_at) VALUES (:i, 'o', 'codex-write', 'codex', "
                "'hz2-workstation', 'odysseus', :l, :s, :n, :n, :n)"),
                {"i": execution_id, "l": lease_id, "s": state, "n": NOW})


def _resolutions(engine):
    with engine.connect() as conn:
        return dict(conn.execute(text("SELECT id, worktree_resolution FROM estate_executions")).fetchall())


def _index_oids(engine):
    with engine.connect() as conn:
        return dict(conn.execute(text(
            "SELECT c.relname, c.oid::int FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = current_schema() AND c.relkind = 'i' AND c.relname IN "
            "('ix_estate_executions_active_lease_unique', 'ix_park_leases_active_repo_unique', "
            "'ix_estate_executions_worktree_resolution')")).fetchall())


@pytest.fixture
def pre_stage6(schema, monkeypatch):
    _build_pre_stage6(schema)
    monkeypatch.setattr(cdb, "engine", schema)
    return schema


def test_pre_stage6_schema_really_lacks_the_columns_and_create_all_does_not_add_them(pre_stage6):
    """The premise of the finding: create_all leaves an existing table alone."""
    cdb.Base.metadata.create_all(pre_stage6)
    names = {c["name"] for c in inspect(pre_stage6).get_columns("estate_executions")}
    assert not set(_WORKER_COLUMNS) & names


def test_migration_adds_columns_backfills_and_replaces_both_indexes(pre_stage6):
    _seed(pre_stage6,
          leases=[("L-active", "odysseus", "active"), ("L-old", "odysseus", "released")],
          executions=[("E-live", "L-active", "succeeded"), ("E-old", "L-old", "succeeded"),
                      ("E-nolease", None, "failed")])
    cdb._migrate_add_estate_execution_worker_columns_postgresql()

    cols = {c["name"]: c for c in inspect(pre_stage6).get_columns("estate_executions")}
    assert set(_WORKER_COLUMNS) <= set(cols)
    assert cols["worktree_resolution"]["nullable"] is False
    assert "unresolved" in str(cols["worktree_resolution"]["default"])
    assert "TIMESTAMP" in str(cols["last_observed_at"]["type"]).upper()
    assert "TIMESTAMP" in str(cols["spool_released_at"]["type"]).upper()
    # S6.1 backfill: only a row under a still-active lease stays blocking; existing rows lose no data.
    assert _resolutions(pre_stage6) == {"E-live": "unresolved", "E-old": "legacy_closed", "E-nolease": "legacy_closed"}
    with pre_stage6.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM estate_executions")).scalar() == 3
    assert "ix_estate_executions_worktree_resolution" in _index_oids(pre_stage6)

    # The new execution index enforces one UNRESOLVED row per lease whatever its lifecycle state...
    with pytest.raises(IntegrityError):
        with pre_stage6.begin() as conn:
            conn.execute(text(
                "INSERT INTO estate_executions (id, objective, executor, provider, host_id, repo_id, lease_id, "
                "lifecycle_state, worktree_resolution, submitted_at, created_at, updated_at) VALUES ('E-dup', 'o', "
                "'codex-write', 'codex', 'h', 'odysseus', 'L-active', 'failed', 'unresolved', :n, :n, :n)"), {"n": NOW})
    # ...and the lease index now blocks a second 'preparing' slot, which the old `status = 'active'` index let through.
    with pre_stage6.begin() as conn:
        conn.execute(text(
            "INSERT INTO park_leases (id, repo_id, host_id, worktree_path, status, heartbeat_at, created_at, "
            "updated_at) VALUES ('L-prep', 'other-repo', 'h', '/w', 'preparing', :n, :n, :n)"), {"n": NOW})
    with pytest.raises(IntegrityError):
        with pre_stage6.begin() as conn:
            conn.execute(text(
                "INSERT INTO park_leases (id, repo_id, host_id, worktree_path, status, heartbeat_at, created_at, "
                "updated_at) VALUES ('L-prep2', 'other-repo', 'h', '/w', 'active', :n, :n, :n)"), {"n": NOW})


def test_rerunning_the_migration_is_a_no_op(pre_stage6):
    _seed(pre_stage6, leases=[("L-active", "odysseus", "active")], executions=[("E-live", "L-active", "succeeded")])
    cdb._migrate_add_estate_execution_worker_columns_postgresql()
    oids, resolutions = _index_oids(pre_stage6), _resolutions(pre_stage6)
    cdb._migrate_add_estate_execution_worker_columns_postgresql()
    cdb._migrate_add_estate_execution_worker_columns_postgresql()
    assert _index_oids(pre_stage6) == oids, "indexes were rebuilt on a re-run"
    assert _resolutions(pre_stage6) == resolutions


def test_duplicate_unresolved_rows_keep_the_old_index_and_log(pre_stage6, caplog):
    _seed(pre_stage6, leases=[("L-active", "odysseus", "active")],
          executions=[("E-a", "L-active", "failed"), ("E-b", "L-active", "succeeded")])
    with caplog.at_level(logging.ERROR):
        cdb._migrate_add_estate_execution_worker_columns_postgresql()
    assert any("L-active" in record.getMessage() for record in caplog.records)
    # Both rows stay unresolved (so the in-Python rule still blocks the lease) and no data was lost.
    assert set(_resolutions(pre_stage6).values()) == {"unresolved"}
    with pre_stage6.connect() as conn:
        old = conn.execute(text("SELECT indexdef FROM pg_indexes WHERE schemaname = current_schema() "
                                "AND indexname = 'ix_estate_executions_active_lease_unique'")).scalar()
    assert "lifecycle_state" in old


def test_a_schema_built_by_create_all_migrates_without_change(schema, monkeypatch):
    """A fresh PostgreSQL database (tables made from the current models) must also run the migration cleanly."""
    cdb.Base.metadata.create_all(schema, tables=[ParkLease.__table__, EstateExecution.__table__])
    monkeypatch.setattr(cdb, "engine", schema)
    _seed(schema, leases=[("L1", "odysseus", "active")], executions=[("E1", "L1", "running")])
    cdb._migrate_add_estate_execution_worker_columns_postgresql()
    cdb._migrate_add_estate_execution_worker_columns_postgresql()
    assert _resolutions(schema) == {"E1": "unresolved"}


def test_the_migration_is_a_no_op_on_other_dialects(monkeypatch, tmp_path):
    sqlite_engine = create_engine(f"sqlite:///{tmp_path / 'x.db'}", poolclass=NullPool)
    monkeypatch.setattr(cdb, "engine", sqlite_engine)
    cdb._migrate_add_estate_execution_worker_columns_postgresql()  # must not raise or touch anything


# ---------------------------------------------------------------------------------------------------------------
# the write lane against the migrated PostgreSQL schema
# ---------------------------------------------------------------------------------------------------------------

def test_write_lane_create_update_admission_and_recovery_on_postgresql(pre_stage6, monkeypatch):
    import src.estate_router as router

    _seed(pre_stage6, leases=[("L-active", "odysseus", "active")], executions=[("E-legacy", "L-active", "succeeded")])
    cdb._migrate_add_estate_execution_worker_columns_postgresql()
    # the legacy row held the slot (unresolved under an active lease): resolve it so a new write may start
    with pre_stage6.begin() as conn:
        conn.execute(text("UPDATE estate_executions SET worktree_resolution = 'finalized' WHERE id = 'E-legacy'"))
    monkeypatch.setattr(cdb, "SessionLocal", sessionmaker(bind=pre_stage6, autoflush=False, autocommit=False))

    args = dict(decision_id=None, objective="write something", executor="codex-write", provider="codex",
                host_id="hz2-workstation", repo_id="odysseus", lease_id="L-active",
                worktree_path="/w", branch="feat/x")
    first = router._create_estate_execution(**args)
    assert _resolutions(pre_stage6)[first] == "unresolved"

    # admission control: the database itself rejects a second unresolved row for the lease
    with pytest.raises(router._ConcurrentExecutionExists):
        router._create_estate_execution(**args)
    assert router._in_flight_execution_for_lease("L-active")["execution_id"] == first

    # state transitions through the single write path, including the Stage 6 worker columns
    now = datetime.datetime(2026, 9, 23, 12, 5, 0)
    router._update_estate_execution(first, lifecycle_state="running", worker_pid=4242,
                                    worker_handle_json='{"run": "r1"}', last_observed_at=now,
                                    execution_deadline_at=now + datetime.timedelta(hours=1),
                                    admission_head_sha="abc123")
    with cdb.SessionLocal() as db:
        row = db.query(EstateExecution).filter(EstateExecution.id == first).one()
        assert (row.lifecycle_state, row.worker_pid, row.admission_head_sha) == ("running", 4242, "abc123")
        assert row.last_observed_at == now and row.worker_handle_json == '{"run": "r1"}'

    # finalising frees the slot: the next write on the lease is admitted
    router._update_estate_execution(first, lifecycle_state="succeeded", worktree_resolution="finalized",
                                    spool_released_at=now)
    assert router._in_flight_execution_for_lease("L-active") is None
    second = router._create_estate_execution(**args)
    assert second != first

    # the lease serialisation helper takes a real SELECT ... FOR UPDATE on PostgreSQL and commits on exit
    with cdb.lease_serialized_transaction(lease_id="L-active") as db:
        lease = db.query(ParkLease).filter(ParkLease.id == "L-active").one()
        lease.worktree_path = "/w2"
    with cdb.SessionLocal() as db:
        assert db.query(ParkLease).filter(ParkLease.id == "L-active").one().worktree_path == "/w2"

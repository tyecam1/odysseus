"""Stage 6 lease authority (plan §6.0 S6.2 ordinary release, S6.3
exact-lease renewal, S6.4 lease_authority_state, S6.5 single-transaction
reclaim): U30, U31, U32, U43, U44, U45, U29(c)."""
import os
import re
import threading
from datetime import timedelta
from pathlib import Path

import pytest

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()

import core.database as cdb
from core.database import EstateExecution, ParkLease, get_db_session, utcnow_naive
from src import park_lease_ops as ops
from src import estate_router

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db(monkeypatch):
    session_local, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", session_local)
    yield
    engine.dispose()
    os.unlink(tmpfile.name)


def _lease(lease_id="L1", *, repo="odysseus", host="hz2-workstation", status="active", stale=False):
    heartbeat = utcnow_naive() - timedelta(seconds=cdb.PARK_LEASE_STALE_SECONDS + 60 if stale else 0)
    with get_db_session() as s:
        s.add(ParkLease(id=lease_id, repo_id=repo, host_id=host, worktree_path="/w/x",
                        branch="feat/x", status=status, heartbeat_at=heartbeat))


def _execution(execution_id, lease_id="L1", *, state="running", resolution="unresolved",
               host="hz2-workstation", repo="odysseus"):
    with get_db_session() as s:
        s.add(EstateExecution(
            id=execution_id, objective="o", executor="codex-write", provider="codex",
            host_id=host, repo_id=repo, lease_id=lease_id, worktree_path="/w/x", branch="feat/x",
            lifecycle_state=state, worktree_resolution=resolution,
            worker_handle_json='{"dispatch_state": "pending_start"}',
        ))


def _lease_row(lease_id):
    with get_db_session() as s:
        row = s.query(ParkLease).filter(ParkLease.id == lease_id).one()
        return row.status, row.heartbeat_at


@pytest.mark.parametrize("state", ["accepted", "running"])
def test_u30_running_execution_protects_stale_lease(db, state):
    _lease(stale=True)
    _execution("E1", state=state)
    with get_db_session() as s:
        authority = ops.lease_authority_state(s, s.query(ParkLease).one())
    assert authority["heartbeat_stale"] is True
    assert authority["reclaimable"] is False and authority["authoritative"] is True
    assert authority["protected_by_execution_id"] == "E1"
    with pytest.raises(ops.ParkConflict):
        ops.park_repo("odysseus", "hz2-workstation", "/w/y", branch="feat/y")
    assert _lease_row("L1")[0] == "active"


def test_u31_lost_execution_still_blocks_stale_reclaim(db):
    _lease(stale=True)
    _execution("E1", state="lost")
    with pytest.raises(ops.ParkConflict):
        ops.park_repo("odysseus", "desktop-in7o23d", "/w/y")
    assert _lease_row("L1")[0] == "active"


@pytest.mark.parametrize("state", ["accepted", "running", "lost", "succeeded", "failed",
                                   "timed_out", "interrupted"])
def test_u32_ordinary_release_refused_while_unresolved(db, state):
    _lease()
    _execution("E1", state=state)
    with pytest.raises(ops.LeaseHasUnresolvedExecution) as info:
        ops.release_repo("odysseus", host_id="hz2-workstation")
    assert info.value.execution_id == "E1" and info.value.lifecycle_state == state
    assert info.value.next_action == ops.UNRESOLVED_NEXT_ACTION[state]
    assert _lease_row("L1")[0] == "active"


def test_u32_pending_start_placeholder_row_blocks_release(db):
    _lease()
    _execution("E1", state="accepted")   # carries the pending_start placeholder
    with pytest.raises(ops.LeaseHasUnresolvedExecution):
        ops.release_repo("odysseus")


@pytest.mark.parametrize("resolutions", [[], ["not_started"], ["finalized"], ["not_started", "finalized"]])
def test_u32_release_allowed_with_only_resolved_rows(db, resolutions):
    _lease()
    for index, resolution in enumerate(resolutions):
        _execution(f"E{index}", state="succeeded" if resolution == "finalized" else "failed",
                   resolution=resolution)
    result = ops.release_repo("odysseus")
    assert result["lease_id"] == "L1" and _lease_row("L1")[0] == "released"


def test_u32_operator_heartbeat_allowed_while_running_refused_while_preparing(db):
    _lease()
    _execution("E1", state="running")
    assert ops.heartbeat_repo("odysseus")["lease_id"] == "L1"
    with get_db_session() as s:
        s.query(ParkLease).delete()
    _lease("P1", status="preparing")
    with pytest.raises(ops.NoActiveLease, match="preparing reservation"):
        ops.heartbeat_repo("odysseus")


def test_u33_renew_lease_for_execution_renews_exact_lease(db):
    _lease(stale=True)
    _execution("E1", state="running")
    before = _lease_row("L1")[1]
    assert ops.renew_lease_for_execution("E1") is True
    assert _lease_row("L1")[1] > before
    # never for a terminal/resolved row
    _execution("E2", "L1", state="succeeded", resolution="finalized")
    assert ops.renew_lease_for_execution("E2") is False


def test_u43_exact_lease_renewal_cannot_renew_a_later_lease(db):
    _lease("L1")
    _execution("E1", "L1", state="running")
    with get_db_session() as s:
        s.query(ParkLease).filter(ParkLease.id == "L1").update({"status": "released"})
    _lease("L2", stale=True)   # same repo/host, later lease
    before = _lease_row("L2")[1]
    assert ops.renew_lease_for_execution("E1") is False
    assert _lease_row("L2")[1] == before


@pytest.mark.parametrize("state", ["running", "lost", "succeeded", "interrupted"])
def test_u44_stale_protected_lease_stays_authoritative_everywhere(db, monkeypatch, state):
    _lease(host="desktop-in7o23d", stale=True)
    _execution("E1", state=state, host="desktop-in7o23d")
    found = ops.active_lease_for_repo("odysseus", "desktop-in7o23d")
    assert found["heartbeat_stale"] is True and found["protected_by_execution_id"] == "E1"
    with pytest.raises(ops.ParkConflict):
        ops.park_repo("odysseus", "hz2-workstation", "/w/y")
    entries = _conflict_filter(monkeypatch)
    assert entries["hz2-workstation"]["eligible"] is False
    assert "parked on 'desktop-in7o23d'" in entries["hz2-workstation"]["reason"]


def test_u44_control_stale_unprotected_lease_is_reclaimable(db, monkeypatch):
    _lease(host="desktop-in7o23d", stale=True)
    assert ops.active_lease_for_repo("odysseus", "desktop-in7o23d") is None
    assert _conflict_filter(monkeypatch)["hz2-workstation"]["eligible"] is True
    result = ops.park_repo("odysseus", "hz2-workstation", "/w/y")
    assert result["reclaimed_stale_lease"]["lease_id"] == "L1"
    assert _lease_row("L1")[0] == "released"


def test_preparing_reservation_is_never_reclaimable_by_age(db, monkeypatch):
    _lease("P1", host="desktop-in7o23d", status="preparing", stale=True)
    with get_db_session() as s:
        authority = ops.lease_authority_state(s, s.query(ParkLease).one())
    assert authority["reclaimable"] is False and authority["authoritative"] is False
    assert authority["prepare_probe_due"] is True
    with pytest.raises(ops.ParkConflict):
        ops.park_repo("odysseus", "hz2-workstation", "/w/y")
    assert _conflict_filter(monkeypatch)["hz2-workstation"]["eligible"] is False
    assert ops.active_lease_for_repo("odysseus", "desktop-in7o23d") is None


def _conflict_filter(monkeypatch):
    """Run eligible_hosts' lease-conflict filter with every other gate
    satisfied, so only the S6.4 rule decides."""
    hosts = [{"id": "hz2-workstation", "role": "lab", "identity_verified": True,
              "worker": {"enabled": True, "transport": "local", "qualified_executors": ["local"]}}]
    monkeypatch.setattr(estate_router, "_load_yaml", lambda name: {"hosts": hosts} if name == "estate" else {})
    monkeypatch.setattr(estate_router, "host_reachable", lambda host, live: (True, "this host"))
    import src.estate_worker_client as client
    monkeypatch.setattr(client, "worker_health", lambda host_id, **kw: {"ok": True})
    monkeypatch.setattr(client, "worker_repo_probe", lambda host_id, repo, **kw: {"resolved": True})
    return {entry["host_id"]: entry for entry in estate_router.eligible_hosts(repo_id="odysseus")}


def test_u29c_stale_reclaim_serializes_against_admission_style_writer(db):
    """U29(c): a park_repo stale reclaim cannot commit while another
    serialized transaction holding the same database lock is open; once
    that transaction has committed an unresolved row, the reclaim
    re-reads it and is refused."""
    _lease(stale=True)
    inside, proceed = threading.Event(), threading.Event()
    outcome = {}

    def _admission():
        with cdb.lease_serialized_transaction(lease_id="L1") as s:
            inside.set()
            proceed.wait(5)
            s.add(EstateExecution(
                id="E-admitted", objective="o", executor="codex-write", provider="codex",
                host_id="hz2-workstation", repo_id="odysseus", lease_id="L1", lifecycle_state="accepted",
                worker_handle_json='{"dispatch_state": "pending_start"}',
            ))

    def _reclaim():
        try:
            outcome["park"] = ops.park_repo("odysseus", "desktop-in7o23d", "/w/y")
        except ops.ParkConflict as exc:
            outcome["conflict"] = str(exc)

    admission = threading.Thread(target=_admission)
    admission.start()
    assert inside.wait(5)
    reclaim = threading.Thread(target=_reclaim)
    reclaim.start()
    reclaim.join(0.5)
    assert reclaim.is_alive(), "reclaim must block on the write lock, not proceed"
    proceed.set()
    admission.join(5)
    reclaim.join(15)
    assert "conflict" in outcome and "E-admitted" in outcome["conflict"]
    assert _lease_row("L1")[0] == "active"


def test_u45_staleness_is_referenced_only_by_authority_and_display():
    allowed = {
        "core/database.py",           # definition
        "src/park_lease_ops.py",      # lease_authority_state only
        "scripts/agent",              # status display projection
        "scripts/cold_reboot_verify.py",  # read-only reboot report
    }
    offenders = []
    for path in list(REPO_ROOT.glob("src/**/*.py")) + list(REPO_ROOT.glob("routes/**/*.py")) \
            + list(REPO_ROOT.glob("core/**/*.py")) + [REPO_ROOT / "scripts" / "agent"] \
            + list(REPO_ROOT.glob("scripts/*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "park_lease_is_stale" in text and rel not in allowed:
            offenders.append(rel)
    assert offenders == []
    ops_source = (REPO_ROOT / "src" / "park_lease_ops.py").read_text()
    calls = [m.start() for m in re.finditer(r"park_lease_is_stale\(", ops_source)]
    authority = ops_source.index("def lease_authority_state")
    end = ops_source.index("\ndef ", authority + 1)
    assert calls and all(authority < c < end for c in calls)

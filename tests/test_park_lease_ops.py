"""Tests for src/park_lease_ops.py — the shared ParkLease mutation authority
now used by both scripts/agent's `park`/`heartbeat`/`release` CLI
subcommands and routes/estate_routing_routes.py's HTTP surface (Workstream
B next_action: "a park/release/heartbeat HTTP surface so the client can
cover those scripts/agent subcommands too" — this factoring is what let the
HTTP surface exist without duplicating lease semantics).

tests/test_agent_cli_parking_lease.py already covers the CLI-level
stale-reclaim/conflict/heartbeat/release lifecycle end-to-end through
scripts/agent; this file tests the extracted ops functions directly.
"""
from datetime import timedelta

import pytest

from core.database import ParkLease, get_db_session, PARK_LEASE_STALE_SECONDS, utcnow_naive
from src.park_lease_ops import NoActiveLease, ParkConflict, heartbeat_repo, park_repo, release_repo


@pytest.fixture(autouse=True)
def _clean_leases():
    with get_db_session() as db:
        db.query(ParkLease).filter(ParkLease.repo_id.in_(["ops-repo", "ops-conflict-repo"])).delete(synchronize_session=False)
    yield
    with get_db_session() as db:
        db.query(ParkLease).filter(ParkLease.repo_id.in_(["ops-repo", "ops-conflict-repo"])).delete(synchronize_session=False)


def test_park_repo_creates_active_lease():
    result = park_repo("ops-repo", "test-lab", "/tmp/ops-repo", branch="main", session_id="s1")
    assert result["repo_id"] == "ops-repo"
    assert result["host_id"] == "test-lab"
    assert result["reclaimed_stale_lease"] is None

    with get_db_session() as db:
        row = db.query(ParkLease).filter(ParkLease.repo_id == "ops-repo", ParkLease.status == "active").first()
        assert row is not None
        assert row.branch == "main"


def test_park_repo_conflicts_on_live_active_lease():
    park_repo("ops-repo", "test-lab", "/tmp/ops-repo")
    with pytest.raises(ParkConflict):
        park_repo("ops-repo", "other-host", "/tmp/ops-repo-2")


def test_park_repo_reclaims_stale_lease():
    stale_heartbeat = utcnow_naive() - timedelta(seconds=PARK_LEASE_STALE_SECONDS + 60)
    with get_db_session() as db:
        db.add(ParkLease(
            id="stale-lease-1", repo_id="ops-repo", host_id="crashed-host",
            worktree_path="/tmp/x", status="active", heartbeat_at=stale_heartbeat,
        ))

    result = park_repo("ops-repo", "test-lab", "/tmp/ops-repo")
    assert result["reclaimed_stale_lease"]["lease_id"] == "stale-lease-1"

    with get_db_session() as db:
        old = db.query(ParkLease).filter(ParkLease.id == "stale-lease-1").first()
        assert old.status == "released"


def test_heartbeat_repo_renews_and_scopes_by_host():
    park_repo("ops-repo", "test-lab", "/tmp/ops-repo")
    result = heartbeat_repo("ops-repo", host_id="test-lab")
    assert result["repo_id"] == "ops-repo"
    assert result["heartbeat_at"]


def test_heartbeat_repo_raises_when_no_active_lease():
    with pytest.raises(NoActiveLease):
        heartbeat_repo("ops-repo")


def test_heartbeat_repo_scoped_to_wrong_host_raises():
    park_repo("ops-repo", "test-lab", "/tmp/ops-repo")
    with pytest.raises(NoActiveLease):
        heartbeat_repo("ops-repo", host_id="some-other-host")


def test_release_repo_releases_active_lease():
    park_repo("ops-repo", "test-lab", "/tmp/ops-repo")
    result = release_repo("ops-repo", host_id="test-lab")
    assert result["repo_id"] == "ops-repo"

    with get_db_session() as db:
        row = db.query(ParkLease).filter(ParkLease.repo_id == "ops-repo").first()
        assert row.status == "released"
        assert row.released_at is not None


def test_release_repo_raises_when_no_active_lease():
    with pytest.raises(NoActiveLease):
        release_repo("ops-repo")

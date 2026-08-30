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
from src.park_lease_ops import (
    NoActiveLease,
    ParkConflict,
    RepoNotClean,
    RepoNotResolvable,
    active_lease_for_repo,
    active_leases_summary,
    git_is_clean,
    heartbeat_repo,
    park_repo,
    park_repo_by_id,
    release_repo,
)


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


def test_active_leases_summary_lists_and_flags_stale():
    park_repo("ops-repo", "test-lab", "/tmp/ops-repo")
    stale_heartbeat = utcnow_naive() - timedelta(seconds=PARK_LEASE_STALE_SECONDS + 60)
    with get_db_session() as db:
        db.add(ParkLease(
            id="stale-lease-2", repo_id="ops-conflict-repo", host_id="crashed-host",
            worktree_path="/tmp/x", status="active", heartbeat_at=stale_heartbeat,
        ))

    summary = {row["repo_id"]: row for row in active_leases_summary()}
    assert summary["ops-repo"]["stale"] is False
    assert summary["ops-conflict-repo"]["stale"] is True


def test_active_leases_summary_degrades_to_empty_on_db_error(monkeypatch):
    import core.database as database

    def boom():
        raise RuntimeError("db unavailable")
    monkeypatch.setattr(database, "get_db_session", boom)

    assert active_leases_summary() == []


def test_active_lease_for_repo_returns_only_live_lease_held_by_requested_host():
    park_repo("ops-repo", "test-lab", "/tmp/ops-repo")

    lease = active_lease_for_repo("ops-repo", "test-lab")

    assert lease["host_id"] == "test-lab"
    assert lease["worktree_path"] == "/tmp/ops-repo"
    assert lease["allowed_write_scope"] == "repo"
    assert active_lease_for_repo("ops-repo", "other-host") is None


def test_active_lease_for_repo_rejects_stale_lease():
    stale_heartbeat = utcnow_naive() - timedelta(seconds=PARK_LEASE_STALE_SECONDS + 60)
    with get_db_session() as db:
        db.add(ParkLease(
            id="stale-write-lease", repo_id="ops-repo", host_id="test-lab",
            worktree_path="/tmp/ops-repo", status="active", heartbeat_at=stale_heartbeat,
        ))

    assert active_lease_for_repo("ops-repo", "test-lab") is None


class TestGitIsClean:
    def test_clean_worktree_reports_clean(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        (tmp_path / "f.txt").write_text("x")
        subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "init"], check=True)

        clean, reason = git_is_clean(str(tmp_path))
        assert clean is True

    def test_dirty_worktree_reports_dirty(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        (tmp_path / "f.txt").write_text("uncommitted")

        clean, reason = git_is_clean(str(tmp_path))
        assert clean is False

    def test_non_git_directory_fails_closed(self, tmp_path):
        clean, reason = git_is_clean(str(tmp_path))
        assert clean is False


class TestParkRepoById:
    """docs/aoteru-final-convergence-activation.agent-task.md item D:
    the safe remote-callable entrypoint — repo_id in, no path ever
    supplied by the caller."""

    def _clean_git_repo(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        (tmp_path / "f.txt").write_text("x")
        subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "init"], check=True)
        return tmp_path

    def test_unresolvable_repo_id_fails_closed(self, monkeypatch):
        import src.estate_router as estate_router
        monkeypatch.setattr(estate_router, "resolve_repo_path", lambda repo_id: None)

        with pytest.raises(RepoNotResolvable):
            park_repo_by_id("unknown-repo", "test-lab")

    def test_dirty_worktree_fails_closed_without_acquiring_lease(self, monkeypatch, tmp_path):
        import subprocess
        import src.estate_router as estate_router
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        (tmp_path / "dirty.txt").write_text("uncommitted")
        monkeypatch.setattr(estate_router, "resolve_repo_path", lambda repo_id: str(tmp_path))

        with pytest.raises(RepoNotClean):
            park_repo_by_id("ops-repo", "test-lab")

        with get_db_session() as db:
            assert db.query(ParkLease).filter(ParkLease.repo_id == "ops-repo", ParkLease.status == "active").first() is None

    def test_clean_resolved_repo_acquires_a_real_lease(self, monkeypatch, tmp_path):
        import src.estate_router as estate_router
        clean_repo = self._clean_git_repo(tmp_path)
        monkeypatch.setattr(estate_router, "resolve_repo_path", lambda repo_id: str(clean_repo))

        result = park_repo_by_id("ops-repo", "test-lab", branch="main")
        assert result["repo_id"] == "ops-repo"
        assert result["worktree_path"] == str(clean_repo)
        assert result["branch"] == "main"

        with get_db_session() as db:
            row = db.query(ParkLease).filter(ParkLease.repo_id == "ops-repo", ParkLease.status == "active").first()
            assert row is not None
            assert row.worktree_path == str(clean_repo)

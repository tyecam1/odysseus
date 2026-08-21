"""Tests for scripts/agent's parking lease heartbeat/staleness handling.

Finding: "the DB uniqueness constraint is good, but heartbeat renewal/
stale lease handling ... are incomplete." Covers:
- `agent heartbeat` actually renews `heartbeat_at` on the caller's lease;
- a stale active lease (holder crashed, heartbeat never renewed) is
  auto-reclaimed by `cmd_park` instead of blocking forever;
- a live (non-stale) active lease still fails closed, unchanged;
- `src.estate_router.eligible_hosts()` stops treating a stale conflicting
  lease on another host as a hard block.
"""
import argparse
import importlib.machinery
import importlib.util
import sys
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "agent"


def load_module():
    loader = importlib.machinery.SourceFileLoader("agent_cli_park", str(SCRIPT_PATH))
    spec = importlib.util.spec_from_loader("agent_cli_park", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _clean_park_leases():
    """The test DB engine is process-wide (shared across tests in this
    file), so a lease left `active` by one test would collide with the
    next test's insert via the same partial-unique-index this feature
    relies on — clean slate per test, not a production concern."""
    from core.database import get_db_session, ParkLease
    with get_db_session() as db:
        db.query(ParkLease).filter(ParkLease.repo_id.in_(["test-repo", "conflict-repo", "never-parked"])).delete(synchronize_session=False)
    yield
    with get_db_session() as db:
        db.query(ParkLease).filter(ParkLease.repo_id.in_(["test-repo", "conflict-repo", "never-parked"])).delete(synchronize_session=False)


@pytest.fixture
def agent_cli(monkeypatch):
    module = load_module()
    # Stub out the parts of cmd_park/cmd_heartbeat that resolve real
    # host/repo/git state — these tests are only about the lease lifecycle.
    monkeypatch.setattr(module, "_load_host_local", lambda: {})
    monkeypatch.setattr(module, "_load_yaml", lambda name: {"hosts": [{"id": "test-lab", "hostname": "THIS-HOST", "role": "lab"}]})
    monkeypatch.setattr(module, "_resolve_repos", lambda host_local: [{"id": "test-repo", "exists": True, "path": "/tmp/test-repo"}])
    monkeypatch.setattr(module, "_repo_by_id", lambda repos, repo_id: repos[0] if repo_id == "test-repo" else None)
    monkeypatch.setattr(module, "_resolve_current_host", lambda estate, hostname: estate["hosts"][0])
    monkeypatch.setattr(module.socket, "gethostname", lambda: "THIS-HOST")
    monkeypatch.setattr(module, "_git_is_clean", lambda path: (True, "clean"))
    return module


def _args(**kw):
    ns = argparse.Namespace(repo_id="test-repo", host=None, branch=None, session=None, pretty=False)
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def test_heartbeat_renews_active_lease(agent_cli, capsys):
    from core.database import get_db_session, ParkLease, utcnow_naive

    lease_id = str(uuid.uuid4())
    old_heartbeat = utcnow_naive() - timedelta(minutes=10)
    with get_db_session() as db:
        db.add(ParkLease(
            id=lease_id, repo_id="test-repo", host_id="test-lab",
            worktree_path="/tmp/test-repo", status="active", heartbeat_at=old_heartbeat,
        ))

    agent_cli.cmd_heartbeat(_args())
    out = capsys.readouterr().out
    assert '"ok": true' in out.lower()

    with get_db_session() as db:
        row = db.query(ParkLease).filter(ParkLease.id == lease_id).first()
        assert row.heartbeat_at > old_heartbeat


def test_heartbeat_fails_when_no_active_lease(agent_cli):
    with pytest.raises(SystemExit):
        agent_cli.cmd_heartbeat(_args(repo_id="never-parked"))


def test_park_reclaims_stale_lease_instead_of_blocking(agent_cli, capsys):
    from core.database import get_db_session, ParkLease, park_lease_is_stale, PARK_LEASE_STALE_SECONDS, utcnow_naive

    old_lease_id = str(uuid.uuid4())
    stale_heartbeat = utcnow_naive() - timedelta(seconds=PARK_LEASE_STALE_SECONDS + 60)
    with get_db_session() as db:
        db.add(ParkLease(
            id=old_lease_id, repo_id="test-repo", host_id="test-lab",
            worktree_path="/tmp/test-repo", status="active", heartbeat_at=stale_heartbeat,
        ))

    agent_cli.cmd_park(_args())
    out = capsys.readouterr().out
    assert '"ok": true' in out.lower()
    assert "reclaimed_stale_lease" in out

    with get_db_session() as db:
        old = db.query(ParkLease).filter(ParkLease.id == old_lease_id).first()
        assert old.status == "released"
        active = db.query(ParkLease).filter(
            ParkLease.repo_id == "test-repo", ParkLease.status == "active",
        ).first()
        assert active is not None
        assert active.id != old_lease_id
        assert park_lease_is_stale(active) is False


def test_park_still_fails_closed_on_live_lease(agent_cli):
    from core.database import get_db_session, ParkLease, utcnow_naive

    with get_db_session() as db:
        db.add(ParkLease(
            id=str(uuid.uuid4()), repo_id="test-repo", host_id="test-lab",
            worktree_path="/tmp/test-repo", status="active", heartbeat_at=utcnow_naive(),
        ))

    with pytest.raises(SystemExit):
        agent_cli.cmd_park(_args())


def test_eligible_hosts_ignores_stale_conflicting_lease(monkeypatch, tmp_path):
    import socket
    import yaml
    import src.estate_router as estate_router
    from core.database import get_db_session, ParkLease, PARK_LEASE_STALE_SECONDS, utcnow_naive
    from datetime import timedelta

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "estate.yaml").write_text(yaml.safe_dump({
        "hosts": [
            {"id": "test-lab", "hostname": "THIS-HOST", "role": "lab", "tailscale": True},
        ],
    }))
    (config_dir / "models.yaml").write_text(yaml.safe_dump({"capabilities": []}))
    monkeypatch.setattr(estate_router, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(socket, "gethostname", lambda: "THIS-HOST")

    stale_heartbeat = utcnow_naive() - timedelta(seconds=PARK_LEASE_STALE_SECONDS + 60)
    with get_db_session() as db:
        db.add(ParkLease(
            id=str(uuid.uuid4()), repo_id="conflict-repo", host_id="some-other-host",
            worktree_path="/tmp/x", status="active", heartbeat_at=stale_heartbeat,
        ))

    hosts = {h["host_id"]: h for h in estate_router.eligible_hosts(repo_id="conflict-repo")}
    assert hosts["test-lab"]["eligible"] is True

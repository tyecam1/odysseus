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
import json
import subprocess
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
    import src.estate_router as estate_router
    monkeypatch.setattr(
        estate_router, "resolve_repo_path",
        lambda repo_id: "/tmp/test-repo" if repo_id == "test-repo" else None,
    )
    import src.park_lease_ops as park_lease_ops
    monkeypatch.setattr(park_lease_ops, "git_is_clean", lambda path: (True, "clean"))
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


def test_status_active_park_leases_summary_lists_and_flags_stale(agent_cli):
    """Workstream K: `agent status` previously had no estate-wide lease
    view at all (only `agent where` showed the current repo's own lease).
    Covers both a live lease (not stale) and a crashed-holder lease
    (stale) in the same summary."""
    from core.database import get_db_session, ParkLease, PARK_LEASE_STALE_SECONDS, utcnow_naive

    live_heartbeat = utcnow_naive()
    stale_heartbeat = utcnow_naive() - timedelta(seconds=PARK_LEASE_STALE_SECONDS + 60)
    with get_db_session() as db:
        db.add(ParkLease(
            id=str(uuid.uuid4()), repo_id="test-repo", host_id="test-lab",
            worktree_path="/tmp/test-repo", status="active", heartbeat_at=live_heartbeat,
        ))
        db.add(ParkLease(
            id=str(uuid.uuid4()), repo_id="conflict-repo", host_id="some-other-host",
            worktree_path="/tmp/x", status="active", heartbeat_at=stale_heartbeat,
        ))

    summary = agent_cli._active_park_leases_summary()
    by_repo = {row["repo_id"]: row for row in summary}
    assert by_repo["test-repo"]["stale"] is False
    assert by_repo["conflict-repo"]["stale"] is True


def test_status_active_park_leases_summary_degrades_to_empty_on_db_error(agent_cli, monkeypatch):
    """A missing/unreachable DB must not crash `agent status` — lease
    visibility is one field among many, not the command's reason to
    exist."""
    import core.database as database

    def boom():
        raise RuntimeError("db unavailable")
    monkeypatch.setattr(database, "get_db_session", boom)

    assert agent_cli._active_park_leases_summary() == []


def test_cmd_park_branch_uses_isolated_worktree_not_live_checkout(monkeypatch, capsys, tmp_path):
    import src.estate_router as estate_router
    from core.database import ParkLease, get_db_session

    module = load_module()
    live_repo = tmp_path / "projects" / "odysseus-aoteru"
    live_repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(live_repo)], check=True)
    subprocess.run(["git", "-C", str(live_repo), "checkout", "-q", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(live_repo), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(live_repo), "config", "user.email", "test@example.com"], check=True)
    (live_repo / "f.txt").write_text("x")
    subprocess.run(["git", "-C", str(live_repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(live_repo), "commit", "-q", "-m", "init"], check=True)

    monkeypatch.setattr(module, "_load_host_local", lambda: {})
    monkeypatch.setattr(module, "_load_yaml", lambda name: {"hosts": [{"id": "test-lab", "hostname": "THIS-HOST", "role": "lab"}]})
    monkeypatch.setattr(module, "_resolve_repos", lambda host_local: [{"id": "test-repo", "exists": True, "path": str(live_repo)}])
    monkeypatch.setattr(module, "_repo_by_id", lambda repos, repo_id: repos[0] if repo_id == "test-repo" else None)
    monkeypatch.setattr(module, "_resolve_current_host", lambda estate, hostname: estate["hosts"][0])
    monkeypatch.setattr(module.socket, "gethostname", lambda: "THIS-HOST")
    monkeypatch.setattr(module, "_git_is_clean", lambda path: (_ for _ in ()).throw(AssertionError("cmd_park should not call _git_is_clean directly")))
    monkeypatch.setattr(estate_router, "resolve_repo_path", lambda repo_id: str(live_repo))

    with get_db_session() as db:
        db.query(ParkLease).filter(ParkLease.repo_id == "test-repo").delete(synchronize_session=False)

    module.cmd_park(_args(branch="feature/lease"))
    body = json.loads(capsys.readouterr().out)

    assert body["ok"] is True
    assert body["repo_id"] == "test-repo"
    assert body["branch"] == "feature/lease"
    assert body["worktree_path"] != str(live_repo)

    branch = subprocess.run(
        ["git", "-C", body["worktree_path"], "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert branch == "feature/lease"

    with get_db_session() as db:
        row = db.query(ParkLease).filter(
            ParkLease.repo_id == "test-repo",
            ParkLease.status == "active",
        ).first()
        assert row is not None
        assert row.worktree_path == body["worktree_path"]
        assert row.worktree_path != str(live_repo)
        assert row.branch == "feature/lease"
        assert db.query(ParkLease).filter(
            ParkLease.repo_id == "test-repo",
            ParkLease.worktree_path == str(live_repo),
        ).count() == 0

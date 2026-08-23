"""Tests for scripts/cold_reboot_verify.py's decision logic (Workstream J).

Exercises the pure PASS/FAIL/SKIP classification against mocked
subprocess/HTTP calls — this script must never touch the network/host
state in a test run, and must never reboot anything (it doesn't have that
capability at all, by design).
"""
import importlib.util
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location(
    "cold_reboot_verify", PROJECT_ROOT / "scripts" / "cold_reboot_verify.py"
)
crv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crv)


def _fake_proc(stdout="", returncode=0):
    return types.SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


def test_tailscale_all_routes_private_passes(monkeypatch):
    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["tailscale", "status"]:
            return _fake_proc(returncode=0)
        if cmd[:2] == ["tailscale", "serve"]:
            return _fake_proc(stdout="http://host:8080 (tailnet only)\n|-- / proxy http://127.0.0.1:7001\n")
        raise AssertionError(cmd)
    monkeypatch.setattr(crv.subprocess, "run", fake_run)

    result = crv.check_tailscale_private_only()
    assert result.status == "PASS"


def test_tailscale_public_route_fails(monkeypatch):
    """A Funnel-exposed (public) route on what should be a private-only
    surface must hard-fail, not warn — this is the exact regression this
    check exists to catch."""
    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["tailscale", "status"]:
            return _fake_proc(returncode=0)
        if cmd[:2] == ["tailscale", "serve"]:
            return _fake_proc(stdout="http://host:8080 (Funnel on)\n|-- / proxy http://127.0.0.1:7001\n")
        raise AssertionError(cmd)
    monkeypatch.setattr(crv.subprocess, "run", fake_run)

    result = crv.check_tailscale_private_only()
    assert result.status == "FAIL"
    assert "non-tailnet-only" in result.detail


def test_tailscale_down_fails(monkeypatch):
    def fake_run(cmd, **kwargs):
        return _fake_proc(returncode=1)
    monkeypatch.setattr(crv.subprocess, "run", fake_run)

    result = crv.check_tailscale_private_only()
    assert result.status == "FAIL"


def test_app_ready_falls_back_to_liveness_without_token(monkeypatch):
    monkeypatch.delenv("COLD_REBOOT_AUTH_TOKEN", raising=False)

    def fake_get(url, timeout=4.0, token=None):
        assert url.endswith("/api/health")
        assert token is None
        return 200, "{}"
    monkeypatch.setattr(crv, "_get", fake_get)

    result = crv.check_app_ready()
    assert result.status == "PASS"
    assert "liveness only" in result.detail


def test_app_ready_uses_token_and_reports_readiness(monkeypatch):
    monkeypatch.setenv("COLD_REBOOT_AUTH_TOKEN", "test-token-not-real")

    def fake_get(url, timeout=4.0, token=None):
        assert url.endswith("/api/ready")
        assert token == "test-token-not-real"
        return 200, '{"ready": true, "checks": {}}'
    monkeypatch.setattr(crv, "_get", fake_get)

    result = crv.check_app_ready()
    assert result.status == "PASS"
    monkeypatch.delenv("COLD_REBOOT_AUTH_TOKEN", raising=False)


def test_app_ready_reports_failing_critical_checks(monkeypatch):
    monkeypatch.setenv("COLD_REBOOT_AUTH_TOKEN", "test-token-not-real")

    def fake_get(url, timeout=4.0, token=None):
        return 503, '{"ready": false, "checks": {"database": {"critical": true, "ok": false}}}'
    monkeypatch.setattr(crv, "_get", fake_get)

    result = crv.check_app_ready()
    assert result.status == "FAIL"
    assert "database" in result.detail
    monkeypatch.delenv("COLD_REBOOT_AUTH_TOKEN", raising=False)


def test_park_leases_reports_stale_as_failure(monkeypatch):
    class FakeLease:
        def __init__(self, repo_id, host_id):
            self.repo_id = repo_id
            self.host_id = host_id

    stale_lease = FakeLease("obsidian-PhD", "hz2-workstation")

    class FakeQuery:
        def filter(self, *a, **k):
            return self

        def all(self):
            return [stale_lease]

    class FakeSession:
        def query(self, model):
            return FakeQuery()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import core.database as database
    monkeypatch.setattr(database, "get_db_session", lambda: FakeSession())
    monkeypatch.setattr(database, "park_lease_is_stale", lambda row: True)

    result = crv.check_park_leases()
    assert result.status == "FAIL"
    assert "obsidian-PhD" in result.detail


def test_park_leases_reports_no_active_as_pass(monkeypatch):
    class FakeQuery:
        def filter(self, *a, **k):
            return self

        def all(self):
            return []

    class FakeSession:
        def query(self, model):
            return FakeQuery()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import core.database as database
    monkeypatch.setattr(database, "get_db_session", lambda: FakeSession())

    result = crv.check_park_leases()
    assert result.status == "PASS"

"""Tests for scripts/interface_frontdoor_acceptance.py (Workstream H) —
the rerunnable acceptance suite for whatever the mobile/interface
front-door is pointed at. Mocked HTTP so these don't depend on a live
server; live-proven separately against the real dev instance (see
docs/aoteru-autonomous-programme-state.md workstream H)."""
import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location(
    "interface_frontdoor_acceptance", SCRIPTS_DIR / "interface_frontdoor_acceptance.py"
)
ifa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ifa)


def _mock_statuses(monkeypatch, statuses: dict):
    def fake_get(base_url, path, timeout=4.0):
        return statuses[path]
    monkeypatch.setattr(ifa, "_get", fake_get)


def test_all_checks_pass_for_a_correctly_configured_instance(monkeypatch):
    _mock_statuses(monkeypatch, {
        "/api/health": 200,
        "/static/manifest.json": 200,
        "/api/estate/route/hosts": 401,
        "/api/companion/ping": 401,
        "/login": 200,
    })
    results = ifa.build_report("http://test")
    assert all(r.status == "PASS" for r in results)


def test_unauthenticated_route_exposure_fails_the_auth_check(monkeypatch):
    """The exact regression this check exists to catch: a protected route
    that starts returning 200 to an unauthenticated caller (e.g. a
    middleware misconfiguration exposing it beyond the tailnet) must fail
    loudly, not pass silently."""
    _mock_statuses(monkeypatch, {
        "/api/health": 200,
        "/static/manifest.json": 200,
        "/api/estate/route/hosts": 200,  # should be 401/403 — this is the bug
        "/api/companion/ping": 401,
        "/login": 200,
    })
    result = ifa.check_protected_routes_reject_unauthenticated("http://test")
    assert result.status == "FAIL"


def test_missing_pwa_manifest_fails(monkeypatch):
    _mock_statuses(monkeypatch, {"/static/manifest.json": 404})
    result = ifa.check_pwa_manifest("http://test")
    assert result.status == "FAIL"


def test_liveness_failure_reported(monkeypatch):
    _mock_statuses(monkeypatch, {"/api/health": 503})
    result = ifa.check_health("http://test")
    assert result.status == "FAIL"


def test_main_exits_nonzero_on_any_failure(monkeypatch, capsys):
    _mock_statuses(monkeypatch, {
        "/api/health": 200,
        "/static/manifest.json": 404,
        "/api/estate/route/hosts": 401,
        "/api/companion/ping": 401,
        "/login": 200,
    })
    monkeypatch.setattr(sys, "argv", ["interface_frontdoor_acceptance.py", "--url", "http://test"])
    rc = ifa.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL" in out

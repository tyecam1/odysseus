"""Tests for companion/laptop_client/aoteru.py — the standalone, stdlib-only
laptop thin client (Workstream B).

Imports the script by file path (not as a package) since it is deliberately
NOT part of the odysseus-aoteru Python package — a laptop with no checkout
only ever has this one file. Verifies: it stays stdlib-only (no accidental
dependency on this repo or third-party packages sneaking in), config
read/write round-trips without ever writing the token in plaintext logs,
and request-building/response-handling logic for each subcommand.
"""
import ast
import importlib.util
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLIENT_PATH = PROJECT_ROOT / "companion" / "laptop_client" / "aoteru.py"
PYPROJECT_PATH = PROJECT_ROOT / "companion" / "laptop_client" / "pyproject.toml"


def test_pyproject_declares_stdlib_only_console_script():
    """Workstream B next_action: pipx packaging. pyproject.toml must add
    an installable `aoteru` console-script entry point without adding any
    third-party dependency — the whole point of the stdlib-only client is
    that it stays that way even when pipx-installed, not just when run as
    a bare copied file."""
    import tomllib
    data = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    assert data["project"]["scripts"]["aoteru"] == "aoteru:main"
    assert data["project"].get("dependencies") == []
    assert data["tool"]["setuptools"]["py-modules"] == ["aoteru"]


def test_client_is_stdlib_only():
    """The whole point of Workstream B: this file must run on a bare laptop
    Python with no pip install and no Odysseus checkout on sys.path."""
    STDLIB = {"__future__", "argparse", "json", "os", "pathlib", "stat", "sys", "urllib"}
    tree = ast.parse(CLIENT_PATH.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(n.name.split(".")[0] for n in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    assert found <= STDLIB, f"non-stdlib import(s) found: {found - STDLIB}"


@pytest.mark.parametrize("argv", [
    ["ask", "an objective"],
    ["auto", "a task"],
    ["lab", "a task"],
    ["home", "a task"],
])
def test_execution_commands_default_timeout_exceeds_server_watchdog(argv):
    """A normal ask/auto/lab/home invocation with no --timeout must not
    silently abandon a request the server is still legitimately working
    on: the client default must stay above the server's own execution
    route watchdog (210s) so the client is always the last one to give up,
    per worker-owned bound < route watchdog < client timeout. Parses a
    real argv with no --timeout flag at all - proves the default path
    itself, not just that a constant happens to hold the right value."""
    spec = importlib.util.spec_from_file_location("aoteru_client_parser_check", CLIENT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    parser = mod.build_parser()
    args = parser.parse_args(argv)

    assert args.timeout == mod._DEFAULT_EXECUTION_TIMEOUT
    assert args.timeout > 210.0, (
        f"default --timeout ({args.timeout}s) must exceed the server's execution "
        "route watchdog (210s) or a normal command can time out client-side while "
        "the server is still legitimately executing it"
    )


def test_execution_commands_timeout_still_overridable(client):
    parser = client.build_parser()
    args = parser.parse_args(["ask", "an objective", "--timeout", "5"])
    assert args.timeout == 5.0


@pytest.fixture
def client(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("aoteru_client", CLIENT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "CONFIG_DIR", tmp_path / ".aoteru")
    monkeypatch.setattr(mod, "CONFIG_PATH", tmp_path / ".aoteru" / "client.json")
    return mod


def test_config_set_and_show_round_trips(client, capsys):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_secret_value"])
    capsys.readouterr()

    saved = json.loads(client.CONFIG_PATH.read_text())
    assert saved == {"url": "http://lab:7001", "token": "ody_secret_value"}

    client.main(["config", "show"])
    out = capsys.readouterr().out
    assert "ody_secret_value" not in out, "the raw token must never be printed"
    assert "set (hidden)" in out
    assert "http://lab:7001" in out


def test_config_partial_update_preserves_existing_field(client):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_a"])
    client.main(["config", "set", "--token", "ody_b"])
    saved = json.loads(client.CONFIG_PATH.read_text())
    assert saved == {"url": "http://lab:7001", "token": "ody_b"}


def test_status_reports_clear_error_when_no_backend_configured(client):
    with pytest.raises(SystemExit) as exc:
        client.main(["status"])
    assert "no backend configured" in str(exc.value)


def test_status_reports_unreachable_backend_clearly(client, monkeypatch, capsys):
    client.main(["config", "set", "--url", "http://127.0.0.1:1", "--token", "ody_x"])

    import urllib.error

    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(SystemExit) as exc:
        client.main(["status"])
    assert "cannot reach" in str(exc.value)


def test_controller_reconnects_cleanly_after_a_disconnect(client, monkeypatch, capsys):
    """Workstream J: 'controller disconnect/reconnect'. The client keeps
    no persistent connection or in-process session state across
    subcommands — each invocation is one fresh HTTP request against the
    on-disk config — so a backend that comes back after being briefly
    unreachable must work on the very next call with no special recovery
    step, reset, or stale config left over from the failed attempt."""
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])
    import urllib.error

    call_count = {"n": 0}

    def flaky_then_healthy(req, timeout=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise urllib.error.URLError("connection refused")

        class FakeResponse:
            status = 200
            def read(self):
                return json.dumps({"active_park_leases": []}).encode()
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
        return FakeResponse()
    monkeypatch.setattr(client.urllib.request, "urlopen", flaky_then_healthy)

    with pytest.raises(SystemExit):
        client.main(["park-status"])

    # Second attempt against the same, untouched config must succeed —
    # no reconnect/reset command needed, and config wasn't mutated by
    # the failed first attempt. park-status is a single request, so the
    # call count directly proves no retry-loop/leftover state either.
    rc = client.main(["park-status"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "active_park_leases" in out
    assert call_count["n"] == 2


def test_ask_sends_allow_paid_escalation_flag(client, monkeypatch):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])

    captured = {}

    class FakeResponse:
        status = 200
        def read(self):
            return json.dumps({"ok": True, "executed": True}).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        captured["headers"] = dict(req.header_items())
        return FakeResponse()
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main([
        "ask", "do the thing", "--repo", "odysseus", "--capability", "code-strong",
        "--allow-paid", "--implementation",
    ])
    assert rc == 0
    assert captured["url"].endswith("/api/estate/run")
    assert captured["body"]["allow_paid_escalation"] is True
    assert captured["body"]["mode"] == "implementation"
    assert captured["body"]["requirements"]["capabilities"] == ["code-strong"]
    assert captured["headers"]["Authorization"] == "Bearer ody_x"


def test_preflight_sends_task_unit_to_live_estate_endpoint(client, monkeypatch):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        return FakeResponse({
            "ok": True,
            "snapshot": {"eligible_hosts": [{"host_id": "test-lab", "eligible": True}]},
            "units": [{"classification": "codex_eligible", "recommended_route": "codex-write"}],
        })

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    rc = client.main([
        "preflight", "implement the router", "--task-class", "bounded_code_implementation",
        "--repo", "odysseus", "--capability", "code-strong",
    ])

    assert rc == 0
    assert captured["url"].endswith("/api/estate/preflight")
    unit = captured["body"]["units"][0]
    assert unit["objective"] == "implement the router"
    assert unit["repo"] == "odysseus"
    assert unit["capabilities"] == ["code-strong"]


def test_ask_reports_scope_denial_clearly(client, monkeypatch, capsys):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_readonly"])

    def fake_urlopen(req, timeout=None):
        import urllib.error
        raise urllib.error.HTTPError(
            req.full_url, 403, "Forbidden", {}, __import__("io").BytesIO(
                json.dumps({"detail": "API token missing required scope: estate:execute"}).encode()
            ),
        )
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main(["ask", "do the thing"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "estate:execute" in out


class FakeResponse:
    def __init__(self, payload):
        self.status = 200
        self._payload = payload
    def read(self):
        return json.dumps(self._payload).encode()
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def test_status_reports_host_id_and_separates_eligible_from_considered(client, monkeypatch, capsys):
    """Regression: `/api/estate/route/hosts` returns every considered host
    (role lab/home) tagged `eligible`/`reason`, keyed `host_id` — not a
    pre-filtered list keyed `id`. The client used to read the wrong key
    (printing `None` for every row) and printed ineligible hosts under the
    same "eligible hosts" heading, which would have made an unverified
    home host look promoted to eligible. Preserve registered != reachable
    != verified != eligible in the laptop-facing output itself."""
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])

    def fake_urlopen(req, timeout=None):
        if req.full_url.endswith("/api/health"):
            return FakeResponse({"status": "healthy"})
        assert req.full_url.endswith("/api/estate/route/hosts")
        return FakeResponse({"hosts": [
            {"host_id": "hz2-workstation", "role": "lab", "eligible": True, "reason": "this host"},
            {"host_id": "desktop-in7o23d", "role": "home", "eligible": False,
             "reason": "'desktop-in7o23d' is not verified (config/estate.yaml verified: false) — reachability alone is not sufficient"},
        ]})
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main(["status"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "eligible hosts: 1" in out
    assert "- hz2-workstation (lab)" in out
    assert "None" not in out
    assert "considered but not eligible: 1" in out
    assert "desktop-in7o23d (home): 'desktop-in7o23d' is not verified" in out


def test_park_hits_the_correct_endpoint_with_branch(client, monkeypatch):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        return FakeResponse({"ok": True, "lease_id": "abc", "repo_id": "odysseus", "worktree_path": "/real/path"})
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main(["park", "odysseus", "--branch", "dev"])
    assert rc == 0
    assert captured["url"] == "http://lab:7001/api/estate/park/odysseus?branch=dev"
    assert captured["method"] == "POST"


def test_park_unresolvable_repo_reports_clearly(client, monkeypatch, capsys):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])

    def fake_urlopen(req, timeout=None):
        import io
        import urllib.error
        raise urllib.error.HTTPError(
            req.full_url, 404, "Not Found", {},
            io.BytesIO(json.dumps({"detail": "'unknown-repo' is not registered"}).encode()),
        )
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main(["park", "unknown-repo"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "not registered" in out


def test_park_dirty_worktree_reports_clearly(client, monkeypatch, capsys):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])

    def fake_urlopen(req, timeout=None):
        import io
        import urllib.error
        raise urllib.error.HTTPError(
            req.full_url, 409, "Conflict", {},
            io.BytesIO(json.dumps({"detail": "refusing to park 'odysseus': dirty"}).encode()),
        )
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main(["park", "odysseus"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "cannot park" in out


def test_heartbeat_hits_the_correct_endpoint(client, monkeypatch):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        return FakeResponse({"ok": True, "lease_id": "abc", "repo_id": "odysseus"})
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main(["heartbeat", "odysseus"])
    assert rc == 0
    assert captured["url"].endswith("/api/estate/park/odysseus/heartbeat")
    assert captured["method"] == "POST"


def test_release_hits_the_correct_endpoint(client, monkeypatch):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        return FakeResponse({"ok": True, "lease_id": "abc", "repo_id": "odysseus"})
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main(["release", "odysseus"])
    assert rc == 0
    assert captured["url"].endswith("/api/estate/park/odysseus/release")


def test_heartbeat_reports_no_active_lease_clearly(client, monkeypatch, capsys):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])

    def fake_urlopen(req, timeout=None):
        import io
        import urllib.error
        raise urllib.error.HTTPError(
            req.full_url, 409, "Conflict", {},
            io.BytesIO(json.dumps({"detail": "no active lease for 'odysseus'"}).encode()),
        )
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main(["heartbeat", "odysseus"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "no active lease" in out


def test_lab_mode_sends_requested_host_placement(client, monkeypatch):
    """Regression: `resolve_route` has always read `placement.requested_host`,
    but nothing sent it over HTTP until `lab`/`home`/`auto` existed."""
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        return FakeResponse({"ok": True, "route": {"host": "hz2-workstation"}})
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main(["lab", "do the thing", "--capability", "code-fast"])
    assert rc == 0
    assert captured["url"].endswith("/api/estate/run")
    assert captured["body"]["placement"]["requested_host"] == "lab"
    assert captured["body"]["objective"] == "do the thing"
    assert captured["body"]["requirements"]["capabilities"] == ["code-fast"]


def test_home_mode_reports_host_not_eligible_truthfully(client, monkeypatch, capsys):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])

    def fake_urlopen(req, timeout=None):
        return FakeResponse({"ok": False, "error": "requested host 'home' is not eligible"})
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main(["home", "do the thing"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "not eligible" in out


def test_auto_mode_sends_auto_placement(client, monkeypatch):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode())
        return FakeResponse({"ok": True})
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main(["auto", "do the thing"])
    assert rc == 0
    assert captured["body"]["placement"]["requested_host"] == "auto"


def test_where_lists_active_sessions(client, monkeypatch, capsys):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        return FakeResponse({"active_sessions": [{"id": "abc", "host_id": "hz2-workstation"}]})
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main(["where"])
    out = capsys.readouterr().out
    assert rc == 0
    assert captured["url"].endswith("/api/estate/sessions")
    assert "hz2-workstation" in out


def test_where_reports_scope_denial_clearly(client, monkeypatch, capsys):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_readonly"])

    def fake_urlopen(req, timeout=None):
        import urllib.error
        raise urllib.error.HTTPError(
            req.full_url, 403, "Forbidden", {}, __import__("io").BytesIO(
                json.dumps({"detail": "API token missing required scope: estate:read"}).encode()
            ),
        )
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main(["where"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "estate:read" in out


def test_sync_writes_skill_md(client, monkeypatch, tmp_path):
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    monkeypatch.setattr(client.Path, "home", staticmethod(lambda: fake_home))

    rc = client.main(["sync"])
    assert rc == 0

    skill_path = fake_home / ".claude" / "skills" / "aoteru-estate-routing" / "SKILL.md"
    assert skill_path.exists()
    content = skill_path.read_text()
    assert "aoteru preflight" in content
    assert "aoteru auto" in content
    assert "aoteru lab" in content
    assert "aoteru home" in content
    assert "aoteru where" in content


def test_park_status_lists_active_leases(client, monkeypatch, capsys):
    client.main(["config", "set", "--url", "http://lab:7001", "--token", "ody_x"])
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        return FakeResponse({"active_park_leases": [{"repo_id": "odysseus", "stale": False}]})
    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    rc = client.main(["park-status"])
    out = capsys.readouterr().out
    assert rc == 0
    assert captured["url"].endswith("/api/estate/park/status")
    assert "odysseus" in out

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

    rc = client.main(["ask", "do the thing", "--capability", "code-strong", "--allow-paid"])
    assert rc == 0
    assert captured["url"].endswith("/api/estate/run")
    assert captured["body"]["allow_paid_escalation"] is True
    assert captured["body"]["requirements"]["capabilities"] == ["code-strong"]
    assert captured["headers"]["Authorization"] == "Bearer ody_x"


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

"""Read-only usage collection: rollout parsing, route scope, claude lane flags."""
import json
import os

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()
import core.database as cdb
from src import estate_router, provider_usage
from routes.estate_routing_routes import setup_estate_routing_routes


def _rollout(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for payload in events:
        lines.append(json.dumps({"type": "event", "payload": payload}))
    path.write_text("\n".join(lines) + "\n")


def _token_count(primary=None, secondary=None, plan="plus"):
    return {"type": "token_count", "rate_limits": {"primary": primary, "secondary": secondary},
            "credits": {"has_credits": False, "unlimited": False, "balance": "0"},
            "plan_type": plan}


def test_codex_windows_reads_latest_provider_stated_event(tmp_path):
    newer = tmp_path / "2026" / "11" / "18" / "rollout-b.jsonl"
    older = tmp_path / "2026" / "11" / "16" / "rollout-a.jsonl"
    _rollout(older, [_token_count(primary={"used_percent": 50.0, "window_minutes": 300,
                                           "resets_at": 1794900000})])
    _rollout(newer, [
        _token_count(primary={"used_percent": 90.0, "window_minutes": 300, "resets_at": 1795000000}),
        {"type": "other"},
        _token_count(primary={"used_percent": 5.0, "window_minutes": 300, "resets_at": 1795016288},
                     secondary={"used_percent": 69.0, "window_minutes": 10080,
                                "resets_at": 1795208916}),
    ])
    os.utime(older, (1794800000, 1794800000))
    os.utime(newer, (1795016300, 1795016300))
    result = provider_usage.codex_windows(tmp_path)
    assert result["confidence"] == "provider-stated"
    assert result["plan_type"] == "plus"
    pools = {w["pool"]: w for w in result["windows"]}
    assert pools["primary"]["used_percent"] == 5.0
    assert pools["primary"]["remaining_percent"] == 95.0
    assert pools["secondary"]["used_percent"] == 69.0
    assert pools["primary"]["resets_at"].startswith("2026-")
    # conservative summary: the most-constrained window wins
    assert result["remaining"] == 31.0


def test_codex_windows_unknown_when_no_recent_rollouts(tmp_path):
    result = provider_usage.codex_windows(tmp_path)
    assert result["remaining"] == "unknown" and result["reset"] == "unknown"
    assert result["confidence"] == "none"


def test_codex_windows_skips_events_without_primary(tmp_path):
    rollout = tmp_path / "r.jsonl"
    _rollout(rollout, [_token_count(primary=None), _token_count()])
    result = provider_usage.codex_windows(tmp_path)
    assert result["remaining"] == "unknown"


@pytest.fixture
def api(monkeypatch):
    factory, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", factory)
    app = FastAPI()

    @app.middleware("http")
    async def identity(request: Request, call_next):
        request.state.api_token = True
        request.state.api_token_owner = "operator"
        request.state.api_token_scopes = ["estate:read"]
        return await call_next(request)

    app.include_router(setup_estate_routing_routes())
    with TestClient(app) as client:
        yield client
    engine.dispose()
    os.unlink(tmpfile.name)


def test_usage_route_returns_provider_snapshot(api, monkeypatch):
    monkeypatch.setattr(provider_usage, "codex_windows",
                        lambda: {"remaining": 31.0, "reset": "unknown", "windows": [],
                                 "confidence": "provider-stated"})
    monkeypatch.setattr(provider_usage, "claude_status", lambda: {"remaining": "unknown"})
    monkeypatch.setattr(provider_usage, "glm_status", lambda: {"remaining": "unknown"})
    response = api.get("/api/estate/usage")
    assert response.status_code == 200
    body = response.json()
    assert set(body["providers"]) == {"codex", "claude", "glm"}
    assert body["providers"]["codex"]["remaining"] == 31.0
    assert body["providers"]["claude"]["remaining"] == "unknown"
    assert "unknown means no authorised machine-readable source" in body["note"]


def test_execute_claude_omits_bare_and_uses_neutral_cwd(tmp_path, monkeypatch):
    import subprocess
    from pathlib import Path as P
    captured = {}

    class FakeProc:
        returncode = 0
        pid = 4242

        def communicate(self, input=None, timeout=None):
            return json.dumps({"type": "result", "is_error": False, "result": "ok",
                               "modelUsage": {"claude-sonnet-5": {}}}), ""

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["cwd"] = kwargs.get("cwd")
        return FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(P, "home", classmethod(lambda cls: tmp_path))
    launcher = tmp_path / "bin" / "claude"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text("#!/bin/sh\n")
    launcher.chmod(0o755)
    monkeypatch.setattr(estate_router, "_claude_launcher_path", lambda: launcher)
    monkeypatch.setenv("DATABASE_URL", "test-only")
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda provider, **kw: {
        "allowed": True, "outcome_id": "out", "provider": provider})
    monkeypatch.setattr(estate_router, "_record_provider_outcome", lambda *a: None)
    monkeypatch.setattr(estate_router, "current_host_id", lambda: "lab")
    result = estate_router.execute_claude("plan", timeout=10)
    assert result["ok"] is True and result["concrete_model"] == "claude-sonnet-5"
    assert "--bare" not in captured["args"]
    assert str(captured["cwd"]).endswith(".cache/aoteru/claude-lane")
    assert P(captured["cwd"]).is_dir()

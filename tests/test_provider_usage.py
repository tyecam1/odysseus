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
    for stamp, payload in events:
        lines.append(json.dumps({"timestamp": stamp, "type": "event", "payload": payload}))
    path.write_text("\n".join(lines) + "\n")


def _token_count(primary=None, secondary=None, plan="plus"):
    return {"type": "token_count", "rate_limits": {"primary": primary, "secondary": secondary},
            "credits": {"has_credits": False, "unlimited": False, "balance": "0"},
            "plan_type": plan}


P5 = {"used_percent": 5.0, "window_minutes": 300, "resets_at": 1795016288}
W69 = {"used_percent": 69.0, "window_minutes": 10080, "resets_at": 1795208916}
P90 = {"used_percent": 90.0, "window_minutes": 300, "resets_at": 1795000000}


def test_codex_windows_newest_valid_event_by_event_time_wins(tmp_path):
    newer_file = tmp_path / "a" / "rollout-new.jsonl"
    older_file = tmp_path / "b" / "rollout-old.jsonl"
    # OLDER mtime file carries the NEWEST event: event time must win
    _rollout(older_file, [("2026-11-18T13:40:00Z", _token_count(primary=P5, secondary=W69))])
    _rollout(newer_file, [("2026-11-18T10:00:00Z", _token_count(primary=P90))])
    os.utime(older_file, (1795014000, 1795014000))
    os.utime(newer_file, (1795016300, 1795016300))
    result = provider_usage.codex_windows(tmp_path)
    assert result["confidence"] == "provider-stated"
    assert result["plan_type"] == "plus"
    assert result["observed_at"].startswith("2026-11-18T13:40:00")
    pools = {w["pool"]: w for w in result["windows"]}
    assert pools["primary"]["used_percent"] == 5.0
    assert pools["primary"]["remaining_percent"] == 95.0
    assert pools["secondary"]["used_percent"] == 69.0
    assert pools["primary"]["resets_at"].startswith("2026-")
    assert result["remaining"] == 31.0  # most-constrained window


def test_codex_windows_unknown_when_no_recent_rollouts(tmp_path):
    result = provider_usage.codex_windows(tmp_path)
    assert result["remaining"] == "unknown" and result["reset"] == "unknown"
    assert result["confidence"] == "none"


def test_codex_windows_rejects_invalid_numbers(tmp_path):
    rollout = tmp_path / "r.jsonl"
    _rollout(rollout, [
        ("2026-11-18T12:00:00Z", _token_count(
            primary={"used_percent": -25.0, "window_minutes": 300, "resets_at": 1795016288})),
        ("2026-11-18T12:01:00Z", _token_count(
            primary={"used_percent": True, "window_minutes": 300, "resets_at": 1795016288})),
        ("2026-11-18T12:02:00Z", _token_count(
            primary={"used_percent": 10.0, "window_minutes": 300,
                     "resets_at": 999999999999999999999})),
        ("2026-11-18T12:03:00Z", _token_count(
            primary={"used_percent": 10.0, "window_minutes": 300, "resets_at": 1795016288},
            plan="x" * 60)),
    ])
    result = provider_usage.codex_windows(tmp_path)
    # the newest event with a valid primary percentage wins; malformed
    # plan_type is dropped. (The invalid-percentage events were never
    # candidates; the huge-reset event is simply older than the winner.)
    assert result["confidence"] == "provider-stated"
    assert result["windows"][0]["used_percent"] == 10.0
    assert result["windows"][0]["resets_at"].startswith("2026-")
    assert result["plan_type"] is None


def test_codex_windows_never_decodes_message_records(tmp_path):
    rollout = tmp_path / "r.jsonl"
    rollout.parent.mkdir(exist_ok=True)
    big_message = json.dumps({"timestamp": "2026-11-18T12:00:00Z", "type": "message",
                              "payload": {"secret": "x" * 20000}})
    rollout.write_text(big_message + "\n" + json.dumps({
        "timestamp": "2026-11-18T12:01:00Z", "type": "event",
        "payload": _token_count(primary=P5)}) + "\n")
    result = provider_usage.codex_windows(tmp_path)
    assert result["confidence"] == "provider-stated"
    assert result["windows"][0]["used_percent"] == 5.0


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


def test_codex_windows_huge_json_integers_and_filter_collisions(tmp_path):
    rollout = tmp_path / "r.jsonl"
    colliding_message = json.dumps({"timestamp": "2026-11-18T12:00:00Z", "type": "message",
                                    "payload": {"text": 'mentioned "token_count" and '
                                                        '"rate_limits" and "timestamp" inline'}})
    huge_int_event = json.dumps({"timestamp": "2026-11-18T12:01:00Z", "type": "event",
                                 "payload": _token_count(
                                     primary={"used_percent": 10 ** 401,
                                              "window_minutes": 300, "resets_at": 1795016288})})
    valid_event = json.dumps({"timestamp": "2026-11-18T12:02:00Z", "type": "event",
                              "payload": _token_count(primary=P5)})
    rollout.parent.mkdir(exist_ok=True)
    rollout.write_text("\n".join([colliding_message, huge_int_event, valid_event]) + "\n")
    result = provider_usage.codex_windows(tmp_path)
    assert result["confidence"] == "provider-stated"
    assert result["windows"][0]["used_percent"] == 5.0  # colliding message and huge int rejected


def test_codex_windows_discovery_visit_cap_is_bounded(tmp_path):
    deep = tmp_path / "d"
    deep.mkdir()
    for i in range(600):
        (deep / ("f%03d.jsonl" % i)).write_text("")
    result = provider_usage.codex_windows(tmp_path)  # must terminate, bounded
    assert result["remaining"] == "unknown"


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


def test_execute_claude_isolated_config_dir_and_neutral_cwd(tmp_path, monkeypatch):
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
        captured.update(kwargs)
        return FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(P, "home", classmethod(lambda cls: tmp_path))
    real_creds = tmp_path / ".claude" / ".credentials.json"
    real_creds.parent.mkdir(parents=True, exist_ok=True)
    real_creds.write_text("{}")
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
    args = captured["args"]
    assert "--bare" not in args
    env = captured["env"]
    config_dir = P(env["CLAUDE_CONFIG_DIR"])
    assert config_dir.is_dir()
    assert json.loads((config_dir / "settings.json").read_text()) == {"disableAllHooks": True}
    assert (config_dir / ".credentials.json").is_symlink()
    assert str(captured["cwd"]).endswith("claude-lane/cwd")
    assert P(captured["cwd"]).is_dir()

"""Read-only usage collection: rollout parsing, route scope, claude lane isolation."""
import json
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()
import core.database as cdb
from src import estate_router, provider_usage
from routes.estate_routing_routes import setup_estate_routing_routes


def _stamp(minutes_ago=1):
    t = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return t.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _pool(used, minutes=300, resets=1795016288):
    return '{"used_percent":%s,"window_minutes":%s,"resets_at":%s}' % (used, minutes, resets)


def _token_count_line(stamp, primary, secondary="null", plan="plus", ordinal=18, info="{}"):
    rate = ('{"limit_id":"codex","limit_name":null,"primary":%s,"secondary":%s,'
            '"credits":{"has_credits":false,"unlimited":false,"balance":"0"},'
            '"individual_limit":null,"spend_control_reached":null,"plan_type":"%s",'
            '"rate_limit_reached_type":null}' % (primary, secondary, plan))
    return ('{"timestamp":"%s","ordinal":%d,"type":"event_msg","payload":'
            '{"type":"token_count","info":%s,"rate_limits":%s}}' % (stamp, ordinal, info, rate))


def _day_dir(root, days_ago=0):
    day = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
    directory = root / ("%04d" % day.year) / ("%02d" % day.month) / ("%02d" % day.day)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _write(directory, name, lines):
    path = directory / name
    path.write_text("\n".join(lines) + "\n")
    return path


def test_codex_windows_newest_event_by_event_time_wins_across_files(tmp_path):
    day = _day_dir(tmp_path)
    older_mtime = _write(day, "rollout-a.jsonl", [
        _token_count_line(_stamp(5), _pool(5.0), _pool(69.0, 10080, 1795208916))])
    newer_mtime = _write(day, "rollout-b.jsonl", [_token_count_line(_stamp(90), _pool(90.0))])
    os.utime(older_mtime, (os.stat(newer_mtime).st_mtime - 100,) * 2)
    result = provider_usage.codex_windows(tmp_path)
    assert result["confidence"] == "provider-stated"
    assert result["plan_type"] == "plus"
    pools = {w["pool"]: w for w in result["windows"]}
    assert pools["primary"]["used_percent"] == 5.0
    assert pools["primary"]["remaining_percent"] == 95.0
    assert pools["secondary"]["used_percent"] == 69.0
    assert pools["secondary"]["window_minutes"] == 10080
    assert pools["primary"]["resets_at"].startswith("2026-")
    assert result["remaining"] == 31.0  # most-constrained window
    assert result["observed_at"][:16] == _stamp(5)[:16] or result["observed_at"][:13] == _stamp(5)[:13]


def test_codex_windows_unknown_without_rollouts(tmp_path):
    assert provider_usage.codex_windows(tmp_path)["remaining"] == "unknown"
    _day_dir(tmp_path)  # empty date directory
    result = provider_usage.codex_windows(tmp_path)
    assert result["remaining"] == "unknown" and result["confidence"] == "none"


def test_message_text_quoting_event_markers_cannot_spoof_a_window(tmp_path):
    day = _day_dir(tmp_path)
    spoof = ('{"timestamp":"%s","ordinal":9,"type":"response_item","payload":{"type":"message",'
             '"text":"fake: {\\"type\\":\\"token_count\\",\\"rate_limits\\":{\\"primary\\":'
             '{\\"used_percent\\":0.0,\\"window_minutes\\":300,\\"resets_at\\":1795016288}}}"}}' % _stamp(0))
    _write(day, "r.jsonl", [_token_count_line(_stamp(3), _pool(40.0)), spoof])
    result = provider_usage.codex_windows(tmp_path)
    assert result["windows"][0]["used_percent"] == 40.0  # the later spoof line never counts


def test_decoy_primary_inside_info_is_not_attributed(tmp_path):
    day = _day_dir(tmp_path)
    decoy = '{"x":{"primary":%s,"secondary":null}}' % _pool(1.0)
    _write(day, "r.jsonl", [_token_count_line(_stamp(2), _pool(55.0), info=decoy)])
    result = provider_usage.codex_windows(tmp_path)
    assert result["windows"][0]["used_percent"] == 55.0  # structurally last rate_limits wins


@pytest.mark.parametrize("bad_primary", [
    _pool(-25.0), _pool(250.0), _pool("true"), _pool(10 ** 401)])
def test_newest_malformed_event_yields_unknown_not_stale_data(tmp_path, bad_primary):
    day = _day_dir(tmp_path)
    _write(day, "r.jsonl", [_token_count_line(_stamp(30), _pool(5.0)),
                            _token_count_line(_stamp(1), bad_primary)])
    result = provider_usage.codex_windows(tmp_path)
    assert result["remaining"] == "unknown" and result["confidence"] == "none"


def test_out_of_range_window_minutes_keeps_the_newest_event_with_null_length(tmp_path):
    # window_minutes is descriptive: a non-conforming value must neither raise
    # nor push selection back to older (stale) data
    day = _day_dir(tmp_path)
    bad_minutes = '{"used_percent":1.0,"window_minutes":%d,"resets_at":1795016288}' % (10 ** 401)
    _write(day, "r.jsonl", [_token_count_line(_stamp(30), _pool(5.0)),
                            _token_count_line(_stamp(1), bad_minutes)])
    result = provider_usage.codex_windows(tmp_path)
    assert result["confidence"] == "provider-stated"
    assert result["windows"][0]["used_percent"] == 1.0
    assert result["windows"][0]["window_minutes"] is None


def test_malformed_secondary_invalidates_the_whole_reading(tmp_path):
    day = _day_dir(tmp_path)
    _write(day, "r.jsonl", [_token_count_line(_stamp(1), _pool(5.0), _pool(-3.0, 10080))])
    assert provider_usage.codex_windows(tmp_path)["remaining"] == "unknown"


def test_events_with_null_rate_limits_are_ignored_not_newest(tmp_path):
    day = _day_dir(tmp_path)
    null_event = ('{"timestamp":"%s","ordinal":30,"type":"event_msg","payload":'
                  '{"type":"token_count","info":null,"rate_limits":null}}' % _stamp(0))
    _write(day, "r.jsonl", [_token_count_line(_stamp(8), _pool(12.0)), null_event])
    assert provider_usage.codex_windows(tmp_path)["windows"][0]["used_percent"] == 12.0


def test_future_timestamp_event_is_rejected(tmp_path):
    day = _day_dir(tmp_path)
    future = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    _write(day, "r.jsonl", [_token_count_line(_stamp(4), _pool(20.0)),
                            _token_count_line(future, _pool(1.0))])
    assert provider_usage.codex_windows(tmp_path)["windows"][0]["used_percent"] == 20.0


def test_oversized_lines_are_skipped(tmp_path):
    day = _day_dir(tmp_path)
    huge = _token_count_line(_stamp(0), _pool(1.0), info='{"pad":"%s"}' % ("x" * 9000))
    _write(day, "r.jsonl", [_token_count_line(_stamp(6), _pool(33.0)), huge])
    assert provider_usage.codex_windows(tmp_path)["windows"][0]["used_percent"] == 33.0


def test_discovery_is_bounded_by_construction(tmp_path):
    day = _day_dir(tmp_path)
    for i in range(700):
        (day / ("f%03d.jsonl" % i)).write_text("")
    # a deep, wide tree outside the date directories must never be walked
    wide = tmp_path / "archive"
    wide.mkdir()
    for i in range(300):
        (wide / ("d%03d" % i)).mkdir()
    files = provider_usage._candidate_files(tmp_path, 0)
    assert len(files) <= provider_usage.MAX_DIR_ENTRIES * 2  # two possible date dirs (UTC/local)
    assert all(path.parent == day for _mtime, path in files)
    assert provider_usage.codex_windows(tmp_path)["remaining"] == "unknown"


def test_duplicated_rate_limits_key_cannot_mis_attribute_a_decoy(tmp_path):
    day = _day_dir(tmp_path)
    decoy = ('"rate_limit_reached_type":{"rate_limits":{"limit_id":"x","primary":%s,'
             '"secondary":null}}' % _pool(1.0))
    line = _token_count_line(_stamp(1), _pool(75.0)).replace(
        '"rate_limit_reached_type":null', decoy)
    assert line.count('"rate_limits":') == 2
    _write(day, "r.jsonl", [_token_count_line(_stamp(30), _pool(5.0)), line])
    result = provider_usage.codex_windows(tmp_path)
    # the ambiguous newest event is neither read as 1% nor replaced by stale 5%
    assert result["remaining"] == "unknown" and result["confidence"] == "none"


def test_duplicated_key_with_nested_null_is_ambiguous_not_skipped(tmp_path):
    day = _day_dir(tmp_path)
    line = _token_count_line(_stamp(1), _pool(75.0)).replace(
        '"rate_limit_reached_type":null', '"rate_limit_reached_type":{"rate_limits":null}')
    assert line.count('"rate_limits":') == 2
    _write(day, "r.jsonl", [_token_count_line(_stamp(30), _pool(5.0)), line])
    result = provider_usage.codex_windows(tmp_path)
    assert result["remaining"] == "unknown" and result["confidence"] == "none"


def test_read_is_one_bounded_tail_and_partial_trailing_line_is_ignored(tmp_path, monkeypatch):
    day = _day_dir(tmp_path)
    complete = _token_count_line(_stamp(5), _pool(12.0))
    partial = _token_count_line(_stamp(1), _pool(99.0))[:-20]  # cut mid-write, no newline
    path = day / "r.jsonl"
    path.write_text(complete + "\n" + partial)
    result = provider_usage.codex_windows(tmp_path)
    assert result["windows"][0]["used_percent"] == 12.0  # the half-written newest line is not read
    # a file larger than the per-file bound is read once, from its tail only
    monkeypatch.setattr(provider_usage, "TAIL_BYTES_PER_FILE", len(complete) + 10)
    older = _token_count_line(_stamp(40), _pool(88.0))
    path.write_text(older + "\n" + complete + "\n")
    assert provider_usage.codex_windows(tmp_path)["windows"][0]["used_percent"] == 12.0
    budget = [10 ** 9]
    seen = list(provider_usage._iter_events(path, budget))
    assert len(seen) == 1 and budget[0] == 10 ** 9 - (len(complete) + 10)


def test_file_deleted_between_discovery_and_read_is_tolerated(tmp_path, monkeypatch):
    day = _day_dir(tmp_path)
    real = _write(day, "real.jsonl", [_token_count_line(_stamp(2), _pool(21.0))])
    gone = day / "gone.jsonl"
    now = datetime.now(timezone.utc).timestamp()
    monkeypatch.setattr(provider_usage, "_candidate_files",
                        lambda root, cutoff: [(now, gone), (now - 5, real)])
    assert provider_usage.codex_windows(tmp_path)["windows"][0]["used_percent"] == 21.0


def test_null_primary_event_is_skipped_so_the_newest_real_window_is_used(tmp_path):
    day = _day_dir(tmp_path)
    null_primary = _token_count_line(_stamp(0), "null", "null")
    _write(day, "r.jsonl", [_token_count_line(_stamp(9), _pool(5.0)), null_primary])
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

    def fake_run(args, **kwargs):
        captured["auth_args"] = args
        captured["auth_kwargs"] = kwargs
        return subprocess.CompletedProcess(args, 0, json.dumps({
            "loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty", "subscriptionType": "pro"}))

    monkeypatch.setattr(subprocess, "run", fake_run)
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
    # the pre-inference auth attestation runs under the SAME stub env and neutral cwd
    assert captured["auth_args"] == [str(launcher), "auth", "status"]
    assert P(captured["auth_kwargs"]["env"]["CLAUDE_CONFIG_DIR"]) == config_dir
    assert str(captured["auth_kwargs"]["cwd"]).endswith("claude-lane/cwd")
    assert P(captured["cwd"]).is_dir()

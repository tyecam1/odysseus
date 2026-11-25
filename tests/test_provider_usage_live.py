"""The live Codex usage read: the CLI's own account rate-limit endpoint over stdio, with a fake CLI.

No test here spawns the real Codex CLI or touches a credential; the fake speaks the same line-delimited JSON."""
import json
import os
import stat
import sys
import time

import pytest

from src import estate_router, provider_usage as pu

FAKE = '''#!{python}
import json, os, sys, time
mode = os.environ.get("FAKE_MODE", "ok")
payload = json.loads(os.environ.get("FAKE_PAYLOAD", "{{}}"))
count = os.environ.get("FAKE_COUNTFILE")
if count:
    open(count, "a").write(str(os.getpid()) + "\\n")
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("method") == "initialize":
        if mode == "boolid_init":
            print(json.dumps({{"id": True, "result": {{}}}}), flush=True)
            time.sleep(60)
        print(json.dumps({{"id": msg["id"], "result": {{}}}}), flush=True)
    elif msg.get("method") == "account/rateLimits/read":
        if mode == "hang":
            time.sleep(60)
        elif mode == "exit":
            sys.exit(0)
        elif mode == "error":
            print(json.dumps({{"id": msg["id"], "error": {{"code": -1, "message": "boom"}}}}), flush=True)
        elif mode == "huge":
            print("x" * 200000, flush=True)
        elif mode == "partial":
            sys.stdout.write('{{"id": ' + str(msg["id"]))
            sys.stdout.flush()
            time.sleep(60)
        elif mode == "coalesce":
            sys.stdout.write(json.dumps({{"method": "x", "params": {{}}}}) + chr(10)
                             + json.dumps({{"id": msg["id"], "result": payload}}) + chr(10))
            sys.stdout.flush()
        elif mode == "bigframe":
            print(json.dumps({{"id": msg["id"], "result": payload, "pad": "x" * 3000}}), flush=True)
        elif mode == "boolid":
            print(json.dumps({{"id": True, "result": payload}}), flush=True)
            time.sleep(60)
        elif mode == "noise":
            print("not json at all", flush=True)
            print(json.dumps({{"method": "account/rateLimits/updated", "params": {{}}}}), flush=True)
            print(json.dumps({{"id": 99, "result": {{"rateLimits": None}}}}), flush=True)
            print(json.dumps({{"id": msg["id"], "result": payload}}), flush=True)
        else:
            print(json.dumps({{"id": msg["id"], "result": payload}}), flush=True)
'''

PRIMARY_RESET, SECONDARY_RESET = 1795643795, 1795814029


def snapshot(**over):
    snap = {"limitId": "codex", "planType": "plus", "rateLimitReachedType": None,
            "primary": {"usedPercent": 1, "windowDurationMins": 300, "resetsAt": PRIMARY_RESET},
            "secondary": {"usedPercent": 78, "windowDurationMins": 10080, "resetsAt": SECONDARY_RESET}}
    snap.update(over)
    return snap


def payload(snap=None, **over):
    snap = snap or snapshot()
    body = {"accountId": "acct-SECRET-123", "ordinaryUsageAllowed": True, "rateLimits": snap,
            "rateLimitsByLimitId": {"codex": snap}}
    body.update(over)
    return body


@pytest.fixture
def fake(tmp_path, monkeypatch):
    path = tmp_path / "codex"
    path.write_text(FAKE.format(python=sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    count = tmp_path / "spawns"
    monkeypatch.delenv("AOTERU_CODEX_USAGE_LIVE", raising=False)
    monkeypatch.setenv("FAKE_COUNTFILE", str(count))
    monkeypatch.setenv("FAKE_PAYLOAD", json.dumps(payload()))
    monkeypatch.setattr(pu, "_live_cache", {"entry": None})
    monkeypatch.setattr(pu, "_binary_cache", {"at": None, "value": None})
    monkeypatch.setattr(pu, "LIVE_DEADLINE_SECONDS", 3)
    # the child only inherits an allow-list; the fake CLI is steered through these test variables
    monkeypatch.setattr(pu, "_CHILD_ENV_KEYS", pu._CHILD_ENV_KEYS + ("FAKE_MODE", "FAKE_PAYLOAD", "FAKE_COUNTFILE"))

    def spawns():
        return len(count.read_text().split()) if count.exists() else 0

    return str(path), spawns


def read(binary, clock=lambda: 1000.0):
    return pu.codex_windows_live(binary=binary, clock=clock)


def test_a_good_read_reports_provider_stated_windows(fake):
    binary, _ = fake
    result = read(binary)
    assert result["confidence"] == "provider-stated" and result["source"] == pu.LIVE_SOURCE
    five, week = result["windows"]
    assert (five["pool"], five["used_percent"], five["remaining_percent"], five["window_minutes"]) == ("primary", 1.0, 99.0, 300)
    assert (week["pool"], week["remaining_percent"], week["window_minutes"]) == ("secondary", 22.0, 10080)
    assert five["resets_at"].startswith("2026-11-25T21:56") and week["resets_at"].startswith("2026-11-27T21:13")
    assert result["remaining"] == 22.0 and result["reset"] == five["resets_at"]
    assert result["plan_type"] == "plus" and result["rate_limit_reached"] is None and result["ordinary_usage_allowed"] is True
    assert "acct-SECRET" not in json.dumps(result)                     # the account id is never returned


def test_the_single_bucket_view_is_used_when_there_is_no_per_limit_map(fake, monkeypatch):
    binary, _ = fake
    monkeypatch.setenv("FAKE_PAYLOAD", json.dumps({"rateLimits": snapshot()}))
    assert read(binary)["confidence"] == "provider-stated"


def test_a_reached_limit_is_reported_as_the_provider_states_it(fake, monkeypatch):
    binary, _ = fake
    monkeypatch.setenv("FAKE_PAYLOAD", json.dumps(payload(snapshot(rateLimitReachedType="rate_limit_reached"),
                                                          ordinaryUsageAllowed=False)))
    result = read(binary)
    assert result["rate_limit_reached"] == "rate_limit_reached" and result["ordinary_usage_allowed"] is False


def test_unrelated_lines_and_other_request_ids_are_ignored(fake, monkeypatch):
    binary, _ = fake
    monkeypatch.setenv("FAKE_MODE", "noise")
    assert read(binary)["confidence"] == "provider-stated"


@pytest.mark.parametrize("bad", [
    {"primary": {"usedPercent": "1", "windowDurationMins": 300, "resetsAt": PRIMARY_RESET}},
    {"primary": {"usedPercent": 101, "windowDurationMins": 300, "resetsAt": PRIMARY_RESET}},
    {"primary": {"usedPercent": -1, "windowDurationMins": 300, "resetsAt": PRIMARY_RESET}},
    {"primary": {"usedPercent": True, "windowDurationMins": 300, "resetsAt": PRIMARY_RESET}},
    {"primary": {"usedPercent": 1.5, "windowDurationMins": 300, "resetsAt": PRIMARY_RESET}},
    {"primary": {"usedPercent": 1, "windowDurationMins": "300", "resetsAt": PRIMARY_RESET}},
    {"primary": {"usedPercent": 1, "windowDurationMins": 0, "resetsAt": PRIMARY_RESET}},
    {"primary": {"usedPercent": 1, "windowDurationMins": 300, "resetsAt": "soon"}},
    {"primary": "full"},
    {"secondary": {"usedPercent": 78, "resetsAt": "x"}},          # one malformed pool must not be dropped silently
    {"primary": None, "secondary": None},
])
def test_any_format_drift_is_unknown_never_a_guess(fake, monkeypatch, bad):
    binary, _ = fake
    monkeypatch.setenv("FAKE_PAYLOAD", json.dumps(payload(snapshot(**bad))))
    result = read(binary)
    assert result["confidence"] == "none" and result["remaining"] == "unknown" and result["windows"] == []
    assert "unrecognised format" in result["reason"]


@pytest.mark.parametrize("body", [[], "ok", None, {"rateLimits": None}, {"rateLimits": "x"}, {}])
def test_a_wrong_result_shape_is_unknown(fake, monkeypatch, body):
    binary, _ = fake
    monkeypatch.setenv("FAKE_PAYLOAD", json.dumps(body))
    assert read(binary)["confidence"] == "none"


@pytest.mark.parametrize("mode,reason", [("error", "refused"), ("exit", "closed the stream"),
                                         ("huge", "oversized"), ("hang", "before the deadline"),
                                         ("partial", "before the deadline"), ("boolid", "before the deadline")])
def test_a_failing_cli_is_unknown_with_a_reason(fake, monkeypatch, mode, reason):
    binary, _ = fake
    monkeypatch.setenv("FAKE_MODE", mode)
    monkeypatch.setattr(pu, "LIVE_DEADLINE_SECONDS", 1)
    started = time.monotonic()
    result = read(binary)
    assert result["confidence"] == "none" and reason in result["reason"]
    assert time.monotonic() - started < 6


def test_a_reply_that_arrives_together_with_a_notification_is_still_read(fake, monkeypatch):
    binary, _ = fake
    monkeypatch.setenv("FAKE_MODE", "coalesce")
    assert read(binary)["confidence"] == "provider-stated"


def test_a_complete_oversized_frame_in_one_read_is_refused(fake, monkeypatch):
    binary, _ = fake
    monkeypatch.setenv("FAKE_MODE", "bigframe")
    monkeypatch.setattr(pu, "LIVE_MAX_LINE", 2000)               # the 3000-byte frame (newline included) fits one read
    assert "oversized" in read(binary)["reason"]


def test_a_boolean_id_is_not_taken_for_request_one(fake, monkeypatch):
    binary, _ = fake
    monkeypatch.setenv("FAKE_MODE", "boolid_init")
    monkeypatch.setattr(pu, "LIVE_DEADLINE_SECONDS", 1)
    assert "before the deadline" in read(binary)["reason"]


@pytest.mark.parametrize("junk", [[1, 2], {"a": 1}, 5, True])
def test_non_string_metadata_becomes_null_and_the_windows_stay_usable(fake, monkeypatch, junk):
    binary, _ = fake
    monkeypatch.setenv("FAKE_PAYLOAD", json.dumps(payload(snapshot(planType=junk, rateLimitReachedType=junk))))
    result = read(binary)
    assert result["confidence"] == "provider-stated" and result["plan_type"] is None and result["rate_limit_reached"] is None
    assert len(result["windows"]) == 2


def test_a_failure_while_setting_up_the_pipe_still_kills_and_reaps_the_child(fake, monkeypatch):
    binary, _ = fake
    monkeypatch.setenv("FAKE_MODE", "hang")
    started = []
    real_popen = pu.subprocess.Popen

    def recording_popen(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        started.append(proc)
        return proc

    def refuse(*args, **kwargs):
        raise OSError("no")

    monkeypatch.setattr(pu.subprocess, "Popen", recording_popen)
    monkeypatch.setattr(pu.os, "set_blocking", refuse)
    result = read(binary)
    assert result["confidence"] == "none" and "failed" in result["reason"]
    assert len(started) == 1 and started[0].poll() is not None      # killed and reaped, not left running
    assert started[0].stdout.closed and started[0].stdin.closed


def test_a_refresh_that_finished_while_waiting_for_the_lock_is_not_repeated(fake, monkeypatch):
    binary, spawns = fake
    first = read(binary, clock=lambda: 1000.0)
    assert spawns() == 1
    entry = pu._live_cache["entry"]
    pu._live_cache["entry"] = None                              # the stale view a late caller took before the lock
    seen = {"calls": 0}
    real = pu._live_cache

    class Racy(dict):
        def __getitem__(self, key):
            seen["calls"] += 1
            return None if seen["calls"] == 1 else entry          # first look: stale; after the lock: fresh again

    monkeypatch.setattr(pu, "_live_cache", Racy(entry=None))
    second = read(binary, clock=lambda: 1001.0)
    assert second is first and spawns() == 1


def test_a_stalled_partial_line_cannot_outlast_the_deadline(fake, monkeypatch):
    binary, _ = fake
    monkeypatch.setenv("FAKE_MODE", "partial")
    monkeypatch.setattr(pu, "LIVE_DEADLINE_SECONDS", 1)
    started = time.monotonic()
    assert "before the deadline" in read(binary)["reason"]
    assert time.monotonic() - started < 4


def test_a_cli_that_cannot_be_started_is_unknown_not_an_error(tmp_path, monkeypatch):
    monkeypatch.delenv("AOTERU_CODEX_USAGE_LIVE", raising=False)
    monkeypatch.setattr(pu, "_live_cache", {"entry": None})
    result = pu.codex_windows_live(binary=str(tmp_path / "missing"))
    assert result["confidence"] == "none" and "could not be started" in result["reason"]


def test_the_child_gets_only_what_it_needs_of_this_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-leak")
    monkeypatch.setenv("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/1/x")
    env = pu._child_env()
    assert "OPENAI_API_KEY" not in env and "DISCORD_WEBHOOK" not in env and "PATH" in env


@pytest.mark.parametrize("field,value", [("planType", "acct-SECRET-123"), ("rateLimitReachedType", "acct-SECRET-123")])
def test_a_field_outside_the_clis_own_enum_is_never_echoed(fake, monkeypatch, field, value):
    binary, _ = fake
    monkeypatch.setenv("FAKE_PAYLOAD", json.dumps(payload(snapshot(**{field: value}))))
    result = read(binary)
    assert result["confidence"] == "provider-stated" and "acct-SECRET" not in json.dumps(result)


def test_a_bucket_that_is_not_codex_is_never_reported_as_codex(fake, monkeypatch):
    binary, _ = fake
    other = snapshot(limitId="codex_other")
    for body in ({"rateLimits": other},
                 {"rateLimitsByLimitId": {"codex": other}},
                 {"rateLimits": snapshot(), "rateLimitsByLimitId": {"codex": "bad"}},
                 {"rateLimits": snapshot(), "rateLimitsByLimitId": {"codex": other}}):
        monkeypatch.setattr(pu, "_live_cache", {"entry": None})
        monkeypatch.setenv("FAKE_PAYLOAD", json.dumps(body))
        assert read(binary)["confidence"] == "none", body


@pytest.mark.parametrize("reset", [10 ** 400, 4102444800 * 10, -5, 0, 1.5e9, "soon", True])
def test_an_unusable_reset_invalidates_the_reading_instead_of_being_dropped(fake, monkeypatch, reset):
    binary, _ = fake
    snap = snapshot()
    snap["secondary"] = {"usedPercent": 78, "windowDurationMins": 10080, "resetsAt": reset}
    monkeypatch.setenv("FAKE_PAYLOAD", '{"rateLimits": %s}' % json.dumps(snap).replace('"resetsAt": 1000', '"resetsAt": 1000'))
    result = read(binary)
    assert result["confidence"] == "none" and "unrecognised format" in result["reason"]


def test_a_missing_reset_is_allowed_and_stays_null(fake, monkeypatch):
    binary, _ = fake
    snap = snapshot()
    snap["secondary"]["resetsAt"] = None
    monkeypatch.setenv("FAKE_PAYLOAD", json.dumps({"rateLimits": snap}))
    result = read(binary)
    assert result["confidence"] == "provider-stated" and result["windows"][1]["resets_at"] is None


def test_only_one_refresh_runs_and_a_second_caller_does_not_queue_behind_it(fake):
    binary, spawns = fake
    assert pu._live_lock.acquire(blocking=False)
    try:
        started = time.monotonic()
        result = read(binary)
        assert result["confidence"] == "none" and "in progress" in result["reason"]
        assert time.monotonic() - started < 1 and spawns() == 0
    finally:
        pu._live_lock.release()


def test_the_installed_cli_is_located_once_not_once_per_request(fake, monkeypatch):
    binary, spawns = fake
    probes = []
    monkeypatch.setattr(estate_router, "_codex_available", lambda: probes.append(1) or (True, binary))
    pu.codex_windows_live(clock=lambda: 1000.0)
    pu._live_cache.update(entry=None)                           # force a second read inside the binary-cache window
    pu.codex_windows_live(clock=lambda: 1100.0)
    assert len(probes) == 1 and spawns() == 2


def test_a_missing_cli_is_remembered_so_it_is_not_probed_every_request(monkeypatch):
    monkeypatch.delenv("AOTERU_CODEX_USAGE_LIVE", raising=False)
    monkeypatch.setattr(pu, "_live_cache", {"entry": None})
    monkeypatch.setattr(pu, "_binary_cache", {"at": None, "value": None})
    probes = []
    monkeypatch.setattr(estate_router, "_codex_available", lambda: probes.append(1) or (False, None))
    first = pu.codex_windows_live(clock=lambda: 1000.0)
    second = pu.codex_windows_live(clock=lambda: 1001.0)
    assert first["confidence"] == "none" and second is first and len(probes) == 1


def test_a_hung_cli_is_killed_not_left_running(fake, monkeypatch, tmp_path):
    binary, _ = fake
    monkeypatch.setenv("FAKE_MODE", "hang")
    monkeypatch.setattr(pu, "LIVE_DEADLINE_SECONDS", 1)
    read(binary)
    pid = int((tmp_path / "spawns").read_text().split()[0])
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    pytest.fail("the CLI process outlived the read")


def test_a_good_reading_is_cached_for_ten_minutes(fake):
    binary, spawns = fake
    read(binary, clock=lambda: 1000.0)
    read(binary, clock=lambda: 1000.0 + pu.LIVE_TTL_SECONDS - 1)
    assert spawns() == 1
    read(binary, clock=lambda: 1000.0 + pu.LIVE_TTL_SECONDS + 1)
    assert spawns() == 2


def test_a_failed_read_is_retried_later_not_every_call(fake, monkeypatch):
    binary, spawns = fake
    monkeypatch.setenv("FAKE_MODE", "error")
    read(binary, clock=lambda: 1000.0)
    read(binary, clock=lambda: 1000.0 + pu.LIVE_RETRY_SECONDS - 1)
    assert spawns() == 1
    read(binary, clock=lambda: 1000.0 + pu.LIVE_RETRY_SECONDS + 1)
    assert spawns() == 2


def test_the_read_can_be_switched_off_and_then_spawns_nothing(fake, monkeypatch):
    binary, spawns = fake
    monkeypatch.setenv("AOTERU_CODEX_USAGE_LIVE", "0")
    assert read(binary)["confidence"] == "none" and spawns() == 0


def test_a_missing_cli_is_unknown(fake, monkeypatch):
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (False, None))
    result = pu.codex_windows_live()
    assert result["confidence"] == "none" and "not installed" in result["reason"]


def test_the_default_reader_never_reaches_the_cli_while_the_test_guard_is_set(monkeypatch):
    assert os.environ.get("AOTERU_CODEX_USAGE_LIVE") == "0"
    monkeypatch.setattr(estate_router, "_codex_available", lambda: pytest.fail("the guard must stop the read first"))
    monkeypatch.setattr(pu, "_live_read", lambda *a, **k: pytest.fail("no process may be started"))
    assert "disabled" in pu.codex_windows_live()["reason"]


def test_the_status_falls_back_to_rollouts_and_says_why(monkeypatch):
    monkeypatch.setattr(pu, "codex_windows_live", lambda *a, **k: {"confidence": "none", "reason": "no response before the deadline"})
    monkeypatch.setattr(pu, "codex_windows", lambda *a, **k: {"confidence": "provider-stated", "source": "codex-cli-session-rollouts"})
    status = pu.codex_status()
    assert status["source"] == "codex-cli-session-rollouts" and status["live_read"] == "no response before the deadline"


def test_the_status_prefers_the_live_read(monkeypatch):
    monkeypatch.setattr(pu, "codex_windows_live", lambda *a, **k: {"confidence": "provider-stated", "source": pu.LIVE_SOURCE})
    monkeypatch.setattr(pu, "codex_windows", lambda *a, **k: pytest.fail("rollouts are only a fallback"))
    assert pu.codex_status()["source"] == pu.LIVE_SOURCE


def test_the_snapshot_reports_the_live_codex_source(monkeypatch):
    monkeypatch.setattr(pu, "codex_status", lambda: {"source": "marker"})
    monkeypatch.setattr(pu, "claude_status", lambda: {})
    monkeypatch.setattr(pu, "glm_status", lambda: {})
    assert pu.usage_snapshot()["providers"]["codex"] == {"source": "marker"}



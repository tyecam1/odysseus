"""Owner-attention alerts to the owner's phone (self-hosted ntfy on the tailnet).

Delivery tests inject the transport; the transport tests talk only to a loopback server started by the test.
Nothing here reaches the real channel file, the real tailnet or the real Codex CLI."""
import http.server
import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()
import core.database as cdb
from core.database import LazyUsageRun, utcnow_naive
from src import estate_router, lazy_usage_runtime as rt, owner_alerts as oa, owner_decisions as od

SECRET = "s3cret-publish-password-0123456789"
NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
OWNER = "aoteru-admin"
APPROVAL = {"task_ref": "obsidian-phd:ready/2026-10-26-cpi-supervision-update.agent-task.md",
            "task_id": "2026-10-26-cpi-supervision-update", "gate": "owner_approval",
            "scope_sha256": "8c16e5c0fed273284e682099083cfef12da603198c5d0b6f971455299bd90b23",
            "opened_at": "2026-11-20T10:00:00"}
ACCEPT = {"task_ref": "odysseus:ready/2026-11-09-qualify-glm.agent-task.md", "task_id": "2026-11-09-qualify-glm",
          "gate": "owner_acceptance", "opened_at": "2026-11-21T09:00:00"}
OK = {"claude": {"state": "ok", "allowed": True}, "codex": {"state": "ok", "allowed": True},
      "glm": {"state": "ok", "allowed": True}}


@pytest.fixture(autouse=True)
def fresh_module_state(monkeypatch):
    monkeypatch.setattr(oa, "_persist_blocked_until", 0.0)
    monkeypatch.setattr(oa, "_worker", {"thread": None, "started": 0.0, "abandoned": []})


def write_channel(tmp_path, **overrides):
    data = {"kind": "ntfy", "base_url": "http://100.75.149.126:8091", "topic": "lazyusage-abcdef0123456789",
            "user": "odysseus", "password": SECRET, "owner": OWNER, **overrides}
    path = tmp_path / "ntfy_channel.json"
    path.write_text(json.dumps(data))
    os.chmod(path, 0o600)
    return path


class Wire:
    """A fake transport that records what would have been sent."""

    def __init__(self, status=200):
        self.status, self.sent = status, []

    def __call__(self, channel, headers, body, timeout):
        self.sent.append({"channel": channel, "headers": headers, "body": body})
        if isinstance(self.status, Exception):
            raise self.status
        return self.status


def run_view(state="budget_exhausted", finished=NOW - timedelta(minutes=5), run_id="52beaff6-c622-440d-91ea-a998676c8369", **extra):
    return {"id": run_id, "state": state, "terminal_reason": "max_paid_calls", "finished_at": finished.isoformat(),
            "counters": {"paid_calls": 4}, "budgets": {"max_paid_calls": 4}, **extra}


def blocked(state, **extra):
    return {"state": state, "allowed": False, **extra}


def send(tmp_path, wire, *, owed=(), runs=(), providers=OK, ts=NOW.timestamp(), channel=None):
    return oa.notify(list(owed), list(runs), providers, state_path=tmp_path / "state.json",
                     channel_path=channel or write_channel(tmp_path), post=wire, clock=lambda: ts)


# ---------------------------------------------------------------- the channel file

@pytest.mark.parametrize("base", ["http://100.75.149.126:8091", "http://100.64.0.1", "http://100.127.255.254:8091",
                                  "https://100.75.149.126:8443"])
def test_a_literal_tailnet_address_is_accepted(tmp_path, base):
    status, channel = oa._load_channel(write_channel(tmp_path, base_url=base))
    assert status == "ok" and channel["url"].startswith(base.split("//")[0] + "//100.") and channel["owner"] == OWNER


@pytest.mark.parametrize("base", [
    "http://8.8.8.8:8091", "http://example.com", "http://127.0.0.1:8091", "http://100.128.0.1", "http://100.63.255.255",
    "http://192.168.8.245", "http://lab.tail171792.ts.net:8091", "http://evil.ts.net.example.com",   # no name, ever
    "http://user:pw@100.75.149.126", "http://@100.75.149.126", "http://:@100.75.149.126",
    "http://100.75.149.126/path", "http://100.75.149.126?x=1", "http://100.75.149.126/#f",
    "http://100.75.149.126:0", "http://100.75.149.126:99999", "http://100.75.149.126:abc",
    "ftp://100.75.149.126", "http://[fd7a:115c:a1e0::1]:8091", "http://100.75.149.126.", "http://0x64.0x4b.0x95.0x7e",
    "http://1684441470", "", "http://"])
def test_anything_that_is_not_a_literal_tailnet_address_is_refused(tmp_path, base):
    assert oa._load_channel(write_channel(tmp_path, base_url=base)) == ("bad_channel", None)


@pytest.mark.parametrize("field,value", [("topic", "short"), ("topic", "has space in it"), ("topic", "../escape12345"),
                                         ("user", ""), ("user", "a b"), ("password", ""), ("kind", "discord"),
                                         ("owner", ""), ("owner", "a b c")])
def test_a_malformed_channel_sends_nothing(tmp_path, field, value):
    wire = Wire()
    assert send(tmp_path, wire, owed=[APPROVAL], channel=write_channel(tmp_path, **{field: value})) == "bad_channel"
    assert wire.sent == []


def test_a_channel_without_an_owner_sends_nothing(tmp_path):
    path = write_channel(tmp_path)
    data = json.loads(path.read_text())
    del data["owner"]
    path.write_text(json.dumps(data))
    assert oa._load_channel(path) == ("bad_channel", None)


def test_a_missing_channel_is_a_quiet_no_op(tmp_path):
    wire = Wire()
    assert oa.notify([APPROVAL], [], OK, state_path=tmp_path / "s.json", channel_path=tmp_path / "none.json",
                     post=wire) == "no_channel"
    assert wire.sent == [] and oa.enabled_owner(tmp_path / "none.json") is None


def test_the_enabled_owner_is_the_channels_owner(tmp_path):
    assert oa.enabled_owner(write_channel(tmp_path)) == OWNER


def test_a_group_readable_or_symlinked_channel_is_refused(tmp_path):
    path = write_channel(tmp_path)
    os.chmod(path, 0o640)
    assert oa._load_channel(path)[0] == "channel_not_private"
    os.chmod(path, 0o600)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    assert oa._load_channel(link) == ("bad_channel", None)


@pytest.mark.parametrize("mode", [0o770, 0o750, 0o755, 0o705])
def test_a_directory_others_can_use_is_refused(tmp_path, mode):
    path = write_channel(tmp_path)
    os.chmod(tmp_path, mode)
    try:
        assert oa._load_channel(path)[0] == "channel_not_private"
    finally:
        os.chmod(tmp_path, 0o700)


def test_a_symlinked_directory_is_refused(tmp_path):
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    write_channel(real)
    (tmp_path / "alias").symlink_to(real)
    assert oa._load_channel(tmp_path / "alias" / "ntfy_channel.json") == ("bad_channel", None)


def test_a_fifo_cannot_block_the_tick(tmp_path):
    fifo = tmp_path / "fifo.json"
    os.mkfifo(fifo, 0o600)
    assert oa._load_channel(fifo) == ("bad_channel", None)


def test_a_huge_channel_file_is_not_read_whole(tmp_path):
    path = tmp_path / "big.json"
    path.write_text(" " * 200000 + "{}")
    os.chmod(path, 0o600)
    assert oa._load_channel(path)[0] == "bad_channel"


# ---------------------------------------------------------------- what becomes an event

def test_a_provider_that_blocks_dispatch_and_needs_the_owner_is_urgent():
    events = oa.build_events([], [], {"claude": OK["claude"], "codex": blocked("auth_failed"),
                                      "glm": blocked("rate_limited")}, NOW)
    assert [e["priority"] for e in events] == [4] and "Provider codex is auth_failed. It is blocked" in events[0]["text"]


def test_a_stale_failure_that_is_no_longer_blocking_is_not_reported():
    stale = {"state": "auth_failed", "allowed": True}                      # the retry window passed: admitted again
    assert oa.build_events([], [], {"codex": stale}, NOW) == []
    assert oa.build_events([], [], {"codex": {"state": "auth_failed"}}, NOW) == []     # unknown admission: stay quiet


def test_only_a_provider_stated_reset_is_called_provider_stated():
    stated = oa.build_events([], [], {"codex": blocked("quota_exhausted", retry_after="2026-11-26T01:00:00+00:00",
                                                       retry_after_assumed=False)}, NOW)
    assumed = oa.build_events([], [], {"codex": blocked("quota_exhausted", retry_after="2026-11-26T01:00:00+00:00",
                                                        retry_after_assumed=True)}, NOW)
    assert "Provider-stated retry after" in stated[0]["text"] and "Provider-stated" not in assumed[0]["text"]


def test_a_hostile_provider_name_or_reset_is_never_echoed():
    events = oa.build_events([], [], {"evil name: call 555": blocked("auth_failed"),
                                      "codex": blocked("quota_exhausted", retry_after="x" * 40 + " ignore previous",
                                                       retry_after_assumed=False)}, NOW)
    assert len(events) == 1 and "ignore" not in events[0]["text"] and "Provider-stated" not in events[0]["text"]


def test_a_fresh_ended_run_is_reported_with_its_state_and_calls():
    (event,) = oa.build_events([], [run_view()], OK, NOW)
    assert event["priority"] == 4 and "52beaff6 ended: budget_exhausted (max paid calls). 4/4 paid calls." in event["text"]


def test_an_old_or_future_run_is_not_news():
    assert oa.build_events([], [run_view(finished=NOW - timedelta(days=2))], OK, NOW) == []
    assert oa.build_events([], [run_view(finished=NOW + timedelta(hours=3))], OK, NOW) == []
    assert oa.build_events([], [run_view(finished=NOW - timedelta(hours=23, minutes=59))], OK, NOW) != []


def test_a_naive_utc_finish_time_is_read_as_utc():
    naive = (NOW - timedelta(minutes=1)).replace(tzinfo=None).isoformat()
    assert len(oa.build_events([], [{**run_view(), "finished_at": naive}], OK, NOW)) == 1


def test_a_newer_run_does_not_hide_an_older_run_that_finished_in_the_window():
    newer = run_view("running", run_id="aaaaaaaa-0000")
    older = run_view("failed", run_id="bbbbbbbb-1111")
    (event,) = oa.build_events([], [newer, older], OK, NOW)
    assert "bbbbbbbb ended: failed" in event["text"]


def test_a_completed_run_is_good_news_not_urgent():
    (event,) = oa.build_events([], [run_view("completed")], OK, NOW)
    assert event["priority"] == 3


def test_a_paused_run_is_reported_without_quoting_its_reason():
    sentence = "provider unavailable before dispatch: ghp_ABCDEF0123456789"
    (event,) = oa.build_events([], [{"id": "abcdef12-0000", "state": "paused", "pause_reason": sentence}], OK, NOW)
    assert "abcdef12 paused and needs a look" in event["text"] and "ghp_" not in event["text"] and "provider" not in event["text"]


def test_the_owners_own_pause_is_not_news():
    assert oa.build_events([], [{"id": "abcdef12-0000", "state": "paused", "pause_reason": "operator"}], OK, NOW) == []


def test_a_running_run_is_not_an_event():
    assert oa.build_events([], [{"id": "abcdef12-0000", "state": "running"}], OK, NOW) == []


@pytest.mark.parametrize("reason", ["boom: token=ABCDEFGH12345678abcdefgh12345678", "see https://evil.example/x",
                                    "line one\nline two", "Traceback (most recent call last)", "x" * 80, "maple_orbit_cedar",
                                    "", None])
def test_only_a_reason_our_runtime_records_is_ever_shown(reason):
    (ended,) = oa.build_events([], [run_view(terminal_reason=reason)], OK, NOW)
    assert "(unspecified)" in ended["text"] and "token" not in ended["text"] and "evil" not in ended["text"]
    assert "maple" not in ended["text"]


@pytest.mark.parametrize("reason", sorted(oa._TERMINAL_REASONS))
def test_every_recorded_reason_is_shown_as_words(reason):
    (ended,) = oa.build_events([], [run_view(terminal_reason=reason)], OK, NOW)
    assert f"({reason.replace('_', ' ')})" in ended["text"]


def test_waiting_decisions_are_counted_per_repository_with_no_task_text():
    (event,) = oa.build_events([APPROVAL, ACCEPT], [], OK, NOW)
    assert "1 approval and 1 acceptance waiting (odysseus 1, obsidian-phd 1)" in event["text"]
    assert "qualify" not in event["text"] and "supervision" not in event["text"] and "/lazyUsage" in event["text"]


def test_the_decision_key_changes_when_the_set_changes():
    (a,) = oa.build_events([APPROVAL], [], OK, NOW)
    (b,) = oa.build_events([APPROVAL, ACCEPT], [], OK, NOW)
    assert a["key"] != b["key"]


def test_agent_only_debts_do_not_page_the_owner():
    debts = [{"task_ref": "odysseus:ready/x.agent-task.md", "task_id": "x", "gate": g, "opened_at": "2026-11-21T09:00:00"}
             for g in ("verification", "independent_review", "recovery", "finalization")]
    assert oa.build_events(debts, [], OK, NOW) == []


def test_urgent_events_come_first():
    events = oa.build_events([APPROVAL], [run_view()], {"codex": blocked("auth_failed")}, NOW)
    assert [e["priority"] for e in events] == [4, 4, 3]


@pytest.mark.parametrize("task_id", [
    "see https://evil.example/x @everyone `code` [a](b)",
    "deploy-with-key-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
    "maple-orbit-cedar",
    "ghp_" + "A1b2C3d4" * 5,
    "x" * 300])
def test_nothing_a_repository_wrote_reaches_the_message(task_id):
    debt = {**APPROVAL, "task_id": task_id, "task_ref": "odysseus:ready/" + task_id + ".md"}
    (event,) = oa.build_events([debt], [], OK, NOW)
    assert event["text"] == "Needs you: 1 approval waiting (odysseus 1). Decide from the laptop with /lazyUsage."


def test_an_unknown_repository_is_counted_as_other_never_echoed():
    debt = {**APPROVAL, "task_ref": "maple-orbit:ready/x.md"}
    (event,) = oa.build_events([debt], [], OK, NOW)
    assert "(other 1)" in event["text"] and "maple" not in event["text"]


# ---------------------------------------------------------------- delivery

def test_a_new_event_is_sent_once_with_a_short_plain_body(tmp_path):
    wire = Wire()
    assert send(tmp_path, wire, owed=[APPROVAL]) == "sent"
    (message,) = wire.sent
    assert message["headers"]["Title"] == "lazyUsage" and message["headers"]["Priority"] == "3"
    assert len(message["body"]) <= oa.MAX_BODY and message["body"].isascii()
    assert send(tmp_path, wire, owed=[APPROVAL], ts=NOW.timestamp() + 7200) == "nothing_new"
    assert len(wire.sent) == 1


def test_the_secret_never_appears_in_the_message_or_the_state(tmp_path):
    wire = Wire()
    send(tmp_path, wire, owed=[APPROVAL], runs=[run_view()])
    assert SECRET not in json.dumps(wire.sent[0]["headers"]) and SECRET not in wire.sent[0]["body"]
    assert SECRET not in (tmp_path / "state.json").read_text()


def test_the_state_file_holds_hashes_not_free_text(tmp_path):
    paused = {"id": "abcdef12-0000", "state": "paused", "pause_reason": "a secret reason: hunter2-hunter2-hunter2"}
    send(tmp_path, Wire(), runs=[paused])
    assert "hunter2" not in (tmp_path / "state.json").read_text()


def test_a_second_message_waits_for_the_cooldown(tmp_path):
    wire = Wire()
    assert send(tmp_path, wire, owed=[APPROVAL]) == "sent"
    assert send(tmp_path, wire, owed=[APPROVAL, ACCEPT], ts=NOW.timestamp() + 60) == "cooldown"
    assert send(tmp_path, wire, owed=[APPROVAL, ACCEPT], ts=NOW.timestamp() + 601) == "sent"
    assert len(wire.sent) == 2


def test_a_failed_send_is_not_recorded_and_is_retried(tmp_path, caplog):
    boom = Wire(RuntimeError(f"connect failed to http://100.75.149.126 {SECRET}"))
    with caplog.at_level(logging.WARNING):
        assert send(tmp_path, boom, owed=[APPROVAL]) == "send_failed"
    assert SECRET not in caplog.text and "100.75.149.126" not in caplog.text
    assert send(tmp_path, Wire(503), owed=[APPROVAL]) == "cooldown"             # the attempt was reserved
    assert send(tmp_path, Wire(503), owed=[APPROVAL], ts=NOW.timestamp() + 601) == "send_failed"
    good = Wire()
    assert send(tmp_path, good, owed=[APPROVAL], ts=NOW.timestamp() + 1300) == "sent" and len(good.sent) == 1


def test_urgent_events_lead_and_share_one_message(tmp_path):
    wire = Wire()
    send(tmp_path, wire, owed=[APPROVAL], runs=[run_view()], providers={"codex": blocked("auth_failed")})
    (message,) = wire.sent
    assert message["headers"]["Priority"] == "4" and message["body"].splitlines()[0].startswith("Provider codex")


def test_events_that_do_not_fit_wait_for_the_next_message_and_are_then_delivered(tmp_path):
    runs = [{**run_view("failed", run_id=f"{i:08x}-aaaa"), "terminal_reason": "r" * 39} for i in range(3)]
    providers = {"codex": blocked("quota_exhausted")}
    wire, ts = Wire(), NOW.timestamp()
    assert send(tmp_path, wire, owed=[APPROVAL], runs=runs, providers=providers, ts=ts) == "sent"
    assert len(wire.sent[0]["body"]) <= oa.MAX_BODY and wire.sent[0]["body"].count("\n") + 1 <= oa.MAX_EVENTS
    for _ in range(6):
        ts += oa.MIN_INTERVAL_SECONDS + 1
        if send(tmp_path, wire, owed=[APPROVAL], runs=runs, providers=providers, ts=ts) != "sent":
            break
    seen = "\n".join(m["body"] for m in wire.sent)
    for fragment in ("Provider codex", "00000000 ended", "00000001 ended", "00000002 ended", "Needs you"):
        assert fragment in seen, fragment
    assert send(tmp_path, wire, owed=[APPROVAL], runs=runs, providers=providers, ts=ts + 700) == "nothing_new"


def test_the_daily_cap_counts_messages_and_is_a_hard_ceiling(tmp_path):
    wire, ts, results = Wire(), NOW.timestamp(), []
    for i in range(oa.DAILY_CAP + 3):
        debts = [{**APPROVAL, "task_ref": f"odysseus:ready/t{j}.md", "task_id": f"t{j}"} for j in range(i + 1)]
        results.append(send(tmp_path, wire, owed=debts, ts=ts))
        ts += oa.MIN_INTERVAL_SECONDS + 1
    assert results.count("sent") == oa.DAILY_CAP and results[-1] == "daily_cap"


def test_one_message_with_several_events_counts_once_toward_the_cap(tmp_path):
    send(tmp_path, Wire(), owed=[APPROVAL], runs=[run_view()], providers={"codex": blocked("auth_failed")})
    state = json.loads((tmp_path / "state.json").read_text())
    assert len([k for k in state if k.startswith(oa._SEND)]) == 1


def test_a_quiet_day_sends_one_heartbeat_then_waits_a_day(tmp_path):
    wire = Wire()
    assert send(tmp_path, wire) == "heartbeat"
    assert "Heartbeat: 0 decisions waiting" in wire.sent[0]["body"] and wire.sent[0]["headers"]["Priority"] == "2"
    assert send(tmp_path, wire, ts=NOW.timestamp() + 3600) == "nothing_new"
    assert send(tmp_path, wire, ts=NOW.timestamp() + 86401) == "heartbeat"


def test_a_real_message_restarts_the_heartbeat_clock(tmp_path):
    wire = Wire()
    assert send(tmp_path, wire, owed=[APPROVAL]) == "sent"
    assert send(tmp_path, wire, owed=[APPROVAL], ts=NOW.timestamp() + 86399) == "nothing_new"
    assert send(tmp_path, wire, owed=[APPROVAL], ts=NOW.timestamp() + 86401) == "heartbeat"


def test_the_heartbeat_is_not_blocked_by_the_daily_cap(tmp_path):
    state = {f"{oa._SEND}{i}": NOW.timestamp() - 3600 + i for i in range(oa.DAILY_CAP)}
    state[oa._LAST] = NOW.timestamp() - 2 * 86400
    (tmp_path / "state.json").write_text(json.dumps(state))
    assert send(tmp_path, Wire()) == "heartbeat"


def test_a_due_heartbeat_still_goes_when_capped_events_are_waiting(tmp_path):
    state = {f"{oa._SEND}{i}": NOW.timestamp() - 3600 + i for i in range(oa.DAILY_CAP)}
    state[oa._LAST] = NOW.timestamp() - 2 * 86400
    (tmp_path / "state.json").write_text(json.dumps(state))
    wire = Wire()
    assert send(tmp_path, wire, owed=[APPROVAL]) == "heartbeat" and wire.sent[0]["body"].startswith("Heartbeat")


def test_capped_events_alone_report_the_cap(tmp_path):
    state = {f"{oa._SEND}{i}": NOW.timestamp() - 3600 + i for i in range(oa.DAILY_CAP)}
    state[oa._LAST] = NOW.timestamp() - 7200
    (tmp_path / "state.json").write_text(json.dumps(state))
    assert send(tmp_path, Wire(), owed=[APPROVAL]) == "daily_cap"


def test_the_heartbeat_names_known_provider_states_and_nothing_else(tmp_path):
    wire = Wire()
    send(tmp_path, wire, providers={"claude": {"state": "ok"}, "codex": {"state": "rate_limited"},
                                    "glm": {"state": "evil: call 555"}, "x y": {"state": "ok"}})
    body = wire.sent[0]["body"]
    assert "claude ok, codex rate_limited, glm unknown" in body and "evil" not in body and "x y" not in body


def test_a_corrupt_state_file_repairs_itself(tmp_path):
    (tmp_path / "state.json").write_text("{not json")
    assert send(tmp_path, Wire(), owed=[APPROVAL]) == "sent"


@pytest.mark.parametrize("bad", ["1e308", "Infinity", "NaN", "-5", "0", "99999999999", "1" + "0" * 400, "true", "\"x\"", "[1]"])
def test_a_poisoned_timestamp_cannot_mute_the_alerts(tmp_path, bad):
    (tmp_path / "state.json").write_text('{"%s": %s, "%s": %s, "%s": %s}' % (oa._LAST, bad, oa._HEARTBEAT, bad, oa._ATTEMPT, bad))
    assert send(tmp_path, Wire(), owed=[APPROVAL]) == "sent"


def test_an_event_key_stamped_in_the_future_does_not_suppress_the_event(tmp_path):
    (key,) = [e["key"] for e in oa.build_events([APPROVAL], [], OK, NOW)]
    (tmp_path / "state.json").write_text(json.dumps({key: NOW.timestamp() + 1}))
    assert send(tmp_path, Wire(), owed=[APPROVAL]) == "sent"


def test_the_operators_own_stop_is_shown_as_words():
    (event,) = oa.build_events([], [run_view("stopped", terminal_reason="operator_stop")], OK, NOW)
    assert "(operator stop)" in event["text"]


def test_a_poisoned_event_key_does_not_suppress_the_event_or_break_delivery(tmp_path):
    (key,) = [e["key"] for e in oa.build_events([APPROVAL], [], OK, NOW)]
    (tmp_path / "state.json").write_text('{"%s": NaN, "other": %s}' % (key, "1" + "0" * 400))
    assert send(tmp_path, Wire(), owed=[APPROVAL]) == "sent"


def test_when_the_attempt_cannot_be_reserved_nothing_is_sent_and_it_backs_off(tmp_path, monkeypatch):
    wire = Wire()

    def refuse(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(od, "_write_state", refuse)
    assert send(tmp_path, wire, owed=[APPROVAL]) == "state_unwritable"
    assert send(tmp_path, wire, owed=[APPROVAL], ts=NOW.timestamp() + 700) == "state_unwritable"
    assert wire.sent == []                                     # never publish what cannot be recorded
    send(tmp_path, wire, owed=[APPROVAL], ts=NOW.timestamp() + oa.PERSIST_BACKOFF_SECONDS + 5)
    assert wire.sent == []                                     # it retries, fails to reserve again, still sends nothing


def test_a_send_whose_final_state_write_fails_is_not_repeated_by_another_process(tmp_path, monkeypatch):
    wire, real, writes = Wire(), od._write_state, []

    def flaky(path, state):
        writes.append(1)
        if len(writes) == 2:
            raise OSError("disk full")                          # the reservation worked; the final write fails
        return real(path, state)

    monkeypatch.setattr(od, "_write_state", flaky)
    assert send(tmp_path, wire, owed=[APPROVAL]) == "state_unwritable" and len(wire.sent) == 1
    monkeypatch.setattr(oa, "_persist_blocked_until", 0.0)      # a different process has no in-memory back-off
    assert send(tmp_path, wire, owed=[APPROVAL], ts=NOW.timestamp() + 5) == "cooldown"
    assert len(wire.sent) == 1


def test_a_channel_that_changed_owner_after_the_data_was_gathered_receives_nothing(tmp_path):
    wire = Wire()
    status = oa.notify([APPROVAL], [], OK, state_path=tmp_path / "state.json", channel_path=write_channel(tmp_path, owner="someone-else"),
                       post=wire, clock=lambda: NOW.timestamp(), expected_owner=OWNER)
    assert status == "owner_changed" and wire.sent == []
    ok = oa.notify([APPROVAL], [], OK, state_path=tmp_path / "state.json", channel_path=write_channel(tmp_path),
                   post=wire, clock=lambda: NOW.timestamp(), expected_owner=OWNER)
    assert ok == "sent"


def test_a_second_sender_never_stalls_behind_the_lock(tmp_path):
    import fcntl
    wire = Wire()
    fd = os.open(str(tmp_path / "state.json") + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        assert send(tmp_path, wire, owed=[APPROVAL]) == "busy" and wire.sent == []
    finally:
        os.close(fd)


# ---------------------------------------------------------------- the real transport, against a loopback server

class Recorder(http.server.BaseHTTPRequestHandler):
    seen = []
    redirect = False

    def do_GET(self):
        type(self).seen.append(("GET " + self.path, None, b""))
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        type(self).seen.append((self.path, self.headers.get("Authorization"), body))
        if type(self).redirect and self.path != "/other":
            self.send_response(302)
            self.send_header("Location", "/other")
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    Recorder.seen, Recorder.redirect = [], False
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Recorder)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/lazyusage-abcdef0123456789"
    httpd.shutdown()
    httpd.server_close()


def test_the_real_transport_posts_with_basic_auth_and_ignores_proxy_settings(server, monkeypatch):
    for name in ("http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://127.0.0.1:9")        # a dead proxy: a proxied request would fail
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    channel = {"url": server, "user": "odysseus", "password": SECRET, "owner": OWNER}
    assert oa._post(channel, {"Title": "lazyUsage"}, "hello", 5) == 200
    ((path, auth, body),) = Recorder.seen
    assert path == "/lazyusage-abcdef0123456789" and body == b"hello" and auth.startswith("Basic ")


def test_the_real_transport_refuses_a_redirect_and_never_follows_it(server):
    Recorder.redirect = True
    channel = {"url": server, "user": "odysseus", "password": SECRET, "owner": OWNER}
    import urllib.error
    with pytest.raises(urllib.error.HTTPError) as caught:
        oa._post(channel, {"Title": "lazyUsage"}, "hello", 5)
    assert caught.value.code == 302                                   # the redirect itself is what stopped it
    assert [p for p, _, _ in Recorder.seen] == ["/lazyusage-abcdef0123456789"]      # no GET /other, no second POST


def test_a_redirect_is_a_failed_send_not_a_crash(tmp_path, server, monkeypatch):
    Recorder.redirect = True
    monkeypatch.setattr(oa, "_load_channel", lambda path: ("ok", {"url": server, "user": "u", "password": SECRET, "owner": OWNER}))
    assert oa.notify([APPROVAL], [], OK, state_path=tmp_path / "s.json", channel_path=tmp_path / "x",
                     clock=lambda: NOW.timestamp()) == "send_failed"


# ---------------------------------------------------------------- off the lifecycle tick

def test_only_one_worker_runs_at_a_time_and_a_stale_one_does_not_block_forever():
    release, started = threading.Event(), threading.Event()
    clock = {"now": 0.0}

    def job():
        started.set()
        release.wait(5)

    first = oa.start_worker(job, clock=lambda: clock["now"])
    assert started.wait(2) and first is not None
    assert oa.start_worker(lambda: None, clock=lambda: clock["now"]) is None            # one at a time
    clock["now"] = oa.WORKER_STALE_SECONDS + 1
    second = oa.start_worker(lambda: None, clock=lambda: clock["now"])                  # a stuck one is abandoned
    assert second is not None
    second.join(2)
    release.set()
    first.join(2)


def test_stuck_workers_are_bounded_so_a_dead_network_cannot_pile_up_threads():
    release = threading.Event()
    clock = {"now": 0.0}
    threads = []
    for _ in range(oa.MAX_ABANDONED_WORKERS):
        thread = oa.start_worker(lambda: release.wait(5), clock=lambda: clock["now"])
        assert thread is not None
        threads.append(thread)
        clock["now"] += oa.WORKER_STALE_SECONDS + 1
    # the first is abandoned and the second is stale too: tolerating a third stuck worker would pile up threads
    assert oa.start_worker(lambda: None, clock=lambda: clock["now"]) is None
    release.set()
    for thread in threads:
        thread.join(2)
    assert oa.start_worker(lambda: None, clock=lambda: clock["now"]) is not None      # recovered once they finish


def test_a_failing_worker_job_is_swallowed():
    def boom():
        raise RuntimeError("boom")

    thread = oa.start_worker(boom)
    thread.join(2)
    assert not thread.is_alive()


# ---------------------------------------------------------------- wiring into the lifecycle tick

@pytest.fixture
def db(monkeypatch):
    factory, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", factory)
    monkeypatch.setattr(estate_router, "current_host_id", lambda: "hz2-workstation")
    session = factory()
    yield session
    session.close()
    engine.dispose()
    os.unlink(tmpfile.name)


def add_run(db, run_id, owner, state="budget_exhausted"):
    db.add(LazyUsageRun(id=run_id, state=state, created_by=owner, started_at=utcnow_naive(),
                        finished_at=utcnow_naive() if state != "running" else None,
                        terminal_reason="max_paid_calls", checkpoint={"owed_reviews": []}))
    db.commit()


def test_the_tick_offers_alerts_even_when_no_run_is_active(db, monkeypatch):
    calls = []
    monkeypatch.setattr(rt, "_offer_owner_alerts", lambda session=None: calls.append(1))
    monkeypatch.setattr(rt, "_offer_owner_decisions", lambda session: pytest.fail("no run: decisions are not offered here"))
    assert rt.lifecycle_tick() is None
    assert calls == [1]


def test_with_no_channel_nothing_is_read_and_no_thread_starts(db, monkeypatch):
    monkeypatch.setattr(oa, "CHANNEL_PATH", Path("/nonexistent/none.json"))
    monkeypatch.setattr(oa, "start_worker", lambda *a, **k: pytest.fail("no channel: no worker"))
    monkeypatch.setattr(cdb, "SessionLocal", lambda: pytest.fail("no channel: no database read"))
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda *a, **k: pytest.fail("no provider read"))
    assert rt._offer_owner_alerts() is None


def test_a_broken_alert_setup_never_breaks_the_tick(db, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(oa, "enabled_owner", boom)
    assert rt._offer_owner_alerts() is None
    assert rt.lifecycle_tick() is None


def test_the_worker_reports_only_on_the_channels_owner(db, tmp_path, monkeypatch):
    add_run(db, "run-mine-00001", OWNER)
    add_run(db, "run-other-0002", "someone-else")
    monkeypatch.setattr(oa, "CHANNEL_PATH", write_channel(tmp_path))
    monkeypatch.setattr(estate_router, "provider_allows_dispatch",
                        lambda provider, **kw: {"state": "auth_failed" if provider == "codex" else "ok", "allowed": provider != "codex"})
    seen, captured = {}, {}
    monkeypatch.setattr(rt, "all_owed_reviews", lambda session, owner=None: seen.update(owner=owner) or [])
    monkeypatch.setattr(oa, "notify", lambda owed, runs, providers, **kw: captured.update(runs=runs, providers=providers, **kw))
    rt._offer_owner_alerts().join(5)
    assert seen["owner"] == OWNER and captured["expected_owner"] == OWNER
    assert [r["id"] for r in captured["runs"]] == ["run-mine-00001"]
    assert set(captured["providers"]) == {"claude", "codex", "glm"} and captured["providers"]["codex"]["state"] == "auth_failed"


def test_runs_are_chosen_by_finish_time_so_new_activations_cannot_hide_an_unreported_one(db, tmp_path, monkeypatch):
    now = utcnow_naive()
    db.add(LazyUsageRun(id="run-older-fresh", state="budget_exhausted", created_by=OWNER, started_at=now - timedelta(hours=9),
                        finished_at=now - timedelta(hours=8), created_at=now - timedelta(hours=9),
                        terminal_reason="max_paid_calls", checkpoint={}))
    for i in range(6):                      # six newer activations that finished long ago (outside the window)
        db.add(LazyUsageRun(id=f"run-newer-{i:04d}", state="stopped", created_by=OWNER, started_at=now - timedelta(hours=7 - i),
                            finished_at=now - timedelta(days=5), created_at=now - timedelta(hours=7 - i),
                            terminal_reason="operator", checkpoint={}))
    db.commit()
    monkeypatch.setattr(oa, "CHANNEL_PATH", write_channel(tmp_path))
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda provider, **kw: {"state": "ok", "allowed": True})
    captured = {}
    monkeypatch.setattr(oa, "notify", lambda owed, runs, providers, **kw: captured.update(runs=runs))
    rt._offer_owner_alerts().join(5)
    ids = [r["id"] for r in captured["runs"]]
    assert ids == ["run-newer-0005", "run-older-fresh"]      # the newest (for the heartbeat) and the unreported one


def test_the_heartbeat_can_name_the_newest_run_even_when_it_is_old(db, tmp_path, monkeypatch):
    now = utcnow_naive()
    db.add(LazyUsageRun(id="run-ancient-001", state="completed", created_by=OWNER, started_at=now - timedelta(days=9),
                        finished_at=now - timedelta(days=9), created_at=now - timedelta(days=9),
                        terminal_reason="authorised_work_exhausted", checkpoint={}))
    db.commit()
    monkeypatch.setattr(oa, "CHANNEL_PATH", write_channel(tmp_path))
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda provider, **kw: {"state": "ok", "allowed": True})
    captured = {}
    monkeypatch.setattr(oa, "notify", lambda owed, runs, providers, **kw: captured.update(runs=runs))
    rt._offer_owner_alerts().join(5)
    assert [r["id"] for r in captured["runs"]] == ["run-ancient-001"]
    assert oa.build_events([], captured["runs"], OK, NOW) == []                       # old news raises no alert


def test_many_quick_activations_cannot_hide_an_unreported_run(db, tmp_path, monkeypatch):
    now = utcnow_naive()
    db.add(LazyUsageRun(id="run-unreported1", state="failed", created_by=OWNER, started_at=now - timedelta(hours=10),
                        finished_at=now - timedelta(hours=9), created_at=now - timedelta(hours=10), checkpoint={}))
    for i in range(20):
        db.add(LazyUsageRun(id=f"run-quick-{i:05d}", state="stopped", created_by=OWNER, started_at=now - timedelta(hours=8, minutes=i),
                            finished_at=now - timedelta(hours=7, minutes=i), created_at=now - timedelta(hours=8, minutes=i),
                            terminal_reason="operator_stop", checkpoint={}))
    db.commit()
    monkeypatch.setattr(oa, "CHANNEL_PATH", write_channel(tmp_path))
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda provider, **kw: {"state": "ok", "allowed": True})
    captured = {}
    monkeypatch.setattr(oa, "notify", lambda owed, runs, providers, **kw: captured.update(runs=runs))
    rt._offer_owner_alerts().join(5)
    assert "run-unreported1" in [r["id"] for r in captured["runs"]]


def test_an_unreadable_provider_is_reported_as_unknown_not_dropped(db, tmp_path, monkeypatch):
    def gate(provider, **kw):
        if provider == "glm":
            raise RuntimeError("db unavailable")
        return {"state": "ok", "allowed": True}

    monkeypatch.setattr(oa, "CHANNEL_PATH", write_channel(tmp_path))
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", gate)
    captured = {}
    monkeypatch.setattr(oa, "notify", lambda owed, runs, providers, **kw: captured.update(providers=providers))
    rt._offer_owner_alerts().join(5)
    assert captured["providers"]["glm"] == {"state": "unknown"}


def test_the_worker_closes_its_session_and_a_failure_inside_it_is_contained(db, tmp_path, monkeypatch):
    monkeypatch.setattr(oa, "CHANNEL_PATH", write_channel(tmp_path))
    opened, closed = [], []
    real_factory = cdb.SessionLocal

    def factory():
        session = real_factory()
        opened.append(1)
        original = session.close

        def close():
            closed.append(1)
            original()

        session.close = close
        return session

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cdb, "SessionLocal", factory)
    at_send = {}

    def notify_probe(*args, **kwargs):
        at_send.update(opened=len(opened), closed=len(closed))
        raise RuntimeError("boom")

    monkeypatch.setattr(oa, "notify", notify_probe)
    rt._offer_owner_alerts().join(5)
    assert opened and len(opened) == len(closed)          # every session the worker opened was closed
    assert at_send["opened"] >= 1 and at_send["closed"] == at_send["opened"]      # ... before the network send began


def test_the_test_session_can_never_reach_the_real_channel():
    assert str(oa._HOME).startswith(os.environ["AOTERU_ALERTS_HOME"])
    assert not (oa._HOME / "ntfy_channel.json").exists()


def test_the_alert_sender_tags_every_post_as_the_agent(monkeypatch):
    import urllib.request
    from src import owner_alerts as oa
    seen = {}

    class Reply:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Opener:
        def open(self, request, timeout=None):
            seen["tags"] = request.get_header("Tags")
            return Reply()

    monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **k: Opener())
    assert oa._post({"user": "u", "password": "p", "url": "http://100.75.149.126:8091/x"}, {"Title": "t"}, "body", 5) == 200
    assert seen["tags"] == "robot"


def test_the_alert_sender_strips_caller_supplied_tag_headers(monkeypatch):
    import urllib.request
    from src import owner_alerts as oa
    seen = {}

    class Reply:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Opener:
        def open(self, request, timeout=None):
            seen["headers"] = {k.lower(): v for k, v in request.header_items()}
            return Reply()

    monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **k: Opener())
    oa._post({"user": "u", "password": "p", "url": "http://100.75.149.126:8091/x"}, {"Title": "t", "X-Tags": "evil", "Tags": "evil", "ta": "evil"}, "body", 5)
    assert seen["headers"]["tags"] == "robot" and "x-tags" not in seen["headers"] and "ta" not in seen["headers"]

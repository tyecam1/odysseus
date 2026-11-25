"""The coordinator waits for a provider-stated reset instead of dispatching into a spent window.

Only a live, provider-stated reading can hold work back, only toward more caution, windows are told apart by their
duration, an expired window is ignored, and the 5-hour window is the pacing signal (the weekly pool resets on a
different day for each provider and is only a hard stop)."""
from datetime import datetime, timedelta, timezone

import pytest

from core.database import LazyUsageRun, ParkLease, utcnow_naive
from src import estate_router, lazy_usage_runtime as rt, provider_usage as pu
from tests.test_lazy_usage_runtime import LAB, activate, db, frontier, read_result  # noqa: F401  (fixtures)

NOW = datetime(2026, 11, 25, 18, 0, tzinfo=timezone.utc)
NOW_TS = NOW.timestamp()
FIVE_RESET, WEEK_RESET = "2026-11-25T21:56:35+00:00", "2026-11-27T21:13:49+00:00"
PAST = "2026-11-25T12:00:00+00:00"


def window(pool, used, minutes, reset):
    return {"pool": pool, "used_percent": float(used), "remaining_percent": 100.0 - used, "window_minutes": minutes,
            "resets_at": reset}


def reading(five=13, week=80, reached=None, allowed=True, source=pu.LIVE_SOURCE, confidence="provider-stated",
            windows=None):
    return {"confidence": confidence, "source": source, "rate_limit_reached": reached, "ordinary_usage_allowed": allowed,
            "windows": windows if windows is not None else [window("primary", five, 300, FIVE_RESET),
                                                             window("secondary", week, 10080, WEEK_RESET)]}


def block(r, **kw):
    return pu.dispatch_block("codex", reading=r, now=NOW_TS, **kw)


# ---------------------------------------------------------------- the decision

def test_the_live_numbers_of_today_do_not_block_anything():
    assert block(reading(13, 80)) is None and block(reading(13, 80), write=True) is None


def test_a_high_weekly_percentage_alone_is_not_a_reason_to_wait():
    assert block(reading(5, 97)) is None


@pytest.mark.parametrize("five,blocked", [(97, False), (98, True), (99, True), (100, True)])
def test_the_five_hour_boundary_is_exactly_98(five, blocked):
    result = block(reading(five))
    assert (result is not None) is blocked
    if blocked:
        assert result["why"] == "the 5-hour window is nearly spent" and result["resets_at"] == FIVE_RESET
        assert result["used_percent"] == float(five)


@pytest.mark.parametrize("five,write,blocked", [(84, True, False), (85, True, True), (85, False, False), (97, False, False)])
def test_a_write_waits_earlier_than_a_read_with_the_boundary_at_85(five, write, blocked):
    result = block(reading(five), write=write)
    assert (result is not None) is blocked
    if blocked:
        assert result["why"] == "the 5-hour window is too full to start a write" and result["resets_at"] == FIVE_RESET


@pytest.mark.parametrize("week,blocked", [(97, False), (98, True), (100, True)])
def test_a_spent_weekly_window_is_a_hard_stop_with_its_own_reset(week, blocked):
    result = block(reading(5, week))
    assert (result is not None) is blocked
    if blocked:
        assert result["why"] == "the weekly window is nearly spent" and result["resets_at"] == WEEK_RESET


@pytest.mark.parametrize("kw,why", [({"reached": "rate_limit_reached"}, "usage limit reached"),
                                    ({"allowed": False}, "does not allow ordinary usage")])
def test_a_provider_refusal_is_respected_whatever_the_percentages_say(kw, why):
    result = block(reading(1, 1, **kw))
    assert why in result["why"] and result["resets_at"] == FIVE_RESET        # the earliest provider-stated reset


@pytest.mark.parametrize("kw", [{"reached": "rate_limit_reached"}, {"allowed": False}])
def test_a_refusal_survives_a_response_with_no_numeric_window(kw):
    result = block(reading(windows=[], **kw))
    assert result is not None and result["resets_at"] is None


def test_a_response_with_no_window_and_no_refusal_says_nothing():
    assert block(reading(windows=[])) is None


def test_the_response_parser_keeps_an_explicit_refusal_without_windows():
    snap = {"limitId": "codex", "planType": "plus", "rateLimitReachedType": "rate_limit_reached", "primary": None,
            "secondary": None}
    kept = pu._live_reading({"rateLimits": snap, "ordinaryUsageAllowed": False}, now=NOW_TS)
    assert kept["windows"] == [] and kept["remaining"] == "unknown" and kept["rate_limit_reached"] == "rate_limit_reached"
    assert pu._live_reading({"rateLimits": {**snap, "rateLimitReachedType": None}, "ordinaryUsageAllowed": True}, now=NOW_TS) is None


def test_unknown_unstated_or_non_live_readings_never_block():
    assert block(reading(100, confidence="none")) is None
    assert block({"confidence": "none", "windows": []}) is None
    assert block(reading(100, source="codex-cli-session-rollouts")) is None       # a rollout can be two days old
    assert block(reading(100, source=None)) is None


def test_ordinary_usage_unknown_is_not_a_refusal():
    assert block(reading(5, 5, allowed=None)) is None


@pytest.mark.parametrize("provider", ["claude", "glm", "glm-flash", "local", None])
def test_other_providers_are_not_gated_by_the_codex_window(provider):
    assert pu.dispatch_block(provider, reading=reading(100), now=NOW_TS) is None


# ---------------------------------------------------------------- expiry, identity by duration

def test_a_window_whose_reset_has_passed_is_ignored():
    assert block(reading(windows=[window("primary", 99, 300, PAST), window("secondary", 80, 10080, WEEK_RESET)])) is None


def test_an_old_refusal_does_not_outlive_every_window_it_came_with():
    old = reading(1, 1, reached="rate_limit_reached", allowed=False,
                  windows=[window("primary", 1, 300, PAST), window("secondary", 1, 10080, PAST)])
    assert block(old) is None


def test_a_refusal_with_a_current_window_still_blocks_when_the_other_expired():
    mixed = reading(reached="rate_limit_reached", windows=[window("primary", 1, 300, PAST),
                                                           window("secondary", 1, 10080, WEEK_RESET)])
    assert block(mixed)["resets_at"] == WEEK_RESET


def test_an_expired_five_hour_window_does_not_hide_a_current_weekly_hard_stop():
    mixed = reading(windows=[window("primary", 99, 300, PAST), window("secondary", 99, 10080, WEEK_RESET)])
    assert block(mixed)["why"] == "the weekly window is nearly spent"


def test_the_window_order_and_labels_do_not_decide_which_is_which():
    reversed_order = reading(windows=[window("secondary", 99, 10080, WEEK_RESET), window("primary", 5, 300, FIVE_RESET)])
    assert block(reversed_order)["why"] == "the weekly window is nearly spent"
    swapped_labels = reading(windows=[window("primary", 90, 10080, WEEK_RESET), window("secondary", 90, 300, FIVE_RESET)])
    assert block(swapped_labels) is None                                       # 90% of a week is not a 5-hour problem
    assert block(swapped_labels, write=True)["why"] == "the 5-hour window is too full to start a write"


def test_a_missing_five_hour_window_leaves_only_the_weekly_hard_stop():
    assert block(reading(windows=[window("secondary", 80, 10080, WEEK_RESET)]), write=True) is None
    assert block(reading(windows=[window("secondary", 99, 10080, WEEK_RESET)])) is not None


@pytest.mark.parametrize("minutes", [None, 0, 60, 600, 9000])
def test_a_window_of_the_wrong_or_unknown_duration_is_not_the_pacing_window(minutes):
    odd = reading(windows=[window("primary", 99, minutes, FIVE_RESET)])
    assert block(odd) is None and block(odd, write=True) is None


# ---------------------------------------------------------------- the cache, not the subprocess

def test_the_gate_reads_the_cache_and_never_spawns_anything(monkeypatch):
    monkeypatch.setattr(pu, "_live_read", lambda *a, **k: pytest.fail("the gate must never spawn the CLI"))
    monkeypatch.setattr(pu, "codex_windows", lambda *a, **k: pytest.fail("a rollout must never gate"))
    monkeypatch.setattr(pu, "_live_cache", {"entry": (1000.0, {**reading(99), "observed_at": "x"})})
    monkeypatch.setattr(pu.time, "monotonic", lambda: 1100.0)
    assert pu.dispatch_block("codex", now=NOW_TS)["why"] == "the 5-hour window is nearly spent"


def test_a_cache_entry_older_than_twice_the_ttl_is_unknown_not_a_block(monkeypatch):
    monkeypatch.setattr(pu, "_live_cache", {"entry": (1000.0, reading(99))})
    assert pu.codex_windows_cached(clock=lambda: 1000.0 + pu.LIVE_TTL_SECONDS * 2 - 1)["confidence"] == "provider-stated"
    stale = pu.codex_windows_cached(clock=lambda: 1000.0 + pu.LIVE_TTL_SECONDS * 2 + 1)
    assert stale["confidence"] == "none" and "no recent" in stale["reason"]
    assert pu.codex_windows_cached(clock=lambda: 999.0)["confidence"] == "none"           # a negative age is a miss


def test_in_the_test_session_the_default_reading_is_unknown_and_blocks_nothing():
    assert pu.dispatch_block("codex") is None


# ---------------------------------------------------------------- the runtime waits, then resumes

def codex_route(monkeypatch):
    """The fixture's route is the paid one (executor none); make the paid provider Codex."""
    monkeypatch.setattr(estate_router, "_resolve_paid_provider", lambda *a, **k: {"provider": "codex"})


SPENT = {"provider": "codex", "why": "the 5-hour window is nearly spent", "resets_at": FIVE_RESET, "used_percent": 99.0}


def test_a_spent_window_parks_the_run_without_dispatching_and_it_resumes_when_the_window_refills(db, frontier, monkeypatch):  # noqa: F811
    add, _ = frontier
    add("a")
    codex_route(monkeypatch)
    run_id = activate(db)
    state = {"block": SPENT}
    dispatched = []
    monkeypatch.setattr(rt, "_usage_block", lambda provider, write: state["block"])
    monkeypatch.setattr(estate_router, "run_task", lambda task: dispatched.append(task) or read_result())
    view = rt.advance(db, run_id)
    cp = view["checkpoint"]
    assert view["state"] == "paused" and "usage window" in cp["pause_reason"]
    assert cp["usage_block"]["resets_at"] == FIVE_RESET and cp["next_action"] == "event_recheck"
    assert cp["in_flight_execution_id"] is None and db.query(ParkLease).count() == 0
    wait = datetime.fromisoformat(cp["recheck_at"]) - utcnow_naive()
    assert timedelta(seconds=rt.USAGE_RECHECK_SECONDS - 60) < wait <= timedelta(seconds=rt.USAGE_RECHECK_SECONDS)
    assert dispatched == [] and view["counters"]["paid_calls"] == 0          # nothing was sent to the provider

    state["block"] = None                                                    # the window refilled
    row = db.get(LazyUsageRun, run_id)
    row.checkpoint = {**row.checkpoint, "recheck_at": "2000-01-01T00:00:00"}   # the automatic recheck falls due
    db.commit()
    view = rt.advance(db, run_id)
    assert dispatched and not view["checkpoint"].get("usage_block")


def test_the_gate_is_really_consulted_with_the_provider_and_the_write_flag(db, frontier, monkeypatch):  # noqa: F811
    add, _ = frontier
    add("a")
    codex_route(monkeypatch)
    run_id = activate(db)
    seen = []
    monkeypatch.setattr(rt, "_usage_block", lambda provider, write: seen.append((provider, write)))
    monkeypatch.setattr(estate_router, "run_task", lambda task: read_result())
    rt.advance(db, run_id)
    assert seen == [("codex", False)]


def test_a_reading_that_cannot_be_taken_never_stops_a_dispatch(db, frontier, monkeypatch):  # noqa: F811
    add, _ = frontier
    add("a")
    codex_route(monkeypatch)
    run_id = activate(db)
    dispatched, called = [], []

    def explode(provider, write=False, **kw):
        called.append(provider)
        raise RuntimeError("usage read broke")

    monkeypatch.setattr(pu, "dispatch_block", explode)
    monkeypatch.setattr(estate_router, "run_task", lambda task: dispatched.append(task) or read_result())
    rt.advance(db, run_id)
    assert called == ["codex"] and dispatched                                # the gate ran, failed, and did not block


def test_an_operator_pause_made_during_the_park_is_never_turned_into_a_timed_recheck(db, frontier, monkeypatch):  # noqa: F811
    add, _ = frontier
    add("a")
    codex_route(monkeypatch)
    run_id = activate(db)
    real_release = rt._release_owned_lease

    def release_then_operator_pauses(session, run):
        real_release(session, run)
        rt.pause_run(session, run_id, "operator")                              # the race window of the review

    monkeypatch.setattr(rt, "_release_owned_lease", release_then_operator_pauses)
    monkeypatch.setattr(rt, "_usage_block", lambda provider, write: SPENT)
    monkeypatch.setattr(estate_router, "run_task", lambda task: pytest.fail("nothing may be dispatched"))
    view = rt.advance(db, run_id)
    assert view["state"] == "paused" and view["checkpoint"]["pause_reason"] == "operator"
    assert view["checkpoint"]["recheck_at"] is None and view["checkpoint"]["next_action"] == "operator_resume"


def test_park_never_overwrites_a_pause_that_already_exists(db):
    run_id = activate(db)
    rt.pause_run(db, run_id, "operator")
    row = db.get(LazyUsageRun, run_id)
    view = rt._park(db, row, "provider usage window: x", recheck_seconds=900)
    assert view["state"] == "paused" and view["checkpoint"]["pause_reason"] == "operator" and view["checkpoint"]["recheck_at"] is None


def test_the_tick_refreshes_the_usage_reading_outside_the_run_only_when_a_run_exists(db, frontier, monkeypatch):  # noqa: F811
    refreshed = []
    monkeypatch.setattr(pu, "refresh_usage", lambda: refreshed.append(1))
    assert rt.lifecycle_tick() is None and refreshed == []                   # idle: no probe, no cost
    add, _ = frontier
    add("a")
    activate(db)
    monkeypatch.setattr(estate_router, "run_task", lambda task: read_result())
    rt.lifecycle_tick()
    assert refreshed == [1]


def test_a_broken_refresh_never_breaks_the_tick(db, frontier, monkeypatch):  # noqa: F811
    def explode():
        raise RuntimeError("boom")

    monkeypatch.setattr(pu, "refresh_usage", explode)
    add, _ = frontier
    add("a")
    activate(db)
    monkeypatch.setattr(estate_router, "run_task", lambda task: read_result())
    assert rt.lifecycle_tick()["state"] in {"running", "paused"}


def test_two_windows_of_the_pacing_class_are_both_judged_and_the_fullest_decides():
    two = reading(windows=[window("primary", 10, 300, FIVE_RESET), window("secondary", 99, 300, FIVE_RESET)])
    result = block(two)
    assert result["why"] == "the 5-hour window is nearly spent" and result["used_percent"] == 99.0
    assert block(reading(windows=[window("a", 99, 300, FIVE_RESET), window("b", 10, 300, FIVE_RESET)])) is not None


def test_an_automatic_pause_still_renews_its_own_deadline(db):
    run_id = activate(db)
    row = db.get(LazyUsageRun, run_id)
    row.state = "paused"
    row.checkpoint = {**row.checkpoint, "pause_reason": "existing execution child usage remains unknown; dispatch fenced",
                      "recheck_at": "2000-01-01T00:00:00", "next_action": "event_recheck"}
    db.commit()
    view = rt._park(db, db.get(LazyUsageRun, run_id), "existing execution child usage remains unknown; dispatch fenced")
    renewed = datetime.fromisoformat(view["checkpoint"]["recheck_at"])
    assert renewed > utcnow_naive() and view["state"] == "paused"                 # the elapsed deadline moved forward


def test_a_stale_checkpoint_is_never_flushed_over_an_operator_pause_made_in_another_session(db):
    import core.database as cdb
    run_id = activate(db)
    row = db.get(LazyUsageRun, run_id)
    row.checkpoint = {**row.checkpoint, "usage_block": SPENT, "recheck_at": "2000-01-01T00:00:00", "phase": "idle"}   # dirty
    other = cdb.SessionLocal()
    try:
        rt.pause_run(other, run_id, "operator")                                    # committed by another session
    finally:
        other.close()
    view = rt._park(db, row, "provider usage window: x", recheck_seconds=900)
    cp = view["checkpoint"]
    assert view["state"] == "paused" and cp["pause_reason"] == "operator" and cp["recheck_at"] is None
    assert "usage_block" not in cp or cp["usage_block"] is None
    assert cp["next_action"] == "operator_resume"


@pytest.mark.parametrize("state", ["stop_requested", "stopping", "stopped", "budget_exhausted", "completed", "failed"])
def test_an_automatic_park_never_revives_a_run_the_owner_stopped_or_that_already_ended(db, state):
    run_id = activate(db)
    row = db.get(LazyUsageRun, run_id)
    row.state = state
    db.commit()
    view = rt._park(db, db.get(LazyUsageRun, run_id), "provider usage window: x", recheck_seconds=900)
    assert view["state"] == state and view["state"] != "paused" and view["state"] != "running"

"""Governance tests for the provider-agnostic music.* contract (src/music_capability.py), driven through the simulated provider."""

import json

import pytest

from src.music_capability import (
    ALL_ACTIONS, READ_ACTIONS, WRITE_ACTIONS, Device, Item, MusicController, SimulatedMusicProvider,
)


def _ctl(**kwargs):
    provider = SimulatedMusicProvider(**kwargs)
    return MusicController(provider), provider


def _do(controller, action, rid, **kwargs):
    kwargs.setdefault("explicit_command", True)
    return controller.handle(action, request_id=rid, **kwargs)


# --- read-only lookups never reach a write ---------------------------------------------------------------------------------


@pytest.mark.parametrize("action,kwargs", [("search", {"query": "blue"}), ("devices", {}), ("now_playing", {})])
def test_reads_never_call_a_provider_write_even_with_a_command_flag(action, kwargs):
    controller, provider = _ctl()
    result = controller.handle(action, request_id="r", explicit_command=True, **kwargs)
    assert result.ok or result.status == "not_found"
    assert provider.writes() == []


def test_the_action_sets_are_disjoint_and_complete():
    assert READ_ACTIONS.isdisjoint(WRITE_ACTIONS) and ALL_ACTIONS == READ_ACTIONS | WRITE_ACTIONS


def test_whats_playing_is_accurate_and_marked_as_simulation():
    controller, provider = _ctl()
    assert controller.handle("now_playing", request_id="a").message == "[simulation] Nothing is playing."
    _do(controller, "play", "p1", query="Kind of Blue")
    message = controller.handle("now_playing", request_id="b").message
    assert "Playing: Kind of Blue by Miles Davis" in message and message.startswith("[simulation]")


# --- writes need an explicit, non-guest command ----------------------------------------------------------------------------


@pytest.mark.parametrize("action", sorted(WRITE_ACTIONS))
def test_a_write_without_an_explicit_command_is_refused_and_does_nothing(action):
    controller, provider = _ctl()
    result = controller.handle(action, request_id="w", query="Kind of Blue", volume=10)
    assert result.status == "refused" and provider.writes() == []


@pytest.mark.parametrize("action", sorted(WRITE_ACTIONS))
def test_a_guest_can_never_write(action):
    controller, provider = _ctl()
    result = controller.handle(action, request_id="g", explicit_command=True, guest=True, query="Kind of Blue", volume=10)
    assert result.status == "refused" and "Guests" in result.message and provider.writes() == []


def test_a_write_without_a_request_id_is_refused():
    controller, provider = _ctl()
    assert controller.handle("pause", request_id="", explicit_command=True).status == "refused"
    assert provider.writes() == []


def test_an_unknown_action_is_refused():
    controller, _ = _ctl()
    assert controller.handle("purchase", request_id="x", explicit_command=True).status == "refused"


# --- exactly one action, confirmed state ------------------------------------------------------------------------------------


def test_play_issues_exactly_one_write_and_confirms_the_state():
    controller, provider = _ctl()
    result = _do(controller, "play", "p", query="Kind of Blue", device="kitchen")
    assert result.status == "done" and provider.writes() == ["play"] and "Kitchen speaker" in result.message


def test_a_repeated_request_id_does_not_repeat_the_write():
    controller, provider = _ctl()
    first = _do(controller, "play", "same", query="Kind of Blue")
    second = _do(controller, "play", "same", query="Kind of Blue")
    assert second is first and provider.writes() == ["play"]


def test_pause_resume_next_queue_work_and_report_truthfully():
    controller, provider = _ctl()
    _do(controller, "play", "1", query="Kind of Blue")
    assert _do(controller, "pause", "2").status == "done" and provider.state.playing is False
    assert _do(controller, "resume", "3").status == "done" and provider.state.playing is True
    assert _do(controller, "next", "4").status == "done" and provider.state.item.title == "Pastel Blues"
    assert _do(controller, "queue", "5", query="Waltz for Debby").status == "done" and provider.queued == ["spotify:track:sim0003"]


def test_an_unconfirmable_state_is_reported_as_unconfirmed_not_done():
    controller, provider = _ctl()
    real = provider.play
    provider.play = lambda uri, device_id: real(uri, device_id) or setattr(provider, "state", type(provider.state)(None, False, None))
    result = _do(controller, "play", "u", query="Kind of Blue")
    assert result.status == "done_unconfirmed" and "could not confirm" in result.message


# --- devices and ambiguity are clarified, never guessed ----------------------------------------------------------------------


def _two_devices():
    return [Device("d1", "Kitchen speaker", False), Device("d2", "Kitchen display", False), Device("d3", "Lounge", False)]


def test_several_devices_and_none_named_asks_which():
    controller, provider = _ctl(devices=_two_devices())
    result = _do(controller, "pause", "d")
    assert result.status == "clarify" and result.data["options"] and provider.writes() == []


def test_an_ambiguous_device_name_asks_and_a_unique_prefix_resolves():
    controller, provider = _ctl(devices=_two_devices())
    assert _do(controller, "pause", "a", device="kitchen").status == "clarify"
    assert _do(controller, "pause", "b", device="lounge").status == "done" and provider.writes() == ["pause"]


def test_an_unknown_device_asks_and_no_device_at_all_is_a_typed_error():
    controller, provider = _ctl(devices=_two_devices())
    assert _do(controller, "pause", "c", device="garage").status == "clarify"
    empty, p2 = _ctl(devices=[])
    result = _do(empty, "pause", "e")
    assert result.status == "error" and result.trace["error"] == "no_device" and p2.writes() == []


def test_an_ambiguous_track_asks_with_bounded_options_and_a_missing_one_is_not_found():
    items = [Item(f"spotify:track:t{n:04d}", f"Blue Number {n}", "Band") for n in range(8)]
    controller, provider = _ctl(catalogue=items)
    result = _do(controller, "play", "t", query="blue")
    assert result.status == "clarify" and len(result.data["options"]) == 3 and provider.writes() == []
    missing = _do(controller, "play", "m", query="zzz nothing")
    assert missing.status == "not_found" and missing.suggestion and provider.writes() == []


def test_a_direct_uri_plays_and_a_malformed_one_is_refused():
    controller, provider = _ctl()
    assert _do(controller, "play", "u1", uri="spotify:track:abc123").status in ("done", "done_unconfirmed")
    assert _do(controller, "play", "u2", uri="javascript:alert(1)").status == "refused"
    assert provider.writes() == ["play"]


# --- volume is bounded -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", [-1, 101, 81, 3.5, "loud", None, True])
def test_unsafe_or_malformed_volume_is_refused_not_clamped(value):
    controller, provider = _ctl()
    assert _do(controller, "volume", "v", volume=value).status == "refused" and provider.writes() == []


def test_a_safe_volume_is_applied():
    controller, provider = _ctl()
    assert _do(controller, "volume", "v", volume=35).status == "done" and provider.volume["dev-kitchen"] == 35


# --- provider failures are truthful ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("code,needle", [("auth", "reconnected"), ("forbidden", "not allowed"), ("rate_limited", "slow down"),
                                         ("offline", "can't reach")])
def test_provider_failures_become_typed_results_with_an_honest_suggestion(code, needle):
    controller, provider = _ctl()
    provider.fail_next(code, retry_after=7 if code == "rate_limited" else None)
    result = _do(controller, "pause", f"f-{code}")
    assert result.status == "error" and needle in result.message and result.suggestion and result.trace["error"] == code
    if code == "rate_limited":
        assert result.data["retry_after"] == 7


def test_a_failed_write_is_remembered_so_a_retry_with_the_same_id_does_not_double_act():
    controller, provider = _ctl()
    provider.fail_next("offline")
    _do(controller, "pause", "same")
    assert _do(controller, "pause", "same").status == "error" and provider.writes() == []


# --- traces carry no secrets and no history -----------------------------------------------------------------------------------


def test_the_trace_names_the_action_provider_and_outcome_only():
    controller, _ = _ctl()
    result = _do(controller, "play", "tr", query="Kind of Blue")
    assert set(result.trace) == {"action", "provider", "request_id", "outcome"}
    blob = json.dumps(result.trace)
    assert "Kind of Blue" not in blob and "token" not in blob.lower()


def test_every_simulated_result_says_so():
    controller, _ = _ctl()
    for result in (controller.handle("devices", request_id="a"), _do(controller, "play", "b", query="Kind of Blue"),
                   _do(controller, "pause", "c", device="nowhere")):
        assert result.simulated and result.message.startswith("[simulation]")

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


@pytest.mark.parametrize("value", [-1, 101, 81, 3.5, 3.0, 35.0, "loud", None, True, float("nan"), float("inf"), float("-inf")])
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


def test_a_provider_that_raises_anything_gives_a_typed_result_and_is_not_retried():
    controller, provider = _ctl()
    provider.pause = lambda device_id: (_ for _ in ()).throw(RuntimeError("binding bug"))
    first = _do(controller, "pause", "boom")
    assert first.status == "error" and first.trace["error"] == "unexpected"
    provider.pause = lambda device_id: provider.calls.append(("pause", (device_id,)))
    assert _do(controller, "pause", "boom") is first and provider.writes() == []
    provider.devices = lambda: (_ for _ in ()).throw(KeyError("shape changed"))
    assert controller.handle("devices", request_id="r").status == "error"


def test_an_old_request_id_is_never_forgotten_so_it_can_never_write_twice():
    controller, provider = _ctl()
    _do(controller, "play", "first", query="Kind of Blue")
    for number in range(600):
        _do(controller, "pause", f"fill-{number}")
    _do(controller, "play", "first", query="Kind of Blue")
    assert provider.writes().count("play") == 1


def test_the_remembered_set_fails_closed_when_full(monkeypatch):
    import src.music_capability as module

    monkeypatch.setattr(module, "_REMEMBERED_REQUESTS", 3)
    controller, provider = _ctl()
    for number in range(3):
        assert _do(controller, "pause", f"a{number}").status == "done"
    refused = _do(controller, "pause", "overflow")
    assert refused.status == "refused" and provider.writes() == ["pause"] * 3


def test_a_guest_replaying_the_owners_request_id_learns_nothing():
    controller, provider = _ctl()
    _do(controller, "play", "owner-1", query="Kind of Blue")
    replay = controller.handle("play", request_id="owner-1", explicit_command=True, guest=True, query="Kind of Blue")
    assert replay.status == "refused" and not replay.data and provider.writes() == ["play"]
    assert controller.handle("play", request_id="owner-1", explicit_command=False, query="Kind of Blue").status == "refused"


def test_reusing_a_request_id_for_a_different_command_is_refused():
    controller, provider = _ctl()
    _do(controller, "play", "id", query="Kind of Blue")
    assert _do(controller, "play", "id", query="Pastel Blues").status == "refused"
    assert _do(controller, "volume", "id", volume=10).status == "refused" and provider.writes() == ["play"]


@pytest.mark.parametrize("request_id", [None, 5, ["x"], {}])
def test_odd_request_ids_and_inputs_never_raise(request_id):
    controller, provider = _ctl()
    assert controller.handle("pause", request_id=request_id, explicit_command=True).status == "refused"
    assert controller.handle(None, request_id="x").status == "refused"
    assert controller.handle("search", request_id="s", query=None).status == "refused"


def test_concurrent_calls_with_one_request_id_reach_the_provider_exactly_once():
    import threading

    controller, provider = _ctl()
    barrier = threading.Barrier(8)
    real = provider.pause

    def slow_pause(device_id):
        import time
        time.sleep(0.05)
        real(device_id)

    provider.pause = slow_pause
    results = []

    def go():
        barrier.wait()
        results.append(controller.handle("pause", request_id="race", explicit_command=True))

    threads = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert provider.writes().count("pause") == 1 and len(results) == 8 and all(r is results[0] for r in results)


@pytest.mark.parametrize("explicit,guest", [("yes", False), (1, False), ([], False), (True, None), (True, 0), (True, "no"), (True, "")])
def test_authority_needs_exact_booleans(explicit, guest):
    controller, provider = _ctl()
    result = controller.handle("pause", request_id="x", explicit_command=explicit, guest=guest)
    assert result.status == "refused" and provider.writes() == []


def test_unprintable_inputs_never_raise():
    class Bad:
        def __str__(self):
            raise RuntimeError("no")

        def __repr__(self):
            raise RuntimeError("no")

    controller, provider = _ctl()
    for kwargs in ({"query": Bad()}, {"device": Bad()}, {"uri": Bad()}, {"volume": Bad()}, {"kind": Bad()}):
        assert controller.handle("play", request_id="b" + str(len(provider.calls)), explicit_command=True, **kwargs).status in (
            "refused", "not_found", "clarify", "error", "done", "done_unconfirmed")
    assert controller.handle("volume", request_id="bv", explicit_command=True, volume=Bad()).status == "refused"
    assert controller.handle("search", request_id="s", query=Bad()).status in ("refused", "not_found", "done")


@pytest.mark.parametrize("uri", ["spotify:track:abc\n", "javascript:alert:x", "spotify:track:abc def", "spotify:evil:abc123",
                                 "http:track:abc", " spotify:track:abc", "spotify:track:" + "a" * 65])
def test_only_exact_well_formed_uris_reach_the_provider(uri):
    controller, provider = _ctl()
    assert _do(controller, "play", "u", uri=uri).status == "refused" and provider.writes() == []


@pytest.mark.parametrize("rid", ["Bearer token-secret", "a b", "x" * 65, "i\nd", "tok=abc", "é"])
def test_unsafe_request_ids_are_refused_and_never_appear_in_a_trace(rid):
    controller, provider = _ctl()
    result = controller.handle("pause", request_id=rid, explicit_command=True)
    assert result.status == "refused" and provider.writes() == [] and rid not in json.dumps(result.trace)
    assert controller.handle("devices", request_id=rid).trace["request_id"] == ""


def test_a_provider_calling_back_into_the_controller_with_the_same_id_cannot_cause_a_second_write():
    controller, provider = _ctl()
    real = provider.pause
    inner = []

    def reentrant(device_id):
        inner.append(controller.handle("pause", request_id="same", explicit_command=True))
        real(device_id)

    provider.pause = reentrant
    outer = controller.handle("pause", request_id="same", explicit_command=True)
    assert outer.status == "done" and provider.writes().count("pause") == 1
    assert inner and inner[0].status == "refused" and "already running" in inner[0].message


def test_a_slow_provider_does_not_block_an_unrelated_request_and_a_cross_thread_write_cannot_deadlock():
    import threading
    import time

    controller, provider = _ctl()
    release = threading.Event()
    real = provider.pause

    def slow(device_id):
        release.wait(5)
        real(device_id)

    provider.pause = slow
    done = {}
    t1 = threading.Thread(target=lambda: done.setdefault("slow", controller.handle("pause", request_id="slow-1", explicit_command=True)))
    t1.start()
    time.sleep(0.1)
    started = time.monotonic()
    other = controller.handle("volume", request_id="other-1", explicit_command=True, volume=10)   # unrelated id while the slow call runs
    assert other.status == "done" and time.monotonic() - started < 1.0
    # a provider that waits for ANOTHER thread to write through the controller does not deadlock either
    helper = threading.Thread(target=lambda: done.setdefault("helper", controller.handle("resume", request_id="helper-1", explicit_command=True)))
    helper.start(); helper.join(2)
    assert not helper.is_alive() and done["helper"].status in ("done", "done_unconfirmed")
    release.set(); t1.join(5)
    assert done["slow"].status in ("done", "done_unconfirmed") and provider.writes().count("pause") == 1


def test_a_duplicate_on_another_thread_waits_for_the_first_answer_and_never_writes_twice():
    import threading
    import time

    controller, provider = _ctl()
    release = threading.Event()
    real = provider.pause
    provider.pause = lambda device_id: (release.wait(5), real(device_id))
    results = []
    first = threading.Thread(target=lambda: results.append(controller.handle("pause", request_id="dup", explicit_command=True)))
    first.start(); time.sleep(0.1)
    second = threading.Thread(target=lambda: results.append(controller.handle("pause", request_id="dup", explicit_command=True)))
    second.start(); time.sleep(0.1)
    release.set(); first.join(5); second.join(5)
    assert len(results) == 2 and results[0] is results[1] and provider.writes().count("pause") == 1


def test_a_keyboard_interrupt_inside_the_provider_still_burns_the_request_id():
    controller, provider = _ctl()

    def interrupted(device_id):
        provider.calls.append(("pause", (device_id,)))   # the side effect happened ...
        raise KeyboardInterrupt()                         # ... and then the call was interrupted

    provider.pause = interrupted
    with pytest.raises(KeyboardInterrupt):
        controller.handle("pause", request_id="kbd", explicit_command=True)
    again = controller.handle("pause", request_id="kbd", explicit_command=True)
    assert again.status == "error" and provider.writes().count("pause") == 1


def test_a_waiting_duplicate_gets_the_first_calls_non_success_answer_too():
    import threading
    import time

    controller, provider = _ctl(devices=[Device("d1", "Kitchen speaker", False), Device("d2", "Kitchen display", False)])
    release = threading.Event()
    real = provider.devices
    provider.devices = lambda: (release.wait(5), real())[1]
    results = []
    first = threading.Thread(target=lambda: results.append(controller.handle("pause", request_id="amb", explicit_command=True, device="kitchen")))
    first.start(); time.sleep(0.1)
    second = threading.Thread(target=lambda: results.append(controller.handle("pause", request_id="amb", explicit_command=True, device="kitchen")))
    second.start(); time.sleep(0.1)
    release.set(); first.join(5); second.join(5)
    assert len(results) == 2 and all(r.status == "clarify" for r in results) and provider.writes() == []


def test_hung_providers_stop_consuming_capacity_but_their_ids_stay_burnt(monkeypatch):
    import threading
    import time

    import src.music_capability as module

    monkeypatch.setattr(module, "_REMEMBERED_REQUESTS", 3)
    controller, provider = _ctl()
    controller._hung_after = 0.05
    controller._wait_seconds = 0.2
    gate = threading.Event()
    real = provider.pause
    provider.pause = lambda device_id: (gate.wait(10), real(device_id))
    threads = [threading.Thread(target=lambda n=n: controller.handle("pause", request_id=f"hang{n}", explicit_command=True), daemon=True)
               for n in range(3)]
    [t.start() for t in threads]
    time.sleep(0.3)                      # all three are hung and past _hung_after
    provider.pause = real
    fresh = controller.handle("volume", request_id="fresh", explicit_command=True, volume=10)
    assert fresh.status == "done"        # capacity was not exhausted by the hung ones
    stuck = controller.handle("pause", request_id="hang0", explicit_command=True)
    assert stuck.status == "refused" and "still running" in stuck.message   # and a retry of a hung id never writes again
    gate.set(); [t.join(5) for t in threads]


def test_a_device_can_be_named_by_exact_id_and_a_vanished_id_is_a_clarification_not_a_neighbour():
    controller, provider = _ctl(devices=[Device("d1", "Laptop", True, 40), Device("d2", "Laptop TV", False, 10)])
    ok = _do(controller, "pause", "id1", device="id:d1")
    assert ok.ok and "Laptop." in ok.message and "d1" in str(provider.calls)
    provider._devices = [Device("d2", "Laptop TV", False, 10)]               # d1 disappears between reads
    gone = _do(controller, "pause", "id2", device="id:d1")
    assert gone.status == "clarify" and "no longer available" in gone.message
    assert not any(name == "pause" and "d2" in args for name, args in provider.calls)       # never the 'Laptop TV' prefix neighbour

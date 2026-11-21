"""Live-unit tests must never signal a real worker's units.

2026-11-21: `test_estate_stage6_integration_live.py` cleaned up by SIGKILLing EVERY `aoteru-*` user unit
on the host. Run on the lab (the execution host) while a real /lazyUsage write was in flight, it killed
the live `gpt-6.2-sol` writer; the backend correctly recorded the execution `interrupted` and protected the
partial work, but the delivery was lost. The suite now skips live-unit tests when a worker unit is active
and, otherwise, kills only units that appeared during the test.
"""
from tests.helpers import live_units

LISTING = (
    "aoteru-run-aaaa.service loaded active   running Aoteru writer\n"
    "● aoteru-run-bbbb.service loaded failed  failed  Aoteru writer\n"
    "aoteru-run-cccc.service loaded inactive dead    Aoteru writer\n"
    "aoteru-prepare-dddd.service loaded activating start Aoteru prepare\n"
)


class Done:
    returncode = 0
    stderr = ""

    def __init__(self, stdout=""):
        self.stdout = stdout


def fake_systemctl(listing, calls):
    def run(argv, **kwargs):
        calls.append(argv)
        return Done(listing if "list-units" in argv else "")
    return run


def test_busy_units_are_only_the_ones_actually_running_or_starting():
    run = fake_systemctl(LISTING, [])
    assert live_units.busy_units(run) == {"aoteru-run-aaaa.service", "aoteru-prepare-dddd.service"}


def test_active_units_lists_every_loaded_unit_including_stopped_ones():
    run = fake_systemctl(LISTING, [])
    assert live_units.active_units(run) == {
        "aoteru-run-aaaa.service", "aoteru-run-bbbb.service", "aoteru-run-cccc.service", "aoteru-prepare-dddd.service"}


def test_cleanup_never_kills_a_unit_that_existed_before_the_test():
    calls = []
    before = {"aoteru-run-aaaa.service", "aoteru-run-bbbb.service"}          # a real worker's units
    owned = {"cccc", "dddd"}                                                   # ids the test itself created
    live_units.stop_units_started_since(before, owned, fake_systemctl(LISTING, calls))
    killed = sorted(argv[-1] for argv in calls if "kill" in argv)
    assert killed == ["aoteru-prepare-dddd.service", "aoteru-run-cccc.service"]


def test_a_real_worker_that_starts_mid_test_is_never_killed_even_though_it_is_new():
    """Review (GLM-5.3): snapshot-diff alone kills a real writer that starts during the test."""
    calls = []
    listing = LISTING + "aoteru-run-eeee.service loaded active running A real paid writer started mid-test\n"
    live_units.stop_units_started_since(set(), {"cccc", "dddd"}, fake_systemctl(listing, calls))
    killed = {argv[-1] for argv in calls if "kill" in argv}
    assert "aoteru-run-eeee.service" not in killed and "aoteru-run-aaaa.service" not in killed
    assert killed == {"aoteru-run-cccc.service", "aoteru-prepare-dddd.service"}


def test_cleanup_with_nothing_owned_kills_nothing():
    calls = []
    live_units.stop_units_started_since(set(), set(), fake_systemctl(LISTING, calls))
    assert not [argv for argv in calls if "kill" in argv]


class Failed(Done):
    returncode = 1
    stderr = "Failed to connect to bus: No such file or directory"


def test_a_failed_listing_is_an_error_not_an_empty_snapshot():
    """Review (GLM-5.3): a swallowed systemctl failure made the snapshot empty and the busy-skip never fire."""
    import pytest
    def run(argv, **kwargs):
        return Failed()
    with pytest.raises(RuntimeError):
        live_units.active_units(run)
    with pytest.raises(RuntimeError):
        live_units.busy_units(run)


def test_a_failed_listing_at_teardown_kills_nothing():
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return Failed()

    live_units.stop_units_started_since(set(), {"cccc"}, run)
    assert not [argv for argv in calls if "kill" in argv]


def test_a_unit_that_drains_quickly_does_not_cause_a_skip_but_a_persistent_one_does():
    states = iter([LISTING, "aoteru-verify-x-1.service loaded active running v\n", ""])
    now = [0.0]

    def run(argv, **kwargs):
        return Done(next(states, ""))

    def sleep(seconds):
        now[0] += seconds

    assert live_units.wait_until_idle(timeout=10, interval=1, run=run, sleep=sleep, clock=lambda: now[0]) == set()
    always = lambda argv, **kwargs: Done("aoteru-run-live.service loaded active running a real writer\n")
    now[0] = 0.0
    assert live_units.wait_until_idle(timeout=3, interval=1, run=always, sleep=sleep, clock=lambda: now[0]) == {
        "aoteru-run-live.service"}


def test_the_live_test_module_no_longer_kills_every_aoteru_unit():
    import pathlib
    source = (pathlib.Path(__file__).parent / "test_estate_stage6_integration_live.py").read_text()
    assert "def _stop_units" not in source
    assert "stop_units_started_since" in source and "wait_until_idle" in source

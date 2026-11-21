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
    live_units.stop_units_started_since(before, fake_systemctl(LISTING, calls))
    killed = sorted(argv[-1] for argv in calls if "kill" in argv)
    assert killed == ["aoteru-prepare-dddd.service", "aoteru-run-cccc.service"]
    assert "aoteru-run-aaaa.service" not in killed and "aoteru-run-bbbb.service" not in killed


def test_cleanup_with_no_new_units_kills_nothing():
    calls = []
    everything = live_units.active_units(fake_systemctl(LISTING, []))
    live_units.stop_units_started_since(everything, fake_systemctl(LISTING, calls))
    assert not [argv for argv in calls if "kill" in argv]


def test_the_live_test_module_no_longer_kills_every_aoteru_unit():
    import pathlib
    source = (pathlib.Path(__file__).parent / "test_estate_stage6_integration_live.py").read_text()
    assert "def _stop_units" not in source
    assert "stop_units_started_since" in source and "busy_units" in source

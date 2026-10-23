"""The live worker tests wait for a runner script to write its cgroup into a marker file (deterministic, needs no systemd).

These run everywhere, including CI: the module-level skip of the live test file does not apply to this one.
"""
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from tests.helpers.cgroup_marker import _wait_for_cgroup_marker

ROOT = Path(__file__).resolve().parents[1]


def test_waits_through_a_file_that_exists_empty_then_holds_only_a_partial_line_then_completes(tmp_path):
    marker = tmp_path / "cgroup.txt"
    marker.write_text("")                                         # created by the shell redirect, nothing written yet

    def finish():
        marker.write_text("0::")                                  # a partial write: the separator but no path yet
        threading.Timer(0.2, lambda: marker.write_text("0::/user.slice/x.service")).start()          # path, no newline
        threading.Timer(0.4, lambda: marker.write_text("0::/user.slice/x.service\n")).start()        # complete
    threading.Timer(0.2, finish).start()
    assert _wait_for_cgroup_marker(marker, timeout=5) == "/user.slice/x.service"


def test_a_missing_marker_times_out_with_a_clear_error(tmp_path):
    with pytest.raises(AssertionError, match="never held a complete line"):
        _wait_for_cgroup_marker(tmp_path / "missing.txt", timeout=0.2)


def test_a_marker_that_never_completes_times_out(tmp_path):
    marker = tmp_path / "cgroup.txt"
    marker.write_text("0::")
    with pytest.raises(AssertionError, match="never held a complete line"):
        _wait_for_cgroup_marker(marker, timeout=0.2)


def test_fresh_process_import_does_not_launch_subprocesses_or_load_live_tests():
    script = """
import subprocess
import sys

def forbidden(*args, **kwargs):
    raise AssertionError(f"subprocess launch during pure test import: {args!r} {kwargs!r}")

subprocess.Popen = forbidden
import tests.test_estate_cgroup_marker_wait
assert "tests.test_estate_worker_units_live" not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr


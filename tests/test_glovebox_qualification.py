"""Tests for scripts/glovebox_qualification.py (Workstream G) — a
read-only qualification tool for the still-unreachable glovebox Jetson.
Cannot be tested against real hardware this session (glovebox has been
offline 36+ days); these tests exercise the check functions' own
present/absent classification and confirm it never mutates
config/estate.yaml, mirroring test_home_reentry_inventory.py's pattern.
"""
import importlib.util
import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
for p in (str(PROJECT_ROOT), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

_spec = importlib.util.spec_from_file_location(
    "glovebox_qualification", SCRIPTS_DIR / "glovebox_qualification.py"
)
gq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gq)


def test_qualification_is_read_only_and_never_mutates_estate_config():
    estate_yaml = PROJECT_ROOT / "config" / "estate.yaml"
    before = estate_yaml.read_text(encoding="utf-8")

    gq.build_qualification()

    after = estate_yaml.read_text(encoding="utf-8")
    assert before == after


def test_qualification_reports_all_expected_sections():
    report = gq.build_qualification()
    assert report["role"] == "experiment-edge"
    assert set(report) >= {
        "jetpack_l4t", "ros2", "realsense", "thermals_power",
        "candidate_capability_tags", "note",
    }
    assert report["candidate_capability_tags"] == [
        "ros2", "realsense", "experiment-capture", "edge-perception", "robotics-logs",
    ]


def test_jetpack_absent_reported_cleanly_not_guessed():
    # This lab host is genuinely not a Jetson — /etc/nv_tegra_release
    # really doesn't exist here, so this exercises the real absent path
    # rather than mocking it.
    result = gq._jetpack_l4t_version()
    assert result["present"] is False
    assert result["path"] == "/etc/nv_tegra_release"


def test_ros2_absent_when_binary_not_on_path(monkeypatch):
    monkeypatch.setattr(gq.shutil, "which", lambda name: None)
    result = gq._ros2()
    assert result == {"present": False}


def test_ros2_present_reports_version(monkeypatch):
    monkeypatch.setattr(gq.shutil, "which", lambda name: "/usr/bin/ros2" if name == "ros2" else None)

    def fake_run(cmd, **kwargs):
        return types.SimpleNamespace(stdout="ros2 humble\n", stderr="")
    monkeypatch.setattr(gq.subprocess, "run", fake_run)

    result = gq._ros2()
    assert result["present"] is True
    assert result["version"] == "ros2 humble"


def test_tegrastats_absent_when_binary_not_on_path(monkeypatch):
    monkeypatch.setattr(gq.shutil, "which", lambda name: None)
    result = gq._thermals_power()
    assert result == {"present": False}


def test_tegrastats_timeout_treated_as_present_not_a_failure(monkeypatch):
    """tegrastats streams continuously on some L4T versions, so a bounded
    subprocess call will legitimately time out — that must be reported as
    'present' (the binary ran) not as an error."""
    import subprocess as real_subprocess
    monkeypatch.setattr(gq.shutil, "which", lambda name: "/usr/bin/tegrastats")

    def fake_run(cmd, **kwargs):
        raise real_subprocess.TimeoutExpired(cmd=cmd, timeout=3, output=b"RAM 100/1000\n")
    monkeypatch.setattr(gq.subprocess, "run", fake_run)

    result = gq._thermals_power()
    assert result["present"] is True

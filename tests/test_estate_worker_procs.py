"""Tests for src/estate_worker_procs.py's process layer (Stage 2's Linux
implementation, Stage 4's Windows implementation). The Linux branch is
exercised for real against actual child processes; the Windows branch is
untestable on this host by construction, so it's exercised entirely
through monkeypatched `os.name`/`ctypes`/`subprocess`.
"""
import ctypes  # noqa: F401 -- imported here, before any os.name patching below,
                # so the real (posix) ctypes/__init__.py has already run; ctypes
                # itself branches on os.name == "nt" at import time, so importing
                # it for the first time under a patched os.name would blow up.
import subprocess
import sys
import time
import types

import pytest

import src.estate_worker_procs as procs


# ---------------------------------------------------------------------
# Linux — real processes
# ---------------------------------------------------------------------

def test_spawn_detached_is_alive_then_dies(tmp_path):
    handle = procs.spawn_detached(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        str(tmp_path), str(tmp_path / "worker.log"),
    )
    assert procs.is_alive(handle) is True
    outcome = procs.kill_tree(handle)
    assert outcome["ok"] is True
    assert procs.is_alive(handle) is False


def test_spawn_detached_survives_process_exit_naturally(tmp_path):
    handle = procs.spawn_detached(
        [sys.executable, "-c", "pass"],
        str(tmp_path), str(tmp_path / "worker.log"),
    )
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and procs.is_alive(handle):
        time.sleep(0.05)
    assert procs.is_alive(handle) is False


def test_kill_tree_on_already_dead_handle_is_a_clean_noop(tmp_path):
    handle = procs.spawn_detached(
        [sys.executable, "-c", "pass"],
        str(tmp_path), str(tmp_path / "worker.log"),
    )
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and procs.is_alive(handle):
        time.sleep(0.05)
    outcome = procs.kill_tree(handle)
    assert outcome == {"ok": True, "attempted_pids": [], "still_alive_pids": []}


def test_is_alive_rejects_a_reused_pid_with_different_create_time(tmp_path):
    handle = procs.spawn_detached(
        [sys.executable, "-c", "pass"],
        str(tmp_path), str(tmp_path / "worker.log"),
    )
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and procs.is_alive(handle):
        time.sleep(0.05)
    # Same pid number, wrong create_time -- must not be reported alive
    # even if that pid number now belongs to something else.
    forged = {"pid": handle["pid"], "create_time": handle["create_time"] + 999999}
    assert procs.is_alive(forged) is False


def test_is_alive_handles_malformed_handle():
    assert procs.is_alive({}) is False
    assert procs.is_alive({"pid": "not-an-int"}) is False


# ---------------------------------------------------------------------
# Windows — fully monkeypatched, this host never runs these code paths
# ---------------------------------------------------------------------

class _FakeOsNT:
    """A proxy for the `os` module with `name` forced to `"nt"`, bound
    only as `estate_worker_procs`'s module-level `os` reference -- never
    the real, process-wide `os` module. Patching the real module's
    `.name` attribute would also break `pathlib.Path` (which branches on
    `os.name` at construction time) for every other piece of code in the
    same test process, including this test file's own `tmp_path`
    fixture."""

    name = "nt"

    def __getattr__(self, item):
        import os as _real_os
        return getattr(_real_os, item)


def _patch_windows(monkeypatch) -> None:
    monkeypatch.setattr(procs, "os", _FakeOsNT())


class _FakeFileTime:
    def __init__(self):
        self.dwLowDateTime = 0
        self.dwHighDateTime = 0


class _FakeWintypes(types.SimpleNamespace):
    FILETIME = _FakeFileTime


def _install_fake_ctypes(monkeypatch, *, get_process_times_ok=True, creation_ticks=1000,
                          exit_code=259, open_process_ok=True):
    import ctypes as real_ctypes

    calls = {"GetProcessTimes": [], "OpenProcess": [], "GetExitCodeProcess": [], "CloseHandle": []}

    class FakeKernel32:
        def OpenProcess(self, access, inherit, pid):
            calls["OpenProcess"].append((access, inherit, pid))
            return 4242 if open_process_ok else 0

        def GetProcessTimes(self, handle, creation, exit_time, kernel_time, user_time):
            calls["GetProcessTimes"].append(handle)
            if not get_process_times_ok:
                return 0
            creation._obj.dwLowDateTime = creation_ticks & 0xFFFFFFFF
            creation._obj.dwHighDateTime = (creation_ticks >> 32) & 0xFFFFFFFF
            return 1

        def GetExitCodeProcess(self, handle, exit_code_ref):
            calls["GetExitCodeProcess"].append(handle)
            exit_code_ref._obj.value = exit_code
            return 1

        def CloseHandle(self, handle):
            calls["CloseHandle"].append(handle)
            return 1

    fake_windll = types.SimpleNamespace(kernel32=FakeKernel32())
    monkeypatch.setattr(real_ctypes, "windll", fake_windll, raising=False)
    return calls


def test_windows_spawn_detached_composes_breakaway_flags(monkeypatch, tmp_path):
    _patch_windows(monkeypatch)
    _install_fake_ctypes(monkeypatch)

    captured = {}

    class FakePopen:
        def __init__(self, argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            self.pid = 777
            self._handle = 55

    monkeypatch.setattr(procs.subprocess, "Popen", FakePopen)

    handle = procs.spawn_detached(["worker.exe"], str(tmp_path), str(tmp_path / "w.log"))
    assert handle == {"pid": 777, "create_time": 1000}
    flags = captured["kwargs"]["creationflags"]
    assert flags & procs._CREATE_NEW_PROCESS_GROUP
    assert flags & procs._DETACHED_PROCESS
    assert flags & procs._CREATE_BREAKAWAY_FROM_JOB


def test_windows_spawn_detached_breakaway_refused_is_executor_unavailable(monkeypatch, tmp_path):
    _patch_windows(monkeypatch)
    _install_fake_ctypes(monkeypatch)

    def raising_popen(argv, **kwargs):
        raise OSError("access is denied")

    monkeypatch.setattr(procs.subprocess, "Popen", raising_popen)

    with pytest.raises(procs.ProcessLayerError) as excinfo:
        procs.spawn_detached(["worker.exe"], str(tmp_path), str(tmp_path / "w.log"))
    assert excinfo.value.code == "executor_unavailable"


def test_windows_is_alive_true_when_still_active(monkeypatch):
    _patch_windows(monkeypatch)
    _install_fake_ctypes(monkeypatch, creation_ticks=1000, exit_code=259)
    assert procs.is_alive({"pid": 777, "create_time": 1000}) is True


def test_windows_is_alive_false_when_exited(monkeypatch):
    _patch_windows(monkeypatch)
    _install_fake_ctypes(monkeypatch, creation_ticks=1000, exit_code=0)
    assert procs.is_alive({"pid": 777, "create_time": 1000}) is False


def test_windows_is_alive_false_on_create_time_mismatch(monkeypatch):
    _patch_windows(monkeypatch)
    _install_fake_ctypes(monkeypatch, creation_ticks=2000, exit_code=259)
    assert procs.is_alive({"pid": 777, "create_time": 1000}) is False


def test_windows_is_alive_false_when_open_process_fails(monkeypatch):
    _patch_windows(monkeypatch)
    _install_fake_ctypes(monkeypatch, open_process_ok=False)
    assert procs.is_alive({"pid": 777, "create_time": 1000}) is False


def test_windows_kill_tree_uses_taskkill_with_tree_and_force(monkeypatch):
    _patch_windows(monkeypatch)
    calls = _install_fake_ctypes(monkeypatch, creation_ticks=1000, exit_code=259)
    captured = {}

    call_count = {"n": 0}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        call_count["n"] += 1
        # After taskkill "runs", flip is_alive to False by making the
        # next GetExitCodeProcess report the process has exited.
        calls_local = _install_fake_ctypes(monkeypatch, creation_ticks=1000, exit_code=0)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(procs.subprocess, "run", fake_run)

    outcome = procs.kill_tree({"pid": 777, "create_time": 1000})
    assert outcome["ok"] is True
    assert captured["argv"] == ["taskkill", "/PID", "777", "/T", "/F"]

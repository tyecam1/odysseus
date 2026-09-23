"""Integration (plan §G U67 real form / I4 worker half): the REAL worker CLI
launching a REAL transient systemd user unit on this host, with HOME
pointed at a temp dir so no live spool or sentinel is touched. Skipped
with a recorded reason when user units are unavailable (CI, Windows)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from src import estate_worker_procs
from src.estate_router import current_host_id
from src.estate_worker_protocol import build_request

ROOT = Path(__file__).resolve().parents[1]

_supported, _detail = (False, "not probed")
if os.name != "nt":
    _supported, _detail = estate_worker_procs.runner_units_supported()
pytestmark = pytest.mark.skipif(not _supported or current_host_id() is None,
                                reason=f"systemd user units unavailable here: {_detail}")


def _worker(home, verb, payload, deadline_s=30):
    request = build_request(verb, current_host_id(), payload, deadline_s)
    env = {**os.environ, "HOME": str(home), "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR",
                                                                             f"/run/user/{os.getuid()}")}
    completed = subprocess.run([sys.executable, "-m", "src.estate_worker", "--root", str(ROOT)],
                               input=json.dumps(request), capture_output=True, text=True, env=env,
                               cwd=str(ROOT), timeout=deadline_s + 15)
    assert completed.returncode == 0, completed.stderr
    response = json.loads(completed.stdout)
    assert response["ok"] is True, response
    return response["result"]


def _wait(home, execution_id, predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = _worker(home, "status", {"execution_id": execution_id})
        if predicate(status):
            return status
        time.sleep(0.5)
    raise AssertionError(f"timed out; last status {status}")


def test_real_unit_noop_sleep_runs_to_quiescent_success(tmp_path):
    home = tmp_path / "home"
    (home / ".aoteru").mkdir(parents=True)
    (home / ".aoteru" / "worker_selftest_enabled").touch()
    execution_id = f"live-{os.getpid()}-{int(time.time())}"
    started = _worker(home, "start", {"execution_id": execution_id, "kind": "noop-sleep", "timeout_s": 2})
    assert started["accepted"] is True
    running = _wait(home, execution_id, lambda s: s["state"] == "running")
    unit = running["handle"]["unit"]
    assert unit == f"aoteru-run-{execution_id}.service"
    assert running["handle"]["cgroup"].endswith("/" + unit)
    assert running["quiescent"] is False
    done = _wait(home, execution_id, lambda s: s["state"] == "succeeded")
    assert done["quiescent"] is True and done["process_alive"] is False
    # Replay of the same id never spawns again.
    replay = _worker(home, "start", {"execution_id": execution_id, "kind": "noop-sleep", "timeout_s": 2})
    assert replay["reused"] is True and replay["state"] == "succeeded"


def test_real_unit_cancel_kills_the_unit_and_becomes_quiescent(tmp_path):
    home = tmp_path / "home"
    (home / ".aoteru").mkdir(parents=True)
    (home / ".aoteru" / "worker_selftest_enabled").touch()
    execution_id = f"live-cancel-{os.getpid()}-{int(time.time())}"
    _worker(home, "start", {"execution_id": execution_id, "kind": "noop-sleep", "timeout_s": 60})
    _wait(home, execution_id, lambda s: s["state"] == "running")
    cancelled = _worker(home, "cancel", {"execution_id": execution_id})
    final = _wait(home, execution_id, lambda s: s["quiescent"] is True)
    assert final["state"] == "failed" and final["process_alive"] is False
    assert cancelled["still_alive_pids"] in ([], [final["handle"]["pid"]])

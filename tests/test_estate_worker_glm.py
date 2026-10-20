"""GLM write-runner regressions for the existing durable worker lifecycle."""
import json
import os
import socket
import stat
import sys
import time
from pathlib import Path

import yaml

from src import estate_router
from src import estate_worker
from src.estate_worker_protocol import build_request, validate_response
from tests.helpers.fake_units import FakeUnits


def _configure_worker(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    (config / "estate.yaml").write_text(yaml.safe_dump({
        "hosts": [{
            "id": "test-lab", "hostname": "THIS-HOST", "role": "lab",
            "identity_verified": True,
            "worker": {"enabled": True, "transport": "local"},
        }],
    }))
    (config / "repositories.yaml").write_text(yaml.safe_dump({
        "repos": [{"id": "test-repo", "path": str(repo)}],
    }))
    monkeypatch.setattr(estate_worker.estate_router, "_CONFIG_DIR", config)
    monkeypatch.setattr(socket, "gethostname", lambda: "THIS-HOST")
    monkeypatch.setattr(estate_worker, "_SPOOL_ROOT", tmp_path / "spool")
    monkeypatch.setattr(estate_worker, "_PREPARE_ROOT", tmp_path / "prepare")
    monkeypatch.setattr(estate_worker, "machine_fingerprint", lambda: "0123456789abcdef")
    monkeypatch.setattr(estate_worker, "_worker_version", lambda: "abc123")
    monkeypatch.setattr(estate_worker, "_worktree_verification", lambda *args: {
        "ok": True, "path": str(repo), "reason": None, "head_sha": "abc", "clean": True,
    })
    monkeypatch.setattr(estate_worker.estate_worker_procs, "glm_launcher_path", lambda: "/fake/claude-glm")
    units = FakeUnits(tmp_path, monkeypatch, estate_worker)
    return repo, units


def _call(verb, payload):
    request = build_request(verb, "test-lab", payload, 30)
    response = estate_worker.handle(request)
    assert validate_response(response, request) == (True, None)
    return response


def test_glm_start_creates_spool_claim_and_runs_in_existing_unit(tmp_path, monkeypatch):
    repo, units = _configure_worker(tmp_path, monkeypatch)
    execution_id = "glm-execution-1"
    payload = {
        "execution_id": execution_id, "kind": "glm-write", "objective": "make the change",
        "repo_id": "test-repo", "timeout_s": 17,
        "lease": {
            "lease_id": "lease-1", "worktree_path": str(repo), "branch": "feature",
            "expected_head_sha": "abc",
        },
    }

    started = _call("start", payload)["result"]

    spool = estate_worker._SPOOL_ROOT / execution_id
    claim = estate_worker.read_decision(spool / "claim.json")
    assert started["state"] == "starting"
    assert claim["kind"] == "start"
    assert claim["request"]["kind"] == "glm-write"
    assert [entry["unit"] for entry in units.spawned] == [f"aoteru-run-{execution_id}"]

    calls = []

    def fake_glm(objective, **kwargs):
        calls.append((objective, kwargs))
        kwargs["on_started"](777)
        return {
            "ok": True, "provider": "glm", "model": "launcher-model-v1",
            "model_evidence": "launcher_response", "output": "done",
        }

    monkeypatch.setattr(estate_worker.estate_worker_procs, "execute_glm_write", fake_glm)
    units.enter(f"aoteru-run-{execution_id}.service")
    assert estate_worker._run_spooled(execution_id) == 0
    assert calls[0][0] == "make the change"
    assert calls[0][1]["cwd"] == str(repo)
    assert calls[0][1]["timeout"] == 17.0
    assert estate_worker._json_read(spool / "result.json")["model"] == "launcher-model-v1"
    assert estate_worker._json_read(spool / "state.json")["writer_pid"] == 777


def test_glm_read_timeout_kills_launcher_child_process_group(tmp_path, monkeypatch):
    child_pid_path = tmp_path / "child.pid"
    launcher = tmp_path / "claude-glm-stub"
    launcher.write_text(
        "#!" + sys.executable + "\n"
        "import subprocess, sys, time\n"
        f"p = subprocess.Popen([{sys.executable!r}, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(child_pid_path)!r}, 'w').write(str(p.pid))\n"
        "sys.stdout.flush()\n"
        "time.sleep(60)\n"
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr(estate_router, "_resolve_claude_glm_launcher", lambda: (str(launcher), "available"))

    result = estate_router.execute_claude_glm("inspect", timeout=0.2, cwd=str(tmp_path))

    assert result["ok"] is False
    assert "timed out" in result["error"]
    deadline = time.monotonic() + 3
    while not child_pid_path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert child_pid_path.exists()
    child_pid = int(child_pid_path.read_text())
    while time.monotonic() < deadline:
        try:
            fields = Path(f"/proc/{child_pid}/stat").read_text().split()
        except FileNotFoundError:
            break
        if len(fields) > 2 and fields[2] == "Z":
            break
        time.sleep(0.02)
    else:
        os.kill(child_pid, 9)
        raise AssertionError(f"launcher child {child_pid} survived timeout cleanup")


def test_glm_launcher_response_without_model_is_unattributed(monkeypatch):
    class FakeProcess:
        pid = 1234
        returncode = 0

        def communicate(self, objective, timeout):
            return json.dumps({"result": "done"}), ""

    monkeypatch.setattr(estate_worker.estate_worker_procs, "glm_launcher_path", lambda: "/fake/claude-glm")
    monkeypatch.setattr(estate_worker.estate_worker_procs.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    result = estate_worker.estate_worker_procs.execute_glm_write(
        "change", cwd="/worktree", timeout=10,
    )

    assert result["model"] is None
    assert result["model_evidence"] == "unattributed"

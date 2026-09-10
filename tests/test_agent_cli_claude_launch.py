"""Tests for scripts/agent's `cmd_claude` native launch path
(docs/aoteru-model-effort-routing.agent-task.md wired --effort through
it) — previously always failed with "native launch is not yet
implemented"; now actually spawns `claude --print --output-format json`
non-interactively when the binary is present, same bounded-subprocess/
stdin-objective/JSON-envelope shape as the claude-glm candidate lane
(src.estate_router.execute_claude_glm) and execute_codex elsewhere in
this estate.
"""
import importlib.machinery
import importlib.util
import json
import socket
import sys
import types
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "agent"


def load_module():
    loader = importlib.machinery.SourceFileLoader("agent_cli", str(SCRIPT_PATH))
    spec = importlib.util.spec_from_loader("agent_cli", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


@pytest.fixture
def agent_cli():
    return load_module()


@pytest.fixture
def fixture_config(tmp_path, monkeypatch, agent_cli):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "estate.yaml").write_text(yaml.safe_dump({
        "hosts": [{"id": "test-lab", "hostname": "THIS-HOST", "role": "lab", "tailscale": True}],
    }))
    (config_dir / "repositories.yaml").write_text(yaml.safe_dump({"repos": []}))
    monkeypatch.setattr(agent_cli, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(agent_cli, "_load_host_local", lambda: {})
    monkeypatch.setattr(socket, "gethostname", lambda: "THIS-HOST")
    return config_dir


def _args(**overrides):
    base = dict(mode="lab", task="do the thing", repo=None, effort=None, pretty=False)
    base.update(overrides)
    return types.SimpleNamespace(**base)


def test_no_binary_still_fails_truthfully_without_active_row(agent_cli, fixture_config, monkeypatch, capsys):
    from core.database import get_db_session, LogicalSession
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: None)

    with pytest.raises(SystemExit) as exc:
        agent_cli.cmd_claude(_args())
    assert exc.value.code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert "not installed" in out["error"]
    with get_db_session() as db:
        row = db.query(LogicalSession).filter(LogicalSession.id == out["session_id"]).first()
        assert row.status == "failed"


class _FakeProc:
    def __init__(self, returncode, stdout, stderr=""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    def communicate(self, input=None, timeout=None):
        return self._stdout, self._stderr

    def kill(self):
        pass


def test_successful_launch_writes_closed_status_and_session_id(agent_cli, fixture_config, monkeypatch, capsys):
    import shutil
    import subprocess
    from core.database import get_db_session, LogicalSession

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/claude")
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeProc(0, json.dumps({"result": "done", "session_id": "claude-sess-1"}))

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    agent_cli.cmd_claude(_args(effort="high"))

    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["claude_session_id"] == "claude-sess-1"
    assert "--effort" in captured["args"]
    assert captured["args"][captured["args"].index("--effort") + 1] == "high"

    with get_db_session() as db:
        row = db.query(LogicalSession).filter(LogicalSession.id == out["session_id"]).first()
        assert row.status == "closed"
        assert row.claude_session_id == "claude-sess-1"


def test_highest_effort_maps_to_xhigh(agent_cli, fixture_config, monkeypatch, capsys):
    import shutil
    import subprocess

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/claude")
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        return _FakeProc(0, json.dumps({"result": "done"}))

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    agent_cli.cmd_claude(_args(effort="highest"))
    assert captured["args"][captured["args"].index("--effort") + 1] == "xhigh"


def test_no_effort_omits_flag_unchanged(agent_cli, fixture_config, monkeypatch, capsys):
    import shutil
    import subprocess

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/claude")
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        return _FakeProc(0, json.dumps({"result": "done"}))

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    agent_cli.cmd_claude(_args())
    assert "--effort" not in captured["args"]


def test_failed_launch_writes_failed_status(agent_cli, fixture_config, monkeypatch, capsys):
    import shutil
    import subprocess
    from core.database import get_db_session, LogicalSession

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/claude")
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kwargs: _FakeProc(1, "", "boom"))

    with pytest.raises(SystemExit) as exc:
        agent_cli.cmd_claude(_args())
    assert exc.value.code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    with get_db_session() as db:
        row = db.query(LogicalSession).filter(LogicalSession.id == out["session_id"]).first()
        assert row.status == "failed"

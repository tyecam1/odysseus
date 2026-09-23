import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import src.estate_worker as estate_worker
from src.estate_worker_protocol import build_request, validate_response


@pytest.fixture
def fixture_config(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (config_dir / "estate.yaml").write_text(yaml.safe_dump({
        "hosts": [{
            "id": "test-lab", "hostname": "THIS-HOST", "role": "lab",
            "identity_verified": True,
            "worker": {"enabled": True, "transport": "local"},
        }],
    }))
    (config_dir / "repositories.yaml").write_text(yaml.safe_dump({
        "repos": [{"id": "test-repo", "path": str(repo_path)}],
    }))
    monkeypatch.setattr(estate_worker.estate_router, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(socket, "gethostname", lambda: "THIS-HOST")
    monkeypatch.setattr(estate_worker, "_SPOOL_ROOT", tmp_path / "spool")
    monkeypatch.setattr(estate_worker, "machine_fingerprint", lambda: "0123456789abcdef")
    monkeypatch.setattr(estate_worker, "_worker_version", lambda: "abc123")
    return {"config": config_dir, "repo": repo_path, "root": tmp_path}


def _call(verb, payload=None, expected_host_id="test-lab"):
    request = build_request(verb, expected_host_id, payload or {}, 30)
    response = estate_worker.handle(request)
    assert validate_response(response, request) == (True, None)
    return response


def test_health_shape(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_worker, "_ollama_inventory", lambda: (True, [], None))
    monkeypatch.setattr(estate_worker.estate_router, "_codex_available", lambda: (True, "/bin/codex"))
    monkeypatch.setattr(estate_worker.estate_router, "experiment_priority_active", lambda: (False, "idle"))
    response = _call("health")
    assert response["ok"] is True
    assert response["result"]["ollama"] == {
        "reachable": True, "base_url": estate_worker._OLLAMA_BASE, "error": None,
    }
    assert response["result"]["codex"]["available"] is True
    assert response["result"]["gpu_yield"] == {"active": False, "reason": "idle"}
    assert response["result"]["in_flight"] == []


def test_inventory_lists_requested_context_and_repos(fixture_config, monkeypatch):
    monkeypatch.setattr(
        estate_worker, "_ollama_inventory",
        lambda: (True, [{"name": "model-a", "digest": "digest-a"}], None),
    )
    monkeypatch.setattr(estate_worker.estate_router, "_codex_available", lambda: (False, "missing"))
    monkeypatch.setattr(
        estate_worker, "_probe_repo",
        lambda repo_id: {
            "resolved": True, "path": str(fixture_config["repo"]), "head_sha": "abc",
            "branch": "main", "clean": True,
        },
    )
    import src.model_context as model_context
    import scripts.home_reentry_inventory as home_inventory
    monkeypatch.setattr(model_context, "get_context_length_known", lambda base, model: (8192, True))
    monkeypatch.setattr(home_inventory, "_hardware", lambda: {"cpu_count": 8})

    result = _call("inventory", {"models_of_interest": ["model-a"]})["result"]
    assert result["models"] == [{"name": "model-a", "digest": "digest-a"}]
    assert result["context"] == {"model-a": {"length": 8192, "known": True}}
    assert result["repos"] == [{
        "repo_id": "test-repo", "resolved": True,
        "path": str(fixture_config["repo"]), "head_sha": "abc",
        "clean": True,
    }]
    assert result["hardware"] == {"cpu_count": 8}


def test_identity_mismatch_refuses_before_dispatch(fixture_config, monkeypatch):
    called = []
    monkeypatch.setattr(estate_worker, "_verb_health", lambda payload: called.append(payload))
    response = _call("health", expected_host_id="test-home")
    assert response["ok"] is False
    assert response["error"]["code"] == "identity_mismatch"
    assert response["attestation"]["host_id"] == "test-lab"
    assert called == []


def test_execute_local_delegates_with_correct_args(fixture_config, monkeypatch):
    calls = []

    def fake_execute(model, objective, **kwargs):
        calls.append((model, objective, kwargs))
        return {"ok": True, "output": "local", "latency_ms": 1, "retries": 0}

    monkeypatch.setattr(estate_worker.estate_router, "execute_local", fake_execute)
    result = _call("execute", {
        "kind": "local-inference", "model": "model-a", "objective": "hello", "timeout_s": 12,
    })["result"]
    assert calls == [("model-a", "hello", {"timeout": 12.0})]
    assert result["provider"] == "ollama"
    assert result["concrete_model"] == "model-a"


def test_execute_codex_readonly_delegates_with_repo_cwd(fixture_config, monkeypatch):
    calls = []

    def fake_execute(objective, **kwargs):
        calls.append((objective, kwargs))
        return {"ok": True, "output": "codex", "latency_ms": 2}

    monkeypatch.setattr(estate_worker.estate_router, "execute_codex", fake_execute)
    result = _call("execute", {
        "kind": "codex-readonly", "objective": "inspect", "repo_id": "test-repo", "timeout_s": 15,
    })["result"]
    assert calls == [("inspect", {"timeout": 15.0, "cwd": str(fixture_config["repo"])})]
    assert result["provider"] == "codex"
    assert result["concrete_model"] == "codex-cli"


def test_start_is_idempotent_and_spawns_once(fixture_config, monkeypatch):
    spawn_calls = []
    monkeypatch.setattr(
        estate_worker, "_worktree_verification",
        lambda *args: {"ok": True, "path": str(fixture_config["repo"]), "reason": None},
    )

    def fake_spawn(argv, cwd, log_path):
        spawn_calls.append((argv, cwd, log_path))
        return {"pid": 123, "create_time": 456}

    monkeypatch.setattr(estate_worker.estate_worker_procs, "spawn_detached", fake_spawn)
    payload = {
        "execution_id": "execution-1", "kind": "codex-write", "objective": "change",
        "repo_id": "test-repo", "timeout_s": 30,
        "lease": {"lease_id": "lease-1", "worktree_path": str(fixture_config["repo"]), "branch": "feature"},
    }
    first = _call("start", payload)["result"]
    second = _call("start", payload)["result"]
    assert first["reused"] is False
    assert second == {"accepted": True, "handle": first["handle"], "reused": True}
    assert len(spawn_calls) == 1


def test_noop_sleep_start_refused_without_selftest_sentinel(fixture_config, monkeypatch):
    """Stage 4 review finding: the self-test gate must be disabled by
    default. `_selftest_enabled()` reads a home-local sentinel file under
    `~/.aoteru/`, not an environment variable -- `fixture_config` doesn't
    create that file, so this must refuse the same way whether or not
    `AOTERU_WORKER_SELFTEST` happens to be set in the test process's own
    environment (it must have no effect at all any more)."""
    monkeypatch.setenv("AOTERU_WORKER_SELFTEST", "1")
    response = _call("start", {"execution_id": "selftest-1", "kind": "noop-sleep", "timeout_s": 1})
    assert response["ok"] is False
    assert response["error"]["code"] == "bad_request"
    assert "self-test mode" in response["error"]["message"]


def test_noop_sleep_start_accepted_when_sentinel_file_present(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_worker, "_WORKER_SELFTEST_SENTINEL_PATH", fixture_config["root"] / "selftest-enabled")
    estate_worker._WORKER_SELFTEST_SENTINEL_PATH.touch()

    spawn_calls = []

    def fake_spawn(argv, cwd, log_path):
        spawn_calls.append((argv, cwd, log_path))
        return {"pid": 123, "create_time": 456}
    monkeypatch.setattr(estate_worker.estate_worker_procs, "spawn_detached", fake_spawn)

    result = _call("start", {"execution_id": "selftest-2", "kind": "noop-sleep", "timeout_s": 1})["result"]
    assert result["accepted"] is True
    assert len(spawn_calls) == 1


def test_selftest_enabled_reads_the_sentinel_file_only(tmp_path, monkeypatch):
    monkeypatch.setattr(estate_worker, "_WORKER_SELFTEST_SENTINEL_PATH", tmp_path / "worker_selftest_enabled")
    assert estate_worker._selftest_enabled() is False
    estate_worker._WORKER_SELFTEST_SENTINEL_PATH.touch()
    assert estate_worker._selftest_enabled() is True
    estate_worker._WORKER_SELFTEST_SENTINEL_PATH.unlink()
    assert estate_worker._selftest_enabled() is False


def _write_spool(execution_id, state, result=None):
    spool = estate_worker._SPOOL_ROOT / execution_id
    spool.mkdir(parents=True)
    estate_worker._json_write(spool / "state.json", state)
    if result is not None:
        estate_worker._json_write(spool / "result.json", result)


def test_status_running_terminal_and_unknown(fixture_config, monkeypatch):
    handle = {"pid": 123, "create_time": 456, "spool_id": "running-1"}
    monkeypatch.setattr(estate_worker.estate_worker_procs, "is_alive", lambda candidate: candidate == handle)
    _write_spool("running-1", {
        "state": "running", "handle": handle,
        "started_at": "2026-09-22T12:00:00Z", "finished_at": None,
    })
    running = _call("status", {"execution_id": "running-1"})["result"]
    assert running["state"] == "running"
    assert running["process_alive"] is True

    _write_spool("done-1", {
        "state": "succeeded", "handle": {**handle, "spool_id": "done-1"},
        "started_at": "start", "finished_at": "finish",
    }, {"ok": True, "output": "done"})
    terminal = _call("status", {"execution_id": "done-1"})["result"]
    assert terminal["state"] == "succeeded"
    assert terminal["result"] == {"ok": True, "output": "done"}

    unknown = _call("status", {"execution_id": "missing-1"})["result"]
    assert unknown["state"] == "unknown"
    assert unknown["handle"] is None


def test_cancel_uses_process_layer(fixture_config, monkeypatch):
    handle = {"pid": 123, "create_time": 456, "spool_id": "cancel-1"}
    _write_spool("cancel-1", {"state": "running", "handle": handle})
    calls = []
    monkeypatch.setattr(
        estate_worker.estate_worker_procs, "kill_tree",
        lambda candidate: calls.append(candidate) or {"ok": True, "still_alive_pids": []},
    )
    result = _call("cancel", {"execution_id": "cancel-1"})["result"]
    assert result == {"killed": True, "still_alive_pids": []}
    assert calls == [handle]


def test_run_spooled_delegates_to_workspace_write_codex(fixture_config, monkeypatch):
    execution_id = "spooled-1"
    handle = {"pid": 123, "create_time": 456, "spool_id": execution_id}
    spool = estate_worker._SPOOL_ROOT / execution_id
    spool.mkdir(parents=True)
    estate_worker._json_write(spool / "request.json", {
        "execution_id": execution_id,
        "kind": "codex-write",
        "objective": "make the change",
        "timeout_s": 17,
        "lease": {"worktree_path": str(fixture_config["repo"]), "branch": "feature"},
    })
    estate_worker._json_write(spool / "state.json", {
        "state": "accepted", "handle": handle, "started_at": None, "finished_at": None,
    })
    calls = []

    def fake_codex(objective, **kwargs):
        calls.append((objective, kwargs))
        kwargs["on_started"](999)
        return {"ok": True, "output": "done", "provider": "codex"}

    monkeypatch.setattr(estate_worker.estate_router, "_execute_codex_with_sandbox", fake_codex)
    assert estate_worker._run_spooled(execution_id) == 0
    assert calls[0][0] == "make the change"
    assert calls[0][1]["sandbox"] == "workspace-write"
    assert calls[0][1]["provider"] == "codex"
    assert calls[0][1]["timeout"] == 17.0
    assert calls[0][1]["cwd"] == str(fixture_config["repo"])
    assert estate_worker._json_read(spool / "result.json")["ok"] is True
    terminal = estate_worker._json_read(spool / "state.json")
    assert terminal["state"] == "succeeded"
    assert terminal["pid"] == 999


def test_worktree_verify_refuses_live_checkout(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_worker.worktree_ops, "is_live_checkout_path", lambda repo, path: True)
    result = _call("worktree.verify", {
        "repo_id": "test-repo", "worktree_path": str(fixture_config["repo"]), "branch": "main",
    })["result"]
    assert result["ok"] is False
    assert result["reason"] == "refusing the live checkout"


def test_every_worker_verb_leaves_core_database_unimported(fixture_config, monkeypatch):
    # monkeypatch.delitem (not sys.modules.pop) so the real module object is
    # restored afterwards; a bare pop let later tests lazily import a *fresh*
    # core.database whose SessionLocal ignores their temp-DB patches.
    monkeypatch.delitem(sys.modules, "core.database", raising=False)
    monkeypatch.setattr(estate_worker, "_ollama_inventory", lambda: (False, [], "offline"))
    monkeypatch.setattr(estate_worker.estate_router, "_codex_available", lambda: (False, "missing"))
    monkeypatch.setattr(estate_worker.estate_router, "experiment_priority_active", lambda: (False, "idle"))
    monkeypatch.setattr(estate_worker, "_probe_repo", lambda repo: {
        "resolved": False, "path": None, "head_sha": None, "branch": None, "clean": False,
    })
    import src.model_context as model_context
    import scripts.home_reentry_inventory as home_inventory
    monkeypatch.setattr(model_context, "get_context_length_known", lambda base, model: (0, False))
    monkeypatch.setattr(home_inventory, "_hardware", lambda: {})
    monkeypatch.setattr(
        estate_worker.estate_router, "execute_local",
        lambda *args, **kwargs: {"ok": True, "output": "ok", "latency_ms": 1, "retries": 0},
    )
    monkeypatch.setattr(
        estate_worker.worktree_ops, "create_or_reuse_worktree",
        lambda *args, **kwargs: {"path": str(fixture_config["repo"]), "branch": "feature"},
    )
    monkeypatch.setattr(estate_worker.worktree_ops, "verify_worktree", lambda *args, **kwargs: {
        "ok": True, "path": str(fixture_config["repo"]), "branch": "feature", "head": "abc",
    })
    monkeypatch.setattr(estate_worker.worktree_ops, "is_live_checkout_path", lambda *args: False)
    monkeypatch.setattr(estate_worker, "git_is_clean", lambda path: (True, ""))
    monkeypatch.setattr(
        estate_worker.estate_worker_procs, "spawn_detached",
        lambda *args: {"pid": 123, "create_time": 456},
    )
    monkeypatch.setattr(estate_worker.estate_worker_procs, "is_alive", lambda handle: True)
    monkeypatch.setattr(
        estate_worker.estate_worker_procs, "kill_tree",
        lambda handle: {"ok": True, "still_alive_pids": []},
    )

    calls = [
        ("health", {}),
        ("inventory", {"models_of_interest": []}),
        ("repo.probe", {"repo_id": "test-repo"}),
        ("execute", {"kind": "local-inference", "model": "model-a", "objective": "x", "timeout_s": 1}),
        ("worktree.prepare", {"repo_id": "test-repo", "branch": "feature", "base_ref": "HEAD"}),
        ("worktree.verify", {"repo_id": "test-repo", "worktree_path": str(fixture_config["repo"]), "branch": "feature"}),
        ("start", {
            "execution_id": "hygiene-1", "kind": "codex-write", "objective": "x",
            "repo_id": "test-repo", "timeout_s": 1,
            "lease": {"lease_id": "lease", "worktree_path": str(fixture_config["repo"]), "branch": "feature"},
        }),
        ("status", {"execution_id": "hygiene-1"}),
        ("cancel", {"execution_id": "hygiene-1"}),
    ]
    for verb, payload in calls:
        assert _call(verb, payload)["ok"] is True
        assert "core.database" not in sys.modules, verb

    monkeypatch.setattr(
        estate_worker, "_worktree_verification",
        lambda *args: {"ok": True, "path": str(fixture_config["repo"]), "reason": None},
    )
    monkeypatch.setattr(estate_worker, "_run_git", lambda path, args, **kwargs: subprocess.CompletedProcess(
        args, 0, stdout=("feature\n" if args == ["branch", "--show-current"] else ("abc\n" if args == ["rev-parse", "HEAD"] else "")), stderr="",
    ))
    assert _call("worktree.finalize", {
        "repo_id": "test-repo", "worktree_path": str(fixture_config["repo"]),
        "branch": "feature", "commit_message": "test",
    })["ok"] is True
    assert "core.database" not in sys.modules


def test_cli_round_trip_returns_zero_for_handled_refusal(fixture_config):
    request = build_request("health", "test-lab", {}, 5)
    environment = os.environ.copy()
    project_root = str(Path(__file__).parents[1])
    environment["PYTHONPATH"] = project_root + os.pathsep + environment.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-m", "src.estate_worker", "--root", str(fixture_config["root"])],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        cwd=project_root,
        env=environment,
        timeout=15,
    )
    assert completed.returncode == 0
    response = json.loads(completed.stdout)
    assert response["ok"] is False
    assert response["error"]["code"] == "identity_unregistered"
    assert validate_response(response, request) == (True, None)


def test_cli_from_an_arbitrary_starting_directory_cannot_import_the_module(fixture_config, tmp_path):
    """Stage 4 review finding: `python -m src.estate_worker --root
    <checkout>` cannot import `src.estate_worker` at all unless the
    checkout root is already on `sys.path` (via cwd or PYTHONPATH) --
    `--root` runs too late, inside `main()`, to fix its own import. This
    is why the forced SSH command documented in
    docs/aoteru-home-worker-setup.md now explicitly `cd`s into the
    checkout before invoking `-m`, rather than assuming the SSH session
    happens to start there (the previous, broken assumption)."""
    project_root = str(Path(__file__).parents[1])
    elsewhere = tmp_path / "not-the-checkout"
    elsewhere.mkdir()
    environment = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}

    completed = subprocess.run(
        [sys.executable, "-m", "src.estate_worker", "--root", project_root],
        input="{}",
        text=True,
        capture_output=True,
        cwd=str(elsewhere),
        env=environment,
        timeout=15,
    )
    assert completed.returncode != 0
    assert "No module named" in completed.stderr

"""Tests for src/estate_worker_client.py — the control-plane side of the
``aoteru-worker/1`` contract (Stage 3: docs/aoteru-multihost-execution-
implementation-plan.md). Most tests here fake the transport layer to
exercise `call_worker`'s validation/attestation logic in isolation; the
final test runs the real `LocalTransport` subprocess end to end against a
faked Ollama, which is the one place this module actually crosses a
process boundary.
"""
import json
import os
import socket
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import yaml

import src.estate_router as estate_router
import src.estate_worker_client as client


@pytest.fixture
def fixture_config(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "estate.yaml").write_text(yaml.safe_dump({
        "hosts": [
            {
                "id": "test-lab", "hostname": "THIS-HOST", "role": "lab",
                "identity_verified": True,
                "worker": {"enabled": True, "transport": "local"},
            },
            {
                "id": "test-lab-elsewhere", "hostname": "OTHER-HOST", "role": "lab",
                "identity_verified": True,
                "worker": {"enabled": True, "transport": "local"},
            },
            {
                "id": "test-home", "hostname": "OTHER-HOST", "role": "home",
                "identity_verified": True,
                "worker": {
                    "enabled": True, "transport": "ssh",
                    "machine_fingerprint": "fedcba9876543210",
                },
            },
            {
                "id": "test-unconfigured", "hostname": "NOBODY-HOST", "role": "home",
                "identity_verified": True,
                "worker": {"enabled": True},
            },
            {
                "id": "test-ssh-ready", "hostname": "SSH-HOST", "role": "home",
                "identity_verified": True,
                "worker": {
                    "enabled": True, "transport": "ssh",
                    "ssh": {"target": "user@ssh-host", "host_public_key": "ssh-ed25519 AAAAFAKE"},
                },
            },
        ],
    }))
    monkeypatch.setattr(estate_router, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(socket, "gethostname", lambda: "THIS-HOST")
    client.clear_caches()
    yield config_dir
    client.clear_caches()


def _attestation(host_id: str, nonce: str, fingerprint: str = "0123456789abcdef") -> dict:
    return {
        "host_id": host_id, "hostname": host_id, "machine_fingerprint": fingerprint,
        "os": "linux", "worker_pid": 4242, "worker_version": "abc123",
        "nonce": nonce, "observed_at": "2026-09-22T00:00:00Z",
    }


def _ok_response(request: dict, result: dict | None = None, **attestation_overrides) -> dict:
    attestation = _attestation(request["expected_host_id"], request["nonce"])
    attestation.update(attestation_overrides)
    return {
        "protocol": request["protocol"], "request_id": request["request_id"], "ok": True,
        "error": None, "attestation": attestation, "result": result or {},
    }


def _error_response(request: dict, code: str, message: str) -> dict:
    return {
        "protocol": request["protocol"], "request_id": request["request_id"], "ok": False,
        "error": {"code": code, "message": message},
        "attestation": _attestation(request["expected_host_id"], request["nonce"]),
        "result": {},
    }


class _FakeTransport:
    def __init__(self, response_fn):
        self.response_fn = response_fn
        self.sent: list[dict] = []

    def send(self, request: dict, *, deadline_s: float) -> dict:
        self.sent.append(request)
        return self.response_fn(request)


def test_transport_for_host_returns_local_transport_for_this_host(fixture_config):
    transport = client.transport_for_host("test-lab")
    assert isinstance(transport, client.LocalTransport)


def test_transport_for_host_refuses_local_transport_for_a_different_host(fixture_config):
    """The exact guard this stage depends on: a config typo or stale route
    naming a `local`-transport host that is not this process's own host
    must fail closed, never execute here under a false identity."""
    with pytest.raises(client.WorkerTransportError) as excinfo:
        client.transport_for_host("test-lab-elsewhere")
    assert excinfo.value.code == "placement_mismatch"


def test_transport_for_host_returns_ssh_transport_for_ssh_configured_host(fixture_config):
    transport = client.transport_for_host("test-home")
    assert isinstance(transport, client.SshTransport)


def test_transport_for_host_raises_for_unconfigured_transport(fixture_config):
    with pytest.raises(client.WorkerTransportError) as excinfo:
        client.transport_for_host("test-unconfigured")
    assert excinfo.value.code == "placement_mismatch"


def test_transport_for_host_raises_for_unregistered_host(fixture_config):
    with pytest.raises(client.WorkerTransportError) as excinfo:
        client.transport_for_host("nobody-here")
    assert excinfo.value.code == "placement_mismatch"


def test_ssh_transport_refuses_unpinned_host_key(fixture_config):
    transport = client.transport_for_host("test-home")
    with pytest.raises(client.WorkerTransportError) as excinfo:
        transport.send({"nonce": "x"}, deadline_s=10)
    assert excinfo.value.code == "host_key_unpinned"


class _FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_ssh_key(tmp_path, monkeypatch):
    key_dir = tmp_path / ".aoteru"
    key_dir.mkdir()
    key_path = key_dir / "worker_ssh_key"
    key_path.write_text("fake-private-key")
    monkeypatch.setattr(client.Path, "home", lambda: tmp_path)
    return key_path


def test_ssh_transport_builds_pinned_argv_with_no_remote_command(fixture_config, monkeypatch, tmp_path):
    key_path = _fake_ssh_key(tmp_path, monkeypatch)
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        request = json.loads(kwargs["input"])
        return _FakeCompleted(0, json.dumps(_ok_response(request)))

    monkeypatch.setattr(client.subprocess, "run", fake_run)

    response = client.call_worker("test-ssh-ready", "health", {}, deadline_s=10)
    assert response["ok"] is True

    argv = captured["argv"]
    assert argv[0] == "ssh"
    assert "BatchMode=yes" in argv
    assert "StrictHostKeyChecking=yes" in argv
    assert not any("StrictHostKeyChecking=no" in a for a in argv)
    assert any(a.startswith("UserKnownHostsFile=") for a in argv)
    assert "-i" in argv and str(key_path) in argv
    # The target is the last argv entry -- no remote command argument
    # follows it; the forced command on the far end is authoritative.
    assert argv[-1] == "user@ssh-host"


def test_ssh_transport_times_out_as_worker_unreachable(fixture_config, monkeypatch, tmp_path):
    import subprocess as real_subprocess
    _fake_ssh_key(tmp_path, monkeypatch)

    def fake_run(argv, **kwargs):
        raise real_subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(client.subprocess, "run", fake_run)

    with pytest.raises(client.WorkerTransportError) as excinfo:
        client.call_worker("test-ssh-ready", "health", {}, deadline_s=10)
    assert excinfo.value.code == "worker_unreachable"


def test_ssh_transport_nonzero_exit_is_worker_protocol_error(fixture_config, monkeypatch, tmp_path):
    _fake_ssh_key(tmp_path, monkeypatch)

    def fake_run(argv, **kwargs):
        return _FakeCompleted(255, "", "ssh: connection refused")

    monkeypatch.setattr(client.subprocess, "run", fake_run)

    with pytest.raises(client.WorkerTransportError) as excinfo:
        client.call_worker("test-ssh-ready", "health", {}, deadline_s=10)
    assert excinfo.value.code == "worker_protocol_error"


def test_call_worker_happy_path_returns_response(fixture_config, monkeypatch):
    fake = _FakeTransport(lambda request: _ok_response(request, {"foo": "bar"}))
    monkeypatch.setattr(client, "transport_for_host", lambda host_id: fake)

    response = client.call_worker("test-lab", "health", {}, deadline_s=10)
    assert response["ok"] is True
    assert response["result"] == {"foo": "bar"}
    assert fake.sent[0]["verb"] == "health"
    assert fake.sent[0]["expected_host_id"] == "test-lab"


def test_call_worker_raises_worker_reported_error(fixture_config, monkeypatch):
    fake = _FakeTransport(lambda request: _error_response(request, "executor_unavailable", "no codex"))
    monkeypatch.setattr(client, "transport_for_host", lambda host_id: fake)

    with pytest.raises(client.WorkerTransportError) as excinfo:
        client.call_worker("test-lab", "execute", {}, deadline_s=10)
    assert excinfo.value.code == "executor_unavailable"
    # A normal (non-placement) worker-reported error need not carry an
    # attested host -- observed_host_id stays None, same as before this
    # attribute existed.
    assert excinfo.value.observed_host_id is None


def test_call_worker_raises_worker_protocol_error_on_malformed_response(fixture_config, monkeypatch):
    fake = _FakeTransport(lambda request: {"not": "a valid envelope"})
    monkeypatch.setattr(client, "transport_for_host", lambda host_id: fake)

    with pytest.raises(client.WorkerTransportError) as excinfo:
        client.call_worker("test-lab", "health", {}, deadline_s=10)
    assert excinfo.value.code == "unsupported_protocol"


def test_attestation_host_mismatch_is_placement_mismatch(fixture_config, monkeypatch):
    fake = _FakeTransport(lambda request: _ok_response(request, host_id="some-other-host"))
    monkeypatch.setattr(client, "transport_for_host", lambda host_id: fake)

    with pytest.raises(client.WorkerTransportError) as excinfo:
        client.call_worker("test-lab", "health", {}, deadline_s=10)
    assert excinfo.value.code == "placement_mismatch"
    assert excinfo.value.observed_host_id == "some-other-host"


def test_nonce_mismatch_is_rejected_by_envelope_validation(fixture_config, monkeypatch):
    """`validate_response` itself checks the nonce echo, before
    `verify_attestation` ever runs — a replayed or mismatched response is
    caught as a protocol violation, not waved through to the placement
    check."""
    fake = _FakeTransport(lambda request: _ok_response(request, nonce="0" * 32))
    monkeypatch.setattr(client, "transport_for_host", lambda host_id: fake)

    with pytest.raises(client.WorkerTransportError) as excinfo:
        client.call_worker("test-lab", "health", {}, deadline_s=10)
    assert excinfo.value.code == "worker_protocol_error"


def test_pinned_fingerprint_mismatch_is_placement_mismatch(fixture_config, monkeypatch):
    """test-home pins `machine_fingerprint: fedcba9876543210` in
    config/estate.yaml — a worker attesting a different one must not be
    trusted even though the host id and nonce both check out."""
    fake = _FakeTransport(lambda request: _ok_response(request, machine_fingerprint="0000000000000000"))
    monkeypatch.setattr(client, "transport_for_host", lambda host_id: fake)

    with pytest.raises(client.WorkerTransportError) as excinfo:
        client.call_worker("test-home", "health", {}, deadline_s=10)
    assert excinfo.value.code == "placement_mismatch"
    # The attested host_id itself matched -- only the fingerprint didn't
    # -- so the observed host retained for diagnosis is still test-home,
    # not None: enough attestation context to tell "wrong hardware
    # answering as test-home" apart from "nothing answered at all".
    assert excinfo.value.observed_host_id == "test-home"


def test_worker_health_caches_within_ttl_and_clear_caches_busts_it(fixture_config, monkeypatch):
    calls = []

    def fake_call_worker(host_id, verb, payload, *, deadline_s):
        calls.append(verb)
        return {"result": {"n": len(calls)}}

    monkeypatch.setattr(client, "call_worker", fake_call_worker)

    first = client.worker_health("test-lab")
    second = client.worker_health("test-lab")
    assert first == second == {"n": 1}
    assert calls == ["health"]

    client.clear_caches()
    third = client.worker_health("test-lab")
    assert third == {"n": 2}
    assert calls == ["health", "health"]


def test_worker_inventory_cache_is_keyed_by_models_of_interest(fixture_config, monkeypatch):
    calls = []

    def fake_call_worker(host_id, verb, payload, *, deadline_s):
        calls.append(payload["models_of_interest"])
        return {"result": {"models": payload["models_of_interest"]}}

    monkeypatch.setattr(client, "call_worker", fake_call_worker)

    client.worker_inventory("test-lab", ["model-a"])
    client.worker_inventory("test-lab", ["model-a"])
    client.worker_inventory("test-lab", ["model-b"])
    assert calls == [["model-a"], ["model-b"]]


def test_worker_repo_probe_caches_within_ttl_and_clear_caches_busts_it(fixture_config, monkeypatch):
    """Stage 5 review finding: `eligible_hosts()` needs worker-attested
    repo-locality evidence -- `worker_repo_probe` is the client-side seam
    for it, same TTL-cache shape as `worker_health`/`worker_inventory`."""
    calls = []

    def fake_call_worker(host_id, verb, payload, *, deadline_s):
        calls.append((host_id, verb, payload["repo_id"]))
        return {"result": {"resolved": True, "path": "/repo", "head_sha": "abc", "branch": "main", "clean": True}}

    monkeypatch.setattr(client, "call_worker", fake_call_worker)

    first = client.worker_repo_probe("test-lab", "test-repo")
    second = client.worker_repo_probe("test-lab", "test-repo")
    assert first == second == {"resolved": True, "path": "/repo", "head_sha": "abc", "branch": "main", "clean": True}
    assert calls == [("test-lab", "repo.probe", "test-repo")]

    other_repo = client.worker_repo_probe("test-lab", "other-repo")
    assert other_repo["resolved"] is True
    assert calls == [("test-lab", "repo.probe", "test-repo"), ("test-lab", "repo.probe", "other-repo")]

    client.clear_caches()
    client.worker_repo_probe("test-lab", "test-repo")
    assert calls == [
        ("test-lab", "repo.probe", "test-repo"),
        ("test-lab", "repo.probe", "other-repo"),
        ("test-lab", "repo.probe", "test-repo"),
    ]


@contextmanager
def _fake_ollama_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/tags":
                body = json.dumps({"models": []}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_local_transport_subprocess_round_trip_against_fake_ollama(monkeypatch):
    """The one true end-to-end test for this stage: no fixture config, no
    monkeypatched transport — a real `LocalTransport` spawns the real
    `python -m src.estate_worker` subprocess against the shipped
    config/estate.yaml, and gets back a genuinely attested `health`
    response for a faked-reachable Ollama."""
    host_id = estate_router.current_host_id()
    if host_id is None:
        pytest.skip("this machine's hostname is not registered in config/estate.yaml")
    host_cfg = next(h for h in estate_router._load_yaml("estate")["hosts"] if h["id"] == host_id)
    if (host_cfg.get("worker") or {}).get("transport") != "local":
        pytest.skip(f"{host_id!r} is not configured for local transport")

    with _fake_ollama_server() as port:
        monkeypatch.setenv("AOTERU_WORKER_OLLAMA_BASE", f"http://127.0.0.1:{port}")
        response = client.call_worker(host_id, "health", {}, deadline_s=20)

    assert response["ok"] is True
    assert response["attestation"]["host_id"] == host_id
    assert response["result"]["ollama"] == {
        "reachable": True, "base_url": f"http://127.0.0.1:{port}", "error": None,
    }

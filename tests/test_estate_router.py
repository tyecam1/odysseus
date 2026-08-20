"""Tests for src/estate_router.py — the central model+host routing
authority (docs/aoteru-model-host-routing-contract.md, Phase B).

Uses a fixture config dir (not the real repo config/) so these tests don't
break when the real estate/models registries change, and don't depend on
this machine's actual hostname/tailnet state.
"""
import socket

import pytest
import yaml

import src.estate_router as estate_router


@pytest.fixture
def fixture_config(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    (config_dir / "estate.yaml").write_text(yaml.safe_dump({
        "hosts": [
            {"id": "test-lab", "hostname": "THIS-HOST", "role": "lab", "tailscale": True},
            {"id": "test-home", "hostname": "OTHER-HOST", "role": "home", "tailscale": False},
            {"id": "test-interface", "hostname": "INTERFACE-HOST", "role": "interface", "tailscale": True},
        ],
    }))
    (config_dir / "models.yaml").write_text(yaml.safe_dump({
        "capabilities": [
            {"alias": "local-fast", "binding": "test-model-fast"},
            {"alias": "reasoning-strong", "binding": None},
        ],
    }))

    monkeypatch.setattr(estate_router, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(socket, "gethostname", lambda: "THIS-HOST")
    return config_dir


def test_eligible_hosts_excludes_interface_role(fixture_config):
    hosts = estate_router.eligible_hosts()
    ids = {h["host_id"] for h in hosts}
    assert "test-interface" not in ids, "interface role must never be a routing candidate (invariant 9)"
    assert {"test-lab", "test-home"} == ids


def test_eligible_hosts_this_host_is_reachable_by_construction(fixture_config):
    hosts = {h["host_id"]: h for h in estate_router.eligible_hosts()}
    assert hosts["test-lab"]["eligible"] is True
    assert hosts["test-lab"]["reason"] == "this host"


def test_eligible_hosts_home_fails_truthfully_not_a_tailnet_member(fixture_config):
    hosts = {h["host_id"]: h for h in estate_router.eligible_hosts()}
    assert hosts["test-home"]["eligible"] is False
    assert "not a tailnet member" in hosts["test-home"]["reason"]


def test_resolve_alias_bound_and_live(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    result = estate_router.resolve_alias("local-fast")
    assert result == {
        "alias": "local-fast", "resolved": True,
        "concrete_model": "test-model-fast", "evidence": None,
    }


def test_resolve_alias_bound_but_not_live_fails_truthfully(fixture_config, monkeypatch):
    """P9 fault test: a config binding alone is not proof the model is
    actually loadable right now (Ollama could be down, model removed)."""
    monkeypatch.setattr(
        estate_router, "_ollama_model_live",
        lambda model, timeout=3.0: (False, "Ollama unreachable at http://127.0.0.1:11434: connection refused"),
    )
    result = estate_router.resolve_alias("local-fast")
    assert result["resolved"] is False
    assert "not currently live" in result["reason"]
    assert result["concrete_model"] == "test-model-fast"  # still reported, for diagnosis


def test_resolve_alias_unbound_fails_truthfully_not_silently(fixture_config):
    result = estate_router.resolve_alias("reasoning-strong")
    assert result["resolved"] is False
    assert "no evidence-backed binding" in result["reason"]


def test_resolve_alias_unknown(fixture_config):
    result = estate_router.resolve_alias("does-not-exist")
    assert result["resolved"] is False
    assert "unknown alias" in result["reason"]


def test_malformed_config_fails_cleanly_not_a_raw_traceback(fixture_config):
    """P9 fault test ("stale inventory"): a malformed registry file must
    raise a clear, catchable error, not an unhandled yaml.YAMLError."""
    (fixture_config / "models.yaml").write_text("not: valid: yaml: [")
    with pytest.raises(estate_router.RoutingConfigError, match="models.yaml is malformed"):
        estate_router.resolve_alias("local-fast")


def test_resolve_route_deterministic_task_needs_no_model(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    route = estate_router.resolve_route({"task_class": "audit"})
    assert route["ok"] is True
    assert route["route"]["executor"] == "deterministic"
    assert route["route"]["host"] == "test-lab"


def test_resolve_route_bound_alias_resolves_to_local(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    route = estate_router.resolve_route({
        "task_class": "coding", "requirements": {"capabilities": ["local-fast"]},
    })
    assert route["ok"] is True
    assert route["route"]["executor"] == "local"
    assert route["route"]["concrete_model"] == "test-model-fast"


def test_resolve_route_unbound_alias_needs_escalation_not_silent_failure(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    route = estate_router.resolve_route({
        "task_class": "research", "requirements": {"capabilities": ["reasoning-strong"]},
    })
    assert route["ok"] is False
    assert route["route"]["executor"] == "none"
    assert route["alias_resolution"]["resolved"] is False

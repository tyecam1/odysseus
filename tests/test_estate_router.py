"""Tests for src/estate_router.py — the central model+host routing
authority (docs/aoteru-model-host-routing-contract.md, Phase B).

Uses a fixture config dir (not the real repo config/) so these tests don't
break when the real estate/models registries change, and don't depend on
this machine's actual hostname/tailnet state.
"""
import socket
import time
from pathlib import Path

import pytest
import yaml

import src.estate_router as estate_router

_CODEX_PROCESS_GROUP_FIXTURE = Path(__file__).parent / "fixtures" / "codex_process_group_probe.sh"


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
        "paid_providers": [{"name": "codex", "concrete_model_label": "codex-cli"}],
        "default_paid_provider": "codex",
        "capabilities": [
            {"alias": "local-fast", "binding": "test-model-fast"},
            {"alias": "reasoning-strong", "binding": None},
        ],
    }))

    monkeypatch.setattr(estate_router, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(socket, "gethostname", lambda: "THIS-HOST")
    return config_dir


def _wait_for_pid_exit(pid: int, *, timeout: float = 5.0) -> bool:
    proc_path = Path(f"/proc/{pid}")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not proc_path.exists():
            return True
        time.sleep(0.05)
    return not proc_path.exists()


def test_eligible_hosts_excludes_interface_role(fixture_config):
    hosts = estate_router.eligible_hosts()
    ids = {h["host_id"] for h in hosts}
    assert "test-interface" not in ids, "interface role must never be a routing candidate (invariant 9)"
    assert {"test-lab", "test-home"} == ids


def test_eligible_hosts_this_host_is_reachable_by_construction(fixture_config):
    hosts = {h["host_id"]: h for h in estate_router.eligible_hosts()}
    assert hosts["test-lab"]["eligible"] is True
    assert hosts["test-lab"]["reason"] == "this host"


def test_current_host_id_matches_registered_hostname(fixture_config):
    assert estate_router.current_host_id() == "test-lab"


def test_current_host_id_none_when_hostname_not_registered(fixture_config, monkeypatch):
    monkeypatch.setattr(socket, "gethostname", lambda: "UNREGISTERED-HOST")
    assert estate_router.current_host_id() is None


def test_eligible_hosts_home_fails_truthfully_not_a_tailnet_member(fixture_config):
    hosts = {h["host_id"]: h for h in estate_router.eligible_hosts()}
    assert hosts["test-home"]["eligible"] is False
    assert "not a tailnet member" in hosts["test-home"]["reason"]


def test_eligible_hosts_explicit_verified_false_blocks_even_if_reachable(fixture_config):
    """Finding: 'a newly reachable but unverified home host must never
    become eligible automatically' — verified: false must gate ahead of
    (not merely alongside) live reachability."""
    estate = yaml.safe_load((fixture_config / "estate.yaml").read_text())
    for host in estate["hosts"]:
        if host["id"] == "test-home":
            host["tailscale"] = True
            host["tailscale_dns"] = "test-home.example.ts.net"
            host["verified"] = False
    (fixture_config / "estate.yaml").write_text(yaml.safe_dump(estate))

    hosts = {h["host_id"]: h for h in estate_router.eligible_hosts()}
    assert hosts["test-home"]["eligible"] is False
    assert "not verified" in hosts["test-home"]["reason"]


def test_host_reachable_missing_verified_key_defaults_true(fixture_config):
    """Existing hosts (lab/interface) that never opted into `verified`
    must not regress to ineligible."""
    reachable, reason = estate_router.host_reachable(
        {"id": "test-lab", "hostname": "THIS-HOST"}, "THIS-HOST",
    )
    assert reachable is True


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


def test_resolve_alias_gpu_heavy_eligible_when_idle(fixture_config, monkeypatch):
    """P12.4 idle state: a gpu_priority: yield_to_experiment alias resolves
    normally when no experiment is reserved/active."""
    models_path = fixture_config / "models.yaml"
    data = yaml.safe_load(models_path.read_text())
    data["capabilities"][1] = {"alias": "reasoning-strong", "binding": "test-heavy-model", "gpu_priority": "yield_to_experiment"}
    models_path.write_text(yaml.safe_dump(data))
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    monkeypatch.setattr(estate_router, "experiment_priority_active", lambda: (False, "idle"))

    result = estate_router.resolve_alias("reasoning-strong")
    assert result["resolved"] is True
    assert result["concrete_model"] == "test-heavy-model"


def test_resolve_alias_gpu_heavy_withheld_when_experiment_active(fixture_config, monkeypatch):
    """P12.4 reserved state: robotics experiments outrank background
    Aoteru model use (boundary 5) — a heavy alias must fail truthfully,
    not silently degrade or contend for the GPU, while a reservation is
    active. A non-heavy alias (local-fast) is unaffected."""
    models_path = fixture_config / "models.yaml"
    data = yaml.safe_load(models_path.read_text())
    data["capabilities"][1] = {"alias": "reasoning-strong", "binding": "test-heavy-model", "gpu_priority": "yield_to_experiment"}
    models_path.write_text(yaml.safe_dump(data))
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    monkeypatch.setattr(estate_router, "experiment_priority_active", lambda: (True, "robotics run reserved"))

    heavy = estate_router.resolve_alias("reasoning-strong")
    assert heavy["resolved"] is False
    assert "experiment priority active" in heavy["reason"]

    light = estate_router.resolve_alias("local-fast")
    assert light["resolved"] is True


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


def test_resolve_route_validates_all_capabilities_not_just_first(fixture_config, monkeypatch):
    """Finding: 'validate all requested capabilities rather than only the
    first.' Two capabilities requested, first bound+live, second unbound
    — the route must fail even though capabilities[0] alone would pass."""
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    route = estate_router.resolve_route({
        "task_class": "coding",
        "requirements": {"capabilities": ["local-fast", "reasoning-strong"]},
    })
    assert route["ok"] is False
    assert route["route"]["executor"] == "none"
    assert len(route["capability_resolutions"]) == 2
    assert route["capability_resolutions"][0]["resolved"] is True
    assert route["capability_resolutions"][1]["resolved"] is False


def test_resolve_route_all_capabilities_resolved_succeeds(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    (fixture_config / "models.yaml").write_text(yaml.safe_dump({
        "capabilities": [
            {"alias": "local-fast", "binding": "test-model-fast"},
            {"alias": "embedding", "binding": "test-model-embed"},
        ],
    }))
    route = estate_router.resolve_route({
        "task_class": "coding",
        "requirements": {"capabilities": ["local-fast", "embedding"]},
    })
    assert route["ok"] is True
    assert route["route"]["executor"] == "local"


def test_resolve_route_explicit_requested_host_narrows_eligibility(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    route = estate_router.resolve_route({
        "task_class": "audit", "placement": {"requested_host": "test-lab"},
    })
    assert route["ok"] is True
    assert route["route"]["host"] == "test-lab"


def test_resolve_route_explicit_requested_host_fails_truthfully_when_ineligible(fixture_config, monkeypatch):
    """Must not silently substitute a different (eligible) host when the
    caller explicitly asked for one that isn't eligible."""
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    route = estate_router.resolve_route({
        "task_class": "audit", "placement": {"requested_host": "test-home"},
    })
    assert route["ok"] is False
    assert "test-home" in route["error"]


def test_resolve_route_quality_floor_never_fabricated(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    route = estate_router.resolve_route({
        "task_class": "coding",
        "requirements": {"capabilities": ["local-fast"]},
        "routing": {"quality_floor": "high"},
    })
    assert route["ok"] is False
    assert "quality_floor_error" in route
    assert "no benchmarked quality" in route["quality_floor_error"]


def test_resolve_route_context_tokens_exceeding_known_window_fails_truthfully(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    monkeypatch.setattr(
        "src.model_context.get_context_length_known",
        lambda url, model: (8192, True),
    )
    route = estate_router.resolve_route({
        "task_class": "coding",
        "requirements": {"capabilities": ["local-fast"], "context_tokens": 32000},
    })
    assert route["ok"] is False
    assert "context_error" in route


def test_resolve_route_context_tokens_unknown_window_reported_not_assumed(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    monkeypatch.setattr(
        "src.model_context.get_context_length_known",
        lambda url, model: (0, False),
    )
    route = estate_router.resolve_route({
        "task_class": "coding",
        "requirements": {"capabilities": ["local-fast"], "context_tokens": 32000},
    })
    assert route["ok"] is True  # unknown != exceeded — not silently blocked either
    assert "context_note" in route
    assert "could not be verified" in route["context_note"]


def test_resolve_route_budget_fields_reported_as_unverified_not_silently_ignored(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    route = estate_router.resolve_route({
        "task_class": "audit", "budget": {"max_worker_calls": 3},
    })
    assert route["ok"] is True
    assert "budget.max_worker_calls" in route["unverified_constraints"]


def test_resolve_route_unbound_alias_needs_escalation_not_silent_failure(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    route = estate_router.resolve_route({
        "task_class": "research", "requirements": {"capabilities": ["reasoning-strong"]},
    })
    assert route["ok"] is False
    assert route["route"]["executor"] == "none"
    assert route["alias_resolution"]["resolved"] is False


# --- run_task / execute_local: closes "resolves routes but does not execute them" ---

def test_run_task_executes_local_route_and_persists_outcome(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    monkeypatch.setattr(estate_router, "execute_local", lambda model, objective, **k: {"ok": True, "output": "pong", "latency_ms": 42})
    recorded = {}
    monkeypatch.setattr(estate_router, "_update_decision_outcome", lambda decision_id, **k: recorded.update(k))

    result = estate_router.run_task({
        "task_class": "coding", "objective": "say pong",
        "requirements": {"capabilities": ["local-fast"]},
    })
    assert result["executed"] is True
    assert result["execution"]["output"] == "pong"
    assert result["deterministic_gate"] == "pass"
    assert recorded["status"] == "complete"
    assert recorded["deterministic_gate"] == "pass"


def test_run_task_passes_multimodal_objective_through_unmodified(fixture_config, monkeypatch):
    """P12.2: run_task() must carry OpenAI-style multimodal content
    (text + image_url blocks) through to execute_local() unchanged, not
    stringify or drop it — closing the gap LM4 found where vision tasks
    had to bypass run_task() and call resolve_route()+llm_call directly."""
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    received = {}

    def fake_execute_local(model, objective, **k):
        received["objective"] = objective
        return {"ok": True, "output": "7421", "latency_ms": 10}

    monkeypatch.setattr(estate_router, "execute_local", fake_execute_local)

    multimodal_objective = [
        {"type": "text", "text": "What number is shown?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
    ]
    result = estate_router.run_task({
        "task_class": "document_image_understanding",
        "objective": multimodal_objective,
        "requirements": {"capabilities": ["local-fast"]},
    })
    assert result["executed"] is True
    assert result["deterministic_gate"] == "pass"
    assert received["objective"] == multimodal_objective


def test_run_task_marks_empty_output_as_failed_gate(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    monkeypatch.setattr(estate_router, "execute_local", lambda model, objective, **k: {"ok": True, "output": "", "latency_ms": 5})
    recorded = {}
    monkeypatch.setattr(estate_router, "_update_decision_outcome", lambda decision_id, **k: recorded.update(k))

    result = estate_router.run_task({
        "task_class": "coding", "objective": "say pong",
        "requirements": {"capabilities": ["local-fast"]},
    })
    assert result["deterministic_gate"] == "fail"
    assert recorded["status"] == "failed"
    assert recorded["escalation_reason"] == "worker_failed"


def test_run_task_records_worker_disappearance_as_failed_not_a_crash(fixture_config, monkeypatch):
    """Workstream J: 'worker/model/provider disappearance mid-task' — a
    model that resolved as live at routing time but errors out entirely
    by execution time (e.g. unloaded, host restarted, Ollama itself
    down) must be recorded as a truthful failed RoutingDecision, not
    raise or silently report success. Distinct from the existing
    empty-output test above: here execute_local itself reports ok=False,
    the actual disappearance shape, not a hollow success."""
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    monkeypatch.setattr(estate_router, "execute_local", lambda model, objective, **k: {
        "ok": False, "error": "502: Upstream ... 404: model not found", "retries": 0, "latency_ms": 42,
    })
    recorded = {}
    monkeypatch.setattr(estate_router, "_update_decision_outcome", lambda decision_id, **k: recorded.update(k))

    result = estate_router.run_task({
        "task_class": "coding", "objective": "say pong",
        "requirements": {"capabilities": ["local-fast"]},
    })
    assert result["executed"] is True
    assert result["deterministic_gate"] == "fail"
    assert result["execution"]["ok"] is False
    assert recorded["status"] == "failed"
    assert recorded["escalation_reason"] == "worker_failed"


def test_run_task_does_not_execute_deterministic_route(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    called = []
    monkeypatch.setattr(estate_router, "execute_local", lambda *a, **k: called.append(1))

    result = estate_router.run_task({"task_class": "audit"})
    assert result["executed"] is False
    assert called == []


def test_run_task_does_not_execute_needs_escalation_route(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    called = []
    monkeypatch.setattr(estate_router, "execute_local", lambda *a, **k: called.append(1))

    result = estate_router.run_task({
        "task_class": "research", "objective": "prove P=NP",
        "requirements": {"capabilities": ["reasoning-strong"]},
    })
    assert result["ok"] is False
    assert result["executed"] is False
    assert called == []


def test_run_task_does_not_escalate_to_paid_without_opt_in(fixture_config, monkeypatch):
    """P12.3: a needs_escalation route stays unexecuted unless the caller
    explicitly opts in via routing.allow_paid_escalation — evidence
    triggered escalation, not automatic paid fallback for every task."""
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    called = []
    monkeypatch.setattr(estate_router, "execute_codex", lambda *a, **k: called.append(1))

    result = estate_router.run_task({
        "task_class": "research", "objective": "prove P=NP",
        "requirements": {"capabilities": ["reasoning-strong"]},
    })
    assert result["executed"] is False
    assert called == []


def test_run_task_escalates_to_codex_when_opted_in(fixture_config, monkeypatch):
    """P12.3: an unbound local alias (e.g. code-strong) with explicit
    routing.allow_paid_escalation executes against the provider-neutral
    paid worker and updates the same RoutingDecision row (executor=codex,
    escalated=True) rather than writing a second telemetry row."""
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "execute_codex",
                         lambda objective, **k: {"ok": True, "provider": "codex", "output": "done", "latency_ms": 99})
    recorded = {}
    monkeypatch.setattr(estate_router, "_update_decision_outcome", lambda decision_id, **k: recorded.update(k))

    result = estate_router.run_task({
        "task_class": "coding", "objective": "fix the bug",
        "requirements": {"capabilities": ["code-strong"]},
        "routing": {"allow_paid_escalation": True},
    })
    assert result["executed"] is True
    assert result["ok"] is True
    assert result["route"]["executor"] == "codex"
    assert result["execution"]["output"] == "done"
    assert recorded["executor"] == "codex"
    assert recorded["escalated"] is True


def test_resolve_paid_provider_uses_alias_specific_config(fixture_config, monkeypatch):
    """Workstream C: "cheap/strong paid capability aliases via config,
    not hardcoded names" — an alias with its own paid_provider entry
    must use it, not silently fall back to the default."""
    (fixture_config / "models.yaml").write_text(__import__("yaml").safe_dump({
        "paid_providers": [
            {"name": "codex", "concrete_model_label": "codex-cli"},
            {"name": "other-provider", "concrete_model_label": "other-cli"},
        ],
        "default_paid_provider": "codex",
        "capabilities": [
            {"alias": "code-strong", "binding": None, "paid_provider": "other-provider"},
        ],
    }))

    choice = estate_router._resolve_paid_provider("code-strong")
    assert choice == {"provider": "other-provider", "concrete_model_label": "other-cli"}


def test_resolve_paid_provider_falls_back_to_default(fixture_config):
    """An alias with no paid_provider of its own (or not registered at
    all) uses default_paid_provider — this is what makes an unbound alias
    like reasoning-strong (no paid_provider entry in the fixture) still
    escalate to codex today, from config rather than a hardcoded literal."""
    choice = estate_router._resolve_paid_provider("reasoning-strong")
    assert choice == {"provider": "codex", "concrete_model_label": "codex-cli"}


def test_resolve_paid_provider_no_config_fails_truthfully(fixture_config):
    (fixture_config / "models.yaml").write_text(__import__("yaml").safe_dump({
        "capabilities": [{"alias": "code-strong", "binding": None}],
    }))
    choice = estate_router._resolve_paid_provider("code-strong")
    assert choice["provider"] is None
    assert "reason" in choice


def test_run_task_uses_configured_provider_name_not_hardcoded_codex(fixture_config, monkeypatch):
    """The exact regression this change fixes: executor/concrete_model
    must come from config/models.yaml's paid_providers registry, not the
    literal strings "codex"/"codex-cli" baked into run_task()."""
    (fixture_config / "models.yaml").write_text(__import__("yaml").safe_dump({
        "paid_providers": [{"name": "codex", "concrete_model_label": "codex-cli-renamed"}],
        "default_paid_provider": "codex",
        "capabilities": [{"alias": "code-strong", "binding": None, "paid_provider": "codex"}],
    }))
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "execute_codex",
                         lambda objective, **k: {"ok": True, "provider": "codex", "output": "done", "latency_ms": 99})
    monkeypatch.setattr(estate_router, "_update_decision_outcome", lambda decision_id, **k: None)

    result = estate_router.run_task({
        "task_class": "coding", "objective": "fix the bug",
        "requirements": {"capabilities": ["code-strong"]},
        "routing": {"allow_paid_escalation": True},
    })
    assert result["route"]["concrete_model"] == "codex-cli-renamed"


def test_run_task_unresolvable_paid_provider_fails_truthfully_not_silently(fixture_config, monkeypatch):
    (fixture_config / "models.yaml").write_text(__import__("yaml").safe_dump({
        "capabilities": [{"alias": "code-strong", "binding": None}],
    }))
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    called = []
    monkeypatch.setattr(estate_router, "execute_codex", lambda *a, **k: called.append(1))

    result = estate_router.run_task({
        "task_class": "coding", "objective": "fix the bug",
        "requirements": {"capabilities": ["code-strong"]},
        "routing": {"allow_paid_escalation": True},
    })
    assert result["executed"] is False
    assert "execution_error" in result
    assert called == [], "must never fall back to codex when no provider is configured"


def test_run_task_local_route_without_objective_does_not_execute(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    called = []
    monkeypatch.setattr(estate_router, "execute_local", lambda *a, **k: called.append(1))

    result = estate_router.run_task({
        "task_class": "coding", "requirements": {"capabilities": ["local-fast"]},
    })
    assert result["executed"] is False
    assert "execution_error" in result
    assert called == []


def test_execute_local_bounds_and_reports_upstream_failure(fixture_config, monkeypatch):
    import src.model_context as model_context
    monkeypatch.setattr(model_context, "_query_context_length", lambda url, model: (131072, True))

    def _raise(*a, **k):
        raise ConnectionError("connection refused")
    monkeypatch.setattr(estate_router, "llm_call", _raise, raising=False)
    import src.llm_core as llm_core
    monkeypatch.setattr(llm_core, "llm_call", _raise)

    result = estate_router.execute_local("qwen3:8b", "hello", timeout=1.0)
    assert result["ok"] is False
    assert "connection refused" in result["error"]


def test_execute_local_retries_transient_transport_failure(fixture_config, monkeypatch):
    """A retryable failure (connection refused) gets one bounded retry and
    succeeds if the second attempt works — must not require the caller to
    retry manually for a transient blip."""
    import src.model_context as model_context
    monkeypatch.setattr(model_context, "_query_context_length", lambda url, model: (131072, True))

    calls = {"n": 0}

    def flaky(url, model, messages, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("connection refused")
        return "recovered"
    import src.llm_core as llm_core
    monkeypatch.setattr(llm_core, "llm_call", flaky)

    result = estate_router.execute_local("qwen3:8b", "hello", timeout=1.0)
    assert result["ok"] is True
    assert result["output"] == "recovered"
    assert result["retries"] == 1
    assert calls["n"] == 2


def test_execute_local_does_not_retry_deterministic_rejection(fixture_config, monkeypatch):
    """An HTTPException (e.g. bad request/model-not-found) is a deterministic
    upstream rejection — retrying it would just double latency for the same
    answer, so it must fail on the first attempt."""
    from fastapi import HTTPException
    import src.model_context as model_context
    monkeypatch.setattr(model_context, "_query_context_length", lambda url, model: (131072, True))

    calls = {"n": 0}

    def always_bad_request(url, model, messages, **kwargs):
        calls["n"] += 1
        raise HTTPException(status_code=400, detail="bad request")
    import src.llm_core as llm_core
    monkeypatch.setattr(llm_core, "llm_call", always_bad_request)

    result = estate_router.execute_local("qwen3:8b", "hello", timeout=1.0)
    assert result["ok"] is False
    assert calls["n"] == 1, "deterministic upstream rejections must not be retried"


def test_execute_local_gives_up_after_max_retries_on_persistent_transport_failure(fixture_config, monkeypatch):
    """A connection failure that never recovers must still terminate (bounded
    retry, not infinite) and report the retry count actually spent."""
    import src.model_context as model_context
    monkeypatch.setattr(model_context, "_query_context_length", lambda url, model: (131072, True))

    calls = {"n": 0}

    def always_refused(url, model, messages, **kwargs):
        calls["n"] += 1
        raise ConnectionError("connection refused")
    import src.llm_core as llm_core
    monkeypatch.setattr(llm_core, "llm_call", always_refused)

    result = estate_router.execute_local("qwen3:8b", "hello", timeout=1.0, max_retries=2)
    assert result["ok"] is False
    assert result["retries"] == 2
    assert calls["n"] == 3


def test_execute_local_uses_bounded_context_not_full_window(fixture_config, monkeypatch):
    """A1 repair: production execute_local must not blindly request a
    model's full advertised window regardless of prompt size — this is the
    exact production bug LM1 found and fixed only in the benchmark harness,
    leaving `execute_local` (the real production call path) unfixed."""
    import src.model_context as model_context
    monkeypatch.setattr(model_context, "_query_context_length", lambda url, model: (262144, True))

    captured = {}

    def fake_llm_call(url, model, messages, **kwargs):
        captured.update(kwargs)
        return "pong"
    import src.llm_core as llm_core
    monkeypatch.setattr(llm_core, "llm_call", fake_llm_call)

    result = estate_router.execute_local("qwen3.5:9b", "hello", timeout=5.0)
    assert result["ok"] is True
    assert captured["num_ctx"] < 262144, "must not request the full advertised window for a short prompt"
    assert captured["num_ctx"] >= 4096


def test_run_task_end_to_end_uses_bounded_context(fixture_config, monkeypatch):
    """Same repair, exercised through the full run_task -> execute_local ->
    llm_call production path, not just execute_local in isolation."""
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    monkeypatch.setattr(estate_router, "_update_decision_outcome", lambda *a, **k: None)

    import src.model_context as model_context
    monkeypatch.setattr(model_context, "_query_context_length", lambda url, model: (262144, True))

    captured = {}

    def fake_llm_call(url, model, messages, **kwargs):
        captured.update(kwargs)
        return "pong"
    import src.llm_core as llm_core
    monkeypatch.setattr(llm_core, "llm_call", fake_llm_call)

    result = estate_router.run_task({
        "task_class": "coding", "objective": "say pong",
        "requirements": {"capabilities": ["local-fast"]},
    })
    assert result["executed"] is True
    assert result["execution"]["output"] == "pong"
    assert captured["num_ctx"] < 262144


def test_model_config_change_and_rollback_both_take_effect_live(fixture_config):
    """Workstream J audit item: 'rollback of model/config/executor
    changes'. config/models.yaml is read fresh on every _load_yaml() call
    (no lru_cache/module-level caching anywhere in this file) — a
    binding edit takes effect on the very next resolve_alias() call, and
    critically, so does reverting it back. This is what actually makes a
    rollback safe: there is no cached/stale state anywhere in this
    process that a config revert could fail to reach."""
    models_path = fixture_config / "models.yaml"
    original = yaml.safe_load(models_path.read_text())

    assert estate_router.resolve_alias("local-fast")["concrete_model"] == "test-model-fast"

    # Simulate a model/config change (e.g. a binding swap during an
    # incident) landing live.
    changed = yaml.safe_load(models_path.read_text())
    for cap in changed["capabilities"]:
        if cap["alias"] == "local-fast":
            cap["binding"] = "test-model-changed"
    models_path.write_text(yaml.safe_dump(changed))
    assert estate_router.resolve_alias("local-fast")["concrete_model"] == "test-model-changed"

    # Roll it back — must take effect immediately too, not just the
    # forward change.
    models_path.write_text(yaml.safe_dump(original))
    assert estate_router.resolve_alias("local-fast")["concrete_model"] == "test-model-fast"


class TestResolveCodexBinary:
    """docs/aoteru-final-convergence-activation.agent-task.md item 4:
    'prefer fixing/updating tooling over disabling the sandbox'. The
    system codex-cli on this host was running against an incompatible
    bubblewrap version; a user-local install (no root needed) fixed it.
    _resolve_codex_binary must prefer that local install when present,
    without ever changing the --sandbox invocation itself."""

    def test_prefers_user_local_install_when_present(self, monkeypatch, tmp_path):
        fake_home = tmp_path
        local_bin = fake_home / ".local" / "codex-cli" / "node_modules" / ".bin" / "codex"
        local_bin.parent.mkdir(parents=True)
        local_bin.write_text("#!/bin/sh\n")
        monkeypatch.setattr(estate_router.Path, "home", lambda: fake_home)

        binary, source = estate_router._resolve_codex_binary()
        assert binary == str(local_bin)
        assert "user-local" in source

    def test_falls_back_to_system_path_when_no_local_install(self, monkeypatch, tmp_path):
        monkeypatch.setattr(estate_router.Path, "home", lambda: tmp_path)  # empty — no ~/.local/codex-cli
        import shutil as _shutil
        monkeypatch.setattr(_shutil, "which", lambda name: "/usr/bin/codex")

        binary, source = estate_router._resolve_codex_binary()
        assert binary == "/usr/bin/codex"
        assert source == "system PATH"

    def test_returns_none_when_neither_exists(self, monkeypatch, tmp_path):
        monkeypatch.setattr(estate_router.Path, "home", lambda: tmp_path)
        import shutil as _shutil
        monkeypatch.setattr(_shutil, "which", lambda name: None)

        binary, source = estate_router._resolve_codex_binary()
        assert binary is None
        assert "not found" in source


def test_execute_codex_with_sandbox_kills_entire_process_group_on_timeout(tmp_path, monkeypatch):
    pid_dir = tmp_path / "pids"
    pid_dir.mkdir()
    monkeypatch.setenv("AOTERU_TEST_PID_DIR", str(pid_dir))
    monkeypatch.setenv("AOTERU_TEST_MODE", "timeout")
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, str(_CODEX_PROCESS_GROUP_FIXTURE)))

    started = time.monotonic()
    result = estate_router._execute_codex_with_sandbox(
        "timeout probe", sandbox="read-only", provider="codex", timeout=1.0, cwd=str(tmp_path),
    )
    elapsed = time.monotonic() - started

    assert result == {
        "ok": False,
        "provider": "codex",
        "error": "codex exec timed out after 1.0s",
        "latency_ms": result["latency_ms"],
    }
    # Must return promptly after the 1s worker timeout, not block for
    # anywhere near the fixture child's full 30s natural lifetime - a slow
    # return here would mean cleanup is relying on the child dying on its
    # own rather than actually killing it (see the leader-exits test below
    # for exactly this masking failure mode against the prior
    # implementation).
    assert elapsed < 10.0, f"took {elapsed:.1f}s to return - cleanup should be prompt, not waiting on natural exit"
    wrapper_pid = int((pid_dir / "wrapper.pid").read_text().strip())
    child_pid = int((pid_dir / "child.pid").read_text().strip())
    assert _wait_for_pid_exit(wrapper_pid), f"wrapper pid {wrapper_pid} still exists after timeout cleanup"
    assert _wait_for_pid_exit(child_pid), f"child pid {child_pid} still exists after timeout cleanup"


def test_execute_codex_with_sandbox_kills_descendant_when_leader_exits_first(tmp_path, monkeypatch):
    """Adversarial case controller review flagged: the wrapper/group leader
    can exit before the timeout fires (e.g. it forked a detached child and
    returned), leaving os.getpgid(proc.pid) unable to resolve a live
    process by the time cleanup runs - but a descendant, which inherited
    the same process group independent of the leader continuing to exist,
    is still alive and still holds the inherited stdout/stderr pipe open,
    so parent-side communicate() still times out.

    A plain background job in this fixture stays a reachable zombie under
    this test process until reaped, so os.getpgid(proc.pid) would still
    happen to succeed even under the old (buggy) code in that narrow case -
    that is exactly why this test forces the failure os.getpgid() would hit
    in the wider real case (the leader pid no longer resolving at all, for
    any reason - reaped by something else, a stale/reused pid, etc.)
    directly, rather than relying on incidental zombie-reaping timing. The
    retained process_group_id (captured immediately after Popen, never
    rediscovered afterward) must still be enough to kill the descendant
    even when os.getpgid(proc.pid) would raise."""
    pid_dir = tmp_path / "pids"
    pid_dir.mkdir()
    monkeypatch.setenv("AOTERU_TEST_PID_DIR", str(pid_dir))
    monkeypatch.setenv("AOTERU_TEST_MODE", "leader_exits_child_survives")
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, str(_CODEX_PROCESS_GROUP_FIXTURE)))

    import os as _os

    def _getpgid_fails_like_a_reaped_leader(pid):
        raise ProcessLookupError(f"simulated: pid {pid} no longer resolves by cleanup time")

    monkeypatch.setattr(_os, "getpgid", _getpgid_fails_like_a_reaped_leader)

    started = time.monotonic()
    result = estate_router._execute_codex_with_sandbox(
        "leader-exits probe", sandbox="read-only", provider="codex", timeout=1.0, cwd=str(tmp_path),
    )
    elapsed = time.monotonic() - started

    assert result == {
        "ok": False,
        "provider": "codex",
        "error": "codex exec timed out after 1.0s",
        "latency_ms": result["latency_ms"],
    }
    # The critical proof, not just a nice-to-have: against the prior
    # implementation (os.killpg(os.getpgid(proc.pid), ...) plus an
    # unbounded final proc.communicate()), killpg never runs here (getpgid
    # raises), so the descendant is never actually killed - it only dies
    # ~30s later on its own, once its sleep completes, while the unbounded
    # communicate() blocks the whole call waiting for that. By the time
    # _wait_for_pid_exit runs afterward the descendant would already be
    # gone *on its own*, incorrectly satisfying a PID-existence-only
    # assertion and masking the fact that cleanup never actually killed
    # anything. This wall-clock bound is what actually distinguishes
    # "killed promptly" from "happened to die naturally while we waited".
    assert elapsed < 10.0, (
        f"took {elapsed:.1f}s to return - if this is anywhere near the fixture "
        "child's full 30s sleep, cleanup let it die naturally instead of killing it"
    )
    child_pid = int((pid_dir / "child.pid").read_text().strip())
    assert _wait_for_pid_exit(child_pid), (
        f"descendant pid {child_pid} still exists after timeout cleanup - "
        "cleanup must not depend on os.getpgid(proc.pid) resolving"
    )


def test_execute_codex_with_sandbox_success_shape_unchanged(tmp_path, monkeypatch):
    pid_dir = tmp_path / "pids"
    pid_dir.mkdir()
    monkeypatch.setenv("AOTERU_TEST_PID_DIR", str(pid_dir))
    monkeypatch.setenv("AOTERU_TEST_MODE", "success")
    monkeypatch.setenv("AOTERU_TEST_OUTPUT_TEXT", "fixture success output")
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, str(_CODEX_PROCESS_GROUP_FIXTURE)))

    result = estate_router._execute_codex_with_sandbox(
        "success probe", sandbox="read-only", provider="codex", timeout=5.0, cwd=str(tmp_path),
    )

    assert result["ok"] is True
    assert result["provider"] == "codex"
    assert result["output"] == "fixture success output"
    assert result["codex_binary"] == str(_CODEX_PROCESS_GROUP_FIXTURE)
    assert isinstance(result["latency_ms"], int)


class TestResolveRepoPath:
    """docs/aoteru-final-convergence-activation.agent-task.md item 4:
    grounding a paid-escalation task in its actual repo. Regression
    coverage for the exact live-confirmed bug: run_task()'s codex
    escalation previously never passed cwd, so a real repo_reconnaissance
    task reported 'No src/ directory found' — it was pointed at an empty
    scratch dir regardless of task['repo']."""

    def _fixture_repos(self, config_dir, real_repo_path):
        (config_dir / "repositories.yaml").write_text(yaml.safe_dump({
            "repos": [
                {"id": "test-repo", "path": "${TEST_ROOT}/test-repo"},
                {"id": "literal-path-repo", "path": str(real_repo_path)},
            ],
        }))

    def test_resolves_via_host_local_root_var(self, fixture_config, monkeypatch, tmp_path):
        real_path = tmp_path / "resolved" / "test-repo"
        real_path.mkdir(parents=True)
        self._fixture_repos(fixture_config, real_path)

        home = tmp_path / "fakehome"
        (home / ".aoteru").mkdir(parents=True)
        (home / ".aoteru" / "config.local.json").write_text(
            __import__("json").dumps({"TEST_ROOT": str(tmp_path / "resolved")})
        )
        monkeypatch.setattr(estate_router.Path, "home", lambda: home)

        assert estate_router.resolve_repo_path("test-repo") == str(real_path)

    def test_unknown_repo_id_returns_none(self, fixture_config, monkeypatch, tmp_path):
        self._fixture_repos(fixture_config, tmp_path)
        monkeypatch.setattr(estate_router.Path, "home", lambda: tmp_path / "fakehome")
        assert estate_router.resolve_repo_path("does-not-exist") is None

    def test_unset_root_var_returns_none_not_a_guess(self, fixture_config, monkeypatch, tmp_path):
        self._fixture_repos(fixture_config, tmp_path)
        home = tmp_path / "fakehome-no-config"
        monkeypatch.setattr(estate_router.Path, "home", lambda: home)  # no config.local.json at all
        assert estate_router.resolve_repo_path("test-repo") is None

    def test_root_set_but_path_missing_returns_none(self, fixture_config, monkeypatch, tmp_path):
        self._fixture_repos(fixture_config, tmp_path)
        home = tmp_path / "fakehome2"
        (home / ".aoteru").mkdir(parents=True)
        (home / ".aoteru" / "config.local.json").write_text(
            __import__("json").dumps({"TEST_ROOT": str(tmp_path / "nonexistent-root")})
        )
        monkeypatch.setattr(estate_router.Path, "home", lambda: home)
        assert estate_router.resolve_repo_path("test-repo") is None


def test_run_task_paid_escalation_grounds_codex_in_the_named_repo(fixture_config, monkeypatch, tmp_path):
    """The exact live-confirmed regression: without cwd grounding, codex
    escalation always ran against an empty scratch dir regardless of
    task['repo']."""
    (fixture_config / "models.yaml").write_text(yaml.safe_dump({
        "paid_providers": [{"name": "codex", "concrete_model_label": "codex-cli"}],
        "default_paid_provider": "codex",
        "capabilities": [{"alias": "code-strong", "binding": None, "paid_provider": "codex"}],
    }))
    (fixture_config / "repositories.yaml").write_text(yaml.safe_dump({
        "repos": [{"id": "test-repo", "path": "${TEST_ROOT}/test-repo"}],
    }))
    real_path = tmp_path / "resolved" / "test-repo"
    real_path.mkdir(parents=True)
    home = tmp_path / "fakehome"
    (home / ".aoteru").mkdir(parents=True)
    (home / ".aoteru" / "config.local.json").write_text(
        __import__("json").dumps({"TEST_ROOT": str(tmp_path / "resolved")})
    )
    monkeypatch.setattr(estate_router.Path, "home", lambda: home)

    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "_update_decision_outcome", lambda *a, **k: None)
    captured = {}

    def fake_execute_codex(objective, **kwargs):
        captured.update(kwargs)
        return {"ok": True, "provider": "codex", "output": "done", "latency_ms": 1}
    monkeypatch.setattr(estate_router, "execute_codex", fake_execute_codex)

    estate_router.run_task({
        "task_class": "coding", "objective": "fix the bug", "repo": "test-repo",
        "requirements": {"capabilities": ["code-strong"]},
        "routing": {"allow_paid_escalation": True},
    })
    assert captured["cwd"] == str(real_path)


def test_run_task_paid_escalation_without_repo_field_passes_no_cwd_override(fixture_config, monkeypatch):
    """No task['repo'] named at all — must not guess a cwd; execute_codex
    keeps its own default (empty scratch dir) rather than this function
    inventing a path."""
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "fake-decision-id")
    monkeypatch.setattr(estate_router, "_update_decision_outcome", lambda *a, **k: None)
    captured = {}

    def fake_execute_codex(objective, **kwargs):
        captured.update(kwargs)
        return {"ok": True, "provider": "codex", "output": "done", "latency_ms": 1}
    monkeypatch.setattr(estate_router, "execute_codex", fake_execute_codex)

    estate_router.run_task({
        "task_class": "coding", "objective": "fix the bug",
        "requirements": {"capabilities": ["code-strong"]},
        "routing": {"allow_paid_escalation": True},
    })
    assert captured["cwd"] is None


def test_scenario_a_implementation_mode_dispatches_codex_write_under_active_lease(
        fixture_config, monkeypatch, tmp_path):
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()
    worktree_path = tmp_path / "aoteru-worktrees" / "test-repo" / "feature"
    worktree_path.mkdir(parents=True)
    (fixture_config / "repositories.yaml").write_text(yaml.safe_dump({
        "repos": [{"id": "test-repo", "path": str(repo_path)}],
    }))
    recorded_route = {}
    recorded_outcome = {}

    def fake_record(task, **kwargs):
        recorded_route.update(task=task, **kwargs)
        return "implementation-decision"

    monkeypatch.setattr(estate_router, "_record_decision", fake_record)
    monkeypatch.setattr(
        estate_router, "active_lease_for_repo",
        lambda repo_id, host_id: {
            "lease_id": "lease-1", "repo_id": repo_id, "host_id": host_id,
            "worktree_path": str(worktree_path), "branch": "feature/demo", "allowed_write_scope": "repo",
        },
    )
    monkeypatch.setattr(estate_router.worktree_ops, "is_live_checkout_path", lambda repo_id, path: False)
    monkeypatch.setattr(
        estate_router.worktree_ops,
        "verify_worktree",
        lambda repo_id, path, branch: {"ok": True, "path": str(worktree_path), "branch": branch},
    )
    captured = {}

    def fake_codex_process(objective, **kwargs):
        captured.update(objective=objective, **kwargs)
        return {"ok": True, "provider": "codex-write", "output": "implemented", "latency_ms": 12}

    monkeypatch.setattr(estate_router, "_execute_codex_with_sandbox", fake_codex_process)
    monkeypatch.setattr(
        estate_router, "_update_decision_outcome",
        lambda decision_id, **kwargs: recorded_outcome.update(decision_id=decision_id, **kwargs),
    )

    result = estate_router.run_task({
        "task_class": "bounded_code_implementation", "objective": "implement it", "repo": "test-repo",
        "requirements": {"capabilities": ["reasoning-strong"]},
        "routing": {"allow_paid_escalation": True, "mode": "implementation"},
    })

    assert result["ok"] is True
    assert result["executed"] is True
    assert result["route"]["executor"] == "codex-write"
    assert captured["objective"] == "implement it"
    assert captured["cwd"] == str(worktree_path)
    assert captured["sandbox"] == "workspace-write"
    assert recorded_route["task"]["recommended_route"] == "codex_eligible"
    assert recorded_outcome["actual_route"] == "codex-write"
    assert recorded_outcome["executor"] == "codex-write"
    assert recorded_outcome["verification_outcome"] == "pass"


def test_record_decision_rejects_invalid_nondelegation_reason_even_off_preflight_path(fixture_config):
    """`/api/estate/route` and `/api/estate/run` accept `nondelegation_reason`
    on the raw envelope (routes/estate_routing_routes.py) without routing
    through `delegation_preflight`'s validation — `_record_decision` must
    re-validate itself so a caller can't stamp an arbitrary/junk reason
    onto telemetry by skipping `/api/estate/preflight`."""
    from src.routing_evaluator import get_decision_by_id

    junk_id = estate_router._record_decision(
        {"task_class": "audit", "nondelegation_reason": "because I said so"},
        host_id="test-lab", executor="deterministic", model_alias=None,
        concrete_model=None, status="complete",
    )
    assert get_decision_by_id(junk_id)["nondelegation_reason"] is None

    fixed_id = estate_router._record_decision(
        {"task_class": "audit", "nondelegation_reason": "architecture_judgement"},
        host_id="test-lab", executor="deterministic", model_alias=None,
        concrete_model=None, status="complete",
    )
    assert get_decision_by_id(fixed_id)["nondelegation_reason"] == "architecture_judgement"

    freeform_id = estate_router._record_decision(
        {"task_class": "audit", "nondelegation_reason": "other: bespoke evidence-backed reason"},
        host_id="test-lab", executor="deterministic", model_alias=None,
        concrete_model=None, status="complete",
    )
    assert get_decision_by_id(freeform_id)["nondelegation_reason"] == "other: bespoke evidence-backed reason"


def test_implementation_mode_without_active_lease_hard_fails(fixture_config, monkeypatch, tmp_path):
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()
    (fixture_config / "repositories.yaml").write_text(yaml.safe_dump({
        "repos": [{"id": "test-repo", "path": str(repo_path)}],
    }))
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "implementation-decision")
    monkeypatch.setattr(estate_router, "active_lease_for_repo", lambda repo_id, host_id: None)
    called = []
    monkeypatch.setattr(estate_router, "_execute_codex_with_sandbox", lambda *a, **k: called.append(True))
    monkeypatch.setattr(estate_router, "_update_decision_outcome", lambda *a, **k: None)

    result = estate_router.run_task({
        "task_class": "bounded_code_implementation", "objective": "implement it", "repo": "test-repo",
        "requirements": {"capabilities": ["reasoning-strong"]},
        "routing": {"allow_paid_escalation": True, "mode": "implementation"},
    })

    assert result["ok"] is False
    assert result["executed"] is False
    assert "active non-stale lease" in result["execution_error"]
    assert called == []


def test_codex_write_authority_denies_live_checkout_path_even_if_leased(fixture_config, monkeypatch, tmp_path):
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()
    (fixture_config / "repositories.yaml").write_text(yaml.safe_dump({
        "repos": [{"id": "test-repo", "path": str(repo_path)}],
    }))
    monkeypatch.setattr(
        estate_router,
        "active_lease_for_repo",
        lambda repo_id, host_id: {
            "lease_id": "lease-1",
            "repo_id": repo_id,
            "host_id": host_id,
            "worktree_path": str(repo_path),
            "branch": "feature/demo",
            "allowed_write_scope": "repo",
        },
    )
    monkeypatch.setattr(estate_router.worktree_ops, "is_live_checkout_path", lambda repo_id, path: True)

    result = estate_router._codex_write_authority("test-repo", "test-lab")

    assert result["ok"] is False
    assert "live registered checkout" in result["error"]


def test_codex_write_authority_denies_invalid_or_mismatched_worktree(fixture_config, monkeypatch, tmp_path):
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()
    bad_worktree = tmp_path / "not-a-real-worktree"
    bad_worktree.mkdir()
    (fixture_config / "repositories.yaml").write_text(yaml.safe_dump({
        "repos": [{"id": "test-repo", "path": str(repo_path)}],
    }))
    monkeypatch.setattr(
        estate_router,
        "active_lease_for_repo",
        lambda repo_id, host_id: {
            "lease_id": "lease-1",
            "repo_id": repo_id,
            "host_id": host_id,
            "worktree_path": str(bad_worktree),
            "branch": "feature/demo",
            "allowed_write_scope": "repo",
        },
    )
    monkeypatch.setattr(estate_router.worktree_ops, "is_live_checkout_path", lambda repo_id, path: False)
    monkeypatch.setattr(
        estate_router.worktree_ops,
        "verify_worktree",
        lambda repo_id, path, branch: {"ok": False, "reason": "path is not a registered linked git worktree for this repo"},
    )

    result = estate_router._codex_write_authority("test-repo", "test-lab")

    assert result["ok"] is False
    assert "failed verification" in result["error"]


def test_scenario_b_repetitive_compute_dispatches_to_remote_local_executor(fixture_config, monkeypatch):
    monkeypatch.setattr(estate_router, "_record_decision", lambda *a, **k: "remote-decision")
    monkeypatch.setattr(estate_router, "_ollama_model_live", lambda model, timeout=3.0: (True, "live"))
    monkeypatch.setattr(
        estate_router, "execute_local",
        lambda model, objective, **kwargs: {"ok": True, "output": "scan complete", "latency_ms": 4},
    )
    outcome = {}
    monkeypatch.setattr(estate_router, "_update_decision_outcome", lambda decision_id, **kwargs: outcome.update(kwargs))

    result = estate_router.run_task({
        "task_class": "batch_repository_scan", "objective": "scan repository",
        "requirements": {"capabilities": ["local-fast"]},
    })

    assert result["executed"] is True
    assert result["route"]["host"] == "test-lab"
    assert result["route"]["executor"] == "local"
    assert outcome["actual_route"] == "local"


@pytest.mark.parametrize(
    ("executor", "expected_sandbox"),
    [("execute_codex", "read-only"), ("execute_codex_write", "workspace-write")],
)
def test_codex_lanes_preserve_distinct_sandbox_authority(
        fixture_config, monkeypatch, tmp_path, executor, expected_sandbox):
    import subprocess

    monkeypatch.setattr(estate_router, "_codex_available", lambda: (True, "codex"))
    captured = {}

    class FakeProc:
        def __init__(self, args, **kwargs):
            captured["args"] = args
            output_path = args[args.index("-o") + 1]
            estate_router.Path(output_path).write_text("done")
            self.returncode = 0
            self.pid = 4242

        def communicate(self, timeout=None):
            return ("", "")

    monkeypatch.setattr(subprocess, "Popen", FakeProc)
    fn = getattr(estate_router, executor)
    if executor == "execute_codex_write":
        worktree_path = tmp_path / "isolated-worktree"
        worktree_path.mkdir()
        monkeypatch.setattr(estate_router, "resolve_repo_path", lambda repo_id: str(tmp_path))
        monkeypatch.setattr(estate_router, "active_lease_for_repo", lambda repo_id, host_id: {
            "lease_id": "lease-1", "worktree_path": str(worktree_path), "branch": "feature/demo", "allowed_write_scope": "repo",
        })
        monkeypatch.setattr(estate_router.worktree_ops, "is_live_checkout_path", lambda repo_id, path: False)
        monkeypatch.setattr(
            estate_router.worktree_ops,
            "verify_worktree",
            lambda repo_id, path, branch: {"ok": True, "path": str(worktree_path), "branch": branch},
        )
        result = fn("do it", repo_id="test-repo", host_id="test-lab")
    else:
        result = fn("do it", cwd=str(tmp_path))

    assert result["ok"] is True
    sandbox_index = captured["args"].index("--sandbox")
    assert captured["args"][sandbox_index + 1] == expected_sandbox

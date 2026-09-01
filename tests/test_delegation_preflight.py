"""Acceptance coverage for the delegation preflight boundary."""
import pytest
import src.delegation_preflight as preflight


def _hosts(eligible=True):
    return [{
        "host_id": "test-lab", "role": "lab", "eligible": eligible,
        "reason": "this host" if eligible else "unreachable: refused",
    }]


def _route(*, ok=True, executor="local", hosts=None):
    checked = hosts if hosts is not None else _hosts()
    route = {"host": "test-lab", "executor": executor, "model_alias": "local-fast",
             "concrete_model": "test-model", "reason": "live route"} if any(
                 host["eligible"] for host in checked
             ) else None
    return {
        "ok": ok, "route": route, "hosts_checked": checked,
        "capability_resolutions": [{"alias": "local-fast", "resolved": ok}],
        "reason": "live route" if route else "no eligible host",
        "error": None if route else "no eligible host",
    }


def test_scenario_a_substantial_code_recommends_live_codex(monkeypatch):
    monkeypatch.setattr(preflight.estate_router, "eligible_hosts", lambda repo_id=None: _hosts())
    monkeypatch.setattr(preflight.estate_router, "_codex_available", lambda: (True, "/bin/codex"))
    monkeypatch.setattr(preflight.estate_router, "current_host_id", lambda: "test-lab")
    monkeypatch.setattr(
        preflight.estate_router,
        "_codex_write_authority",
        lambda repo_id, host_id: {"ok": True, "lease_id": "lease-1", "cwd": "/tmp/worktree"},
    )
    monkeypatch.setattr(
        preflight.estate_router, "resolve_route",
        lambda task, record_decision=False: {
            **_route(ok=False, executor="none"),
            "route": {"host": "test-lab", "executor": "none", "model_alias": "code-strong",
                      "concrete_model": None, "reason": "local alias unbound"},
            "capability_resolutions": [{"alias": "code-strong", "resolved": False,
                                         "reason": "no evidence-backed binding"}],
        },
    )
    monkeypatch.setattr(preflight.estate_router, "_resolve_paid_provider", lambda alias: {"provider": "codex"})

    result = preflight.delegation_preflight([{
        "task_class": "bounded_code_implementation", "repo": "odysseus",
        "objective": "Implement the bounded router change",
    }])

    unit = result["units"][0]
    assert result["ok"] is True
    assert unit["classification"] == "codex_eligible"
    assert unit["recommended_route"] == "codex-write"
    assert unit["write_authority"]["ready"] is True
    assert "Codex is live" in unit["reason"]


def test_scenario_b_repetitive_compute_recommends_remote_worker(monkeypatch):
    monkeypatch.setattr(preflight.estate_router, "eligible_hosts", lambda repo_id=None: _hosts())
    monkeypatch.setattr(preflight.estate_router, "_codex_available", lambda: (False, "not needed"))
    monkeypatch.setattr(preflight.estate_router, "resolve_route", lambda task, record_decision=False: _route())

    result = preflight.delegation_preflight([{
        "task_class": "batch_repository_scan", "capabilities": ["local-fast"],
    }])

    unit = result["units"][0]
    assert unit["classification"] == "remote_compute_eligible"
    assert unit["route"]["host"] == "test-lab"
    assert unit["route"]["executor"] == "local"
    assert unit["ok"] is True


def test_scenario_c_controller_retention_requires_valid_reason(monkeypatch):
    monkeypatch.setattr(preflight.estate_router, "eligible_hosts", lambda repo_id=None: _hosts())
    monkeypatch.setattr(preflight.estate_router, "_codex_available", lambda: (True, "/bin/codex"))
    monkeypatch.setattr(preflight.estate_router, "current_host_id", lambda: "test-lab")
    recorded = {}
    monkeypatch.setattr(
        preflight.estate_router, "_record_decision",
        lambda task, **kwargs: recorded.update(task=task, **kwargs) or "retained-decision",
    )

    missing = preflight.delegation_preflight([{"task_class": "architecture_judgement"}])
    invalid = preflight.delegation_preflight([{
        "task_class": "architecture_judgement", "nondelegation_reason": "because I prefer it",
    }])
    valid = preflight.delegation_preflight([{
        "task_class": "architecture_judgement", "nondelegation_reason": "architecture_judgement",
    }])

    assert missing["units"][0]["requires_justification"] is True
    assert invalid["units"][0]["ok"] is False
    assert valid["units"][0]["ok"] is True
    assert valid["units"][0]["actual_route"] == "controller"
    assert recorded["task"]["nondelegation_reason"] == "architecture_judgement"
    assert recorded["executor"] == "controller"


def test_known_delegable_unit_cannot_be_silently_retained(monkeypatch):
    monkeypatch.setattr(preflight.estate_router, "eligible_hosts", lambda repo_id=None: _hosts())
    monkeypatch.setattr(preflight.estate_router, "_codex_available", lambda: (True, "/bin/codex"))

    result = preflight.delegation_preflight([{
        "task_class": "code_refactor", "requested_route": "controller_retained",
    }])

    unit = result["units"][0]
    assert unit["ok"] is False
    assert unit["requires_justification"] is True
    assert unit["recommended_route"] == "codex_eligible"


def test_scenario_d_codex_unavailable_rejects_with_live_evidence(monkeypatch):
    monkeypatch.setattr(preflight.estate_router, "eligible_hosts", lambda repo_id=None: _hosts())
    monkeypatch.setattr(preflight.estate_router, "_codex_available", lambda: (False, "no auth on this host"))
    monkeypatch.setattr(preflight.estate_router, "_resolve_paid_provider", lambda alias: {"provider": "codex"})
    monkeypatch.setattr(
        preflight.estate_router, "resolve_route",
        lambda task, record_decision=False: {
            **_route(ok=False, executor="none"),
            "route": {"host": "test-lab", "executor": "none", "model_alias": "code-strong"},
        },
    )

    result = preflight.delegation_preflight([{"task_class": "code_implementation"}])

    assert result["ok"] is False
    assert "codex unavailable: no auth on this host" in result["units"][0]["reason"]


def test_codex_write_preflight_rejects_missing_existing_lease(monkeypatch):
    monkeypatch.setattr(preflight.estate_router, "eligible_hosts", lambda repo_id=None: _hosts())
    monkeypatch.setattr(preflight.estate_router, "_codex_available", lambda: (True, "/bin/codex"))
    monkeypatch.setattr(preflight.estate_router, "current_host_id", lambda: "test-lab")
    monkeypatch.setattr(
        preflight.estate_router,
        "_codex_write_authority",
        lambda repo_id, host_id: {
            "ok": False,
            "error": f"implementation mode requires an active non-stale lease for {repo_id!r} held by {host_id!r}",
        },
    )
    monkeypatch.setattr(preflight.estate_router, "_resolve_paid_provider", lambda alias: {"provider": "codex"})
    monkeypatch.setattr(
        preflight.estate_router, "resolve_route",
        lambda task, record_decision=False: {
            **_route(ok=False, executor="none"),
            "route": {"host": "test-lab", "executor": "none", "model_alias": "code-strong"},
        },
    )

    result = preflight.delegation_preflight([{
        "task_class": "code_implementation", "repo": "odysseus",
    }])

    assert result["ok"] is False
    assert result["units"][0]["write_authority"]["ready"] is False
    assert "active non-stale lease" in result["units"][0]["reason"]


def test_codex_write_preflight_uses_authority_result_when_ready(monkeypatch):
    monkeypatch.setattr(preflight.estate_router, "eligible_hosts", lambda repo_id=None: _hosts())
    monkeypatch.setattr(preflight.estate_router, "_codex_available", lambda: (True, "/bin/codex"))
    monkeypatch.setattr(preflight.estate_router, "current_host_id", lambda: "test-lab")
    monkeypatch.setattr(preflight.estate_router, "active_lease_for_repo", lambda repo_id, host_id: (_ for _ in ()).throw(AssertionError("preflight must not reimplement write authority via active_lease_for_repo")))
    calls = []
    monkeypatch.setattr(
        preflight.estate_router,
        "_codex_write_authority",
        lambda repo_id, host_id: calls.append((repo_id, host_id)) or {"ok": True, "lease_id": "lease-iso", "cwd": "/tmp/isolated"},
    )
    monkeypatch.setattr(preflight.estate_router, "_resolve_paid_provider", lambda alias: {"provider": "codex"})
    monkeypatch.setattr(
        preflight.estate_router, "resolve_route",
        lambda task, record_decision=False: {
            **_route(ok=False, executor="none"),
            "route": {"host": "test-lab", "executor": "none", "model_alias": "code-strong"},
        },
    )

    result = preflight.delegation_preflight([{
        "task_class": "code_implementation", "repo": "odysseus",
    }])

    unit = result["units"][0]
    assert unit["ok"] is True
    assert unit["write_authority"] == {
        "ready": True,
        "host_id": "test-lab",
        "lease_id": "lease-iso",
        "reason": "active non-stale repo lease matches the execution host",
    }
    assert calls == [("odysseus", "test-lab")]


@pytest.mark.parametrize("authority_error", [
    "refusing implementation mode in live registered checkout for 'odysseus'",
    "active lease for 'odysseus' is missing an enforced branch",
    "active lease worktree for 'odysseus' failed verification: branch mismatch",
    "active lease worktree for 'odysseus' failed verification: path is not a registered linked git worktree for this repo",
])
def test_codex_write_preflight_surfaces_authority_denial_reason(monkeypatch, authority_error):
    monkeypatch.setattr(preflight.estate_router, "eligible_hosts", lambda repo_id=None: _hosts())
    monkeypatch.setattr(preflight.estate_router, "_codex_available", lambda: (True, "/bin/codex"))
    monkeypatch.setattr(preflight.estate_router, "current_host_id", lambda: "test-lab")
    monkeypatch.setattr(preflight.estate_router, "active_lease_for_repo", lambda repo_id, host_id: (_ for _ in ()).throw(AssertionError("preflight must not use active_lease_for_repo directly")))
    monkeypatch.setattr(
        preflight.estate_router,
        "_codex_write_authority",
        lambda repo_id, host_id: {"ok": False, "error": authority_error},
    )
    monkeypatch.setattr(preflight.estate_router, "_resolve_paid_provider", lambda alias: {"provider": "codex"})
    monkeypatch.setattr(
        preflight.estate_router, "resolve_route",
        lambda task, record_decision=False: {
            **_route(ok=False, executor="none"),
            "route": {"host": "test-lab", "executor": "none", "model_alias": "code-strong"},
        },
    )

    result = preflight.delegation_preflight([{
        "task_class": "code_implementation", "repo": "odysseus",
    }])

    unit = result["units"][0]
    assert unit["ok"] is False
    assert unit["write_authority"] == {
        "ready": False,
        "host_id": "test-lab",
        "lease_id": None,
        "reason": authority_error,
    }
    assert unit["reason"] == authority_error


def test_read_only_code_review_with_repo_does_not_require_write_lease(monkeypatch):
    monkeypatch.setattr(preflight.estate_router, "eligible_hosts", lambda repo_id=None: _hosts())
    monkeypatch.setattr(preflight.estate_router, "_codex_available", lambda: (True, "/bin/codex"))
    monkeypatch.setattr(preflight.estate_router, "_resolve_paid_provider", lambda alias: {"provider": "codex"})
    monkeypatch.setattr(
        preflight.estate_router, "resolve_route",
        lambda task, record_decision=False: {
            **_route(ok=False, executor="none"),
            "route": {"host": "test-lab", "executor": "none", "model_alias": "code-strong"},
        },
    )

    result = preflight.delegation_preflight([{
        "task_class": "code_review", "repo": "odysseus",
    }])

    assert result["ok"] is True
    assert result["units"][0]["recommended_route"] == "codex"
    assert result["units"][0]["write_authority"] is None


def test_scenario_d_worker_unavailable_rejects_with_host_evidence(monkeypatch):
    unavailable = _hosts(eligible=False)
    monkeypatch.setattr(preflight.estate_router, "eligible_hosts", lambda repo_id=None: unavailable)
    monkeypatch.setattr(preflight.estate_router, "_codex_available", lambda: (True, "/bin/codex"))
    monkeypatch.setattr(
        preflight.estate_router, "resolve_route",
        lambda task, record_decision=False: _route(ok=False, executor="none", hosts=unavailable),
    )

    result = preflight.delegation_preflight([{"task_class": "batch_index_evaluation"}])

    assert result["ok"] is False
    assert result["units"][0]["reason"] == "no eligible host"
    assert result["snapshot"]["eligible_hosts"][0]["reason"] == "unreachable: refused"

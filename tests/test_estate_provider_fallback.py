"""Regression coverage for Codex quota cooldown and bounded GLM fallback."""
import json
import os
import socket
from datetime import datetime, timedelta

import pytest
import yaml

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()

import core.database as cdb
from core.database import EstateExecution, ParkLease, get_db_session
from src import estate_router
from src import estate_write_lane as lane
from src.estate_provider_quota import ProviderCooldown, ProviderUnavailable, resolve_provider
from tests.helpers.fake_worker import FakeWorker


NOW = datetime(2026, 10, 19, 14, 0)
HOST = "test-lab"
QUOTA_ERROR = "Usage limit reached; try again at 2:30 PM"
BALANCE_429 = (
    "API Error: Request rejected (429) ... "
    "[1113][Insufficient balance or no resource package]"
)


def _task(*, implementation=False):
    routing = {"allow_paid_escalation": True}
    if implementation:
        routing["mode"] = "implementation"
    return {
        "task_class": "bounded_code_implementation" if implementation else "coding",
        "objective": "implement it" if implementation else "inspect it",
        "repo": "odysseus",
        "requirements": {"capabilities": ["code-strong"]},
        "routing": routing,
    }


def _placement():
    return {
        "routed_host": HOST, "executed_host": HOST, "attested": True,
        "transport": "local", "observed_host": HOST,
    }


@pytest.fixture
def fallback_router(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    (config / "models.yaml").write_text(yaml.safe_dump({
        "paid_providers": [
            {"name": "codex", "concrete_model_label": "codex-cli"},
            {"name": "glm", "concrete_model_label": "glm-5.3", "launcher": "claude-glm",
             "candidate_only": True, "allow_quota_fallback": True},
        ],
        "default_paid_provider": "codex",
        "capabilities": [{"alias": "code-strong", "binding": None, "paid_provider": "codex"}],
    }))
    qualified = ["codex", "codex-write", "glm", "glm-write"]
    (config / "estate.yaml").write_text(yaml.safe_dump({
        "hosts": [{
            "id": HOST, "hostname": "THIS-HOST", "role": "lab", "identity_verified": True,
            "worker": {"enabled": True, "transport": "local", "qualified_executors": qualified},
        }],
    }))
    monkeypatch.setattr(estate_router, "_CONFIG_DIR", config)
    monkeypatch.setattr(socket, "gethostname", lambda: "THIS-HOST")
    monkeypatch.setattr(estate_router, "resolve_route", lambda task: {
        "ok": False, "decision_id": "D", "reason": "needs escalation",
        "route": {"host": HOST, "executor": "none", "model_alias": "code-strong",
                  "concrete_model": None},
        "hosts_checked": [{"host_id": HOST, "qualified_executors": qualified, "transport": "local"}],
    })
    monkeypatch.setattr(estate_router, "_update_decision_outcome", lambda *args, **kwargs: None)
    monkeypatch.setattr(estate_router, "_resolve_claude_glm_launcher", lambda: ("/fake/claude-glm", "available"))
    clock = [NOW]
    monkeypatch.setattr(estate_router, "_provider_now", lambda: clock[0])
    monkeypatch.setattr(estate_router, "_provider_cooldown", ProviderCooldown(lambda: clock[0]))
    monkeypatch.setattr(estate_router, "resolve_repo_path", lambda repo_id: "/worktree")
    return clock


def test_quota_exhaustion_sets_cooldown_and_switches_once(fallback_router, monkeypatch):
    codex_calls = []
    monkeypatch.setattr(estate_router, "_dispatch_read_only", lambda *args, **kwargs: (
        codex_calls.append(args) or {
            "ok": False, "provider": "codex", "error": QUOTA_ERROR,
            "latency_ms": 8, "placement": _placement(),
        }
    ))
    glm_calls = []
    monkeypatch.setattr(estate_router, "execute_claude_glm", lambda objective, **kwargs: (
        glm_calls.append((objective, kwargs)) or {
            "ok": True, "provider": "glm", "model": "glm-5.3", "output": "done",
            "usage": {"input_tokens": 4, "output_tokens": 2}, "latency_ms": 6,
        }
    ))

    result = estate_router.run_task(_task())

    assert len(codex_calls) == 1 and len(glm_calls) == 1
    assert result["provider_switched"] is True
    assert result["original_provider"] == "codex"
    assert result["switch_reason"] == "quota_exhaustion"
    assert result["route"]["executor"] == "glm"
    assert result["route"]["concrete_model"] == "glm-5.3"
    assert result["execution"]["usage"]["output_tokens"] == 2
    assert result["execution"]["host_id"] == HOST
    assert result["cooldown_expires_at"] == "2026-10-19T14:30:00"
    assert estate_router._provider_cooldown.active("codex", NOW)


def test_active_cooldown_short_circuits_codex_then_expiry_restores_it(fallback_router, monkeypatch):
    clock = fallback_router
    estate_router._provider_cooldown.set("codex", NOW + timedelta(minutes=5), now=NOW)
    codex_calls = []

    def codex(*args, **kwargs):
        codex_calls.append(1)
        return {"ok": True, "provider": "codex", "output": "codex", "placement": _placement()}

    monkeypatch.setattr(estate_router, "_dispatch_read_only", codex)
    monkeypatch.setattr(estate_router, "execute_claude_glm", lambda *args, **kwargs: {
        "ok": True, "provider": "glm", "model": "glm-5.3", "output": "glm",
    })

    switched = estate_router.run_task(_task())
    assert switched["execution"]["provider"] == "glm"
    assert codex_calls == []

    clock[0] = NOW + timedelta(minutes=5)
    restored = estate_router.run_task(_task())
    assert restored["execution"]["provider"] == "codex"
    assert codex_calls == [1]


def test_unparseable_quota_defaults_to_30_minute_cooldown(fallback_router, monkeypatch):
    monkeypatch.setattr(estate_router, "_dispatch_read_only", lambda *args, **kwargs: {
        "ok": False, "provider": "codex", "error": "quota exceeded; retry later",
        "placement": _placement(),
    })
    monkeypatch.setattr(estate_router, "execute_claude_glm", lambda *args, **kwargs: {
        "ok": True, "provider": "glm", "output": "done", "model": "glm-5.3",
    })

    result = estate_router.run_task(_task())

    assert result["cooldown_expires_at"] == "2026-10-19T14:30:00"
    assert estate_router._provider_cooldown.remaining("codex", NOW) == timedelta(minutes=30)


def test_glm_unavailable_preserves_original_codex_failure(fallback_router, monkeypatch):
    original = {"ok": False, "provider": "codex", "error": QUOTA_ERROR,
                "latency_ms": 7, "placement": _placement()}
    monkeypatch.setattr(estate_router, "_dispatch_read_only", lambda *args, **kwargs: original)
    monkeypatch.setattr(estate_router, "_resolve_claude_glm_launcher", lambda: (None, "launcher missing"))

    result = estate_router.run_task(_task())

    assert result["execution"] == original
    # Skipped before any dispatch (launcher availability): reported as
    # skipped, never as an attempted fallback.
    assert result["glm_fallback_skipped"] == "launcher missing"
    assert "glm_fallback_attempted" not in result
    assert "provider_switched" not in result


@pytest.mark.parametrize("error", [
    "codex exec timed out after 180s",
    "codex exited 1: network connection failed",
])
def test_non_quota_codex_errors_do_not_switch_or_set_cooldown(
        fallback_router, monkeypatch, error):
    glm_calls = []
    monkeypatch.setattr(estate_router, "_dispatch_read_only", lambda *args, **kwargs: {
        "ok": False, "provider": "codex", "error": error, "placement": _placement(),
    })
    monkeypatch.setattr(estate_router, "execute_claude_glm", lambda *args, **kwargs: glm_calls.append(1))

    result = estate_router.run_task(_task())

    assert result["execution"]["error"] == error
    assert glm_calls == []
    assert estate_router._provider_cooldown.active("codex", NOW) is False
    assert "glm_fallback_attempted" not in result


def test_glm_429_balance_rejection_preserves_original_failure(fallback_router, monkeypatch):
    original = {"ok": False, "provider": "codex", "error": QUOTA_ERROR,
                "latency_ms": 7, "placement": _placement()}
    monkeypatch.setattr(estate_router, "_dispatch_read_only", lambda *args, **kwargs: original)
    monkeypatch.setattr(estate_router, "execute_claude_glm", lambda *args, **kwargs: {
        "ok": False, "provider": "glm", "error": BALANCE_429,
        "error_code": "glm_unavailable", "unavailable": True,
    })

    result = estate_router.run_task(_task())

    assert result["execution"] == original
    assert result["glm_fallback_attempted"] is True
    assert result["glm_fallback_error"] == BALANCE_429
    assert "provider_switched" not in result
    assert estate_router._provider_cooldown.active("glm", NOW) is False


def test_glm_read_fallback_placement_is_truthful_not_attested(fallback_router, monkeypatch):
    estate_router._provider_cooldown.set("codex", NOW + timedelta(minutes=30), now=NOW)
    monkeypatch.setattr(
        estate_router, "_dispatch_read_only",
        lambda *args, **kwargs: pytest.fail("active cooldown must not dispatch codex"),
    )
    monkeypatch.setattr(estate_router, "execute_claude_glm", lambda *args, **kwargs: {
        "ok": True, "provider": "glm", "model": "glm-5.3", "output": "done",
    })

    result = estate_router.run_task(_task())

    # Host-local GLM runs bypass the worker protocol: executed_host is
    # truthful, but the run is not worker-attested and no host was observed
    # by an attestation.
    assert result["execution"]["placement"] == {
        "routed_host": HOST, "executed_host": HOST, "attested": False,
        "transport": "local", "observed_host": None,
    }


def test_glm_unavailable_error_requires_balance_markers_with_429():
    live_lab_error = (
        "Request rejected (429) · [1113][Insufficient balance or no resource package. "
        "Please recharge.]"
    )
    assert estate_router._glm_unavailable_error(live_lab_error) is True
    # A bare 429 (generic rate limiting) is NOT provider-balance exhaustion.
    assert estate_router._glm_unavailable_error("HTTP 429: Too Many Requests") is False
    assert estate_router._glm_unavailable_error("codex exited 1: upstream said 429, retry later") is False


def test_failed_glm_attempt_records_glm_as_actual_route(fallback_router, monkeypatch):
    estate_router._provider_cooldown.set("codex", NOW + timedelta(minutes=30), now=NOW)
    monkeypatch.setattr(
        estate_router, "_dispatch_read_only",
        lambda *args, **kwargs: pytest.fail("active cooldown must not dispatch codex"),
    )
    monkeypatch.setattr(estate_router, "execute_claude_glm", lambda *args, **kwargs: {
        "ok": False, "provider": "glm", "error": "claude-glm exited 1",
    })
    outcomes = []
    monkeypatch.setattr(estate_router, "_update_decision_outcome",
                        lambda decision_id, **kwargs: outcomes.append(kwargs))

    result = estate_router.run_task(_task())

    assert result["glm_fallback_attempted"] is True
    assert result["glm_fallback_error"] == "claude-glm exited 1"
    # GLM was the provider that actually executed (and failed) even though
    # the reported failure is the codex cooldown: actual_route must say glm,
    # not the reset codex executor label.
    assert outcomes[-1]["actual_route"] == "glm"


def test_both_providers_cooling_reports_glm_unavailable(fallback_router, monkeypatch):
    estate_router._provider_cooldown.set("codex", NOW + timedelta(minutes=30), now=NOW)
    estate_router._provider_cooldown.set("glm", NOW + timedelta(minutes=5), now=NOW)
    monkeypatch.setattr(
        estate_router, "_dispatch_read_only",
        lambda *args, **kwargs: pytest.fail("cooling codex must not dispatch"),
    )
    monkeypatch.setattr(
        estate_router, "execute_claude_glm",
        lambda *args, **kwargs: pytest.fail("cooling glm must not dispatch"),
    )

    result = estate_router.run_task(_task())

    assert result["executed"] is False
    assert result["ok"] is False
    assert result["escalation_reason"] == "worker_failed"
    assert "both cooling" in result["glm_fallback_skipped"]
    assert "glm_fallback_attempted" not in result


def test_write_admission_switches_provider_before_single_execution_row(
        fallback_router, monkeypatch):
    estate_router._provider_cooldown.set("codex", NOW + timedelta(minutes=30), now=NOW)
    import src.estate_write_lane as write_lane
    monkeypatch.setattr(write_lane, "_lease_authority", lambda repo_id, host_id: {
        "ok": True, "lease_id": "L1", "worktree_path": "/worktree",
        "branch": "feat/glm-quota-fallback",
    })
    monkeypatch.setattr(
        estate_router, "execute_write_via_worker",
        lambda *args, **kwargs: pytest.fail("active cooldown must not call codex-write"),
    )
    captured = {}

    def glm_write(objective, **kwargs):
        captured.update(objective=objective, **kwargs)
        return {"ok": True, "provider": "glm", "execution_id": "E1",
                "lifecycle_state": "running", "dispatch": "new", "next_action": {}}

    monkeypatch.setattr(estate_router, "execute_claude_glm_write_durable", glm_write)

    result = estate_router.run_task(_task(implementation=True))

    assert result["provider_switched"] is True
    assert result["execution"]["provider"] == "glm"
    assert captured == {
        "objective": "implement it", "repo_id": "odysseus", "host_id": HOST,
        "decision_id": "D", "cooldown_expires_at": "2026-10-19T14:30:00",
    }


@pytest.fixture
def write_db(monkeypatch):
    session_local, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", session_local)
    monkeypatch.setattr(lane, "_observe_worker_execution", lambda execution_id: None)
    monkeypatch.setattr(estate_router, "_update_decision_outcome", lambda *args, **kwargs: None)
    monkeypatch.setattr(estate_router, "_provider_cooldown", ProviderCooldown(lambda: NOW))
    yield
    engine.dispose()
    os.unlink(tmpfile.name)


def _lease():
    with get_db_session() as db:
        db.add(ParkLease(
            id="L1", repo_id="odysseus", host_id=HOST, worktree_path="/w/feat",
            branch="feat/glm-quota-fallback", status="active",
        ))


def _row(execution_id):
    with get_db_session() as db:
        row = db.query(EstateExecution).filter(EstateExecution.id == execution_id).one()
        db.expunge(row)
        return row


def test_glm_write_uses_same_lease_worktree_branch_and_lifecycle(
        write_db, monkeypatch):
    _lease()
    FakeWorker(monkeypatch, head="a" * 40, path="/w/feat")
    calls = []

    def runner(objective, **kwargs):
        calls.append((objective, kwargs))
        return {"ok": True, "provider": "glm", "model": "glm-5.3", "output": "changed",
                "usage": {"input_tokens": 3, "output_tokens": 2}}

    result = lane.execute_write_via_worker(
        "change it", repo_id="odysseus", host_id=HOST, wait_timeout=2,
        provider="glm", executor="glm-write", provider_runner=runner,
        concrete_model="glm-5.3", cooldown_expires_at="2026-10-19T14:30:00",
    )
    row = _row(result["execution_id"])
    payload = json.loads(row.result_json)

    assert (row.provider, row.executor) == ("glm", "glm-write")
    assert (row.lease_id, row.worktree_path, row.branch) == (
        "L1", "/w/feat", "feat/glm-quota-fallback",
    )
    assert row.lifecycle_state == "succeeded" and row.worktree_resolution == "unresolved"
    assert payload["model"] == "glm-5.3"
    assert payload["cooldown_expires_at"] == "2026-10-19T14:30:00"
    assert payload["verification_result"] == "pass"
    assert calls == [("change it", {"timeout": 1800.0, "cwd": "/w/feat"})]


def test_codex_write_quota_failure_records_cooldown_without_midflight_switch(
        write_db, monkeypatch):
    _lease()
    from datetime import datetime
    monkeypatch.setattr(lane, "_now", lambda: datetime(2026, 10, 19, 10, 0, 0))
    worker = FakeWorker(monkeypatch, head="a" * 40, path="/w/feat")
    monkeypatch.setattr(
        estate_router, "execute_claude_glm",
        lambda *args, **kwargs: pytest.fail("a post-admission failure must never switch provider"),
    )
    admitted = lane.execute_write_via_worker(
        "change it", repo_id="odysseus", host_id=HOST, wait_timeout=0,
    )
    execution_id = admitted["execution_id"]
    worker.set_state(execution_id, "running", quiescent=False)
    lane._apply_view(execution_id, worker._view(execution_id))
    worker.set_state(execution_id, "failed", result={
        "ok": False, "provider": "codex", "error": QUOTA_ERROR,
    })
    lane._apply_view(execution_id, worker._view(execution_id))
    row = _row(execution_id)
    payload = json.loads(row.result_json)

    assert (row.provider, row.executor) == ("codex", "codex-write")
    assert row.lifecycle_state == "failed"
    assert payload["quota_exhaustion"] is True
    assert payload["cooldown_expires_at"] == "2026-10-19T14:30:00"


def test_admission_reuse_reports_the_existing_rows_provider(write_db, monkeypatch):
    _lease()
    with get_db_session() as db:
        db.add(EstateExecution(
            id="E-existing", decision_id="D0", objective="first change",
            executor="codex-write", provider="codex", host_id=HOST,
            repo_id="odysseus", lease_id="L1", worktree_path="/w/feat",
            branch="feat/glm-quota-fallback", lifecycle_state="running",
            worktree_resolution="unresolved", submitted_at=NOW,
        ))

    result = lane.execute_write_via_worker(
        "second change", repo_id="odysseus", host_id=HOST,
        provider="glm", executor="glm-write",
        provider_runner=lambda *args, **kwargs: pytest.fail(
            "admission reuse must not dispatch a new provider run"),
    )

    # The reused execution row is a codex row: the response must describe
    # the row's own provider/executor, not the glm-write request that
    # collided with it.
    assert result["dispatch"] == "reused_in_flight"
    assert result["execution_id"] == "E-existing"
    assert result["provider"] == "codex"
    assert result["executor"] == "codex-write"


def test_fallback_write_without_active_lease_is_refused_like_codex_write(
        fallback_router, monkeypatch):
    estate_router._provider_cooldown.set("codex", NOW + timedelta(minutes=30), now=NOW)
    monkeypatch.setattr(lane, "_lease_authority", lambda repo_id, host_id: {
        "ok": False, "code": "write_lease_missing", "error": "missing lease",
    })
    monkeypatch.setattr(
        estate_router, "execute_claude_glm_write_durable",
        lambda *args, **kwargs: pytest.fail("admission must refuse before provider execution"),
    )

    result = estate_router.run_task(_task(implementation=True))

    assert result["executed"] is False
    assert result["escalation_reason"] == "write_lease_missing"
    assert result["execution_error"] == "missing lease"


def test_resolve_provider_both_cooling_raises():
    cooldown = ProviderCooldown(lambda: NOW)
    cooldown.set("codex", NOW + timedelta(minutes=30), now=NOW)
    cooldown.set("glm", NOW + timedelta(minutes=5), now=NOW)
    with pytest.raises(ProviderUnavailable):
        resolve_provider("codex", "glm", cooldown, NOW)

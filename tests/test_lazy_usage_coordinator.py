"""Coordinator lane selection, plan validation and fail-closed integration.

Unit-level: no live provider is contacted; execute_glm/execute_claude are
monkeypatched. Live qualification evidence lives in
docs/runtime-work-packages/2026-11-16-lazyusage-sonnet-coordinator-lab.md.
"""
import json
import os
import sys
from pathlib import Path

import pytest

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()
import core.database as cdb
from src import estate_router, lazy_usage_coordinator as coord, lazy_usage_runtime as rt

LAB = "hz2-workstation"


@pytest.fixture
def db(monkeypatch):
    factory, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", factory)
    monkeypatch.setattr(estate_router, "current_host_id", lambda: LAB)
    session = factory()
    yield session
    session.close()
    engine.dispose()
    os.unlink(tmpfile.name)


@pytest.fixture
def frontier(tmp_path, monkeypatch):
    root = tmp_path / "odysseus"
    queue = root / "automation/review/agent-tasks/ready"
    queue.mkdir(parents=True)
    records = []

    def add(name="a", priority="high", body="Run the bounded owning task.\n", **meta):
        import yaml
        metadata = {"task_id": name, "title": name, "status": "ready", "priority": priority,
                    "execution_mode": "read-only", **meta}
        (queue / (name + ".md")).write_text("---\n" + yaml.safe_dump(metadata) +
                                            "---\n" + body)
        record = {"ref": "odysseus:ready/" + name + ".md", "repo_id": "odysseus", "bucket": "ready",
                  "task_id": name, "status": "ready", "priority": priority, "eligible": "unverified"}
        records.append(record)
        return record

    monkeypatch.setattr(rt, "refresh_frontier", lambda scope: {
        "roots": {"odysseus": root}, "records": list(records), "unavailable": {},
        "counts": {"odysseus": {"ready": len(records)}}, "warnings": []})
    return add, records


def qualify(monkeypatch, executors=("glm-flash",), allowed=True):
    monkeypatch.setattr(coord, "_qualified_executors", lambda: list(executors))
    monkeypatch.setattr(estate_router, "provider_allows_dispatch",
                        lambda provider, **kw: {"allowed": allowed, "provider": provider})
    monkeypatch.setattr(coord, "master_enabled", lambda: True)


def glm_plan_result(order, steps=("step one", "step two"), next_action="dispatch first"):
    return {"ok": True, "executed": True, "provider": "glm", "output": json.dumps(
        {"selected": order, "decomposition": list(steps), "next_action": next_action}),
        "concrete_model": "glm-5.3-flash"}


# --------------------------------------------------------------- activation gate

@pytest.mark.parametrize("bad", [{"enabled": "yes"}, {"extra": 1}, "x", ["enabled"], {"enabled": None}])
def test_activation_rejects_invalid_coordinator(db, bad):
    with pytest.raises(rt.RunError) as exc:
        rt.activate_run(db, "operator", ["odysseus"], None, bad)
    assert exc.value.status_code == 422
    assert not db.query(cdb.LazyUsageRun).count()


def test_activation_stores_opt_in_only_when_enabled(db):
    run_id = rt.activate_run(db, "operator", ["odysseus"], None, {"enabled": True})["id"]
    assert db.get(cdb.LazyUsageRun, run_id).checkpoint["coordinator"] == {"enabled": True}
    rt.stop_run(db, run_id, "operator")
    run_id = rt.activate_run(db, "operator2", ["odysseus"], None, {"enabled": False})["id"]
    assert "coordinator" not in db.get(cdb.LazyUsageRun, run_id).checkpoint


# ------------------------------------------------------------------ lane choice

def _run(db, paid_calls=0, **coordinator):
    run_id = rt.activate_run(db, "operator", ["odysseus"], None,
                             {"enabled": True} if coordinator.pop("on", True) else None)["id"]
    run = db.get(cdb.LazyUsageRun, run_id)
    run.state = "running"   # the coordinator only plans for a running activation
    if paid_calls:
        run.counters = {**run.counters, "paid_calls": paid_calls}
    db.commit()
    return run


def test_select_lane_prefers_sonnet_for_opted_in_runs(db, monkeypatch):
    qualify(monkeypatch, executors=("glm-flash", "glm", "claude", "claude-sonnet"))
    run = _run(db)
    assert coord.select_lane(run, high_consequence=False)["lane"] == "claude-sonnet"
    assert coord.select_lane(run, high_consequence=True)["lane"] == "claude-sonnet"


def test_select_lane_skips_unqualified_executor(db, monkeypatch):
    qualify(monkeypatch, executors=("glm",))
    assert coord.select_lane(_run(db), high_consequence=False)["lane"] == "glm-standard"


def test_standard_glm_qualification_does_not_authorise_flash(db, monkeypatch):
    qualify(monkeypatch, executors=("glm",))
    monkeypatch.setattr(coord, "policy", lambda: {**coord.DEFAULT_POLICY, "routine_lanes": ["glm-flash"]})
    assert coord.select_lane(_run(db), high_consequence=False)["lane"] is None


def test_general_claude_qualification_does_not_authorise_sonnet_coordinator(db, monkeypatch):
    qualify(monkeypatch, executors=("claude",))
    assert coord.select_lane(_run(db), high_consequence=False)["lane"] is None


def test_select_lane_skips_disallowed_provider(db, monkeypatch):
    monkeypatch.setattr(coord, "_qualified_executors", lambda: ["glm", "claude", "claude-sonnet"])
    seen = []

    def health(provider, **kw):
        seen.append(provider)
        return {"allowed": provider == "claude", "provider": provider}

    monkeypatch.setattr(estate_router, "provider_allows_dispatch", health)
    monkeypatch.setattr(coord, "master_enabled", lambda: True)
    choice = coord.select_lane(_run(db), high_consequence=True)
    assert choice["lane"] == "claude-sonnet"
    assert seen == ["claude"]


def test_select_lane_none_qualified(db, monkeypatch):
    qualify(monkeypatch, executors=())
    choice = coord.select_lane(_run(db), high_consequence=False)
    assert choice["lane"] is None and choice["reason"] == "no_qualified_coordinator_lane"


def test_select_lane_reserves_paid_budget_for_task_dispatch(db, monkeypatch):
    qualify(monkeypatch)
    choice = coord.select_lane(_run(db, paid_calls=11), high_consequence=False)
    assert choice["lane"] is None and choice["reason"] == "paid_budget_reserved_for_task_dispatch"


def test_select_lane_ignores_unknown_configured_lanes(db, monkeypatch):
    monkeypatch.setattr(coord, "policy", lambda: {**coord.DEFAULT_POLICY,
                                                  "routine_lanes": ["nonsense", "glm-flash"]})
    monkeypatch.setattr(coord, "_qualified_executors", lambda: ["glm-flash"])
    monkeypatch.setattr(estate_router, "provider_allows_dispatch",
                        lambda provider, **kw: {"allowed": True, "provider": provider})
    assert coord.select_lane(_run(db), high_consequence=False)["lane"] == "glm-flash"


# ---------------------------------------------------------------- plan validation

def _frontier_with(*refs):
    return {ref for ref in refs}


def test_parse_plan_accepts_bounded_valid_plan():
    plan = coord.parse_plan('{"selected": ["odysseus:ready/a.md"], "decomposition": [], '
                            '"next_action": "dispatch"}', _frontier_with("odysseus:ready/a.md"))
    assert plan == {"order": ["odysseus:ready/a.md"], "primary": "odysseus:ready/a.md",
                    "decomposition": [], "next_action": "dispatch"}


@pytest.mark.parametrize("text,frontier", [
    ("not json", _frontier_with("a")),
    ('{"selected": [], "decomposition": [], "next_action": "x"}', _frontier_with("a")),
    ('{"selected": ["ghost"], "decomposition": [], "next_action": "x"}', _frontier_with("a")),
    ('{"selected": ["a"], "decomposition": [], "next_action": "x", "extra": 1}', _frontier_with("a")),
    ('{"selected": ["a"], "next_action": "x"}', _frontier_with("a")),
    ('{"selected": ["a"], "decomposition": [], "next_action": "' + "x" * 200 + '"}', _frontier_with("a")),
    ('{"selected": ["a"], "decomposition": ["' + "x" * 300 + '"], "next_action": "x"}', _frontier_with("a")),
    ('{"selected": ["a"] * 13, "decomposition": [], "next_action": "x"}', _frontier_with("a")),
    ('{"selected": "a", "decomposition": [], "next_action": "x"}', _frontier_with("a")),
])
def test_parse_plan_rejects_invalid(text, frontier):
    assert coord.parse_plan(text, frontier) is None


def test_parse_plan_dedups_selected_preserving_order():
    plan = coord.parse_plan('{"selected": ["a", "b", "a"], "decomposition": [], "next_action": "x"}',
                            _frontier_with("a", "b"))
    assert plan["order"] == ["a", "b"]


# ------------------------------------------------------- coordinator_step bounds

def test_step_no_call_when_not_opted_in(db, frontier, monkeypatch):
    monkeypatch.setattr(estate_router, "execute_glm", lambda *a, **kw: pytest.fail("unexpected call"))
    add, records = frontier
    add("a")
    run_id = rt.activate_run(db, "operator", ["odysseus"])["id"]
    assert coord.coordinator_step(db, db.get(cdb.LazyUsageRun, run_id),
                                  rt.refresh_frontier(["odysseus"]), "digest") is None


def test_step_env_kill_switch(db, frontier, monkeypatch):
    monkeypatch.setenv("ODYSSEUS_LAZY_USAGE_COORDINATOR", "0")
    monkeypatch.setattr(estate_router, "execute_glm", lambda *a, **kw: pytest.fail("unexpected call"))
    add, _ = frontier
    add("a")
    run = _run(db)
    assert coord.coordinator_step(db, run, rt.refresh_frontier(["odysseus"]), "digest") is None
    assert run.checkpoint["coordinator_skip"] == "coordinator_disabled"
    assert run.counters["paid_calls"] == 0


def test_step_charges_persists_and_reuses_plan(db, frontier, monkeypatch):
    qualify(monkeypatch)
    calls = []
    add, _ = frontier
    add("a")
    add("b", priority="low")
    monkeypatch.setattr(estate_router, "execute_glm",
                        lambda prompt, **kw: calls.append(prompt) or glm_plan_result(
                            ["odysseus:ready/b.md", "odysseus:ready/a.md"]))
    run = _run(db)
    snapshot = rt.refresh_frontier(["odysseus"])
    digest = rt._digest(snapshot)
    plan = coord.coordinator_step(db, run, snapshot, digest)
    assert plan["primary"] == "odysseus:ready/b.md"
    assert run.counters["paid_calls"] == 1 and run.counters["tool_calls"] == 1
    assert run.checkpoint["coordinator_lane"] == "glm-flash"
    assert run.checkpoint["coordinator_model"] == "glm-5.3-flash"
    # unchanged frontier state: persisted reuse, no second paid call
    again = coord.coordinator_step(db, run, snapshot, digest)
    assert again["order"] == plan["order"] and len(calls) == 1
    assert run.counters["paid_calls"] == 1
    # a new digest (frontier changed) allows exactly one new call
    snapshot2 = dict(snapshot)
    snapshot2["warnings"] = ["changed"]
    coord.coordinator_step(db, run, snapshot2, rt._digest(snapshot2))
    assert len(calls) == 2 and run.counters["paid_calls"] == 2


def test_step_provider_failure_fails_closed_and_records_skip(db, frontier, monkeypatch):
    qualify(monkeypatch)
    add, _ = frontier
    add("a")
    monkeypatch.setattr(estate_router, "execute_glm",
                        lambda prompt, **kw: {"ok": False, "error_code": "quota_exhausted"})
    run = _run(db)
    assert coord.coordinator_step(db, run, rt.refresh_frontier(["odysseus"]), "d") is None
    assert run.checkpoint["coordinator_skip"].startswith("provider_failed_")
    assert run.checkpoint["coordinator_key"] is None
    assert run.counters["paid_calls"] == 1  # the failed call was really spent


def test_step_digest_fence_prevents_repeat_paid_call_after_failure(db, frontier, monkeypatch):
    qualify(monkeypatch)
    calls = []
    add, _ = frontier
    add("a")

    def flaky(prompt, **kw):
        calls.append(prompt)
        return {"ok": False, "error_code": "quota_exhausted"} if len(calls) == 1 else \
            glm_plan_result(["odysseus:ready/a.md"])

    monkeypatch.setattr(estate_router, "execute_glm", flaky)
    run_id = _run(db).id
    snapshot = rt.refresh_frontier(["odysseus"])
    digest = rt._digest(snapshot)
    assert coord.coordinator_step(db, db.get(cdb.LazyUsageRun, run_id), snapshot, digest) is None
    # crash simulation: reload the run purely from durable committed state;
    # the fence committed before the call must still hold
    db.expire_all()
    run = db.get(cdb.LazyUsageRun, run_id)
    assert run.checkpoint["coordinator_attempted_key"] == coord.plan_key(digest)
    assert coord.coordinator_step(db, run, snapshot, digest) is None
    assert run.checkpoint["coordinator_skip"] == "digest_already_attempted"
    assert len(calls) == 1 and run.counters["paid_calls"] == 1
    # a changed frontier (new digest) permits exactly one new attempt
    snapshot2 = dict(snapshot, warnings=["changed"])
    plan = coord.coordinator_step(db, run, snapshot2, rt._digest(snapshot2))
    assert plan is not None and len(calls) == 2


@pytest.mark.parametrize("first_result", [
    {"ok": True, "output": "garbage not json", "concrete_model": "glm-5.3-flash"},
    {"ok": True, "output": json.dumps({"selected": ["odysseus:ready/ghost.md"],
                                       "decomposition": [], "next_action": "x"}),
     "concrete_model": "glm-5.3-flash"},
])
def test_step_digest_fence_also_covers_invalid_output(db, frontier, monkeypatch, first_result):
    qualify(monkeypatch)
    calls = []
    add, _ = frontier
    add("a")
    monkeypatch.setattr(estate_router, "execute_glm",
                        lambda prompt, **kw: calls.append(prompt) or first_result)
    run = _run(db)
    snapshot = rt.refresh_frontier(["odysseus"])
    digest = rt._digest(snapshot)
    assert coord.coordinator_step(db, run, snapshot, digest) is None
    assert run.checkpoint["coordinator_skip"] == "plan_validation_failed"
    assert coord.coordinator_step(db, run, snapshot, digest) is None
    assert run.checkpoint["coordinator_skip"] == "digest_already_attempted"
    assert len(calls) == 1


def test_step_rejects_ref_beyond_bounded_candidate_window(db, frontier, monkeypatch):
    qualify(monkeypatch)
    add, _ = frontier
    for i in range(coord.MAX_CANDIDATES + 1):
        add("task-%02d" % i)
    # the record just past the window exists in the frontier but was never shown to the
    # model; a plan promoting it must be rejected
    unshown = "odysseus:ready/task-%02d.md" % coord.MAX_CANDIDATES
    assert unshown not in {r["ref"] for r in coord._candidates(rt.refresh_frontier(["odysseus"]))}
    monkeypatch.setattr(estate_router, "execute_glm", lambda prompt, **kw: glm_plan_result([unshown]))
    run = _run(db)
    snapshot = rt.refresh_frontier(["odysseus"])
    assert coord.coordinator_step(db, run, snapshot, rt._digest(snapshot)) is None
    assert run.checkpoint["coordinator_skip"] == "plan_validation_failed"


def test_step_invalid_output_fails_closed(db, frontier, monkeypatch):
    qualify(monkeypatch)
    add, _ = frontier
    add("a")
    monkeypatch.setattr(estate_router, "execute_glm",
                        lambda prompt, **kw: {"ok": True, "output": "I will help!", "concrete_model": "glm-5.3-flash"})
    run = _run(db)
    assert coord.coordinator_step(db, run, rt.refresh_frontier(["odysseus"]), "d") is None
    assert run.checkpoint["coordinator_skip"] == "plan_validation_failed"


def test_step_no_qualified_lane_records_skip(db, frontier, monkeypatch):
    qualify(monkeypatch, executors=())
    monkeypatch.setattr(estate_router, "execute_glm", lambda *a, **kw: pytest.fail("unexpected call"))
    add, _ = frontier
    add("a")
    run = _run(db)
    assert coord.coordinator_step(db, run, rt.refresh_frontier(["odysseus"]), "d") is None
    assert run.checkpoint["coordinator_skip"] == "no_qualified_coordinator_lane"
    assert run.counters["paid_calls"] == 0


# --------------------------------------------------------- runtime integration

def _integration(monkeypatch, db, frontier, *, second_priority="low"):
    """Read-only advance with the router mocked at the dispatch boundary."""
    add, _ = frontier
    add("a", priority="high")
    add("b", priority=second_priority)
    qualify(monkeypatch)
    monkeypatch.setattr(estate_router, "resolve_route", lambda *a, **kw: {
        "ok": False, "route": {"host": LAB, "executor": "none", "model_alias": "local-fast"},
        "hosts_checked": [{"host_id": LAB, "qualified_executors": ["local", "codex", "glm"]}]})
    monkeypatch.setattr(rt, "delegation_preflight", lambda units: {"ok": True})
    dispatched = []
    monkeypatch.setattr(estate_router, "run_task",
                        lambda task: dispatched.append(task) or {
                            "ok": True, "executed": True, "output": "done",
                            "deterministic_gate": "pass", "provider": "glm"})
    monkeypatch.setattr(estate_router, "get_estate_execution",
                        lambda execution_id, wait_s=0: None)
    monkeypatch.setattr(estate_router, "provider_allows_dispatch",
                        lambda provider, **kw: {"allowed": True, "provider": provider})
    return dispatched


def test_advance_uses_plan_order_and_checkpoints_decomposition(db, frontier, monkeypatch):
    dispatched = _integration(monkeypatch, db, frontier, second_priority="high")
    add, _ = frontier
    monkeypatch.setattr(estate_router, "execute_glm", lambda prompt, **kw: glm_plan_result(
        ["odysseus:ready/b.md", "odysseus:ready/a.md"],
        steps=["confirm scope", "run deterministic checks"]))
    run_id = rt.activate_run(db, "operator", ["odysseus"], None, {"enabled": True})["id"]
    rt.advance(db, run_id)
    run = db.get(cdb.LazyUsageRun, run_id)
    assert run.checkpoint["task_ref"] == "odysseus:ready/b.md"
    assert run.counters["paid_calls"] >= 2  # coordinator + task advisory
    # decomposition stays advisory evidence in the checkpoint and never
    # enters the worker objective (Sol review P1): assert the actual step
    # text is absent from what the worker receives
    assert "run deterministic checks" not in dispatched[0]["objective"]
    assert "Coordinator advisory decomposition" not in dispatched[0]["objective"]
    assert "run deterministic checks" in run.checkpoint["coordinator_decomposition"]
    assert run.checkpoint["coordinator_order"][0] == "odysseus:ready/b.md"


def test_advance_keeps_owner_priority_when_coordinator_disagrees(db, frontier, monkeypatch):
    _integration(monkeypatch, db, frontier)
    monkeypatch.setattr(estate_router, "execute_glm", lambda prompt, **kw: glm_plan_result(
        ["odysseus:ready/b.md", "odysseus:ready/a.md"]))
    run_id = rt.activate_run(db, "operator", ["odysseus"], None, {"enabled": True})["id"]
    rt.advance(db, run_id)
    run = db.get(cdb.LazyUsageRun, run_id)
    assert run.checkpoint["coordinator_order"][0] == "odysseus:ready/b.md"
    assert run.checkpoint["task_ref"] == "odysseus:ready/a.md"


def test_stop_during_planning_prevents_task_dispatch(db, frontier, monkeypatch):
    dispatched = _integration(monkeypatch, db, frontier)
    run_id = rt.activate_run(db, "operator", ["odysseus"], None, {"enabled": True})["id"]

    def stop_then_return_plan(*args, **kwargs):
        rt.stop_run(db, run_id, "operator")
        return glm_plan_result(["odysseus:ready/a.md"])

    monkeypatch.setattr(estate_router, "execute_glm", stop_then_return_plan)
    rt.advance(db, run_id)
    assert rt.advance(db, run_id)["state"] == "stopped"
    assert not dispatched
    assert db.get(cdb.LazyUsageRun, run_id).counters["paid_calls"] == 1


def test_advance_survives_garbage_plan_deterministically(db, frontier, monkeypatch):
    dispatched = _integration(monkeypatch, db, frontier)
    monkeypatch.setattr(estate_router, "execute_glm", lambda prompt, **kw: {
        "ok": True, "output": "<think>helping</think>", "concrete_model": "glm-5.3-flash"})
    run_id = rt.activate_run(db, "operator", ["odysseus"], None, {"enabled": True})["id"]
    rt.advance(db, run_id)
    run = db.get(cdb.LazyUsageRun, run_id)
    assert run.checkpoint["coordinator_skip"] == "plan_validation_failed"
    # deterministic priority still picked the high-priority task
    assert run.checkpoint["task_ref"] == "odysseus:ready/a.md"
    assert "decomposition" not in dispatched[0]["objective"]


def test_advance_restart_reuses_plan_without_second_call(db, frontier, monkeypatch):
    _integration(monkeypatch, db, frontier)
    calls = []
    monkeypatch.setattr(estate_router, "execute_glm", lambda prompt, **kw: calls.append(1) or
                        glm_plan_result(["odysseus:ready/b.md", "odysseus:ready/a.md"]))
    run_id = rt.activate_run(db, "operator", ["odysseus"], None, {"enabled": True})["id"]
    rt.advance(db, run_id)
    first = db.get(cdb.LazyUsageRun, run_id).counters["paid_calls"]
    rt.advance(db, run_id)  # same unchanged frontier: no repeat coordinator call
    run = db.get(cdb.LazyUsageRun, run_id)
    assert len(calls) == 1
    assert run.counters["paid_calls"] == first


# ------------------------------------------------------------ claude provider lane

@pytest.fixture
def claude_admission(monkeypatch, tmp_path):
    outcomes = []
    # Keep the fixture's working directory inside the disposable home.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("DATABASE_URL", "test-only")
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)

    def admit(provider, **kwargs):
        assert provider == "claude" and kwargs.get("launch_timeout") > 0
        return {"allowed": True, "outcome_id": "test-outcome", "provider": provider}

    monkeypatch.setattr(estate_router, "provider_allows_dispatch", admit)
    monkeypatch.setattr(estate_router, "_record_provider_outcome",
                        lambda result, outcome_id: outcomes.append(result))
    return outcomes


def _claude_cli(tmp_path, monkeypatch, response, *, auth=None):
    if auth is None:
        auth = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty",
                "subscriptionType": "pro"}
    cli = tmp_path / "claude"
    stdout = response if response == "not-json" else json.dumps(response)
    cli.write_text(f"#!{sys.executable}\nimport sys\n"
                   f"if sys.argv[1:3] == ['auth', 'status']:\n    print({json.dumps(auth)!r})\n"
                   f"else:\n    assert sys.argv[sys.argv.index('--tools') + 1] == ''\n"
                   f"    assert sys.argv[sys.argv.index('--disallowedTools') + 1] == '*'\n"
                   f"    print({stdout!r})\n")
    cli.chmod(0o755)
    monkeypatch.setattr(estate_router, "_claude_launcher_path", lambda: cli)
    return cli


def test_execute_claude_attests_sonnet_model(tmp_path, monkeypatch, claude_admission):
    _claude_cli(tmp_path, monkeypatch, {"type": "result", "is_error": False, "result": '{"selected": []}',
                                        "modelUsage": {"claude-sonnet-5-5": {}}})
    result = estate_router.execute_claude("plan", timeout=5)
    assert result["ok"] is True
    assert result["concrete_model"] == "claude-sonnet-5-5"
    assert result["model_attestation"] == "provider-usage-response"
    assert claude_admission[0]["ok"] is True


def test_execute_claude_classifies_expired_oauth_as_auth_failure(tmp_path, monkeypatch, claude_admission):
    _claude_cli(tmp_path, monkeypatch, {"type": "result", "is_error": True, "api_error_status": None,
                                        "result": "Failed to authenticate: OAuth session expired and could not be refreshed",
                                        "modelUsage": {}})
    result = estate_router.execute_claude("plan", timeout=5)
    assert result["ok"] is False and result["error_code"] == "auth_failed"
    assert claude_admission[0]["error_code"] == "auth_failed"


def test_execute_claude_refuses_an_endpoint_override(monkeypatch, claude_admission):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://override.invalid")
    result = estate_router.execute_claude("plan", timeout=5)
    assert result["error_code"] == "auth_failed" and result["executed"] is False
    assert not claude_admission


@pytest.mark.parametrize("override", [
    {"loggedIn": False}, {"authMethod": "api_key"}, {"apiProvider": "bedrock"},
    {"subscriptionType": None}, {"apiKeySource": "/login managed key"},
])
def test_execute_claude_refuses_unverified_subscription_before_inference(
        tmp_path, monkeypatch, claude_admission, override):
    auth = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty",
            "subscriptionType": "pro", **override}
    _claude_cli(tmp_path, monkeypatch, {}, auth=auth)
    result = estate_router.execute_claude("plan", timeout=5)
    assert result["error_code"] == claude_admission[0]["error_code"] == "auth_failed"
    assert result["executed"] is False


@pytest.mark.parametrize("response,code", [
    ({"type": "result", "is_error": True, "api_error_status": 429, "result": "rate limited",
      "modelUsage": {}}, "rate_limited"),
    ({"type": "result", "is_error": True, "api_error_status": None,
      "result": "Claude usage limit reached until 5pm", "modelUsage": {}}, "quota_exhausted"),
    ({"type": "result", "is_error": False, "result": "advice",
      "modelUsage": {"claude-opus-5-5": {}}}, "model_mismatch"),
    ({"type": "result", "is_error": False, "result": "advice", "modelUsage": {}}, "model_mismatch"),
    ("not-json", "bad_output"),
])
def test_execute_claude_typed_failures(tmp_path, monkeypatch, claude_admission, response, code):
    _claude_cli(tmp_path, monkeypatch, response)
    result = estate_router.execute_claude("plan", timeout=5)
    assert result["ok"] is False and result["error_code"] == code


def test_execute_glm_unconfigured_variant_fails_typed_and_finalizes(monkeypatch):
    outcomes = []
    monkeypatch.setenv("DATABASE_URL", "test-only")
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda provider, **kw: {
        "allowed": True, "outcome_id": "out-1", "provider": provider})
    monkeypatch.setattr(estate_router, "_record_provider_outcome",
                        lambda result, outcome_id: outcomes.append(result))
    monkeypatch.setattr(estate_router, "_glm_variant_launcher_path", lambda variant: None)
    result = estate_router.execute_glm("plan", variant="flash")
    assert result["ok"] is False and result["error_code"] == "launcher_missing"
    assert "not configured" in result["error"]
    # the reserved provider outcome is finalized, never left "launching"
    assert outcomes and outcomes[0]["error_code"] == "launcher_missing"


def test_preflight_explicit_write_false_overrides_text_heuristic():
    from src.delegation_preflight import _requires_repo_write
    body = "Implement the bounded change in src/ and merge it."
    assert _requires_repo_write({"repo": "odysseus", "objective": body}) is True
    # trusted in-process classification wins in both directions
    assert _requires_repo_write({"repo": "odysseus", "objective": body,
                                 "write_classified": True, "requires_repo_write": False}) is False
    assert _requires_repo_write({"repo": "odysseus", "objective": body,
                                 "write_classified": True, "requires_repo_write": True}) is True
    # envelope units carry write=False by default; that must NOT disable
    # the heuristic inference the HTTP contract relies on
    assert _requires_repo_write({"repo": "odysseus", "objective": body, "write": False}) is True


def test_advance_dispatches_read_only_reconnaissance_with_write_pattern_body(db, frontier, monkeypatch):
    """Live 2026-11-16 finding: an approval_required card's embedded body can
    match the write text-heuristic while the runtime's classification is a
    read-only reconnaissance. The runtime's explicit write: False must keep
    the preflight on the advisory lane instead of demanding a write lease."""
    _integration(monkeypatch, db, frontier)
    add, _ = frontier
    add("a", approval_required=True, body="Implement the bounded owning task in src/.\n")
    # exercise the REAL preflight (the _integration helper bypasses it)
    from src import estate_worker_client
    from src.delegation_preflight import delegation_preflight as real_preflight
    monkeypatch.setattr(rt, "delegation_preflight", real_preflight)
    monkeypatch.setattr(estate_worker_client, "worker_health",
                        lambda host_id: {"codex": {"available": True}})
    monkeypatch.setattr(estate_router, "execute_glm", lambda prompt, **kw: glm_plan_result(
        ["odysseus:ready/a.md"]))
    run_id = rt.activate_run(db, "operator", ["odysseus"], None, {"enabled": True})["id"]
    rt.advance(db, run_id)
    run = db.get(cdb.LazyUsageRun, run_id)
    # before the fix this parked at "delegation preflight has no qualified route"
    assert run.checkpoint.get("pause_reason") != "delegation preflight has no qualified route"
    assert run.checkpoint["current_task_id"] == "a"


def test_preflight_explicit_write_intent_counts_without_heuristic_match():
    from src.delegation_preflight import _requires_repo_write
    assert _requires_repo_write({"repo": "odysseus", "objective": "Review the patch",
                                 "write": True}) is True
    assert _requires_repo_write({"repo": "odysseus", "objective": "Review the patch",
                                 "mode": "implementation"}) is True


def test_preflight_fallthrough_refuses_write_intent_local_route(monkeypatch):
    from src.delegation_preflight import delegation_preflight as real_pf
    monkeypatch.setattr(estate_router, "resolve_route", lambda task, record_decision=False: {
        "ok": True, "route": {"host": "lab", "executor": "local", "model_alias": "local-fast"},
        "hosts_checked": [{"host_id": "lab", "qualified_executors": ["local"]}]})
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo_id=None: [])
    result = real_pf([{"task_class": "batch", "repo": "odysseus",
                       "objective": "Run the batch scan", "write": True,
                       "capabilities": ["local-fast"], "allow_paid_escalation": False}])
    unit = result["units"][0]
    assert unit["ok"] is False and unit["recommended_route"] is None
    assert unit["error_code"] == "write_intent_requires_codex_write_lane"


def test_execute_claude_requires_authoritative_database(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    result = estate_router.execute_claude("plan")
    assert result["ok"] is False and "DATABASE_URL" in result["error"]


def test_step_uses_claude_lane_when_high_consequence_and_qualified(db, frontier, monkeypatch):
    qualify(monkeypatch, executors=("claude", "claude-sonnet", "glm-flash"))
    add, _ = frontier
    add("a")
    calls = []
    monkeypatch.setattr(estate_router, "execute_claude", lambda prompt, **kw: calls.append(prompt) or {
        "ok": True, "output": json.dumps({"selected": ["odysseus:ready/a.md"],
                                          "decomposition": [], "next_action": "go"}),
        "provider": "claude", "model_attestation": "provider-usage-response", "model_unverified": False,
        "concrete_model": "claude-sonnet-5-5"})
    run = _run(db)
    run.checkpoint = {**run.checkpoint, "owed_reviews": [{"task_ref": "odysseus:ready/x.md", "gate": "verification"}]}
    db.commit()
    plan = coord.coordinator_step(db, run, rt.refresh_frontier(["odysseus"]), "d")
    assert plan is not None and len(calls) == 1
    assert run.checkpoint["coordinator_lane"] == "claude-sonnet"
    assert run.checkpoint["coordinator_high_consequence"] is True
    assert run.checkpoint["coordinator_model_attestation"] == "provider-usage-response"
    db.expire_all()
    assert coord.coordinator_step(db, run, rt.refresh_frontier(["odysseus"]), "d") == plan
    assert len(calls) == 1


@pytest.mark.parametrize("model_id,attestation", [
    ("claude-sonnet-5", "provider-usage-response"),
    ("claude-sonnet-5-5", None),
])
def test_step_rejects_unattested_sonnet_5_5_plan(db, frontier, monkeypatch, model_id, attestation):
    qualify(monkeypatch, executors=("claude", "claude-sonnet"))
    add, _ = frontier
    ref = add("a")["ref"]
    calls = []
    monkeypatch.setattr(estate_router, "execute_claude", lambda prompt, **kw: calls.append(prompt) or {
        **glm_plan_result([ref]), "provider": "claude", "concrete_model": model_id,
        "model_unverified": False, "model_attestation": attestation,
        "provider_usage": {"inputTokens": 31, "outputTokens": 7},
    })
    run = _run(db)
    snapshot = rt.refresh_frontier(["odysseus"])
    assert coord.coordinator_step(db, run, snapshot, "same-frontier") is None
    assert run.checkpoint["coordinator_skip"] == "sonnet_5_5_unattested"
    assert run.checkpoint["coordinator_model"] == model_id
    assert run.counters["tokens_measured"] == 38
    db.expire_all()
    assert coord.coordinator_step(db, run, snapshot, "same-frontier") is None
    assert len(calls) == run.counters["paid_calls"] == 1


def test_legacy_sonnet_plan_is_not_reused_or_replayed(db, frontier, monkeypatch):
    qualify(monkeypatch, executors=("claude",))
    add, _ = frontier
    ref = add("a")["ref"]
    key = coord.plan_key("same-frontier")
    run = _run(db, paid_calls=1)
    run.checkpoint = {**run.checkpoint, "coordinator_lane": "claude-sonnet",
                      "coordinator_model": "claude-sonnet-5", "coordinator_order": [ref],
                      "coordinator_key": key, "coordinator_attempted_key": key}
    db.commit()
    monkeypatch.setattr(estate_router, "execute_claude", lambda *a, **kw: pytest.fail("replayed call"))
    assert coord.coordinator_step(db, run, rt.refresh_frontier(["odysseus"]), "same-frontier") is None
    assert run.checkpoint["coordinator_skip"] == "sonnet_5_5_unattested"
    assert run.counters["paid_calls"] == 1


def test_step_reserves_tokens_and_keeps_the_reservation_on_uncertain_call(db, frontier, monkeypatch):
    qualify(monkeypatch, executors=("claude", "claude-sonnet"))
    add, _ = frontier
    add("a")
    run = _run(db)
    snapshot = rt.refresh_frontier(["odysseus"])
    run.budgets = {**run.budgets, "max_tokens": coord.COORDINATOR_TOKEN_ESTIMATE - 1}
    calls = []

    def interrupted(*args, **kwargs):
        db.refresh(run)
        calls.append(run.counters["tokens_assumed"])
        raise OSError("interrupted at provider boundary")

    monkeypatch.setattr(estate_router, "execute_claude", interrupted)
    assert coord.coordinator_step(db, run, snapshot, "same-frontier") is None
    assert run.checkpoint["coordinator_skip"] == "coordinator_token_headroom"
    assert not calls
    run.budgets = {**run.budgets, "max_tokens": coord.COORDINATOR_TOKEN_ESTIMATE + 1}
    assert coord.coordinator_step(db, run, snapshot, "same-frontier") is None
    db.expire_all()
    assert coord.coordinator_step(db, run, snapshot, "same-frontier") is None
    assert calls == [run.counters["tokens_assumed"]] == [coord.COORDINATOR_TOKEN_ESTIMATE]


def test_preflight_explicit_glm_passthrough_refuses_write_intent(monkeypatch):
    from src.delegation_preflight import delegation_preflight as real_pf
    monkeypatch.setattr(estate_router, "resolve_route", lambda task, record_decision=False: {
        "ok": True, "route": {"host": "lab", "executor": "local", "model_alias": "local-fast"},
        "hosts_checked": [{"host_id": "lab", "qualified_executors": ["local"]}]})
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo_id=None: [])
    result = real_pf([{"task_class": "batch", "repo": "odysseus",
                       "objective": "Run the batch scan", "write": True,
                       "paid_provider": "glm", "allow_paid_escalation": True,
                       "capabilities": ["local-fast"]}])
    unit = result["units"][0]
    assert unit["ok"] is False and unit["recommended_route"] is None
    assert unit["error_code"] == "write_intent_requires_codex_write_lane"

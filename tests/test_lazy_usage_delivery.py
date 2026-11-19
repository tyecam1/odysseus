"""Regression tests for the /lazyUsage delivery corrections.

Activation b102b3ce (2026-11-19) ended budget_exhausted/max_repeat_failures with
zero deliveries. Three distinct tasks were dispatched to a plain local model as
"reconnaissance"; each executed "successfully", stayed `ready` on its owner
card, and was recorded as a failure with the *status* as its signature, so the
third trip of the same signature stopped the run. The tasks were:

* obsidian-phd branch-protection-main: a human-only GitHub settings handoff;
* obsidian-phd icac2026 conference harvest: evidence synthesis needing Zotero;
* obsidian-phd opportunity-radar: an implementation gated by approval_required.

The card metadata below is copied (trimmed) from those real task cards.
"""
import json
import os
from datetime import timedelta

import pytest
import yaml

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()
import core.database as cdb
from core.database import LazyUsageRun, utcnow_naive
from src import estate_router, estate_worker, estate_write_lane as lane
from src import lazy_usage_coordinator as coord, lazy_usage_runtime as rt, park_lease_ops
from tests.helpers.fake_worker import FakeWorker

LAB = "hz2-workstation"
ONE_CALL = {"paid_calls": 1, "tool_calls": 1}

BRANCH_PROTECTION = dict(
    task_id="2026-06-11-branch-protection-main", task_type="human-approval", executor="human",
    execution_mode="handoff", verification_route="V2_HUMAN_VERIFIED", approval_required=True,
    risk_level="low", allowed_paths=[], outputs=[],
    notes="GitHub settings mutation is external mutation: human executor only.")
ICAC = dict(
    task_id="2026-08-30-icac2026-conference-learning-harvest-and-routing", task_type="evidence-synthesis",
    executor="claude_subscription", execution_mode="review-first", requires_zotero=True, requires_mcp=True,
    requires_web=True, execution_host="laptop", approval_required=True,
    verification_route="V2_HUMAN_VERIFIED", allowed_paths=["automation/review/**"],
    outputs=["one conference-learning evidence and routing report"],
    result_path="automation/review/2026-08-30-icac2026-conference-learning-harvest.md")
RADAR = dict(
    task_id="2026-08-30-opportunity-radar-networking-and-research-opportunities", task_type="implementation",
    executor="claude_subscription", execution_mode="implementation", execution_host="compute-box",
    approval_required=True, verification_route="V2_HUMAN_VERIFIED",
    allowed_paths=["Scripts/automation/**", "automation/config/**"],
    outputs=["implemented incremental Opportunity Radar capability"],
    result_path="automation/review/automation/2026-08-30-opportunity-radar-implementation.md")


@pytest.fixture
def db(monkeypatch):
    factory, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", factory)
    monkeypatch.setattr(estate_router, "current_host_id", lambda: LAB)
    monkeypatch.setattr(lane, "_trigger_background_reconcile", lambda: None)
    monkeypatch.setattr(lane, "_observe_worker_execution", lambda execution_id: None)
    session = factory()
    yield session
    session.close()
    engine.dispose()
    os.unlink(tmpfile.name)


class Queue:
    def __init__(self, tmp_path):
        self.tmp_path, self.roots, self.records = tmp_path, {}, []
        self.executor = "none"   # "none" = paid grounded lane, "local" = plain local model

    def add(self, repo, name, **meta):
        root = self.roots.setdefault(repo, self.tmp_path / repo)
        folder = root / "automation/review/agent-tasks/ready"
        folder.mkdir(parents=True, exist_ok=True)
        metadata = {"task_id": name, "title": name, "status": "ready", "priority": "high", **meta}
        (folder / (name + ".agent-task.md")).write_text("---\n" + yaml.safe_dump(metadata) + "---\nBody.\n")
        ref = f"{repo}:ready/{name}.agent-task.md"
        self.records = [r for r in self.records if r["ref"] != ref]
        self.records.append({"ref": ref, "repo_id": repo, "bucket": "ready", "task_id": name,
                             "status": metadata["status"], "priority": "high", "eligible": "unverified"})
        return ref

    def route(self, task, **kwargs):
        qualified = ["local", "codex", "codex-write", "glm", "claude"]
        if self.executor == "local":
            return {"ok": True, "route": {"host": LAB, "executor": "local", "model_alias": "local-fast",
                                          "concrete_model": "qwen3:8b"},
                    "hosts_checked": [{"host_id": LAB, "qualified_executors": qualified}]}
        return {"ok": False, "route": {"host": LAB, "executor": "none", "model_alias": "code-strong"},
                "hosts_checked": [{"host_id": LAB, "qualified_executors": qualified}]}


@pytest.fixture
def queue(tmp_path, monkeypatch):
    q = Queue(tmp_path)
    monkeypatch.setattr(rt, "refresh_frontier", lambda scope: {
        "roots": dict(q.roots), "records": [r for r in q.records if r["repo_id"] in scope],
        "unavailable": {}, "counts": {}, "warnings": []})
    monkeypatch.setattr(estate_router, "resolve_route", q.route)
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda *a, **kw: {"allowed": True})
    monkeypatch.setattr(rt, "delegation_preflight", lambda units: {"ok": True})
    return q


def activate(db, scope=("odysseus",), coordinator=None):
    return rt.activate_run(db, "operator", list(scope), {}, coordinator)["id"]


def advisory_pass(**extra):
    return {"ok": True, "executed": True, "deterministic_gate": "pass", "usage": ONE_CALL, **extra}


def no_dispatch(*args, **kwargs):
    pytest.fail("unexpected model dispatch")


# ------------------------------------------------------------- 1. failure accounting

def test_failure_signature_is_task_revision_and_cause(db):
    run = db.get(LazyUsageRun, activate(db))
    for _ in range(3):
        rt._failure(run, "boom", scope=("odysseus:ready/a.md", "rev1"))
    assert run.counters["repeated_failures"] == 3
    other = db.get(LazyUsageRun, run.id)
    for scope in (("odysseus:ready/a.md", "rev1"), ("odysseus:ready/b.md", "rev1"),
                  ("odysseus:ready/a.md", "rev2")):
        rt._failure(other, "boom", scope=scope)
    # Different tasks, or the same task after its card changed, are separate failures.
    assert other.counters["repeated_failures"] == 1
    rt._failure(other, "other cause", scope=("odysseus:ready/a.md", "rev2"))
    assert other.counters["repeated_failures"] == 1


def test_three_distinct_incomplete_tasks_do_not_trip_repeat_failures(db, queue, monkeypatch):
    """b102b3ce reproduction: three different tasks, each executed and verified but
    still `ready` on its owner card. They must not count as repeats of one failure."""
    for name in "abc":
        queue.add("odysseus", name, execution_mode="read-only")
    monkeypatch.setattr(estate_router, "run_task", lambda task: advisory_pass())
    run_id = activate(db)
    for _ in range(3):
        view = rt.advance(db, run_id)
    assert view["state"] != "budget_exhausted", view["terminal_reason"]
    assert view["counters"]["repeated_failures"] == 0
    assert view["counters"]["no_delivery_turns"] == 3
    ledger = view["checkpoint"]["ledger"]
    assert {e["outcome"] for e in ledger.values()} == {"advisory_complete"}
    assert len(ledger) == 3
    # The accepted-work debt is still visible, not silently dropped.
    assert len(view["owed_reviews"]) == 3


def test_the_same_task_failing_repeatedly_still_trips_the_guard(db, queue, monkeypatch):
    ref = queue.add("odysseus", "a", execution_mode="read-only")
    monkeypatch.setattr(estate_router, "run_task",
                        lambda task: {"ok": False, "executed": True, "error": "boom", "usage": ONE_CALL})
    monkeypatch.setattr(rt, "FAILURE_RETRY_SECONDS", 0)
    run_id = activate(db)
    for _ in range(3):
        row = db.get(LazyUsageRun, run_id)
        row.checkpoint = {**row.checkpoint, "attempted": {}}   # model a retry the fence would allow
        db.commit()
        view = rt.advance(db, run_id)
    assert view["counters"]["repeated_failures"] == 3
    assert view["state"] == "budget_exhausted" and view["terminal_reason"] == "max_repeat_failures"
    assert ref in view["checkpoint"]["ledger"]


def test_two_different_tasks_failing_with_one_cause_are_not_a_repeat(db, queue, monkeypatch):
    for name in "ab":
        queue.add("odysseus", name, execution_mode="read-only")
    monkeypatch.setattr(estate_router, "run_task",
                        lambda task: {"ok": False, "executed": True, "error": "boom", "usage": ONE_CALL})
    run_id = activate(db)
    rt.advance(db, run_id)
    view = rt.advance(db, run_id)
    assert view["counters"]["no_delivery_turns"] == 2
    assert view["counters"]["repeated_failures"] == 1


# ----------------------------------------------------- 2. execution classification

@pytest.mark.parametrize("meta,bucket,kind", [
    (BRANCH_PROTECTION, "ready", "protected_handoff"),
    (ICAC, "ready", "reconnaissance"),
    (RADAR, "ready", "reconnaissance"),
    ({"execution_mode": "implementation"}, "ready", "implementation"),
    ({"execution_mode": "read-only"}, "ready", "evidence"),
    ({"task_type": "evidence-gathering"}, "ready", "evidence"),
    ({"execution_mode": "implementation"}, "review", "review"),
    ({"task_type": "independent-review"}, "ready", "review"),
    ({"executor": "human", "approval_required": False}, "ready", "protected_handoff"),
])
def test_cards_are_classified_from_metadata(meta, bucket, kind):
    assert rt._classify({"bucket": bucket}, meta) == kind


def test_only_implementation_delivers():
    assert rt.DELIVERING_KINDS == {"implementation"}
    assert set(rt.KINDS) - rt.DELIVERING_KINDS == {"reconnaissance", "evidence", "review", "protected_handoff"}


def test_successful_reconnaissance_is_never_delivery_or_debt(db, queue, monkeypatch):
    ref = queue.add("obsidian-phd", "radar", **RADAR)
    monkeypatch.setattr(estate_router, "run_task", lambda task: advisory_pass())
    run_id = activate(db, ("obsidian-phd",))
    view = rt.advance(db, run_id)
    assert view["checkpoint"]["acceptance"]["delivered"] is False
    assert view["checkpoint"]["ledger"][ref]["kind"] == "reconnaissance"
    assert view["checkpoint"]["ledger"][ref]["outcome"] == "advisory_complete"
    assert view["owed_reviews"] == []          # a re-adjudication report is not task output
    assert view["counters"]["repeated_failures"] == 0
    assert view["counters"]["no_delivery_turns"] == 1


def test_reconnaissance_task_objective_is_read_only_adjudication(db, queue, monkeypatch):
    queue.add("obsidian-phd", "radar", **RADAR)
    seen = []
    monkeypatch.setattr(estate_router, "run_task", lambda task: (seen.append(task), advisory_pass())[1])
    rt.advance(db, activate(db, ("obsidian-phd",)))
    assert seen[0]["task_class"] == "repository-reconnaissance"
    assert "re-adjudicate" in seen[0]["objective"]
    assert "mode" not in seen[0]["routing"]


# --------------------------------------------------------- 3. feasibility selection

def test_b102b3ce_routes_are_refused_before_dispatch(db, queue, monkeypatch):
    """The exact failure: all three real cards routed to the plain local model."""
    queue.executor = "local"
    refs = {"bp": queue.add("obsidian-phd", "bp", **BRANCH_PROTECTION),
            "icac": queue.add("obsidian-phd", "icac", **ICAC),
            "radar": queue.add("obsidian-phd", "radar", **RADAR)}
    monkeypatch.setattr(estate_router, "run_task", no_dispatch)
    monkeypatch.setattr(estate_router, "execute_write_via_worker", no_dispatch)
    run_id = activate(db, ("obsidian-phd",))
    view = rt.advance(db, run_id)
    skipped = view["checkpoint"]["skipped"]
    assert skipped[refs["bp"]] == "protected_handoff"
    assert skipped[refs["icac"]] == "requires_zotero_unavailable"
    assert skipped[refs["radar"]] == "ungrounded_local_executor"
    assert view["counters"]["paid_calls"] == 0
    assert view["counters"]["repeated_failures"] == 0
    assert view["state"] == "paused"


def test_protected_handoff_is_recorded_once_and_never_dispatched(db, queue, monkeypatch):
    ref = queue.add("obsidian-phd", "bp", **BRANCH_PROTECTION)
    monkeypatch.setattr(estate_router, "run_task", no_dispatch)
    monkeypatch.setattr(estate_router, "execute_write_via_worker", no_dispatch)
    first = activate(db, ("obsidian-phd",))
    view = rt.advance(db, first)
    entry = view["checkpoint"]["ledger"][ref]
    assert entry["outcome"] == "protected_handoff" and entry["execution_id"] is None
    rt.stop_run(db, first, "operator")
    second = activate(db, ("obsidian-phd",))
    assert db.get(LazyUsageRun, second).checkpoint["ledger"][ref]["outcome"] == "protected_handoff"
    assert rt.advance(db, second)["counters"]["paid_calls"] == 0


def test_requires_zotero_has_no_qualified_lane(db, queue, monkeypatch):
    ref = queue.add("obsidian-phd", "icac", **ICAC)
    verdict = rt._assess(rt.refresh_frontier(["obsidian-phd"]), db.get(LazyUsageRun, activate(db, ("obsidian-phd",))),
                         {"ref": ref, "repo_id": "obsidian-phd", "bucket": "ready"})
    assert verdict["ok"] is False and verdict["blocker"] == "requires_zotero_unavailable"


def test_implementation_without_deliverable_surface_is_infeasible(db, queue, monkeypatch):
    ref = queue.add("odysseus", "w", execution_mode="implementation")
    monkeypatch.setattr(estate_router, "execute_write_via_worker", no_dispatch)
    view = rt.advance(db, activate(db))
    assert view["checkpoint"]["skipped"][ref] == "no_deliverable_surface"
    assert view["counters"]["paid_calls"] == 0


@pytest.mark.parametrize("field", ["allowed_paths", "outputs", "result_path"])
def test_any_declared_deliverable_surface_is_enough(db, queue, field):
    ref = queue.add("odysseus", "w", execution_mode="implementation",
                    **{field: ["x"] if field != "result_path" else "r.md"})
    verdict = rt._assess(rt.refresh_frontier(["odysseus"]), db.get(LazyUsageRun, activate(db)),
                         {"ref": ref, "repo_id": "odysseus", "bucket": "ready"})
    assert verdict["ok"] is True and verdict["delivers"] is True and verdict["write"] is True


def test_qualified_paid_grounded_reconnaissance_is_feasible(db, queue):
    ref = queue.add("obsidian-phd", "radar", **RADAR)
    verdict = rt._assess(rt.refresh_frontier(["obsidian-phd"]), db.get(LazyUsageRun, activate(db, ("obsidian-phd",))),
                         {"ref": ref, "repo_id": "obsidian-phd", "bucket": "ready"})
    assert verdict["ok"] is True and verdict["kind"] == "reconnaissance" and verdict["delivers"] is False


# ---------------------------------------------------------- 4. coordinator context

def _plan_result(refs):
    return {"ok": True, "executed": True, "provider": "glm", "concrete_model": "glm-5.3-flash",
            "output": json.dumps({"selected": refs, "decomposition": [], "next_action": "go"})}


def test_coordinator_sees_feasibility_not_metadata_only(db, queue, monkeypatch):
    refs = {"bp": queue.add("obsidian-phd", "bp", **BRANCH_PROTECTION),
            "icac": queue.add("obsidian-phd", "icac", **ICAC),
            "radar": queue.add("obsidian-phd", "radar", **RADAR),
            "impl": queue.add("odysseus", "impl", execution_mode="implementation", allowed_paths=["src/**"])}
    run = db.get(LazyUsageRun, activate(db, ("odysseus", "obsidian-phd"), {"enabled": True}))
    run.state = "running"
    db.commit()
    frontier = rt.refresh_frontier(["odysseus", "obsidian-phd"])
    evidence = rt.candidate_evidence(frontier, run)
    by_ref = {e["ref"]: e for e in evidence}
    assert by_ref[refs["bp"]]["blocker"] == "protected_handoff" and not by_ref[refs["bp"]]["feasible"]
    assert by_ref[refs["icac"]]["blocker"] == "requires_zotero_unavailable"
    assert by_ref[refs["impl"]]["feasible"] and by_ref[refs["impl"]]["delivers"]
    shown = {r["ref"] for r in coord._candidates(frontier, evidence)}
    assert refs["bp"] not in shown and refs["icac"] not in shown
    assert refs["impl"] in shown and refs["radar"] in shown
    prompt = coord.build_prompt(frontier, run, evidence)
    assert '"why": "requires_zotero_unavailable"' in prompt and '"delivers": true' in prompt
    assert "never select" in prompt


def test_coordinator_makes_no_paid_call_when_nothing_is_feasible(db, queue, monkeypatch):
    queue.add("obsidian-phd", "bp", **BRANCH_PROTECTION)
    queue.add("obsidian-phd", "icac", **ICAC)
    monkeypatch.setattr(coord, "master_enabled", lambda: True)
    monkeypatch.setattr(estate_router, "execute_glm", no_dispatch)
    run = db.get(LazyUsageRun, activate(db, ("obsidian-phd",), {"enabled": True}))
    run.state = "running"
    db.commit()
    frontier = rt.refresh_frontier(["obsidian-phd"])
    evidence = rt.candidate_evidence(frontier, run)
    assert coord.coordinator_step(db, run, frontier, "digest", evidence) is None
    assert run.checkpoint["coordinator_skip"] == "no_feasible_candidates"
    assert run.counters["paid_calls"] == 0


def test_coordinator_plan_is_confined_to_feasible_candidates(db, queue, monkeypatch):
    bp = queue.add("obsidian-phd", "bp", **BRANCH_PROTECTION)
    impl = queue.add("odysseus", "impl", execution_mode="implementation", allowed_paths=["src/**"])
    monkeypatch.setattr(coord, "master_enabled", lambda: True)
    monkeypatch.setattr(coord, "_qualified_executors", lambda: ["glm", "claude"])
    prompts = []
    monkeypatch.setattr(estate_router, "execute_glm",
                        lambda prompt, **kw: (prompts.append(prompt), _plan_result([bp]))[1])
    run = db.get(LazyUsageRun, activate(db, ("odysseus", "obsidian-phd"), {"enabled": True}))
    run.state = "running"
    db.commit()
    frontier = rt.refresh_frontier(["odysseus", "obsidian-phd"])
    evidence = rt.candidate_evidence(frontier, run)
    # The model names an excluded task: its plan is rejected, never trusted.
    assert coord.coordinator_step(db, run, frontier, "digest", evidence) is None
    assert run.checkpoint["coordinator_skip"] == "plan_validation_failed"
    assert impl in prompts[0] and bp not in prompts[0].split("candidates:")[1].split("excluded:")[0]


# ------------------------------------------------------ 5. cross-activation memory

def _age(db, run_id, ref, seconds):
    row = db.get(LazyUsageRun, run_id)
    ledger = json.loads(json.dumps(row.checkpoint["ledger"]))
    ledger[ref]["at"] = (utcnow_naive() - timedelta(seconds=seconds)).isoformat()
    row.checkpoint = {**row.checkpoint, "ledger": ledger}
    db.commit()


def test_unchanged_result_is_reused_then_expires(db, queue, monkeypatch):
    ref = queue.add("odysseus", "a", execution_mode="read-only")
    calls = []
    monkeypatch.setattr(estate_router, "run_task", lambda task: (calls.append(1), advisory_pass())[1])
    first = activate(db)
    rt.advance(db, first)
    assert len(calls) == 1
    rt.stop_run(db, first, "operator")

    second = activate(db)
    inherited = db.get(LazyUsageRun, second).checkpoint
    assert inherited["ledger"][ref]["outcome"] == "advisory_complete"
    assert [d["task_ref"] for d in inherited["owed_reviews"]] == [ref]      # acceptance debt carried
    view = rt.advance(db, second)
    assert len(calls) == 1 and view["checkpoint"]["skipped"][ref] == "result_reusable"
    rt.stop_run(db, second, "operator")

    _age(db, second, ref, rt.ADVISORY_REUSE_SECONDS + 60)       # window expired: a retry is legitimate
    third = activate(db)
    rt.advance(db, third)
    assert len(calls) == 2


def test_changed_card_is_retried_immediately(db, queue, monkeypatch):
    ref = queue.add("odysseus", "a", execution_mode="read-only")
    calls = []
    monkeypatch.setattr(estate_router, "run_task", lambda task: (calls.append(1), advisory_pass())[1])
    first = activate(db)
    rt.advance(db, first)
    rt.stop_run(db, first, "operator")
    queue.add("odysseus", "a", execution_mode="read-only", title="revised after owner feedback")
    rt.advance(db, activate(db))
    assert len(calls) == 2 and ref in queue.records[0]["ref"]


def test_failures_back_off_then_retry_without_permanent_block(db, queue, monkeypatch):
    ref = queue.add("odysseus", "a", execution_mode="read-only")
    calls = []
    monkeypatch.setattr(estate_router, "run_task", lambda task: (
        calls.append(1), {"ok": False, "executed": True, "error": "boom", "usage": ONE_CALL})[1])
    first = activate(db)
    rt.advance(db, first)
    rt.stop_run(db, first, "operator")
    second = activate(db)
    assert rt.advance(db, second)["checkpoint"]["skipped"][ref] == "failure_backoff"
    assert len(calls) == 1
    rt.stop_run(db, second, "operator")
    _age(db, second, ref, rt.FAILURE_RETRY_SECONDS + 60)
    rt.advance(db, activate(db))
    assert len(calls) == 2


def test_legacy_attempted_map_is_inherited_as_a_reuse_window(db, queue, monkeypatch):
    """Runs before this change (like b102b3ce) only stored `attempted`."""
    ref = queue.add("odysseus", "a", execution_mode="read-only")
    frontier = rt.refresh_frontier(["odysseus"])
    revision = rt._assess(frontier, db.get(LazyUsageRun, activate(db)),
                          {"ref": ref, "repo_id": "odysseus", "bucket": "ready"})["revision"]
    legacy = db.query(LazyUsageRun).one()
    legacy.state, legacy.finished_at, legacy.terminal_reason = "budget_exhausted", utcnow_naive(), "max_repeat_failures"
    legacy.checkpoint = {"attempted": {ref: revision}, "owed_reviews": []}
    db.commit()
    monkeypatch.setattr(estate_router, "run_task", no_dispatch)
    view = rt.advance(db, activate(db))
    assert view["checkpoint"]["ledger"][ref]["outcome"] == "attempted_legacy"
    assert view["checkpoint"]["skipped"][ref] == "result_reusable"


def test_owner_acceptance_wait_is_not_redispatched_while_debt_stands(db, queue, monkeypatch):
    ref = queue.add("odysseus", "w", execution_mode="implementation", allowed_paths=["src/**"])
    run_id = activate(db)
    row = db.get(LazyUsageRun, run_id)
    revision = rt._assess(rt.refresh_frontier(["odysseus"]), row,
                          {"ref": ref, "repo_id": "odysseus", "bucket": "ready"})["revision"]
    rt._ledger_put(row, ref, revision, "implementation", "delivered_pending_acceptance", "e1")
    row.checkpoint = {**row.checkpoint, "owed_reviews": [{"task_ref": ref, "gate": "owner_acceptance"}]}
    db.commit()
    monkeypatch.setattr(estate_router, "execute_write_via_worker", no_dispatch)
    assert rt.advance(db, run_id)["checkpoint"]["skipped"][ref] == "awaiting_owner_acceptance"


# --------------------------------------------------- 6. worker-boundary child usage

def test_worker_reports_usage_from_decision_files(tmp_path, monkeypatch):
    root = tmp_path / "worker" / "spool"
    monkeypatch.setattr(estate_worker, "_SPOOL_ROOT", root)
    spool = root / "e-fenced"
    spool.mkdir(parents=True)
    assert estate_worker._execution_usage(spool) == {"paid_calls": 0, "tool_calls": 0}   # never ran
    files = estate_worker._spool_files(spool)
    estate_worker.decide_once(files["run"], {"decision": "abort", "reason": "fenced"})
    assert estate_worker._execution_usage(spool) == {"paid_calls": 0, "tool_calls": 0}   # fenced, writer never ran
    ran = root / "e-ran"
    ran.mkdir()
    estate_worker.decide_once(estate_worker._spool_files(ran)["run"], {"decision": "execute", "unit": "u"})
    assert estate_worker._execution_usage(ran) == {"paid_calls": 1, "tool_calls": 1}
    estate_worker._record_attempt(ran, "finalize", {"n": 1})
    estate_worker._record_attempt(ran, "finalize", {"n": 2})
    estate_worker._record_attempt(ran, "push", {})
    assert estate_worker._execution_usage(ran) == {"paid_calls": 1, "tool_calls": 4}


def test_terminal_result_keeps_worker_reported_usage_and_is_metered(db, queue, monkeypatch):
    queue.add("odysseus", "w", execution_mode="implementation", allowed_paths=["src/**"])
    worker = FakeWorker(monkeypatch)
    monkeypatch.setattr(park_lease_ops, "park_with_worktree", lambda repo, host, branch, session_id: park_lease_ops.park_repo(
        repo, host, "/w/feat", branch=branch, session_id=session_id))
    run_id = activate(db)
    execution_id = rt.advance(db, run_id)["checkpoint"]["in_flight_execution_id"]
    worker.set_state(execution_id, "succeeded", result={"ok": True, "output": "done", "exit_code": 0})
    worker.executions[execution_id]["usage"] = {"paid_calls": 1, "tool_calls": 4}
    lane._apply_view(execution_id, worker._view(execution_id))
    assert json.loads(db.get(cdb.EstateExecution, execution_id).result_json)["usage"] == {"paid_calls": 1, "tool_calls": 4}
    view = rt.advance(db, run_id)
    # Dispatch charged 1 paid + counted tool calls; the worker's extra children are added once.
    assert view["counters"]["paid_calls"] == 1
    assert not view["checkpoint"].get("usage_accounting_pending")
    assert view["state"] == "running"       # metered, so not fenced
    entry = next(iter(view["checkpoint"]["ledger"].values()))
    assert entry["kind"] == "implementation" and entry["outcome"] == "delivered_pending_acceptance"


def test_missing_worker_usage_still_fences_continuation(db, queue, monkeypatch):
    queue.add("odysseus", "w", execution_mode="implementation", allowed_paths=["src/**"])
    worker = FakeWorker(monkeypatch)
    monkeypatch.setattr(park_lease_ops, "park_with_worktree", lambda repo, host, branch, session_id: park_lease_ops.park_repo(
        repo, host, "/w/feat", branch=branch, session_id=session_id))
    run_id = activate(db)
    execution_id = rt.advance(db, run_id)["checkpoint"]["in_flight_execution_id"]
    worker.set_state(execution_id, "succeeded", result={"ok": True, "output": "done", "exit_code": 0})
    lane._apply_view(execution_id, worker._view(execution_id))
    view = rt.advance(db, run_id)
    assert view["checkpoint"]["usage_accounting_pending"] == execution_id
    assert view["state"] == "paused"      # absence is not zero: no unmetered continuation
    # Once the worker boundary's totals are supplied the fence clears and metering is exact.
    row = db.get(cdb.EstateExecution, execution_id)
    row.result_json = json.dumps({**json.loads(row.result_json), "usage": {"paid_calls": 2, "tool_calls": 10}})
    db.commit()
    rt.resume_run(db, run_id, "operator")
    after = rt.advance(db, run_id)
    assert not after["checkpoint"].get("usage_accounting_pending")
    assert after["counters"]["paid_calls"] >= 2


# ------------------------------------------- review findings (Haiku 5.5, 2026-11-19)

def test_paid_advisory_run_is_metered_and_the_activation_continues(db, queue, monkeypatch):
    """Finding 1: the real router result carries no usage key. A paid advisory call must
    not park the activation behind an accounting fence it can never clear."""
    queue.add("odysseus", "a", execution_mode="read-only")
    queue.add("odysseus", "b", execution_mode="read-only")
    real_shape = {"ok": True, "executed": True, "deterministic_gate": "pass",
                  "execution": {"ok": True, "output": "grounded report"}}      # no usage anywhere
    calls = []
    monkeypatch.setattr(estate_router, "run_task", lambda task: (calls.append(1), dict(real_shape))[1])
    run_id = activate(db)
    first = rt.advance(db, run_id)
    assert first["state"] == "running" and not first["checkpoint"].get("usage_accounting_pending")
    assert first["counters"]["paid_calls"] == 1                  # charged once, not double counted
    second = rt.advance(db, run_id)
    assert len(calls) == 2 and second["counters"]["paid_calls"] == 2


def test_worker_proven_not_started_write_does_not_fence(db, queue, monkeypatch):
    """Finding 2: an execution the worker proves never ran owes no child usage."""
    queue.add("odysseus", "w", execution_mode="implementation", allowed_paths=["src/**"])
    worker = FakeWorker(monkeypatch)
    monkeypatch.setattr(park_lease_ops, "park_with_worktree", lambda repo, host, branch, session_id: park_lease_ops.park_repo(
        repo, host, "/w/feat", branch=branch, session_id=session_id))
    run_id = activate(db)
    execution_id = rt.advance(db, run_id)["checkpoint"]["in_flight_execution_id"]
    worker.set_state(execution_id, "start_failed", quiescent=True)
    lane._apply_view(execution_id, worker._view(execution_id))
    assert db.get(cdb.EstateExecution, execution_id).worktree_resolution == "not_started"
    view = rt.advance(db, run_id)
    assert not view["checkpoint"].get("usage_accounting_pending")


def test_one_malformed_card_does_not_starve_the_cards_after_it(db, queue, monkeypatch):
    """Finding 3: an exception while assessing one card must not abort selection."""
    bad = queue.add("odysseus", "a-bad", execution_mode="read-only")
    good = queue.add("odysseus", "z-good", execution_mode="read-only")
    original = rt._assess

    def flaky(frontier, run, record):
        if record["ref"] == bad:
            raise ValueError("malformed card")
        return original(frontier, run, record)

    monkeypatch.setattr(rt, "_assess", flaky)
    seen = []
    monkeypatch.setattr(estate_router, "run_task", lambda task: (seen.append(task["objective"]), advisory_pass())[1])
    view = rt.advance(db, activate(db))
    assert len(seen) == 1 and "z-good" in seen[0]
    assert view["counters"]["repeated_failures"] == 0
    assert good in view["checkpoint"]["ledger"] and bad not in view["checkpoint"]["ledger"]
    assert view["checkpoint"]["skipped"][bad] == "assessment_ValueError"


def test_quota_parked_without_a_stated_reset_is_only_a_bounded_backoff(db, queue):
    """Finding 4: a reconciled-away quota debt must not block an unchanged card forever."""
    ref = queue.add("odysseus", "a", execution_mode="read-only")
    run = db.get(LazyUsageRun, activate(db))
    revision = rt._assess(rt.refresh_frontier(["odysseus"]), run,
                          {"ref": ref, "repo_id": "odysseus", "bucket": "ready"})["revision"]
    rt._ledger_put(run, ref, revision, "reconnaissance", "quota_parked", "e1")
    assert rt._recent_blocker(run, ref, revision) == "quota_retry_pending"
    ledger = json.loads(json.dumps(run.checkpoint["ledger"]))
    ledger[ref]["at"] = (utcnow_naive() - timedelta(seconds=rt.FAILURE_RETRY_SECONDS + 5)).isoformat()
    run.checkpoint = {**run.checkpoint, "ledger": ledger}
    assert rt._recent_blocker(run, ref, revision) is None
    # With a provider-stated future reset it still waits for that reset, however old the entry.
    future = (utcnow_naive() + timedelta(hours=2)).isoformat() + "+00:00"
    run.checkpoint = {**run.checkpoint, "owed_reviews": [{"task_ref": ref, "gate": "verification",
                                                          "error": "usage limit", "retry_after": future}]}
    assert rt._recent_blocker(run, ref, revision) == "quota_retry_pending"


def test_a_delivered_entry_is_not_redispatched_inside_the_reuse_window(db, queue):
    ref = queue.add("odysseus", "a", execution_mode="read-only")
    run = db.get(LazyUsageRun, activate(db))
    revision = rt._assess(rt.refresh_frontier(["odysseus"]), run,
                          {"ref": ref, "repo_id": "odysseus", "bucket": "ready"})["revision"]
    rt._ledger_put(run, ref, revision, "implementation", "delivered", "e1")
    assert rt._recent_blocker(run, ref, revision) == "result_reusable"


def test_history_window_is_not_exhausted_by_unrelated_scopes(db, queue):
    """Finding 5: many recent terminal runs for other repos must not hide in-scope history."""
    ref = queue.add("odysseus", "a", execution_mode="read-only")
    old = db.get(LazyUsageRun, activate(db))
    old.state, old.finished_at, old.terminal_reason = "stopped", utcnow_naive() - timedelta(days=1), "operator_stop"
    old.checkpoint = {"ledger": {ref: {"revision": "r", "kind": "evidence", "outcome": "advisory_complete",
                                       "execution_id": None, "at": utcnow_naive().isoformat()}}}
    db.commit()
    for i in range(60):
        db.add(LazyUsageRun(id=f"other-{i}", state="stopped", created_by="operator", initializer=rt.INITIALIZER,
                            repo_scope=["misumi"], budgets=dict(rt.CEILINGS), started_at=utcnow_naive(),
                            finished_at=utcnow_naive(), terminal_reason="operator_stop",
                            counters={}, checkpoint={}))
    db.commit()
    ledger, _ = rt._inherited_history(db, ["odysseus"])
    assert ref in ledger


def test_selection_evidence_survives_when_another_task_is_dispatched(db, queue, monkeypatch):
    """A recorded handoff and the skipped reasons must persist even on a turn that dispatches."""
    handoff = queue.add("obsidian-phd", "bp", **BRANCH_PROTECTION)
    queue.add("obsidian-phd", "radar", **RADAR)
    monkeypatch.setattr(estate_router, "run_task", lambda task: advisory_pass())
    view = rt.advance(db, activate(db, ("obsidian-phd",)))
    assert view["checkpoint"]["ledger"][handoff]["outcome"] == "protected_handoff"
    assert view["checkpoint"]["skipped"][handoff] == "protected_handoff"
    assert any(e["outcome"] == "advisory_complete" for e in view["checkpoint"]["ledger"].values())


def test_operator_pause_during_selection_is_not_undone(db, queue, monkeypatch):
    """D1: a pause committed while selection runs must survive; only selection evidence is kept."""
    ref = queue.add("odysseus", "a", execution_mode="read-only")
    queue.add("obsidian-phd", "bp", **BRANCH_PROTECTION)
    run_id = activate(db, ("odysseus", "obsidian-phd"))
    row = db.get(LazyUsageRun, run_id)
    row.checkpoint = {**row.checkpoint, "recheck_at": (utcnow_naive() - timedelta(seconds=5)).isoformat()}
    db.commit()
    original = rt._choose

    def choose_then_operator_pauses(frontier, run, plan=None):
        chosen = original(frontier, run, plan)
        with cdb.SessionLocal() as other:
            rt.pause_run(other, run_id, "operator")
        return chosen

    monkeypatch.setattr(rt, "_choose", choose_then_operator_pauses)
    monkeypatch.setattr(estate_router, "run_task", no_dispatch)
    view = rt.advance(db, run_id)
    assert view["state"] == "paused"
    assert view["checkpoint"]["recheck_at"] is None and view["checkpoint"]["pause_reason"] == "operator"
    again = rt.advance(db, run_id)                      # the next tick must still see the pause
    assert again["state"] == "paused" and ref not in again["checkpoint"].get("attempted", {})


def test_operator_pause_during_selection_is_not_undone_when_nothing_is_eligible(db, queue, monkeypatch):
    """The nothing-eligible path used the unreloaded row and let _park overwrite the pause."""
    queue.add("obsidian-phd", "bp", **BRANCH_PROTECTION)
    run_id = activate(db, ("obsidian-phd",))
    row = db.get(LazyUsageRun, run_id)
    row.checkpoint = {**row.checkpoint, "recheck_at": (utcnow_naive() - timedelta(seconds=5)).isoformat()}
    db.commit()
    original = rt._choose

    def choose_then_operator_pauses(frontier, run, plan=None):
        chosen = original(frontier, run, plan)
        with cdb.SessionLocal() as other:
            rt.pause_run(other, run_id, "operator")
        return chosen

    monkeypatch.setattr(rt, "_choose", choose_then_operator_pauses)
    view = rt.advance(db, run_id)
    assert view["state"] == "paused"
    assert view["checkpoint"]["pause_reason"] == "operator" and view["checkpoint"]["recheck_at"] is None
    assert view["checkpoint"]["ledger"][next(iter(view["checkpoint"]["ledger"]))]["outcome"] == "protected_handoff"


def test_debt_reconciled_during_selection_is_persisted_on_a_dispatching_tick(db, queue, monkeypatch):
    """Review: owed_reviews reconciled in _choose must not be discarded by the reload."""
    gone = "obsidian-phd:ready/finished.agent-task.md"
    queue.add("odysseus", "a", execution_mode="read-only")
    run_id = activate(db)
    row = db.get(LazyUsageRun, run_id)
    row.checkpoint = {**row.checkpoint, "owed_reviews": [{"task_ref": gone, "gate": "owner_acceptance"}]}
    db.commit()
    monkeypatch.setattr(rt, "_owner_task_status", lambda checkpoint, frontier: {
        "delivered": True, "status": "done", "reason": "owner acceptance evidence recorded"})
    monkeypatch.setattr(estate_router, "run_task", lambda task: advisory_pass())
    view = rt.advance(db, run_id)
    assert all(d["task_ref"] != gone for d in view["checkpoint"]["owed_reviews"])
    assert db.get(LazyUsageRun, run_id).checkpoint["owed_reviews"] == view["checkpoint"]["owed_reviews"]

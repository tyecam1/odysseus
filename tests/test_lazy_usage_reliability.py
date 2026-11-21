"""Regression tests for the /lazyUsage reliability and acceptance work (2026-11-19).

Each class of defect was reproduced against the deployed runtime (`ba4aa58b`) before
its fix:

1. debt reconciled in one activation reappeared from an older run in the next;
2. execution success, deterministic verification, independent review and owner
   acceptance were one boolean;
3. evidence/review cards could never deliver, and an `approval_required`
   implementation had no governed way past reconnaissance;
4. the dispatch gate ignored `execution_host`, `requires_web/mcp/local_model`;
5. the budget counted dispatches, never tokens;
6. a successful write stayed unfinalised until the controller did it by hand;
7. fabricated review debts of run b102b3ce had no supersession path.
"""
import json
from datetime import timedelta

import pytest

from tests.test_lazy_usage_delivery import (  # noqa: F401  (fixtures + helpers)
    ICAC, RADAR, LAB, ONE_CALL, Queue, activate, advisory_pass, db, no_dispatch, queue)
from tests.helpers.fake_worker import FakeWorker
import core.database as cdb
from core.database import LazyUsageRun, utcnow_naive
from src import estate_router, estate_write_lane as lane
from src import lazy_usage_coordinator as coord, lazy_usage_runtime as rt, park_lease_ops

WRITE = dict(execution_mode="implementation", allowed_paths=["src/**"])


def terminal(db, scope, owed=(), *, settled=None, ledger=None, minutes_ago=0, supersessions=None):
    """A finished activation row, as left by an earlier `am lazy` run."""
    when = utcnow_naive() - timedelta(minutes=minutes_ago)
    row = LazyUsageRun(id=f"old-{len(db.query(LazyUsageRun).all())}-{minutes_ago}", state="stopped",
                       created_by="operator", initializer=rt.INITIALIZER, repo_scope=list(scope),
                       budgets=dict(rt.CEILINGS), started_at=when, finished_at=when,
                       terminal_reason="operator_stop", counters={},
                       checkpoint={"owed_reviews": [dict(d) for d in owed], "ledger": ledger or {},
                                   **({"settled_reviews": settled} if settled else {}),
                                   **({"review_supersessions": supersessions} if supersessions else {})})
    db.add(row)
    db.commit()
    return row


def debt(ref, gate="owner_acceptance", **extra):
    return {"task_id": ref.rsplit("/", 1)[-1], "task_ref": ref, "gate": gate, "execution_id": "e", **extra}


def write_card(queue, monkeypatch, name="w", **meta):
    ref = queue.add("odysseus", name, **{**WRITE, **meta})
    worker = FakeWorker(monkeypatch)
    monkeypatch.setattr(park_lease_ops, "park_with_worktree", lambda repo, host, branch, session_id: park_lease_ops.park_repo(
        repo, host, "/w/feat", branch=branch, session_id=session_id))
    finalize = worker._worktree_finalize

    def finalize_then_move_head(payload):            # the worktree now sits on the finalize commit
        outcome = finalize(payload)
        if outcome.get("commit_sha"):
            worker.head = outcome["commit_sha"]
        return outcome

    worker._worktree_finalize = finalize_then_move_head
    return ref, worker


def finish_write(db, worker, run_id, *, usage=None, result=None):
    view = rt.advance(db, run_id)
    execution_id = view["checkpoint"]["in_flight_execution_id"]
    worker.set_state(execution_id, "succeeded", result=result or {"ok": True, "output": "done", "exit_code": 0})
    worker.executions[execution_id]["usage"] = usage or {"paid_calls": 1, "tool_calls": 1}
    lane._apply_view(execution_id, worker._view(execution_id))
    return execution_id, rt.advance(db, run_id)


# ============================================================ 1. debt reconciliation

A = "odysseus:ready/a.agent-task.md"
P = "obsidian-phd:ready/p.agent-task.md"


def test_task_identity_ignores_the_bucket_a_card_moved_to():
    assert rt._task_key("odysseus:ready/a.agent-task.md") == rt._task_key("odysseus:done/a.agent-task.md")
    assert rt._task_key("odysseus:ready/a.agent-task.md") != rt._task_key("obsidian-phd:ready/a.agent-task.md")


def test_a_debt_resolved_in_a_later_activation_does_not_reappear(db):
    """Live b5db0e86 -> next activation: the older all-repo run still listed the debt that a
    newer run had reconciled away, and the union brought it back every time."""
    terminal(db, ["odysseus", "obsidian-phd"], [debt(A), debt(P)], minutes_ago=60)
    terminal(db, ["odysseus"], [], minutes_ago=10)           # the newer run reconciled A (card is done)
    _, owed = rt._inherited_history(db, ["odysseus"])
    assert owed == []
    _, owed_phd = rt._inherited_history(db, ["obsidian-phd"])
    assert [d["task_ref"] for d in owed_phd] == [P]           # the repo it never touched keeps its debt


def test_a_settled_card_is_a_tombstone_that_outlives_the_reconciling_run(db):
    row = terminal(db, ["odysseus"], [debt(A)], minutes_ago=30)
    run = db.get(LazyUsageRun, activate(db))
    run.checkpoint = {**run.checkpoint, "owed_reviews": [debt(A)]}
    rt._reconcile_review_debts(run, A, acceptance={"delivered": True, "status": "done"})
    db.commit()
    assert rt._task_key(A) in run.checkpoint["settled_reviews"]
    rt.stop_run(db, run.id, "operator")
    # An older run's stale copy of the debt (even under the done/ bucket name) stays settled.
    terminal(db, ["odysseus"], [debt("odysseus:done/a.agent-task.md")], minutes_ago=120)
    _, owed = rt._inherited_history(db, ["odysseus"])
    assert owed == []


def test_a_new_debt_after_settlement_reopens(db):
    terminal(db, ["odysseus"], [], settled={rt._task_key(A): {"at": (utcnow_naive() - timedelta(hours=2)).isoformat(),
                                                             "status": "done"}}, minutes_ago=30)
    newer = debt(A, opened_at=utcnow_naive().isoformat())
    terminal(db, ["odysseus"], [newer], minutes_ago=5)
    _, owed = rt._inherited_history(db, ["odysseus"])
    assert [d["task_ref"] for d in owed] == [A]


def test_new_debts_are_stamped_with_when_they_opened(db, queue, monkeypatch):
    queue.add("odysseus", "a", execution_mode="read-only")
    monkeypatch.setattr(estate_router, "run_task", lambda task: advisory_pass())
    view = rt.advance(db, activate(db))
    assert all(d.get("opened_at") for d in view["owed_reviews"]) and view["owed_reviews"]


# ================================================ 2. four separate pieces of evidence

PASS = {"ok": True, "output": "x", "deterministic_gate": "pass"}
SUCCEEDED = {"lifecycle_state": "succeeded"}
V3 = {"verification_route": "V3_INDEPENDENT_MODEL_ADJUDICATION"}
V2 = {"verification_route": "V2_HUMAN_VERIFIED"}
PENDING = {"delivered": False, "status": "ready"}
ACCEPTED = {"delivered": True, "status": "done"}


def stages(result=None, acceptance=PENDING, meta=V2, author="codex", view=SUCCEEDED, finalization=None):
    return rt.evidence_stages(view, result if result is not None else PASS, acceptance, meta,
                              author_provider=author, finalization=finalization)


def test_exit_zero_and_output_is_execution_success_not_verification():
    s = stages(result={"ok": True, "output": "plausible prose", "exit_code": 0})
    assert s["execution"]["status"] == "succeeded"
    assert s["verification"]["status"] == "unverified"
    assert s["complete"] is False


def test_each_stage_needs_its_own_evidence():
    s = stages(meta=V3)
    assert (s["execution"]["status"], s["verification"]["status"]) == ("succeeded", "pass")
    assert s["review"]["status"] == "required" and s["acceptance"]["status"] == "pending"
    assert s["complete"] is False
    assert stages(meta=V3, acceptance=ACCEPTED)["complete"] is False      # accepted, review still owed
    assert stages(meta=V2, acceptance=ACCEPTED)["complete"] is True       # no independent review required


def test_a_failed_execution_cannot_be_verified_or_accepted_into_completeness():
    s = stages(result={"ok": False, "error": "boom", "deterministic_gate": "pass"}, view={"lifecycle_state": "failed"},
               acceptance=ACCEPTED)
    assert s["execution"]["status"] == "failed" and s["verification"]["status"] == "fail"
    assert s["complete"] is False


@pytest.mark.parametrize("reviewer,author,status", [
    ("claude", "codex", "recorded"),        # different provider family
    ("codex", "codex", "not_independent"),  # the author reviewing itself
    ("glm", "claude", "recorded"),
])
def test_review_must_come_from_another_provider_family(reviewer, author, status):
    meta = {**V3, "review_evidence": [{"reviewer_provider": reviewer, "verdict": "approve", "ref": "pr#1"}]}
    assert stages(meta=meta, author=author)["review"]["status"] == status


def test_a_rejecting_or_unattributed_review_is_not_a_review():
    for entry in ({"reviewer_provider": "claude", "verdict": "reject"}, {"verdict": "approve"}, "approved"):
        assert stages(meta={**V3, "review_evidence": [entry]})["review"]["status"] == "required"


def test_finalization_does_not_substitute_for_deterministic_verification():
    ok = stages(result={"ok": True, "output": "done", "exit_code": 0},
                finalization={"finalized": True, "committed": True, "scope_violations": []})
    assert ok["verification"]["status"] == "unverified"
    assert ok["verification"]["basis"] == "no_deterministic_check"
    checked = stages(finalization={"finalized": True, "committed": True, "scope_violations": []})
    assert checked["verification"] == {"status": "pass", "basis": "deterministic_gate"}
    rejected = stages(result={"ok": True, "deterministic_gate": "fail"},
                      finalization={"finalized": True, "committed": True, "scope_violations": []})
    assert rejected["verification"]["status"] == "fail"
    accepted = stages(result={"ok": True, "output": "done", "exit_code": 0}, acceptance=ACCEPTED,
                      meta={**V3, "review_evidence": [
                          {"reviewer_provider": "claude", "verdict": "approve", "ref": "review"}]},
                      finalization={"finalized": True, "committed": True, "scope_violations": []})
    assert accepted["review"]["status"] == "recorded" and accepted["complete"] is False
    bad = stages(result=PASS,
                 finalization={"finalized": True, "committed": True, "scope_violations": ["src/x"]})
    assert bad["verification"]["status"] == "fail" and bad["verification"]["scope_violations"] == ["src/x"]
    empty = stages(result={"ok": True, "output": "done", "exit_code": 0},
                   finalization={"finalized": True, "committed": False, "scope_violations": []})
    assert empty["verification"]["status"] == "unverified"       # nothing was delivered to verify


def test_owner_acceptance_without_the_other_evidence_is_not_a_clean_delivery(db, queue, monkeypatch):
    ref = queue.add("odysseus", "a", execution_mode="read-only", **V3)
    monkeypatch.setattr(estate_router, "run_task", lambda task: {"ok": True, "executed": True, "output": "prose",
                                                                  "exit_code": 0, "usage": ONE_CALL})
    monkeypatch.setattr(rt, "_owner_task_status", lambda cp, frontier: {"delivered": True, "status": "done"})
    run_id = activate(db)
    view = rt.advance(db, run_id)
    entry = view["checkpoint"]["ledger"][ref]
    assert entry["outcome"] == "accepted_unproven"
    assert view["checkpoint"]["stages"][ref]["verification"]["status"] == "unverified"
    assert {d["gate"] for d in view["owed_reviews"] if d["task_ref"] == ref} == {"verification", "independent_review"}
    assert view["counters"]["no_delivery_turns"] == 1            # the run is not credited with a delivery


# ======================================= 3. classification and the approval transition

REVIEW_SIDE = dict(task_type="evidence-synthesis", approval_required=False,
                   allowed_paths=["automation/review/**"], result_path="automation/review/ev.md")


def assess(db, queue, ref, repo="odysseus"):
    for live in db.query(LazyUsageRun).filter(LazyUsageRun.state.notin_(rt.TERMINAL)).all():
        rt.stop_run(db, live.id, live.created_by)
    run = db.get(LazyUsageRun, activate(db, (repo,)))
    return rt._assess(rt.refresh_frontier([repo]), run, {"ref": ref, "repo_id": repo, "bucket": "ready"})


def test_an_evidence_card_with_a_review_side_deliverable_delivers_through_the_write_lane(db, queue):
    ref = queue.add("obsidian-phd", "ev", **REVIEW_SIDE)
    verdict = assess(db, queue, ref, "obsidian-phd")
    assert verdict["ok"] is True and verdict["kind"] == "evidence"
    assert verdict["delivers"] is True and verdict["write"] is True
    assert verdict["scope"]["allowed"] == ["automation/review/**"]


def test_a_review_card_has_no_delivering_lane_until_a_reviewer_write_lane_is_attested(db, queue):
    ref = queue.add("obsidian-phd", "rv", task_type="independent-review", allowed_paths=["automation/review/**"],
                    outputs=["review verdict"])
    verdict = assess(db, queue, ref, "obsidian-phd")
    assert verdict["kind"] == "review" and verdict["delivers"] is False


def test_an_evidence_deliverable_outside_the_review_area_is_refused(db, queue, monkeypatch):
    ref = queue.add("obsidian-phd", "ev", **{**REVIEW_SIDE, "allowed_paths": ["canonical/**"]})
    monkeypatch.setattr(estate_router, "execute_write_via_worker", no_dispatch)
    verdict = assess(db, queue, ref, "obsidian-phd")
    assert verdict["ok"] is False and verdict["blocker"] == "deliverable_outside_review_area"


def test_read_only_evidence_without_a_deliverable_stays_advisory(db, queue):
    ref = queue.add("obsidian-phd", "ev", execution_mode="read-only")
    verdict = assess(db, queue, ref, "obsidian-phd")
    assert verdict["kind"] == "evidence" and verdict["delivers"] is False and verdict["write"] is False


def test_the_owner_card_directory_is_always_denied_to_a_writer(db, queue):
    ref = queue.add("obsidian-phd", "ev", **REVIEW_SIDE)
    scope = assess(db, queue, ref, "obsidian-phd")["scope"]
    assert any(p.startswith("automation/review/agent-tasks") for p in scope["denied"])


def test_approval_scope_binds_what_the_owner_approved():
    scope = rt.approval_scope(RADAR)
    assert len(scope) == 64 and scope == rt.approval_scope({**RADAR, "title": "reworded"})
    assert scope != rt.approval_scope({**RADAR, "allowed_paths": ["src/**"]})


def valid_approval(meta, **over):
    return {"status": "approved", "approved_by": "tye", "approved_at": "2026-11-19T20:00:00Z",
            "scope_sha256": rt.approval_scope(meta), **over}


def test_an_approval_gated_card_leaves_reconnaissance_only_with_a_bound_owner_approval():
    record = {"bucket": "ready"}
    assert rt._classify(record, RADAR) == "reconnaissance"
    assert rt._classify(record, {**RADAR, "approval": valid_approval(RADAR)}) == "implementation"
    for bad in (valid_approval(RADAR, scope_sha256="0" * 64),            # approved a different scope
                valid_approval(RADAR, approved_by=""),                   # no principal
                valid_approval(RADAR, status="requested"),
                "approved"):
        assert rt._classify(record, {**RADAR, "approval": bad}) == "reconnaissance"


def test_a_scope_change_after_approval_invalidates_it():
    approved = {**RADAR, "approval": valid_approval(RADAR)}
    widened = {**approved, "allowed_paths": [*RADAR["allowed_paths"], "src/**"]}
    assert rt._classify({"bucket": "ready"}, widened) == "reconnaissance"


def test_approved_implementation_dispatches_as_a_write(db, queue):
    card = {**RADAR, "execution_host": "lab"}                    # the real card names an unregistered host
    ref = queue.add("odysseus", "radar", **{**card, "approval": valid_approval(card)})
    verdict = assess(db, queue, ref)
    assert verdict["ok"] is True and verdict["kind"] == "implementation" and verdict["write"] is True


def test_reconnaissance_of_an_approval_gated_card_asks_the_owner_for_one_concrete_approval(db, queue, monkeypatch):
    ref = queue.add("obsidian-phd", "radar", **RADAR)
    monkeypatch.setattr(estate_router, "run_task", lambda task: advisory_pass())
    run_id = activate(db, ("obsidian-phd",))
    view = rt.advance(db, run_id)
    assert view["checkpoint"]["ledger"][ref]["outcome"] == "awaiting_approval"
    (ask,) = [d for d in view["owed_reviews"] if d["task_ref"] == ref]
    assert ask["gate"] == "owner_approval" and ask["scope_sha256"] == rt.approval_scope(RADAR)
    assert "approval" in ask["next_action"]
    rt.stop_run(db, run_id, "operator")
    again = rt.advance(db, activate(db, ("obsidian-phd",)))      # not re-dispatched while the ask stands
    assert again["checkpoint"]["skipped"][ref] == "awaiting_owner_approval"


def test_recording_the_approval_reopens_the_card_for_delivery(db, queue, monkeypatch):
    ref = queue.add("odysseus", "radar", **RADAR)
    monkeypatch.setattr(estate_router, "run_task", lambda task: advisory_pass())
    first = activate(db)
    rt.advance(db, first)
    rt.stop_run(db, first, "operator")
    queue.add("odysseus", "radar", **{**RADAR, "approval": valid_approval(RADAR)})   # the owner edits the card
    verdict = rt._assess(rt.refresh_frontier(["odysseus"]), db.get(LazyUsageRun, activate(db)),
                         {"ref": ref, "repo_id": "odysseus", "bucket": "ready"})
    assert verdict["blocker"] != "awaiting_owner_approval" and verdict["kind"] == "implementation"


# =============================================== 4. capability validation before dispatch

def blocker(db, queue, **meta):
    ref = queue.add("odysseus", "c", **{"execution_mode": "read-only", **meta})
    return assess(db, queue, ref)["blocker"]


def test_a_card_that_needs_the_laptop_is_not_dispatched_to_the_lab(db, queue):
    assert blocker(db, queue, execution_host="laptop") == "execution_host_not_a_worker"


def test_an_unknown_execution_host_fails_closed(db, queue):
    assert blocker(db, queue, execution_host="compute-box") == "execution_host_unresolved"


def test_the_lab_host_label_is_accepted(db, queue):
    assert blocker(db, queue, execution_host="lab") is None


def test_a_host_other_than_the_selected_one_is_refused(db, queue):
    assert blocker(db, queue, execution_host="home") == "execution_host_not_selected"


@pytest.mark.parametrize("need,declared,expected", [
    ("requires_web", {"web"}, None), ("requires_web", set(), "requires_web_unavailable"),
    ("requires_mcp", set(), "requires_mcp_unavailable"), ("requires_mcp", {"mcp"}, None),
])
def test_declared_tool_requirements_are_checked_against_the_host(db, queue, monkeypatch, need, declared, expected):
    monkeypatch.setattr(rt, "_host_capabilities", lambda host_id: set(declared))
    assert blocker(db, queue, **{need: True}) == expected


def test_a_local_model_requirement_needs_a_qualified_local_executor(db, queue, monkeypatch):
    assert blocker(db, queue, requires_local_model=True) is None          # the lab qualifies `local`
    monkeypatch.setattr(queue, "route", lambda task, **kw: {
        "ok": False, "route": {"host": LAB, "executor": "none", "model_alias": "code-strong"},
        "hosts_checked": [{"host_id": LAB, "qualified_executors": ["codex", "codex-write", "glm", "claude"]}]})
    monkeypatch.setattr(estate_router, "resolve_route", queue.route)
    assert blocker(db, queue, requires_local_model=True) == "requires_local_model_unavailable"


def test_false_or_absent_requirements_never_block(db, queue):
    assert blocker(db, queue, requires_web=False, requires_mcp=False, requires_zotero=False) is None


def test_the_lab_declares_only_capabilities_it_really_has():
    hosts = {h["id"]: h for h in estate_router._load_yaml("estate")["hosts"]}
    declared = set((hosts[LAB].get("worker") or {}).get("capabilities") or [])
    assert declared <= {"web"} and "zotero" not in declared and "mcp" not in declared


# ======================================== 5. dispatches are not tokens: conservative limits

def test_run_status_separates_dispatches_from_token_usage(db):
    view = rt.run_dict(db.get(LazyUsageRun, activate(db)))
    assert view["usage"] == {"dispatches": 0, "tool_calls": 0, "tokens_measured": 0, "tokens_assumed": 0,
                             "tokens_total": 0, "basis": "no usage yet"}
    assert "max_tokens" in view["budgets"]


def test_an_unmeasured_paid_dispatch_is_charged_a_conservative_estimate(db, queue, monkeypatch):
    queue.add("odysseus", "a", execution_mode="read-only")
    monkeypatch.setattr(estate_router, "run_task", lambda task: advisory_pass())
    view = rt.advance(db, activate(db))
    assert view["counters"]["tokens_assumed"] == rt.UNMEASURED_TOKEN_ESTIMATE
    assert view["counters"].get("tokens_measured", 0) == 0
    assert view["usage"]["dispatches"] == 1 and "assumed" in view["usage"]["basis"]


def test_measured_provider_tokens_replace_the_estimate(db, queue, monkeypatch):
    queue.add("odysseus", "a", execution_mode="read-only")
    tokens = {"inputTokens": 10, "outputTokens": 200, "cacheReadInputTokens": 3000, "cacheCreationInputTokens": 400}
    monkeypatch.setattr(estate_router, "run_task", lambda task: advisory_pass(provider_usage=tokens))
    view = rt.advance(db, activate(db))
    assert view["counters"]["tokens_measured"] == 3610
    assert view["counters"].get("tokens_assumed", 0) == 0
    assert view["usage"]["basis"] == "measured"


def test_the_token_ceiling_ends_the_run_even_when_nothing_is_measurable(db, queue, monkeypatch):
    for name in "abc":
        queue.add("odysseus", name, execution_mode="read-only")
    monkeypatch.setattr(estate_router, "run_task", lambda task: advisory_pass())
    run_id = rt.activate_run(db, "operator", ["odysseus"], {"max_tokens": rt.UNMEASURED_TOKEN_ESTIMATE + 1})["id"]
    rt.advance(db, run_id)
    view = rt.advance(db, run_id)
    assert view["state"] == "budget_exhausted" and view["terminal_reason"] == "max_tokens"


def test_a_dispatch_whose_estimate_would_cross_the_ceiling_is_refused_before_it_runs(db, queue, monkeypatch):
    queue.add("odysseus", "a", execution_mode="read-only")
    monkeypatch.setattr(estate_router, "run_task", no_dispatch)
    run_id = rt.activate_run(db, "operator", ["odysseus"], {"max_tokens": rt.UNMEASURED_TOKEN_ESTIMATE - 1})["id"]
    view = rt.advance(db, run_id)
    assert view["state"] == "budget_exhausted" and view["terminal_reason"] == "max_tokens"
    assert view["counters"]["paid_calls"] == 0


def test_the_token_ceiling_cannot_be_raised_above_the_hard_ceiling(db):
    run = rt.activate_run(db, "operator", ["odysseus"], {"max_tokens": 10 ** 12})
    assert run["budgets"]["max_tokens"] == rt.CEILINGS["max_tokens"]


def test_a_write_dispatch_without_measurable_tokens_is_charged_the_larger_estimate(db, queue, monkeypatch):
    ref, worker = write_card(queue, monkeypatch)
    run_id = activate(db)
    _, view = finish_write(db, worker, run_id)
    assert view["counters"]["tokens_assumed"] == rt.UNMEASURED_WRITE_TOKEN_ESTIMATE


# ================================== 6. worker-owned finalisation, restart, lease release

def test_a_successful_write_is_finalised_and_its_lease_released_without_the_controller(db, queue, monkeypatch):
    ref, worker = write_card(queue, monkeypatch)
    run_id = activate(db)
    execution_id, view = finish_write(db, worker, run_id)
    row = db.get(cdb.EstateExecution, execution_id)
    db.refresh(row)
    assert row.worktree_resolution == "finalized"
    assert "worktree.finalize" in worker.verbs()
    assert view["checkpoint"].get("lease") is None and not view["checkpoint"].get("lease_release_debt")
    assert view["checkpoint"]["ledger"][ref]["outcome"] == "unverified"
    assert view["checkpoint"]["stages"][ref]["verification"]["basis"] == "no_deterministic_check"
    assert {d["gate"] for d in view["owed_reviews"] if d["task_ref"] == ref} == {"verification"}
    lease = db.query(cdb.ParkLease).filter_by(session_id=run_id).one()
    db.refresh(lease)
    assert lease.status == "released"


@pytest.mark.parametrize("requires_review", [False, True])
def test_unverified_write_keeps_its_debt_and_is_not_reimplemented_next_activation(
        db, queue, monkeypatch, requires_review):
    ref, worker = write_card(queue, monkeypatch, **(V3 if requires_review else {}))
    first = activate(db)
    execution_id, view = finish_write(db, worker, first)
    assert view["counters"]["no_delivery_turns"] == 1
    assert view["checkpoint"]["acceptance"]["status"] == "verification_pending"
    gap = next(d for d in view["owed_reviews"] if d["gate"] == "verification")
    assert gap["evidence_gap"] is True and gap["execution_id"] == execution_id
    assert {d["gate"] for d in view["owed_reviews"]} == (
        {"verification", "independent_review"} if requires_review else {"verification"})
    rt.stop_run(db, first, "operator")
    monkeypatch.setattr(estate_router, "execute_write_via_worker", no_dispatch)
    second = activate(db)
    view = rt.advance(db, second)
    assert view["checkpoint"]["skipped"][ref] == "awaiting_verification"
    assert view["counters"]["paid_calls"] == 0
    assert any(d["gate"] == "verification" for d in view["owed_reviews"])


def test_a_deterministically_checked_write_can_await_owner_acceptance(db, queue, monkeypatch):
    ref, worker = write_card(queue, monkeypatch)
    _, view = finish_write(db, worker, activate(db), result=PASS)
    assert view["checkpoint"]["ledger"][ref]["outcome"] == "delivered_pending_acceptance"
    assert {d["gate"] for d in view["owed_reviews"] if d["task_ref"] == ref} == {"owner_acceptance"}


def test_legacy_verification_helper_rejects_success_prose_without_a_check():
    assert not rt.verify_attempt({"lifecycle_state": "succeeded", "result": {
        "ok": True, "exit_code": 0, "output": "tests all passed"}}, {})
    assert rt.verify_attempt({"lifecycle_state": "succeeded", "result": PASS}, {})


def test_finalisation_carries_the_cards_scope_and_a_provenance_message(db, queue, monkeypatch):
    ref, worker = write_card(queue, monkeypatch, allowed_paths=["automation/review/**"],
                             denied_paths=["**/.env"])
    run_id = activate(db)
    finish_write(db, worker, run_id)
    (payload,) = [p for _h, verb, p in worker.calls if verb == "worktree.finalize"]
    assert payload["allowed_paths"] == ["automation/review/**"]
    assert "**/.env" in payload["denied_paths"]
    assert any(p.startswith("automation/review/agent-tasks") for p in payload["denied_paths"])
    assert payload["commit_message"].startswith("task(")


def test_a_failed_finalisation_is_recorded_as_a_debt_not_hidden(db, queue, monkeypatch):
    ref, worker = write_card(queue, monkeypatch)
    worker.finalize_outcome = {"outcome": "finalize_ambiguous", "head": "c" * 40, "parent": None,
                               "trailer_matches": False}
    run_id = activate(db)
    _, view = finish_write(db, worker, run_id)
    assert view["checkpoint"]["ledger"][ref]["outcome"] == "finalize_failed"
    assert {"finalization"} == {d["gate"] for d in view["owed_reviews"] if d["task_ref"] == ref}
    assert view["checkpoint"]["lease_release_debt"]
    assert view["state"] == "paused" and "finali" in view["checkpoint"]["pause_reason"]
    assert view["counters"]["repeated_failures"] == 1


def test_a_scope_violating_write_is_not_verified_or_delivered(db, queue, monkeypatch):
    ref, worker = write_card(queue, monkeypatch)
    worker.finalize_outcome = {**worker.finalize_outcome, "scope_violations": ["src/tampered.py"]}
    run_id = activate(db)
    _, view = finish_write(db, worker, run_id)
    assert view["checkpoint"]["ledger"][ref]["outcome"] == "scope_violation"
    assert view["checkpoint"]["stages"][ref]["verification"]["status"] == "fail"
    assert view["owed_reviews"] == [] or all(d["gate"] != "owner_acceptance" for d in view["owed_reviews"])


def test_finalisation_after_a_service_restart_is_idempotent(db, queue, monkeypatch):
    """The observation is re-entered after a crash between finalising and recording."""
    ref, worker = write_card(queue, monkeypatch)
    run_id = activate(db)
    execution_id, _ = finish_write(db, worker, run_id)
    row = db.get(cdb.EstateExecution, execution_id)
    db.refresh(row)
    again = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=LAB, commit_message="m")
    assert again["finalized"] is True and again.get("already_finalized") is True
    assert worker.verbs().count("worktree.finalize") == 1


# ================================================ 7. supersede fabricated review debts

B102 = ["obsidian-phd:ready/2026-06-11-branch-protection-main.agent-task.md",
        "obsidian-phd:ready/2026-08-30-icac2026-conference-learning-harvest-and-routing.agent-task.md",
        "obsidian-phd:ready/2026-08-30-opportunity-radar-networking-and-research-opportunities.agent-task.md"]


def supersede(db, run, refs=B102, **over):
    args = dict(reason="owner instruction 2026-11-19: debts rest on fabricated local-model output",
                evidence=["docs/runtime-work-packages/2026-11-19-lazyusage-delivery-corrections.md",
                          "run b102b3ce: qwen3:8b, executor=local, no repository access"])
    return rt.supersede_review_debts(db, "aoteru-admin", run.id, refs, **{**args, **over})


def test_fabricated_review_debts_can_be_superseded_with_owner_authorised_evidence(db):
    run = terminal(db, ["odysseus", "misumi", "obsidian-phd"], [debt(r) for r in B102], minutes_ago=300)
    result = supersede(db, run)
    assert result["superseded"] == sorted(B102)
    db.refresh(run)
    assert run.checkpoint["owed_reviews"] == []
    records = run.checkpoint["review_supersessions"]
    assert {r["task_ref"] for r in records} == set(B102)
    assert all(r["by"] == "aoteru-admin" and r["reason"] and r["evidence"] and r["original"]["gate"] == "owner_acceptance"
               for r in records)
    _, owed = rt._inherited_history(db, ["obsidian-phd"])
    assert owed == []                                       # and it stays gone in every later activation


def test_supersession_does_not_mark_the_tasks_delivered_or_reusable(db):
    run = terminal(db, ["obsidian-phd"], [debt(B102[2])], minutes_ago=300)
    supersede(db, run, [B102[2]])
    ledger, _ = rt._inherited_history(db, ["obsidian-phd"])
    assert B102[2] not in ledger or ledger[B102[2]]["outcome"] != "delivered"


@pytest.mark.parametrize("over", [{"reason": ""}, {"reason": "  "}, {"evidence": []}, {"evidence": [""]}])
def test_supersession_needs_a_reason_and_evidence(db, over):
    run = terminal(db, ["obsidian-phd"], [debt(B102[0])], minutes_ago=300)
    with pytest.raises(rt.RunError) as err:
        supersede(db, run, [B102[0]], **over)
    assert err.value.status_code == 422
    db.refresh(run)
    assert len(run.checkpoint["owed_reviews"]) == 1


def test_only_debts_that_exist_can_be_superseded(db):
    run = terminal(db, ["obsidian-phd"], [debt(B102[0])], minutes_ago=300)
    with pytest.raises(rt.RunError) as err:
        supersede(db, run, [B102[1]])
    assert err.value.status_code == 404


def test_a_live_activation_cannot_have_its_debts_superseded(db):
    run = db.get(LazyUsageRun, activate(db, ("obsidian-phd",)))
    run.checkpoint = {**run.checkpoint, "owed_reviews": [debt(B102[0])]}
    db.commit()
    with pytest.raises(rt.RunError) as err:
        supersede(db, run, [B102[0]])
    assert err.value.status_code == 409


def _route_client(scopes):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from routes.lazy_usage_routes import setup_lazy_usage_routes
    app = FastAPI()

    @app.middleware("http")
    async def identity(request: Request, call_next):
        request.state.api_token = True
        request.state.api_token_owner = "operator"
        request.state.api_token_scopes = scopes
        return await call_next(request)

    app.include_router(setup_lazy_usage_routes())
    return TestClient(app)


BODY = {"run_id": "x", "task_refs": ["odysseus:ready/a.agent-task.md"], "reason": "r", "evidence": ["e"]}


def test_the_supersede_route_refuses_a_read_only_token():
    assert _route_client(["estate:read"]).post("/api/lazy-usage/supersede", json=BODY).status_code in {401, 403}


def test_the_supersede_route_works_with_the_execute_scope(db, monkeypatch):
    run = terminal(db, ["obsidian-phd"], [debt(B102[0])], minutes_ago=300)
    monkeypatch.setattr("routes.lazy_usage_routes.get_db_session", lambda: cdb.SessionLocal())
    response = _route_client(["estate:execute"]).post("/api/lazy-usage/supersede", json={
        **BODY, "run_id": run.id, "task_refs": [B102[0]]})
    assert response.status_code == 200 and response.json()["superseded"] == [B102[0]]


# ------------------------------------------------ independent review of this change (GLM-5.3, 2026-11-19)

def test_an_evidence_gap_debt_survives_the_settle_tombstone_across_activations(db):
    """A card accepted without independent review keeps that debt in later activations."""
    opened = (utcnow_naive() - timedelta(hours=3)).isoformat()
    gap = debt(A, gate="independent_review", evidence_gap=True, opened_at=opened)
    terminal(db, ["odysseus"], [gap, debt(A, opened_at=opened)], minutes_ago=60,
             settled={rt._task_key(A): {"at": (utcnow_naive() - timedelta(hours=1)).isoformat(), "status": "done"}})
    _, owed = rt._inherited_history(db, ["odysseus"])
    assert [(d["gate"]) for d in owed] == ["independent_review"]     # owner_acceptance is settled, the gap is not


def test_a_reviewer_alias_of_the_authors_family_is_not_independent():
    for alias in ("sol", "gpt-6.1-terra", "Luna", "codex-auto-review"):
        meta = {**V3, "review_evidence": [{"reviewer_provider": alias, "verdict": "approve"}]}
        assert stages(meta=meta, author="codex")["review"]["status"] == "not_independent", alias
    for alias in ("sonnet", "claude-sonnet-5", "opus", "haiku-5.5"):
        meta = {**V3, "review_evidence": [{"reviewer_provider": alias, "verdict": "approve"}]}
        assert stages(meta=meta, author="codex")["review"]["status"] == "recorded", alias


def test_an_unrecognised_reviewer_alias_fails_closed():
    meta = {**V3, "review_evidence": [{"reviewer_provider": "mystery-model", "verdict": "approve"}]}
    assert stages(meta=meta, author="codex")["review"]["status"] == "required"


def test_a_crash_after_finalising_does_not_double_charge_the_execution(db, queue, monkeypatch):
    ref, worker = write_card(queue, monkeypatch)
    run_id = activate(db)
    view = rt.advance(db, run_id)
    execution_id = view["checkpoint"]["in_flight_execution_id"]
    worker.set_state(execution_id, "succeeded", result={"ok": True, "output": "done", "exit_code": 0})
    worker.executions[execution_id]["usage"] = {"paid_calls": 1, "tool_calls": 1}
    lane._apply_view(execution_id, worker._view(execution_id))
    original = rt._reconcile_review_debts

    def crash(*args, **kwargs):
        raise RuntimeError("process died after finalising")

    monkeypatch.setattr(rt, "_reconcile_review_debts", crash)
    with pytest.raises(RuntimeError):
        rt._observe(db, db.get(LazyUsageRun, run_id))
    db.rollback()
    before = dict(db.get(LazyUsageRun, run_id).counters)
    monkeypatch.setattr(rt, "_reconcile_review_debts", original)
    after = rt.advance(db, run_id)["counters"]
    assert after["tokens_assumed"] == before["tokens_assumed"] == rt.UNMEASURED_WRITE_TOKEN_ESTIMATE
    assert after["paid_calls"] == before["paid_calls"]


def test_a_pre_upgrade_debt_keyed_only_by_task_id_is_carried_forward(db):
    legacy = {"task_id": "2026-06-11-old-task", "gate": "owner_acceptance", "execution_id": "e"}
    terminal(db, ["obsidian-phd"], [legacy], minutes_ago=300)
    _, owed = rt._inherited_history(db, ["obsidian-phd"])
    assert [d["task_id"] for d in owed] == ["2026-06-11-old-task"]


# ================ live run ae1b1f20 (2026-11-19): a quota-failed write left its lease active ==========

QUOTA_RESULT = {"ok": False, "exit_code": 1, "error": "ERROR: You've hit your usage limit. try again at Nov 20th, 2026 9:08 PM.",
                "provider": "codex"}


def failed_write(db, worker, run_id, result=None, *, dirty=False):
    view = rt.advance(db, run_id)
    execution_id = view["checkpoint"]["in_flight_execution_id"]
    worker.clean = not dirty                # the writer ran after admission; it may have left partial work
    worker.set_state(execution_id, "failed", result=result or dict(QUOTA_RESULT))
    worker.executions[execution_id]["usage"] = {"paid_calls": 1, "tool_calls": 1}
    lane._apply_view(execution_id, worker._view(execution_id))
    return execution_id, rt.advance(db, run_id)


def lease_of(db, run_id):
    row = db.query(cdb.ParkLease).filter_by(session_id=run_id).one()
    db.refresh(row)
    return row


def test_a_failed_write_releases_its_own_lease_without_the_controller(db, queue, monkeypatch):
    ref, worker = write_card(queue, monkeypatch)
    run_id = activate(db)
    execution_id, view = failed_write(db, worker, run_id)
    assert lease_of(db, run_id).status == "released"
    row = db.get(cdb.EstateExecution, execution_id)
    db.refresh(row)
    assert row.worktree_resolution == "recovered"
    assert view["checkpoint"].get("lease") is None and not view["checkpoint"].get("lease_release_debt")
    assert all(d["gate"] != "recovery" for d in view["owed_reviews"])


def test_a_failed_write_with_a_dirty_worktree_is_not_auto_recovered(db, queue, monkeypatch):
    """Partial work may be in the tree: only the governed controller path may decide about it."""
    ref, worker = write_card(queue, monkeypatch)
    run_id = activate(db)
    execution_id, view = failed_write(db, worker, run_id, dirty=True)
    assert lease_of(db, run_id).status == "active"
    assert "recovery" in {d["gate"] for d in view["owed_reviews"] if d["task_ref"] == ref}
    assert view["checkpoint"]["lease_release_debt"]


def test_a_quota_refused_write_is_charged_no_assumed_tokens(db, queue, monkeypatch):
    ref, worker = write_card(queue, monkeypatch)
    run_id = activate(db)
    _, view = failed_write(db, worker, run_id)
    assert view["checkpoint"]["ledger"][ref]["outcome"] == "quota_parked"
    assert view["counters"].get("tokens_assumed", 0) == 0     # the provider refused it; nothing ran
    assert view["counters"]["paid_calls"] == 1                # the dispatch itself is still counted


def test_a_lease_left_by_a_finished_activation_is_recovered_by_the_next_one(db, queue, monkeypatch):
    """Restart recovery: the previous run stopped with a failed execution still holding the lease."""
    ref, worker = write_card(queue, monkeypatch)
    first = activate(db)
    execution_id, _ = failed_write(db, worker, first)
    # Undo the in-run recovery to model the state the deployed code left behind.
    row = db.get(cdb.EstateExecution, execution_id)
    lease = lease_of(db, first)
    row.worktree_resolution, lease.status, lease.released_at = "unresolved", "active", None
    db.commit()
    rt.stop_run(db, first, "operator")
    second = activate(db)
    monkeypatch.setattr(estate_router, "execute_write_via_worker", no_dispatch)
    view = rt.advance(db, second)
    assert lease_of(db, first).status == "released"
    assert view["checkpoint"]["recovered_leases"][0]["execution_id"] == execution_id
    assert view["checkpoint"]["skipped"].get(ref) != "repo_lease_held"


def test_coordinator_tokens_are_metered_from_provider_usage(db, queue, monkeypatch):
    impl = queue.add("odysseus", "impl", **WRITE)
    monkeypatch.setattr(coord, "master_enabled", lambda: True)
    monkeypatch.setattr(coord, "_qualified_executors", lambda: ["glm", "claude"])
    usage = {"inputTokens": 2, "outputTokens": 5000, "cacheReadInputTokens": 7000, "cacheCreationInputTokens": 9000}
    monkeypatch.setattr(estate_router, "execute_glm", lambda prompt, **kw: {
        **_coordinator_plan(impl), "provider_usage": usage})
    run = db.get(LazyUsageRun, activate(db, ("odysseus",), {"enabled": True}))
    run.state = "running"
    db.commit()
    frontier = rt.refresh_frontier(["odysseus"])
    coord.coordinator_step(db, run, frontier, "digest", rt.candidate_evidence(frontier, run))
    assert run.counters["tokens_measured"] == 21002
    assert run.counters.get("tokens_assumed", 0) == 0


def test_an_unmeasured_coordinator_call_is_charged_an_estimate(db, queue, monkeypatch):
    impl = queue.add("odysseus", "impl", **WRITE)
    monkeypatch.setattr(coord, "master_enabled", lambda: True)
    monkeypatch.setattr(coord, "_qualified_executors", lambda: ["glm", "claude"])
    monkeypatch.setattr(estate_router, "execute_glm", lambda prompt, **kw: _coordinator_plan(impl))
    run = db.get(LazyUsageRun, activate(db, ("odysseus",), {"enabled": True}))
    run.state = "running"
    db.commit()
    frontier = rt.refresh_frontier(["odysseus"])
    coord.coordinator_step(db, run, frontier, "digest", rt.candidate_evidence(frontier, run))
    assert run.counters["tokens_assumed"] == coord.COORDINATOR_TOKEN_ESTIMATE


def _coordinator_plan(ref):
    return {"ok": True, "executed": True, "provider": "glm", "concrete_model": "glm-5.3-flash",
            "output": json.dumps({"selected": [ref], "decomposition": ["step"], "next_action": "go"})}


# ------------------------------------------------ independent review of the lease-recovery delta (GLM-5.3)

def stuck_orphan(db, queue, monkeypatch, name="w"):
    """A terminal activation's failed write whose worktree is dirty: recovery can never succeed."""
    ref, worker = write_card(queue, monkeypatch, name)
    first = activate(db)
    execution_id, _ = failed_write(db, worker, first, dirty=True)
    rt.stop_run(db, first, "operator")
    worker.clean = False
    return ref, worker, first, execution_id


def test_a_permanently_unrecoverable_orphan_is_attempted_once_per_activation(db, queue, monkeypatch):
    ref, worker, first, _ = stuck_orphan(db, queue, monkeypatch)
    monkeypatch.setattr(estate_router, "execute_write_via_worker", no_dispatch)
    second = activate(db)
    rt.advance(db, second)
    after_first_pass = db.get(LazyUsageRun, second).counters["tool_calls"]
    verifies = worker.verbs().count("worktree.verify")
    for _ in range(3):
        row = db.get(LazyUsageRun, second)
        row.state = "running"
        row.checkpoint = {**row.checkpoint, "recheck_at": None, "phase": "idle"}
        db.commit()
        rt.advance(db, second)
    # No further recovery attempts (worker calls) and no further budget drain on the foreign lease.
    assert worker.verbs().count("worktree.verify") == verifies
    attempts = [e for e in db.get(LazyUsageRun, second).checkpoint["recovered_leases"]]
    assert len(attempts) == 1 and attempts[0]["recovered"] is False
    assert lease_of(db, first).status == "active"            # still protected: dirty work is never discarded


def test_foreign_leases_are_left_alone_while_the_orphan_is_recovered(db, queue, monkeypatch):
    ref, worker, first, execution_id = stuck_orphan(db, queue, monkeypatch)
    worker.clean = True                                      # the owner has since cleaned it: recoverable
    for i, repo in enumerate(("misumi", "obsidian-phd")):    # operator park leases on the other repos in scope
        park_lease_ops.park_repo(repo, LAB, f"/w/op{i}", branch=f"op/{i}", session_id=f"operator-{i}")
    second = rt.activate_run(db, "operator", ["odysseus", "misumi", "obsidian-phd"], {})["id"]
    monkeypatch.setattr(estate_router, "execute_write_via_worker", no_dispatch)
    rt.advance(db, second)
    assert lease_of(db, first).status == "released"
    assert db.query(cdb.ParkLease).filter(cdb.ParkLease.session_id.like("operator-%"),
                                          cdb.ParkLease.status == "active").count() == 2


def test_a_foreign_active_lease_is_never_touched_by_the_sweep(db, queue, monkeypatch):
    queue.add("odysseus", "a", execution_mode="read-only")
    park_lease_ops.park_repo("odysseus", LAB, "/w/op", branch="op/x", session_id="operator-session")
    monkeypatch.setattr(estate_router, "run_task", lambda task: advisory_pass())
    run_id = activate(db)
    view = rt.advance(db, run_id)
    lease = db.query(cdb.ParkLease).filter_by(session_id="operator-session").one()
    db.refresh(lease)
    assert lease.status == "active" and not view["checkpoint"].get("recovered_leases")


def test_a_failed_coordinator_call_is_charged_an_estimate_but_a_refusal_is_not(db, queue, monkeypatch):
    impl = queue.add("odysseus", "impl", **WRITE)
    monkeypatch.setattr(coord, "master_enabled", lambda: True)
    monkeypatch.setattr(coord, "_qualified_executors", lambda: ["glm", "claude"])
    frontier = None

    def run_with(result):
        nonlocal frontier
        for live in db.query(LazyUsageRun).filter(LazyUsageRun.state.notin_(rt.TERMINAL)).all():
            rt.stop_run(db, live.id, live.created_by)
        monkeypatch.setattr(estate_router, "execute_glm", lambda prompt, **kw: result)
        run = db.get(LazyUsageRun, activate(db, ("odysseus",), {"enabled": True}))
        run.state = "running"
        db.commit()
        frontier = rt.refresh_frontier(["odysseus"])
        coord.coordinator_step(db, run, frontier, "digest", rt.candidate_evidence(frontier, run))
        return run.counters

    timed_out = run_with({"ok": False, "executed": True, "error": "timed out after 120s", "error_code": "timeout"})
    assert timed_out["tokens_assumed"] == coord.COORDINATOR_TOKEN_ESTIMATE
    refused = run_with({"ok": False, "executed": True, "provider": "glm", "stderr": "usage limit reached",
                        "error": "You've hit your usage limit", "error_code": "quota_exhausted"})
    assert refused.get("tokens_assumed", 0) == 0


# ====== live run f4b6f653 (2026-11-20): findings from the first successful unattended writes ======

def test_observing_an_in_flight_write_is_not_charged_as_tool_usage(db, queue, monkeypatch):
    """Polling a running writer (every tick, plus lease renewal) consumed the 150 tool-call ceiling in
    ~40 minutes, so a healthy gpt-6.2-sol write was cancelled by a budget stop."""
    ref, worker = write_card(queue, monkeypatch)
    run_id = activate(db)
    first = rt.advance(db, run_id)
    baseline = first["counters"]["tool_calls"]
    for _ in range(12):
        view = rt.advance(db, run_id)
    assert view["checkpoint"]["in_flight_execution_id"] == first["checkpoint"]["in_flight_execution_id"]
    assert view["counters"]["tool_calls"] == baseline


def test_a_budget_stop_that_cancels_a_write_is_recorded_as_interrupted_not_failed(db, queue, monkeypatch):
    ref, worker = write_card(queue, monkeypatch)
    run_id = activate(db)
    execution_id = rt.advance(db, run_id)["checkpoint"]["in_flight_execution_id"]

    def cancel_ends_the_writer(host, verb, payload):
        if verb == "cancel":
            worker.set_state(payload["execution_id"], "failed", result={"ok": False, "error": "execution cancelled"})
            worker.executions[payload["execution_id"]]["usage"] = {"paid_calls": 1, "tool_calls": 1}
            lane._apply_view(payload["execution_id"], worker._view(payload["execution_id"]))   # as the real worker reports it

    worker.on_call = cancel_ends_the_writer
    row = db.get(LazyUsageRun, run_id)
    row.counters = {**row.counters, "tool_calls": rt.CEILINGS["max_tool_calls"] + 1}      # budget exhausted in flight
    db.commit()
    view = rt.advance(db, run_id)
    for _ in range(3):
        if view["state"] in rt.TERMINAL:
            break
        view = rt.advance(db, run_id)
    assert view["state"] == "budget_exhausted"
    assert view["checkpoint"]["ledger"][ref]["outcome"] == "interrupted"
    assert view["counters"]["repeated_failures"] == 0
    # and the next activation may retry it at once: an interrupted run is not evidence about the task
    successor = db.get(LazyUsageRun, activate(db))
    assert successor.checkpoint["ledger"][ref]["outcome"] == "interrupted"
    assert rt._recent_blocker(successor, ref, view["checkpoint"]["ledger"][ref]["revision"]) is None


@pytest.mark.parametrize("outcome", ["scope_violation", "finalize_failed", "failed"])
def test_outcomes_that_cost_a_whole_write_back_off_before_the_next_attempt(db, queue, outcome):
    ref = queue.add("odysseus", "w", **WRITE)
    run = db.get(LazyUsageRun, activate(db))
    revision = rt._assess(rt.refresh_frontier(["odysseus"]), run,
                          {"ref": ref, "repo_id": "odysseus", "bucket": "ready"})["revision"]
    rt._ledger_put(run, ref, revision, "implementation", outcome, "e1")
    assert rt._recent_blocker(run, ref, revision) == "failure_backoff"
    ledger = json.loads(json.dumps(run.checkpoint["ledger"]))
    ledger[ref]["at"] = (utcnow_naive() - timedelta(seconds=rt.FAILURE_RETRY_SECONDS + 5)).isoformat()
    run.checkpoint = {**run.checkpoint, "ledger": ledger}
    assert rt._recent_blocker(run, ref, revision) is None


SHA = "c" * 40


def verification_debt(ref):
    return {"task_ref": ref, "gate": "verification", "evidence_gap": True, "commit_sha": SHA,
            "execution_id": "e", "opened_at": utcnow_naive().isoformat()}


def with_debt(db, queue, **card):
    ref = queue.add("odysseus", "w", **{**WRITE, **card})
    run = db.get(LazyUsageRun, activate(db))
    run.checkpoint = {**run.checkpoint, "owed_reviews": [verification_debt(ref)]}
    return ref, run


def test_finalised_write_debt_records_the_commit_it_covers(db, queue, monkeypatch):
    ref, worker = write_card(queue, monkeypatch)
    run_id = activate(db)
    _, view = finish_write(db, worker, run_id)
    gap = [d for d in view["owed_reviews"] if d["task_ref"] == ref and d["gate"] == "verification"]
    assert gap and gap[0]["commit_sha"] == worker.finalize_outcome["commit_sha"]


def test_a_passing_verification_record_for_that_exact_commit_clears_the_debt(db, queue):
    good = [{"result": "pass", "commit_sha": SHA, "ref": "pytest tests -q: 9748 passed", "verified_by": "tye"}]
    ref, run = with_debt(db, queue, verification_evidence=good)
    rt._resolve_met_debts(run, ref, rt.refresh_frontier(["odysseus"]))
    assert run.checkpoint["owed_reviews"] == []


@pytest.mark.parametrize("record", [
    {"result": "pass", "commit_sha": "d" * 40, "ref": "r", "verified_by": "tye"},       # another commit
    {"result": "fail", "commit_sha": SHA, "ref": "r", "verified_by": "tye"},            # a failing check
    {"result": "pass", "commit_sha": SHA, "ref": "r"},                                  # nobody attests it
    {"result": "pass", "commit_sha": SHA, "verified_by": "tye"},                        # no reference
    "pass",
])
def test_a_verification_record_that_does_not_attest_this_commit_keeps_the_debt(db, queue, record):
    ref, run = with_debt(db, queue, verification_evidence=[record])
    rt._resolve_met_debts(run, ref, rt.refresh_frontier(["odysseus"]))
    assert [d["gate"] for d in run.checkpoint["owed_reviews"]] == ["verification"]


def test_a_real_failure_that_coincides_with_a_pending_stop_is_still_a_failure(db, queue, monkeypatch):
    """Review (GLM-5.3): `interrupted` must not hide a deterministic failure from the repeat guard."""
    ref, worker = write_card(queue, monkeypatch)
    run_id = activate(db)
    execution_id = rt.advance(db, run_id)["checkpoint"]["in_flight_execution_id"]
    worker.set_state(execution_id, "failed", result={"ok": False, "error": "codex crashed: segmentation fault"})
    worker.executions[execution_id]["usage"] = {"paid_calls": 1, "tool_calls": 1}
    lane._apply_view(execution_id, worker._view(execution_id))
    rt.stop_run(db, run_id, "operator")                       # the stop lands while the failure is unobserved
    view = db.get(LazyUsageRun, run_id)
    for _ in range(3):
        if view.state in rt.TERMINAL:
            break
        rt.advance(db, run_id)
        db.refresh(view)
    assert view.checkpoint["ledger"][ref]["outcome"] == "failed"
    assert view.counters["repeated_failures"] == 1


# ---- learning ingested from live runs f4b6f653 / 473209ae (2026-11-20/21) ----------------------------

def test_a_write_objective_tells_the_writer_the_controller_records_traces_and_owner_cards(db, queue):
    """Writers kept editing their own owner card and recording evals/ prompt-application traces; the scope
    gate reverts those and reports a scope_violation that costs a whole write. Say so up front."""
    ref = queue.add("odysseus", "w", **WRITE)
    verdict = assess(db, queue, ref)
    objective = verdict["task"]["objective"]
    assert "outside the allowed paths" in objective
    assert "prompt-application" in objective and "controller records" in objective
    assert "owner task card" in objective


def test_a_read_only_objective_is_not_given_the_write_scope_notice(db, queue):
    ref = queue.add("odysseus", "a", execution_mode="read-only")
    assert "controller records" not in assess(db, queue, ref)["task"]["objective"]

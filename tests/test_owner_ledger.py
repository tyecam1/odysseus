"""The owner decision ledger: storage rules, and that a ledger approval lifts the same gate a card-written one does."""
import json
from datetime import timedelta

import pytest

from core.database import RoutingDecision
from src import owner_ledger as ledger, lazy_usage_runtime as rt
from tests.test_lazy_usage_runtime import db, frontier  # noqa: F401  (fixtures)

SCOPE = "a" * 64
OTHER = "b" * 64


def put(db, **over):
    kw = dict(owner="operator", kind="approval", task_ref="odysseus:ready/t.md", task_id="t", scope_sha256=SCOPE,
              actor="owner", via="phone", rationale="fine")
    kw.update(over)
    return ledger.record(db, **kw)


def test_approval_is_read_back_by_task_and_scope(db):
    put(db)
    assert ledger.approved_scopes(db, "operator") == {("odysseus", "t", SCOPE)}
    assert ledger.held_scopes(db, "operator") == frozenset()


def test_decisions_are_owner_scoped(db):
    put(db)
    assert ledger.approved_scopes(db, "someone-else") == frozenset()
    assert ledger.listing(db, "someone-else") == []
    row_id = ledger.listing(db, "operator")[0]["id"]
    assert ledger.revoke(db, row_id, "someone-else") is False
    assert ledger.approved_scopes(db, "operator") == {("odysseus", "t", SCOPE)}


def test_a_later_decision_supersedes_the_earlier_one(db):
    put(db)
    put(db, kind="decline", rationale="no")
    assert ledger.approved_scopes(db, "operator") == frozenset()
    assert ledger.held_scopes(db, "operator") == {("odysseus", "t", SCOPE)}
    put(db, kind="approval")
    assert ledger.approved_scopes(db, "operator") == {("odysseus", "t", SCOPE)}
    assert ledger.held_scopes(db, "operator") == frozenset()
    states = [r["status"] for r in ledger.listing(db, "operator")]
    assert states.count("active") == 1 and states.count("superseded") == 2


def test_revoke_withdraws_an_approval(db):
    row_id = put(db)
    assert ledger.revoke(db, row_id, "operator") is True
    assert ledger.approved_scopes(db, "operator") == frozenset()
    assert ledger.revoke(db, row_id, "operator") is False


def test_a_snooze_expires(db):
    put(db, kind="defer", defer_days=3)
    assert ledger.held_scopes(db, "operator") == {("odysseus", "t", SCOPE)}
    row = db.query(RoutingDecision).filter_by(task_class=ledger.TASK_CLASS).one()
    data = json.loads(row.escalation_reason)
    data["expires"] = (ledger._now() - timedelta(minutes=1)).isoformat()
    row.escalation_reason = json.dumps(data)
    db.commit()
    assert ledger.held_scopes(db, "operator") == frozenset()


def test_a_snooze_has_a_ceiling(db):
    put(db, kind="defer", defer_days=10_000)
    row = db.query(RoutingDecision).filter_by(task_class=ledger.TASK_CLASS).one()
    when = ledger._stamp(json.loads(row.escalation_reason)["expires"])
    assert (when - ledger._now()) <= timedelta(days=ledger.MAX_DEFER_DAYS, minutes=1)


@pytest.mark.parametrize("over", [
    {"kind": "maybe"}, {"actor": "robot"}, {"owner": ""}, {"task_id": "../x"}, {"scope_sha256": "abc"},
    {"scope_sha256": "G" * 64}, {"task_ref": "nocolon"}, {"via": "Phone Reply"},
    {"actor": "advisor"},                                   # an advisor decision must name its model
    {"actor": "advisor", "model": "x y"},
])
def test_malformed_decisions_are_refused(db, over):
    with pytest.raises(ledger.LedgerError):
        put(db, **over)
    assert db.query(RoutingDecision).filter_by(task_class=ledger.TASK_CLASS).count() == 0


def test_an_advisor_decision_records_its_model_and_stays_distinguishable(db):
    put(db, actor="advisor", model="claude-opus-5-5", via="advisor-delegation")
    entry = ledger.listing(db, "operator")[0]
    assert entry["actor"] == "advisor" and entry["via"] == "advisor-delegation"
    assert db.query(RoutingDecision).filter_by(task_class=ledger.TASK_CLASS).one().concrete_model == "claude-opus-5-5"


def test_owner_load_counts_active_card_settlements_for_this_owner_in_the_window(db, monkeypatch):
    now = ledger._now()
    monkeypatch.setattr(ledger, "_now", lambda: now - timedelta(days=2))
    put(db, kind="decline", task_id="old")
    monkeypatch.setattr(ledger, "_now", lambda: now)
    put(db, task_id="advised", actor="advisor", model="claude-opus-5-5")
    put(db, kind="decline", task_id="declined")
    put(db, kind="defer", task_id="deferred")
    put(db, kind="escalate", task_id="escalated", actor="advisor", model="claude-opus-5-5")
    put(db, task_ref="policy:advisor-approvals", task_id="delegation")
    put(db, owner="other-owner", task_id="other")
    revoked = put(db, task_id="revoked")
    assert ledger.revoke(db, revoked, "operator")
    from src.owner_inbox import _digest_text
    load = ledger.owner_load(db, "operator", open_gates=3, since=now - timedelta(days=1))
    assert load == {"open": 3, "agent_or_advisor": 1, "owner": 1}
    assert _digest_text({"owner_load": load}, [])[1] == (
        "Owner gates: 3 open. Settled in 24h: 1 by agent or advisor, 1 by owner."
    )


def test_rationale_is_plain_bounded_text(db):
    put(db, rationale="<b>ok</b>\n`rm -rf`\x00" + "x" * 900)
    text = ledger.listing(db, "operator")[0]["rationale"]
    assert len(text) <= 300 and not any(c in text for c in "<>`\n\x00")


# ---- the runtime reads it exactly like a card-written approval

def gated(add, **meta):
    record = add("g", write=True, approval_required=True, **meta)
    frontier_now = rt.refresh_frontier(["odysseus"])
    card, _ = rt._contract(frontier_now, record)
    return record, card


def test_ledger_approval_lifts_the_gate_for_that_exact_scope(db, frontier, monkeypatch):
    add, _ = frontier
    record, card = gated(add)
    monkeypatch.setattr(rt, "_LEDGER_APPROVALS", frozenset())
    assert rt._classify(record, card) == "reconnaissance"
    scope = rt.approval_scope(card)
    put(db, task_id="g", scope_sha256=scope)
    rt.refresh_owner_ledger(db, "operator")
    assert rt._classify(record, card) == "implementation"


def test_a_changed_scope_invalidates_the_ledger_approval(db, frontier):
    add, _ = frontier
    record, card = gated(add)
    put(db, task_id="g", scope_sha256=rt.approval_scope(card))
    rt.refresh_owner_ledger(db, "operator")
    assert rt._classify(record, card) == "implementation"
    widened = {**card, "allowed_paths": ["src/**", "routes/**"]}
    assert rt._classify(record, widened) == "reconnaissance"


def test_an_approval_for_another_task_or_owner_does_not_apply(db, frontier):
    add, _ = frontier
    record, card = gated(add)
    scope = rt.approval_scope(card)
    put(db, task_id="other", scope_sha256=scope)
    put(db, owner="someone-else", task_id="g", scope_sha256=scope)
    rt.refresh_owner_ledger(db, "operator")
    assert rt._classify(record, card) == "reconnaissance"


def test_a_revoked_or_declined_approval_stops_applying(db, frontier):
    add, _ = frontier
    record, card = gated(add)
    row_id = put(db, task_id="g", scope_sha256=rt.approval_scope(card))
    rt.refresh_owner_ledger(db, "operator")
    assert rt._classify(record, card) == "implementation"
    ledger.revoke(db, row_id, "operator")
    rt.refresh_owner_ledger(db, "operator")
    assert rt._classify(record, card) == "reconnaissance"


def test_an_unreadable_ledger_honours_nothing(db, frontier, monkeypatch):
    add, _ = frontier
    record, card = gated(add)
    put(db, task_id="g", scope_sha256=rt.approval_scope(card))
    rt.refresh_owner_ledger(db, "operator")
    assert rt._classify(record, card) == "implementation"
    monkeypatch.setattr(ledger, "approved_scopes", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    rt.refresh_owner_ledger(db, "operator")
    assert rt._classify(record, card) == "reconnaissance"


def test_advance_refreshes_the_ledger_for_the_runs_owner(db, frontier, monkeypatch):
    add, _ = frontier
    record, card = gated(add)
    put(db, owner="operator", task_id="g", scope_sha256=rt.approval_scope(card))
    monkeypatch.setattr(rt, "_LEDGER_APPROVALS", frozenset())
    run_id = rt.activate_run(db, "operator", ["odysseus"], {})["id"]
    rt.pause_run(db, run_id, "operator")                    # advance refreshes first, then respects the pause: nothing dispatches
    rt.advance(db, run_id)
    assert ("odysseus", "g", rt.approval_scope(card)) in rt._LEDGER_APPROVALS


def test_the_same_task_id_in_another_repository_is_another_card(db, frontier):  # noqa: F811
    add, _ = frontier
    record, card = gated(add)
    put(db, task_ref="misumi:ready/g.md", task_id="g", scope_sha256=rt.approval_scope(card))     # approved in ANOTHER repo
    rt.refresh_owner_ledger(db, "operator")
    assert rt._classify(record, card) == "reconnaissance"
    put(db, task_ref="odysseus:ready/g.md", task_id="g", scope_sha256=rt.approval_scope(card))
    rt.refresh_owner_ledger(db, "operator")
    assert rt._classify(record, card) == "implementation"
    # deciding one repository's card does not supersede the other's
    assert ledger.approved_scopes(db, "operator") == {("misumi", "g", rt.approval_scope(card)), ("odysseus", "g", rt.approval_scope(card))}


def test_racing_decisions_resolve_to_the_newest_never_both(db):
    first = put(db)
    second = put(db, kind="decline")
    # simulate the race: a writer that read before the other committed leaves its row active too
    row = db.query(RoutingDecision).filter_by(id=first).one()
    row.status = "active"
    db.commit()
    assert ledger.approved_scopes(db, "operator") == frozenset()          # the newer decline wins
    assert ledger.held_scopes(db, "operator") == {("odysseus", "t", SCOPE)}
    assert db.query(RoutingDecision).filter_by(id=second).one().status == "active"


def test_a_snooze_without_a_readable_expiry_is_not_a_hold(db):
    put(db, kind="defer")
    row = db.query(RoutingDecision).filter_by(task_class=ledger.TASK_CLASS).one()
    data = json.loads(row.escalation_reason)
    data["expires"] = "garbage"
    row.escalation_reason = json.dumps(data)
    db.commit()
    assert ledger.held_scopes(db, "operator") == frozenset()
    data["expires"] = None
    row.escalation_reason = json.dumps(data)
    db.commit()
    assert ledger.held_scopes(db, "operator") == frozenset()


def test_generic_routing_telemetry_cannot_mint_a_reserved_class(db):
    from src import estate_router
    for reserved in ("owner_decision", "lazyusage_learning", "lazyusage_advisor_review"):
        decision_id = estate_router._record_decision({"task_class": reserved}, host_id="lab", executor="deterministic",
                                                     model_alias=None, concrete_model=None, status="complete")
        row = db.query(RoutingDecision).filter_by(id=decision_id).one()
        assert row.task_class == "unclassified"


def test_an_approval_after_reconnaissance_is_not_blocked_as_already_attempted(db, frontier):  # noqa: F811
    add, _ = frontier
    record, card = gated(add)
    run_id = rt.activate_run(db, "operator", ["odysseus"], {})["id"]
    run = rt._load(db, run_id)
    revision = "rev1"
    run.checkpoint = {**run.checkpoint, "attempted": {record["ref"]: revision},
                      "ledger": {record["ref"]: {"revision": revision, "kind": "reconnaissance", "outcome": "awaiting_approval",
                                                  "execution_id": "e", "at": rt.utcnow_naive().isoformat()}}}
    assert rt._recent_blocker(run, record["ref"], revision, "reconnaissance") == "attempted_this_activation"
    assert rt._recent_blocker(run, record["ref"], revision, "implementation") is None
    assert rt._recent_blocker(run, record["ref"], revision) == "attempted_this_activation"      # unknown kind: unchanged


def test_a_withdrawn_approval_stops_a_selected_dispatch(db, frontier, monkeypatch):  # noqa: F811
    add, _ = frontier
    record, card = gated(add)
    row_id = put(db, task_id="g", task_ref=record["ref"], scope_sha256=rt.approval_scope(card))
    rt.refresh_owner_ledger(db, "operator")
    assert rt._classify(record, card) == "implementation"
    chosen_then_revoked = rt._choose
    def revoke_after_choice(*a, **k):
        out = chosen_then_revoked(*a, **k)
        ledger.revoke(db, row_id, "operator")                               # the owner revokes while the run is selecting
        return out
    monkeypatch.setattr(rt, "_choose", revoke_after_choice)
    monkeypatch.setattr(rt.park_lease_ops, "park_with_worktree", lambda *a, **k: pytest.fail("no lease may be taken"))
    monkeypatch.setattr(rt, "delegation_preflight", lambda *a, **k: pytest.fail("no preflight may run"))
    run_id = rt.activate_run(db, "operator", ["odysseus"], {})["id"]
    view = rt.advance(db, run_id)
    assert view["state"] == "paused" and "approval withdrawn" in view["checkpoint"]["pause_reason"]


def test_revoking_the_winning_row_does_not_uncover_an_older_approval(db):
    first = put(db)
    second = put(db, kind="decline")
    db.query(RoutingDecision).filter_by(id=first).one().status = "active"       # the race: both rows active
    db.commit()
    assert ledger.approved_scopes(db, "operator") == frozenset()
    assert ledger.revoke(db, second, "operator")
    assert ledger.approved_scopes(db, "operator") == frozenset()                # the tombstone hides the older approval
    assert ledger.held_scopes(db, "operator") == frozenset()
    put(db)                                                                     # a fresh decision after the revoke is effective
    assert ledger.approved_scopes(db, "operator") == {("odysseus", "t", SCOPE)}


def test_other_owners_rows_never_crowd_out_this_owners_and_like_wildcards_do_not_match(db):
    put(db, owner="operator", task_id="mine")
    for i in range(520):
        put(db, owner="someone-else", task_id=f"x{i}", scope_sha256=f"{i:064x}", commit=False)
    db.commit()
    assert ledger.approved_scopes(db, "operator") == {("odysseus", "mine", SCOPE)}
    assert ledger.approved_scopes(db, "oper%") == frozenset() and ledger.approved_scopes(db, "oper_tor") == frozenset()
    put(db, owner="100%", task_id="pct")
    assert ledger.approved_scopes(db, "100%") == {("odysseus", "pct", SCOPE)} and ledger.approved_scopes(db, "1000") == frozenset()


def test_an_approval_gated_review_card_is_not_parked_by_the_pre_dispatch_recheck(db, frontier):  # noqa: F811
    add, _ = frontier
    add("rv", approval_required=True, task_type="review")
    run_id = rt.activate_run(db, "operator", ["odysseus"], {})["id"]
    view = rt.advance(db, run_id)
    assert "approval withdrawn" not in str((view["checkpoint"] or {}).get("pause_reason") or "")

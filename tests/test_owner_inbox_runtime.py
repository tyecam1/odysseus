"""The inbox wiring: what reaches the phone, the advisor floor, and that a confirmed approval is bound to the card's
CURRENT scope and fingerprint, re-read from fresh facts at the moment of confirmation."""
import pytest

from src import owner_inbox as ib, owner_inbox_runtime as glue, owner_ledger as ledger, lazy_usage_runtime as rt
from tests.test_lazy_usage_runtime import db, frontier  # noqa: F401  (fixtures)

OWNER = "operator"


def card(**over):
    return {"executor": "claude_subscription", "execution_mode": "implementation", "task_type": "implementation",
            "risk_level": "medium", "allowed_paths": ["src/**", "tests/**"], **over}


@pytest.mark.parametrize("over,ok", [
    ({}, True), ({"risk_level": "low"}, True), ({"risk_level": "high"}, False), ({"risk_level": ""}, False),
    ({"executor": "human"}, False), ({"executor": ""}, False), ({"executor": None}, False),
    ({"execution_mode": "handoff"}, False), ({"task_type": "human-approval"}, False),
    ({"allowed_paths": []}, False), ({"allowed_paths": None}, False), ({"allowed_paths": ["src/**", ""]}, False),
    ({"allowed_paths": ["/etc/**"]}, False), ({"allowed_paths": ["~/x"]}, False), ({"allowed_paths": ["../x"]}, False),
    ({"allowed_paths": ["src/../x"]}, False), ({"allowed_paths": [".github/workflows/**"]}, False),
    ({"allowed_paths": ["config/secrets/**"]}, False), ({"allowed_paths": ["src/credentials.py"]}, False),
    ({"allowed_paths": ["deploy/.env"]}, False), ({"allowed_paths": ["keys/id_rsa"]}, False), ({"allowed_paths": ["a\\b"]}, False),
    ({"allowed_paths": ["**"]}, False), ({"allowed_paths": ["*"]}, False), ({"allowed_paths": ["**/*.py"]}, False),
    ({"allowed_paths": ["*.md"]}, False), ({"allowed_paths": ["src/*"]}, True),
])
def test_advisor_floor(over, ok):
    assert glue.advisor_floor(card(**over)) is ok


def test_the_fingerprint_also_moves_with_the_card_body():
    base = {"title": "T", "risk_level": "low"}
    assert glue.card_facts(base, "one")["fp"] != glue.card_facts(base, "two")["fp"]
    assert glue.card_facts(base, "one")["fp"] == glue.card_facts(base, "one")["fp"]


def test_card_facts_are_built_from_the_card_and_the_fingerprint_moves_with_anything_the_owner_approves():
    base = {"title": "Glovebox shortlist", "risk_level": "medium", "allowed_paths": ["a/**"], "notes": "n"}
    facts = glue.card_facts(base)
    assert facts["card_line"] == "Glovebox shortlist, medium risk" and len(facts["fp"]) == 64
    for change in ({"title": "Other"}, {"risk_level": "high"}, {"allowed_paths": ["b/**"]}, {"notes": "changed"}, {"executor": "x"}):
        assert glue.card_facts({**base, **change})["fp"] != facts["fp"]
    assert glue.card_facts({**base, "irrelevant": 1})["fp"] == facts["fp"]


def gated(add, **meta):
    record = add("g", write=True, approval_required=True, **meta)
    snapshot = rt.refresh_frontier(["odysseus"])
    meta_now, _ = rt._contract(snapshot, record)
    return record, meta_now


def debt(ref="odysseus:ready/g.md", **over):
    return {"task_id": "g", "task_ref": ref, "gate": "owner_approval", "opened_at": "2026-11-20T10:00:00", **over}


@pytest.fixture(autouse=True)
def fresh_cache():
    glue._cache.update(at=0.0, value=None, owner=None)
    yield
    glue._cache.update(at=0.0, value=None, owner=None)


def test_a_high_risk_approval_reaches_the_phone_and_the_delegation_question_does_not(db, frontier, monkeypatch):  # noqa: F811
    add, _ = frontier
    gated(add, risk_level="high")
    monkeypatch.setattr(rt, "all_owed_reviews", lambda db_, owner: [debt()])
    out = glue.gather(OWNER)
    assert [c["kind"] for c in out] == ["approval"]                    # nothing the advisor could decide, so no delegation ask
    assert out[0]["task_id"] == "g" and len(out[0]["scope"]) == 64 and len(out[0]["fp"]) == 64
    assert out[0]["card_line"] == "g, high risk"                       # identity from the card, not from a model


def test_while_the_advisor_worker_is_not_shipped_nobody_is_asked_to_delegate_and_floor_cards_stay_on_the_phone(db, frontier, monkeypatch):  # noqa: F811
    add, _ = frontier
    gated(add, risk_level="medium", executor="claude_subscription")
    monkeypatch.setattr(rt, "all_owed_reviews", lambda db_, owner: [debt()])
    assert glue.ADVISOR_APPROVALS_READY is False
    assert [c["kind"] for c in glue.gather(OWNER)] == ["approval"]
    ledger.record(db, owner=OWNER, kind="approval", task_ref="policy:advisor-approvals", task_id=ib.DELEGATION_TASK_ID,
                  scope_sha256=ib.DELEGATION_SCOPE, actor="owner", via="phone-reply")
    glue._cache["value"] = None
    assert [c["kind"] for c in glue.gather(OWNER)] == ["approval"]     # even a recorded delegation hides nothing yet
    assert glue.advisor_step(OWNER) == []


def test_a_floor_eligible_approval_triggers_the_delegation_question_once(db, frontier, monkeypatch):  # noqa: F811
    monkeypatch.setattr(glue, "ADVISOR_APPROVALS_READY", True)
    add, _ = frontier
    gated(add, risk_level="medium", executor="claude_subscription")
    monkeypatch.setattr(rt, "all_owed_reviews", lambda db_, owner: [debt()])
    assert sorted(c["kind"] for c in glue.gather(OWNER)) == ["approval", "delegation"]
    ledger.record(db, owner=OWNER, kind="decline", task_ref="policy:advisor-approvals", task_id=ib.DELEGATION_TASK_ID,
                  scope_sha256=ib.DELEGATION_SCOPE, actor="owner", via="phone-reply")
    glue._cache["value"] = None
    assert sorted(c["kind"] for c in glue.gather(OWNER)) == ["approval"]   # declined: not asked again, the approval stays the owner's


def test_the_scan_cache_is_per_owner(db, frontier, monkeypatch):  # noqa: F811
    add, _ = frontier
    gated(add, risk_level="high")
    monkeypatch.setattr(rt, "all_owed_reviews", lambda db_, owner: [debt()] if owner == OWNER else [])
    assert len(glue.gather(OWNER)) == 1
    assert glue.gather("someone-else") == []


def test_a_decided_card_is_not_asked_again(db, frontier, monkeypatch):  # noqa: F811
    add, _ = frontier
    _, meta = gated(add, risk_level="high")
    monkeypatch.setattr(rt, "all_owed_reviews", lambda db_, owner: [debt()])
    ledger.record(db, owner=OWNER, kind="defer", task_ref="odysseus:ready/g.md", task_id="g",
                  scope_sha256=rt.approval_scope(meta), actor="owner", via="phone-reply")
    assert glue.gather(OWNER) == []


def item_for(record, meta, **over):
    live_meta, live_body = rt._contract(rt.refresh_frontier(["odysseus"]), record)
    return {"id": "i" * 12, "kind": "approval", "state": "open", "name": "glove", "task_ref": record["ref"], "task_id": "g",
            "scope": rt.approval_scope(meta), "fp": glue.card_facts(live_meta, live_body)["fp"], **over}


def confirm(item, **over):
    return {"op": "approve", "item": item["id"], "confirmed": True, **over}


def test_a_confirmed_approval_is_bound_to_the_current_scope(db, frontier, monkeypatch):  # noqa: F811
    add, _ = frontier
    record, meta = gated(add)
    monkeypatch.setattr(rt, "all_owed_reviews", lambda db_, owner: [debt()])
    item = item_for(record, meta)
    text, status = glue.apply_factory(OWNER)(confirm(item), {item["id"]: item}, "d1")
    assert status == "done" and "Approved" in text
    assert ledger.approved_scopes(db, OWNER) == {("odysseus", "g", rt.approval_scope(meta))}
    assert ledger.listing(db, OWNER)[0]["via"] == "phone-reply"


def test_an_approval_that_is_not_confirmed_is_never_written(db, frontier, monkeypatch):  # noqa: F811
    add, _ = frontier
    record, meta = gated(add)
    monkeypatch.setattr(rt, "all_owed_reviews", lambda db_, owner: [debt()])
    item = item_for(record, meta)
    apply = glue.apply_factory(OWNER)
    assert apply({"op": "approve", "item": item["id"]}, {item["id"]: item}, "d")[1] == "error"
    assert apply({"op": "approve", "item": item["id"], "confirmed": "yes"}, {item["id"]: item}, "d")[1] == "error"
    assert ledger.approved_scopes(db, OWNER) == frozenset()


@pytest.mark.parametrize("breakage", ["scope", "fingerprint", "task_id", "not_open", "not_owed", "unknown_item"])
def test_a_changed_or_closed_item_is_stale_and_nothing_is_written(db, frontier, monkeypatch, breakage):  # noqa: F811
    add, _ = frontier
    record, meta = gated(add)
    monkeypatch.setattr(rt, "all_owed_reviews", lambda db_, owner: [] if breakage == "not_owed" else [debt()])
    item = item_for(record, meta)
    if breakage == "scope":
        item["scope"] = "f" * 64
    elif breakage == "fingerprint":
        item["fp"] = "e" * 64
    elif breakage == "task_id":
        item["task_id"] = "other"
    elif breakage == "not_open":
        item["state"] = "answered"
    items = {} if breakage == "unknown_item" else {item["id"]: item}
    text, status = glue.apply_factory(OWNER)(confirm(item), items, "d1")
    assert status == "stale" and ledger.approved_scopes(db, OWNER) == frozenset()


def test_decline_defer_and_the_delegation_switch_are_written(db, frontier, monkeypatch):  # noqa: F811
    add, _ = frontier
    record, meta = gated(add)
    scope = rt.approval_scope(meta)
    apply = glue.apply_factory(OWNER)
    item = item_for(record, meta)
    assert apply({"op": "decline", "item": item["id"]}, {item["id"]: item}, "d")[1] == "done"
    assert ledger.held_scopes(db, OWNER) == {("odysseus", "g", scope)}
    d1 = {"id": "d" * 12, "kind": "delegation", "state": "open", "name": "advisor approvals", "task_ref": "policy:advisor-approvals",
          "task_id": ib.DELEGATION_TASK_ID, "scope": ib.DELEGATION_SCOPE}
    assert apply({"op": "approve", "item": d1["id"]}, {d1["id"]: d1}, "d")[1] == "error"        # unconfirmed
    assert apply(confirm(d1), {d1["id"]: d1}, "d")[1] == "done"
    assert glue.delegation_active(db, OWNER)
    assert apply({"op": "stop_advisor"}, {}, "d")[1] == "done"
    assert not glue.delegation_active(db, OWNER)


def test_a_forged_delegation_item_cannot_borrow_the_delegation_path(db):  # noqa: F811
    forged = {"id": "d" * 12, "kind": "delegation", "state": "open", "name": "x", "task_ref": "odysseus:ready/g.md",
              "task_id": "g", "scope": "a" * 64}
    assert glue.apply_factory(OWNER)(confirm(forged), {forged["id"]: forged}, "d")[1] == "error"
    assert ledger.listing(db, OWNER) == []


def test_pause_stops_the_active_run_for_that_owner_only(db, frontier):  # noqa: F811
    run_id = rt.activate_run(db, OWNER, ["odysseus"], {})["id"]
    text, status = glue.apply_factory(OWNER)({"op": "pause_run"}, {}, "d")
    assert status == "done" and rt.run_dict(rt._load(db, run_id))["state"] == "paused"
    text, status = glue.apply_factory("someone-else")({"op": "pause_run"}, {}, "d")
    assert text == "Nothing is running."


def test_the_inbox_is_off_with_the_switch_or_without_a_channel(monkeypatch, tmp_path):
    monkeypatch.setenv("ODYSSEUS_OWNER_INBOX", "0")
    assert glue.offer() is None
    monkeypatch.delenv("ODYSSEUS_OWNER_INBOX")
    monkeypatch.setattr(ib, "load_channel", lambda *a, **k: ("no_channel", None))
    assert glue.offer() is None


def test_older_channels_are_silenced_only_while_the_inbox_is_healthy(monkeypatch):
    monkeypatch.setattr(ib, "load_channel", lambda *a, **k: ("ok", {"owner": OWNER, "fingerprint": "f" * 16}))
    monkeypatch.setattr(ib, "healthy", lambda *a, **k: False)
    assert rt._inbox_active() is False                      # configured but not working: Discord and the heartbeat carry on
    monkeypatch.setattr(ib, "healthy", lambda *a, **k: True)
    assert rt._inbox_active() is True
    monkeypatch.setenv("ODYSSEUS_OWNER_INBOX", "0")
    assert rt._inbox_active() is False


def test_alerts_stop_repeating_decisions_and_the_heartbeat_when_the_inbox_owns_them():
    from datetime import datetime, timezone
    from src import owner_alerts as oa
    owed = [{"task_ref": "odysseus:ready/a.md", "task_id": "a", "gate": "owner_approval", "scope_sha256": "a" * 64,
             "execution_id": "e", "opened_at": "2026-11-20T10:00:00"}]
    now = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
    assert any(e["text"].startswith("Needs you") for e in oa.build_events(owed, [], {}, now))
    assert not any(e["text"].startswith("Needs you") for e in oa.build_events(owed, [], {}, now, decisions=False))

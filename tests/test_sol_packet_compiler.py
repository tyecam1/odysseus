"""Sol packet admission must fail closed, stay deterministic and never batch away an independent check."""
import itertools
import json
import random
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import sol_packet_compiler as spc  # noqa: E402

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
LATER = (NOW + timedelta(days=2)).isoformat()


def make(ident="a", **over):
    base = dict(
        decision_id=ident, parent_task="t", role_required="adjudicator", question="Q " + ident,
        decision_type="choice", consequence="medium", packet_class="decision",
        evidence_pointers=("e1", "e2"), acceptance_criteria=("c",), allowed_verdicts=("YES", "NO"),
        deadline=LATER, independence_required=False, candidate_options=("YES", "NO"),
        shared_context_key="ctx", context_manifest_hash="h1", context_tokens=5000,
        unique_tokens=800, output_reserve_tokens=400)
    base.update(over)
    return spc.Item(**base)


POLICY = spc.Policy(
    min_net_reuse_tokens=1000, wrapper_overhead_tokens=300, max_input_tokens=60000, max_output_tokens=8000,
    max_items=6, headroom_tokens=2000, wait_benefit_lower_bound=5.0, urgency_cost_upper_bound=1.0,
    max_wait_seconds=3600.0, evidence_version="test-v1")


def pairs(*ids):
    return [frozenset(p) for p in itertools.combinations(ids, 2)]


def admit(items, policy=POLICY, certs=None, wait=600.0):
    certs = pairs(*[i.decision_id for i in items]) if certs is None else certs
    return spc.admit(items, policy, certs, NOW, wait)


def test_compatible_items_with_everything_established_are_batched():
    verdict = admit([make("a"), make("b")])
    assert verdict.outcome == spc.BATCH and "policy=test-v1" in verdict.detail


@pytest.mark.parametrize("a_over,reason", [
    ({"role_required": "other"}, "role_or_class_mismatch"),
    ({"packet_class": "verification", "allowed_verdicts": spc.VERIFICATION_VERDICTS}, "role_or_class_mismatch"),
    ({"context_manifest_hash": None}, "context_reuse_unestablished"),
    ({"context_manifest_hash": "h2"}, "context_reuse_unestablished"),
    ({"shared_context_key": "other"}, "context_reuse_unestablished"),
    ({"context_tokens": None}, "context_reuse_unestablished"),
    ({"independence_required": True}, "independence_required"),
    ({"fresh_context_required": True}, "independence_required"),
    ({"separate_adjudication_required": True}, "independence_required"),
    ({"depends_on": ("b",)}, "independence_required"),
    ({"exposes_label_of": ("b",)}, "independence_required"),
    ({"independence_required": None}, "independence_unestablished"),
    ({"unique_tokens": None}, "capacity_unestablished_or_exceeded"),
    ({"unique_tokens": 70000}, "capacity_unestablished_or_exceeded"),
    ({"output_reserve_tokens": 9000}, "capacity_unestablished_or_exceeded"),
    ({"urgent": True}, "urgent_or_blocking_item"),
    ({"blocking": True}, "urgent_or_blocking_item"),
    ({"deadline": (NOW + timedelta(seconds=60)).isoformat()}, "wait_not_justified"),
])
def test_each_refusal_reason_is_reported_and_nothing_is_batched(a_over, reason):
    verdict = admit([make("a", **a_over), make("b")])
    assert verdict.outcome == spc.SINGLE and verdict.reason == reason


def test_net_reuse_must_be_positive_and_meet_the_governed_threshold():
    small = [make("a", context_tokens=200), make("b", context_tokens=200)]
    assert admit(small).reason == "context_reuse_insufficient"
    exactly_below = [make("a", context_tokens=1299), make("b", context_tokens=1299)]  # net 999 < 1000
    assert admit(exactly_below).reason == "context_reuse_insufficient"
    at_threshold = [make("a", context_tokens=1300), make("b", context_tokens=1300)]   # net exactly 1000
    assert admit(at_threshold).outcome == spc.BATCH


@pytest.mark.parametrize("field_name", ["min_net_reuse_tokens", "wrapper_overhead_tokens", "max_input_tokens",
                                        "max_output_tokens", "max_items", "headroom_tokens",
                                        "wait_benefit_lower_bound", "urgency_cost_upper_bound", "max_wait_seconds"])
def test_any_unestablished_policy_number_refuses_batching(field_name):
    verdict = admit([make("a"), make("b")], policy=replace(POLICY, **{field_name: None}))
    assert verdict.outcome == spc.SINGLE


def test_unknown_everything_never_admits():
    assert admit([make("a"), make("b")], policy=spc.Policy()).outcome == spc.SINGLE


def test_group_larger_than_max_items_is_refused():
    items = [make(str(i)) for i in range(4)]
    assert admit(items, policy=replace(POLICY, max_items=3)).reason == "capacity_unestablished_or_exceeded"


def test_certificates_must_cover_every_pair_not_just_neighbours():
    items = [make("a"), make("b"), make("c")]
    chain = [frozenset(("a", "b")), frozenset(("b", "c"))]      # a-c missing: no transitive chaining
    assert admit(items, certs=chain).reason == "independence_unestablished"
    assert admit(items, certs=pairs("a", "b", "c")).outcome == spc.BATCH


def test_waiting_must_beat_urgency_cost_and_fit_the_window():
    items = [make("a"), make("b")]
    assert admit(items, wait=7200.0).reason == "wait_not_justified"
    assert admit(items, policy=replace(POLICY, wait_benefit_lower_bound=1.0)).reason == "wait_not_justified"
    assert admit(items, wait=None).reason == "wait_not_justified"


def test_collision_and_gate_items_must_share_one_question_identity():
    one = [make("a", packet_class="collision", question_id="Q1"), make("b", packet_class="collision", question_id="Q1")]
    two = [make("a", packet_class="collision", question_id="Q1"), make("b", packet_class="collision", question_id="Q2")]
    assert admit(one).outcome == spc.BATCH
    assert admit(two).reason == "question_identity_mismatch"


def test_not_decision_ready_items_return_needs_preparation_not_a_blind_single():
    bad = make("a", evidence_pointers=())
    verdict = admit([bad, make("b")])
    assert verdict.outcome == spc.NEEDS_PREPARATION and "missing_evidence_pointers" in verdict.detail
    assert admit([make("a"), make("a")]).reason == "duplicate_decision_id"


@pytest.mark.parametrize("over,problem", [
    ({"question": " "}, "missing_question"),
    ({"packet_class": "bogus"}, "unknown_packet_class"),
    ({"acceptance_criteria": ()}, "missing_acceptance_criteria"),
    ({"allowed_verdicts": ()}, "missing_allowed_verdicts"),
    ({"candidate_options": ()}, "missing_candidate_options"),
    ({"deadline": None}, "deadline_not_explicit"),
    ({"deadline": "2026-11-05T00:00:00"}, "deadline_not_explicit"),
    ({"packet_class": "gate"}, "missing_question_id"),
    ({"packet_class": "verification", "allowed_verdicts": ("PASS", "FAIL")},
     "verification_verdicts_must_be_pass_revise_escalate"),
])
def test_item_validation_reports_precise_problems(over, problem):
    assert problem in spc.validate_item(make("a", **over))


def test_open_judgment_may_omit_options_and_none_deadline_must_be_explicit():
    assert spc.validate_item(make("a", candidate_options=(), open_judgment=True, deadline=spc.NO_DEADLINE)) == []


def test_naive_now_is_rejected():
    with pytest.raises(ValueError):
        spc.admit([make("a"), make("b")], POLICY, pairs("a", "b"), datetime(2026, 11, 3), 60.0)


# ---------- plan ----------

def test_plan_batches_compatible_items_and_sends_the_rest_alone_with_reasons():
    items = [make("a"), make("b"), make("c", role_required="other")]
    groups = spc.plan(items, POLICY, pairs("a", "b", "c"), NOW, 600.0)
    assert [tuple(i.decision_id for i in g.items) for g in groups] == [("a", "b"), ("c",)]
    assert groups[0].decision.outcome == spc.BATCH
    assert groups[1].decision.outcome == spc.SINGLE and groups[1].decision.reason == "no_compatible_pending"


def test_plan_is_deterministic_under_input_order():
    items = [make("d1", deadline=(NOW + timedelta(days=1)).isoformat()), make("d3", deadline=spc.NO_DEADLINE),
             make("d2", deadline=(NOW + timedelta(days=3)).isoformat()), make("d4", role_required="x")]
    certs = pairs(*[i.decision_id for i in items])
    expected = [tuple(i.decision_id for i in g.items) for g in spc.plan(items, POLICY, certs, NOW, 600.0)]
    rng = random.Random(7)
    for _ in range(10):
        shuffled = items[:]
        rng.shuffle(shuffled)
        got = [tuple(i.decision_id for i in g.items) for g in spc.plan(shuffled, POLICY, certs, NOW, 600.0)]
        assert got == expected


def test_no_deadline_sorts_after_dated_items():
    items = [make("late", deadline=spc.NO_DEADLINE), make("soon", deadline=(NOW + timedelta(days=1)).isoformat())]
    groups = spc.plan(items, replace(POLICY, wait_benefit_lower_bound=0.0), pairs("late", "soon"), NOW, 60.0)
    assert [g.items[0].decision_id for g in groups] == ["soon", "late"]


def test_plan_isolates_not_ready_items_and_oversized_singletons():
    items = [make("ok"), make("bad", evidence_pointers=()), make("huge", unique_tokens=999999)]
    groups = {g.items[0].decision_id: g.decision for g in spc.plan(items, POLICY, pairs("ok", "huge"), NOW, 600.0)}
    assert groups["bad"].outcome == spc.NEEDS_PREPARATION
    assert groups["huge"].outcome == spc.NEEDS_PREPARATION and groups["huge"].reason == "singleton_exceeds_capacity"
    assert groups["ok"].outcome == spc.SINGLE


def test_plan_never_chains_a_batch_through_a_missing_certificate():
    items = [make("a"), make("b"), make("c")]
    groups = spc.plan(items, POLICY, [frozenset(("a", "b")), frozenset(("b", "c"))], NOW, 600.0)
    sizes = sorted(len(g.items) for g in groups)
    assert sizes == [1, 2] and all(len(g.items) < 3 for g in groups)


def test_mandatory_independent_checks_are_never_in_a_batch_whatever_the_mix():
    rng = random.Random(11)
    flags = ["independence_required", "fresh_context_required", "separate_adjudication_required"]
    for trial in range(60):
        items = []
        for n in range(rng.randint(2, 6)):
            over = {}
            if rng.random() < 0.4:
                over[rng.choice(flags)] = True
            items.append(make("i%d" % n, **over))
        certs = pairs(*[i.decision_id for i in items])
        for group in spc.plan(items, POLICY, certs, NOW, 600.0):
            if len(group.items) > 1:
                assert not any(i.independence_required or i.fresh_context_required
                               or i.separate_adjudication_required for i in group.items), trial


# ---------- compile and parse ----------

def test_compiled_packet_states_shared_context_once_and_every_item():
    items = [make("a"), make("b")]
    text = spc.compile_packet(items, "pk1", "SHARED-CONTEXT-BODY", ["be brief"])
    assert text.count("SHARED-CONTEXT-BODY") == 1 and "id=a" in text and "id=b" in text
    assert text == spc.compile_packet(items, "pk1", "SHARED-CONTEXT-BODY", ["be brief"])  # deterministic
    with pytest.raises(ValueError):
        spc.compile_packet([], "pk", "x", [])


def good(ident, verdict="YES", **over):
    entry = {"decision_id": ident, "verdict": verdict, "rationale": "because", "evidence_refs": ["e1"],
             "uncertainty": "low", "another_strong_call_could_change": False}
    entry.update(over)
    return entry


def test_parse_results_attributes_each_item_and_isolates_failures():
    items = [make("a"), make("b"), make("c"), make("d")]
    raw = json.dumps({"results": [good("a"), good("b", verdict="MAYBE"), good("c", rationale=" "),
                                  good("zzz"), good("a")]})
    out = spc.parse_results(items, raw)
    assert out["a"] == "duplicate_result"          # a repeated id is not trusted either time it conflicts
    assert out["b"] == "malformed_result" and out["c"] == "malformed_result"
    assert out["d"] == "missing_result" and "zzz" not in out


def test_parse_results_good_path_and_total_failure():
    items = [make("a"), make("b")]
    out = spc.parse_results(items, json.dumps({"results": [good("a"), good("b", verdict="NO")]}))
    assert isinstance(out["a"], spc.ItemResult) and out["b"].verdict == "NO"
    for raw in ("not json", "{}", json.dumps({"results": "x"}), json.dumps([1])):
        assert set(spc.parse_results(items, raw).values()) == {"unparsable_packet_output"}


def test_parse_results_survives_hostile_entries():
    items = [make("a")]
    raw = json.dumps({"results": [None, 5, "x", {"decision_id": ["a"]}, {"decision_id": {"k": 1}}, good("a")]})
    assert isinstance(spc.parse_results(items, raw)["a"], spc.ItemResult)


# ---------- follow-up suppression ----------

def test_unchanged_question_reuses_its_conclusion_unless_a_trigger_fired():
    item = make("a")
    prior = spc.manifest_hash(item)
    assert spc.needs_new_call(item, prior).outcome == spc.REUSE
    assert spc.needs_new_call(item, prior, ["new_evidence"]).reason == "follow_up_trigger"
    assert spc.needs_new_call(item, prior, ["wording_polish"]).outcome == spc.REUSE   # not a declared trigger
    changed = make("a", evidence_pointers=("e1", "e2", "e3"))
    assert spc.needs_new_call(changed, prior).reason == "no_prior_or_changed_question"
    assert spc.needs_new_call(item, None).outcome == spc.SINGLE


def test_a_required_independent_check_is_never_suppressed():
    item = make("a", independence_required=True)
    assert spc.needs_new_call(item, spc.manifest_hash(item)).reason == "independent_check_still_required"
    fresh = make("a", fresh_context_required=True)
    assert spc.needs_new_call(fresh, spc.manifest_hash(fresh)).outcome == spc.SINGLE

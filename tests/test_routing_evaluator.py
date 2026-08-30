"""Tests for src/routing_evaluator.py — the canonical replay/shadow
routing evaluator (Workstream D).

Uses plain namespace objects shaped like RoutingDecision rows rather than
a live DB, so these tests exercise the aggregation math directly and
don't depend on what's actually accumulated in the real database.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.routing_evaluator import (
    EVIDENCE_THRESHOLD,
    RECENCY_HALF_LIFE_DAYS,
    aggregate_routing_decisions,
    canonical_task_class,
    compute_delegation_metrics,
)


def _decision(**overrides):
    base = dict(
        task_class="code", model_alias="local-fast", concrete_model="qwen3:8b",
        executor="local", deterministic_gate="pass", verification_outcome=None,
        escalated=False, retries=0, latency_ms=500, context_tokens=1000,
        paid_tokens=None, created_at=datetime.utcnow(),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_groups_by_task_class_alias_model_and_executor():
    decisions = [
        _decision(task_class="code", model_alias="local-fast"),
        _decision(task_class="code", model_alias="local-fast"),
        _decision(task_class="chat", model_alias="local-fast"),
        _decision(task_class="code", model_alias="local-fast", executor="codex", concrete_model="codex-cli"),
    ]
    aggs = aggregate_routing_decisions(decisions)
    keys = {(a.task_class, a.model_alias, a.executor) for a in aggs}
    assert keys == {("chat", "local-fast", "local"), ("code", "local-fast", "local"),
                     ("code", "local-fast", "codex")}
    code_local = next(a for a in aggs if a.task_class == "code" and a.executor == "local")
    assert code_local.n == 2


class TestCanonicalTaskClass:
    """docs/aoteru-final-convergence-activation.agent-task.md item 7:
    routing-evidence hygiene. Only unambiguous synonym pairs are mapped
    (never the one-off smoke/proof-of-concept labels — merging those
    would be exactly the arbitrary grouping the task explicitly
    forbids)."""

    def test_known_synonyms_map_to_canonical_name(self):
        assert canonical_task_class("strict_json_schema_output") == "strict_schema_output"
        assert canonical_task_class("ros_log_test_interpretation") == "log_interpretation"

    def test_unknown_task_class_passes_through_unchanged(self):
        assert canonical_task_class("code") == "code"
        assert canonical_task_class("lm1-a1-live-smoke") == "lm1-a1-live-smoke"
        assert canonical_task_class("p12_controller_proof") == "p12_controller_proof"


def test_aggregate_merges_known_synonym_task_classes():
    """The evaluator-side normalization item 7 asks for: two raw labels
    that are the same benchmark concept must fold into one aggregate
    (growing toward EVIDENCE_THRESHOLD together), while the exact raw
    labels that contributed stay visible via raw_task_classes — never
    hidden, never rewriting the underlying RoutingDecision rows."""
    decisions = [
        _decision(task_class="strict_json_schema_output", model_alias="code-strong", executor="codex"),
        _decision(task_class="strict_schema_output", model_alias="code-strong", executor="codex"),
    ]
    aggs = aggregate_routing_decisions(decisions)
    assert len(aggs) == 1
    agg = aggs[0]
    assert agg.task_class == "strict_schema_output"
    assert agg.n == 2
    assert agg.raw_task_classes == {"strict_json_schema_output", "strict_schema_output"}


def test_aggregate_does_not_merge_unrelated_one_off_labels():
    decisions = [
        _decision(task_class="lm1-a1-live-smoke", model_alias="local-fast"),
        _decision(task_class="systemd-cutover-smoke", model_alias="local-fast"),
    ]
    aggs = aggregate_routing_decisions(decisions)
    assert len(aggs) == 2
    assert {a.task_class for a in aggs} == {"lm1-a1-live-smoke", "systemd-cutover-smoke"}


def test_success_rate_counts_only_deterministic_gate_pass():
    decisions = [_decision(deterministic_gate="pass") for _ in range(3)] + \
                [_decision(deterministic_gate="fail") for _ in range(1)]
    agg = aggregate_routing_decisions(decisions)[0]
    assert agg.n == 4
    assert agg.success_rate == pytest.approx(0.75, abs=0.01)


def test_verification_rate_only_counts_attempted_verifications():
    decisions = [
        _decision(verification_outcome="pass"),
        _decision(verification_outcome="fail"),
        _decision(verification_outcome=None),  # not attempted — must not count as a failure
    ]
    agg = aggregate_routing_decisions(decisions)[0]
    assert agg.verification_rate == pytest.approx(0.5, abs=0.01)


def test_escalation_and_retry_rates():
    decisions = [
        _decision(escalated=True, retries=2),
        _decision(escalated=False, retries=0),
        _decision(escalated=False, retries=1),
        _decision(escalated=False, retries=0),
    ]
    agg = aggregate_routing_decisions(decisions)[0]
    assert agg.escalation_rate == pytest.approx(0.25, abs=0.01)
    assert agg.retry_rate == pytest.approx(3 / 4, abs=0.01)


def test_latency_percentiles():
    decisions = [_decision(latency_ms=ms) for ms in [100, 200, 300, 400, 500]]
    agg = aggregate_routing_decisions(decisions)[0]
    assert agg.latency_p50_ms == 300
    assert agg.latency_p95_ms == 500


def test_paid_tokens_summed():
    decisions = [
        _decision(executor="codex", concrete_model="codex-cli", paid_tokens=1000),
        _decision(executor="codex", concrete_model="codex-cli", paid_tokens=500),
    ]
    agg = aggregate_routing_decisions(decisions)[0]
    assert agg.paid_tokens_total == 1500


def test_evidence_insufficient_below_threshold():
    decisions = [_decision() for _ in range(EVIDENCE_THRESHOLD - 1)]
    agg = aggregate_routing_decisions(decisions)[0]
    assert agg.evidence_sufficient is False

    decisions_ok = [_decision() for _ in range(EVIDENCE_THRESHOLD)]
    agg_ok = aggregate_routing_decisions(decisions_ok)[0]
    assert agg_ok.evidence_sufficient is True


def test_recency_weighting_down_weights_old_decisions_without_dropping_them():
    """A stale decision must still count (never silently discarded — that
    would be a second, hidden way to change what counts as evidence) but
    contribute less than a fresh one to the success rate."""
    now = datetime.utcnow()
    old_but_failed = _decision(deterministic_gate="fail", created_at=now - timedelta(days=RECENCY_HALF_LIFE_DAYS))
    fresh_and_passed = _decision(deterministic_gate="pass", created_at=now)

    agg = aggregate_routing_decisions([old_but_failed, fresh_and_passed], now=now)[0]
    assert agg.n == 2, "both decisions must still be counted, not dropped for being old"
    # The fresh pass has weight 1.0; the old fail has weight 0.5 (one
    # half-life). Success rate = 1.0 / 1.5, comfortably above 0.5 even
    # though half the raw decisions failed — recency weighting is doing
    # something, not a no-op.
    assert agg.success_rate > 0.5


def test_missing_timestamp_gets_full_weight_not_dropped():
    decisions = [_decision(created_at=None, deterministic_gate="pass")]
    agg = aggregate_routing_decisions(decisions)[0]
    assert agg.n == 1
    assert agg.success_rate == 1.0


def test_to_dict_is_json_shaped_and_reports_evidence_flag():
    decisions = [_decision() for _ in range(3)]
    agg = aggregate_routing_decisions(decisions)[0]
    d = agg.to_dict()
    assert d["n"] == 3
    assert d["evidence_sufficient"] is False
    assert set(d) >= {
        "task_class", "model_alias", "concrete_model", "executor", "n",
        "evidence_sufficient", "success_rate", "verification_rate",
        "escalation_rate", "retry_rate", "latency_p50_ms", "latency_p95_ms",
        "avg_context_tokens", "paid_tokens_total", "first_seen", "last_seen",
    }


def test_empty_input_returns_empty_list():
    assert aggregate_routing_decisions([]) == []


def test_delegation_metrics_cover_dispatch_retention_verification_and_escalation():
    decisions = [
        _decision(
            recommended_route="codex_eligible", actual_route="codex-write",
            executor="codex-write", verification_outcome="pass", escalated=True,
            escalation_reason="insufficient_capability", nondelegation_reason=None,
        ),
        _decision(
            recommended_route="remote_compute_eligible", actual_route="local",
            executor="local", verification_outcome="pass", nondelegation_reason=None,
        ),
        _decision(
            recommended_route="controller_retained", actual_route="controller",
            executor="controller", verification_outcome=None,
            nondelegation_reason="architecture_judgement",
        ),
        _decision(
            recommended_route="remote_compute_eligible", actual_route="controller",
            executor="controller", verification_outcome="fail",
            nondelegation_reason=None,
        ),
    ]

    metrics = compute_delegation_metrics(decisions)

    assert metrics == {
        "delegation_eligible_units": 3,
        "units_dispatched": 2,
        "units_retained_by_controller": 2,
        "avoidable_controller_execution_rate": pytest.approx(1 / 3),
        "codex_eligible_units": 1,
        "codex_dispatched_units": 1,
        "remote_compute_eligible_units": 2,
        "remote_compute_dispatched_units": 1,
        "verification_success_rate": pytest.approx(2 / 3),
        "reroute_or_escalation_rate": pytest.approx(1 / 4),
    }

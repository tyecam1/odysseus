"""Offline tests for the finance goal-lock evaluator (src/finance_goals.py)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src import finance_goals as fg


NOW = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)


def _registry(goals):
    return {
        "program_id": "test-program",
        "version": "0.1",
        "owner_repository": "tyecam1/misumi",
        "goals": goals,
    }


MT = _registry([
    {"id": "MT-00", "title": "probe", "depends_on": []},
    {"id": "MT-01", "title": "collect", "depends_on": ["MT-00"]},
    {"id": "MT-04", "title": "cross", "depends_on": ["MT-03", "FT-02"]},
    {"id": "MT-03", "title": "shadow", "depends_on": ["MT-02"]},
    {"id": "MT-02", "title": "signals", "depends_on": ["MT-01"]},
])
FT = _registry([
    {"id": "FT-00", "title": "env", "depends_on": []},
    {"id": "FT-02", "title": "protocol", "depends_on": ["FT-01"]},
    {"id": "FT-01", "title": "data", "depends_on": ["FT-00"]},
])


def _receipt(goal_id, kind, *, status="pass", days_ago=0, run_id="r1",
             verifier="codex gpt-6.1-sol", verifies=None, artifacts=None,
             name="receipt.json"):
    rec = {
        "_file": name,
        "goal_id": goal_id,
        "kind": kind,
        "status": status,
        "observed_at": (NOW - timedelta(days=days_ago)).isoformat(),
        "run_id": run_id,
        "verifier": verifier,
        "notes": "test",
    }
    if kind == fg.KIND_INDEPENDENT_VERIFICATION:
        rec["verifies"] = verifies if verifies is not None else run_id
    if artifacts is not None:
        rec["artifacts"] = artifacts
    return rec


def _evaluate(receipts, registries=None, policy=None):
    return fg.evaluate_goals(
        registries=registries or [MT, FT],
        receipts=receipts,
        policy=policy or fg.load_policy(),
        now=NOW,
    )


def _goal(result, goal_id):
    return next(g for g in result["goals"] if g["id"] == goal_id)


def test_locked_by_default_without_any_receipts():
    result = _evaluate([])
    assert result["ok"] is True
    for goal in result["goals"]:
        assert goal["satisfied"] is False
        assert goal["eligible"] is False
        assert goal["blockers"]


def test_root_goal_eligible_with_attestation_only():
    receipts = [
        _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION, days_ago=1),
        _receipt("FT-00", fg.KIND_OPERATOR_ATTESTATION, days_ago=1),
    ]
    result = _evaluate(receipts)
    assert _goal(result, "MT-00")["eligible"] is True
    assert _goal(result, "MT-00")["satisfied"] is False
    assert _goal(result, "FT-00")["eligible"] is True
    assert _goal(result, "MT-01")["eligible"] is False


def test_satisfied_needs_run_and_independent_verification():
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9", days_ago=1)
    # verification naming a different run does not satisfy
    wrong_verifies = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, run_id="v1",
        verifies="run-other",
    )
    result = _evaluate([attestation, run, wrong_verifies])
    assert _goal(result, "MT-00")["satisfied"] is False

    good_verifies = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, run_id="v2",
        verifies="run-9",
    )
    result = _evaluate([attestation, run, wrong_verifies, good_verifies])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is True
    assert mt00["eligible"] is True
    assert _goal(result, "MT-01")["eligible"] is True


def test_glm_verification_is_corroborating_not_independent():
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9")
    glm = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, run_id="v1",
        verifies="run-9", verifier="glm-5.3",
    )
    result = _evaluate([attestation, run, glm])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("corroborating" in b for b in mt00["blockers"])


def test_stale_run_receipt_relocks_dependents():
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9", days_ago=30)
    verifies = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, run_id="v1",
        verifies="run-9", days_ago=29,
    )
    result = _evaluate([attestation, run, verifies])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("stale" in b for b in mt00["blockers"])
    assert _goal(result, "MT-01")["eligible"] is False


def test_artifact_hash_mismatch_relocks(tmp_path: Path):
    artifact = tmp_path / "config.json"
    artifact.write_text('{"dry_run": true}', encoding="utf-8")
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt(
        "MT-00", fg.KIND_RUN, run_id="run-9",
        artifacts=[{"label": "cfg", "path": str(artifact),
                    "sha256": fg.sha256_file(artifact)}],
    )
    verifies = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, verifies="run-9",
    )
    result = fg.evaluate_goals(
        registries=[MT, FT], receipts=[attestation, run, verifies],
        policy=fg.load_policy(), now=NOW, repo_root=tmp_path,
    )
    assert _goal(result, "MT-00")["satisfied"] is True

    artifact.write_text('{"dry_run": true, "tampered": 1}', encoding="utf-8")
    result = fg.evaluate_goals(
        registries=[MT, FT], receipts=[attestation, run, verifies],
        policy=fg.load_policy(), now=NOW, repo_root=tmp_path,
    )
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("hash mismatch" in b for b in mt00["blockers"])


def test_missing_artifact_file_relocks(tmp_path: Path):
    gone = tmp_path / "gone.json"
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt(
        "MT-00", fg.KIND_RUN, run_id="run-9",
        artifacts=[{"label": "cfg", "path": str(gone), "sha256": "0" * 64}],
    )
    verifies = _receipt("MT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                        verifies="run-9")
    result = fg.evaluate_goals(
        registries=[MT, FT], receipts=[attestation, run, verifies],
        policy=fg.load_policy(), now=NOW, repo_root=tmp_path,
    )
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("artifact missing" in b for b in mt00["blockers"])


def test_cross_program_dependency_mt04_needs_ft02():
    def full(goal_id, run_id):
        return [
            _receipt(goal_id, fg.KIND_OPERATOR_ATTESTATION),
            _receipt(goal_id, fg.KIND_RUN, run_id=run_id),
            _receipt(goal_id, fg.KIND_INDEPENDENT_VERIFICATION,
                     verifies=run_id),
        ]

    receipts = []
    for goal_id in ("MT-00", "MT-01", "MT-02", "MT-03", "FT-00", "FT-01"):
        receipts += full(goal_id, f"run-{goal_id}")
    result = _evaluate(receipts)
    # MT-03 satisfied but FT-02 not: MT-04 must stay locked
    mt04 = _goal(result, "MT-04")
    assert mt04["satisfied"] is False
    assert mt04["eligible"] is False
    assert any("FT-02" in b for b in mt04["blockers"])


def test_fail_status_receipt_does_not_satisfy():
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, status="fail")
    verifies = _receipt("MT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                        verifies="r1")
    result = _evaluate([attestation, run, verifies])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("status='fail'" in b for b in mt00["blockers"])


def test_malformed_receipt_is_blocker_not_crash():
    receipts = [{"_file": "bad.json", "_invalid": "missing fields: ['goal_id']"}]
    result = _evaluate(receipts)
    assert result["ok"] is True
    assert all(g["eligible"] is False for g in result["goals"])


def test_unknown_dependency_id_blocks():
    broken = _registry([
        {"id": "X-01", "title": "x", "depends_on": ["NOPE-00"]},
    ])
    result = _evaluate([], registries=[broken])
    x01 = _goal(result, "X-01")
    assert x01["eligible"] is False
    assert any("unknown" in b for b in x01["blockers"])


def test_repo_prefixed_artifacts_resolve_against_repo_root(tmp_path: Path):
    rel = tmp_path / "src" / "probe.py"
    rel.parent.mkdir(parents=True)
    rel.write_text("print('x')\n", encoding="utf-8")
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt(
        "MT-00", fg.KIND_RUN, run_id="run-9",
        artifacts=[{"label": "code", "path": "repo:src/probe.py",
                    "sha256": fg.sha256_file(rel)}],
    )
    verifies = _receipt("MT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                        verifies="run-9")
    result = fg.evaluate_goals(
        registries=[MT, FT], receipts=[attestation, run, verifies],
        policy=fg.load_policy(), now=NOW, repo_root=tmp_path,
    )
    assert _goal(result, "MT-00")["satisfied"] is True


def test_goal_ttl_override_in_policy():
    attestation = _receipt("FT-04", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("FT-04", fg.KIND_RUN, run_id="run-4", days_ago=10)
    verifies = _receipt("FT-04", fg.KIND_INDEPENDENT_VERIFICATION,
                        verifies="run-4", days_ago=9)
    ft_long = _registry([
        {"id": "FT-04", "title": "forward", "depends_on": []},
    ])
    policy = fg.load_policy()
    policy["goal_ttl_overrides"] = {
        "FT-04": {fg.KIND_RUN: 40, fg.KIND_INDEPENDENT_VERIFICATION: 40},
    }
    result = fg.evaluate_goals(
        registries=[ft_long], receipts=[attestation, run, verifies],
        policy=policy, now=NOW,
    )
    assert _goal(result, "FT-04")["satisfied"] is True

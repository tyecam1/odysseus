"""Offline tests for the finance goal-lock evaluator (src/finance_goals.py)."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src import finance_goals as fg


NOW = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)

# Verification receipts must carry their own hash-checked artifacts; this
# default points at a real repo file so the hash check passes under the
# default repo_root (tests with an explicit tmp repo_root override it).
POLICY_ARTIFACT = [
    {
        "label": "policy",
        "path": "repo:config/finance-goals/runtime-evaluation.json",
        "sha256": fg.sha256_file(fg.DEFAULT_POLICY_PATH),
    }
]


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
             verifier="codex", verifies=None, artifacts=None,
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
    if kind in (fg.KIND_RUN, fg.KIND_INDEPENDENT_VERIFICATION):
        # both run and verification receipts must carry hash-checked
        # artifacts; the shared default overlaps so the verification
        # cites the run's evidence
        rec["artifacts"] = (
            artifacts if artifacts is not None
            else copy.deepcopy(POLICY_ARTIFACT)
        )
    if kind == fg.KIND_INDEPENDENT_VERIFICATION:
        rec["verifies"] = verifies if verifies is not None else run_id
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
    # verification cites the SAME artifact hash: it must overlap the
    # run's evidence to bind the verification to that exact run
    run_artifacts = [{"label": "cfg", "path": str(artifact),
                      "sha256": fg.sha256_file(artifact)}]
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9",
                   artifacts=run_artifacts)
    verifies = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, verifies="run-9",
        artifacts=run_artifacts,
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
    result = _evaluate([attestation, run, verifies])
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
    verifies = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, verifies="run-9",
        artifacts=[{"label": "code", "path": "repo:src/probe.py",
                    "sha256": fg.sha256_file(rel)}],
    )
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


def test_verifier_identity_is_exact_not_substring():
    # "glm-codex" contains "codex" — a substring match would let a
    # corroborating GLM lane discharge an independent gate
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9")
    lookalike = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, run_id="v1",
        verifies="run-9", verifier="glm-codex",
    )
    result = _evaluate([attestation, run, lookalike])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("corroborating" in b for b in mt00["blockers"])


def test_failed_verification_does_not_satisfy():
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9")
    failed = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, run_id="v1",
        verifies="run-9", status="fail",
    )
    result = _evaluate([attestation, run, failed])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("status='fail'" in b for b in mt00["blockers"])


def test_run_receipt_without_run_id_cannot_satisfy():
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="")
    verifies = _receipt("MT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                        verifies="")
    result = _evaluate([attestation, run, verifies])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("no run_id" in b for b in mt00["blockers"])


def test_verification_without_verifies_cannot_satisfy():
    # missing run_id on BOTH sides must not compare equal (None == None)
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9")
    bare = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, run_id="v1", verifies="",
    )
    result = _evaluate([attestation, run, bare])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("names no run id" in b for b in mt00["blockers"])


def test_verification_without_artifacts_cannot_satisfy(tmp_path: Path):
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9")
    bare = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, verifies="run-9",
        artifacts=[],
    )
    result = _evaluate([attestation, run, bare])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("records no artifacts" in b for b in mt00["blockers"])


def test_verification_artifacts_are_hash_checked(tmp_path: Path):
    run_art = tmp_path / "run-evidence.json"
    run_art.write_text('{"run": 1}', encoding="utf-8")
    vnote = tmp_path / "verification-note.txt"
    vnote.write_text("reviewed\n", encoding="utf-8")
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt(
        "MT-00", fg.KIND_RUN, run_id="run-9",
        artifacts=[{"label": "evidence", "path": str(run_art),
                    "sha256": fg.sha256_file(run_art)}],
    )
    # verification cites BOTH the run's evidence (overlap) and its own
    # note; tampering the note alone must relock
    verifies = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, verifies="run-9",
        artifacts=[
            {"label": "evidence", "path": str(run_art),
             "sha256": fg.sha256_file(run_art)},
            {"label": "note", "path": str(vnote),
             "sha256": fg.sha256_file(vnote)},
        ],
    )
    result = fg.evaluate_goals(
        registries=[MT, FT], receipts=[attestation, run, verifies],
        policy=fg.load_policy(), now=NOW, repo_root=tmp_path,
    )
    assert _goal(result, "MT-00")["satisfied"] is True

    vnote.write_text("tampered\n", encoding="utf-8")
    result = fg.evaluate_goals(
        registries=[MT, FT], receipts=[attestation, run, verifies],
        policy=fg.load_policy(), now=NOW, repo_root=tmp_path,
    )
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("hash mismatch" in b for b in mt00["blockers"])


def test_own_evidence_cannot_satisfy_goal_with_locked_deps():
    # MT-04 carries a full satisfied-quality evidence chain of its own,
    # but MT-03/FT-02 have no receipts at all: it must stay locked.
    receipts = [
        _receipt("MT-04", fg.KIND_RUN, run_id="run-mt04"),
        _receipt("MT-04", fg.KIND_INDEPENDENT_VERIFICATION,
                 verifies="run-mt04"),
    ]
    result = _evaluate(receipts)
    mt04 = _goal(result, "MT-04")
    assert mt04["satisfied"] is False
    assert mt04["eligible"] is False
    assert any("dependency MT-03 not satisfied" in b for b in mt04["blockers"])
    assert any("dependency FT-02 not satisfied" in b for b in mt04["blockers"])
    # and its OWN evidence raised no blocker — the lock is purely the deps
    assert not any(b.startswith("MT-04: ") for b in mt04["blockers"])


def test_superseded_receipts_do_not_poison_fresh_evidence(tmp_path: Path):
    # the real re-verification flow: code changes -> old run receipt's
    # artifact hashes mismatch -> fresh run + fresh verification naming
    # the NEW run id must re-satisfy; the stale receipts are notes only
    code = tmp_path / "probe.py"
    code.write_text("v1\n", encoding="utf-8")
    old_hash = fg.sha256_file(code)

    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION,
                           name="att.json")
    old_run = _receipt(
        "MT-00", fg.KIND_RUN, run_id="run-old", days_ago=1,
        artifacts=[{"label": "code", "path": str(code),
                    "sha256": old_hash}], name="run-old.json",
    )
    old_verifies = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, verifies="run-old",
        days_ago=1,
        artifacts=[{"label": "code", "path": str(code),
                    "sha256": old_hash}], name="verify-old.json",
    )
    # code changes on disk: both old receipts now mismatch
    code.write_text("v2 fixed\n", encoding="utf-8")
    new_hash = fg.sha256_file(code)

    new_run = _receipt(
        "MT-00", fg.KIND_RUN, run_id="run-new",
        artifacts=[{"label": "code", "path": str(code),
                    "sha256": new_hash}], name="run-new.json",
    )
    new_verifies = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, verifies="run-new",
        artifacts=[{"label": "code", "path": str(code),
                    "sha256": new_hash}], name="verify-new.json",
    )
    result = fg.evaluate_goals(
        registries=[MT, FT],
        receipts=[attestation, old_run, old_verifies, new_run, new_verifies],
        policy=fg.load_policy(), now=NOW, repo_root=tmp_path,
    )
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is True
    assert mt00["blockers"] == []

    # but fresh evidence alone, without a verification naming the NEW
    # run, re-locks: the old verification names run-old
    result = fg.evaluate_goals(
        registries=[MT, FT],
        receipts=[attestation, old_run, old_verifies, new_run],
        policy=fg.load_policy(), now=NOW, repo_root=tmp_path,
    )
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("no current independent verification of run 'run-new'" in b
               for b in mt00["blockers"])


def test_run_receipt_without_artifacts_cannot_satisfy():
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9", artifacts=[])
    verifies = _receipt("MT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                        verifies="run-9")
    result = _evaluate([attestation, run, verifies])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("records no artifacts" in b for b in mt00["blockers"])
    assert any("newest run receipt does not validate" in b
               for b in mt00["blockers"])


def test_verification_predating_run_cannot_satisfy():
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9", days_ago=1)
    early = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, run_id="v1",
        verifies="run-9", days_ago=3,  # observed BEFORE the run
    )
    result = _evaluate([attestation, run, early])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("predates run" in b for b in mt00["blockers"])


def test_future_dated_receipt_cannot_satisfy():
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9", days_ago=-30)
    verifies = _receipt("MT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                        verifies="run-9", days_ago=-30)
    result = _evaluate([attestation, run, verifies])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("future-dated" in b for b in mt00["blockers"])


def test_newest_invalid_run_locks_despite_older_valid_chain(tmp_path: Path):
    # old chain cites a file that never changes (still valid); a NEWER
    # run cites the code file, which then changes: the newest run
    # invalidates and the goal MUST lock — no fallback to the old chain
    stable = tmp_path / "stable-evidence.json"
    stable.write_text('{"stable": true}', encoding="utf-8")
    code = tmp_path / "probe.py"

    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    old_run = _receipt(
        "MT-00", fg.KIND_RUN, run_id="run-old", days_ago=2,
        artifacts=[{"label": "stable", "path": str(stable),
                    "sha256": fg.sha256_file(stable)}], name="run-old.json",
    )
    old_verifies = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, verifies="run-old",
        days_ago=2,
        artifacts=[{"label": "stable", "path": str(stable),
                    "sha256": fg.sha256_file(stable)}],
        name="verify-old.json",
    )
    code.write_text("v1\n", encoding="utf-8")
    new_run = _receipt(
        "MT-00", fg.KIND_RUN, run_id="run-new", days_ago=0,
        artifacts=[{"label": "code", "path": str(code),
                    "sha256": fg.sha256_file(code)}], name="run-new.json",
    )
    receipts = [attestation, old_run, old_verifies, new_run]

    result = fg.evaluate_goals(
        registries=[MT, FT], receipts=receipts,
        policy=fg.load_policy(), now=NOW, repo_root=tmp_path,
    )
    # newest run valid but unverified: locked (old chain superseded)
    assert _goal(result, "MT-00")["satisfied"] is False

    code.write_text("v2 changed\n", encoding="utf-8")
    result = fg.evaluate_goals(
        registries=[MT, FT], receipts=receipts,
        policy=fg.load_policy(), now=NOW, repo_root=tmp_path,
    )
    mt00 = _goal(result, "MT-00")
    # newest run now INVALID: still locked, no fallback to the old chain
    assert mt00["satisfied"] is False
    assert any("newest run receipt does not validate" in b
               for b in mt00["blockers"])
    assert any("run-new.json" in b and "hash mismatch" in b
               for b in mt00["blockers"])

"""Offline tests for the finance goal-lock evaluator (src/finance_goals.py)."""
from __future__ import annotations

import copy
import json
import tempfile
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
    assert any("no usable run_id" in b for b in mt00["blockers"])


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
    assert any("names no usable run id" in b for b in mt00["blockers"])


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


def test_unattributable_receipt_locks_every_goal():
    # a receipt that cannot even be attributed to a goal (missing
    # goal_id) poisons the whole ledger: every goal locks until it is
    # repaired — a healthy goal's own evidence chain cannot override it
    attestation = _receipt("FT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("FT-00", fg.KIND_RUN, run_id="run-9")
    verifies = _receipt("FT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                        verifies="run-9")
    poison = {"_file": "poison.json",
              "_invalid": "missing fields: ['goal_id']"}
    result = _evaluate([attestation, run, verifies, poison])
    ft00 = _goal(result, "FT-00")
    assert ft00["satisfied"] is False
    assert ft00["eligible"] is False
    assert any("unattributable" in b for b in ft00["blockers"])
    assert result["ledger_unattributable"]
    # isolation: the SAME chain without the poison satisfies
    result = _evaluate([attestation, run, verifies])
    assert _goal(result, "FT-00")["satisfied"] is True


def test_goal_attributed_unknown_kind_receipt_locks_that_goal():
    # attributed to MT-00 but of an unknown kind: it locks MT-00's
    # satisfaction while leaving other goals' derivations untouched
    weird = {"_file": "weird.json", "goal_id": "MT-00", "kind": "banana",
             "status": "pass", "observed_at": NOW.isoformat()}
    mt_att = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    ft_att = _receipt("FT-00", fg.KIND_OPERATOR_ATTESTATION)
    result = _evaluate([mt_att, ft_att, weird])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("malformed receipt(s)" in b and "weird.json" in b
               for b in mt00["blockers"])
    ft00 = _goal(result, "FT-00")
    assert not any("malformed" in b for b in ft00["blockers"])
    assert result["ledger_unattributable"] == []


def test_goal_attributed_invalid_status_receipt_locks_that_goal(tmp_path: Path):
    # a goal-attributed receipt with an impossible status, as it arrives
    # from the receipts DIRECTORY (load_receipts flags it _invalid): it
    # can never be classified into the newest-governs ordering, so it
    # locks the goal from the malformed bucket instead of leaving an
    # older valid chain silently satisfied (Sol round-3 finding 1)
    (tmp_path / "bad-status.json").write_text(json.dumps({
        "goal_id": "MT-00", "kind": "run", "status": "banana",
        "observed_at": NOW.isoformat(), "run_id": "r9",
        "artifacts": copy.deepcopy(POLICY_ARTIFACT),
    }), encoding="utf-8")
    loaded = fg.load_receipts(tmp_path)
    assert loaded[0].get("_invalid")
    mt_att = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9")
    verifies = _receipt("MT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                        verifies="run-9")
    result = _evaluate([mt_att, run, verifies] + loaded)
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("malformed receipt(s)" in b and "bad-status.json" in b
               for b in mt00["blockers"])


def test_unparseable_observed_at_treated_as_newest_and_locks(tmp_path: Path):
    # an unparseable observed_at cannot be proven OLDER than the newest
    # receipt, so it must never sort to the back of history: it is
    # treated as newest and locks the goal (no fallback to the old chain)
    stable = tmp_path / "stable-evidence.json"
    stable.write_text('{"stable": true}', encoding="utf-8")
    art = [{"label": "stable", "path": str(stable),
            "sha256": fg.sha256_file(stable)}]
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    old_run = _receipt("MT-00", fg.KIND_RUN, run_id="run-old", days_ago=2,
                       artifacts=copy.deepcopy(art), name="run-old.json")
    old_verify = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, verifies="run-old",
        days_ago=2, artifacts=copy.deepcopy(art), name="verify-old.json",
    )
    unreadable = _receipt("MT-00", fg.KIND_RUN, run_id="run-new",
                          artifacts=copy.deepcopy(art), name="run-new.json")
    unreadable["observed_at"] = "not-a-timestamp"
    result = fg.evaluate_goals(
        registries=[MT, FT],
        receipts=[attestation, old_run, old_verify, unreadable],
        policy=fg.load_policy(), now=NOW, repo_root=tmp_path,
    )
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("unparseable observed_at" in b for b in mt00["blockers"])
    assert any("newest run receipt does not validate" in b
               for b in mt00["blockers"])


def test_verification_hash_without_matching_path_does_not_bind(tmp_path: Path):
    # identical BYTES at two paths (latest.json vs a timestamped
    # snapshot) share a sha256: a verification citing the other file's
    # path must not count as citing the run's evidence
    payload = '{"records": []}\n'
    snapshot = tmp_path / "snapshot-20261029T100000Z.json"
    latest = tmp_path / "latest.json"
    snapshot.write_text(payload, encoding="utf-8")
    latest.write_text(payload, encoding="utf-8")
    digest = fg.sha256_bytes(payload.encode("utf-8"))
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9",
                   artifacts=[{"label": "snapshot", "path": str(snapshot),
                               "sha256": digest}])
    lookalike = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, verifies="run-9",
        artifacts=[{"label": "snapshot", "path": str(latest),
                    "sha256": digest}],
    )
    result = fg.evaluate_goals(
        registries=[MT, FT], receipts=[attestation, run, lookalike],
        policy=fg.load_policy(), now=NOW, repo_root=tmp_path,
    )
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("cites none of run" in b for b in mt00["blockers"])
    # the same verification citing the run's ACTUAL path satisfies
    good = _receipt(
        "MT-00", fg.KIND_INDEPENDENT_VERIFICATION, verifies="run-9",
        artifacts=[{"label": "snapshot", "path": str(snapshot),
                    "sha256": digest}],
    )
    result = fg.evaluate_goals(
        registries=[MT, FT], receipts=[attestation, run, good],
        policy=fg.load_policy(), now=NOW, repo_root=tmp_path,
    )
    assert _goal(result, "MT-00")["satisfied"] is True


def test_future_dated_receipt_recovers_when_clock_catches_up():
    # future-dating is fail-closed but not a permanent lock: the receipt
    # ages into validity once the clock reaches its stamped time
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9", days_ago=-1)
    verifies = _receipt("MT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                        verifies="run-9", days_ago=-1)
    result = _evaluate([attestation, run, verifies])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("future-dated" in b and "recovers" in b
               for b in mt00["blockers"])
    later = fg.evaluate_goals(
        registries=[MT, FT], receipts=[attestation, run, verifies],
        policy=fg.load_policy(), now=NOW + timedelta(days=2),
    )
    mt00 = _goal(later, "MT-00")
    assert mt00["satisfied"] is True
    assert mt00["blockers"] == []


# --- round-5 review findings: classification cannot drop or mis-scope ---


def _satisfying_mt00_receipts(**overrides):
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9", days_ago=1)
    verifies = _receipt("MT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                        run_id="v1", verifies="run-9")
    return [attestation, run, verifies]


def test_spoofed_file_field_cannot_shadow_a_newer_failed_run():
    # A receipt dict carrying its own "_file" must never control its
    # ledger key: a newer status=fail receipt spoofing another file's
    # name could otherwise be overwritten by the valid one and vanish.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        good = _receipt("MT-00", fg.KIND_RUN, run_id="run-9", days_ago=2,
                        name="b-valid.json")
        newer_fail = _receipt("MT-00", fg.KIND_RUN, status="fail",
                              run_id="run-10", days_ago=1,
                              name="a-newer-fail.json")
        # the poisoned file claims the valid receipt's file name
        newer_fail["_file"] = "b-valid.json"
        (tmp_path / "b-valid.json").write_text(
            json.dumps(good), encoding="utf-8")
        (tmp_path / "a-newer-fail.json").write_text(
            json.dumps(newer_fail), encoding="utf-8")
        loaded = fg.load_receipts(tmp_path)
        names = sorted(r["_file"] for r in loaded)
        assert names == ["a-newer-fail.json", "b-valid.json"]
        attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
        verifies = _receipt("MT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                            run_id="v1", verifies="run-9")
        result = fg.evaluate_goals(
            registries=[MT, FT],
            receipts=loaded + [attestation, verifies],
            policy=fg.load_policy(), now=NOW,
        )
        # the newer FAILED run governs: the goal must NOT be satisfied,
        # and the failure must surface under the failed run's REAL file
        # name (a-newer-fail.json), never shadowed by the spoofed one
        mt00 = _goal(result, "MT-00")
        assert mt00["satisfied"] is False
        assert any(
            "a-newer-fail.json" in b and "status='fail'" in b
            for b in mt00["blockers"]
        )
        assert not any(
            "b-valid.json" in b and "status='fail'" in b
            for b in mt00["blockers"]
        )


def test_empty_goal_id_locks_every_goal():
    # "" is NOT an attribution: the receipt lands in the global
    # unattributable bucket, and no goal stays satisfied behind it
    poisoned = _receipt("", fg.KIND_RUN, run_id="run-x", days_ago=0)
    result = _evaluate(_satisfying_mt00_receipts() + [poisoned])
    assert result["ledger_unattributable"], "empty goal_id must surface"
    for goal in result["goals"]:
        assert goal["satisfied"] is False


def test_missing_kind_locks_only_that_goal():
    # a receipt naming MT-00 but carrying no kind is MT-00's problem:
    # FT-00 (independently satisfied) must not be dragged into the lock
    mt_poisoned = {
        "_file": "mt-nokind.json",
        "goal_id": "MT-00",
        "status": "pass",
        "observed_at": NOW.isoformat(),
        "run_id": "run-x",
        "notes": "test",
    }
    ft_receipts = [
        _receipt("FT-00", fg.KIND_OPERATOR_ATTESTATION),
        _receipt("FT-00", fg.KIND_RUN, run_id="ft-run-9", days_ago=1),
        _receipt("FT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                 run_id="v9", verifies="ft-run-9"),
    ]
    result = _evaluate(_satisfying_mt00_receipts() + [mt_poisoned]
                       + ft_receipts)
    assert _goal(result, "MT-00")["satisfied"] is False
    assert any("malformed" in b for b in _goal(result, "MT-00")["blockers"])
    assert _goal(result, "FT-00")["satisfied"] is True


def test_unknown_goal_id_locks_every_goal():
    # naming a goal no registry knows can neither be isolated to that
    # goal nor safely ignored — it locks the whole ledger
    poisoned = _receipt("MT-99", fg.KIND_RUN, run_id="run-x")
    result = _evaluate(_satisfying_mt00_receipts() + [poisoned])
    assert result["ledger_unattributable"]
    assert any("MT-99" in entry for entry in result["ledger_unattributable"])
    for goal in result["goals"]:
        assert goal["satisfied"] is False


# --- round-6 review findings: ill-typed receipts LOCK, never crash ---


def test_ill_typed_goal_id_locks_every_goal():
    # a list/dict goal_id used to raise TypeError and take the whole
    # /goals response down; it must lock like any other unattributable
    # receipt instead
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        poisoned = _receipt("MT-00", fg.KIND_RUN, run_id="run-x",
                            name="illtyped-goal.json")
        poisoned["goal_id"] = ["MT-00"]
        (tmp_path / "illtyped-goal.json").write_text(
            json.dumps(poisoned), encoding="utf-8")
        loaded = fg.load_receipts(tmp_path)
        assert any(r["_file"] == "illtyped-goal.json" for r in loaded)
        result = fg.evaluate_goals(
            registries=[MT, FT],
            receipts=_satisfying_mt00_receipts() + loaded,
            policy=fg.load_policy(), now=NOW,
        )
        assert result["ledger_unattributable"]
        for goal in result["goals"]:
            assert goal["satisfied"] is False


def test_ill_typed_kind_locks_only_that_goal():
    mt_poisoned = _receipt("MT-00", ["run"], run_id="run-x",
                           name="illtyped-kind.json")
    mt_poisoned["kind"] = ["run"]
    ft_receipts = [
        _receipt("FT-00", fg.KIND_OPERATOR_ATTESTATION),
        _receipt("FT-00", fg.KIND_RUN, run_id="ft-run-9", days_ago=1),
        _receipt("FT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                 run_id="v9", verifies="ft-run-9"),
    ]
    result = _evaluate(_satisfying_mt00_receipts() + [mt_poisoned]
                       + ft_receipts)
    assert _goal(result, "MT-00")["satisfied"] is False
    assert any("unusable kind" in b for b in _goal(result, "MT-00")["blockers"])
    assert _goal(result, "FT-00")["satisfied"] is True


def test_ill_typed_status_is_invalid_at_load_and_locks_that_goal():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        poisoned = _receipt("MT-00", fg.KIND_RUN, run_id="run-x",
                            name="illtyped-status.json")
        poisoned["status"] = ["pass"]
        (tmp_path / "illtyped-status.json").write_text(
            json.dumps(poisoned), encoding="utf-8")
        loaded = fg.load_receipts(tmp_path)
        rec = next(r for r in loaded if r["_file"] == "illtyped-status.json")
        assert rec.get("_invalid")
        ft_receipts = [
            _receipt("FT-00", fg.KIND_OPERATOR_ATTESTATION),
            _receipt("FT-00", fg.KIND_RUN, run_id="ft-run-9", days_ago=1),
            _receipt("FT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                     run_id="v9", verifies="ft-run-9"),
        ]
        result = fg.evaluate_goals(
            registries=[MT, FT],
            receipts=_satisfying_mt00_receipts() + [rec] + ft_receipts,
            policy=fg.load_policy(), now=NOW,
        )
        assert _goal(result, "MT-00")["satisfied"] is False
        assert _goal(result, "FT-00")["satisfied"] is True


def test_artifacts_not_objects_is_invalid_at_load():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        poisoned = _receipt("MT-00", fg.KIND_RUN, run_id="run-x",
                            name="illtyped-artifacts.json")
        poisoned["artifacts"] = ["bad"]
        (tmp_path / "illtyped-artifacts.json").write_text(
            json.dumps(poisoned), encoding="utf-8")
        loaded = fg.load_receipts(tmp_path)
        rec = next(r for r in loaded
                   if r["_file"] == "illtyped-artifacts.json")
        assert "artifacts" in (rec.get("_invalid") or "")


# --- round-7: ill-typed identity fields and artifact fields lock, never
# --- crash the response or match by value-equality ---


def test_ill_typed_artifact_path_locks_goal_not_response():
    # a list/object artifact PATH in a NEWEST run must produce a
    # per-goal malformed lock inside an ok:true response — never an
    # AttributeError that loses the whole /goals evaluation
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-9", days_ago=0,
                   name="illtyped-path.json",
                   artifacts=[{
                       "label": "x",
                       "sha256": "a" * 64,
                       "path": ["repo:", "src/x.py"],
                   }])
    result = _evaluate(_satisfying_mt00_receipts()
                      + [run, _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)])
    assert result["ok"] is True
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("malformed artifact entry" in b for b in mt00["blockers"])
    # the ill-typed run is NEWER than the valid one, so it governs
    assert any("illtyped-path.json" in b for b in mt00["blockers"])


def test_object_run_id_cannot_be_a_valid_run_identity():
    # {"a": 1} is truthy: without a string guard it slips past the
    # run_id check, and a value-equal OBJECT "verifies" then matches it
    # ({"a": 1} == {"a": 1} in Python) — an ill-typed pair must never
    # satisfy a goal
    run = _receipt("MT-00", fg.KIND_RUN, run_id={"a": 1}, days_ago=0,
                   name="object-runid.json")
    verifies = _receipt("MT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                        run_id="v1", verifies={"a": 1}, days_ago=0)
    result = _evaluate(_satisfying_mt00_receipts() + [
        run, verifies, _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION),
    ])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("no usable run_id" in b for b in mt00["blockers"])


def test_object_verifies_cannot_match_a_valid_run():
    # even with a perfectly valid newest run, a verification whose
    # "verifies" is an object (value-equal to nothing string-typed) must
    # be rejected as unusable identity, not compared by value equality
    verifies = _receipt("MT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                        run_id="v1", verifies=["run-9"], days_ago=0)
    result = _evaluate(_satisfying_mt00_receipts() + [verifies])
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any(
        "no usable run id" in b for b in mt00["blockers"]
    ) or any(
        "no current independent verification" in b
        for b in mt00["blockers"]
    )


# --- round-8: a directory/unreadable artifact is a per-goal blocker,
# --- never a lost response ---


def test_directory_artifact_locks_goal_not_response(tmp_path):
    # an artifact path naming a DIRECTORY raises IsADirectoryError in
    # the hasher unless guarded: it must lock just that goal inside an
    # ok:true response
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-dir", days_ago=0,
                   name="dir-artifact.json",
                   artifacts=[{
                       "label": "dir",
                       "sha256": "a" * 64,
                       "path": "repo:subdir",
                   }])
    (tmp_path / "subdir").mkdir(exist_ok=True)
    result = fg.evaluate_goals(
        registries=[MT, FT],
        receipts=_satisfying_mt00_receipts() + [
            run, _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION),
        ],
        policy=fg.load_policy(), now=NOW, repo_root=tmp_path,
    )
    assert result["ok"] is True
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("not a regular file" in b for b in mt00["blockers"])
    assert any("dir-artifact.json" in b for b in mt00["blockers"])


def test_extreme_future_receipt_locks_goal_not_response():
    # observed_at = 9999-12-31T23:59:59Z previously raised OverflowError
    # in observed + timedelta(days=ttl) and lost the WHOLE /goals
    # response; now it is a per-receipt future-dating lock
    attestation = _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION)
    run = _receipt("MT-00", fg.KIND_RUN, run_id="run-x")
    run["observed_at"] = "9999-12-31T23:59:59Z"
    verifies = _receipt("MT-00", fg.KIND_INDEPENDENT_VERIFICATION,
                        verifies="run-x")
    verifies["observed_at"] = "9999-12-31T23:59:59Z"
    result = _evaluate([attestation, run, verifies])
    assert result["ok"] is True  # the response itself survives
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("beyond datetime range" in b for b in mt00["blockers"])


def test_unexpected_receipt_exception_locks_never_loses_response(monkeypatch):
    # structural invariant (catch-all wrapper): whatever a FUTURE review
    # round finds, an unexpected failure while evaluating a hostile
    # receipt is itself a per-receipt blocker — the /goals response can
    # never be lost
    def boom(*args, **kwargs):
        raise RuntimeError("unexpected hostile-receipt failure")

    monkeypatch.setattr(fg, "_receipt_blockers_inner", boom)
    receipts = [
        _receipt("MT-00", fg.KIND_OPERATOR_ATTESTATION),
        _receipt("MT-00", fg.KIND_RUN, run_id="run-x"),
    ]
    result = _evaluate(receipts)
    assert result["ok"] is True
    mt00 = _goal(result, "MT-00")
    assert mt00["satisfied"] is False
    assert any("could not be evaluated" in b for b in mt00["blockers"])

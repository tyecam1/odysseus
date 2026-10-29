"""Deterministic finance goal-lock evaluator (MT-xx / FT-xx).

Task cards ``finance-market-media-intelligence-2026-10-29.md`` and
``finance-paper-trading-goals-2026-10-29.md``; canonical goal registries
live in ``tyecam1/misumi@main:config/finance-*-goals.json`` and are
mirrored read-only into ``config/finance-goals/`` for the runtime.

The registries are durable DEFINITIONS, not runtime state. This module
derives current status on every call, fail-closed:

- a goal is **satisfied** only while it has a ``run`` receipt with
  status=pass and a ``run_id``, inside its TTL, whose recorded artifact
  hashes still match the live files, AND a current
  ``independent_verification`` receipt (status=pass, with its own
  hash-checked artifacts) from an accepted independent verifier — matched
  by EXACT identity, never substring — naming that exact run, AND every
  dependency of the goal is itself satisfied (own evidence can never
  unlock a goal whose dependencies are still locked);
- a goal is **eligible** (may be worked on) when its unlock arm holds:
  root goals need a current ``operator_attestation``; dependent goals
  need every dependency satisfied;
- anything absent, stale, future-dated, hash-mismatched, malformed or
  verified only by a corroborating (non-independent) lane is a blocker —
  locked, never assumed good. Evidence supersession is strict in BOTH
  directions: the NEWEST run receipt governs (when it stops validating
  the goal locks with no fallback to older runs), older receipts are
  notes only, and a fresh run + a verification that cites one of the
  run's own artifacts (exact sha256+path pair, dated at/after the run)
  can re-satisfy the goal after the code or artifacts it cites change.
  A receipt that cannot even be attributed to a goal (unparseable, no
  goal_id) locks EVERY goal until the ledger is repaired.

No scheduler, no writes, no network: a pure function of (registries,
receipts, files, clock). The HTTP adapter in
``routes/finance_goals_routes.py`` exposes it read-only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRIES_DIR = REPO_ROOT / "config" / "finance-goals"
DEFAULT_RECEIPTS_DIR = REPO_ROOT / "automation" / "review" / "finance" / "receipts"
DEFAULT_POLICY_PATH = DEFAULT_REGISTRIES_DIR / "runtime-evaluation.json"

KIND_RUN = "run"
KIND_OPERATOR_ATTESTATION = "operator_attestation"
KIND_INDEPENDENT_VERIFICATION = "independent_verification"
VALID_STATUSES = {"pass", "fail", "insufficient"}

DEFAULT_POLICY: Dict[str, Any] = {
    "receipt_ttl_days": {
        KIND_RUN: 7,
        KIND_OPERATOR_ATTESTATION: 365,
        KIND_INDEPENDENT_VERIFICATION: 30,
    },
    # Accepted independent verifier identities (standing rules: GLM lanes
    # are corroborating only; Sol-class Codex or the human owner are the
    # independent lanes that can discharge a gate).
    "independent_verifiers": ["codex", "sol", "human:tye"],
    "goal_ttl_overrides": {},
}

REQUIRED_RECEIPT_FIELDS = ("goal_id", "kind", "status", "observed_at")

# A receipt dated more than this far in the FUTURE is rejected: clocks
# drift, but a receipt that predates its own evaluation by months is
# evidence tampering, not freshness.
FUTURE_SKEW_MINUTES = 5


class ReceiptError(ValueError):
    """A receipt file is malformed — recorded as a blocker, never fatal."""


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_policy(path: Path = DEFAULT_POLICY_PATH) -> Dict[str, Any]:
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    if path.exists():
        try:
            override = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return policy
        for key in ("receipt_ttl_days", "independent_verifiers"):
            if isinstance(override.get(key), dict):
                policy[key].update(override[key])
            elif isinstance(override.get(key), list):
                policy[key] = override[key]
        if isinstance(override.get("goal_ttl_overrides"), dict):
            policy["goal_ttl_overrides"].update(override["goal_ttl_overrides"])
    return policy


def load_registries(directory: Path = DEFAULT_REGISTRIES_DIR) -> List[Dict[str, Any]]:
    registries = []
    for path in sorted(directory.glob("finance-*-goals.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            registries.append(
                {"file": path.name, "program_id": path.stem, "error": str(exc),
                 "goals": []}
            )
            continue
        data["_file"] = path.name
        data["_sha256"] = sha256_file(path)
        registries.append(data)
    return registries


def load_receipts(directory: Path = DEFAULT_RECEIPTS_DIR) -> List[Dict[str, Any]]:
    receipts: List[Dict[str, Any]] = []
    if not directory.exists():
        return receipts
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            receipts.append(
                {"_file": path.name, "_invalid": f"unparseable: {exc}"}
            )
            continue
        if not isinstance(data, dict):
            receipts.append({"_file": path.name, "_invalid": "not an object"})
            continue
        data.setdefault("_file", path.name)
        missing = [f for f in REQUIRED_RECEIPT_FIELDS if not data.get(f)]
        if missing:
            data["_invalid"] = f"missing fields: {missing}"
        elif data["status"] not in VALID_STATUSES:
            data["_invalid"] = f"status {data['status']!r} not in {sorted(VALID_STATUSES)}"
        receipts.append(data)
    return receipts


def _ttl_days(receipt: Dict[str, Any], policy: Dict[str, Any]) -> Optional[int]:
    goal_overrides = policy.get("goal_ttl_overrides") or {}
    per_goal = (goal_overrides.get(receipt.get("goal_id")) or {}).get(receipt["kind"])
    if isinstance(per_goal, int):
        return per_goal
    return (policy.get("receipt_ttl_days") or {}).get(receipt["kind"])


def _receipt_blockers(
    receipt: Dict[str, Any], *, now: datetime, policy: Dict[str, Any],
    repo_root: Path, check_artifacts: bool,
) -> List[str]:
    if receipt.get("_invalid"):
        return [f"receipt {receipt.get('_file')}: {receipt['_invalid']}"]
    blockers: List[str] = []
    try:
        observed = _parse_iso(receipt["observed_at"])
    except (TypeError, ValueError):
        return [f"receipt {receipt.get('_file')}: observed_at not ISO-8601"]
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    ttl = _ttl_days(receipt, policy)
    if ttl is None:
        blockers.append(
            f"receipt {receipt.get('_file')}: unknown kind {receipt['kind']!r}"
        )
    elif now > observed + timedelta(days=ttl):
        blockers.append(
            f"receipt {receipt.get('_file')}: stale (observed "
            f"{receipt['observed_at']}, ttl {ttl}d)"
        )
    elif observed > now + timedelta(minutes=FUTURE_SKEW_MINUTES):
        # fail-closed but not permanent: the receipt ages into validity
        # once the clock reaches its stamped time, so a single mis-dated
        # receipt can never lock a goal forever
        blockers.append(
            f"receipt {receipt.get('_file')}: future-dated (observed "
            f"{receipt['observed_at']}, now {now.astimezone(timezone.utc).isoformat()}; "
            "recovers when the clock reaches the stamped time)"
        )
    if check_artifacts:
        for artifact in receipt.get("artifacts") or []:
            label = artifact.get("label")
            recorded = artifact.get("sha256")
            art_path = artifact.get("path")
            if not label or not recorded or not art_path:
                blockers.append(
                    f"receipt {receipt.get('_file')}: malformed artifact entry"
                )
                continue
            path = (
                repo_root / art_path[5:]
                if art_path.startswith("repo:")
                else Path(art_path)
            )
            if not path.exists():
                blockers.append(
                    f"receipt {receipt.get('_file')}: artifact missing: {art_path}"
                )
            elif sha256_file(path) != recorded:
                blockers.append(
                    f"receipt {receipt.get('_file')}: artifact hash mismatch "
                    f"({label})"
                )
    return blockers


def _artifact_check_needed(receipt: Dict[str, Any]) -> bool:
    return receipt.get("kind") in (KIND_RUN, KIND_INDEPENDENT_VERIFICATION)


def evaluate_goals(
    *,
    registries: Optional[List[Dict[str, Any]]] = None,
    receipts: Optional[List[Dict[str, Any]]] = None,
    policy: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
    repo_root: Path = REPO_ROOT,
) -> Dict[str, Any]:
    registries = registries if registries is not None else load_registries()
    receipts = receipts if receipts is not None else load_receipts()
    policy = policy if policy is not None else load_policy()
    now = now or datetime.now(timezone.utc)

    goals: Dict[str, Dict[str, Any]] = {}
    program_of: Dict[str, str] = {}
    for registry in registries:
        for goal in registry.get("goals") or []:
            goals[goal["id"]] = {**goal, "_program": registry.get("program_id")}
            program_of[goal["id"]] = registry.get("program_id") or "?"

    by_goal: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {
        KIND_RUN: {},
        KIND_OPERATOR_ATTESTATION: {},
        KIND_INDEPENDENT_VERIFICATION: {},
    }
    # Malformed evidence is never invisible: receipts that carry a
    # goal_id but cannot be classified lock that goal, and receipts that
    # cannot even be attributed (unparseable, no goal_id) lock EVERY
    # goal — a corrupted ledger must fail closed, not quietly drop the
    # poisoned file out of the derivation.
    malformed_by_goal: Dict[str, List[str]] = {}
    global_invalid: List[str] = []
    for receipt in receipts:
        file_name = receipt.get("_file") or "?"
        goal_id = receipt.get("goal_id")
        kind = receipt.get("kind")
        invalid_reason = receipt.get("_invalid")
        if goal_id is None or kind is None:
            # cannot be attributed to a goal at all (unparseable JSON,
            # missing goal_id/kind): poisons the whole ledger
            global_invalid.append(
                f"{file_name} ({invalid_reason or 'no goal_id/kind attribution'})"
            )
            continue
        if kind not in by_goal or invalid_reason:
            # attributed to a goal but malformed (bad status, missing
            # fields) or of unknown kind: locks that goal specifically
            malformed_by_goal.setdefault(goal_id, []).append(
                f"{file_name} ("
                + (invalid_reason or f"unknown kind {kind!r}")
                + ")"
            )
            continue
        by_goal[kind].setdefault(goal_id, {})[file_name] = receipt

    evaluated: List[Dict[str, Any]] = []

    def _observed_at(receipt: Dict[str, Any]) -> Optional[datetime]:
        """Parse observed_at, or None when unparseable (unorderable)."""
        try:
            parsed = _parse_iso(receipt["observed_at"])
        except (KeyError, TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _order_key(receipt: Dict[str, Any]) -> Any:
        parsed = _observed_at(receipt)
        if parsed is None:
            # unparseable receipts sort LAST: an unreadable timestamp can
            # never be proven older than the newest receipt, so it must
            # never quietly sort to the back of history
            return (1, datetime.min.replace(tzinfo=timezone.utc))
        return (0, parsed)

    def own_evidence_blockers(goal_id: str) -> List[str]:
        """Blockers in this goal's OWN run/verification receipts.

        The NEWEST run receipt (by observed_at) governs — valid or not.
        If the newest run no longer validates (stale, future-dated,
        artifact hash mismatch, unparseable timestamp), the goal is
        LOCKED even when an older run still validates: fresh evidence
        cannot silently fall back to a superseded result. Older receipts
        are notes, surfaced only while the goal stays locked. A receipt
        whose observed_at cannot be parsed is treated as newest (it
        cannot be proven older), and a receipt that cannot be classified
        at all locks the goal from the malformed bucket."""
        malformed = malformed_by_goal.get(goal_id) or []
        if malformed:
            return [
                f"{goal_id}: malformed receipt(s) in the evidence ledger — "
                "locked: " + "; ".join(malformed)
            ]

        notes: List[str] = []
        run_receipts = by_goal[KIND_RUN].get(goal_id) or {}
        ordered = sorted(
            run_receipts.items(),
            key=lambda kv: (_order_key(kv[1]), kv[0]),
        )
        if not ordered:
            return [f"{goal_id}: no run receipt"]

        def run_problems(name: str, receipt: Dict[str, Any]) -> List[str]:
            problems: List[str] = []
            if receipt.get("status") != "pass":
                problems.append(f"run receipt {name} status={receipt.get('status')!r}")
            elif not receipt.get("run_id"):
                problems.append(f"run receipt {name} has no run_id")
            elif not receipt.get("artifacts"):
                problems.append(f"run receipt {name} records no artifacts")
            else:
                problems.extend(_receipt_blockers(
                    receipt, now=now, policy=policy, repo_root=repo_root,
                    check_artifacts=_artifact_check_needed(receipt),
                ))
            if _observed_at(receipt) is None:
                problems.append(
                    f"run receipt {name} has an unparseable observed_at — "
                    "cannot be ordered against other evidence"
                )
            return problems

        # Older receipts are history: their problems are noted but can
        # neither lock nor unlock the goal. Only the NEWEST governs —
        # and unparseable timestamps sort newest, so they lock.
        for name, receipt in ordered[:-1]:
            if run_problems(name, receipt):
                notes.append(
                    f"{goal_id}: superseded run receipt {name} no longer "
                    "validates (noted; newest run governs)"
                )

        newest_name, newest = ordered[-1]
        problems = run_problems(newest_name, newest)
        if problems:
            notes.append(f"{goal_id}: " + "; ".join(problems))
            # the newest run governs: when it no longer validates we do
            # NOT fall back to an older still-valid run
            return notes + [
                f"{goal_id}: newest run receipt does not validate — locked"
            ]
        best_run = newest

        # (sha256, path) pairs, not bare hashes: identical bytes at two
        # paths (latest.json vs a timestamped snapshot) must not let a
        # verification "cite" an artifact the run receipt never named
        run_cited = {
            (artifact.get("sha256"), artifact.get("path"))
            for artifact in best_run.get("artifacts") or []
        }
        run_observed = _observed_at(best_run)

        verifications = by_goal[KIND_INDEPENDENT_VERIFICATION].get(goal_id) or {}
        verified = None
        for name, verification in sorted(verifications.items()):
            problems = list(_receipt_blockers(
                verification, now=now, policy=policy, repo_root=repo_root,
                check_artifacts=_artifact_check_needed(verification),
            ))
            if verification.get("status") != "pass":
                problems.append(
                    f"verification {name} status={verification.get('status')!r}"
                )
            if not verification.get("verifies"):
                problems.append(f"verification {name} names no run id")
            elif verification.get("verifies") != best_run.get("run_id"):
                problems.append(
                    f"verification {name} names run "
                    f"{verification.get('verifies')!r}, not "
                    f"{best_run.get('run_id')!r}"
                )
            if not verification.get("artifacts"):
                problems.append(
                    f"verification {name} records no artifacts"
                )
            # EXACT identity match against the accepted independent lanes.
            # A substring match would let e.g. "glm-codex" ride on "codex"
            # and discharge a gate a corroborating lane must never open.
            if verification.get("verifier") not in policy.get(
                "independent_verifiers", []
            ):
                problems.append(
                    f"verification {name} lane "
                    f"{verification.get('verifier')!r} is corroborating, "
                    "not independent"
                )
            # A verification cannot predate the run it claims to verify.
            # (unparseable observed_at already produced a blocker above,
            # so None never reaches this comparison)
            v_observed = _observed_at(verification)
            if v_observed is not None and v_observed < run_observed:
                problems.append(
                    f"verification {name} predates run "
                    f"{best_run.get('run_id')!r}"
                )
            # The verifier must have actually looked at the run's
            # evidence: at least one verification artifact must reproduce
            # an EXACT (sha256, path) pair the run receipt cites (run_id
            # strings are reusable and identical bytes can live at many
            # paths; the pair binds the verification to THIS run).
            v_cited = {
                (artifact.get("sha256"), artifact.get("path"))
                for artifact in verification.get("artifacts") or []
            }
            if not (run_cited & v_cited):
                problems.append(
                    f"verification {name} cites none of run "
                    f"{best_run.get('run_id')!r}'s artifacts "
                    "(exact sha256+path pairs)"
                )
            if problems:
                notes.append(f"{goal_id}: " + "; ".join(problems))
            else:
                verified = verification
                break
        if verified is None:
            return notes + [
                f"{goal_id}: no current independent verification of run "
                f"{best_run.get('run_id')!r}"
            ]
        return []

    satisfaction_cache: Dict[str, Tuple[bool, List[str]]] = {}

    def goal_satisfaction(goal_id: str, seen: frozenset) -> Tuple[bool, List[str]]:
        """(satisfied, blockers), recursion-safe on cycles. A goal is
        satisfied only while its OWN evidence is current AND every
        dependency is itself satisfied — own receipts can never unlock a
        goal whose dependencies are still locked (cross-program MT-04 ->
        MT-03 + FT-02 included)."""
        if goal_id in satisfaction_cache:
            return satisfaction_cache[goal_id]
        if goal_id in seen:
            return False, [f"{goal_id}: dependency cycle"]
        if goal_id not in goals:
            return False, [f"dependency {goal_id}: unknown goal id"]
        blockers = list(own_evidence_blockers(goal_id))
        for dep in goals[goal_id].get("depends_on") or []:
            dep_satisfied, dep_blockers = goal_satisfaction(
                dep, seen | {goal_id}
            )
            if not dep_satisfied:
                blockers.append(f"dependency {dep} not satisfied")
                blockers.extend(dep_blockers)
        result = (not blockers, blockers)
        satisfaction_cache[goal_id] = result
        return result

    for goal_id, goal in goals.items():
        satisfied, sat_blockers = goal_satisfaction(goal_id, frozenset())
        blockers: List[str] = list(sat_blockers)

        eligible = True
        if global_invalid:
            # a receipt that cannot be attributed to ANY goal (unparseable
            # JSON, missing goal_id) poisons the whole ledger: every goal
            # locks until the file is repaired or removed — it must never
            # be quietly dropped from the derivation
            satisfied = False
            eligible = False
            blockers.append(
                f"{goal_id}: evidence ledger has unattributable receipt(s) "
                "— locked: " + "; ".join(global_invalid)
            )
        if goal.get("depends_on"):
            for dep in goal["depends_on"]:
                dep_satisfied, _ = goal_satisfaction(dep, frozenset())
                if not dep_satisfied:
                    eligible = False
        else:
            attestations = by_goal[KIND_OPERATOR_ATTESTATION].get(goal_id) or {}
            current_attestation = None
            for name, attestation in sorted(attestations.items()):
                a_blockers = _receipt_blockers(
                    attestation, now=now, policy=policy, repo_root=repo_root,
                    check_artifacts=False,
                )
                if a_blockers:
                    blockers.extend(
                        f"{goal_id}: attestation {name}: {b}" for b in a_blockers
                    )
                    continue
                if attestation.get("status") == "pass":
                    current_attestation = attestation
                    break
            if current_attestation is None:
                eligible = False
                blockers.append(
                    f"{goal_id}: no current operator authorisation attestation"
                )

        evaluated.append(
            {
                "id": goal_id,
                "title": goal.get("title"),
                "program_id": goal.get("_program"),
                "depends_on": goal.get("depends_on") or [],
                "satisfied": satisfied,
                "eligible": eligible,
                "blockers": blockers,
            }
        )

    return {
        "ok": True,
        "evaluated_at": now.astimezone(timezone.utc).isoformat(),
        "ledger_unattributable": global_invalid,
        "policy": {
            "receipt_ttl_days": policy.get("receipt_ttl_days"),
            "independent_verifiers": policy.get("independent_verifiers"),
        },
        "programs": [
            {
                "program_id": r.get("program_id"),
                "file": r.get("_file") or r.get("file"),
                "sha256": r.get("_sha256"),
                "canonical_source": r.get("owner_repository"),
                "error": r.get("error"),
            }
            for r in registries
        ],
        "goals": evaluated,
    }

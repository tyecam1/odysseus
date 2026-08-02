"""Independently testable stages for quarantine-first pattern ingestion."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import date
from pathlib import Path
from typing import Callable, Dict, Iterable, Mapping, Optional

from services.memory.skills import SkillsManager
from src.prompt_security import untrusted_context_message

from .models import (
    AdaptationProposal,
    CandidateRecord,
    EvaluationResult,
    StageResult,
)
from .storage import PipelinePaths, create_snapshot, quarantine_snapshot, save_json, tree_hash

logger = logging.getLogger(__name__)

PERMITTED_LICENCES = {"MIT", "APACHE-2.0", "BSD-2-CLAUSE", "BSD-3-CLAUSE", "ISC"}
PERMISSION_CEILINGS = {
    "prompt-skill-pattern-source": frozenset({"read-local-snapshot"}),
}
ROOT_INSTRUCTION_FILES = {
    "agents.md", "claude.md", "system.md", "system-prompt.md", "constitution.md",
}

_IDENTITY_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
_INJECTION_PATTERNS = {
    "prompt-injection": re.compile(
        r"\b(ignore|disregard|override)\s+(all\s+)?(previous|prior|system)\s+instructions?\b",
        re.IGNORECASE,
    ),
    "role-redefinition": re.compile(r"\byou\s+are\s+now\b|\bact\s+as\s+(?:the\s+)?system\b", re.IGNORECASE),
    "permission-redefinition": re.compile(
        r"\b(?:grant|widen|escalate)\s+(?:your\s+)?permissions?\b|\bbypass\s+(?:the\s+)?approval\b",
        re.IGNORECASE,
    ),
    "root-instruction-mutation": re.compile(
        r"\b(?:write|edit|modify|replace)\s+(?:the\s+)?(?:agents\.md|system prompt|root instructions?)\b",
        re.IGNORECASE,
    ),
    "embedded-credential": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b|\b(?:api[_-]?key|secret)\s*[:=]\s*['\"][^'\"]{12,}",
        re.IGNORECASE,
    ),
}
_EXECUTABLE_SUFFIXES = {
    ".exe", ".dll", ".so", ".dylib", ".bat", ".cmd", ".ps1", ".sh", ".com", ".msi", ".jar",
}


class StageBlocked(RuntimeError):
    """A prerequisite stage or gate was not conclusively completed."""


def _completed(candidate: CandidateRecord, stage: str) -> bool:
    result = candidate.stage_results.get(stage)
    return bool(result and result.completed)


def _require(candidate: CandidateRecord, stage: str) -> None:
    if not _completed(candidate, stage):
        state = candidate.stage_results.get(stage)
        detail = state.state if state else "not-run"
        raise StageBlocked(f"{stage} is {detail}; absence of evidence does not satisfy the gate")


def discover_local(candidate: CandidateRecord, source: Path) -> StageResult:
    candidate.validate_required_metadata()
    if not source.is_dir():
        return candidate.record_stage(StageResult("discover", "not-found", False, str(source)))
    candidate.provenance = "local-fixture" if "fixture" in str(source).lower() else "local-directory"
    return candidate.record_stage(StageResult("discover", "local-source", True, str(source.resolve())))


def discover_network(
    candidate: CandidateRecord,
    resolver: Optional[Callable[[str], str]] = None,
) -> StageResult:
    candidate.validate_required_metadata()
    if resolver is None:
        return candidate.record_stage(StageResult(
            "discover", "not-run", False,
            "network resolver unavailable; discovery was not attempted",
        ))
    try:
        resolved = resolver(candidate.repository_url)
    except Exception as exc:
        logger.warning("prompt ingestion discovery could not run: %s", exc)
        return candidate.record_stage(StageResult("discover", "not-run", False, str(exc)))
    if not resolved:
        return candidate.record_stage(StageResult("discover", "not-found", True, "resolver returned no repository"))
    return candidate.record_stage(StageResult("discover", "found", True, str(resolved)))


def snapshot_local(candidate: CandidateRecord, source: Path, paths: PipelinePaths) -> StageResult:
    _require(candidate, "discover")
    snapshot_id, content_root, source_hash = create_snapshot(source, paths)
    # A re-fetch is new evidence. Never let identity, licence, scan, evaluation,
    # or review results from an older snapshot satisfy gates for the new bytes.
    for stage in (
        "identify", "licence-check", "hash", "quarantine", "security-scan",
        "classify", "deduplicate", "evaluate", "adapt", "review", "activate",
    ):
        candidate.stage_results.pop(stage, None)
    candidate.licence = "not-checked"
    candidate.prompt_injection_risk = "not-scanned"
    candidate.overlapping_local_skill = "not-compared"
    candidate.evaluation_corpus = "not-run"
    candidate.evaluation_result = None
    candidate.adaptation_decision = "not-made"
    candidate.quarantine_path = "not-quarantined"
    candidate.adapted_artifact_path = "not-adapted"
    candidate.activated_skill_name = "not-activated"
    candidate.terminal_state = "not-terminal"
    candidate.terminal_reason = "not-terminal"
    entry = {
        "snapshot_id": snapshot_id,
        "source_hash": source_hash,
        "content_path": str(content_root),
        "provenance": candidate.provenance,
    }
    candidate.snapshot_history.append(entry)
    candidate.current_snapshot_id = snapshot_id
    candidate.source_path = str(content_root)
    candidate.source_hash = source_hash
    candidate.retrieved_date = date.today().isoformat()
    return candidate.record_stage(StageResult("snapshot", "local-snapshot", True, snapshot_id))


def snapshot_network(candidate: CandidateRecord) -> StageResult:
    if not _completed(candidate, "discover"):
        return candidate.record_stage(StageResult(
            "snapshot", "not-fetched", False,
            "network discovery did not complete; no bytes were fetched",
        ))
    return candidate.record_stage(StageResult(
        "snapshot", "not-fetched", False,
        "network snapshot transport is unavailable in this runtime",
    ))


def identify(candidate: CandidateRecord) -> StageResult:
    _require(candidate, "snapshot")
    match = _IDENTITY_RE.fullmatch(candidate.repository_url.strip())
    if not match:
        candidate.terminal_state = "defer"
        candidate.terminal_reason = "unresolved-identity"
        return candidate.record_stage(StageResult(
            "identify", "unresolved-identity", False,
            "identity requires exactly one owner-qualified GitHub repository URL",
        ))
    if (
        match.group("owner").lower() != candidate.repository_owner.lower()
        or match.group("repo").lower() != candidate.repository_name.lower()
    ):
        candidate.terminal_state = "defer"
        candidate.terminal_reason = "identity-mismatch"
        return candidate.record_stage(StageResult("identify", "unresolved-identity", False, "URL and metadata disagree"))
    return candidate.record_stage(StageResult("identify", "resolved", True, candidate.repository_url))


def _licence_text(snapshot_root: Path) -> Optional[str]:
    for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"):
        path = snapshot_root / name
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    return None


def licence_check(candidate: CandidateRecord) -> StageResult:
    _require(candidate, "identify")
    text = _licence_text(Path(candidate.source_path))
    if text is None:
        candidate.licence = "absent"
        candidate.terminal_state = "defer"
        candidate.terminal_reason = "licence-absent"
        return candidate.record_stage(StageResult("licence-check", "absent", False, "no LICENSE or COPYING file"))
    upper = text.upper()
    if "NONCOMMERCIAL" in upper or "NO DERIVATIVES" in upper or "BY-NC-ND" in upper:
        candidate.licence = "CC-BY-NC-ND-4.0"
        candidate.terminal_state = "reject"
        candidate.terminal_reason = "licence-prohibits-use"
        return candidate.record_stage(StageResult("licence-check", "prohibited", False, candidate.licence))
    if "MIT LICENSE" in upper and "PERMISSION IS HEREBY GRANTED" in upper:
        candidate.licence = "MIT"
    elif "APACHE LICENSE" in upper and "VERSION 2.0" in upper:
        candidate.licence = "APACHE-2.0"
    else:
        candidate.licence = "ambiguous"
        candidate.terminal_state = "defer"
        candidate.terminal_reason = "licence-ambiguous"
        return candidate.record_stage(StageResult("licence-check", "ambiguous", False, "licence could not be determined"))
    return candidate.record_stage(StageResult("licence-check", "permitted", True, candidate.licence))


def verify_hash(candidate: CandidateRecord) -> StageResult:
    _require(candidate, "licence-check")
    actual = tree_hash(Path(candidate.source_path))
    if actual != candidate.source_hash:
        candidate.terminal_state = "reject"
        candidate.terminal_reason = "snapshot-hash-mismatch"
        return candidate.record_stage(StageResult("hash", "mismatch", False, actual))
    return candidate.record_stage(StageResult("hash", "verified", True, actual))


def quarantine(candidate: CandidateRecord, paths: PipelinePaths) -> StageResult:
    _require(candidate, "hash")
    destination = quarantine_snapshot(candidate.current_snapshot_id, paths)
    candidate.quarantine_path = str(destination)
    return candidate.record_stage(StageResult("quarantine", "quarantined", True, str(destination)))


def security_scan(
    candidate: CandidateRecord,
    scanner: Optional[Callable[[Path], Iterable[str]]] = None,
) -> StageResult:
    _require(candidate, "quarantine")
    if scanner is None:
        scanner = _default_security_scanner
    try:
        findings = sorted(set(scanner(Path(candidate.quarantine_path))))
    except Exception as exc:
        candidate.prompt_injection_risk = "not-scanned"
        logger.warning("prompt ingestion security scan could not run: %s", exc)
        return candidate.record_stage(StageResult("security-scan", "not-scanned", False, str(exc)))
    if findings:
        candidate.prompt_injection_risk = "findings:" + ",".join(findings)
        candidate.terminal_state = "reject"
        candidate.terminal_reason = "security-findings"
        return candidate.record_stage(StageResult("security-scan", "findings", False, ", ".join(findings)))
    candidate.prompt_injection_risk = "clean"
    return candidate.record_stage(StageResult("security-scan", "clean", True, "scanner completed with no findings"))


def _default_security_scanner(root: Path) -> Iterable[str]:
    for relative, path in _iter_quarantine_files(root):
        if path.suffix.lower() in _EXECUTABLE_SUFFIXES:
            yield f"executable-payload:{relative}"
        raw = path.read_bytes()
        if raw.startswith((b"MZ", b"\x7fELF")):
            yield f"executable-payload:{relative}"
        text = raw.decode("utf-8", errors="replace")
        if text.startswith("#!"):
            yield f"executable-payload:{relative}"
        for label, pattern in _INJECTION_PATTERNS.items():
            if pattern.search(text):
                yield f"{label}:{relative}"


def _iter_quarantine_files(root: Path):
    resolved_root = root.resolve(strict=True)
    for path in sorted(resolved_root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ValueError(f"quarantine contains a symlink: {path}")
        if path.is_file():
            yield path.relative_to(resolved_root).as_posix(), path


def build_snapshot_model_messages(system_prompt: str, source_label: str, snapshot_text: str) -> list[dict]:
    """Package snapshot text as a fenced, untrusted user message only."""
    return [
        {"role": "system", "content": system_prompt},
        untrusted_context_message(source_label, snapshot_text),
    ]


def classify(candidate: CandidateRecord) -> StageResult:
    _require(candidate, "security-scan")
    ceiling = PERMISSION_CEILINGS.get(candidate.capability_family)
    if ceiling is None:
        candidate.terminal_state = "defer"
        candidate.terminal_reason = "unknown-capability-family"
        return candidate.record_stage(StageResult("classify", "not-classified", False, candidate.capability_family))
    excess = sorted(set(candidate.required_permissions) - ceiling)
    if excess:
        candidate.terminal_state = "reject"
        candidate.terminal_reason = "permission-widening"
        return candidate.record_stage(StageResult("classify", "rejected", False, ", ".join(excess)))
    return candidate.record_stage(StageResult("classify", "classified", True, candidate.capability_family))


def deduplicate(candidate: CandidateRecord, skills_manager: SkillsManager) -> StageResult:
    _require(candidate, "classify")
    wanted = set(re.findall(r"[a-z0-9]+", candidate.intended_capability.lower()))
    overlaps = []
    for skill in skills_manager.load_all():
        existing = set(re.findall(
            r"[a-z0-9]+",
            " ".join((skill.get("name", ""), skill.get("description", ""))).lower(),
        ))
        if wanted and len(wanted & existing) / len(wanted) >= 0.6:
            overlaps.append(skill.get("name", "unknown"))
    candidate.overlapping_local_skill = ",".join(sorted(overlaps)) if overlaps else "none-found"
    state = "overlap" if overlaps else "unique"
    return candidate.record_stage(StageResult("deduplicate", state, True, candidate.overlapping_local_skill))


def evaluate(
    candidate: CandidateRecord,
    corpus_path: Path,
    candidate_responses: Mapping[str, str],
    paths: PipelinePaths,
) -> StageResult:
    _require(candidate, "deduplicate")
    corpus = _load_held_out_corpus(corpus_path, candidate, paths)
    cases = corpus["cases"]
    case_ids = {case["id"] for case in cases}
    extra = set(candidate_responses) - case_ids
    if extra:
        raise ValueError("candidate cannot add evaluation cases: " + ", ".join(sorted(extra)))
    baseline_score = _score_cases(cases, {case["id"]: case["baseline_response"] for case in cases})
    candidate_score = _score_cases(cases, candidate_responses)
    raw = corpus_path.read_bytes()
    result = EvaluationResult(
        corpus_id=corpus["corpus_id"],
        corpus_hash=hashlib.sha256(raw).hexdigest(),
        baseline_score=baseline_score,
        candidate_score=candidate_score,
        delta=round(candidate_score - baseline_score, 6),
        case_count=len(cases),
        corpus_created=corpus["created"],
    )
    candidate.evaluation_corpus = result.corpus_id
    candidate.evaluation_result = result
    save_json(paths.evaluations / f"{candidate.candidate_id}.json", {
        "candidate_id": candidate.candidate_id,
        **result.__dict__,
    })
    state = "improved" if result.delta > 0 else "not-improved"
    return candidate.record_stage(StageResult("evaluate", state, True, f"delta={result.delta:+.6f}"))


def _load_held_out_corpus(corpus_path: Path, candidate: CandidateRecord, paths: PipelinePaths) -> dict:
    resolved = corpus_path.resolve(strict=True)
    excluded = [paths.snapshots.resolve(), paths.quarantine.resolve()]
    for root in excluded:
        if os_commonpath(root, resolved) == root:
            raise ValueError("evaluation corpus cannot originate from candidate snapshot or quarantine")
    corpus = json.loads(resolved.read_text(encoding="utf-8"))
    if corpus.get("trusted_source") is not True:
        raise ValueError("evaluation corpus lacks explicit trusted_source=true")
    if not corpus.get("corpus_id") or not corpus.get("created") or not corpus.get("cases"):
        raise ValueError("evaluation corpus metadata is incomplete")
    if candidate.retrieved_date.startswith("not-") or corpus["created"] >= candidate.retrieved_date:
        raise ValueError("evaluation corpus must predate candidate retrieval")
    for case in corpus["cases"]:
        if not case.get("id") or not case.get("required_phrases") or "baseline_response" not in case:
            raise ValueError("evaluation case is incomplete")
    return corpus


def os_commonpath(root: Path, path: Path) -> Path:
    try:
        return Path(os.path.commonpath((str(root), str(path))))
    except ValueError:
        return Path("__different_volume__")


def _score_cases(cases: list[dict], responses: Mapping[str, str]) -> float:
    scores = []
    for case in cases:
        response = responses.get(case["id"], "").lower()
        required = [str(item).lower() for item in case["required_phrases"]]
        scores.append(sum(item in response for item in required) / len(required))
    return round(sum(scores) / len(scores), 6)


def adapt(candidate: CandidateRecord, proposal: AdaptationProposal, paths: PipelinePaths) -> StageResult:
    _require(candidate, "evaluate")
    target_name = Path(proposal.target).name.lower()
    if target_name in ROOT_INSTRUCTION_FILES or proposal.target != "existing-skill-registry":
        candidate.adaptation_decision = "reject-root-instruction-mutation"
        candidate.terminal_state = "reject"
        candidate.terminal_reason = "root-instruction-mutation"
        return candidate.record_stage(StageResult("adapt", "rejected", False, proposal.target))
    ceiling = PERMISSION_CEILINGS.get(candidate.capability_family, frozenset())
    excess = sorted(set(proposal.required_permissions) - ceiling)
    if excess:
        candidate.adaptation_decision = "reject-permission-widening"
        candidate.terminal_state = "reject"
        candidate.terminal_reason = "permission-widening"
        return candidate.record_stage(StageResult("adapt", "rejected", False, ", ".join(excess)))
    total_text = proposal.principle + " ".join(proposal.procedure)
    if len(proposal.principle) > 500 or len(total_text) > 2000 or len(proposal.procedure) > 7:
        candidate.adaptation_decision = "reject-bulk-copy"
        candidate.terminal_state = "reject"
        candidate.terminal_reason = "adaptation-not-small"
        return candidate.record_stage(StageResult("adapt", "rejected", False, "adaptation exceeds small-principle limits"))
    artifact = {
        "name": proposal.name,
        "principle": proposal.principle,
        "when_to_use": proposal.when_to_use,
        "procedure": proposal.procedure,
        "verification": proposal.verification,
        "required_tools": proposal.required_tools,
        "required_permissions": proposal.required_permissions,
        "target": proposal.target,
        "derivation": {
            "repository": f"{candidate.repository_owner}/{candidate.repository_name}",
            "repository_url": candidate.repository_url,
            "commit_or_release": candidate.commit_or_release,
            "source_hash": candidate.source_hash,
            "snapshot_id": candidate.current_snapshot_id,
            "provenance": candidate.provenance,
        },
    }
    artifact_path = paths.adaptations / f"{candidate.candidate_id}.json"
    save_json(artifact_path, artifact)
    candidate.adapted_artifact_path = str(artifact_path)
    candidate.adaptation_decision = "adapt-small-principle"
    return candidate.record_stage(StageResult("adapt", "adapted", True, str(artifact_path)))


def review(candidate: CandidateRecord) -> StageResult:
    _require(candidate, "adapt")
    candidate.validate_required_metadata()
    blockers = []
    if candidate.licence.upper() not in PERMITTED_LICENCES:
        blockers.append("licence-not-permitted")
    scan = candidate.stage_results.get("security-scan")
    if not scan or scan.state != "clean" or not scan.completed:
        blockers.append("scan-not-clean")
    if candidate.evaluation_result is None:
        blockers.append("evaluation-not-run")
    elif candidate.evaluation_result.delta <= 0:
        blockers.append("evaluation-did-not-beat-baseline")
    if blockers:
        candidate.terminal_state = "reject"
        candidate.terminal_reason = ",".join(blockers)
        return candidate.record_stage(StageResult("review", "rejected", True, candidate.terminal_reason))
    return candidate.record_stage(StageResult("review", "approved", True, "all activation gates satisfied"))


def activate(candidate: CandidateRecord, skills_manager: SkillsManager) -> StageResult:
    candidate.validate_required_metadata()
    review_result = candidate.stage_results.get("review")
    if not review_result or not review_result.completed or review_result.state != "approved":
        result = candidate.reject("activation requires an approved review")
        candidate.stage_results["activate"] = result
        return result
    if candidate.licence.upper() not in PERMITTED_LICENCES:
        result = candidate.reject("activation requires a licence permitting actual use")
        candidate.stage_results["activate"] = result
        return result
    scan = candidate.stage_results.get("security-scan")
    if not scan or not scan.completed or scan.state != "clean":
        result = candidate.reject("activation requires a completed clean scan")
        candidate.stage_results["activate"] = result
        return result
    if candidate.evaluation_result is None:
        result = candidate.reject("activation requires an evaluation result")
        candidate.stage_results["activate"] = result
        return result
    artifact = json.loads(Path(candidate.adapted_artifact_path).read_text(encoding="utf-8"))
    provenance = artifact["derivation"]
    provenance_note = (
        "Provenance: adapted as a small principle from "
        f"{provenance['repository']} at {provenance['commit_or_release']}; "
        f"snapshot SHA-256 {provenance['source_hash']}; provenance {provenance['provenance']}."
    )
    skill = skills_manager.add_skill(
        name=artifact["name"],
        description=artifact["principle"],
        category="adapted-patterns",
        when_to_use=artifact["when_to_use"],
        procedure=artifact["procedure"],
        verification=[*artifact["verification"], provenance_note],
        requires_toolsets=artifact["required_tools"],
        status="published",
        source="imported",
    )
    candidate.activated_skill_name = skill["name"]
    candidate.terminal_state = "activate"
    candidate.terminal_reason = "all gates satisfied"
    return candidate.record_stage(StageResult("activate", "activated", True, skill["name"]))

"""Ordered orchestration for the external pattern ingestion stages."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Mapping, Optional

from services.memory.skills import SkillsManager

from .models import AdaptationProposal, CandidateRecord
from .stages import (
    activate,
    adapt,
    classify,
    deduplicate,
    discover_local,
    discover_network,
    evaluate,
    identify,
    licence_check,
    quarantine,
    review,
    security_scan,
    snapshot_local,
    snapshot_network,
    verify_hash,
)
from .storage import PipelinePaths, save_json

logger = logging.getLogger(__name__)


def _persist(candidate: CandidateRecord, paths: PipelinePaths) -> None:
    save_json(paths.records / f"{candidate.candidate_id}.json", candidate.to_dict())


def run_local_pipeline(
    candidate: CandidateRecord,
    source: Path,
    corpus_path: Path,
    candidate_responses: Mapping[str, str],
    proposal: AdaptationProposal,
    paths: PipelinePaths,
    skills_manager: SkillsManager,
) -> CandidateRecord:
    """Run one local-directory candidate, stopping on every inconclusive gate."""
    ordered = (
        lambda: discover_local(candidate, source),
        lambda: snapshot_local(candidate, source, paths),
        lambda: identify(candidate),
        lambda: licence_check(candidate),
        lambda: verify_hash(candidate),
        lambda: quarantine(candidate, paths),
        lambda: security_scan(candidate),
        lambda: classify(candidate),
        lambda: deduplicate(candidate, skills_manager),
        lambda: evaluate(candidate, corpus_path, candidate_responses, paths),
        lambda: adapt(candidate, proposal, paths),
        lambda: review(candidate),
    )
    for stage in ordered:
        result = stage()
        _persist(candidate, paths)
        if not result.completed:
            logger.info(
                "prompt ingestion stopped candidate=%s stage=%s state=%s",
                candidate.candidate_id,
                result.stage,
                result.state,
            )
            return candidate
    if candidate.stage_results["review"].state == "approved":
        activate(candidate, skills_manager)
        _persist(candidate, paths)
    return candidate


def run_network_unavailable(
    candidate: CandidateRecord,
    paths: PipelinePaths,
    resolver: Optional[object] = None,
) -> CandidateRecord:
    """Record an unavailable network path without representing it as empty."""
    discover_network(candidate, resolver=resolver)
    snapshot_network(candidate)
    _persist(candidate, paths)
    return candidate


__all__ = ["PipelinePaths", "run_local_pipeline", "run_network_unavailable"]

"""Transparent, versioned work-node difficulty scoring."""

from __future__ import annotations

from typing import Mapping

from .models import DifficultyComponents, DifficultyExplanation


DIFFICULTY_VERSION = "1.1"
DIFFICULTY_WEIGHTS = {
    "blocker_severity": 0.14,
    "blocker_count": 0.08,
    "external_dependency": 0.12,
    "cross_repository_dependency": 0.10,
    "unresolved_uncertainty": 0.13,
    "test_gap": 0.11,
    "deployment_surface": 0.10,
    "rollback_risk": 0.09,
    "implementation_complexity": 0.13,
}


def score_difficulty(
    components: DifficultyComponents | Mapping[str, int],
    *,
    rationale: list[str] | None = None,
) -> DifficultyExplanation:
    values = components if isinstance(components, DifficultyComponents) else DifficultyComponents(**components)
    raw = sum(getattr(values, key) * weight for key, weight in DIFFICULTY_WEIGHTS.items())
    score = max(0, min(100, int(round(raw))))
    band = "low" if score < 34 else "medium" if score < 67 else "high"
    reasons = list(rationale or [])
    if not reasons:
        ranked = sorted(
            ((getattr(values, key), key.replace("_", " ")) for key in DIFFICULTY_WEIGHTS),
            reverse=True,
        )
        reasons = [f"{label}: {value}/100" for value, label in ranked[:3] if value]
    if not reasons:
        reasons = ["No material difficulty indicators were present in the source artifact."]
    return DifficultyExplanation(
        version=DIFFICULTY_VERSION,
        score=score,
        band=band,
        components=values,
        weights=DIFFICULTY_WEIGHTS,
        rationale=reasons,
    )

"""Deterministic lead-persona routing for the Misumi interface.

Implements the ratified Aoteru routing contract v0.1
(docs/core/aoteru-routing-contract-v0.1.md in the canonical knowledgebase):

1. Read persona routes from ``config/personas.yaml`` at
   ``personas.<id>.routing.intents``.
2. Route explicit keyword matches to the best-matching persona. Manifest
   order resolves equal scores.
3. Route unmatched requests to Aoteru for direct handling.
4. Keep standards, values, boundaries, ratification, and Level 5 or Level 6
   matters with Aoteru even when another intent also matches.

The matching algorithm intentionally mirrors ``scripts/route_dry_run.py`` in
the canonical knowledgebase so that the dry-run contract test stays a faithful
local projection of runtime behaviour. This module selects only the lead
persona for one request: it grants no write authority, triggers no extra
model calls, and never creates a separate persona truth store — persona routes
are read from the canonical knowledgebase via the seed-order root.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.seed_order_context import _resolve_seed_root

try:
    import yaml
except ImportError:  # PyYAML is optional at runtime; routing degrades to Aoteru.
    yaml = None


logger = logging.getLogger(__name__)

_PERSONAS_FILE = Path("config/personas.yaml")
_ROUTING_METHOD = "routing-contract-v0.1"
_FALLBACK_PERSONA = "aoteru"
RESERVED = re.compile(
    r"\b(?:standards?|values?|boundaries|ratif(?:y|ied|ication))\b|"
    r"\blevel\s*(?:5|five|6|six)\b",
    re.IGNORECASE,
)


def _keyword_present(text: str, keyword: str) -> bool:
    return re.search(
        r"(?<![a-z0-9])" + re.escape(keyword.lower()) + r"(?![a-z0-9])",
        text.lower(),
    ) is not None


def load_personas(root: str | os.PathLike[str] | None = None) -> Mapping[str, Any] | None:
    """Load ``config/personas.yaml`` from the canonical seed root (or ``root``)."""
    if yaml is None:
        return None
    try:
        resolved = Path(root).expanduser().resolve() if root else _resolve_seed_root()
        if resolved is None:
            return None
        path = (resolved / _PERSONAS_FILE).resolve()
        try:
            path.relative_to(resolved)
        except ValueError:
            return None
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("Misumi routing manifest unavailable: %s", exc, exc_info=True)
        return None
    if not isinstance(raw, Mapping):
        return None
    personas = raw.get("personas", raw)
    if not isinstance(personas, Mapping) or _FALLBACK_PERSONA not in personas:
        return None
    return personas


def resolve_auto_lead(
    prompt: str,
    personas: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Route one auto-persona request to its lead persona deterministically.

    Returns ``(persona_id, provenance)``. Provenance records the method, the
    selection, and the deterministic reasons so the choice is traceable.
    """
    if personas is None:
        personas = load_personas()
    text = str(prompt or "")
    if RESERVED.search(text):
        return _FALLBACK_PERSONA, {
            "method": _ROUTING_METHOD,
            "selected": _FALLBACK_PERSONA,
            "reasons": ["reserved:aoteru"],
        }
    best_id = _FALLBACK_PERSONA
    best_matches: list[str] = []
    if isinstance(personas, Mapping):
        for persona_id, persona in personas.items():
            routing = persona.get("routing", {}) if isinstance(persona, dict) else {}
            intents = routing.get("intents", []) if isinstance(routing, dict) else []
            matches = [
                intent for intent in intents
                if intent != "default" and isinstance(intent, str) and _keyword_present(text, intent)
            ]
            # Strict ``>`` keeps manifest order as the deterministic tie-break.
            if len(matches) > len(best_matches):
                best_id, best_matches = str(persona_id), matches
    reasons = list(best_matches) or ["fallback:aoteru"]
    return best_id, {
        "method": _ROUTING_METHOD,
        "selected": best_id,
        "reasons": reasons,
    }

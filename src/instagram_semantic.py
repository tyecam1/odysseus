"""Stage-7 semantic second opinion for Instagram Saved items the deterministic rules left neutral.

Reuses the existing routing (``estate_router.resolve_alias`` + ``execute_local``), the SourceEvent payload store and the
handoff record; it adds no scheduler, queue, store or provider.  Off by default (``ODYSSEUS_INSTAGRAM_SEMANTIC=1``).
Local inference only: the call is refused unless the resolved runtime is a local endpoint, and no text leaves the host.
Evidence for the prompt and the acceptance decision: docs/instagram-semantic-pilot-evidence-2026-10-20.md.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from src.instagram_handoff import _LATIN1_RUN, _unmojibake

logger = logging.getLogger(__name__)

ALIAS = "local-classify"
PROMPT_VERSION = "v2"
MAX_TEXT = 700
TIMEOUT_S = 60.0
DEFAULT_BATCH = 400          # at most this many inferences per run; the rest wait for the next scheduled run
DEFAULT_DOMAINS = ("misumi", "obsidian-phd")  # model-routed items are a flagged low tier ("model"); PhD evidence is thin (5 holdout leads)

SYSTEM = """You triage one saved Instagram post for two private knowledge owners. Be conservative: when unsure answer N. Reply with JSON only: {"label": "P"|"M"|"N"|"A", "useful": true|false}.
P = research lead for a PhD on industrial human-robot collaboration. Choose P only if the post itself names a concrete method, system, hardware design, paper, lab, dataset or measured result in robotics, manipulation, sensing/measurement, human factors, manufacturing/automation or research methods. NOT P: PhD-life memes, study or writing tips, motivation, AI-assistant / coding-agent / LLM tooling, finance, product ads, hype or news with no concrete method.
M = personal reference. Choose M only if the post names a specific film, series, anime, album, artist, recipe, restaurant, place, product, design idea or creative technique that could inform a recommendation. NOT M: memes, quotes, motivation, pets, fitness, relationship or mental-health posts, politics, generic travel or lifestyle hashtags, engagement bait with no named work.
N = neither. A = almost no text.
useful = true only for a specific named work, place or concrete method a reviewer would keep; false for anything generic."""


def semantic_enabled() -> bool:
    return os.getenv("ODYSSEUS_INSTAGRAM_SEMANTIC", "0") == "1" and "PYTEST_CURRENT_TEST" not in os.environ


def semantic_domains() -> tuple[str, ...]:
    raw = os.getenv("ODYSSEUS_INSTAGRAM_SEMANTIC_DOMAINS")
    names = tuple(x.strip() for x in raw.split(",") if x.strip()) if raw else DEFAULT_DOMAINS
    return tuple(x for x in names if x in ("misumi", "obsidian-phd")) or DEFAULT_DOMAINS


def semantic_batch() -> int:
    try:
        value = int(os.getenv("ODYSSEUS_INSTAGRAM_SEMANTIC_BATCH", ""))
    except ValueError:
        return DEFAULT_BATCH
    return value if value > 0 else DEFAULT_BATCH


def _repair(text: Any) -> str:
    return " ".join(_LATIN1_RUN.sub(_unmojibake, str(text or "")).split())


def build_objective(payload: dict[str, Any]) -> str:
    collections = payload.get("collections")
    names = [c.get("name") for c in collections if isinstance(c, dict)] if isinstance(collections, (list, tuple)) else []
    tags = payload.get("hashtags") if isinstance(payload.get("hashtags"), (list, tuple)) else []
    return (
        f"{SYSTEM}\n\nPost text: {_repair(payload.get('caption'))[:MAX_TEXT] or '(none)'}\n"
        f"Hashtags: {' '.join('#' + _repair(t) for t in tags[:10]) or '(none)'}\n"
        f"User's collection names: {', '.join(_repair(n) for n in names) or '(none)'}"
    )


def parse_reply(text: Any) -> Optional[dict[str, Any]]:
    match = re.search(r"\{[^{}]*\}", str(text or ""), re.S)
    if not match:
        return None
    try:
        value = json.loads(match.group())
    except ValueError:
        return None
    label = value.get("label") if isinstance(value, dict) else None
    if label not in ("P", "M", "N", "A"):
        return None
    return {"label": label, "useful": value.get("useful") is True}


def runtime() -> tuple[Optional[str], Optional[str]]:
    """(concrete model, None) when the alias resolves to a LOCAL runtime on this host, else (None, reason)."""
    from src import estate_router
    from src.model_context import is_local_endpoint

    if not is_local_endpoint(estate_router._OLLAMA_BASE):
        return None, "semantic inference refused: the model endpoint is not local"
    resolved = estate_router.resolve_alias(ALIAS, estate_router.current_host_id())
    if not resolved.get("resolved") or not resolved.get("concrete_model"):
        return None, f"alias {ALIAS} unavailable: {str(resolved.get('reason'))[:160]}"
    return str(resolved["concrete_model"]), None


def classify_semantic(payload: Any, model: str) -> Optional[dict[str, Any]]:
    """One bounded local inference; None on any failure (the row is retried on the next run, never guessed)."""
    if not isinstance(payload, dict):
        return None
    from src import estate_router

    result = estate_router.execute_local(model, build_objective(payload), timeout=TIMEOUT_S, max_retries=0, think=False)
    if not result.get("ok"):
        logger.warning("Instagram semantic call failed: %s", str(result.get("error"))[:160])
        return None
    verdict = parse_reply(result.get("output"))
    return None if verdict is None else {**verdict, "model": model, "prompt": PROMPT_VERSION}

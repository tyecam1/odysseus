"""Stage-7 semantic second opinion for Instagram Saved items the deterministic rules left neutral.

Reuses the existing routing (``estate_router.resolve_alias`` + ``execute_local``), the SourceEvent payload store and the
handoff record; it adds no scheduler, queue, store or provider.  Off by default (``ODYSSEUS_INSTAGRAM_SEMANTIC=1``).
Local inference only: the call is refused unless the resolved runtime is a local endpoint, and no text leaves the host.
Evidence for the prompt and the acceptance decision: docs/instagram-semantic-pilot-evidence-2026-10-20.md.
"""

from __future__ import annotations

import hashlib
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
MAX_TAG = 40
MAX_NAME = 60
MAX_ITEMS = 10
MAX_OBJECTIVE = 4000
TIMEOUT_S = 60.0
DEFAULT_BATCH = 400          # at most this many inferences per run; the rest wait for the next scheduled run
DEFAULT_DOMAINS = ("misumi", "obsidian-phd")  # model-routed items are a flagged low tier ("model"); PhD evidence is thin (5 holdout leads)

from src import prompt_library as _prompt_lib
SYSTEM = _prompt_lib.text("instagram/triage")


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
    objective = (
        f"{SYSTEM}\n\nPost text: {_repair(payload.get('caption'))[:MAX_TEXT] or '(none)'}\n"
        f"Hashtags: {' '.join('#' + _repair(t)[:MAX_TAG] for t in tags[:MAX_ITEMS]) or '(none)'}\n"
        f"User's collection names: {', '.join(_repair(n)[:MAX_NAME] for n in names[:MAX_ITEMS]) or '(none)'}"
    )
    return objective[:MAX_OBJECTIVE]


def objective_identity(payload: dict[str, Any]) -> str:
    """Hash of the exact model input plus the prompt version: the same identity never needs a second inference."""
    return hashlib.sha256(f"{PROMPT_VERSION}\0{build_objective(payload)}".encode("utf-8")).hexdigest()


def parse_reply(text: Any) -> Optional[dict[str, Any]]:
    """The reply must be exactly one JSON object holding only label/useful (a stripped <think> block or code fence aside)."""
    body = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.S).strip()
    body = re.sub(r"^```(?:json)?\s*|\s*```$", "", body).strip()
    try:
        value = json.loads(body)
    except ValueError:
        return None
    if not isinstance(value, dict) or not set(value) <= {"label", "useful"} or value.get("label") not in ("P", "M", "N", "A"):
        return None
    return {"label": value["label"], "useful": value.get("useful") is True}


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
        logger.warning("Instagram semantic call failed (upstream error body withheld)")      # it can echo the prompt, i.e. caption text
        return None
    verdict = parse_reply(result.get("output"))
    _prompt_lib.outcome("instagram/triage", verdict is not None)
    return None if verdict is None else {**verdict, "model": model, "prompt": PROMPT_VERSION, "identity": objective_identity(payload)}

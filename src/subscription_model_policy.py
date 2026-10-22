"""Resolve subscription Codex models from the authenticated CLI catalogue.

No static model selection or old-version fallback is allowed. The only
operator-selectable inference parameter is reasoning effort. The CLI catalogue
is a provider/account-scoped view, not proof of global release recency.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any

class SubscriptionModelError(RuntimeError):
    """A subscription model cannot be selected with sufficient evidence."""

# A minimum safety floor, NOT a model selection: prevents an old CLI/catalogue
# from silently selecting Sol 5.6 or 6.0 after 6.1 has been established.
# Newer eligible versions are always selected automatically.
_CODEX_MINIMUM_VERSION = (6, 1)
_CODEX_PREMIUM = re.compile(r"^gpt-(\d+)(?:\.(\d+))?(?:-(sol|astra))?$")
_ALLOWED_EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})

def subscription_effort() -> str:
    """The sole configurable subscription-model inference dial."""
    value = os.environ.get("AOTERU_SUBSCRIPTION_REASONING_EFFORT", "high").lower()
    if value not in _ALLOWED_EFFORTS:
        raise SubscriptionModelError(
            "invalid AOTERU_SUBSCRIPTION_REASONING_EFFORT; "
            "expected low, medium, high, xhigh, or max"
        )
    return value

def _catalogue_models(raw: str) -> list[dict[str, Any]]:
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise SubscriptionModelError("Codex model catalogue is not valid JSON") from exc
    if isinstance(doc, dict):
        models = doc.get("models")
    elif isinstance(doc, list):
        models = doc
    else:
        models = None
    if not isinstance(models, list) or not models:
        raise SubscriptionModelError("Codex model catalogue has no models")
    return [item for item in models if isinstance(item, dict)]

def resolve_latest_codex_model(codex_binary: str, *, timeout: float = 30.0) -> str:
    """Select the highest version among current *premium* subscription models.

    'codex debug models' uses Codex's authenticated model manager, including its
    provider/account-scoped refresh policy. Never use --bundled or a local static
    model table to claim current subscription availability. A catalogue that is
    stale, incomplete, or missing a known released floor fails closed.
    """
    try:
        check = subprocess.run(
            [codex_binary, "debug", "models"], capture_output=True,
            text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SubscriptionModelError("Codex authenticated catalogue unavailable") from exc
    if check.returncode:
        raise SubscriptionModelError("Codex catalogue command failed; upgrade/sign in to Codex")

    candidates = []
    for item in _catalogue_models(check.stdout):
        slug = item.get("slug") or item.get("id")
        if not isinstance(slug, str):
            continue
        match = _CODEX_PREMIUM.fullmatch(slug)
        if not match or item.get("visibility", "list") != "list":
            continue
        major, minor = int(match.group(1)), int(match.group(2) or 0)
        # Same-version Astra wins over Sol and generic GPT. No old economical tier.
        candidates.append(((major, minor, int(match.group(3) == "astra")), slug))
    if not candidates:
        raise SubscriptionModelError("no current premium Codex subscription model in authenticated catalogue")

    version, slug = max(candidates)
    if version[:2] < _CODEX_MINIMUM_VERSION:
        raise SubscriptionModelError(
            "Codex authenticated catalogue predates the known GPT-6.1 release; "
            "update Codex and verify subscription access before dispatch"
        )
    return slug

"""Read-only provider allowance windows for the estate control surface.

Only authoritative, provider-stated numeric data is reported; anything
without an accessible machine-readable source stays explicitly unknown.
No credentials, tokens or message content are ever read or returned.

Sources (2026-11-18):
- Codex: the ChatGPT-authenticated CLI's session rollouts carry
  `token_count` events with provider-stated `rate_limits` (used_percent,
  window_minutes, resets_at epoch seconds, plan_type). Numeric fields
  only; the most recent event with a non-null primary window wins.
- Claude: the official CLI (2.1.281) exposes no headless usage surface;
  subscription allowance stays unknown rather than inferred. Dispatch
  health comes from the existing provider-outcome gate.
- Z.AI: the authenticated anthropic-compatible endpoint exposes no usage
  endpoint (probed 2026-11-18: /v1/usage, /api/v1/usage, /v1/usage/limits,
  /api/promptusage, /v1/quota all 404/NOT_FOUND); allowance stays unknown.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import estate_router

SESSIONS_MAX_AGE_H = 48
MAX_SESSION_FILES = 40


def _iso(epoch: float | None) -> str | None:
    if not isinstance(epoch, (int, float)) or epoch <= 0:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def codex_windows(sessions_root: Path | None = None) -> dict:
    """Latest provider-stated rate-limit windows from Codex session rollouts."""
    root = Path(sessions_root) if sessions_root else Path.home() / ".codex" / "sessions"
    observed_at = datetime.now(timezone.utc).isoformat()
    if not root.is_dir():
        return {"remaining": "unknown", "reset": "unknown", "windows": [],
                "source": "codex-cli-session-rollouts", "confidence": "none",
                "reason": "no session rollouts found", "observed_at": observed_at}
    cutoff = time.time() - SESSIONS_MAX_AGE_H * 3600
    files = sorted((p for p in root.rglob("*.jsonl") if p.stat().st_mtime >= cutoff),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:MAX_SESSION_FILES]
    latest = None
    for path in files:
        try:
            with path.open() as handle:
                for line in handle:
                    try:
                        payload = (json.loads(line).get("payload") or {})
                    except ValueError:
                        continue
                    limits = payload.get("rate_limits") or {}
                    if payload.get("type") == "token_count" and limits.get("primary"):
                        latest = payload  # events append chronologically
        except OSError:
            continue
        if latest is not None:
            break
    if latest is None:
        return {"remaining": "unknown", "reset": "unknown", "windows": [],
                "source": "codex-cli-session-rollouts", "confidence": "none",
                "reason": "no token_count rate_limits events in recent rollouts",
                "observed_at": observed_at}
    windows = []
    for pool in ("primary", "secondary"):
        entry = (latest.get("rate_limits") or {}).get(pool) or {}
        used = entry.get("used_percent")
        if not isinstance(used, (int, float)):
            continue
        windows.append({"pool": pool,
                        "used_percent": used,
                        "remaining_percent": max(0.0, 100.0 - float(used)),
                        "window_minutes": entry.get("window_minutes"),
                        "resets_at": _iso(entry.get("resets_at"))})
    return {"remaining": "unknown" if not windows else
            min(w["remaining_percent"] for w in windows),
            "reset": "unknown" if not windows else
            min((w["resets_at"] for w in windows if w["resets_at"]), default="unknown"),
            "windows": windows, "plan_type": latest.get("plan_type"),
            "source": "codex-cli-session-rollouts", "confidence": "provider-stated",
            "observed_at": observed_at}


def claude_status() -> dict:
    observed_at = datetime.now(timezone.utc).isoformat()
    health = estate_router.provider_allows_dispatch("claude")
    return {"remaining": "unknown", "reset": "unknown", "windows": [],
            "source": "claude-cli", "confidence": "none",
            "reason": "official CLI exposes no headless usage/allowance surface",
            "dispatch_health": {"state": health.get("state"), "allowed": health.get("allowed"),
                                "retry_after": health.get("retry_after")},
            "observed_at": observed_at}


def glm_status() -> dict:
    observed_at = datetime.now(timezone.utc).isoformat()
    health = estate_router.provider_allows_dispatch("glm")
    return {"remaining": "unknown", "reset": "unknown", "windows": [],
            "source": "zai-anthropic-endpoint", "confidence": "none",
            "reason": "authenticated endpoint exposes no usage route (probed 2026-11-18)",
            "dispatch_health": {"state": health.get("state"), "allowed": health.get("allowed"),
                                "retry_after": health.get("retry_after")},
            "observed_at": observed_at}


def usage_snapshot() -> dict:
    return {"observed_at": datetime.now(timezone.utc).isoformat(),
            "providers": {"codex": codex_windows(), "claude": claude_status(),
                          "glm": glm_status()},
            "note": "provider-stated windows only; unknown means no authorised "
                    "machine-readable source, never zero"}

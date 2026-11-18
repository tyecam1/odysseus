"""Read-only provider allowance windows for the estate control surface.

Only authoritative, provider-stated numeric data is reported; anything
without an accessible machine-readable source stays explicitly unknown.
No credentials, tokens or message content are ever decoded or returned.

Sources (2026-11-18):
- Codex: the ChatGPT-authenticated CLI's session rollouts carry
  `token_count` events with provider-stated `rate_limits` (used_percent,
  window_minutes, resets_at epoch seconds, plan_type). Numeric fields
  only; the event with the newest valid EVENT timestamp wins across all
  recently-modified candidate rollouts. Discovery, per-file and total
  read sizes are bounded; raw lines are substring-prefiltered before any
  JSON decode so message records are never materialised.
- Claude: the official CLI (2.1.281) exposes no headless usage surface;
  subscription allowance stays unknown rather than inferred. Dispatch
  health comes from the existing provider-outcome gate.
- Z.AI: the authenticated anthropic-compatible endpoint exposes no usage
  endpoint (probed 2026-11-18: /v1/usage, /api/v1/usage, /v1/usage/limits,
  /api/promptusage, /v1/quota all 404/NOT_FOUND); allowance stays unknown.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from itertools import islice
from pathlib import Path

from src import estate_router

MAX_VISIT_PATHS = 500          # bounded directory traversal
MAX_CANDIDATE_FILES = 40       # newest by file mtime, discovery filter only
TAIL_BYTES_PER_FILE = 2 * 1024 * 1024   # token_count events are small; scan the tail
TOTAL_BYTES_BUDGET = 8 * 1024 * 1024
MAX_EVENT_LINE = 8192          # token_count records are tiny; never decode long lines
RESET_HORIZON_DAYS = 400


def _valid_percent(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 100.0:
        return None
    return value


def _valid_epoch(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        return None
    if value > (datetime.now(timezone.utc) + timedelta(days=RESET_HORIZON_DAYS)).timestamp():
        return None
    return value


def _iso(epoch) -> str | None:
    value = _valid_epoch(epoch)
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    except (OverflowError, ValueError, OSError):
        return None


def _event_timestamp(record) -> datetime | None:
    stamp = record.get("timestamp")
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _iter_usage_lines(path: Path, budget: list[int]):
    """Bounded tail scan; only small, substring-prefiltered lines decode."""
    size = path.stat().st_size
    take = min(size, TAIL_BYTES_PER_FILE, budget[0])
    if take <= 0:
        return
    budget[0] -= take
    with path.open("rb") as handle:
        if size > take:
            handle.seek(size - take)
            handle.readline()  # drop the partial first line
        for raw in handle:
            if len(raw) > MAX_EVENT_LINE:
                continue
            if b'"token_count"' not in raw or b'"rate_limits"' not in raw:
                continue
            try:
                record = json.loads(raw)
            except ValueError:
                continue
            if isinstance(record, dict):
                yield record


def codex_windows(sessions_root: Path | None = None) -> dict:
    """Latest provider-stated rate-limit windows from Codex session rollouts."""
    observed_at = datetime.now(timezone.utc).isoformat()
    unknown = lambda reason: {  # noqa: E731
        "remaining": "unknown", "reset": "unknown", "windows": [],
        "source": "codex-cli-session-rollouts", "confidence": "none",
        "reason": reason, "observed_at": observed_at}
    root = Path(sessions_root) if sessions_root else Path.home() / ".codex" / "sessions"
    if not root.is_dir():
        return unknown("no session rollouts found")
    cutoff = datetime.now(timezone.utc).timestamp() - 48 * 3600
    try:
        paths = list(islice((p for p in root.rglob("*.jsonl")
                             if p.stat().st_mtime >= cutoff), MAX_VISIT_PATHS))
    except OSError:
        return unknown("session rollout enumeration failed")
    if not paths:
        return unknown("no recent session rollouts found")
    paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    best = None  # (event_timestamp, payload)
    budget = [TOTAL_BYTES_BUDGET]
    for path in paths[:MAX_CANDIDATE_FILES]:
        try:
            for record in _iter_usage_lines(path, budget):
                payload = record.get("payload")
                if not isinstance(payload, dict) or payload.get("type") != "token_count":
                    continue
                limits = payload.get("rate_limits")
                if not isinstance(limits, dict) or not isinstance(limits.get("primary"), dict):
                    continue
                primary = _valid_percent((limits.get("primary") or {}).get("used_percent"))
                if primary is None:
                    continue
                stamp = _event_timestamp(record)
                if stamp is not None and (best is None or stamp > best[0]):
                    best = (stamp, payload)
        except OSError:
            continue
        if budget[0] <= 0:
            break
    if best is None:
        return unknown("no valid token_count rate_limits events in recent rollouts")
    limits = best[1].get("rate_limits") or {}
    windows = []
    for pool in ("primary", "secondary"):
        entry = limits.get(pool)
        if not isinstance(entry, dict):
            continue
        used = _valid_percent(entry.get("used_percent"))
        if used is None:
            continue
        minutes = entry.get("window_minutes")
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) \
                or not math.isfinite(minutes) or not 0 < minutes < 10 ** 6:
            minutes = None
        windows.append({"pool": pool, "used_percent": used,
                        "remaining_percent": 100.0 - used,
                        "window_minutes": minutes,
                        "resets_at": _iso(entry.get("resets_at"))})
    plan = best[1].get("plan_type")
    if not isinstance(plan, str) or not plan or len(plan) > 40:
        plan = None
    return {"remaining": "unknown" if not windows else min(w["remaining_percent"] for w in windows),
            "reset": "unknown" if not windows else
            min((w["resets_at"] for w in windows if w["resets_at"]), default="unknown"),
            "windows": windows, "plan_type": plan,
            "source": "codex-cli-session-rollouts", "confidence": "provider-stated",
            "observed_at": best[0].astimezone(timezone.utc).isoformat()}


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

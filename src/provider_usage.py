"""Read-only provider allowance windows for the estate control surface.

Only authoritative, provider-stated numeric data is reported; anything
without an accessible machine-readable source stays explicitly unknown.
No credentials, tokens or message content are ever decoded or returned:
Codex windows are extracted by bounded REGEX over raw rollout bytes —
JSON records are never parsed or materialised at all.

Sources (2026-11-18):
- Codex: the ChatGPT-authenticated CLI's session rollouts carry
  `token_count` events with provider-stated `rate_limits` (used_percent,
  window_minutes, resets_at epoch seconds, plan_type). The event with the
  newest valid EVENT timestamp wins across bounded recently-modified
  candidates; discovery, per-file and total read sizes are bounded.
- Claude: the official CLI (2.1.281) exposes no headless usage surface;
  subscription allowance stays unknown rather than inferred. Dispatch
  health comes from the existing provider-outcome gate.
- Z.AI: the authenticated anthropic-compatible endpoint exposes no usage
  endpoint (probed 2026-11-18: /v1/usage, /api/v1/usage, /v1/usage/limits,
  /api/promptusage, /v1/quota all 404/NOT_FOUND); allowance stays unknown.
"""
from __future__ import annotations

import math
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import estate_router

MAX_VISIT_ENTRIES = 500          # bounded traversal: directories AND files
MAX_CANDIDATE_FILES = 40         # newest by file mtime, discovery filter only
TAIL_BYTES_PER_FILE = 2 * 1024 * 1024   # token_count events are small; scan the tail
TOTAL_BYTES_BUDGET = 8 * 1024 * 1024
MAX_EVENT_LINE = 8192            # token_count records are tiny
RESET_HORIZON_DAYS = 400

_TS_RE = re.compile(rb'"timestamp":\s*"([^"\\]{1,64})"')
_LIMITS_RE = re.compile(rb'"rate_limits":\s*\{(.{0,800}?)\}', re.S)
_PLAN_RE = re.compile(rb'"plan_type":\s*"([^"\\]{1,40})"')
_POOL_RES = {pool: re.compile((r'"%s":\s*\{(.{0,300}?)\}' % pool).encode()) for pool in ("primary", "secondary")}
_NUM_RES = {field: re.compile((r'"%s":\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)' % field).encode())
            for field in ("used_percent", "window_minutes", "resets_at")}


def _number(blob: bytes, field: str) -> float | None:
    """Bounded regex numeric extraction; never decodes JSON, never raises."""
    match = _NUM_RES[field].search(blob)
    if match is None:
        return None
    try:
        value = float(match.group(1))
    except (OverflowError, ValueError, TypeError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _valid_percent(value) -> bool:
    return value is not None and 0.0 <= value <= 100.0


def _iso(epoch) -> str | None:
    if epoch is None or epoch <= 0:
        return None
    if epoch > (datetime.now(timezone.utc) + timedelta(days=RESET_HORIZON_DAYS)).timestamp():
        return None
    try:
        return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
    except (OverflowError, ValueError, OSError):
        return None


def _event_timestamp(raw: bytes) -> datetime | None:
    match = _TS_RE.search(raw)
    if match is None:
        return None
    try:
        stamp = match.group(1).decode("ascii", "strict")
    except UnicodeDecodeError:
        return None
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _iter_usage_lines(path: Path, budget: list[int]):
    """Bounded tail scan yielding raw lines that structurally match a
    token_count rate_limits event. No JSON decoding anywhere."""
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
            if _POOL_RES["primary"].search(raw) is None or _event_timestamp(raw) is None:
                continue
            yield raw


def _candidate_files(root: Path, cutoff: float) -> list[Path]:
    """Bounded traversal: the visit cap bounds enumeration work itself
    (directories and files), not just the filtered result."""
    visited = 0
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        visited += 1 + len(dirnames)  # entering this dir implies visiting its children
        if visited > MAX_VISIT_ENTRIES:
            return found
        for name in filenames:
            visited += 1
            if visited > MAX_VISIT_ENTRIES:
                return found
            if not name.endswith(".jsonl"):
                continue
            candidate = Path(dirpath) / name
            try:
                if candidate.stat().st_mtime >= cutoff:
                    found.append(candidate)
            except OSError:
                continue
    return found


def codex_windows(sessions_root: Path | None = None) -> dict:
    """Latest provider-stated rate-limit windows from Codex session rollouts."""
    observed_at = datetime.now(timezone.utc).isoformat()

    def unknown(reason):
        return {"remaining": "unknown", "reset": "unknown", "windows": [],
                "source": "codex-cli-session-rollouts", "confidence": "none",
                "reason": reason, "observed_at": observed_at}

    root = Path(sessions_root) if sessions_root else Path.home() / ".codex" / "sessions"
    if not root.is_dir():
        return unknown("no session rollouts found")
    cutoff = datetime.now(timezone.utc).timestamp() - 48 * 3600
    try:
        paths = _candidate_files(root, cutoff)
    except OSError:
        return unknown("session rollout enumeration failed")
    if not paths:
        return unknown("no recent session rollouts found")
    paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    best = None  # (event_timestamp, raw_line, plan_type)
    budget = [TOTAL_BYTES_BUDGET]
    for path in paths[:MAX_CANDIDATE_FILES]:
        try:
            for raw in _iter_usage_lines(path, budget):
                primary = _POOL_RES["primary"].search(raw)
                if primary is None or not _valid_percent(_number(primary.group(1), "used_percent")):
                    continue
                stamp = _event_timestamp(raw)
                if stamp is not None and (best is None or stamp > best[0]):
                    plan = _PLAN_RE.search(raw)
                    best = (stamp, raw,
                            plan.group(1).decode("ascii", "replace") if plan else None)
        except OSError:
            continue
        if budget[0] <= 0:
            break
    if best is None:
        return unknown("no valid token_count rate_limits events in recent rollouts")
    windows = []
    for pool in ("primary", "secondary"):
        blob = _POOL_RES[pool].search(best[1])
        if blob is None:
            continue
        used = _number(blob.group(1), "used_percent")
        if not _valid_percent(used):
            continue
        minutes = _number(blob.group(1), "window_minutes")
        if minutes is not None and not (0 < minutes < 10 ** 6):
            minutes = None
        windows.append({"pool": pool, "used_percent": used,
                        "remaining_percent": 100.0 - used,
                        "window_minutes": minutes,
                        "resets_at": _iso(_number(blob.group(1), "resets_at"))})
    plan = best[2] if isinstance(best[2], str) and best[2] else None
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

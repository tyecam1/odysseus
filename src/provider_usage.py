"""Read-only provider allowance windows for the estate control surface.

Only authoritative, provider-stated numeric data is reported; anything
without an accessible machine-readable source stays explicitly unknown.
No credentials, tokens or message content are ever decoded or returned.

Codex windows come from the ChatGPT-authenticated CLI's session rollouts
(`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`). No JSON record is ever
parsed: each line must match the CLI's fixed structural prefix

    {"timestamp":"<iso>","ordinal":<n>,"type":"event_msg","payload":{"type":"token_count",

before any field is read. A `token_count` payload carries only numeric usage
plus the rate_limits object, and free text (user/agent messages) lives in
other payload types that fail the prefix, so message text cannot spoof a
window. Fields are then taken only from the structurally last `rate_limits`
object on the line. The newest valid-timestamp event with a non-null primary
window wins; if THAT event fails validation the answer is unknown rather
than a fall-back to older data. Traversal is bounded by construction (only
the last three date directories, lazily scanned and capped), as are
per-file and total read sizes. A format drift yields unknown, never a guess.

Claude (official CLI 2.1.281) and Z.AI (probed 2026-11-18: /v1/usage,
/api/v1/usage, /v1/usage/limits, /api/promptusage, /v1/quota all 404) expose
no authorised machine-readable allowance source; they stay unknown, with
dispatch health from the existing provider-outcome gate reported alongside.
"""
from __future__ import annotations

import math
import os
import re
from datetime import datetime, timedelta, timezone
from itertools import islice
from pathlib import Path

from src import estate_router

DATE_DIR_DAYS = 3                 # today and the two previous days
MAX_DIR_ENTRIES = 500             # lazy scandir cap per date directory
MAX_CANDIDATE_FILES = 40          # newest by file mtime, discovery filter only
TAIL_BYTES_PER_FILE = 2 * 1024 * 1024
TOTAL_BYTES_BUDGET = 8 * 1024 * 1024
MAX_EVENT_LINE = 8192             # token_count records are tiny
RESET_HORIZON_DAYS = 400
FUTURE_SKEW = timedelta(minutes=5)

_EVENT_PREFIX = re.compile(
    rb'\{"timestamp":"([0-9T:.\-]{10,40}Z?)","ordinal":\d{1,9},'
    rb'"type":"event_msg","payload":\{"type":"token_count",')
_RATE_LIMITS = re.compile(
    rb'"rate_limits":\{[^{}]{0,300}?"primary":(null|\{[^{}]*\}),"secondary":(null|\{[^{}]*\})')
_PLAN = re.compile(rb'"plan_type":"([A-Za-z0-9_.-]{1,40})"')
_NUMBERS = {name: re.compile(rb'"%s":(-?\d{1,20}(?:\.\d{1,10})?)(?=[,}])' % name.encode())
            for name in ("used_percent", "window_minutes", "resets_at")}


def _number(blob: bytes, field: str) -> float | None:
    match = _NUMBERS[field].search(blob)
    if match is None:
        return None
    try:
        value = float(match.group(1))
    except (OverflowError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _iso(epoch: float | None) -> str | None:
    if epoch is None or epoch <= 0:
        return None
    if epoch > (datetime.now(timezone.utc) + timedelta(days=RESET_HORIZON_DAYS)).timestamp():
        return None
    try:
        return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
    except (OverflowError, ValueError, OSError):
        return None


def _parse_stamp(text: bytes) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(text.decode("ascii").replace("Z", "+00:00"))
    except (UnicodeDecodeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed > datetime.now(timezone.utc) + FUTURE_SKEW:
        return None
    return parsed


def _candidate_files(root: Path, cutoff: float) -> list[tuple[float, Path]]:
    """Last few date directories only, lazily scanned and capped, so the work
    is bounded regardless of how large the sessions tree is. The mtime is
    captured once here so later sorting never touches a vanished file."""
    today = datetime.now(timezone.utc)
    days = {(today - timedelta(days=n)).date() for n in range(DATE_DIR_DAYS)}
    days |= {(datetime.now() - timedelta(days=n)).date() for n in range(DATE_DIR_DAYS)}
    found = []
    for day in sorted(days, reverse=True):
        directory = root / ("%04d" % day.year) / ("%02d" % day.month) / ("%02d" % day.day)
        try:
            with os.scandir(directory) as entries:
                for entry in islice(entries, MAX_DIR_ENTRIES):
                    if not entry.name.endswith(".jsonl"):
                        continue
                    try:
                        mtime = entry.stat().st_mtime
                        if entry.is_file() and mtime >= cutoff:
                            found.append((mtime, Path(entry.path)))
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def _iter_events(path: Path, budget: list[int]):
    """Bounded tail scan yielding (timestamp, raw_line) for COMPLETE lines
    matching the fixed token_count prefix. Exactly one bounded read per file,
    so a concurrently appended file can never exceed the byte budgets. No JSON
    decoding."""
    size = path.stat().st_size
    take = min(size, TAIL_BYTES_PER_FILE, budget[0])
    if take <= 0:
        return
    budget[0] -= take
    with path.open("rb") as handle:
        handle.seek(size - take)
        data = handle.read(take)
    lines = data.split(b"\n")
    if size > take:
        lines = lines[1:]   # the first line is a partial tail cut
    lines = lines[:-1]      # the last element is a partial or empty trailing line
    for raw in lines:
        if len(raw) > MAX_EVENT_LINE:
            continue
        head = _EVENT_PREFIX.match(raw)
        if head is None:
            continue
        stamp = _parse_stamp(head.group(1))
        if stamp is not None:
            yield stamp, raw


def _is_candidate(raw: bytes) -> bool:
    """Does this event claim a rate-limit window? Events with no rate_limits,
    null rate_limits, or a null primary window carry no reading and are
    skipped; anything else that mentions rate_limits (including a malformed or
    duplicated key) is a candidate and, if it is the newest, makes the answer
    unknown rather than falling back to older data."""
    count = raw.count(b'"rate_limits":')
    if count == 0:
        return False
    if count > 1:
        return True  # ambiguous (duplicated key, even a nested null): never skipped
    if b'"rate_limits":null' in raw:
        return False
    index = raw.find(b'"rate_limits":{')
    if index < 0:
        return True
    limits = _RATE_LIMITS.match(raw, index)
    return limits is None or limits.group(1) != b"null"


def _read_windows(raw: bytes) -> tuple[list[dict], str | None] | None:
    """Windows from the line's single rate_limits object; None when the event
    has a duplicated key (a decoy could be mis-attributed) or no, or a
    malformed, primary window."""
    if raw.count(b'"rate_limits":') != 1:
        return None
    index = raw.find(b'"rate_limits":{')
    if index < 0:
        return None
    limits = _RATE_LIMITS.match(raw, index)
    if limits is None or limits.group(1) == b"null":
        return None
    windows = []
    for pool, blob in (("primary", limits.group(1)), ("secondary", limits.group(2))):
        if blob == b"null":
            continue
        used = _number(blob, "used_percent")
        if used is None or not 0.0 <= used <= 100.0:
            # any malformed non-null window invalidates the reading: a dropped
            # pool would silently overstate the remaining allowance
            return None
        minutes = _number(blob, "window_minutes")
        if minutes is not None and not 0 < minutes < 10 ** 6:
            minutes = None
        windows.append({"pool": pool, "used_percent": used,
                        "remaining_percent": 100.0 - used, "window_minutes": minutes,
                        "resets_at": _iso(_number(blob, "resets_at"))})
    plan = _PLAN.search(raw, limits.end())
    return windows, plan.group(1).decode("ascii") if plan else None


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
    paths = _candidate_files(root, cutoff)
    if not paths:
        return unknown("no recent session rollouts found")
    paths.sort(key=lambda item: item[0], reverse=True)
    newest = None  # (timestamp, raw) of the newest event that claims a primary window
    budget = [TOTAL_BYTES_BUDGET]
    for _mtime, path in paths[:MAX_CANDIDATE_FILES]:
        try:
            for stamp, raw in _iter_events(path, budget):
                if not _is_candidate(raw):
                    continue
                if newest is None or stamp > newest[0]:
                    newest = (stamp, raw)
        except OSError:
            continue  # vanished or unreadable between discovery and read
        if budget[0] <= 0:
            break
    if newest is None:
        return unknown("no token_count rate_limits events in recent rollouts")
    parsed = _read_windows(newest[1])
    if parsed is None or not parsed[0]:
        # The newest event is malformed or unrecognised: never fall back to
        # older data presented as current.
        return unknown("newest rate_limits event is malformed or in an unrecognised format")
    windows, plan = parsed
    return {"remaining": min(w["remaining_percent"] for w in windows),
            "reset": min((w["resets_at"] for w in windows if w["resets_at"]), default="unknown"),
            "windows": windows, "plan_type": plan,
            "source": "codex-cli-session-rollouts", "confidence": "provider-stated",
            "observed_at": newest[0].astimezone(timezone.utc).isoformat()}


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

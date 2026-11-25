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

The primary Codex source is a one-shot read of the installed CLI's own account rate-limit endpoint
(`codex app-server`, JSON-RPC over stdio, method `account/rateLimits/read`). It is an account read, not a model
turn: it bills nothing, persists nothing to disk and never touches credentials from this code. The response is
parsed strictly (integer percentages 0-100, integer epoch resets, a known window pool); any drift, error, timeout
or oversized line yields unknown. The rollout reader above stays as a labelled fallback for manual sessions.

Claude (official CLI 2.1.281) and Z.AI (probed 2026-11-18: /v1/usage,
/api/v1/usage, /v1/usage/limits, /api/promptusage, /v1/quota all 404) expose
no authorised machine-readable allowance source; they stay unknown, with
dispatch health from the existing provider-outcome gate reported alongside.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import select
import signal
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from itertools import islice
from pathlib import Path

from src import estate_router

log = logging.getLogger(__name__)

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


LIVE_TTL_SECONDS = 600            # a good reading is reused for ten minutes: `am usage` cannot hammer the CLI
LIVE_RETRY_SECONDS = 120          # a failed read is not retried sooner
LIVE_DEADLINE_SECONDS = 15
LIVE_MAX_LINE = 64 * 1024
LIVE_MAX_BYTES = 1024 * 1024
LIVE_SOURCE = "codex-app-server-rate-limits-read"
BINARY_TTL_SECONDS = 600
# The CLI's own enums (generated with `codex app-server generate-json-schema`, CLI 0.172.0). Anything else is shown
# as unknown rather than echoed, so a malformed response cannot publish an identifier through these fields.
_PLAN_TYPES = frozenset({"free", "go", "plus", "pro", "prolite", "promax", "team", "self_serve_business_prolite",
                         "self_serve_business_usage_based", "business", "ent26", "enterprise_cbp_automation",
                         "enterprise_cbp_usage_based", "enterprise", "edu", "edu_plus", "edu_pro", "sci", "sci_plus",
                         "unknown"})
_REACHED_TYPES = frozenset({"rate_limit_reached", "workspace_owner_credits_depleted",
                            "workspace_member_credits_depleted", "workspace_owner_usage_limit_reached",
                            "workspace_member_usage_limit_reached"})
_CHILD_ENV_KEYS = ("HOME", "PATH", "LANG", "LC_ALL", "CODEX_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "TMPDIR")
_live_lock = threading.Lock()
_live_cache = {"entry": None}          # one immutable (completed_at, value) pair, replaced as a whole
_binary_cache = {"at": None, "value": None}


def _live_window(pool: str, window, now: float):
    """One strictly validated window; None for an absent pool, False when the window is malformed. A non-null reset
    that is not an integer inside (0, now + horizon] invalidates the whole reading: it is never silently dropped."""
    if window is None:
        return None
    if not isinstance(window, dict):
        return False
    used, minutes, reset = window.get("usedPercent"), window.get("windowDurationMins"), window.get("resetsAt")
    if type(used) is not int or not 0 <= used <= 100:
        return False
    if minutes is not None and (type(minutes) is not int or not 0 < minutes < 10 ** 6):
        return False
    resets_at = None
    if reset is not None:
        if type(reset) is not int or not 0 < reset <= now + RESET_HORIZON_DAYS * 86400:
            return False
        resets_at = datetime.fromtimestamp(reset, tz=timezone.utc).isoformat()
    return {"pool": pool, "used_percent": float(used), "remaining_percent": 100.0 - used,
            "window_minutes": minutes, "resets_at": resets_at}


def _codex_snapshot(result):
    """The snapshot that is verifiably the Codex bucket, or None: a conflicting or unnamed bucket is never used."""
    by_id = result.get("rateLimitsByLimitId")
    if isinstance(by_id, dict) and "codex" in by_id:
        entry = by_id["codex"]
        return entry if isinstance(entry, dict) and entry.get("limitId") in (None, "codex") else None
    single = result.get("rateLimits")
    return single if isinstance(single, dict) and single.get("limitId") in (None, "codex") else None


def _live_reading(result, now: float | None = None) -> dict | None:
    """The reading for the account's Codex limit from an `account/rateLimits/read` result, or None on any drift."""
    if not isinstance(result, dict):
        return None
    snapshot = _codex_snapshot(result)
    if snapshot is None:
        return None
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    windows = []
    for pool in ("primary", "secondary"):
        window = _live_window(pool, snapshot.get(pool), now)
        if window is False:
            return None                  # a malformed window invalidates the reading: never drop a pool silently
        if window:
            windows.append(window)
    if not windows:
        return None
    plan, reached, allowed = snapshot.get("planType"), snapshot.get("rateLimitReachedType"), result.get("ordinaryUsageAllowed")
    return {"remaining": min(w["remaining_percent"] for w in windows),
            "reset": min((w["resets_at"] for w in windows if w["resets_at"]), default="unknown"),
            "windows": windows, "plan_type": plan if isinstance(plan, str) and plan in _PLAN_TYPES else None,
            "rate_limit_reached": reached if isinstance(reached, str) and reached in _REACHED_TYPES else None,
            "ordinary_usage_allowed": allowed if isinstance(allowed, bool) else None,
            "source": LIVE_SOURCE, "confidence": "provider-stated"}


def _child_env() -> dict:
    """Only what the CLI needs to find its own configured login; nothing else of this service's environment."""
    return {key: os.environ[key] for key in _CHILD_ENV_KEYS if key in os.environ}


def _live_read(binary: str) -> tuple:
    """(reading, reason). One-shot stdio session, bounded by time, frame size and total bytes. Reads are
    non-blocking on raw bytes with an explicit line buffer, so neither a stalled partial line nor a reply that
    arrives together with a notification can outlast the deadline. The process group is always killed."""
    try:
        proc = subprocess.Popen([binary, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, start_new_session=True, env=_child_env(), bufsize=0)
    except OSError:
        return None, "the Codex CLI could not be started"
    deadline, total, buffer = time.monotonic() + LIVE_DEADLINE_SECONDS, 0, b""

    def send(obj):
        proc.stdin.write((json.dumps(obj) + "\n").encode())

    def response(want):
        nonlocal total, buffer
        fd = proc.stdout.fileno()
        while True:
            while b"\n" in buffer:
                line, _, buffer = buffer.partition(b"\n")
                if len(line) > LIVE_MAX_LINE:
                    return None, "the CLI sent an oversized response"
                if time.monotonic() >= deadline:
                    return None, "no response before the deadline"
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if isinstance(message, dict) and type(message.get("id")) is int and message["id"] == want:
                    return message, None
            if len(buffer) > LIVE_MAX_LINE:
                return None, "the CLI sent an oversized response"
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None, "no response before the deadline"
            ready, _, _ = select.select([fd], [], [], min(remaining, 0.25))
            if not ready:
                continue
            try:
                chunk = os.read(fd, 65536)
            except BlockingIOError:
                continue
            if not chunk:
                return None, "the CLI closed the stream"
            total += len(chunk)
            if total > LIVE_MAX_BYTES:
                return None, "the CLI sent an oversized response"
            buffer += chunk

    try:
        fd = proc.stdout.fileno()
        os.set_blocking(fd, False)
        send({"id": 1, "method": "initialize",
              "params": {"clientInfo": {"name": "odysseus-usage-reader", "version": "1"}}})
        message, why = response(1)
        if message is None or "result" not in message:
            return None, why or "initialize was refused"
        send({"method": "initialized"})
        send({"id": 2, "method": "account/rateLimits/read", "params": {"excludeResetCreditDetails": True}})
        message, why = response(2)
        if message is None:
            return None, why
        if "result" not in message:
            return None, "the CLI refused the rate-limit read"
        reading = _live_reading(message["result"])
        return (reading, None) if reading else (None, "the rate-limit response is in an unrecognised format")
    except (OSError, ValueError) as exc:
        return None, f"the rate-limit read failed ({type(exc).__name__})"
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        for pipe in (proc.stdin, proc.stdout):
            try:
                pipe.close()
            except OSError:
                pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            log.warning("the Codex usage reader could not reap its child within 5 s")


def _resolve_binary(clock) -> tuple:
    """(path, reason). The installed CLI's location is resolved at most every BINARY_TTL_SECONDS (resolution runs
    `--version` probes), and only inside the single refresh, never once per request."""
    now = clock()
    cached = _binary_cache["value"]
    if cached is not None and _binary_cache["at"] is not None and 0 <= now - _binary_cache["at"] < BINARY_TTL_SECONDS:
        return cached
    available, found = estate_router._codex_available()
    value = (found, None) if available and found else (None, "the Codex CLI is not installed on this host")
    _binary_cache.update(at=clock(), value=value)
    return value


def codex_windows_live(binary: str | None = None, clock=time.monotonic) -> dict:
    """Provider-stated Codex windows from the CLI's own account read; unknown on any failure.

    One refresh runs at a time. A caller that arrives while another read is in flight, or inside the cache window,
    gets the last answer (a good one for ten minutes, a failure for two) or a labelled unknown: an HTTP worker
    never queues behind the subprocess. Every outcome is timestamped when it completes, the (time, value) pair is
    replaced as one object, and freshness is checked again once the refresh lock is held."""
    def unknown(reason):
        return {"remaining": "unknown", "reset": "unknown", "windows": [], "source": LIVE_SOURCE,
                "confidence": "none", "reason": reason, "observed_at": datetime.now(timezone.utc).isoformat()}

    def fresh(entry):
        if entry is None:
            return False
        at, value = entry
        return 0 <= clock() - at < (LIVE_TTL_SECONDS if value["confidence"] != "none" else LIVE_RETRY_SECONDS)

    if os.environ.get("AOTERU_CODEX_USAGE_LIVE") == "0":
        return unknown("the live Codex usage read is disabled")
    entry = _live_cache["entry"]
    if fresh(entry):
        return entry[1]
    if not _live_lock.acquire(blocking=False):
        return entry[1] if entry is not None else unknown("another usage read is in progress")
    try:
        entry = _live_cache["entry"]
        if fresh(entry):                       # another caller finished while this one was acquiring the lock
            return entry[1]
        path, why = (binary, None) if binary is not None else _resolve_binary(clock)
        if path is None:
            value = unknown(why)
        else:
            reading, reason = _live_read(path)
            value = {**reading, "observed_at": datetime.now(timezone.utc).isoformat()} if reading else unknown(reason)
        _live_cache["entry"] = (clock(), value)
        return value
    finally:
        _live_lock.release()


def codex_status() -> dict:
    """The live account read when it works, else the rollout reader, labelled with why the live read failed."""
    live = codex_windows_live()
    if live["confidence"] != "none":
        return live
    fallback = codex_windows()
    fallback["live_read"] = live.get("reason")
    return fallback


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
            "providers": {"codex": codex_status(), "claude": claude_status(),
                          "glm": glm_status()},
            "note": "provider-stated windows only; unknown means no authorised "
                    "machine-readable source, never zero"}

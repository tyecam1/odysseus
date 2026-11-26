"""Owner-attention alerts to the owner's phone, through a self-hosted ntfy server on the tailnet.

Whatever reaches the owner-oversight gate is turned into one short plain-text message: a decision or acceptance
is waiting, a run ended or paused, a provider needs the owner (login failed, quota exhausted), or the daily
heartbeat. The heartbeat is also the detector for a silently broken phone link.

This module only formats and delivers. The source of truth stays the debts, runs and provider health that
`/lazyUsage` and the router already record, and an alert never decides, approves or blocks anything.

What a message may contain is closed by construction, not by cleaning: counts, run states, provider names and
states, a run id prefix, and words taken from task titles only when each word is a short alphabetic word or a
short number. Run and pause reasons are shown only when they are a short snake_case token. Anything else is
replaced by a fixed placeholder, so a repository-supplied string can never smuggle a secret, a link, an error
text or a model output into a notification.

The channel is one private file on the lab (never in the repository, never logged) that names the server, the
topic, the publish login and the one owner whose runs and debts may be reported. The server must be a literal
tailnet address (100.64.0.0/10): no DNS lookup is ever made, proxies are ignored, redirects are refused, and
the file must be owned by this user, not a symlink, and not readable by anyone else.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import logging
import math
import os
import re
import stat
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from src import owner_decisions as od

log = logging.getLogger(__name__)

# The tests point AOTERU_ALERTS_HOME at a scratch directory, so no test can ever reach the real phone channel.
_HOME = Path(os.environ.get("AOTERU_ALERTS_HOME") or Path.home() / ".aoteru")
CHANNEL_PATH = _HOME / "ntfy_channel.json"
STATE_PATH = _HOME / "owner_alerts_sent.json"
MIN_INTERVAL_SECONDS = 600           # at most one message in ten minutes; the rest wait
DAILY_CAP = 12                       # a hard ceiling on event messages per rolling day (the heartbeat is one a day)
HEARTBEAT_SECONDS = 86400
FRESH_RUN_HOURS = 24                 # an old terminal run is history, not news
FUTURE_SKEW_SECONDS = 300
PERSIST_BACKOFF_SECONDS = 3600       # after a confirmed send whose state could not be saved
MAX_BODY = 300
MAX_EVENTS = 3
SEND_TIMEOUT_SECONDS = 5
WORKER_STALE_SECONDS = 60            # a delivery worker that has not finished by then no longer blocks the next
_LAST, _HEARTBEAT, _SEND, _ATTEMPT = "__last_sent", "__heartbeat", "__send:", "__attempt"
_TOPIC = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
_USER = re.compile(r"[A-Za-z0-9_.-]{1,40}\Z")
_OWNER = re.compile(r"[A-Za-z0-9_.@-]{1,80}\Z")
_TAILNET = ipaddress.ip_network("100.64.0.0/10")
_PROVIDER_ALERT_STATES = ("auth_failed", "quota_exhausted")
# Reasons our own runtime records when a run ends. Anything else is shown as "unspecified".
_TERMINAL_REASONS = frozenset({"max_seconds", "max_paid_calls", "max_tool_calls", "max_no_delivery_turns",
                               "max_repeat_failures", "max_tokens", "authorised_work_exhausted", "operator",
                               "operator_stop"})
_REPOS = ("odysseus", "misumi", "obsidian-phd")
_PROVIDER_NAME = re.compile(r"[a-z][a-z0-9-]{0,11}\Z")
_persist_blocked_until = 0.0


def _owned_private(info: os.stat_result) -> bool:
    return info.st_uid == os.geteuid() and not info.st_mode & (stat.S_IRWXG | stat.S_IRWXO)


def _read_channel_file(path: Path) -> tuple:
    """(status, data). The directory is opened first and checked on its descriptor; the file is opened relative
    to it without following symlinks and checked on its own descriptor, so a swapped parent or file cannot slip
    through between the check and the read."""
    try:
        dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return "no_channel", None
    except OSError:
        return "bad_channel", None
    fd = None
    try:
        if not _owned_private(os.fstat(dir_fd)):
            return "channel_not_private", None
        try:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
        except FileNotFoundError:
            return "no_channel", None
        except OSError:
            return "bad_channel", None
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            return "bad_channel", None
        if not _owned_private(info):
            return "channel_not_private", None
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            fd = None
            return "ok", json.loads(handle.read(65536))
    except (OSError, ValueError):
        return "bad_channel", None
    finally:
        if fd is not None:
            os.close(fd)
        os.close(dir_fd)


def _load_channel(path: Path) -> tuple:
    status, data = _read_channel_file(path)
    if status != "ok":
        return status, None
    if not isinstance(data, dict) or data.get("kind") != "ntfy":
        return "bad_channel", None
    base, topic, user, password, owner = (data.get(k) for k in ("base_url", "topic", "user", "password", "owner"))
    if not all(isinstance(v, str) for v in (base, topic, user, password, owner)) or not password:
        return "bad_channel", None
    if _TOPIC.match(topic) is None or _USER.match(user) is None or _OWNER.match(owner) is None:
        return "bad_channel", None
    try:
        parsed = urllib.parse.urlsplit(base)
        port = parsed.port                                  # raises on a malformed or out-of-range port
        host = ipaddress.ip_address(parsed.hostname or "")   # a literal address only: no name is ever resolved
    except ValueError:
        return "bad_channel", None
    if (parsed.scheme not in ("http", "https") or "@" in parsed.netloc or host.version != 4 or host not in _TAILNET
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment or (port is not None and port == 0)):
        return "bad_channel", None
    netloc = f"{host}:{port}" if port else str(host)
    return "ok", {"url": f"{parsed.scheme}://{netloc}/{topic}", "user": user, "password": password, "owner": owner}


def enabled_owner(channel_path: Optional[Path] = None) -> Optional[str]:
    """The one owner this channel reports on, or None when no valid channel exists (the cheap pre-check)."""
    status, channel = _load_channel(channel_path or CHANNEL_PATH)
    return channel["owner"] if status == "ok" else None


def _post(channel: dict, headers: dict, body: str, timeout: float) -> int:
    token = base64.b64encode(f"{channel['user']}:{channel['password']}".encode()).decode()
    request = urllib.request.Request(channel["url"], data=body.encode("utf-8"), method="POST",
                                     headers={**headers, "Authorization": "Basic " + token,
                                              "User-Agent": "odysseus-owner-alerts"})
    # No proxy (a proxy would receive the credential), no redirect (the pinned host must not forward the payload).
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), od._NoRedirect)
    with opener.open(request, timeout=timeout) as response:        # noqa: S310 - literal tailnet address
        return response.status


def _reason(text) -> str:
    value = str(text or "")
    return value.replace("_", " ") if value in _TERMINAL_REASONS else "unspecified"


def _repo_counts(cards) -> str:
    """Decisions counted per repository from a closed list: no task title or other repository text is shown."""
    counts = {}
    for card in cards:
        repo = str(card.get("ref") or "").partition(":")[0]
        counts[repo if repo in _REPOS else "other"] = counts.get(repo if repo in _REPOS else "other", 0) + 1
    return ", ".join(f"{name} {counts[name]}" for name in (*_REPOS, "other") if name in counts)


def _provider_name(name) -> Optional[str]:
    return name if isinstance(name, str) and _PROVIDER_NAME.match(name) else None


def _digest(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def _age_seconds(finished_at, now: datetime):
    try:
        when = datetime.fromisoformat(str(finished_at))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (now - when).total_seconds()


def build_events(owed_reviews, runs, providers, now: datetime, decisions: bool = True) -> list:
    """Owner-attention events, most urgent first. Each carries a dedupe key that changes when the situation does."""
    events = []
    for name, health in sorted((providers or {}).items()):
        health = health or {}
        shown = _provider_name(name)
        # `allowed` matters: once a retry window has passed the router admits a call again, whatever the last
        # recorded outcome was, so an old auth_failed row is not a current block.
        if shown and health.get("state") in _PROVIDER_ALERT_STATES and health.get("allowed") is False:
            stated = health.get("retry_after") and not health.get("retry_after_assumed")
            until = str(health.get("retry_after") or "")[:25] if stated else ""
            tail = f" Provider-stated retry after {until}." if re.fullmatch(r"[0-9TZ:+.-]{10,25}", until) else ""
            events.append({"key": f"provider:{shown}:{health['state']}:{_digest(health.get('retry_after'))}",
                           "priority": 4, "text": f"Provider {shown} is {health['state']}. It is blocked for dispatch.{tail}"})
    for run in runs or []:
        run_id, state = str(run.get("id") or ""), run.get("state")
        short = re.sub(r"[^0-9a-f]", "", run_id.lower())[:8]
        if not short:
            continue
        if state in ("budget_exhausted", "failed", "stopped", "completed"):
            age = _age_seconds(run.get("finished_at"), now)
            if age is None or age < -FUTURE_SKEW_SECONDS or age > FRESH_RUN_HOURS * 3600:
                continue
            counters, budgets = run.get("counters") or {}, run.get("budgets") or {}
            paid, cap = counters.get("paid_calls"), budgets.get("max_paid_calls")
            calls = f" {paid}/{cap} paid calls." if type(paid) is int and type(cap) is int else ""
            events.append({"key": f"run:{run_id}:{state}", "priority": 4 if state in ("failed", "budget_exhausted") else 3,
                           "text": f"lazyUsage run {short} ended: {state} ({_reason(run.get('terminal_reason'))}).{calls}"})
        elif state == "paused" and run.get("pause_reason") and run.get("pause_reason") != "operator":
            # The owner's own pause is not news. The runtime's pause reasons are free sentences, so none is quoted:
            # the owner reads the exact reason from `am lazy status`.
            events.append({"key": f"pause:{run_id}:{_digest(run.get('pause_reason'))}", "priority": 3,
                           "text": f"lazyUsage run {short} paused and needs a look. See am lazy status."})
    cards = od.build_cards(owed_reviews or []) if decisions else []     # the phone inbox owns decisions when it is on
    if cards:
        approvals = sum(1 for c in cards if c["gate"] == "owner_approval")
        accepts = len(cards) - approvals
        parts = ([f"{approvals} approval{'s' if approvals != 1 else ''}"] if approvals else []) + \
                ([f"{accepts} acceptance{'s' if accepts != 1 else ''}"] if accepts else [])
        events.append({"key": f"decisions:{_digest(*sorted(c['key'] for c in cards))}", "priority": 3,
                       "text": f"Needs you: {' and '.join(parts)} waiting ({_repo_counts(cards)}). "
                               "Decide from the laptop with /lazyUsage."})
    events.sort(key=lambda e: -e["priority"])
    return events


def _heartbeat_text(owed_reviews, runs, providers) -> str:
    cards = od.build_cards(owed_reviews or [])
    states = ", ".join(f"{n} {(h or {}).get('state') if (h or {}).get('state') in _KNOWN_STATES else 'unknown'}"
                       for n, h in sorted((providers or {}).items()) if _provider_name(n))
    newest = (runs or [{}])[0]
    short = re.sub(r"[^0-9a-f]", "", str(newest.get("id") or "").lower())[:8]
    state = newest.get("state") if newest.get("state") in _RUN_STATES else "unknown"
    last = f"{short} {state}" if short else "none"
    return f"Heartbeat: {len(cards)} decision{'s' if len(cards) != 1 else ''} waiting. Last run: {last}. Providers: {states or 'unknown'}."


_KNOWN_STATES = frozenset({"ok", "launching", "unknown", "quota_exhausted", "auth_failed", "rate_limited", "unreachable"})
_RUN_STATES = frozenset({"requested", "running", "paused", "stop_requested", "stopping", "completed", "stopped",
                         "failed", "budget_exhausted"})


def _compose(events: list) -> tuple:
    """(title, body, priority, shown events). Whole events only, most urgent first, within MAX_BODY."""
    shown, lines = [], []
    for event in events[:MAX_EVENTS]:
        candidate = "\n".join(lines + [event["text"]])
        if len(candidate) > MAX_BODY and shown:
            break
        lines.append(event["text"])
        shown.append(event)
    return "lazyUsage", "\n".join(lines)[:MAX_BODY], max(e["priority"] for e in shown), shown


def notify(owed_reviews, runs, providers, *, state_path: Optional[Path] = None, channel_path: Optional[Path] = None,
           post: Optional[Callable] = None, clock: Optional[Callable] = None,
           expected_owner: Optional[str] = None, inbox: bool = False) -> str:
    """Send what is new, within the cooldown and the daily cap. Returns a short status; never raises.

    `expected_owner` is the owner whose data the caller gathered. It is checked against the channel actually used
    for the send, so a channel file replaced between gathering and sending can never receive another owner's data."""
    import fcntl
    clock = clock or time.time
    state_path, channel_path, post = state_path or STATE_PATH, channel_path or CHANNEL_PATH, post or _post
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(str(state_path) + ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except Exception as exc:
        log.warning("owner alert lock failed: %s", type(exc).__name__)
        return "error"
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return "busy"
        return _notify_locked(owed_reviews, runs, providers, clock, state_path, channel_path, post, expected_owner, inbox)
    except Exception as exc:
        log.warning("owner alert failed: %s", type(exc).__name__)
        return "error"
    finally:
        os.close(lock_fd)


def _read_state(path: Path, now_ts: float) -> dict:
    """The sent-event state. Every value must be a finite timestamp that is not in the future; anything else is
    dropped, so a corrupt or poisoned file repairs itself and can never mute or break delivery."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except OSError:
        return {}
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return {}
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            fd = None
            data = json.loads(handle.read(1 << 20))
    except (OSError, ValueError):
        return {}
    finally:
        if fd is not None:
            os.close(fd)
    clean = {}
    for key, value in data.items() if isinstance(data, dict) else ():
        if not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        try:
            stamp = float(value)
        except (OverflowError, ValueError):
            continue
        if math.isfinite(stamp) and 0 <= stamp <= now_ts:       # a stamp from the future is never trusted
            clean[key] = stamp
    return clean


def _save(state_path: Path, state: dict, clock: Callable) -> bool:
    """Persist; on failure stay quiet for a while rather than resend every tick. Returns whether it was saved."""
    global _persist_blocked_until
    try:
        od._write_state(state_path, state)
        return True
    except Exception as exc:
        _persist_blocked_until = clock() + PERSIST_BACKOFF_SECONDS
        log.warning("owner alert state not saved: %s", type(exc).__name__)
        return False


def _notify_locked(owed_reviews, runs, providers, clock, state_path, channel_path, post, expected_owner, inbox=False):
    now_ts = clock()
    if now_ts < _persist_blocked_until:
        return "state_unwritable"
    status, channel = _load_channel(channel_path)
    if status != "ok":
        return status
    if expected_owner is not None and channel["owner"] != expected_owner:
        return "owner_changed"
    state = _read_state(state_path, now_ts)
    if now_ts - max(state.get(_LAST, 0.0), state.get(_ATTEMPT, 0.0)) < MIN_INTERVAL_SECONDS:
        return "cooldown"
    sent_today = sum(1 for k, v in state.items() if k.startswith(_SEND) and now_ts - v < 86400)
    now = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    fresh = [e for e in build_events(owed_reviews, runs, providers, now, decisions=not inbox) if e["key"] not in state]
    capped = bool(fresh) and sent_today >= DAILY_CAP
    if capped:
        fresh = []                              # capped events wait for tomorrow; the heartbeat can still go
    heartbeat = False
    if not fresh:
        if inbox:
            return "nothing_new"                # the inbox's daily digest replaces the heartbeat
        # quiet days only: the clock restarts at the last successful delivery of any kind
        if now_ts - max(state.get(_HEARTBEAT, 0.0), state.get(_LAST, 0.0)) < HEARTBEAT_SECONDS:
            return "daily_cap" if capped else "nothing_new"
        fresh = [{"key": None, "priority": 2, "text": _heartbeat_text(owed_reviews, runs, providers)}]
        heartbeat = True
    title, body, priority, shown = _compose(fresh)
    # Reserve the attempt in shared state BEFORE publishing: another process that takes the lock after this one
    # sees the cooldown even if this send succeeds and its final state write fails.
    state[_ATTEMPT] = now_ts
    if not _save(state_path, state, clock):
        return "state_unwritable"
    try:
        code = post(channel, {"Title": title, "Priority": str(priority), "Content-Type": "text/plain; charset=utf-8"},
                    body, SEND_TIMEOUT_SECONDS)
    except Exception as exc:                                    # never include the URL, the payload or the secret
        log.warning("owner alert send failed: %s", type(exc).__name__)
        return "send_failed"
    if not isinstance(code, int) or not 200 <= code < 300:
        log.warning("owner alert send failed: HTTP %s", code)
        return "send_failed"
    for event in shown:
        if event["key"]:
            state[event["key"]] = now_ts
    state[_LAST] = now_ts
    if heartbeat:
        state[_HEARTBEAT] = now_ts
    else:
        state[f"{_SEND}{now_ts:.3f}"] = now_ts                  # one entry per delivered event message, for the cap
    if not _save(state_path, state, clock):
        return "state_unwritable"
    return "heartbeat" if heartbeat else "sent"


# ---------------------------------------------------------------- delivery off the lifecycle tick

MAX_ABANDONED_WORKERS = 2
_worker = {"thread": None, "started": 0.0, "abandoned": []}
_worker_lock = threading.Lock()


def start_worker(job: Callable, *, clock: Callable = time.monotonic):
    """Run `job` on one background thread, never two at once, so the lifecycle tick never waits for a network
    call. A worker still alive after WORKER_STALE_SECONDS is abandoned (it is a daemon thread) and a replacement
    may start, but at most MAX_ABANDONED_WORKERS stuck workers are ever tolerated: past that nothing new starts."""
    with _worker_lock:
        current = _worker["thread"]
        if current is not None and current.is_alive():
            if clock() - _worker["started"] < WORKER_STALE_SECONDS:
                return None
            _worker["abandoned"].append(current)
            _worker["thread"] = None
        _worker["abandoned"] = [t for t in _worker["abandoned"] if t.is_alive()]
        if len(_worker["abandoned"]) >= MAX_ABANDONED_WORKERS:
            return None

        def run():
            try:
                job()
            except Exception as exc:
                log.warning("owner alert worker failed: %s", type(exc).__name__)

        thread = threading.Thread(target=run, name="owner-alerts", daemon=True)
        _worker.update(thread=thread, started=clock())
        thread.start()
        return thread

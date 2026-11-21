"""Lightweight owner-decision cards, sent to a private Discord webhook.

The few decisions that genuinely need the owner (a scope approval, an acceptance) are turned into short
cards and sent once each, so the owner can answer quickly. Nothing here blocks work: an unanswered card is
simply skipped and /lazyUsage carries on with other items.

Source of truth stays the owner debts `/lazyUsage` already records; this module only formats and delivers.
Cards carry a title, a one-line reason and the options, never a task body, an error text, a secret or a
model output. The webhook URL is a secret read from a private file on the lab (never from the repo, never
logged); only discord.com webhook URLs are accepted.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import stat
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)

CHANNEL_PATH = Path.home() / ".aoteru" / "decision_channel.json"
STATE_PATH = Path.home() / ".aoteru" / "decision_cards_sent.json"
MAX_CARDS = 3
MAX_MESSAGE = 1800
SEND_TIMEOUT_SECONDS = 5           # the send runs inside the lifecycle tick: keep it short
MIN_INTERVAL_SECONDS = 3600        # at most one message an hour; the rest wait (no bursts of cards)
_LAST = "__last_sent"
OWNER_GATES = ("owner_acceptance", "owner_approval")           # ranked: finished work first
# Open evidence on the same task that the AGENT must close before the owner is asked to accept it.
AGENT_FIRST_GATES = frozenset({"verification", "independent_review", "recovery", "finalization"})
_DUE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_WEBHOOK = re.compile(r"https://(?:discord|discordapp)\.com/api/webhooks/\d+/[A-Za-z0-9_\-]+\Z")
_STATE_KEEP = 400


def _title(debt: dict) -> str:
    slug = str(debt.get("task_id") or str(debt.get("task_ref", "")).rsplit("/", 1)[-1])
    slug = re.sub(r"\.agent-task(\.md)?$", "", slug)
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", slug)
    return re.sub(r"[^A-Za-z0-9 ._()-]+", " ", slug.replace("-", " "))[:70].strip() or "task"


def _ref_text(ref: str) -> str:
    """A task ref rendered safely: no newline, no control character, nothing that could forge a card line."""
    return re.sub(r"[^A-Za-z0-9:/._-]+", "_", str(ref))[:140]


def _task_key(ref) -> str:
    repo, _, rest = str(ref).partition(":")
    return f"{repo}:{rest.rsplit('/', 1)[-1]}"


def build_cards(owed_reviews: list) -> list:
    """Owner-gate debts -> ranked cards.

    An acceptance is only asked once nothing else is owed on that task: while verification, independent
    review or recovery is still open it is the agent's job, and asking would invite the owner to accept
    unverified work. Approvals rank by due date, then age."""
    open_agent_gates = {}
    for debt in owed_reviews or []:
        if debt.get("gate") in AGENT_FIRST_GATES and debt.get("task_ref"):
            open_agent_gates.setdefault(_task_key(debt["task_ref"]), set()).add(debt["gate"])
    cards = []
    for debt in owed_reviews or []:
        gate = debt.get("gate")
        if gate not in OWNER_GATES or not debt.get("task_ref"):
            continue
        if gate == "owner_acceptance" and open_agent_gates.get(_task_key(debt["task_ref"])):
            continue
        due = str(debt.get("due") or "")
        due = due if _DUE.match(due) else ''
        title = _title(debt)
        if gate == "owner_acceptance":
            why = "delivered and no verification or review is still owed on it; waiting for your accept or reject"
            options = "A accept | B reject | C retry"
        else:
            scope = str(debt.get("scope_sha256") or "")[:12]
            why = f"the pipeline is gated on your approval of this exact scope (digest {scope})" if scope else \
                "the pipeline is gated on your approval of this scope"
            if due:
                why += f"; due {due}"
            options = "A approve (I send the exact block) | B not now"
        key = hashlib.sha256("|".join([debt["task_ref"], gate, str(debt.get("scope_sha256") or ""),
                                       str(debt.get("execution_id") or "")]).encode()).hexdigest()[:16]
        cards.append({"key": key, "gate": gate, "ref": debt["task_ref"], "title": title, "why": why,
                      "options": options, "default": "If no reply I skip it and continue other work.",
                      "due": due, "opened_at": str(debt.get("opened_at") or "")})
    cards.sort(key=lambda c: (OWNER_GATES.index(c["gate"]), c["due"] or "9999-99-99", c["opened_at"], c["ref"]))
    return cards


def render(cards: list) -> str:
    shown, rest = cards[:MAX_CARDS], cards[MAX_CARDS:]
    lines = []
    for index, card in enumerate(shown, 1):
        verb = "Accept" if card["gate"] == "owner_acceptance" else "Approve"
        lines.append(f"Decision needed ({index}/{len(shown)}) - {verb}: {card['title']}\n"
                     f"Why now: {card['why']}\n"
                     f"Reply: {card['options']}\n"
                     f"{card['default']}\n"
                     f"ref: {_ref_text(card['ref'])}")
    if rest:
        lines.append(f"+{len(rest)} more waiting (lower priority)")
    return "\n\n".join(lines)[:MAX_MESSAGE]


def _load_channel(path: Path) -> tuple:
    """(status, url). Refuses a missing, symlinked, malformed, wrong-host or group/world-readable channel
    file, or one in a directory others can write. The file is opened once without following symlinks and its
    mode is read from the open descriptor, so the check and the read cannot be raced."""
    try:
        parent = path.parent.stat()
    except OSError:
        return "no_channel", None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return "no_channel", None
    except OSError:
        return "bad_channel", None              # a symlink (ELOOP) or an unreadable file
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            return "bad_channel", None
        if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO) or parent.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            return "channel_not_private", None
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            fd = None
            data = json.loads(handle.read())
    except (OSError, ValueError):
        return "bad_channel", None
    finally:
        if fd is not None:
            os.close(fd)
    url = data.get("url") if isinstance(data, dict) and data.get("kind") == "discord" else None
    if not isinstance(url, str) or _WEBHOOK.match(url) is None:
        return "bad_channel", None
    return "ok", url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """The pinned discord.com host must not be able to bounce the payload to another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def _post(url: str, payload: dict, timeout: float) -> int:
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "User-Agent": "odysseus-decisions"})
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(request, timeout=timeout) as response:                     # noqa: S310 - host pinned by _WEBHOOK
        return response.status


def _read_state(path: Path) -> dict:
    """Sent-card state; anything that is not a number is dropped so a corrupt file repairs itself."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: float(v) for k, v in data.items()
            if isinstance(k, str) and isinstance(v, (int, float)) and not isinstance(v, bool)}


def _write_state(path: Path, state: dict) -> None:
    """Atomic (temp file in the same directory, then replace), so a crash never leaves truncated JSON."""
    keep = dict(sorted(state.items(), key=lambda kv: kv[1])[-_STATE_KEEP:])
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(keep))
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def notify(owed_reviews: list, *, state_path: Optional[Path] = None, channel_path: Optional[Path] = None,
           post: Optional[Callable] = None, clock: Optional[Callable] = None,
           min_interval: float = MIN_INTERVAL_SECONDS) -> str:
    """Send the cards not yet sent. Returns a short status; never raises."""
    import time
    now = (clock or time.time)()
    state_path, channel_path, post = state_path or STATE_PATH, channel_path or CHANNEL_PATH, post or _post
    try:
        cards = build_cards(owed_reviews)
        status, url = _load_channel(channel_path)
        if status != "ok":
            return status
        state = _read_state(state_path)
        fresh = [c for c in cards if c["key"] not in state]
        if not fresh:
            return "nothing_new"
        if now - float(state.get(_LAST, 0) or 0) < min_interval:
            return "cooldown"
        try:
            code = post(url, {"content": render(fresh), "allowed_mentions": {"parse": []}}, SEND_TIMEOUT_SECONDS)
        except Exception as exc:                                         # never include the URL or the payload
            log.warning("decision card send failed: %s", type(exc).__name__)
            return "send_failed"
        if not isinstance(code, int) or not 200 <= code < 300:
            log.warning("decision card send failed: HTTP %s", code)
            return "send_failed"
        for card in fresh[:MAX_CARDS]:
            state[card["key"]] = now
        state[_LAST] = now
        _write_state(state_path, state)
        return "sent"
    except Exception as exc:
        log.warning("decision notify failed: %s", type(exc).__name__)
        return "error"

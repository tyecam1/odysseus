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
        # Any debt on the task that is not an owner gate is the agent's to close first, including a legacy
        # debt recorded before gates existed (no `gate`, usually an `error`).
        if debt.get("gate") not in OWNER_GATES and debt.get("task_ref"):
            open_agent_gates.setdefault(_task_key(debt["task_ref"]), set()).add(str(debt.get("gate") or "legacy"))
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
            scope = (_HEX.match(str(debt.get("scope_sha256") or "")) or [""])[0][:12]
            why = f"the pipeline is gated on your approval of this exact scope (digest {scope})" if scope else \
                "the pipeline is gated on your approval of this scope"
            if due:
                why += f"; due {due}"
            options = "A approve (I send the exact block) | B not now"
        key = hashlib.sha256("|".join([debt["task_ref"], gate, str(debt.get("scope_sha256") or ""),
                                       str(debt.get("execution_id") or "")]).encode()).hexdigest()[:16]
        cards.append({"key": key, "gate": gate, "ref": debt["task_ref"], "title": title, "why": why,
                      "debt": debt, "commit_sha": debt.get("commit_sha"), "author_provider": debt.get("author_provider"),
                      "scope_digest": (_HEX.match(str(debt.get("scope_sha256") or "")) or [""])[0][:12],
                      "options": options, "default": "If no reply I skip it and continue other work.",
                      "due": due, "opened_at": str(debt.get("opened_at") or "")})
    cards.sort(key=lambda c: (OWNER_GATES.index(c["gate"]), c["due"] or "9999-99-99", c["opened_at"], c["ref"]))
    return cards


_URL = re.compile(r"(?:https?://\S+|\S*discord(?:app)?\.com/api/webhooks\S*)", re.I)
_TOKEN = re.compile(r"[A-Za-z0-9_-]{40,}")
_MARKDOWN = re.compile(r"[`*_~|>#\[\]]")
_HEX = re.compile(r"[0-9a-f]+")


def _redact_tokens(text: str) -> str:
    """A long mixed-case-and-digit run is a secret-shaped string (a webhook token): never echo it."""
    def one(match):
        run = match.group(0)
        shaped = (any(c.islower() for c in run) and any(c.isupper() for c in run) and any(c.isdigit() for c in run)
                  and run.count("-") < 3)
        return "[redacted]" if shaped else run
    return _TOKEN.sub(one, text)


_MARKDOWN_PATH = re.compile(r"[`~|>#\[\]]")


def _clean(value, limit: int, path: bool = False) -> str:
    """Text safe for a chat card: printable ASCII only, one line, no link (no preview), no mention, bounded."""
    text = _URL.sub("[link]", str(value or ""))
    text = re.sub(r"[^\x20-\x7e]", " ", text).replace("@", "at ")
    # card text never carries Discord formatting or a secret; a path keeps its glob and underscores because it is
    # shown inside a code span, where they are literal
    text = _redact_tokens((_MARKDOWN_PATH if path else _MARKDOWN).sub(" ", text))
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _paths(values, shown: int = 3, each: int = 70) -> str:
    items = [_clean(v, each, path=True) for v in (values or []) if str(v or "").strip()]
    items = [i for i in items if i]
    if not items:
        return ""
    text = ", ".join(f"`{i}`" for i in items[:shown])
    return text + (f" (+{len(items) - shown} more)" if len(items) > shown else "")


def _rich_block(index: int, count: int, card: dict, ctx: dict) -> str:
    """One decision: what it is, what each answer does, what it binds. Only allow-listed fields, each bounded."""
    accept = card["gate"] == "owner_acceptance"
    verb = "Accept" if accept else "Approve"
    title = _clean(ctx.get("title"), 110) or card["title"]
    lines = [f"Decision needed ({index}/{count}) - {verb}: {title}"]
    what = _clean(ctx.get("what"), 200)
    if what:
        lines.append(f"What: {what}")
    facts = [_clean(ctx.get("kind"), 60)]
    for label, key in (("priority", "priority"), ("risk", "risk")):
        if _clean(ctx.get(key), 20):
            facts.append(f"{label} {_clean(ctx.get(key), 20)}")
    if card.get("due"):
        facts.append(f"due {card['due']}")
    facts = [f for f in facts if f]
    if facts:
        lines.append("Type: " + "; ".join(facts) + ".")
    if accept:
        sha = _clean(card.get("commit_sha"), 40)[:8]
        author = _clean(card.get("author_provider"), 20)
        delivered = f"commit {sha}" if sha else "a delivery"
        lines.append(f"Delivered: {delivered}{' by ' + author if author else ''}. Nothing else is owed on it: "
                     "verification and review are closed.")
        result = _clean(ctx.get("result_path"), 110)
        extra = ctx.get("outputs_count")
        if result:
            more = f" and {extra - 1} other output{'s' if extra - 1 != 1 else ''}" if isinstance(extra, int) and extra > 1 else ""
            lines.append(f"Review: {result}{more}.")
        lines.append("If you accept: reply A and I record it on the owner card, so the task closes as delivered. "
                     "If you reject or ask for a retry, it is not closed as delivered.")
    else:
        paths = _paths(ctx.get("write_paths"))
        denied = ctx.get("denied_count")
        limit = (f"; {denied} protected paths and the owner task cards stay off limits"
                 if isinstance(denied, int) and denied >= 0 else "; the owner task cards stay off limits")
        if paths:
            lines.append(f"If you approve: it may write only under {paths}" + limit
                         + ". Its result is unaccepted until you accept it.")
        else:
            lines.append("If you approve: nothing can be written yet, because the card names no writable path"
                         + limit + ". It would need a scope first.")
        lines.append("If you decline: it stays blocked and other work continues.")
        digest = _clean(card.get("scope_digest"), 12)
        if digest:
            lines.append(f"Binds scope {digest}; any scope change voids it.")
        if ctx.get("scope_changed"):
            lines.append("Note: the card's scope changed after this request, so approving needs a new digest.")
    lines.append(f"Reply: {card['options']}")
    return "\n".join(lines)


def _plain_block(index: int, count: int, card: dict) -> str:
    verb = "Accept" if card["gate"] == "owner_acceptance" else "Approve"
    return (f"Decision needed ({index}/{count}) - {verb}: {card['title']}\n"
            f"Why now: {card['why']}\n"
            f"Reply: {card['options']}\n"
            f"{card['default']}")


def _context_for(card: dict, context) -> dict:
    try:
        return context(card.get("debt") or {}) or {}
    except Exception:                                       # a failing context never breaks the tick
        return {}


def render_shown(cards: list, context=None) -> tuple:
    """(message, the cards actually shown). With a context function every shown card is rich; a card whose card
    cannot be read is held back for a later tick rather than sent plain (a plain send would be recorded as sent
    and suppress the rich version). Shows as many of the top cards as fit one message."""
    pool = cards[:MAX_CARDS]
    contexts = {}
    if context is not None:
        for card in pool:                                   # one read per card, never repeated while fitting
            contexts[card["key"]] = _context_for(card, context)
        pool = [card for card in pool if contexts[card["key"]]]
    for count in range(len(pool), 0, -1):
        shown = pool[:count]
        rest = len(cards) - count
        blocks = [(_rich_block(i, count, card, contexts[card["key"]]) if context is not None
                   else _plain_block(i, count, card)) for i, card in enumerate(shown, 1)]
        if rest:
            blocks.append(f"+{rest} more waiting (lower priority)")
        text = "\n\n".join(blocks)
        if len(text) <= MAX_MESSAGE or count == 1:
            return text[:MAX_MESSAGE], shown
    return "", []


def render(cards: list, context=None) -> str:
    return render_shown(cards, context)[0]


def _load_channel(path: Path) -> tuple:
    """(status, url). Refuses a missing, symlinked, malformed, wrong-host or group/world-readable channel
    file, or one in a directory others can write. The file is opened once without following symlinks and its
    mode is read from the open descriptor, so the check and the read cannot be raced."""
    try:
        parent = path.parent.stat()
    except OSError:
        return "no_channel", None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
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
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return {}
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return {}                                      # a FIFO or device must never block the tick
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            fd = None
            data = json.loads(handle.read())
    except (OSError, ValueError):
        return {}
    finally:
        if fd is not None:
            os.close(fd)
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
           min_interval: float = MIN_INTERVAL_SECONDS, context: Optional[Callable] = None) -> str:
    """Send the cards not yet sent. Returns a short status; never raises."""
    import fcntl
    import time
    now = (clock or time.time)()
    state_path, channel_path, post = state_path or STATE_PATH, channel_path or CHANNEL_PATH, post or _post
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(str(state_path) + ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except Exception as exc:
        log.warning("decision notify lock failed: %s", type(exc).__name__)
        return "error"
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)   # read state, send and record under one lock
        except BlockingIOError:
            return "busy"                            # another sender is mid-call: never stall the lifecycle tick
        return _notify_locked(owed_reviews, now, state_path, channel_path, post, min_interval, context)
    except Exception as exc:
        log.warning("decision notify failed: %s", type(exc).__name__)
        return "error"
    finally:
        os.close(lock_fd)                            # closing the descriptor releases the lock


def _notify_locked(owed_reviews, now, state_path, channel_path, post, min_interval, context=None):
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
            text, shown = render_shown(fresh, context)
            if not shown:
                return "deferred"                           # nothing readable to show yet: try again next tick
            code = post(url, {"content": text, "allowed_mentions": {"parse": []}}, SEND_TIMEOUT_SECONDS)
        except Exception as exc:                                         # never include the URL or the payload
            log.warning("decision card send failed: %s", type(exc).__name__)
            return "send_failed"
        if not isinstance(code, int) or not 200 <= code < 300:
            log.warning("decision card send failed: HTTP %s", code)
            return "send_failed"
        for card in shown:
            state[card["key"]] = now
        state[_LAST] = now
        _write_state(state_path, state)
        return "sent"
    except Exception as exc:
        log.warning("decision notify failed: %s", type(exc).__name__)
        return "error"

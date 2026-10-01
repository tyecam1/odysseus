"""Durable, owner-scoped Misumi transcript runtime (service layer).

Ambient and push-to-talk speech becomes durable *text* here before any wake or
intent routing. This module is deliberately small and database-only: it owns the
idempotent write, bounded query/export, the finite-retention purge and the
credential re-filter. It does not own speech-to-text placement (routes) and it
is not a semantic-memory store: transcript rows are operational history and are
never auto-promoted to memory capsules or committed to Git.

Invariants enforced here rather than documented and hoped for:

* ``(owner, domain, event_id)`` is unique, so a retry after an ambiguous timeout
  returns the existing row instead of creating a second one. The unique
  constraint, not a read-then-write check, is the arbiter of concurrent inserts.
* The owner is stored NOT NULL (``""`` for the local/no-auth owner) so SQLite's
  "NULLs are distinct" behaviour cannot defeat the unique constraint.
* A row is only reported persisted after the transaction commits.
* Retention is finite: ``transcript_retention_days`` is clamped to 1..90 and
  expired rows are purged in bounded batches.
* Credential-shaped text is refused before storage (defence in depth: the
  interface box applies the same rule before it forwards anything).
* Raw audio is never stored by this module.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from core.database import MisumiRetentionPolicy, TranscriptEvent, utcnow_naive

logger = logging.getLogger(__name__)

OWNER_LOCAL = ""
DEFAULT_DOMAIN = "misumi"
MAX_TEXT_CHARS = 8000
MAX_EVENT_ID_CHARS = 128
RETENTION_DEFAULT_DAYS = 14
RETENTION_MIN_DAYS = 1
RETENTION_MAX_DAYS = 90
QUERY_DEFAULT_LIMIT = 50
QUERY_MAX_LIMIT = 200
EXPORT_MAX_LIMIT = 1000
PURGE_BATCH = 200
CAPTURE_MODES = ("ambient", "ptt")
_EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-]*$")

# Ported unchanged from the deployed interface box's ratified ambient capture
# (2026-07-20). Deliberately blunt: a window that merely talks about a password
# is dropped along with one that contains it.
CREDENTIAL_PATTERNS = (
    re.compile(
        r"\b(?:pass(?:word|phrase|code)s?|api[\s-]*keys?|secret[\s-]*keys?|"
        r"access[\s-]*(?:keys?|tokens?)|auth(?:orisation|orization)?[\s-]*tokens?|"
        r"bearer[\s-]*tokens?|private[\s-]*keys?|security[\s-]*codes?|"
        r"pin[\s-]*(?:numbers?|codes?)|one[\s-]*time[\s-]*(?:codes?|passwords?)|"
        r"two[\s-]*factor|2fa|otp|seed[\s-]*phrases?|"
        r"recovery[\s-]*(?:codes?|phrases?)|credit[\s-]*card|card[\s-]*numbers?|"
        r"cvv|sort[\s-]*code|account[\s-]*numbers?|national[\s-]*insurance)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:sk|pk|rk|ghp|gho|ghs|ghu|xox[baprs])[-_][A-Za-z0-9_-]{12,}"),
    re.compile(r"-----BEGIN\s+\S*\s*PRIVATE KEY-----"),
    re.compile(r"\b[A-Fa-f0-9]{32,}\b"),
    re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/-]{8,}", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}"),
    re.compile(r"(?:\b\d[ -]?){13,19}\b"),
    # Added after retrospective review: ordinary household phrasing the ported box
    # patterns miss. "wifi key is abcd1234", "the door code is 4821". Still a blunt
    # filter and not a guarantee: spelled-out digits and indirect references are
    # not caught, so ambient retention stays finite and the box filters first.
    re.compile(r"\b(?:wi[\s-]*fi|wifi|network|router)\b[^.\n]{0,24}\b(?:key|code|pass\w*)\b", re.IGNORECASE),
    re.compile(r"\b(?:key|code|pin|passcode|pass)\s+(?:is|was|=|:)\s*\S*\d\S*", re.IGNORECASE),
)


class TranscriptError(Exception):
    """Base class; ``code`` is the stable machine-readable reason."""

    code = "transcript_error"
    status_code = 400


class TranscriptInvalid(TranscriptError):
    code = "invalid_event"
    status_code = 422


class ArchiveDisabled(TranscriptError):
    """The owner's transcript archive is off: nothing was stored, nothing is 'saved'."""

    code = "archive_disabled"
    status_code = 409


class CredentialFiltered(TranscriptError):
    """Credential-shaped text was refused before storage (a final, non-retryable outcome)."""

    code = "credential_filtered"
    status_code = 200


class EventConflict(TranscriptError):
    """The same event_id already exists with different text; never silently overwritten."""

    code = "event_id_conflict"
    status_code = 409


class EventNotFound(TranscriptError):
    code = "event_not_found"
    status_code = 404


@dataclass
class IngestResult:
    event: TranscriptEvent
    deduplicated: bool


def normalize_owner(owner: Optional[str]) -> str:
    return (owner or OWNER_LOCAL).strip()


def looks_credential_shaped(text: str) -> bool:
    return any(pattern.search(text) for pattern in CREDENTIAL_PATTERNS)


def _text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clamp_retention_days(days: object) -> int:
    try:
        value = int(days)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return RETENTION_DEFAULT_DAYS
    return max(RETENTION_MIN_DAYS, min(value, RETENTION_MAX_DAYS))


def _as_naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def parse_timestamp(value: object) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp (``Z`` accepted) to naive UTC; None if absent/invalid."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _as_naive_utc(value)
    text = str(value).strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        return _as_naive_utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _commit(db) -> None:
    """Single commit seam: durability is only claimed after this returns."""
    db.commit()


# ---- policy -----------------------------------------------------------------

def policy_dict(row: Optional[MisumiRetentionPolicy]) -> dict:
    return {
        "transcript_archive": bool(row.transcript_archive) if row else False,
        "transcript_retention_days": clamp_retention_days(
            row.transcript_retention_days if row else RETENTION_DEFAULT_DAYS
        ),
        # Raw audio is never retained server-side; this is reported, not settable.
        "raw_audio_retention": "off",
        # The other retention dimensions are enforced per request, not here.
        "request_level": {
            "conversation_history": "history_mode on /misumi/respond",
            "semantic_promotion": "retention_mode on /misumi/respond",
            "artifact_creation": "retention_mode on /misumi/respond",
        },
    }


def get_policy(db, owner: Optional[str]) -> dict:
    row = db.get(MisumiRetentionPolicy, normalize_owner(owner))
    return policy_dict(row)


def set_policy(
    db,
    owner: Optional[str],
    *,
    transcript_archive: Optional[bool] = None,
    transcript_retention_days: Optional[int] = None,
) -> dict:
    key = normalize_owner(owner)
    row = db.get(MisumiRetentionPolicy, key)
    if row is None:
        row = MisumiRetentionPolicy(
            owner=key,
            transcript_archive=False,
            transcript_retention_days=RETENTION_DEFAULT_DAYS,
            raw_audio_retention="off",
        )
        db.add(row)
    if transcript_archive is not None:
        row.transcript_archive = bool(transcript_archive)
    if transcript_retention_days is not None:
        row.transcript_retention_days = clamp_retention_days(transcript_retention_days)
    _commit(db)
    return policy_dict(row)


# ---- ingest -----------------------------------------------------------------

def _validate(event_id: str, text: str, capture_mode: str) -> tuple[str, str]:
    event_id = (event_id or "").strip()
    if not event_id or len(event_id) > MAX_EVENT_ID_CHARS or not _EVENT_ID_RE.match(event_id):
        raise TranscriptInvalid("event_id must be 1-128 chars of [A-Za-z0-9._:-]")
    text = (text or "").strip()
    if not text:
        raise TranscriptInvalid("empty transcript text")
    if len(text) > MAX_TEXT_CHARS:
        raise TranscriptInvalid(f"transcript text exceeds {MAX_TEXT_CHARS} characters")
    if capture_mode not in CAPTURE_MODES:
        raise TranscriptInvalid("capture_mode must be 'ambient' or 'ptt'")
    return event_id, text


def retention_cutoff(db, owner: Optional[str], now: Optional[datetime] = None) -> datetime:
    """Rows persisted before this instant are expired for this owner."""
    days = get_policy(db, owner)["transcript_retention_days"]
    return (now or utcnow_naive()) - timedelta(days=days)


def find_event(db, owner: Optional[str], domain: str, event_id: str, *,
               live_only: bool = True) -> Optional[TranscriptEvent]:
    """Owner-scoped lookup. By default an expired-but-not-yet-purged row is treated
    as absent, so retention holds even if nothing has triggered a purge."""
    stmt = select(TranscriptEvent).where(
        TranscriptEvent.owner == normalize_owner(owner),
        TranscriptEvent.domain == domain,
        TranscriptEvent.event_id == event_id,
    )
    if live_only:
        stmt = stmt.where(TranscriptEvent.persisted_at >= retention_cutoff(db, owner))
    return db.execute(stmt).scalar_one_or_none()


def lookup_existing(db, owner, domain, event_id) -> Optional[TranscriptEvent]:
    """Pre-check used by the audio path so a retry skips STT entirely."""
    return find_event(db, owner, domain, (event_id or "").strip())


def ingest_event(
    db,
    *,
    owner: Optional[str],
    domain: str = DEFAULT_DOMAIN,
    event_id: str,
    text: str,
    capture_mode: str = "ambient",
    source: str = "text-event",
    capture_started_at: Optional[datetime] = None,
    capture_ended_at: Optional[datetime] = None,
    persona: Optional[str] = None,
    stt_provider: Optional[str] = None,
    stt_model: Optional[str] = None,
    stt_host: Optional[str] = None,
    stt_latency_ms: Optional[int] = None,
    now: Optional[datetime] = None,
) -> IngestResult:
    """Persist one transcript event exactly once. Raises a TranscriptError subclass
    for every outcome that is not "a durable row now exists"."""
    event_id, text = _validate(event_id, text, capture_mode)
    owner_key = normalize_owner(owner)
    digest = _text_sha(text)

    # Drop anything already expired first, so an expired row can never be reported
    # as "already saved" and the unique key is free to be reused.
    try:
        purge_expired(db, owner_key, max_batches=2)
    except Exception:
        db.rollback()
        logger.warning("transcript pre-ingest purge failed", exc_info=True)

    # A retry of something already stored is reported truthfully even if the
    # archive has since been switched off: the row exists.
    existing = find_event(db, owner_key, domain, event_id)
    if existing is not None:
        if existing.text_sha256 != digest:
            raise EventConflict("event_id already stored with different text")
        return IngestResult(existing, True)

    if not get_policy(db, owner_key)["transcript_archive"]:
        raise ArchiveDisabled("transcript archive is disabled for this owner")
    if looks_credential_shaped(text):
        raise CredentialFiltered("credential-shaped text refused before storage")

    stamp = now or utcnow_naive()
    event = TranscriptEvent(
        owner=owner_key,
        domain=domain,
        event_id=event_id,
        text=text,
        text_sha256=digest,
        capture_mode=capture_mode,
        source=(source or "text-event")[:48],
        capture_started_at=_as_naive_utc(capture_started_at),
        capture_ended_at=_as_naive_utc(capture_ended_at),
        persisted_at=stamp,
        stt_provider=stt_provider,
        stt_model=stt_model,
        stt_host=stt_host,
        stt_latency_ms=stt_latency_ms,
        persona=(persona or None),
        state="persisted",
    )
    db.add(event)
    try:
        _commit(db)
    except IntegrityError:
        # Lost a race against a concurrent insert of the same key: the unique
        # constraint arbitrated. Return what the winner wrote.
        db.rollback()
        winner = find_event(db, owner_key, domain, event_id, live_only=False)
        if winner is None:
            raise
        if winner.text_sha256 != digest:
            raise EventConflict("event_id already stored with different text")
        return IngestResult(winner, True)
    except Exception:
        db.rollback()
        raise

    try:
        purge_expired(db, owner_key, now=stamp, max_batches=2)
    except Exception:  # retention housekeeping must never turn a saved row into a failure
        db.rollback()
        logger.warning("transcript retention purge failed", exc_info=True)
    return IngestResult(event, False)


# ---- retention --------------------------------------------------------------

def purge_expired(db, owner: Optional[str], *, now: Optional[datetime] = None,
                  batch: int = PURGE_BATCH, max_batches: int = 1) -> int:
    """Delete this owner's expired rows in bounded batches (at most ``max_batches``
    of ``batch`` rows), so a large backlog drains over a few calls instead of one
    unbounded delete. Returns the number of rows removed."""
    owner_key = normalize_owner(owner)
    cutoff = retention_cutoff(db, owner_key, now)
    removed = 0
    for _ in range(max(1, max_batches)):
        seqs = [
            row[0]
            for row in db.execute(
                select(TranscriptEvent.seq)
                .where(TranscriptEvent.owner == owner_key, TranscriptEvent.persisted_at < cutoff)
                .order_by(TranscriptEvent.seq)
                .limit(batch)
            ).all()
        ]
        if not seqs:
            break
        db.execute(delete(TranscriptEvent).where(TranscriptEvent.seq.in_(seqs)))
        _commit(db)
        removed += len(seqs)
    return removed

# ---- query / export ---------------------------------------------------------

def event_dict(event: TranscriptEvent) -> dict:
    def iso(value):
        return value.replace(microsecond=0).isoformat() + "Z" if value else None

    wake = None
    if event.wake_result:
        try:
            wake = json.loads(event.wake_result)
        except ValueError:
            wake = None
    return {
        "event_id": event.event_id,
        "seq": event.seq,
        "domain": event.domain,
        "text": event.text,
        "capture_mode": event.capture_mode,
        "source": event.source,
        "capture_started_at": iso(event.capture_started_at),
        "capture_ended_at": iso(event.capture_ended_at),
        "persisted_at": iso(event.persisted_at),
        "stt": {
            "provider": event.stt_provider,
            "model": event.stt_model,
            "host": event.stt_host,
            "latency_ms": event.stt_latency_ms,
        },
        "persona": event.persona,
        "wake": wake,
        "session_id": event.session_id,
        "response_request_id": event.response_request_id,
        "state": event.state,
    }


def query_events(
    db,
    owner: Optional[str],
    domain: str = DEFAULT_DOMAIN,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    after_seq: Optional[int] = None,
    before_seq: Optional[int] = None,
    limit: int = QUERY_DEFAULT_LIMIT,
    newest_first: bool = True,
) -> dict:
    """Owner-scoped, keyset-paginated, hard-bounded read. Never returns unbounded history."""
    limit = max(1, min(int(limit), QUERY_MAX_LIMIT))
    owner_key = normalize_owner(owner)
    stmt = select(TranscriptEvent).where(
        TranscriptEvent.owner == owner_key,
        TranscriptEvent.domain == domain,
        # Retention is enforced on read, not only by the purge: expired rows are
        # never returned even if no ingest has run since the window moved.
        TranscriptEvent.persisted_at >= retention_cutoff(db, owner_key),
    )
    since_n, until_n = _as_naive_utc(since), _as_naive_utc(until)
    if since_n is not None:
        stmt = stmt.where(TranscriptEvent.persisted_at >= since_n)
    if until_n is not None:
        stmt = stmt.where(TranscriptEvent.persisted_at < until_n)
    if after_seq is not None:
        stmt = stmt.where(TranscriptEvent.seq > int(after_seq))
    if before_seq is not None:
        stmt = stmt.where(TranscriptEvent.seq < int(before_seq))
    stmt = stmt.order_by(TranscriptEvent.seq.desc() if newest_first else TranscriptEvent.seq.asc())
    rows = db.execute(stmt.limit(limit + 1)).scalars().all()
    more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1].seq if (rows and more) else None
    return {
        "events": [event_dict(row) for row in rows],
        "limit": limit,
        "next_cursor": next_cursor,
        "newest_first": newest_first,
        "retention_days": get_policy(db, owner_key)["transcript_retention_days"],
    }


def export_events(
    db,
    owner: Optional[str],
    domain: str = DEFAULT_DOMAIN,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = EXPORT_MAX_LIMIT,
    fmt: str = "jsonl",
) -> str:
    """Stable, bounded export (oldest first) for the caller's own rows only."""
    limit = max(1, min(int(limit), EXPORT_MAX_LIMIT))
    page = query_events(
        db, owner, domain, since=since, until=until, limit=limit, newest_first=False
    )
    events = page["events"]
    if fmt == "md":
        lines = ["# Misumi transcript export", ""]
        for item in events:
            lines.append(f"- {item['persisted_at']} [{item['capture_mode']}] {item['text']}")
        return "\n".join(lines) + "\n"
    return "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in events)


# ---- wake / linkage ---------------------------------------------------------

def attach_wake(
    db,
    owner: Optional[str],
    domain: str,
    event_id: str,
    *,
    matched: bool,
    intent: Optional[str] = None,
    session_id: Optional[str] = None,
    response_request_id: Optional[str] = None,
) -> TranscriptEvent:
    """Attach the wake/intent decision AFTER persistence (idempotent update)."""
    event = find_event(db, owner, domain, (event_id or "").strip())
    if event is None:
        raise EventNotFound("transcript event not found")
    event.wake_result = json.dumps({"matched": bool(matched), "intent": intent}, sort_keys=True)
    event.wake_recorded_at = utcnow_naive()
    if session_id is not None:
        event.session_id = session_id
    if response_request_id is not None:
        event.response_request_id = response_request_id
    _commit(db)
    return event


# ---- importer for the interface box's day files ------------------------------

def derive_box_event_id(box_id: str, record: dict) -> str:
    """Deterministic id for box records, which carry none: re-importing the same
    day file can never create a second row."""
    basis = "|".join(
        str(part)
        for part in (
            box_id,
            record.get("at", ""),
            record.get("source", ""),
            record.get("persona", ""),
            record.get("duration_s", ""),
            record.get("text", ""),
        )
    )
    return "box-" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:40]


def import_box_lines(
    db,
    *,
    owner: Optional[str],
    lines: Iterable[str],
    domain: str = DEFAULT_DOMAIN,
    box_id: str = "interface-box",
    now: Optional[datetime] = None,
) -> dict:
    """Import ``ambient-YYYY-MM-DD.jsonl`` lines idempotently.

    Records older than the owner's retention window are skipped and counted, so
    an old day file cannot resurrect text that retention would already have
    removed. Credential-shaped lines are refused again here."""
    counts = {"inserted": 0, "duplicates": 0, "filtered": 0, "expired": 0, "invalid": 0,
              "archive_disabled": 0, "conflicts": 0}
    days = get_policy(db, owner)["transcript_retention_days"]
    cutoff = (now or utcnow_naive()) - timedelta(days=days)
    for raw in lines:
        raw = (raw or "").strip()
        if not raw:
            continue
        try:
            record = json.loads(raw)
            if not isinstance(record, dict):
                raise ValueError("not an object")
        except ValueError:
            counts["invalid"] += 1
            continue
        stamp = parse_timestamp(record.get("at"))
        if stamp is None or not str(record.get("text") or "").strip():
            counts["invalid"] += 1
            continue
        if stamp < cutoff:
            counts["expired"] += 1
            continue
        try:
            duration = float(record.get("duration_s") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        try:
            result = ingest_event(
                db,
                owner=owner,
                domain=domain,
                event_id=derive_box_event_id(box_id, record),
                text=str(record["text"]),
                capture_mode="ambient",
                source="import:box-day-file",
                capture_started_at=stamp - timedelta(seconds=duration) if duration > 0 else None,
                capture_ended_at=stamp,
                persona=str(record.get("persona") or "") or None,
                now=now,
            )
        except CredentialFiltered:
            counts["filtered"] += 1
        except ArchiveDisabled:
            counts["archive_disabled"] += 1
        except EventConflict:
            counts["conflicts"] += 1
        except TranscriptInvalid:
            counts["invalid"] += 1
        else:
            counts["duplicates" if result.deduplicated else "inserted"] += 1
    return counts


def new_event_id() -> str:
    return "evt-" + uuid.uuid4().hex

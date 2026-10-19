"""Deterministic retrieval and governed domain handoff for imported Instagram Saved items.

Directive stages 5-6 (docs/instagram-saved-primary-ingestion-directive-2026-10-17.md).  This module has no model and no
network dependency.  It reads only the private payload behind each ``source_events`` row, never copies raw text anywhere,
and records its decision as a small pointer in the row's existing ``domain`` and ``payload`` columns - no new table,
scheduler or queue.

Classification is by purpose and evidence, and a save is only ever a LEAD: ``obsidian-phd`` means "worth a research
intake review", ``misumi`` means "a personal reference cue".  Anything weak or ambiguous stays ``neutral`` (retained,
searchable, not forced into a domain).  Domain repositories keep their own write gates: the outbox written here is a
pointer list (permalink + reason codes), not a note, and the owning repository decides what to do with it.
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.constants import DATA_DIR

logger = logging.getLogger(__name__)

HANDOFF_VERSION = 1
SOURCE = "instagram"
DOMAIN_PHD = "obsidian-phd"
DOMAIN_MISUMI = "misumi"
DOMAIN_NEUTRAL = "neutral"
DEFAULT_HANDOFF_DIR = Path(DATA_DIR) / "instagram" / "handoff"
DEFAULT_BATCH = 5000   # one scheduled run drains a whole export (a 1772-item export took 9 runs at 200)
_MIN_SCORE = 2          # one stray word is never enough to route a save
_MIN_MARGIN = 1         # a tie between domains stays neutral

# Cues are matched as whole words/phrases against the item's own caption, title, hashtags and collection names.
_PHD_CUES = {
    "robot", "robots", "robotics", "cobot", "cobots", "hri", "hrc", "automation", "manufacturing", "kinematics",
    "gripper", "manipulator", "actuator", "ergonomics", "ergonomic", "human factors", "humanrobotinteraction",
    "industrial robot", "assembly line", "machine learning", "reinforcement learning", "computer vision", "sensor",
    "sensors", "paper", "research", "study", "thesis", "phd", "literature", "experiment", "measurement", "metrology",
    "lab", "prototype", "ros", "ros2", "slam", "teleoperation", "exoskeleton", "wearable",
}
_MISUMI_CUES = {
    "recipe", "recipes", "cooking", "food", "dinner", "baking", "restaurant", "cafe", "travel", "trip", "holiday",
    "hotel", "music", "song", "album", "playlist", "band", "gig", "concert", "film", "movie", "anime", "game",
    "gaming", "fashion", "outfit", "decor", "interior", "garden", "plant", "plants", "diy", "gift", "book", "books",
    "art", "design", "craft", "home", "kitchen", "pets", "dog", "cat",
}

_WORD = re.compile(r"[a-z0-9][a-z0-9+#_-]*")


def _normalise(text: Any) -> str:
    return unicodedata.normalize("NFKC", str(text or "")).casefold()


def _terms(*parts: Any) -> set[str]:
    """Words and adjacent word pairs of the item's own descriptive fields."""
    words: list[str] = []
    for part in parts:
        values = part if isinstance(part, (list, tuple)) else [part]
        for value in values:
            words.extend(_WORD.findall(_normalise(value)))
    found = set(words)
    found.update(f"{a} {b}" for a, b in zip(words, words[1:]))
    return found


def classify_payload(payload: Any) -> dict[str, Any]:
    """Return ``{"domain", "confidence", "reasons"}`` for one private saved-post payload (pure, deterministic)."""
    if not isinstance(payload, dict):
        return {"domain": DOMAIN_NEUTRAL, "confidence": "none", "reasons": ["no_payload"]}
    collections = [c.get("name") for c in payload.get("collections") or [] if isinstance(c, dict)]
    terms = _terms(payload.get("caption"), payload.get("title"), payload.get("hashtags"), collections)
    phd = sorted(terms & _PHD_CUES)
    misumi = sorted(terms & _MISUMI_CUES)
    reasons = [f"phd:{cue}" for cue in phd[:5]] + [f"misumi:{cue}" for cue in misumi[:5]]
    if len(phd) >= _MIN_SCORE and len(phd) - len(misumi) >= _MIN_MARGIN:
        return {"domain": DOMAIN_PHD, "confidence": "low" if len(phd) < 4 else "medium", "reasons": reasons}
    if len(misumi) >= _MIN_SCORE and len(misumi) - len(phd) >= _MIN_MARGIN:
        return {"domain": DOMAIN_MISUMI, "confidence": "low" if len(misumi) < 4 else "medium", "reasons": reasons}
    return {"domain": DOMAIN_NEUTRAL, "confidence": "none", "reasons": reasons or ["no_cues"]}


def _handoff_record(row_payload: Optional[str]) -> Optional[dict[str, Any]]:
    try:
        value = json.loads(row_payload) if row_payload else None
    except (TypeError, ValueError):
        return None
    record = value.get("handoff") if isinstance(value, dict) else None
    return record if isinstance(record, dict) else None


def _private_append(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, stat.S_IRUSR | stat.S_IWUSR)
    try:
        os.write(fd, (line + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def run_instagram_handoff(
    handoff_dir: str | os.PathLike[str] | None = None,
    *,
    batch: int = DEFAULT_BATCH,
) -> dict[str, Any]:
    """Classify not-yet-handed-off Instagram source events and write pointer outboxes.

    Idempotent: a row whose recorded ``handoff.content_hash`` equals its current ``content_hash`` is skipped, so an
    unchanged export costs one query and no payload reads.  A revised row (new hash) is classified again.  Rows whose
    payload cannot be read or verified are counted ``failed`` and retried on the next run; they are never guessed at.
    """
    from core.database import SourceEvent, get_db_session
    from src.source_events import read_source_event_payload

    started = time.monotonic()
    out = Path(handoff_dir) if handoff_dir is not None else DEFAULT_HANDOFF_DIR
    counts = {"routed_phd": 0, "routed_misumi": 0, "retained_neutral": 0, "skipped": 0, "failed": 0}
    stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    handled = 0
    with get_db_session() as db:
        rows = db.query(SourceEvent).filter(SourceEvent.source == SOURCE).order_by(SourceEvent.received_at, SourceEvent.id).all()
        for row in rows:
            record = _handoff_record(row.payload)
            if record and record.get("content_hash") == row.content_hash and record.get("version") == HANDOFF_VERSION:
                counts["skipped"] += 1
                continue
            if handled >= batch:
                break
            handled += 1
            try:
                payload = read_source_event_payload(row.payload_ref)
            except Exception as exc:  # unreadable or checksum-mismatched payload: report, retry later, never guess
                counts["failed"] += 1
                logger.warning("Instagram handoff could not read a payload (%s)", type(exc).__name__)
                continue
            verdict = classify_payload(payload)
            domain = verdict["domain"]
            row.domain = domain
            row.payload = json.dumps({"handoff": {
                "version": HANDOFF_VERSION, "content_hash": row.content_hash, "domain": domain,
                "confidence": verdict["confidence"], "reasons": verdict["reasons"], "classified_at": stamp,
            }}, sort_keys=True, separators=(",", ":"))
            if domain == DOMAIN_NEUTRAL:
                counts["retained_neutral"] += 1
                continue
            counts["routed_phd" if domain == DOMAIN_PHD else "routed_misumi"] += 1
            _private_append(out / f"{domain}.jsonl", json.dumps({
                "permalink": row.external_id, "domain": domain, "confidence": verdict["confidence"],
                "reasons": verdict["reasons"], "source_event_id": row.id, "content_hash": row.content_hash,
                "revision_count": row.revision_count, "evidence": "lead_only_metadata", "handed_off_at": stamp,
            }, sort_keys=True, separators=(",", ":")))
    accounting = {"timestamp": stamp, **counts, "duration_ms": int((time.monotonic() - started) * 1000)}
    _private_append(out / "handoff-runs.jsonl", json.dumps(accounting, sort_keys=True, separators=(",", ":")))
    return accounting


def search_instagram_items(
    *,
    permalink: Optional[str] = None,
    collection: Optional[str] = None,
    domain: Optional[str] = None,
    term: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Metadata retrieval baseline (directive stage 5): by permalink, collection, domain or a term in the item's own text.

    Returns provenance only - permalink, domain, handoff reasons, saved_at and the payload pointer - never caption text.
    """
    from core.database import SourceEvent, get_db_session
    from src.source_events import read_source_event_payload

    wanted_collection = _normalise(collection) if collection else None
    wanted_term = _normalise(term) if term else None
    results: list[dict[str, Any]] = []
    with get_db_session() as db:
        query = db.query(SourceEvent).filter(SourceEvent.source == SOURCE)
        if permalink:
            query = query.filter(SourceEvent.external_id == permalink)
        if domain:
            query = query.filter(SourceEvent.domain == domain)
        for row in query.order_by(SourceEvent.received_at.desc(), SourceEvent.id).all():
            payload: Any = None
            if wanted_collection or wanted_term:
                try:
                    payload = read_source_event_payload(row.payload_ref)
                except Exception:
                    continue
                names = {_normalise(c.get("name")) for c in payload.get("collections") or [] if isinstance(c, dict)}
                if wanted_collection and wanted_collection not in names:
                    continue
                if wanted_term and wanted_term not in _terms(payload.get("caption"), payload.get("title"), payload.get("hashtags")):
                    continue
            record = _handoff_record(row.payload) or {}
            try:
                ref = json.loads(row.payload_ref) if row.payload_ref else {}
            except ValueError:
                ref = {}
            results.append({
                "permalink": row.external_id, "domain": row.domain, "reasons": record.get("reasons", []),
                "saved_at": ref.get("saved_at"), "payload_path": ref.get("path"), "revision_count": row.revision_count,
            })
            if len(results) >= limit:
                break
    return results

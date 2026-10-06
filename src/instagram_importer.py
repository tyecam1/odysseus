"""Instagram "Download Your Information" (DYI) saved-posts export importer (P2).

Offline, file-based only. This module never makes a network call to
instagram.com/meta and never scrapes anything live - it reads a JSON export
file the user already downloaded via Meta's DYI tool and turns each saved
item into a `SourceEvent` row by calling the generic, source-agnostic
`src/source_events.py::record_source_event()` contract added in P1.

Neutral provenance only: this importer has no `domain` argument and never
touches `SourceEvent.domain`. Every row it creates or revises keeps
`record_source_event`'s own neutral-by-default value. Collection-to-domain
routing is exclusively a P3 governed-handoff concern - this module does not
implement, anticipate, or stub any part of that classification.

Expected export shape (see tests/fixtures/instagram_saved_posts_sample.json
for a SYNTHETIC, schema-representative fixture and a fuller note on the
documented simplifying assumptions taken there pending a real export):

    {
      "saved_saved_media": [
        {
          "title": "<post author / item label>",
          "collection": "<collection name, optional>",
          "string_map_data": {
            "Saved on": {
              "href": "<stable permalink for the saved item>",
              "timestamp": <unix seconds>
            }
          }
        },
        ...
      ]
    }

Stable identity, one row per permalink: `external_id` passed to
`record_source_event` is the saved item's own permalink (`href`) - never a
hash of its content - so re-importing the same export (or a later export
containing the same saved item) resolves to the same SourceEvent row
instead of creating a duplicate.

The same permalink can legitimately appear multiple times in one export -
Instagram lets a user save the same post into more than one collection, at
different times. Those occurrences are pre-aggregated by permalink BEFORE
any `record_source_event` call is made, so there is exactly one call (and
therefore one create-or-revise decision) per distinct permalink, never a
second call for the same href that would compete with and silently replace
the first's collection membership. The aggregated row's `collections` field
is the full deduplicated, sorted set of every collection that permalink was
found in across all its occurrences - not just the most recent one. The
canonical title/timestamp used for that row's content is taken from its
earliest ("Saved on") occurrence, a deterministic choice independent of
list order, so repeated imports of the same export (or a superset export
that still contains that earliest occurrence) hash to the same content and
stay idempotent.

Payload discipline: only small structured fields (title, href, collections,
timestamp) are ever passed as `content`/`metadata` - never raw media bytes,
never a full raw copy of the export. `record_source_event` itself only
persists a sha256 hash of `content` plus the small `metadata` pointer, never
the raw content, mirroring `src/attachment_refs.py`'s ref-not-raw-bytes
convention.

Truthful accounting: `record_source_event` alone does not report whether it
created, revised, or no-op'd a row - its no-op path returns the existing
row with whatever status it already had, indistinguishable by `status`
alone from a fresh single "received" row. This importer therefore checks
for an existing row (by source, external_id) immediately before each call,
and classifies the outcome as "created" (no prior row existed), "revised"
(a prior row existed with a different content hash), or "unchanged" (a
prior row existed with an identical content hash) by comparing before and
after - `counts["created"]` means exactly what it says, never inflated by
counting every successfully processed permalink as newly created.

Schema-drift handling (design choice, see module docstring of
`import_instagram_saved_export` below): this importer uses **partial-import-
with-report** semantics, not exception-per-malformed-item, at the per-item
level - a single malformed entry in an otherwise-valid export does not abort
the whole import, but it is never silently dropped either. It is collected
into the returned result's `failed` list with an explicit reason naming the
offending entry (by index and, when available, its `title`), so a caller
can inspect `result["failed"]` and treat a non-empty list as a visible
signal rather than have it disappear from both success and failure
accounting. A structurally broken *file* (not a single malformed item, but
a top-level shape that doesn't match the expected export at all, e.g.
missing or non-list `saved_saved_media`) still raises
`InstagramImportSchemaError` immediately, since there is nothing item-level
to partially import in that case.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from src.source_events import SourceEventValidationError, record_source_event

# The export's top-level array key. Documented assumption pending a real
# export: Meta has used a couple of versioned spellings for this key across
# DYI export format revisions; this importer only looks for this one name
# (see module docstring / fixture notice for the reasoning). Update to the
# observed real-export key once one is available (see the fixture's
# _fixture_notice).
SAVED_MEDIA_KEY = "saved_saved_media"

# The string_map_data label the "Saved on" timestamp/href entry is keyed
# under in a real DYI export.
SAVED_ON_LABEL = "Saved on"


class InstagramImportSchemaError(ValueError):
    """Raised for a top-level export file that isn't a recognizable DYI export.

    A ValueError subclass so callers can catch it specifically or via the
    generic `except ValueError`. Not raised for a single malformed *item*
    inside an otherwise-valid export - those are reported, not raised (see
    module docstring for the partial-import-with-report design choice).
    """


def _extract_saved_on(entry: dict[str, Any]) -> tuple[Optional[str], Optional[int]]:
    """Return (href, timestamp) for one export entry, or (None, None) if absent."""
    string_map_data = entry.get("string_map_data")
    if not isinstance(string_map_data, dict):
        return None, None
    saved_on = string_map_data.get(SAVED_ON_LABEL)
    if not isinstance(saved_on, dict):
        return None, None
    href = saved_on.get("href")
    timestamp = saved_on.get("timestamp")
    if not isinstance(href, str) or not href.strip():
        return None, None
    if not isinstance(timestamp, int) or isinstance(timestamp, bool):
        return None, None
    return href, timestamp


def _describe_entry(index: int, entry: Any) -> str:
    title = entry.get("title") if isinstance(entry, dict) else None
    if title:
        return f"entry #{index} (title={title!r})"
    return f"entry #{index}"


def _aggregate_by_permalink(items: list, source_file: str) -> tuple[dict[str, dict], list[dict]]:
    """Group valid export entries by stable permalink (href).

    Returns (aggregated, failed):
      - aggregated: {href: {"collections": [sorted, deduped], "title":...,
        "saved_on_timestamp":..., "item_indices": [sorted]}} - exactly one
        entry per distinct permalink, ready for exactly one
        record_source_event call each.
      - failed: per-occurrence schema-drift reports, in original order -
        never silently dropped, matching the item-level partial-import-
        with-report contract.

    The canonical title/timestamp for a permalink with multiple occurrences
    is taken from its earliest ("Saved on") occurrence - a deterministic
    choice independent of input list order, so the same export (or any
    superset export that still contains that earliest occurrence) always
    aggregates to the same content and stays idempotent across re-imports.
    """
    buckets: dict[str, list[dict[str, Any]]] = {}
    failed: list[dict[str, Any]] = []

    for index, entry in enumerate(items):
        if not isinstance(entry, dict):
            failed.append({
                "index": index,
                "title": None,
                "reason": "entry is not a JSON object",
            })
            continue

        href, timestamp = _extract_saved_on(entry)
        if href is None or timestamp is None:
            failed.append({
                "index": index,
                "title": entry.get("title"),
                "reason": (
                    f"{_describe_entry(index, entry)} is missing a valid "
                    f"string_map_data[{SAVED_ON_LABEL!r}].href/timestamp "
                    f"pair (schema drift from the expected DYI export shape)"
                ),
            })
            continue

        collection = entry.get("collection")
        if collection is not None and not isinstance(collection, str):
            failed.append({
                "index": index,
                "title": entry.get("title"),
                "reason": (
                    f"{_describe_entry(index, entry)} has a non-string "
                    f"'collection' field ({type(collection).__name__}) - "
                    "schema drift from the expected DYI export shape"
                ),
            })
            continue

        buckets.setdefault(href, []).append({
            "index": index,
            "title": entry.get("title"),
            "collection": collection,
            "timestamp": timestamp,
        })

    aggregated: dict[str, dict[str, Any]] = {}
    for href, occurrences in buckets.items():
        earliest = min(occurrences, key=lambda o: o["timestamp"])
        collections = sorted({o["collection"] for o in occurrences if o["collection"]})
        aggregated[href] = {
            "title": earliest["title"],
            "saved_on_timestamp": earliest["timestamp"],
            "collections": collections,
            "item_indices": sorted(o["index"] for o in occurrences),
        }

    return aggregated, failed


def import_instagram_saved_export(export_path: str) -> dict:
    """Import one Instagram DYI saved-posts export file.

    Reads the JSON file at `export_path`, pre-aggregates its valid entries
    by stable permalink (see `_aggregate_by_permalink`), and for each
    distinct permalink calls `record_source_event(source="instagram",
    external_id=<href>, content=..., metadata=...)` exactly once. See the
    module docstring for the schema-drift handling design (partial-import-
    with-report), the stable-external-id/single-call-per-permalink
    rationale, and the truthful-accounting design.

    Returns a dict:
        {
          "imported": [
            {"external_id":..., "id":..., "collections": [...],
             "saved_at":..., "outcome": "created"|"revised"|"unchanged"},
            ...
          ],
          "failed": [ {"index":..., "title":..., "reason":...}, ... ],
          "counts": {
            "created": <int>, "revised": <int>, "unchanged": <int>,
            "processed": <int>, "failed": <int>,
          },
        }

    `counts["processed"]` is the number of distinct permalinks successfully
    handled (created + revised + unchanged) - never conflated with
    `counts["created"]`, which counts only genuinely new SourceEvent rows.

    Raises `InstagramImportSchemaError` if the file's top-level shape doesn't
    match a recognizable DYI export (missing/non-list saved-media key) - see
    module docstring.
    """
    with open(export_path, "r", encoding="utf-8") as fh:
        export = json.load(fh)

    if not isinstance(export, dict) or SAVED_MEDIA_KEY not in export:
        raise InstagramImportSchemaError(
            f"Instagram export at {export_path!r} is missing the expected "
            f"top-level {SAVED_MEDIA_KEY!r} key - not a recognizable DYI "
            f"saved-posts export."
        )

    items = export[SAVED_MEDIA_KEY]
    if not isinstance(items, list):
        raise InstagramImportSchemaError(
            f"Instagram export at {export_path!r} has a non-list "
            f"{SAVED_MEDIA_KEY!r} value - not a recognizable DYI saved-posts "
            f"export."
        )

    source_file = os.path.basename(export_path)
    aggregated, failed = _aggregate_by_permalink(items, source_file)

    imported: list[dict[str, Any]] = []
    counts = {"created": 0, "revised": 0, "unchanged": 0}

    # Imported lazily, matching src/source_events.py's own lazy-import
    # convention, so importing this module doesn't force core.database's
    # import at module load time for callers that only need the exception
    # type.
    from core.database import SessionLocal, SourceEvent

    for href, agg in aggregated.items():
        content = {
            "title": agg["title"],
            "href": href,
            "saved_on_timestamp": agg["saved_on_timestamp"],
        }
        metadata = {
            "collections": agg["collections"],
            "saved_at": agg["saved_on_timestamp"],
            "source_file": source_file,
            "item_indices": agg["item_indices"],
        }

        db = SessionLocal()
        try:
            existing = (
                db.query(SourceEvent)
                .filter(SourceEvent.source == "instagram", SourceEvent.external_id == href)
                .first()
            )
            existed_before = existing is not None
            prior_hash = existing.content_hash if existing is not None else None
        finally:
            db.close()

        try:
            row = record_source_event(
                source="instagram",
                external_id=href,
                content=content,
                metadata=metadata,
            )
        except SourceEventValidationError as exc:
            for index in agg["item_indices"]:
                failed.append({
                    "index": index,
                    "title": agg["title"],
                    "reason": f"record_source_event rejected entry #{index}: {exc}",
                })
            continue

        if not existed_before:
            outcome = "created"
        elif row.content_hash != prior_hash:
            outcome = "revised"
        else:
            outcome = "unchanged"
        counts[outcome] += 1

        imported.append({
            "external_id": href,
            "id": row.id,
            "collections": agg["collections"],
            "saved_at": agg["saved_on_timestamp"],
            "outcome": outcome,
        })

    counts["processed"] = counts["created"] + counts["revised"] + counts["unchanged"]
    counts["failed"] = len(failed)

    return {
        "imported": imported,
        "failed": failed,
        "counts": counts,
    }

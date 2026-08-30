"""Instagram "Download Your Information" (DYI) saved-posts export importer (P2).

Offline, file-based only. This module never makes a network call to
instagram.com/meta and never scrapes anything live — it reads a JSON export
file the user already downloaded via Meta's DYI tool and turns each saved
item into a `SourceEvent` row by calling the generic, source-agnostic
`src/source_events.py::record_source_event()` contract added in P1. It does
not implement any misumi/obsidian-phd governance or content-based domain
classification — `domain` here is a simple caller-supplied passthrough
applied uniformly to every item in one import call (see P3 for any future
content-based routing).

Expected export shape (see tests/fixtures/instagram_saved_posts_sample.json
for a SYNTHETIC, schema-representative fixture and a fuller note on the two
documented simplifying assumptions taken there):

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

Stable identity: `external_id` passed to `record_source_event` is the saved
item's own permalink (`href`) — never a hash of its content — so re-importing
the same export (or a later export containing the same saved item) resolves
to the same SourceEvent row instead of creating a duplicate, and so that a
genuine content change (e.g. a re-scrape picking up an edited caption) is
detected as a revision by `record_source_event` rather than masked as a new
row.

Payload discipline: only small structured fields (title, href, collection,
timestamp) are ever passed as `content`/`metadata` — never raw media bytes,
never a full raw copy of the export. `record_source_event` itself only
persists a sha256 hash of `content` plus the small `metadata` pointer, never
the raw content, mirroring `src/attachment_refs.py`'s ref-not-raw-bytes
convention.

Schema-drift handling (design choice, see module docstring of
`import_instagram_saved_export` below): this importer uses **partial-import-
with-report** semantics, not exception-per-malformed-item. A single malformed
entry in an otherwise-valid export does not abort the whole import, but it is
never silently dropped either — it is collected into the returned result's
`failed` list with an explicit reason naming the offending entry (by index
and, when available, its `title`), so a caller can inspect
`result["failed"]` and treat a non-empty list as a visible signal (e.g. log,
alert, or raise) rather than have it disappear from both success and failure
accounting. A structurally broken *file* (not a single malformed item, but a
top-level shape that doesn't match the expected export at all, e.g. missing
or non-list `saved_saved_media`) still raises
`InstagramImportSchemaError` immediately, since there is nothing item-level
to partially import in that case.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from src.source_events import SourceEventValidationError, record_source_event

# The export's top-level array key. Documented assumption: Meta has used a
# couple of versioned spellings for this key across DYI export format
# revisions; this importer only looks for this one name (see module
# docstring / fixture notice for the reasoning).
SAVED_MEDIA_KEY = "saved_saved_media"

# The string_map_data label the "Saved on" timestamp/href entry is keyed
# under in a real DYI export.
SAVED_ON_LABEL = "Saved on"


class InstagramImportSchemaError(ValueError):
    """Raised for a top-level export file that isn't a recognizable DYI export.

    A ValueError subclass so callers can catch it specifically or via the
    generic `except ValueError`. Not raised for a single malformed *item*
    inside an otherwise-valid export — those are reported, not raised (see
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
    if not isinstance(timestamp, int):
        return None, None
    return href, timestamp


def _describe_entry(index: int, entry: Any) -> str:
    title = entry.get("title") if isinstance(entry, dict) else None
    if title:
        return f"entry #{index} (title={title!r})"
    return f"entry #{index}"


def import_instagram_saved_export(export_path: str, domain: str = "neutral") -> dict:
    """Import one Instagram DYI saved-posts export file.

    Reads the JSON file at `export_path`, and for each valid saved item calls
    `record_source_event(source="instagram", external_id=<href>, content=...,
    metadata=...)` once. See the module docstring for the schema-drift
    handling design (partial-import-with-report) and the stable-external-id
    rationale.

    `domain` is a simple declarative passthrough (default "neutral") applied
    to every SourceEvent row created or touched by this call — it performs no
    content-based classification. `record_source_event` itself always stores
    new rows with domain="neutral" (P1's neutral-by-default contract), so
    this importer updates the row's `domain` field directly, after the
    record_source_event call, whenever a non-"neutral" domain is requested.

    Returns a dict:
        {
          "imported": [ {"external_id":..., "id":..., "collection":..., "saved_at":...}, ... ],
          "failed":   [ {"index":..., "title":..., "reason":...}, ... ],
          "counts":   {"created": <int>, "failed": <int>},
        }

    Raises `InstagramImportSchemaError` if the file's top-level shape doesn't
    match a recognizable DYI export (missing/non-list saved-media key) — see
    module docstring.
    """
    with open(export_path, "r", encoding="utf-8") as fh:
        export = json.load(fh)

    if not isinstance(export, dict) or SAVED_MEDIA_KEY not in export:
        raise InstagramImportSchemaError(
            f"Instagram export at {export_path!r} is missing the expected "
            f"top-level {SAVED_MEDIA_KEY!r} key — not a recognizable DYI "
            f"saved-posts export."
        )

    items = export[SAVED_MEDIA_KEY]
    if not isinstance(items, list):
        raise InstagramImportSchemaError(
            f"Instagram export at {export_path!r} has a non-list "
            f"{SAVED_MEDIA_KEY!r} value — not a recognizable DYI saved-posts "
            f"export."
        )

    imported: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    source_file = os.path.basename(export_path)

    for index, entry in enumerate(items):
        if not isinstance(entry, dict):
            failed.append(
                {
                    "index": index,
                    "title": None,
                    "reason": "entry is not a JSON object",
                }
            )
            continue

        href, timestamp = _extract_saved_on(entry)
        if href is None or timestamp is None:
            failed.append(
                {
                    "index": index,
                    "title": entry.get("title"),
                    "reason": (
                        f"{_describe_entry(index, entry)} is missing a valid "
                        f"string_map_data[{SAVED_ON_LABEL!r}].href/timestamp "
                        f"pair (schema drift from the expected DYI export shape)"
                    ),
                }
            )
            continue

        collection = entry.get("collection")
        title = entry.get("title")

        content = {
            "title": title,
            "href": href,
            "saved_on_timestamp": timestamp,
        }
        metadata = {
            "collection": collection,
            "saved_at": timestamp,
            "source_file": source_file,
            "item_index": index,
        }

        try:
            row = record_source_event(
                source="instagram",
                external_id=href,
                content=content,
                metadata=metadata,
            )
        except SourceEventValidationError as exc:
            failed.append(
                {
                    "index": index,
                    "title": title,
                    "reason": f"record_source_event rejected {_describe_entry(index, entry)}: {exc}",
                }
            )
            continue

        _apply_domain(row.id, domain)

        imported.append(
            {
                "external_id": href,
                "id": row.id,
                "collection": collection,
                "saved_at": timestamp,
            }
        )

    return {
        "imported": imported,
        "failed": failed,
        "counts": {"created": len(imported), "failed": len(failed)},
    }


def _apply_domain(source_event_id: str, domain: str) -> None:
    """Set `SourceEvent.domain` for one row.

    `record_source_event` (src/source_events.py, P1) always stores new/
    revised rows with domain="neutral" — it has no `domain` parameter, by
    design, since it is the source-agnostic contract shared by every future
    importer. This importer's `domain` argument is applied here as a plain
    declarative passthrough, not a classifier: every item imported in one
    `import_instagram_saved_export` call gets the same `domain` value.
    """
    from core.database import SessionLocal, SourceEvent

    db = SessionLocal()
    try:
        row = db.query(SourceEvent).filter(SourceEvent.id == source_event_id).first()
        if row is not None and row.domain != domain:
            row.domain = domain
            db.commit()
    finally:
        db.close()

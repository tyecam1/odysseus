"""Offline importer for Instagram Download Your Information saved posts.

Meta's observed 2026 saved-post export consists of two top-level JSON lists:
``saved_posts.json`` contains one metadata-only item per saved post, while
``saved_collections.json`` contains collection metadata and nested ``Media``
membership entries. This module joins those files by normalized permalink and
records exactly one neutral :class:`SourceEvent` per distinct permalink.

The export's ``media`` arrays are empty, so the evidence ceiling is metadata
only. Missing Caption or Title labels are tolerated and remain explicitly
unknown; they are never interpreted as evidence that the source text was
empty. Missing required URL labels are reported per item as
``permanent_schema_error``. A non-list top level is a file-level schema error.

Privacy/provenance discipline: raw captions, titles, owners, hashtags, and
collection details are copied only to the governed local SourceEvent payload
store.  The SourceEvent content/metadata envelopes and importer result contain
only neutral counts, timestamps, checksums, and a ``payload_ref`` pointer.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

from src.source_events import (
    SourceEventValidationError,
    _hash_content,
    _payload_ref_json,
    read_source_event_payload,
    record_source_event,
    store_source_event_payload,
)


EVIDENCE_CEILING = "metadata_only"
PERMANENT_SCHEMA_ERROR = "permanent_schema_error"


class InstagramImportSchemaError(ValueError):
    """Raised when an export file has no item-level shape to import."""


def _load_list(path: str, export_kind: str) -> list[Any]:
    with open(path, "r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, list):
        raise InstagramImportSchemaError(
            f"Instagram {export_kind} export at {path!r} must have a top-level "
            f"JSON list, got {type(value).__name__}."
        )
    return value


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _normalize_permalink(value: Any) -> Optional[str]:
    """Normalize a permalink for SourceEvent identity."""
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    path = parsed.path or "/"
    if not path.endswith("/"):
        path += "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def _label_values(entry: dict[str, Any]) -> Optional[list[Any]]:
    values = entry.get("label_values")
    return values if isinstance(values, list) else None


def _direct_label(
    values: list[Any], label: str, *, key: str = "value"
) -> tuple[Any, Optional[int]]:
    for index, value in enumerate(values):
        if isinstance(value, dict) and value.get("label") == label:
            return value.get(key), index
    return None, None


def _group(values: list[Any], title: str) -> tuple[Optional[dict[str, Any]], Optional[int]]:
    for index, value in enumerate(values):
        if isinstance(value, dict) and value.get("title") == title:
            return value, index
    return None, None


def _nested_records(group: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract label/value maps from a Hashtags/Owner-style nested group."""
    if not group or not isinstance(group.get("dict"), list):
        return []
    records: list[dict[str, Any]] = []
    for wrapper in group["dict"]:
        if not isinstance(wrapper, dict) or not isinstance(wrapper.get("dict"), list):
            continue
        record: dict[str, Any] = {}
        for field in wrapper["dict"]:
            if not isinstance(field, dict):
                continue
            label = field.get("label")
            if isinstance(label, str) and "value" in field:
                record[label] = field.get("value")
        if record:
            records.append(record)
    return records


def _failure(
    source_file: str,
    index: int,
    reason: str,
    *,
    member_index: Optional[int] = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "source_file": source_file,
        "index": index,
        "status": PERMANENT_SCHEMA_ERROR,
        "reason": reason,
    }
    if member_index is not None:
        report["member_index"] = member_index
    return report


def _parse_saved_posts(
    items: list[Any],
    source_file: str,
    *,
    selected_permalinks: Optional[set[str]] = None,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    failed: list[dict[str, Any]] = []

    for index, entry in enumerate(items):
        if not isinstance(entry, dict):
            failed.append(_failure(source_file, index, "saved-post item is not a JSON object"))
            continue
        values = _label_values(entry)
        if values is None:
            failed.append(_failure(source_file, index, "saved-post item has no label_values list"))
            continue

        raw_url, url_index = _direct_label(values, "URL")
        permalink = _normalize_permalink(raw_url)
        if permalink is None:
            failed.append(_failure(source_file, index, "saved-post item is missing a valid URL label"))
            continue
        timestamp = entry.get("timestamp")
        if not _is_int(timestamp):
            failed.append(_failure(source_file, index, "saved-post item has no valid integer timestamp"))
            continue
        if selected_permalinks is not None and permalink not in selected_permalinks:
            continue

        caption, caption_index = _direct_label(values, "Caption")
        title, title_index = _direct_label(values, "Title")
        hashtags_group, hashtags_index = _group(values, "Hashtags")
        owner_group, owner_index = _group(values, "Owner")
        hashtags = [
            record["Name"]
            for record in _nested_records(hashtags_group)
            if isinstance(record.get("Name"), str)
        ]
        owner = _nested_records(owner_group)
        missing_optional = []
        if not isinstance(caption, str):
            caption = None
            missing_optional.append("caption")
        if not isinstance(title, str):
            title = None
            missing_optional.append("title")

        field_pointers = {
            "url": f"/{index}/label_values/{url_index}",
            "hashtags": (
                f"/{index}/label_values/{hashtags_index}"
                if hashtags_index is not None else None
            ),
            "owner": (
                f"/{index}/label_values/{owner_index}"
                if owner_index is not None else None
            ),
        }
        if caption_index is not None:
            field_pointers["caption"] = f"/{index}/label_values/{caption_index}"
        if title_index is not None:
            field_pointers["title"] = f"/{index}/label_values/{title_index}"

        buckets.setdefault(permalink, []).append({
            "index": index,
            "timestamp": timestamp,
            "fbid": entry.get("fbid") if isinstance(entry.get("fbid"), str) else None,
            "caption": caption,
            "title": title,
            "hashtags": hashtags,
            "owner": owner,
            "missing_optional_fields": missing_optional,
            "field_pointers": field_pointers,
        })

    aggregated: dict[str, dict[str, Any]] = {}
    for permalink, occurrences in buckets.items():
        canonical = min(occurrences, key=lambda item: (-item["timestamp"], item["index"]))
        aggregated[permalink] = {
            **canonical,
            "item_indices": sorted(item["index"] for item in occurrences),
        }
    return aggregated, failed


def _parse_collections(
    items: list[Any], source_file: str
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    memberships: dict[str, list[dict[str, Any]]] = {}
    failed: list[dict[str, Any]] = []

    for index, entry in enumerate(items):
        if not isinstance(entry, dict):
            failed.append(_failure(source_file, index, "collection item is not a JSON object"))
            continue
        values = _label_values(entry)
        if values is None:
            failed.append(_failure(source_file, index, "collection item has no label_values list"))
            continue

        name, name_index = _direct_label(values, "Name")
        collection_type, _ = _direct_label(values, "Type")
        privacy, _ = _direct_label(values, "Privacy")
        update_time, update_index = _direct_label(values, "Update time", key="timestamp_value")
        media_group, media_index = _group(values, "Media")
        if not isinstance(name, str) or not name:
            failed.append(_failure(source_file, index, "collection item is missing a valid Name label"))
            continue
        if update_index is not None and not _is_int(update_time):
            failed.append(_failure(source_file, index, "collection Update time is not an integer timestamp_value"))
            continue
        if media_group is None or not isinstance(media_group.get("dict"), list):
            failed.append(_failure(source_file, index, "collection item is missing a valid Media group"))
            continue

        by_permalink: dict[str, list[int]] = {}
        for member_index, member in enumerate(media_group["dict"]):
            if not isinstance(member, dict) or not isinstance(member.get("dict"), list):
                failed.append(_failure(
                    source_file, index, "collection Media member is not a nested dict list",
                    member_index=member_index,
                ))
                continue
            # Meta emits empty wrappers in otherwise valid Media lists.
            if not member["dict"]:
                continue
            raw_url, _ = _direct_label(member["dict"], "URL")
            permalink = _normalize_permalink(raw_url)
            if permalink is None:
                failed.append(_failure(
                    source_file, index, "collection Media member is missing a valid URL label",
                    member_index=member_index,
                ))
                continue
            by_permalink.setdefault(permalink, []).append(member_index)

        for permalink, member_indices in by_permalink.items():
            memberships.setdefault(permalink, []).append({
                "name": name,
                "type": collection_type if isinstance(collection_type, str) else None,
                "privacy": privacy if isinstance(privacy, str) else None,
                "updated_at": update_time if _is_int(update_time) else None,
                "fbid": entry.get("fbid") if isinstance(entry.get("fbid"), str) else None,
                "collection_index": index,
                "member_indices": sorted(member_indices),
                "name_pointer": f"/{index}/label_values/{name_index}",
                "update_time_pointer": (
                    f"/{index}/label_values/{update_index}"
                    if update_index is not None else None
                ),
                "media_pointer": f"/{index}/label_values/{media_index}",
            })

    for records in memberships.values():
        records.sort(key=lambda record: (
            record["name"].casefold(), record["name"], record["collection_index"]
        ))
    return memberships, failed


def _collection_content(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return unique private collection values in a deterministic total order."""
    unique = {
        (
            record["name"], record["type"], record["privacy"],
            record["updated_at"], record["fbid"],
        )
        for record in records
    }
    return [
        {
            "name": name,
            "type": collection_type,
            "privacy": privacy,
            "updated_at": updated_at,
            "fbid": fbid,
        }
        for name, collection_type, privacy, updated_at, fbid in sorted(
            unique,
            key=lambda item: (
                item[0].casefold(),
                item[0],
                item[1] is None,
                item[1] or "",
                item[2] is None,
                item[2] or "",
                item[3] is None,
                item[3] if item[3] is not None else 0,
                item[4] is None,
                item[4] or "",
            ),
        )
    ]


def _private_payload(
    post: dict[str, Any],
    collection_records: list[dict[str, Any]],
    posts_file: str,
    collections_file: str,
    permalink: str,
) -> dict[str, Any]:
    collection_memberships = [
        {
            "name": record["name"],
            "type": record["type"],
            "privacy": record["privacy"],
            "updated_at": record["updated_at"],
            "fbid": record["fbid"],
            "collection_index": record["collection_index"],
            "member_indices": record["member_indices"],
            "name_pointer": record["name_pointer"],
            "update_time_pointer": record["update_time_pointer"],
            "media_pointer": record["media_pointer"],
        }
        for record in collection_records
    ]
    return {
        "kind": "instagram_saved_post",
        "permalink": permalink,
        "saved_at": post["timestamp"],
        "fbid": post["fbid"],
        "caption": post["caption"],
        "title": post["title"],
        "hashtags": post["hashtags"],
        "owner": post["owner"],
        "collections": _collection_content(collection_records),
        "collection_memberships": collection_memberships,
        "saved_posts_file": posts_file,
        "saved_collections_file": collections_file,
        "item_indices": post["item_indices"],
        "field_pointers": post["field_pointers"],
        "evidence_ceiling": EVIDENCE_CEILING,
        "missing_optional_fields": post["missing_optional_fields"],
    }


def _provenance_path(path: str, export_root: str | os.PathLike[str] | None) -> str:
    """Unambiguous file provenance for the governed payload store.

    Every export snapshot names its files ``saved_posts.json`` /
    ``saved_collections.json``, so a bare basename cannot identify the winning
    snapshot.  With an ``export_root`` the posix-style root-relative path is
    recorded; otherwise the full path. Rows written by older versions whose
    provenance is a bare basename are upgraded in place by the freshness-aware
    scheduled job.
    """
    if export_root is None:
        return path
    try:
        return Path(path).relative_to(Path(export_root)).as_posix()
    except ValueError:
        return path


def _payload_counts(
    post: dict[str, Any],
    collection_records: list[dict[str, Any]],
    private_payload: dict[str, Any],
) -> dict[str, int]:
    return {
        "saved_at": post["timestamp"],
        "item_count": len(post["item_indices"]),
        "collection_count": len(private_payload["collections"]),
        "collection_membership_count": len(collection_records),
    }


def _source_event_envelopes(
    permalink: str,
    payload_pointer: dict[str, str],
    counts: dict[str, int],
    missing_optional_fields: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    content = {
        "permalink": permalink,
        **counts,
        "payload_sha256": payload_pointer["sha256"],
        "payload_ref": payload_pointer["path"],
    }
    metadata = {
        **payload_pointer,
        "source_kind": "instagram_saved_post",
        **counts,
        "evidence_ceiling": EVIDENCE_CEILING,
        "missing_optional_fields": missing_optional_fields,
    }
    return content, metadata


def _is_provenance_only_change(
    prior_metadata: dict[str, Any],
    prior_payload: Any,
    incoming_payload: dict[str, Any],
    incoming_counts: dict[str, int],
) -> bool:
    if not isinstance(prior_payload, dict):
        return False
    if any(prior_metadata.get(key) != value for key, value in incoming_counts.items()):
        return False

    provenance_fields = {"saved_posts_file", "saved_collections_file"}
    prior_content = {
        key: value for key, value in prior_payload.items() if key not in provenance_fields
    }
    incoming_content = {
        key: value for key, value in incoming_payload.items() if key not in provenance_fields
    }
    prior_paths = {key: prior_payload.get(key) for key in provenance_fields}
    incoming_paths = {key: incoming_payload.get(key) for key in provenance_fields}
    return prior_content == incoming_content and prior_paths != incoming_paths


def import_instagram_saved_export(
    saved_posts_path: str,
    saved_collections_path: Optional[str] = None,
    *,
    selected_permalinks: Optional[set[str]] = None,
    enforce_freshness: bool = False,
    export_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Import real-shape ``saved_posts`` and ``saved_collections`` exports.

    The scheduled job may select the permalinks owned by this snapshot after
    its cross-snapshot reduction and enable the source-timestamp freshness
    guard, and passes ``export_root`` so payload provenance identifies the
    snapshot directory rather than an ambiguous bare basename. Direct one-off
    imports retain their existing behavior by default and record the full
    path as provenance.
    """
    if saved_collections_path is None:
        saved_collections_path = str(Path(saved_posts_path).with_name("saved_collections.json"))

    saved_posts = _load_list(saved_posts_path, "saved-posts")
    saved_collections = _load_list(saved_collections_path, "saved-collections")
    posts_file = os.path.basename(saved_posts_path)
    collections_file = os.path.basename(saved_collections_path)
    posts_provenance = _provenance_path(saved_posts_path, export_root)
    collections_provenance = _provenance_path(saved_collections_path, export_root)

    posts, post_failures = _parse_saved_posts(
        saved_posts,
        posts_file,
        selected_permalinks=selected_permalinks,
    )
    memberships, collection_failures = _parse_collections(saved_collections, collections_file)
    failed = post_failures + collection_failures

    from core.database import SessionLocal, SourceEvent

    imported: list[dict[str, Any]] = []
    counts = {"created": 0, "revised": 0, "unchanged": 0}
    if enforce_freshness:
        counts.update({"superseded": 0, "provenance_updated": 0})
    for permalink in sorted(posts):
        post = posts[permalink]
        collection_records = memberships.get(permalink, [])
        private_payload = _private_payload(
            post,
            collection_records,
            posts_provenance,
            collections_provenance,
            permalink,
        )
        incoming_payload_sha256 = _hash_content(private_payload)
        payload_counts = _payload_counts(post, collection_records, private_payload)

        db = SessionLocal()
        try:
            existing = (
                db.query(SourceEvent)
                .filter(
                    SourceEvent.source == "instagram",
                    SourceEvent.external_id == permalink,
                )
                .first()
            )
            existed_before = existing is not None
            prior_hash = existing.content_hash if existing is not None else None
            prior_timestamp = None
            prior_metadata: dict[str, Any] = {}
            if enforce_freshness and existing is not None:
                try:
                    prior_metadata = json.loads(existing.payload_ref or "")
                except (TypeError, json.JSONDecodeError):
                    prior_metadata = {}
                candidate = prior_metadata.get("saved_at")
                if _is_int(candidate):
                    prior_timestamp = candidate
        finally:
            db.close()

        if prior_timestamp is not None and post["timestamp"] <= prior_timestamp:
            prior_payload_sha256 = prior_metadata.get("sha256")
            if not isinstance(prior_payload_sha256, str):
                prior_payload_sha256 = prior_metadata.get("payload_sha256")
            if incoming_payload_sha256 == prior_payload_sha256:
                counts["superseded"] += 1
                continue

            try:
                prior_payload = read_source_event_payload(prior_metadata)
            except (OSError, SourceEventValidationError, json.JSONDecodeError):
                prior_payload = None
            if _is_provenance_only_change(
                prior_metadata,
                prior_payload,
                private_payload,
                payload_counts,
            ):
                payload_pointer = store_source_event_payload(
                    "instagram", permalink, private_payload
                )
                _, metadata = _source_event_envelopes(
                    permalink,
                    payload_pointer,
                    payload_counts,
                    post["missing_optional_fields"],
                )
                db = SessionLocal()
                try:
                    row = (
                        db.query(SourceEvent)
                        .filter(
                            SourceEvent.source == "instagram",
                            SourceEvent.external_id == permalink,
                        )
                        .one()
                    )
                    row.payload_ref = _payload_ref_json(metadata)
                    db.commit()
                    db.refresh(row)
                    db.expunge(row)
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()

                counts["provenance_updated"] += 1
                imported.append({
                    "external_id": permalink,
                    "id": row.id,
                    "collection_count": payload_counts["collection_count"],
                    "payload_ref": payload_pointer,
                    "saved_at": post["timestamp"],
                    "imported_at": row.received_at.isoformat() if row.received_at else None,
                    "evidence_ceiling": EVIDENCE_CEILING,
                    "missing_optional_fields": post["missing_optional_fields"],
                    "outcome": "provenance_updated",
                })
                continue

        payload_pointer = store_source_event_payload(
            "instagram", permalink, private_payload
        )
        content, metadata = _source_event_envelopes(
            permalink,
            payload_pointer,
            payload_counts,
            post["missing_optional_fields"],
        )

        try:
            row = record_source_event(
                source="instagram",
                external_id=permalink,
                content=content,
                metadata=metadata,
            )
        except SourceEventValidationError as exc:
            # Validation errors contain structural details only; never echo
            # private export values into a failure report or log.
            failed.append(_failure(
                posts_file,
                post["index"],
                f"SourceEvent validation rejected saved-post item: {exc}",
            ))
            continue

        if not existed_before:
            outcome = "created"
        elif row.content_hash != prior_hash:
            outcome = "revised"
        else:
            outcome = "unchanged"
        counts[outcome] += 1
        imported.append({
            "external_id": permalink,
            "id": row.id,
            "collection_count": len(private_payload["collections"]),
            "payload_ref": payload_pointer,
            "saved_at": post["timestamp"],
            "imported_at": row.received_at.isoformat() if row.received_at else None,
            "evidence_ceiling": EVIDENCE_CEILING,
            "missing_optional_fields": post["missing_optional_fields"],
            "outcome": outcome,
        })

    counts["processed"] = (
        counts["created"]
        + counts["revised"]
        + counts["unchanged"]
        + counts.get("provenance_updated", 0)
    )
    counts["failed"] = len(failed)
    return {"imported": imported, "failed": failed, "counts": counts}


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("saved_posts", help="path to saved_posts.json")
    parser.add_argument("saved_collections", help="path to saved_collections.json")
    args = parser.parse_args(argv)
    try:
        result = import_instagram_saved_export(args.saved_posts, args.saved_collections)
    except (OSError, json.JSONDecodeError, InstagramImportSchemaError) as exc:
        parser.exit(2, f"instagram import failed: {exc}\n")
    print(json.dumps(result["counts"], sort_keys=True))
    return 0 if result["counts"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_main())

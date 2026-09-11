"""Tests for src.instagram_importer.import_instagram_saved_export (P2).

Uses tests/fixtures/instagram_saved_posts_sample.json - a SYNTHETIC,
schema-representative fixture (see that file's "_fixture_notice" field and
src/instagram_importer.py's module docstring); it contains no real Instagram
export data and is explicitly NOT sufficient for P2 acceptance on its own
(see the real-export schema gate). 8 top-level entries: 4 distinct valid
permalinks (one of them - "AAA111" - saved into two different collections
at two different timestamps, to exercise multi-collection-permalink
aggregation and preservation), and 3 intentionally schema-drifted entries
(missing "Saved on" label; a non-string "collection" field; a bare string
instead of an object) to exercise visible schema-drift-failure reporting.
"""
import json
import os

import pytest

from core.database import SourceEvent, get_db_session
from src.instagram_importer import (
    InstagramImportSchemaError,
    import_instagram_saved_export,
)

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "instagram_saved_posts_sample.json"
)

ALL_HREFS = [
    "https://www.instagram.com/p/AAA111/",
    "https://www.instagram.com/p/BBB222/",
    "https://www.instagram.com/p/DDD444/",
    "https://www.instagram.com/p/EEE555/",
    "https://www.instagram.com/p/FFF666/",  # malformed entry's href - never recorded
    "https://www.instagram.com/p/GGG777/",  # malformed entry's href - never recorded
]


def _cleanup():
    with get_db_session() as db:
        db.query(SourceEvent).filter(
            SourceEvent.source == "instagram",
            SourceEvent.external_id.in_(ALL_HREFS),
        ).delete(synchronize_session=False)


@pytest.fixture(autouse=True)
def _clean_rows():
    _cleanup()
    yield
    _cleanup()


def _rows_by_external_id():
    """Return {external_id: {field: value, ...}} snapshots.

    Copies plain field values out while the session is still open rather than
    returning ORM instances - SessionLocal's default expire_on_commit=True
    would make attribute access on a returned row raise
    DetachedInstanceError once the session (and its `with` block) has closed.
    """
    with get_db_session() as db:
        rows = (
            db.query(SourceEvent)
            .filter(
                SourceEvent.source == "instagram",
                SourceEvent.external_id.in_(ALL_HREFS),
            )
            .all()
        )
        return {
            r.external_id: {
                "id": r.id,
                "source": r.source,
                "domain": r.domain,
                "payload_ref": r.payload_ref,
                "content_hash": r.content_hash,
                "status": r.status,
                "revision_count": r.revision_count,
            }
            for r in rows
        }


def test_one_source_event_per_distinct_permalink_with_truthful_created_count():
    result = import_instagram_saved_export(FIXTURE_PATH)

    # 4 distinct valid permalinks in the fixture (AAA111's two occurrences
    # collapse to one row via pre-aggregation).
    rows = _rows_by_external_id()
    assert len(rows) == 4
    for row in rows.values():
        assert row["source"] == "instagram"

    # Truthful accounting: all 4 are genuinely new on a first import.
    assert result["counts"]["created"] == 4
    assert result["counts"]["revised"] == 0
    assert result["counts"]["unchanged"] == 0
    assert result["counts"]["processed"] == 4
    assert result["counts"]["failed"] == 3
    outcomes = {item["external_id"]: item["outcome"] for item in result["imported"]}
    assert all(outcome == "created" for outcome in outcomes.values())


def test_duplicate_permalink_across_collections_preserves_both_memberships():
    """The controller-identified defect this corrects: a permalink saved
    into two collections must not become a last-write-wins single-
    collection record - both memberships must survive in the same row."""
    result = import_instagram_saved_export(FIXTURE_PATH)
    rows = _rows_by_external_id()

    reused_row = rows["https://www.instagram.com/p/AAA111/"]
    payload = json.loads(reused_row["payload_ref"])

    assert set(payload["collections"]) == {"Recipes", "Weekend Ideas"}
    assert payload["collections"] == sorted(payload["collections"])  # deterministic order

    imported_entry = next(
        item for item in result["imported"]
        if item["external_id"] == "https://www.instagram.com/p/AAA111/"
    )
    assert set(imported_entry["collections"]) == {"Recipes", "Weekend Ideas"}

    # Only one row exists for this permalink - not two competing rows.
    assert reused_row["revision_count"] == 0
    assert reused_row["status"] == "received"


def test_canonical_content_uses_earliest_occurrence_deterministically():
    import_instagram_saved_export(FIXTURE_PATH)
    rows = _rows_by_external_id()

    # AAA111's earliest occurrence is timestamp 1700000000 (Recipes), not
    # 1700500000 (Weekend Ideas, saved later) - the canonical content must
    # reflect the earliest save, independent of fixture list order.
    payload = json.loads(rows["https://www.instagram.com/p/AAA111/"]["payload_ref"])
    assert payload["saved_at"] == 1700000000


def test_single_collection_permalink_preserved():
    import_instagram_saved_export(FIXTURE_PATH)
    rows = _rows_by_external_id()

    travel_payload = json.loads(rows["https://www.instagram.com/p/BBB222/"]["payload_ref"])
    diy_payload = json.loads(rows["https://www.instagram.com/p/DDD444/"]["payload_ref"])

    assert travel_payload["collections"] == ["Travel Ideas"]
    assert diy_payload["collections"] == ["DIY Projects"]


def test_reimport_is_idempotent_no_duplicate_rows_and_no_spurious_revisions():
    first_result = import_instagram_saved_export(FIXTURE_PATH)
    first_rows = _rows_by_external_id()
    first_ids = {r["id"] for r in first_rows.values()}
    first_hashes = {href: r["content_hash"] for href, r in first_rows.items()}

    second_result = import_instagram_saved_export(FIXTURE_PATH)
    second_rows = _rows_by_external_id()
    second_ids = {r["id"] for r in second_rows.values()}
    second_hashes = {href: r["content_hash"] for href, r in second_rows.items()}

    assert len(first_rows) == len(second_rows) == 4
    assert first_ids == second_ids  # same rows, not new ones
    assert first_hashes == second_hashes  # content did not drift on re-import

    assert first_result["counts"]["created"] == 4
    # Truthful accounting on the second pass: nothing is newly created,
    # nothing genuinely changed - all 4 are "unchanged", never re-labelled
    # "created".
    assert second_result["counts"]["created"] == 0
    assert second_result["counts"]["unchanged"] == 4
    assert second_result["counts"]["revised"] == 0
    assert second_result["counts"]["processed"] == 4
    for row in second_rows.values():
        assert row["revision_count"] == 0


def test_malformed_entries_are_visibly_reported_not_silently_dropped():
    result = import_instagram_saved_export(FIXTURE_PATH)

    assert result["counts"]["failed"] == 3
    assert len(result["failed"]) == 3
    reasons = " | ".join(f["reason"] for f in result["failed"])
    assert "Saved on" in reasons or "string_map_data" in reasons
    assert "collection" in reasons
    assert "not a JSON object" in reasons

    # Never silently absent from both success and failure accounting: their
    # hrefs must not appear in the imported list nor as SourceEvent rows.
    imported_external_ids = {item["external_id"] for item in result["imported"]}
    assert "https://www.instagram.com/p/FFF666/" not in imported_external_ids
    assert "https://www.instagram.com/p/GGG777/" not in imported_external_ids

    with get_db_session() as db:
        ghost_rows = (
            db.query(SourceEvent)
            .filter(
                SourceEvent.source == "instagram",
                SourceEvent.external_id.in_([
                    "https://www.instagram.com/p/FFF666/",
                    "https://www.instagram.com/p/GGG777/",
                ]),
            )
            .all()
        )
    assert ghost_rows == []


def test_never_sets_or_mutates_domain():
    """Neutral provenance only: this importer must never write anything but
    P1's own neutral default into SourceEvent.domain - there is no domain
    parameter to pass one."""
    import inspect
    sig = inspect.signature(import_instagram_saved_export)
    assert "domain" not in sig.parameters

    import_instagram_saved_export(FIXTURE_PATH)
    rows = _rows_by_external_id()
    for row in rows.values():
        assert row["domain"] == "neutral"


def test_module_has_no_apply_domain_helper():
    import src.instagram_importer as mod
    assert not hasattr(mod, "_apply_domain")


def test_missing_top_level_key_raises_schema_error(tmp_path):
    bad_export = tmp_path / "bad_export.json"
    bad_export.write_text(json.dumps({"not_the_right_key": []}), encoding="utf-8")

    with pytest.raises(InstagramImportSchemaError):
        import_instagram_saved_export(str(bad_export))


def test_non_list_saved_media_value_raises_schema_error(tmp_path):
    bad_export = tmp_path / "bad_export.json"
    bad_export.write_text(json.dumps({"saved_saved_media": "not a list"}), encoding="utf-8")

    with pytest.raises(InstagramImportSchemaError):
        import_instagram_saved_export(str(bad_export))


def test_content_revision_is_reported_as_revised_not_created(tmp_path):
    """A genuine content change (e.g. a later export with an updated
    earliest-occurrence timestamp for the same permalink) must be truthfully
    reported as 'revised', never folded into 'created'."""
    export_v1 = {
        "saved_saved_media": [
            {
                "title": "chef_marco",
                "collection": "Recipes",
                "string_map_data": {"Saved on": {"href": "https://www.instagram.com/p/ZZZ999/", "timestamp": 1700000000}},
            },
        ],
    }
    export_v2 = {
        "saved_saved_media": [
            {
                "title": "chef_marco",
                "collection": "Recipes",
                "string_map_data": {"Saved on": {"href": "https://www.instagram.com/p/ZZZ999/", "timestamp": 1600000000}},
            },
        ],
    }
    path_v1 = tmp_path / "v1.json"
    path_v2 = tmp_path / "v2.json"
    path_v1.write_text(json.dumps(export_v1), encoding="utf-8")
    path_v2.write_text(json.dumps(export_v2), encoding="utf-8")

    try:
        result_v1 = import_instagram_saved_export(str(path_v1))
        assert result_v1["counts"]["created"] == 1

        result_v2 = import_instagram_saved_export(str(path_v2))
        assert result_v2["counts"]["created"] == 0
        assert result_v2["counts"]["revised"] == 1
        assert result_v2["imported"][0]["outcome"] == "revised"
    finally:
        with get_db_session() as db:
            db.query(SourceEvent).filter(
                SourceEvent.source == "instagram",
                SourceEvent.external_id == "https://www.instagram.com/p/ZZZ999/",
            ).delete(synchronize_session=False)

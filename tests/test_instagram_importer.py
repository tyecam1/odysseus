"""Tests for src.instagram_importer.import_instagram_saved_export (P2).

Uses tests/fixtures/instagram_saved_posts_sample.json — a SYNTHETIC,
schema-representative fixture (see that file's "_fixture_notice" field and
src/instagram_importer.py's module docstring); it contains no real Instagram
export data. 7 entries: 6 well-formed saved items across 4 distinct
collections (one href — "AAA111" — reused across two of those entries with
different saved-on timestamps/collections, to exercise the reused-item /
multi-collection-save-over-time case), and 1
intentionally schema-drifted entry (missing the "Saved on" string_map_data
label) to exercise visible schema-drift-failure reporting.
"""
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
    "https://www.instagram.com/p/CCC333/",
    "https://www.instagram.com/p/DDD444/",
    "https://www.instagram.com/p/EEE555/",
    "https://www.instagram.com/p/FFF666/",  # malformed entry's href — never recorded
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
    returning ORM instances — SessionLocal's default expire_on_commit=True
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
            }
            for r in rows
        }


def test_creates_one_source_event_per_valid_saved_item():
    result = import_instagram_saved_export(FIXTURE_PATH)

    # 6 valid entries in the fixture, but one href (AAA111) is reused by a
    # second entry -> 5 distinct SourceEvent rows expected.
    rows = _rows_by_external_id()
    assert len(rows) == 5
    for row in rows.values():
        assert row["source"] == "instagram"

    assert result["counts"]["created"] == 6  # importer processed 6 valid entries...
    assert len(rows) == 5  # ...but only 5 distinct rows exist (one reused href)


def test_collection_membership_present_and_correct_for_multiple_collections():
    import_instagram_saved_export(FIXTURE_PATH)
    rows = _rows_by_external_id()

    import json

    # AAA111 appears twice in the fixture (a "reused item" saved into a
    # second collection, "Weekend Ideas", at a later timestamp than its
    # first "Recipes" save). Its content (which includes the saved-on
    # timestamp) genuinely differs between the two entries, so the second
    # import is a *revision* per record_source_event's own contract, not a
    # silent no-op — the row's collection reflects the latest save.
    reused_row = rows["https://www.instagram.com/p/AAA111/"]
    travel_row = rows["https://www.instagram.com/p/BBB222/"]
    diy_row = rows["https://www.instagram.com/p/DDD444/"]

    reused_payload = json.loads(reused_row["payload_ref"])
    travel_payload = json.loads(travel_row["payload_ref"])
    diy_payload = json.loads(diy_row["payload_ref"])

    assert reused_payload["collection"] == "Weekend Ideas"
    assert travel_payload["collection"] == "Travel Ideas"
    assert diy_payload["collection"] == "DIY Projects"
    # at least 2 distinct collections proven directly
    assert {reused_payload["collection"], travel_payload["collection"]} == {
        "Weekend Ideas",
        "Travel Ideas",
    }


def test_saved_on_timestamp_roundtrips():
    import json

    import_instagram_saved_export(FIXTURE_PATH)
    rows = _rows_by_external_id()

    row = rows["https://www.instagram.com/p/BBB222/"]
    payload = json.loads(row["payload_ref"])
    assert payload["saved_at"] == 1701000000


def test_reimport_is_idempotent_no_duplicate_rows():
    import_instagram_saved_export(FIXTURE_PATH)
    first_count = len(_rows_by_external_id())
    first_ids = {r["id"] for r in _rows_by_external_id().values()}

    import_instagram_saved_export(FIXTURE_PATH)
    second_count = len(_rows_by_external_id())
    second_ids = {r["id"] for r in _rows_by_external_id().values()}

    assert first_count == second_count == 5
    assert first_ids == second_ids  # same rows, not new ones


def test_malformed_entry_is_visibly_reported_not_silently_dropped():
    result = import_instagram_saved_export(FIXTURE_PATH)

    assert result["counts"]["failed"] == 1
    assert len(result["failed"]) == 1
    failure = result["failed"][0]
    assert failure["title"] == "ghost_user"
    assert "Saved on" in failure["reason"] or "string_map_data" in failure["reason"]

    # never silently absent from both success and failure accounting:
    # its href must not appear in the imported list nor as a SourceEvent row.
    imported_external_ids = {item["external_id"] for item in result["imported"]}
    assert "https://www.instagram.com/p/FFF666/" not in imported_external_ids

    with get_db_session() as db:
        ghost_row = (
            db.query(SourceEvent)
            .filter(
                SourceEvent.source == "instagram",
                SourceEvent.external_id == "https://www.instagram.com/p/FFF666/",
            )
            .first()
        )
    assert ghost_row is None


def test_domain_parameter_applied_to_created_rows():
    import_instagram_saved_export(FIXTURE_PATH, domain="misumi")
    rows = _rows_by_external_id()

    assert len(rows) == 5
    for row in rows.values():
        assert row["domain"] == "misumi"


def test_domain_defaults_to_neutral():
    import_instagram_saved_export(FIXTURE_PATH)
    rows = _rows_by_external_id()

    for row in rows.values():
        assert row["domain"] == "neutral"


def test_missing_top_level_key_raises_schema_error(tmp_path):
    import json

    bad_export = tmp_path / "bad_export.json"
    bad_export.write_text(json.dumps({"not_the_right_key": []}), encoding="utf-8")

    with pytest.raises(InstagramImportSchemaError):
        import_instagram_saved_export(str(bad_export))

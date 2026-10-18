"""Acceptance coverage for the real Meta DYI saved-post export schema."""

import copy
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.database import SourceEvent, get_db_session
from src.instagram_importer import (
    EVIDENCE_CEILING,
    InstagramImportSchemaError,
    _parse_collections,
    _parse_saved_posts,
    import_instagram_saved_export,
)
from src.source_events import read_source_event_payload


FIXTURES = Path(__file__).parent / "fixtures"
POSTS_FIXTURE = FIXTURES / "instagram_saved_posts_real_schema_fixture.json"
COLLECTIONS_FIXTURE = FIXTURES / "instagram_saved_collections_real_schema_fixture.json"
TEST_PREFIX = "https://www.instagram.com/p/REDACTED_"


def _fixture(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_exports(tmp_path: Path, posts, collections) -> tuple[str, str]:
    posts_path = tmp_path / "saved_posts.json"
    collections_path = tmp_path / "saved_collections.json"
    posts_path.write_text(json.dumps(posts), encoding="utf-8")
    collections_path.write_text(json.dumps(collections), encoding="utf-8")
    return str(posts_path), str(collections_path)


def _cleanup():
    with get_db_session() as db:
        db.query(SourceEvent).filter(
            SourceEvent.source == "instagram",
            SourceEvent.external_id.like(f"{TEST_PREFIX}%"),
        ).delete(synchronize_session=False)


@pytest.fixture(autouse=True)
def _clean_rows(tmp_path, monkeypatch):
    import src.source_events as source_events

    monkeypatch.setattr(
        source_events, "SOURCE_EVENT_PAYLOAD_DIR", tmp_path / "source_event_payloads"
    )
    _cleanup()
    yield
    _cleanup()


def _rows():
    with get_db_session() as db:
        rows = db.query(SourceEvent).filter(
            SourceEvent.source == "instagram",
            SourceEvent.external_id.like(f"{TEST_PREFIX}%"),
        ).all()
        return {
            row.external_id: {
                "id": row.id,
                "source": row.source,
                "domain": row.domain,
                "payload": row.payload,
                "payload_ref": row.payload_ref,
                "content_hash": row.content_hash,
                "received_at": row.received_at,
                "status": row.status,
                "revision_count": row.revision_count,
            }
            for row in rows
        }


def test_real_shape_parsing_extracts_nested_fields_and_timestamp_value():
    posts, post_failures = _parse_saved_posts(_fixture(POSTS_FIXTURE), POSTS_FIXTURE.name)
    memberships, collection_failures = _parse_collections(
        _fixture(COLLECTIONS_FIXTURE), COLLECTIONS_FIXTURE.name
    )

    assert post_failures == []
    assert collection_failures == []
    assert len(posts) == 4
    post = posts["https://www.instagram.com/p/REDACTED_PERMALINK0/"]
    assert len(post["hashtags"]) == 5
    assert post["owner"] == [{
        "URL": "",
        "Name": "REDACTED_Name",
        "Username": "REDACTED_Username",
    }]
    collection_records = memberships["https://www.instagram.com/p/REDACTED_PERMALINK0/"]
    assert len(collection_records) == 2
    assert all(record["updated_at"] == 1750000000 for record in collection_records)
    assert all(record["member_indices"] == [0, 1] for record in collection_records)


def test_import_creates_one_neutral_event_per_distinct_permalink():
    result = import_instagram_saved_export(str(POSTS_FIXTURE), str(COLLECTIONS_FIXTURE))
    rows = _rows()

    assert result["counts"] == {
        "created": 4,
        "revised": 0,
        "unchanged": 0,
        "processed": 4,
        "failed": 0,
    }
    assert len(rows) == 4
    assert all(row["source"] == "instagram" for row in rows.values())
    assert all(row["domain"] == "neutral" for row in rows.values())


def test_permalink_normalization_collapses_query_host_case_and_missing_slash(tmp_path):
    posts = _fixture(POSTS_FIXTURE)[:1]
    duplicate = copy.deepcopy(posts[0])
    duplicate["timestamp"] += 10
    duplicate["label_values"][0]["value"] = (
        "https://WWW.INSTAGRAM.COM/p/REDACTED_PERMALINK0?tracking=removed"
    )
    posts.append(duplicate)
    paths = _write_exports(tmp_path, posts, [])

    result = import_instagram_saved_export(*paths)

    assert result["counts"]["created"] == 1
    assert result["imported"][0]["external_id"] == (
        "https://www.instagram.com/p/REDACTED_PERMALINK0/"
    )
    assert len(_rows()) == 1


def test_permalink_in_two_collections_has_union_in_deterministic_order(tmp_path):
    collections = _fixture(COLLECTIONS_FIXTURE)
    collections[0]["label_values"][0]["value"] = "REDACTED_Zeta"
    collections[0]["fbid"] = "REDACTED_FBID_Z"
    collections[1]["label_values"][0]["value"] = "REDACTED_Alpha"
    collections[1]["fbid"] = "REDACTED_FBID_A"
    paths = _write_exports(tmp_path, _fixture(POSTS_FIXTURE), collections)

    result = import_instagram_saved_export(*paths)
    imported = next(
        item for item in result["imported"]
        if item["external_id"].endswith("REDACTED_PERMALINK0/")
    )

    assert imported["collection_count"] == 2
    assert "collections" not in imported
    payload = read_source_event_payload(imported["payload_ref"])
    assert [item["name"] for item in payload["collections"]] == [
        "REDACTED_Alpha", "REDACTED_Zeta",
    ]
    assert len(payload["collection_memberships"]) == 2
    assert payload["collection_memberships"][0]["collection_index"] == 1
    assert payload["collection_memberships"][1]["collection_index"] == 0


def test_missing_caption_is_tolerated_and_evidence_ceiling_is_explicit(tmp_path):
    posts = _fixture(POSTS_FIXTURE)
    posts[1]["label_values"] = [
        value for value in posts[1]["label_values"]
        if value.get("label") != "Caption"
    ]
    paths = _write_exports(tmp_path, posts, _fixture(COLLECTIONS_FIXTURE))

    result = import_instagram_saved_export(*paths)
    imported = next(
        item for item in result["imported"]
        if item["external_id"].endswith("REDACTED_PERMALINK1/")
    )

    assert result["counts"]["failed"] == 0
    assert imported["missing_optional_fields"] == ["caption"]
    assert imported["evidence_ceiling"] == EVIDENCE_CEILING
    payload = json.loads(_rows()[imported["external_id"]]["payload_ref"])
    assert payload["missing_optional_fields"] == ["caption"]
    assert payload["evidence_ceiling"] == EVIDENCE_CEILING


def test_missing_url_is_item_level_permanent_schema_error(tmp_path):
    posts = _fixture(POSTS_FIXTURE)
    posts[2]["label_values"] = [
        value for value in posts[2]["label_values"]
        if value.get("label") != "URL"
    ]
    paths = _write_exports(tmp_path, posts, _fixture(COLLECTIONS_FIXTURE))

    result = import_instagram_saved_export(*paths)

    assert result["counts"]["processed"] == 3
    assert result["counts"]["failed"] == 1
    assert result["failed"] == [{
        "source_file": "saved_posts.json",
        "index": 2,
        "status": "permanent_schema_error",
        "reason": "saved-post item is missing a valid URL label",
    }]


def test_payload_ref_resolves_to_private_payload_outside_source_event():
    import_instagram_saved_export(str(POSTS_FIXTURE), str(COLLECTIONS_FIXTURE))
    row = _rows()["https://www.instagram.com/p/REDACTED_PERMALINK0/"]
    payload_ref = json.loads(row["payload_ref"])
    payload = read_source_event_payload(payload_ref)

    assert payload["field_pointers"]["hashtags"] == "/0/label_values/3"
    assert payload["field_pointers"]["owner"] == "/0/label_values/4"
    assert payload["saved_at"] == 1750000000
    for private_value in (
        "REDACTED_Caption", "REDACTED_Title", "REDACTED_Name",
        "REDACTED_Username", "REDACTED_Privacy",
    ):
        assert private_value not in row["payload_ref"]
        assert private_value in json.dumps(payload)


def test_private_values_are_only_in_payload_store_not_envelopes_or_logs(
    tmp_path, monkeypatch, caplog
):
    import src.instagram_importer as importer

    posts = _fixture(POSTS_FIXTURE)
    collections = _fixture(COLLECTIONS_FIXTURE)
    posts[0]["label_values"][1]["value"] = "PRIVATE_CAPTION_SENTINEL"
    posts[0]["label_values"][2]["value"] = "PRIVATE_TITLE_SENTINEL"
    posts[0]["label_values"][3]["dict"][0]["dict"][0]["value"] = (
        "PRIVATE_HASHTAG_SENTINEL"
    )
    posts[0]["label_values"][4]["dict"][0]["dict"][1]["value"] = (
        "PRIVATE_OWNER_SENTINEL"
    )
    collections[0]["label_values"][0]["value"] = "PRIVATE_COLLECTION_SENTINEL"
    paths = _write_exports(tmp_path, posts, collections)

    captured = []
    real_record = importer.record_source_event

    def capture_record(**kwargs):
        captured.append(copy.deepcopy(kwargs))
        return real_record(**kwargs)

    monkeypatch.setattr(importer, "record_source_event", capture_record)
    result = import_instagram_saved_export(*paths)
    external_id = "https://www.instagram.com/p/REDACTED_PERMALINK0/"
    call = next(item for item in captured if item["external_id"] == external_id)
    row = _rows()[external_id]
    imported = next(item for item in result["imported"] if item["external_id"] == external_id)
    private_values = (
        "PRIVATE_CAPTION_SENTINEL",
        "PRIVATE_TITLE_SENTINEL",
        "PRIVATE_HASHTAG_SENTINEL",
        "PRIVATE_OWNER_SENTINEL",
        "PRIVATE_COLLECTION_SENTINEL",
    )

    source_event_envelope = json.dumps({
        "content": call["content"],
        "metadata": call["metadata"],
        "payload": row["payload"],
        "payload_ref": row["payload_ref"],
    })
    result_envelope = json.dumps(result)
    for private_value in private_values:
        assert private_value not in source_event_envelope
        assert private_value not in result_envelope
        assert private_value not in caplog.text

    payload = read_source_event_payload(imported["payload_ref"])
    payload_text = json.dumps(payload)
    for private_value in private_values:
        assert private_value in payload_text
    assert imported["collection_count"] == 2
    assert "collections" not in imported
    assert set(imported["payload_ref"]) == {"kind", "path", "sha256"}


def test_collection_aggregation_hash_is_stable_across_fresh_hash_seeds(tmp_path):
    posts = _fixture(POSTS_FIXTURE)[:1]
    collections = _fixture(COLLECTIONS_FIXTURE)
    collections[0]["label_values"][0]["value"] = "PRIVATE_COLLECTION"
    collections[0]["label_values"][1]["value"] = "PRIVATE_TYPE_A"
    collections[0]["label_values"][2]["value"] = "PRIVATE_PRIVACY_A"
    collections[1]["label_values"][0]["value"] = "PRIVATE_COLLECTION"
    collections[1]["label_values"][1]["value"] = "PRIVATE_TYPE_B"
    collections[1]["label_values"][2]["value"] = "PRIVATE_PRIVACY_B"
    posts_path, collections_path = _write_exports(tmp_path, posts, collections)
    database_path = tmp_path / "subprocess.db"
    data_path = tmp_path / "subprocess-data"
    script = """
import json
from core.database import SourceEvent, get_db_session
from src.instagram_importer import import_instagram_saved_export

result = import_instagram_saved_export({posts!r}, {collections!r})
with get_db_session() as db:
    row = db.query(SourceEvent).filter(
        SourceEvent.source == "instagram",
        SourceEvent.external_id == "https://www.instagram.com/p/REDACTED_PERMALINK0/",
    ).one()
    snapshot = {{
        "content_hash": row.content_hash,
        "row_status": row.status,
        "revision_count": row.revision_count,
        "counts": result["counts"],
    }}
print(json.dumps(snapshot, sort_keys=True))
""".format(posts=posts_path, collections=collections_path)

    snapshots = []
    for hash_seed in ("1", "2"):
        environment = os.environ.copy()
        environment.update({
            "DATABASE_URL": f"sqlite:///{database_path}",
            "ODYSSEUS_DATA_DIR": str(data_path),
            "PYTHONHASHSEED": hash_seed,
        })
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).parents[1],
            env=environment,
            text=True,
            capture_output=True,
            check=True,
        )
        snapshots.append(json.loads(completed.stdout.strip().splitlines()[-1]))

    assert snapshots[0]["content_hash"] == snapshots[1]["content_hash"]
    assert snapshots[0]["row_status"] == snapshots[1]["row_status"] == "received"
    assert snapshots[1]["revision_count"] == 0
    assert snapshots[1]["counts"] == {
        "created": 0,
        "revised": 0,
        "unchanged": 1,
        "processed": 1,
        "failed": 0,
    }


def test_saved_at_is_source_timestamp_and_imported_at_is_separate():
    result = import_instagram_saved_export(str(POSTS_FIXTURE), str(COLLECTIONS_FIXTURE))
    imported = next(
        item for item in result["imported"]
        if item["external_id"].endswith("REDACTED_PERMALINK0/")
    )

    assert imported["saved_at"] == 1750000000
    assert imported["imported_at"] is not None
    assert imported["imported_at"] != str(imported["saved_at"])


def test_reimport_is_noop_with_truthful_unchanged_counts():
    first = import_instagram_saved_export(str(POSTS_FIXTURE), str(COLLECTIONS_FIXTURE))
    first_rows = _rows()
    second = import_instagram_saved_export(str(POSTS_FIXTURE), str(COLLECTIONS_FIXTURE))
    second_rows = _rows()

    assert first["counts"] == {
        "created": 4, "revised": 0, "unchanged": 0, "processed": 4, "failed": 0,
    }
    assert second["counts"] == {
        "created": 0, "revised": 0, "unchanged": 4, "processed": 4, "failed": 0,
    }
    assert {value["id"] for value in first_rows.values()} == {
        value["id"] for value in second_rows.values()
    }
    assert all(value["revision_count"] == 0 for value in second_rows.values())


def test_collection_update_time_change_is_a_revision(tmp_path):
    paths = _write_exports(
        tmp_path, _fixture(POSTS_FIXTURE), _fixture(COLLECTIONS_FIXTURE)
    )
    first = import_instagram_saved_export(*paths)
    collections = _fixture(COLLECTIONS_FIXTURE)
    collections[0]["label_values"][3]["timestamp_value"] += 1
    paths = _write_exports(tmp_path, _fixture(POSTS_FIXTURE), collections)
    second = import_instagram_saved_export(*paths)

    assert first["counts"]["created"] == 4
    assert second["counts"]["created"] == 0
    assert second["counts"]["revised"] == 1
    assert second["counts"]["unchanged"] == 3


@pytest.mark.parametrize("broken_file", ["posts", "collections"])
def test_non_list_top_level_fails_visibly(tmp_path, broken_file):
    posts = {} if broken_file == "posts" else _fixture(POSTS_FIXTURE)
    collections = {} if broken_file == "collections" else _fixture(COLLECTIONS_FIXTURE)
    paths = _write_exports(tmp_path, posts, collections)

    with pytest.raises(InstagramImportSchemaError, match="top-level JSON list"):
        import_instagram_saved_export(*paths)


def test_never_accepts_domain_routing_and_has_no_domain_helper():
    import src.instagram_importer as module

    assert "domain" not in inspect.signature(import_instagram_saved_export).parameters
    assert not hasattr(module, "_apply_domain")

"""Tests for src.source_events.record_source_event — the generic external-
ingest SourceEvent adapter contract (P1). No Instagram/WhatsApp parsing here,
only the neutral idempotent record/revision contract future importers call.
"""
import pytest

from src.source_events import (
    MAX_PAYLOAD_REF_BYTES,
    SourceEventValidationError,
    record_source_event,
)


def _cleanup(source, external_id):
    from core.database import SourceEvent, get_db_session
    with get_db_session() as db:
        db.query(SourceEvent).filter(
            SourceEvent.source == source, SourceEvent.external_id == external_id
        ).delete(synchronize_session=False)


@pytest.fixture(autouse=True)
def _clean_test_rows():
    _cleanup("instagram", "test-ext-1")
    _cleanup("whatsapp", "test-ext-2")
    _cleanup("instagram", "test-ext-3")
    yield
    _cleanup("instagram", "test-ext-1")
    _cleanup("whatsapp", "test-ext-2")
    _cleanup("instagram", "test-ext-3")


def test_aaa_diagnostic_source_events_table_exists():
    """Temporary CI diagnostic (see docs/aoteru-external-knowledge-ingestion-programme-state.md):
    CI's `pytest -q` run reports every test below as
    `sqlalchemy.exc.OperationalError: no such table: source_events`, but
    the full suite otherwise passes (5121 tests) and this table is defined
    unconditionally in core/database.py's Base metadata, created by the
    unconditional `Base.metadata.create_all(bind=engine)` in `init_db()`.
    This dumps what the shared `engine` actually sees, to find out whether
    the table plainly never got created, or something else is going on
    (e.g. a different DB/engine object than expected).
    """
    from core.database import engine
    from sqlalchemy import inspect as sa_inspect

    tables = sorted(sa_inspect(engine).get_table_names())
    print(f"DIAGNOSTIC engine.url={engine.url!r}")
    print(f"DIAGNOSTIC table_count={len(tables)}")
    print(f"DIAGNOSTIC tables={tables}")
    assert "source_events" in tables, (
        f"source_events missing from {len(tables)} tables seen via "
        f"core.database.engine ({engine.url!r}): {tables}"
    )


def _row_count(source, external_id):
    from core.database import SourceEvent, get_db_session
    with get_db_session() as db:
        return db.query(SourceEvent).filter(
            SourceEvent.source == source, SourceEvent.external_id == external_id
        ).count()


def test_duplicate_identical_import_is_not_a_new_row():
    first = record_source_event("instagram", "test-ext-1", "hello world", metadata={"ref": "a"})
    second = record_source_event("instagram", "test-ext-1", "hello world", metadata={"ref": "a"})

    assert _row_count("instagram", "test-ext-1") == 1
    assert first.id == second.id
    assert first.content_hash == second.content_hash
    assert second.status == "received"
    assert second.revision_count == 0


def test_duplicate_import_with_different_whitespace_is_still_idempotent():
    # normalization strips whitespace, so this counts as identical content
    first = record_source_event("instagram", "test-ext-1", "hello world")
    second = record_source_event("instagram", "test-ext-1", "  hello world  ")

    assert _row_count("instagram", "test-ext-1") == 1
    assert first.id == second.id
    assert first.content_hash == second.content_hash


def test_revision_detected_when_content_changes():
    first = record_source_event("whatsapp", "test-ext-2", "message v1")
    assert first.content_hash is not None
    assert first.prior_content_hash is None

    second = record_source_event("whatsapp", "test-ext-2", "message v2 (edited)")

    # still one row for this (source, external_id) — updated in place
    assert _row_count("whatsapp", "test-ext-2") == 1
    assert second.id == first.id
    # content_hash changed and the prior state is recoverable
    assert second.content_hash != first.content_hash
    assert second.prior_content_hash == first.content_hash
    assert second.status == "revised"
    assert second.revision_count == 1

    # a further revision keeps the trail moving and increments again
    third = record_source_event("whatsapp", "test-ext-2", "message v3")
    assert _row_count("whatsapp", "test-ext-2") == 1
    assert third.id == first.id
    assert third.prior_content_hash == second.content_hash
    assert third.revision_count == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(source="", external_id="ext-1", content="hi"),
        dict(source=None, external_id="ext-1", content="hi"),
        dict(source="instagram", external_id="", content="hi"),
        dict(source="instagram", external_id=None, content="hi"),
        dict(source="instagram", external_id="ext-1", content=""),
        dict(source="instagram", external_id="ext-1", content=None),
        dict(source="instagram", external_id="ext-1", content="   "),
    ],
)
def test_malformed_input_raises_typed_exception(kwargs):
    with pytest.raises(SourceEventValidationError):
        record_source_event(**kwargs)


def test_missing_source_raises_typed_exception_separately():
    with pytest.raises(SourceEventValidationError):
        record_source_event(source="", external_id="test-ext-3", content="valid content")
    assert _row_count("instagram", "test-ext-3") == 0


def test_missing_external_id_raises_typed_exception_separately():
    with pytest.raises(SourceEventValidationError):
        record_source_event(source="instagram", external_id="", content="valid content")


def test_missing_content_raises_typed_exception_separately():
    with pytest.raises(SourceEventValidationError):
        record_source_event(source="instagram", external_id="test-ext-3", content="")
    assert _row_count("instagram", "test-ext-3") == 0


def test_roundtrip_preserves_fields_on_read_back():
    from core.database import SourceEvent, get_db_session

    created = record_source_event(
        "instagram", "test-ext-3", "round trip content", metadata={"path": "exports/x.json"}
    )

    with get_db_session() as db:
        row = db.query(SourceEvent).filter(SourceEvent.id == created.id).first()
        assert row is not None
        assert row.source == "instagram"
        assert row.external_id == "test-ext-3"
        assert row.content_hash == created.content_hash
        assert row.payload_ref == created.payload_ref
        assert row.status == "received"
        # raw content must never be persisted verbatim in the row
        assert "round trip content" not in (row.payload_ref or "")
        assert "round trip content" not in (row.payload or "")


def test_never_stores_raw_content_only_hash_and_pointer():
    secret_like_content = "super secret raw message body that must not be stored"
    row = record_source_event(
        "instagram", "test-ext-1", secret_like_content, metadata={"ref": "pointer-only"}
    )
    assert secret_like_content not in (row.payload_ref or "")
    assert row.content_hash != secret_like_content
    assert len(row.content_hash) == 64  # sha256 hex digest length


def test_metadata_must_be_dict_when_provided():
    with pytest.raises(SourceEventValidationError):
        record_source_event("instagram", "test-ext-3", "content", metadata="not-a-dict")


def test_oversized_metadata_is_rejected():
    # Comfortably over MAX_PAYLOAD_REF_BYTES once JSON-serialized.
    oversized = {"blob": "x" * (MAX_PAYLOAD_REF_BYTES + 100)}
    with pytest.raises(SourceEventValidationError):
        record_source_event("instagram", "test-ext-3", "content", metadata=oversized)
    assert _row_count("instagram", "test-ext-3") == 0


def test_metadata_at_or_under_limit_is_accepted():
    # A small pointer dict, comfortably under the cap, must still work.
    row = record_source_event(
        "instagram", "test-ext-3", "content", metadata={"path": "exports/small.json"}
    )
    assert row.payload_ref is not None
    assert len(row.payload_ref.encode("utf-8")) <= MAX_PAYLOAD_REF_BYTES


def test_source_and_external_id_whitespace_normalized_to_same_identity():
    first = record_source_event("instagram", "test-ext-3", "hello")
    second = record_source_event(" instagram ", " test-ext-3 ", "hello")

    assert _row_count("instagram", "test-ext-3") == 1
    assert first.id == second.id
    assert second.source == "instagram"
    assert second.external_id == "test-ext-3"

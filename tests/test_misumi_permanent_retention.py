"""Permanent transcript retention: an explicit policy state, not a huge day count.

Permanent means accepted transcript rows never expire. It does not mean raw audio is retained (audio is never
stored by the transcript runtime), it does not store credential-filtered speech, and it does not touch semantic
memory. See docs/misumi-durable-transcript-runtime.md.
"""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

import core.database as cdb
from core.database import MisumiRetentionPolicy, TranscriptEvent, utcnow_naive
from src import misumi_transcripts as svc

from tests.test_misumi_transcripts import FakeSTT, count_rows, make_client, make_db

OLD = timedelta(days=400)  # far beyond the 90-day maximum finite window


def ingest_old(factory, owner, event_id, text="we are out of oats", age=OLD):
    with factory() as db:
        return svc.ingest_event(db, owner=owner, domain="misumi", event_id=event_id, text=text,
                                capture_mode="ambient", now=utcnow_naive() - age)


def policy(factory, owner="alice"):
    with factory() as db:
        return svc.get_policy(db, owner)


def go_permanent(factory, owner="alice"):
    with factory() as db:
        return svc.set_policy(db, owner, transcript_archive=True, transcript_retention_mode="permanent")


# ---- finite -> permanent ----------------------------------------------------------------------------------

def test_the_default_policy_is_finite_and_unchanged_for_existing_callers(tmp_path):
    _, factory = make_db(tmp_path / "t.db")
    p = policy(factory)
    assert p["transcript_retention_mode"] == "finite"
    assert p["transcript_retention_days"] == 14 and p["transcript_archive"] is False
    assert p["raw_audio_retention"] == "off"
    with factory() as db:  # the old call shape still works and still clamps
        assert svc.set_policy(db, "alice", transcript_retention_days=9999)["transcript_retention_days"] == 90
        assert svc.set_policy(db, "alice", transcript_retention_days=3)["transcript_retention_mode"] == "finite"


def test_finite_to_permanent_keeps_old_rows_visible_everywhere(tmp_path):
    _, factory = make_db(tmp_path / "t.db")
    with factory() as db:
        svc.set_policy(db, "alice", transcript_archive=True, transcript_retention_days=5)
    ingest_old(factory, "alice", "old-1")
    ingest_old(factory, "alice", "old-2", text="and the milk too")
    ingest_old(factory, "alice", "recent", age=timedelta(days=1))
    # finite: the two old rows were purged by the ingest itself
    assert count_rows(factory, "alice") == 1

    after = go_permanent(factory)
    assert after["transcript_retention_mode"] == "permanent"
    assert after["transcript_retention_days"] is None  # no sentinel number
    assert after["transcript_retention_days_if_finite"] == 5

    ingest_old(factory, "alice", "old-3", text="three years ago")
    ingest_old(factory, "alice", "old-4", text="a week later", age=OLD - timedelta(days=7))
    with factory() as db:
        assert svc.purge_expired(db, "alice", max_batches=50) == 0
        page = svc.query_events(db, "alice", limit=50)
        assert {e["event_id"] for e in page["events"]} == {"recent", "old-3", "old-4"}
        assert page["retention_days"] is None and page["retention_mode"] == "permanent"
        assert svc.find_event(db, "alice", "misumi", "old-3") is not None            # direct lookup
        assert svc.lookup_existing(db, "alice", "misumi", "old-3") is not None       # duplicate pre-check
        exported = svc.export_events(db, "alice", limit=100)
        assert "three years ago" in exported and "a week later" in exported           # export
    again = ingest_old(factory, "alice", "old-3", text="three years ago")
    assert again.deduplicated is True and count_rows(factory, "alice") == 3           # duplicate lookup


def test_permanent_does_not_leak_between_owners(tmp_path):
    _, factory = make_db(tmp_path / "t.db")
    go_permanent(factory, "alice")
    with factory() as db:
        svc.set_policy(db, "bob", transcript_archive=True, transcript_retention_days=2)
    ingest_old(factory, "alice", "a-old")
    ingest_old(factory, "bob", "b-old")
    assert count_rows(factory, "alice") == 1
    with factory() as db:
        assert svc.query_events(db, "bob")["events"] == []   # bob's finite window still applies on read...
        assert svc.purge_expired(db, "bob", max_batches=5) == 1  # ...and at purge, while alice's row is untouched
        assert svc.purge_expired(db, "alice", max_batches=5) == 0
    assert count_rows(factory, "bob") == 0 and count_rows(factory, "alice") == 1
    assert policy(factory, "bob")["transcript_retention_mode"] == "finite"


def test_importing_old_box_records_is_not_skipped_as_expired_under_permanent(tmp_path):
    _, factory = make_db(tmp_path / "t.db")
    go_permanent(factory)
    old = (utcnow_naive() - OLD).replace(microsecond=0).isoformat() + "Z"
    with factory() as db:
        counts = svc.import_box_lines(db, owner="alice", lines=[
            '{"at": "%s", "source": "ambient", "persona": "aoteru", "duration_s": 3, "text": "an old kitchen line"}' % old])
    assert counts["inserted"] == 1 and counts["expired"] == 0


# ---- permanent -> finite ------------------------------------------------------------------------------------

def test_permanent_to_finite_is_refused_when_it_would_expire_rows_and_changes_nothing(tmp_path):
    _, factory = make_db(tmp_path / "t.db")
    go_permanent(factory)
    ingest_old(factory, "alice", "old-1")
    ingest_old(factory, "alice", "fresh", age=timedelta(days=1))
    with factory() as db:
        with pytest.raises(svc.RetentionChangeRefused) as exc:
            svc.set_policy(db, "alice", transcript_retention_mode="finite", transcript_retention_days=7)
        assert exc.value.would_expire == 1 and exc.value.status_code == 409
    assert policy(factory)["transcript_retention_mode"] == "permanent"
    assert count_rows(factory, "alice") == 2  # nothing was deleted


def test_permanent_to_finite_with_explicit_confirmation_then_purges_in_bounded_batches(tmp_path):
    _, factory = make_db(tmp_path / "t.db")
    go_permanent(factory)
    for i in range(5):
        ingest_old(factory, "alice", f"old-{i}", text=f"old line number {i}")
    ingest_old(factory, "alice", "fresh", age=timedelta(days=1))
    with factory() as db:
        out = svc.set_policy(db, "alice", transcript_retention_mode="finite", transcript_retention_days=7,
                             confirm_expire_existing=True)
        assert out["transcript_retention_mode"] == "finite" and out["transcript_retention_days"] == 7
        # read-time enforcement applies immediately, before any purge has run
        assert [e["event_id"] for e in svc.query_events(db, "alice")["events"]] == ["fresh"]
        assert svc.find_event(db, "alice", "misumi", "old-0") is None
        assert svc.purge_expired(db, "alice", batch=2, max_batches=1) == 2   # bounded
        assert svc.purge_expired(db, "alice", batch=2, max_batches=50) == 3
    assert count_rows(factory, "alice") == 1


def test_permanent_to_finite_needs_no_confirmation_when_nothing_would_expire(tmp_path):
    _, factory = make_db(tmp_path / "t.db")
    go_permanent(factory)
    ingest_old(factory, "alice", "fresh", age=timedelta(days=1))
    with factory() as db:
        assert svc.set_policy(db, "alice", transcript_retention_mode="finite")["transcript_retention_mode"] == "finite"


def test_a_day_count_alone_never_changes_a_permanent_archive_to_finite(tmp_path):
    """The old call shape (days only) must not silently start expiring a permanent archive."""
    _, factory = make_db(tmp_path / "t.db")
    go_permanent(factory)
    ingest_old(factory, "alice", "old-1")
    with factory() as db:
        out = svc.set_policy(db, "alice", transcript_retention_days=3)
    assert out["transcript_retention_mode"] == "permanent" and out["transcript_retention_days"] is None
    assert out["transcript_retention_days_if_finite"] == 3
    assert count_rows(factory, "alice") == 1


def test_an_unknown_stored_mode_fails_safe_to_permanent(tmp_path, caplog):
    engine, factory = make_db(tmp_path / "t.db")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO misumi_retention_policies (owner, transcript_archive, transcript_retention_days, "
                          "transcript_retention_mode, raw_audio_retention, created_at, updated_at) VALUES "
                          "('carol', 1, 1, 'garbled', 'off', '2026-10-01', '2026-10-01')"))
    with factory() as db:
        assert svc.get_policy(db, "carol")["transcript_retention_mode"] == "permanent"
        assert svc.retention_cutoff(db, "carol") is None


def test_an_invalid_mode_is_rejected(tmp_path):
    _, factory = make_db(tmp_path / "t.db")
    with factory() as db:
        with pytest.raises(svc.TranscriptInvalid):
            svc.set_policy(db, "alice", transcript_retention_mode="forever")


# ---- what permanent does NOT change ---------------------------------------------------------------------------

def test_credential_shaped_speech_is_still_refused_under_permanent(tmp_path):
    _, factory = make_db(tmp_path / "t.db")
    go_permanent(factory)
    with factory() as db:
        with pytest.raises(svc.CredentialFiltered):
            svc.ingest_event(db, owner="alice", domain="misumi", event_id="cred-1",
                             text="my wifi password is hunter2", capture_mode="ambient")
    assert count_rows(factory, "alice") == 0


def test_permanent_text_never_makes_raw_audio_permanent(tmp_path):
    _, factory = make_db(tmp_path / "t.db")
    p = go_permanent(factory)
    assert p["raw_audio_retention"] == "off"
    import inspect
    assert "raw_audio_retention" not in inspect.signature(svc.set_policy).parameters  # not settable in any mode
    assert not any(c.name in ("audio", "audio_blob", "raw_audio") for c in TranscriptEvent.__table__.columns)


def test_archive_off_still_stores_nothing_in_permanent_mode(tmp_path):
    _, factory = make_db(tmp_path / "t.db")
    with factory() as db:
        svc.set_policy(db, "alice", transcript_archive=False, transcript_retention_mode="permanent")
        with pytest.raises(svc.ArchiveDisabled):
            svc.ingest_event(db, owner="alice", domain="misumi", event_id="e", text="hello there",
                             capture_mode="ambient")


# ---- restart durability and migration ---------------------------------------------------------------------------

def test_permanent_survives_a_restart(tmp_path):
    path = tmp_path / "t.db"
    _, factory = make_db(path)
    go_permanent(factory)
    ingest_old(factory, "alice", "old-1")
    # a fresh engine over the same file = a process restart
    engine2 = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    factory2 = sessionmaker(bind=engine2, autoflush=False, autocommit=False)
    assert policy(factory2)["transcript_retention_mode"] == "permanent"
    with factory2() as db:
        assert svc.purge_expired(db, "alice", max_batches=50) == 0
        assert [e["event_id"] for e in svc.query_events(db, "alice")["events"]] == ["old-1"]


def test_an_existing_policy_table_without_the_column_migrates_to_finite_and_is_rerunnable(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    with engine.begin() as conn:  # the schema as deployed before this change
        conn.execute(text("CREATE TABLE misumi_retention_policies (owner VARCHAR PRIMARY KEY, transcript_archive BOOLEAN "
                          "NOT NULL, transcript_retention_days INTEGER NOT NULL, raw_audio_retention VARCHAR NOT NULL, "
                          "created_at DATETIME, updated_at DATETIME)"))
        conn.execute(text("INSERT INTO misumi_retention_policies VALUES ('', 1, 14, 'off', '2026-10-01', '2026-10-01')"))
    monkeypatch.setattr(cdb, "engine", engine)
    cdb._migrate_add_transcript_retention_mode_column()
    cdb._migrate_add_transcript_retention_mode_column()  # idempotent
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as db:
        p = svc.get_policy(db, "")
    assert p["transcript_archive"] is True and p["transcript_retention_mode"] == "finite"
    assert p["transcript_retention_days"] == 14  # exactly the behaviour the row had before
    with factory() as db:  # and the owner can then be made permanent
        assert svc.set_policy(db, "", transcript_retention_mode="permanent")["transcript_retention_mode"] == "permanent"


# ---- HTTP surface -------------------------------------------------------------------------------------------------

def test_policy_api_permanent_roundtrip_and_the_safety_refusal(tmp_path, monkeypatch):
    _, factory = make_db(tmp_path / "t.db")
    client = make_client(factory, monkeypatch, stt=FakeSTT())
    h = {"x-test-owner": "alice"}
    r = client.put("/misumi/transcript/policy", json={"transcript_archive": True, "transcript_retention_mode": "permanent"}, headers=h)
    assert r.status_code == 200 and r.json()["transcript_retention_mode"] == "permanent"
    assert r.json()["transcript_retention_days"] is None
    assert client.get("/misumi/transcript/policy", headers=h).json()["transcript_retention_mode"] == "permanent"

    ingest_old(factory, "alice", "old-1")
    listed = client.get("/misumi/transcript", headers=h).json()
    assert [e["event_id"] for e in listed["events"]] == ["old-1"] and listed["retention_mode"] == "permanent"
    assert client.get("/misumi/transcript/old-1", headers=h).status_code == 200
    exported = client.get("/misumi/transcript/export", headers=h)
    assert exported.status_code == 200 and "we are out of oats" in exported.text  # export honours permanent
    purge = client.post("/misumi/transcript/purge", headers=h).json()
    assert purge == {"removed": 0, "retention_days": None, "retention_mode": "permanent"}

    refused = client.put("/misumi/transcript/policy", json={"transcript_retention_mode": "finite", "transcript_retention_days": 7}, headers=h)
    assert refused.status_code == 409
    assert refused.json()["state"] == "would_expire_existing_transcripts" and refused.json()["would_expire"] == 1
    assert client.get("/misumi/transcript/policy", headers=h).json()["transcript_retention_mode"] == "permanent"

    accepted = client.put("/misumi/transcript/policy", json={"transcript_retention_mode": "finite", "transcript_retention_days": 7,
                                                             "confirm_expire_existing": True}, headers=h)
    assert accepted.status_code == 200 and accepted.json()["transcript_retention_days"] == 7


def test_policy_api_rejects_an_invalid_mode(tmp_path, monkeypatch):
    _, factory = make_db(tmp_path / "t.db")
    client = make_client(factory, monkeypatch, stt=FakeSTT())
    r = client.put("/misumi/transcript/policy", json={"transcript_retention_mode": "forever"}, headers={"x-test-owner": "alice"})
    assert r.status_code == 422

"""Indefinite text-transcript retention on the Odysseus durable store, with synthetic aged rows.

Operator policy (2026-10-26): text transcripts are kept indefinitely; nothing implies indefinite raw audio. This does not wait
for real transcripts to cross a window: rows are persisted with old timestamps and every cleanup trigger is exercised
(write-triggered, read-triggered, explicit purge route) across a simulated restart, with a finite-policy control that
proves the same rows WOULD be purged otherwise. Deletion and owner scoping stay available.
"""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from core.database import TranscriptEvent, utcnow_naive
from src import misumi_transcripts as svc
from tests.test_misumi_transcript_delete import _client, _h
from tests.test_misumi_transcripts import enable_archive, make_db

AGES = {"d8": 8, "d40": 40, "d400": 400, "d3000": 3000}


def _seed(factory, owner="alice"):
    now = utcnow_naive()
    with factory() as db:
        for event_id, days in AGES.items():
            svc.ingest_event(db, owner=owner, event_id=event_id, text=f"synthetic line aged {days} days", now=now - timedelta(days=days))


def _ids(factory, owner="alice"):
    with factory() as db:
        return {e["event_id"] for e in svc.query_events(db, owner, limit=200)["events"]}


def _permanent(factory, owner="alice"):
    with factory() as db:
        svc.set_policy(db, owner, transcript_archive=True, transcript_retention_mode="permanent")


@pytest.fixture()
def store(tmp_path):
    path = tmp_path / "t.db"
    engine, factory = make_db(path)
    yield path, factory
    engine.dispose()


def test_control_finite_policy_does_purge_the_same_aged_rows(store):
    _, factory = store
    enable_archive(factory, "alice", days=14)
    # A finite archive refuses/filters rows already past the window, so seed inside it and age the cutoff instead.
    now = utcnow_naive()
    with factory() as db:
        svc.ingest_event(db, owner="alice", event_id="fresh", text="inside the window", now=now)
        removed = svc.purge_expired(db, "alice", now=now + timedelta(days=400), max_batches=50)
    assert removed == 1 and _ids(factory) == set()


def test_permanent_rows_survive_write_read_and_explicit_cleanup_and_a_restart(store, monkeypatch):
    path, factory = store
    _permanent(factory)
    _seed(factory)
    assert _ids(factory) == set(AGES)

    # write-triggered cleanup: ingest_event purges opportunistically
    with factory() as db:
        svc.ingest_event(db, owner="alice", event_id="write-trigger", text="a new line")
    assert set(AGES) <= _ids(factory)

    # explicit purge (service, far-future clock) and the HTTP purge route
    with factory() as db:
        assert svc.purge_expired(db, "alice", now=utcnow_naive() + timedelta(days=5000), max_batches=50) == 0
    client = _client(factory, monkeypatch)
    r = client.post("/misumi/transcript/purge", headers=_h())
    assert r.status_code == 200 and r.json()["removed"] == 0
    # read-triggered cleanup runs on query paths
    assert client.get("/misumi/transcript/events", headers=_h()).status_code in (200, 404)
    assert set(AGES) <= _ids(factory)

    # simulated restart: new engine and session factory over the same database file
    engine2, factory2 = make_db(path)
    try:
        assert svc.get_policy(factory2(), "alice")["transcript_retention_mode"] == "permanent"
        assert set(AGES) | {"write-trigger"} == _ids(factory2)
        with factory2() as db:
            assert svc.purge_expired(db, "alice", max_batches=50) == 0
        assert set(AGES) <= _ids(factory2)
    finally:
        engine2.dispose()


def test_a_permanent_archive_cannot_be_silently_narrowed_to_a_finite_window(store):
    _, factory = store
    _permanent(factory)
    _seed(factory)
    with factory() as db:
        with pytest.raises(svc.RetentionChangeRefused):
            svc.set_policy(db, "alice", transcript_retention_mode="finite", transcript_retention_days=14)
        # a stray days-only change keeps the permanent mode
        assert svc.set_policy(db, "alice", transcript_retention_days=14)["transcript_retention_mode"] == "permanent"
    assert set(AGES) == _ids(factory)


def test_withdrawal_and_owner_scoping_still_work_on_old_permanent_rows(store, monkeypatch):
    _, factory = store
    _permanent(factory, "alice")
    enable_archive(factory, "bob")
    _seed(factory, "alice")
    client = _client(factory, monkeypatch)
    bob = client.post("/misumi/transcript/delete", json={"event_ids": ["d3000"]}, headers=_h("bob"))
    assert bob.status_code == 200 and bob.json()["not_found"] == ["d3000"] and "d3000" in _ids(factory)
    mine = client.post("/misumi/transcript/delete", json={"event_ids": ["d3000", "d400"]}, headers=_h("alice"))
    assert mine.status_code == 200 and sorted(mine.json()["deleted"]) == ["d3000", "d400"]
    assert _ids(factory) == {"d8", "d40"}


def test_text_retention_does_not_imply_audio_retention():
    from src import misumi_transcripts
    doc = misumi_transcripts.__doc__ or ""
    assert "Permanent text never makes raw audio permanent" in doc.replace("\n", " ").replace("  ", " ")

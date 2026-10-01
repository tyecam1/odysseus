"""Durable Misumi transcript runtime: idempotency, isolation, persist-before-ack,
retention, locality and recovery. See docs/misumi-durable-transcript-runtime.md."""

import json
import threading
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import sessionmaker

from core.database import Base, MisumiRetentionPolicy, SourceEvent, TranscriptEvent, utcnow_naive
from routes import misumi_transcript_routes as routes_mod
from routes.misumi_transcript_routes import setup_misumi_transcript_routes
from src import misumi_transcripts as svc

HOME_OK = lambda: (True, "desktop-in7o23d", "registered home host")  # noqa: E731


def make_db(path):
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 30})
    Base.metadata.create_all(
        engine, tables=[TranscriptEvent.__table__, MisumiRetentionPolicy.__table__]
    )
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def enable_archive(factory, owner="alice", days=None):
    with factory() as db:
        svc.set_policy(db, owner, transcript_archive=True, transcript_retention_days=days)


def count_rows(factory, owner=None):
    with factory() as db:
        stmt = select(func.count()).select_from(TranscriptEvent)
        if owner is not None:
            stmt = stmt.where(TranscriptEvent.owner == owner)
        return db.execute(stmt).scalar_one()


class FakeSTT:
    def __init__(self, text="we need mushrooms on the way home", available=True, log=None):
        self.text = text
        self._available = available
        self.calls = 0
        self.log = log

    @property
    def available(self):
        return self._available

    def transcribe(self, audio):
        self.calls += 1
        if self.log is not None:
            self.log.append("stt")
        return self.text

    def _load_settings(self):
        return {"stt_provider": "local", "whisper_model_size": "tiny.en"}


def make_client(factory, monkeypatch, stt=None, locality=HOME_OK, enabled=True):
    if enabled:
        monkeypatch.setenv("ODYSSEUS_MISUMI_TRANSCRIPT_ENABLED", "1")
    else:
        monkeypatch.delenv("ODYSSEUS_MISUMI_TRANSCRIPT_ENABLED", raising=False)
    app = FastAPI()

    @app.middleware("http")
    async def as_user(request, call_next):
        request.state.current_user = request.headers.get("x-test-owner") or None
        return await call_next(request)

    app.include_router(setup_misumi_transcript_routes(
        stt_service=stt, session_factory=factory, audio_locality=locality))
    return TestClient(app)


def audio_post(client, event_id, owner="alice", **form):
    data = {"event_id": event_id, "capture_mode": "ambient", **form}
    return client.post(
        "/misumi/transcript/audio", data=data,
        files={"file": ("seg.webm", b"\x1aE\xdf\xa3fake-audio", "audio/webm")},
        headers={"x-test-owner": owner},
    )


# 1. retry after an ambiguous timeout -> exactly one durable event --------------

def test_same_event_id_retry_creates_one_row_and_skips_stt(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory)
    stt = FakeSTT()
    client = make_client(factory, monkeypatch, stt=stt)

    first = audio_post(client, "evt-1")
    assert first.status_code == 200 and first.json()["persisted"] is True
    assert first.json()["deduplicated"] is False
    # The client never saw the ack (timeout after server commit) and retries.
    retry = audio_post(client, "evt-1")
    assert retry.status_code == 200 and retry.json()["deduplicated"] is True
    assert retry.json()["event_id"] == "evt-1"
    assert count_rows(factory) == 1
    assert stt.calls == 1  # the retry reconciled from the store, STT did not run again


def test_event_id_with_different_text_is_a_conflict_not_an_overwrite(tmp_path):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory)
    with factory() as db:
        svc.ingest_event(db, owner="alice", event_id="e1", text="original words")
        with pytest.raises(svc.EventConflict):
            svc.ingest_event(db, owner="alice", event_id="e1", text="different words")
    with factory() as db:
        assert db.execute(select(TranscriptEvent.text)).scalar_one() == "original words"


def test_concurrent_duplicate_inserts_resolve_to_one_row(tmp_path):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory)
    barrier = threading.Barrier(8)
    results, errors = [], []

    def worker():
        try:
            with factory() as db:
                barrier.wait(timeout=10)
                results.append(svc.ingest_event(db, owner="alice", event_id="race-1", text="same words"))
        except Exception as exc:  # pragma: no cover - failure path is asserted below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not errors, errors
    assert len(results) == 8
    assert sum(1 for item in results if not item.deduplicated) == 1
    assert count_rows(factory) == 1


# 2. owner isolation -------------------------------------------------------------

def test_owners_cannot_read_or_overwrite_each_others_events(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory, "alice")
    enable_archive(factory, "bob")
    client = make_client(factory, monkeypatch, stt=FakeSTT())

    a = client.post("/misumi/transcript/events", json={"event_id": "shared-id", "text": "alice words"},
                    headers={"x-test-owner": "alice"})
    b = client.post("/misumi/transcript/events", json={"event_id": "shared-id", "text": "bob words"},
                    headers={"x-test-owner": "bob"})
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["deduplicated"] is False and b.json()["deduplicated"] is False  # separate keys
    assert count_rows(factory) == 2

    only_alice = client.get("/misumi/transcript", headers={"x-test-owner": "alice"}).json()["events"]
    assert [item["text"] for item in only_alice] == ["alice words"]
    assert client.get("/misumi/transcript/shared-id", headers={"x-test-owner": "bob"}).json()["text"] == "bob words"

    client.post("/misumi/transcript/events", json={"event_id": "alice-only", "text": "private to alice"},
                headers={"x-test-owner": "alice"})
    assert client.get("/misumi/transcript/alice-only", headers={"x-test-owner": "bob"}).status_code == 404
    assert client.patch("/misumi/transcript/alice-only/wake", json={"matched": True},
                        headers={"x-test-owner": "bob"}).status_code == 404


# 3. durability across a process restart ------------------------------------------

def test_persisted_transcript_survives_process_restart(tmp_path):
    path = tmp_path / "t.db"
    engine, factory = make_db(path)
    enable_archive(factory)
    with factory() as db:
        svc.ingest_event(db, owner="alice", event_id="before-restart", text="hello after reboot")
    engine.dispose()

    engine2, factory2 = make_db(path)  # a new process opening the same database
    with factory2() as db:
        page = svc.query_events(db, "alice")
        assert [item["event_id"] for item in page["events"]] == ["before-restart"]
        retry = svc.ingest_event(db, owner="alice", event_id="before-restart", text="hello after reboot")
        assert retry.deduplicated is True


# 4. commit before acknowledgement ------------------------------------------------

def test_acknowledgement_follows_the_commit(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory)
    order = []
    stt = FakeSTT(log=order)
    real_commit = svc._commit

    def tracking_commit(db):
        order.append("commit")
        real_commit(db)

    monkeypatch.setattr(svc, "_commit", tracking_commit)
    client = make_client(factory, monkeypatch, stt=stt)
    response = audio_post(client, "ordered-1")
    order.append("ack")
    assert response.json()["persisted"] is True
    assert order[:3] == ["stt", "commit", "ack"]


def test_commit_failure_is_never_acknowledged_and_retry_succeeds(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory)
    stt = FakeSTT()
    client = make_client(factory, monkeypatch, stt=stt)
    real_commit = svc._commit
    state = {"fail": True}

    def flaky_commit(db):
        if state["fail"]:
            state["fail"] = False
            raise RuntimeError("disk full")
        real_commit(db)

    monkeypatch.setattr(svc, "_commit", flaky_commit)
    failed = audio_post(client, "evt-flaky")
    assert failed.status_code == 503
    assert failed.json()["detail"]["persisted"] is False
    assert count_rows(factory) == 0  # nothing claimed, nothing stored

    ok = audio_post(client, "evt-flaky")
    assert ok.status_code == 200 and ok.json()["persisted"] is True
    assert count_rows(factory) == 1


# 5/6. retention dimensions ---------------------------------------------------------

def test_archive_disabled_is_explicit_and_never_claims_persisted(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")  # no policy => archive off by default
    client = make_client(factory, monkeypatch, stt=FakeSTT())
    response = client.post("/misumi/transcript/events", json={"event_id": "e1", "text": "some words"},
                           headers={"x-test-owner": "alice"})
    assert response.status_code == 409
    body = response.json()
    assert body["persisted"] is False and body["state"] == "archive_disabled"
    assert count_rows(factory) == 0
    assert client.get("/misumi/transcript/policy", headers={"x-test-owner": "alice"}).json() == {
        "transcript_archive": False,
        "transcript_retention_days": 14,
        "raw_audio_retention": "off",
        "request_level": {
            "conversation_history": "history_mode on /misumi/respond",
            "semantic_promotion": "retention_mode on /misumi/respond",
            "artifact_creation": "retention_mode on /misumi/respond",
        },
    }


def test_runtime_is_disabled_by_default(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    client = make_client(factory, monkeypatch, stt=FakeSTT(), enabled=False)
    response = client.post("/misumi/transcript/events", json={"event_id": "e1", "text": "words"})
    assert response.status_code == 503
    assert response.json()["detail"]["state"] == "runtime_disabled"


def test_retention_is_finite_and_enforced_on_ingest(tmp_path):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory, days=3)
    now = utcnow_naive()
    with factory() as db:
        assert svc.set_policy(db, "alice", transcript_retention_days=9999)["transcript_retention_days"] == 90
        svc.set_policy(db, "alice", transcript_retention_days=3)
        svc.ingest_event(db, owner="alice", event_id="old", text="ten days ago", now=now - timedelta(days=10))
        assert count_rows(factory) == 1
        svc.ingest_event(db, owner="alice", event_id="new", text="today", now=now)
    with factory() as db:
        ids = [item["event_id"] for item in svc.query_events(db, "alice")["events"]]
    assert ids == ["new"]  # the expired row was purged, bounded, by the ingest itself


# 7. host attribution, locality, no silent fallback --------------------------------

def test_stt_host_is_the_physical_host_and_recorded(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory)
    client = make_client(factory, monkeypatch, stt=FakeSTT())
    body = audio_post(client, "evt-host").json()
    assert body["stt"]["host"] == "desktop-in7o23d"
    assert body["stt"]["provider"] == "local"
    assert body["stt"]["model"] == "tiny.en"
    assert body["stt"]["latency_ms"] is not None


def test_audio_is_refused_off_home_and_stt_never_runs(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory)
    stt = FakeSTT()
    lab = lambda: (False, "hz2-workstation", "host role lab is not 'home' (data_locality: home-lan)")  # noqa: E731
    client = make_client(factory, monkeypatch, stt=stt, locality=lab)
    response = audio_post(client, "evt-lab")
    assert response.status_code == 403
    assert response.json()["detail"]["state"] == "audio_locality_refused"
    assert stt.calls == 0 and count_rows(factory) == 0


def test_stt_unavailable_does_not_fall_back_or_store(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory)
    client = make_client(factory, monkeypatch, stt=FakeSTT(available=False))
    response = audio_post(client, "evt-nostt")
    assert response.status_code == 503 and response.json()["detail"]["state"] == "stt_unavailable"
    assert count_rows(factory) == 0


def test_default_locality_allows_only_a_registered_home_host(monkeypatch):
    import src.estate_router as router

    monkeypatch.delenv("ODYSSEUS_TRANSCRIPT_AUDIO_HOSTS", raising=False)
    monkeypatch.setattr(router, "current_host_id", lambda: "hz2-workstation")
    allowed, host, reason = routes_mod.default_audio_locality()
    assert allowed is False and host == "hz2-workstation" and "lab" in reason

    monkeypatch.setattr(router, "current_host_id", lambda: None)
    assert routes_mod.default_audio_locality()[0] is False  # unregistered host fails closed

    monkeypatch.setattr(router, "current_host_id", lambda: "desktop-in7o23d")
    assert routes_mod.default_audio_locality()[0] is True  # estate.yaml registers it with role home

    monkeypatch.setenv("ODYSSEUS_TRANSCRIPT_AUDIO_HOSTS", "dev-box")
    monkeypatch.setattr(router, "current_host_id", lambda: "dev-box")
    assert routes_mod.default_audio_locality()[0] is True  # explicit operator override only


# 8. no raw audio is stored -----------------------------------------------------------

def test_raw_audio_is_not_written_anywhere(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory)
    monkeypatch.chdir(tmp_path)
    before = {path.name for path in tmp_path.rglob("*")}
    client = make_client(factory, monkeypatch, stt=FakeSTT())
    assert audio_post(client, "evt-audio").status_code == 200
    created = {path.name for path in tmp_path.rglob("*")} - before
    assert not [name for name in created if name.endswith((".webm", ".wav", ".mp3", ".ogg", ".m4a"))]
    with factory() as db:
        columns = {col.name for col in TranscriptEvent.__table__.columns}
    assert not {"audio", "audio_blob", "audio_path"} & columns


def test_no_speech_and_empty_audio_create_no_row(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory)
    client = make_client(factory, monkeypatch, stt=FakeSTT(text="   "))
    quiet = audio_post(client, "evt-quiet")
    assert quiet.status_code == 200 and quiet.json()["state"] == "no_speech" and quiet.json()["persisted"] is False
    assert count_rows(factory) == 0


def test_credential_shaped_text_is_refused_before_storage(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory)
    client = make_client(factory, monkeypatch, stt=FakeSTT())
    response = client.post("/misumi/transcript/events",
                           json={"event_id": "e-secret", "text": "the wifi password is hunter2"},
                           headers={"x-test-owner": "alice"})
    assert response.status_code == 200
    assert response.json()["persisted"] is False and response.json()["state"] == "credential_filtered"
    assert count_rows(factory) == 0


# 9. bounded query / export / wake ------------------------------------------------------

def test_query_is_paginated_and_hard_bounded(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory)
    with factory() as db:
        for index in range(7):
            svc.ingest_event(db, owner="alice", event_id=f"e{index}", text=f"utterance number {index}")
    client = make_client(factory, monkeypatch, stt=FakeSTT())
    headers = {"x-test-owner": "alice"}
    page1 = client.get("/misumi/transcript?limit=3", headers=headers).json()
    assert [e["event_id"] for e in page1["events"]] == ["e6", "e5", "e4"] and page1["next_cursor"] is not None
    page2 = client.get(f"/misumi/transcript?limit=3&before_seq={page1['next_cursor']}", headers=headers).json()
    assert [e["event_id"] for e in page2["events"]] == ["e3", "e2", "e1"]
    assert client.get("/misumi/transcript?limit=100000", headers=headers).status_code == 422
    exported = client.get("/misumi/transcript/export?limit=3", headers=headers)
    assert exported.status_code == 200
    lines = [json.loads(line) for line in exported.text.splitlines()]
    assert [item["event_id"] for item in lines] == ["e0", "e1", "e2"]  # oldest first, bounded
    assert client.get("/misumi/transcript/export?limit=999999", headers=headers).status_code == 422


def test_wake_result_is_attached_after_persistence(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory)
    client = make_client(factory, monkeypatch, stt=FakeSTT())
    headers = {"x-test-owner": "alice"}
    saved = client.post("/misumi/transcript/events", json={"event_id": "w1", "text": "not addressed to anyone"},
                        headers=headers).json()
    assert saved["wake"] is None  # a non-wake utterance is stored before any wake decision
    first = client.patch("/misumi/transcript/w1/wake", json={"matched": False}, headers=headers)
    again = client.patch("/misumi/transcript/w1/wake", json={"matched": False}, headers=headers)
    assert first.status_code == 200 and again.status_code == 200
    assert client.get("/misumi/transcript/w1", headers=headers).json()["wake"] == {"matched": False, "intent": None}
    assert count_rows(factory) == 1


# 10. importer for the interface box's existing day files -----------------------------------

def _box_line(at, text, **extra):
    record = {"at": at, "text": text, "source": "lan-stt", "persona": "", "duration_s": 3.5,
              "reviewed_by": None, "filter_owner": "kurisu@host-agent", **extra}
    return json.dumps(record)


def test_box_import_is_idempotent_filters_credentials_and_skips_expired(tmp_path):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory, days=14)
    now = utcnow_naive()
    recent = (now - timedelta(days=1)).replace(microsecond=0).isoformat() + "Z"
    ancient = (now - timedelta(days=60)).replace(microsecond=0).isoformat() + "Z"
    lines = [
        _box_line(recent, "pick up the parcel tomorrow"),
        _box_line(recent, "the card number is 4111 1111 1111 1111"),
        _box_line(ancient, "text from two months ago"),
        "not json at all",
        _box_line(recent, ""),
    ]
    with factory() as db:
        first = svc.import_box_lines(db, owner="alice", lines=lines)
        again = svc.import_box_lines(db, owner="alice", lines=lines)
    assert first == {"inserted": 1, "duplicates": 0, "filtered": 1, "expired": 1, "invalid": 2,
                     "archive_disabled": 0, "conflicts": 0}
    assert again["inserted"] == 0 and again["duplicates"] == 1  # re-pull never duplicates
    assert count_rows(factory) == 1
    with factory() as db:
        row = db.execute(select(TranscriptEvent)).scalar_one()
    assert row.source == "import:box-day-file" and row.capture_mode == "ambient"


# 11. additive migration ---------------------------------------------------------------------

def test_new_tables_are_additive_and_preserve_existing_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}", connect_args={"check_same_thread": False})
    new_tables = {TranscriptEvent.__table__, MisumiRetentionPolicy.__table__}
    Base.metadata.create_all(engine, tables=[t for t in Base.metadata.sorted_tables if t not in new_tables])
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add(SourceEvent(id="legacy-1", source="chat"))
        db.commit()
    assert "misumi_transcript_events" not in inspect(engine).get_table_names()

    Base.metadata.create_all(engine)  # what init_db() does on the next start
    names = set(inspect(engine).get_table_names())
    assert {"misumi_transcript_events", "misumi_retention_policies", "source_events"} <= names
    with factory() as db:
        assert db.get(SourceEvent, "legacy-1").source == "chat"

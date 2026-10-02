"""Explicit user deletion from the permanent transcript archive.

``permanent`` retention means no automatic expiry; it does not mean undeletable. Deletion removes the selected
transcript text from the live archive only (older backups are handled by invalidation, see docs/backup-restore.md),
is owner-scoped, bounded and idempotent, and works under every retention mode.
"""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from core.database import TranscriptEvent, utcnow_naive
from routes.misumi_transcript_routes import BACKUP_NOTICE, setup_misumi_transcript_routes
from src import misumi_transcripts as svc
from tests.test_misumi_transcripts import enable_archive, make_db

HOME_OK = lambda: (True, "desktop-in7o23d", "registered home host")  # noqa: E731


@pytest.fixture()
def factory(tmp_path):
    engine, fac = make_db(tmp_path / "t.db")
    yield fac
    engine.dispose()


def _add(factory, owner, event_id, text="a line of speech", now=None):
    with factory() as db:
        svc.ingest_event(db, owner=owner, event_id=event_id, text=text, now=now)


def _ids(factory, owner="alice"):
    with factory() as db:
        return {e["event_id"] for e in svc.query_events(db, owner, limit=200)["events"]}


def _count(factory):
    with factory() as db:
        return db.execute(select(func.count()).select_from(TranscriptEvent)).scalar_one()


# ---- service ------------------------------------------------------------------------------------

def test_deleting_selected_rows_leaves_the_rest_untouched(factory):
    enable_archive(factory, "alice")
    for i in range(4):
        _add(factory, "alice", f"e{i}", f"line {i}")
    with factory() as db:
        res = svc.delete_events(db, "alice", "misumi", ["e1", "e3"])
    assert res == {"deleted": ["e1", "e3"], "not_found": []}
    assert _ids(factory) == {"e0", "e2"}


def test_unknown_ids_are_reported_and_duplicates_collapsed_in_request_order(factory):
    enable_archive(factory, "alice")
    _add(factory, "alice", "e1")
    with factory() as db:
        res = svc.delete_events(db, "alice", "misumi", ["nope", "e1", "e1", "also-nope"])
    assert res == {"deleted": ["e1"], "not_found": ["nope", "also-nope"]}


def test_deletion_is_idempotent(factory):
    enable_archive(factory, "alice")
    _add(factory, "alice", "e1")
    with factory() as db:
        assert svc.delete_events(db, "alice", "misumi", ["e1"])["deleted"] == ["e1"]
        assert svc.delete_events(db, "alice", "misumi", ["e1"]) == {"deleted": [], "not_found": ["e1"]}


def test_another_owner_cannot_delete_or_even_learn_that_a_row_exists(factory):
    enable_archive(factory, "alice")
    enable_archive(factory, "bob")
    _add(factory, "alice", "shared-id", "alice's line")
    with factory() as db:
        res = svc.delete_events(db, "bob", "misumi", ["shared-id"])
    assert res == {"deleted": [], "not_found": ["shared-id"]}  # indistinguishable from an id that does not exist
    assert _ids(factory, "alice") == {"shared-id"}


def test_a_permanent_archive_is_user_deletable_including_very_old_rows(factory):
    with factory() as db:
        svc.set_policy(db, "alice", transcript_archive=True, transcript_retention_mode="permanent")
    _add(factory, "alice", "old", "from over a year ago", now=utcnow_naive() - timedelta(days=400))
    _add(factory, "alice", "new")
    assert _ids(factory) == {"old", "new"}  # permanent: nothing expired it
    with factory() as db:
        assert svc.delete_events(db, "alice", "misumi", ["old"])["deleted"] == ["old"]
        exported = svc.export_events(db, "alice", limit=1000)
        assert "from over a year ago" not in str(exported) and "a line of speech" in str(exported)
    assert _ids(factory) == {"new"}


def test_deletion_works_after_the_archive_is_switched_off(factory):
    enable_archive(factory, "alice")
    _add(factory, "alice", "e1")
    with factory() as db:
        svc.set_policy(db, "alice", transcript_archive=False)
        assert svc.delete_events(db, "alice", "misumi", ["e1"])["deleted"] == ["e1"]
    assert _count(factory) == 0


def test_a_deleted_event_id_can_be_stored_again_as_a_new_row(factory):
    # Documented behaviour: deletion removes the row and with it the idempotency key.
    enable_archive(factory, "alice")
    _add(factory, "alice", "e1", "first version")
    with factory() as db:
        svc.delete_events(db, "alice", "misumi", ["e1"])
        again = svc.ingest_event(db, owner="alice", event_id="e1", text="a different line")
    assert again.deduplicated is False


@pytest.mark.parametrize("bad", [None, "e1", [], [""], ["  "], [1], ["ok", None]])
def test_invalid_requests_are_refused_and_delete_nothing(factory, bad):
    enable_archive(factory, "alice")
    _add(factory, "alice", "e1")
    with factory() as db:
        with pytest.raises(svc.TranscriptInvalid):
            svc.delete_events(db, "alice", "misumi", bad)
    assert _count(factory) == 1


def test_the_request_is_bounded(factory):
    ids = [f"x{i}" for i in range(svc.MAX_DELETE_IDS + 1)]
    with factory() as db:
        with pytest.raises(svc.TranscriptInvalid, match="at most"):
            svc.delete_events(db, "alice", "misumi", ids)
        assert svc.delete_events(db, "alice", "misumi", ids[:-1])["not_found"] == ids[:-1]


# ---- HTTP ---------------------------------------------------------------------------------------

def _client(factory, monkeypatch, *, scopes=None, enabled=True):
    if enabled:
        monkeypatch.setenv("ODYSSEUS_MISUMI_TRANSCRIPT_ENABLED", "1")
    else:
        monkeypatch.delenv("ODYSSEUS_MISUMI_TRANSCRIPT_ENABLED", raising=False)
    app = FastAPI()

    @app.middleware("http")
    async def as_user(request, call_next):
        request.state.current_user = request.headers.get("x-test-owner") or None
        if scopes is not None:
            request.state.api_token = True
            request.state.api_token_scopes = scopes
            request.state.api_token_owner = request.headers.get("x-test-owner") or None
        return await call_next(request)

    app.include_router(setup_misumi_transcript_routes(stt_service=None, session_factory=factory, audio_locality=HOME_OK))
    return TestClient(app)


def _h(owner="alice"):
    return {"x-test-owner": owner}


def test_post_delete_removes_the_text_and_says_honestly_what_it_did_not_remove(factory, monkeypatch):
    enable_archive(factory, "alice")
    _add(factory, "alice", "e1", "turquoise walrus")
    _add(factory, "alice", "e2", "keep me")
    client = _client(factory, monkeypatch)
    r = client.post("/misumi/transcript/delete", json={"event_ids": ["e1", "ghost"]}, headers=_h())
    assert r.status_code == 200
    body = r.json()
    assert body["deleted"] == ["e1"] and body["not_found"] == ["ghost"] and body["backup_notice"] == BACKUP_NOTICE
    assert "older backup snapshots can still contain this text" in body["backup_notice"].lower()
    assert client.get("/misumi/transcript/e1", headers=_h()).status_code == 404
    export = client.get("/misumi/transcript/export?format=jsonl", headers=_h()).text
    assert "walrus" not in export and "keep me" in export


def test_delete_one_by_id_then_404(factory, monkeypatch):
    enable_archive(factory, "alice")
    _add(factory, "alice", "e1")
    client = _client(factory, monkeypatch)
    assert client.delete("/misumi/transcript/e1", headers=_h()).json()["deleted"] == ["e1"]
    gone = client.delete("/misumi/transcript/e1", headers=_h())
    assert gone.status_code == 404 and gone.json()["detail"]["state"] == "event_not_found"


def test_http_owner_isolation(factory, monkeypatch):
    enable_archive(factory, "alice")
    _add(factory, "alice", "e1")
    client = _client(factory, monkeypatch)
    assert client.delete("/misumi/transcript/e1", headers=_h("bob")).status_code == 404
    assert client.post("/misumi/transcript/delete", json={"event_ids": ["e1"]}, headers=_h("bob")).json()["deleted"] == []
    assert _ids(factory) == {"e1"}


def test_a_read_only_token_cannot_delete(factory, monkeypatch):
    enable_archive(factory, "alice")
    _add(factory, "alice", "e1")
    client = _client(factory, monkeypatch, scopes=["misumi:read"])
    assert client.post("/misumi/transcript/delete", json={"event_ids": ["e1"]}, headers=_h()).status_code == 403
    assert client.delete("/misumi/transcript/e1", headers=_h()).status_code == 403
    assert _ids(factory) == {"e1"}
    allowed = _client(factory, monkeypatch, scopes=["misumi:execute"])
    assert allowed.delete("/misumi/transcript/e1", headers=_h()).status_code == 200


def test_http_validation_and_disabled_runtime(factory, monkeypatch):
    client = _client(factory, monkeypatch)
    assert client.post("/misumi/transcript/delete", json={"event_ids": []}, headers=_h()).status_code == 422
    assert client.post("/misumi/transcript/delete", json={}, headers=_h()).status_code == 422
    too_many = {"event_ids": [f"x{i}" for i in range(svc.MAX_DELETE_IDS + 1)]}
    assert client.post("/misumi/transcript/delete", json=too_many, headers=_h()).status_code == 422
    off = _client(factory, monkeypatch, enabled=False)
    assert off.post("/misumi/transcript/delete", json={"event_ids": ["a"]}, headers=_h()).status_code == 503
    assert off.delete("/misumi/transcript/a", headers=_h()).status_code == 503

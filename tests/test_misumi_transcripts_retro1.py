"""Regression tests for the findings of retrospective Sol review #1 (2026-10-01)."""

import os
import time
from datetime import timedelta

import pytest
from sqlalchemy import select

from core.database import TranscriptEvent, utcnow_naive
from src import misumi_transcripts as svc
from services.stt import stt_service as stt_mod
from tests.test_misumi_transcripts import (
    FakeSTT,
    audio_post,
    count_rows,
    enable_archive,
    make_client,
    make_db,
)
from tests.test_misumi_consultation import _client as consultation_client
from tests.test_misumi_consultation import _is_consult


# Finding 1 (critical): history on + semantic retention off must not write memory ----

def test_consultation_with_history_on_and_retention_off_writes_no_memory(tmp_path, monkeypatch):
    async def llm_call(url, model, messages, **kwargs):
        if not _is_consult(messages):
            return '{"answer":"Reviewed.","memory":null,"artifact":null}'
        return "Review the deployment boundary."

    client, memory = consultation_client(tmp_path, monkeypatch, llm_call)
    body = client.post("/misumi/respond", json={
        "prompt": "Kurisu and Lelouch: review the deployment boundary",
        "persona": "aoteru",
        "retention_mode": "off",
        "history_mode": "auto",
    }).json()

    assert [item["persona"] for item in body["consulted"]] == ["kurisu", "lelouch"]
    assert body["capsule_id"] is None
    assert body["handoff_ids"] == []
    assert memory.capsules() == ([], 0)
    assert memory.handoffs() == ([], 0)
    assert body["retention"] == {"memory": {"status": "disabled"}, "artifact": {"status": "disabled"}}


def test_consultation_with_semantic_retention_on_still_captures(tmp_path, monkeypatch):
    async def llm_call(url, model, messages, **kwargs):
        if not _is_consult(messages):
            return '{"answer":"Reviewed.","memory":null,"artifact":null}'
        return "Review the deployment boundary."

    client, memory = consultation_client(tmp_path, monkeypatch, llm_call)
    body = client.post("/misumi/respond", json={
        "prompt": "Kurisu and Lelouch: review the deployment boundary",
        "persona": "aoteru",
        "retention_mode": "auto",
        "history_mode": "off",
    }).json()
    assert body["capsule_id"] is not None  # semantic capture follows retention_mode alone
    assert len(memory.capsules()[0]) == 1


# Finding 2 (major): only the local STT provider may transcribe household audio -----

def test_non_local_stt_provider_is_refused_before_any_audio_is_read(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory)

    class RemoteSTT(FakeSTT):
        def _load_settings(self):
            return {"stt_provider": "endpoint:cloud-whisper"}

    stt = RemoteSTT()
    client = make_client(factory, monkeypatch, stt=stt)
    response = audio_post(client, "evt-remote")
    assert response.status_code == 403
    assert response.json()["detail"]["state"] == "stt_provider_not_local"
    assert stt.calls == 0 and count_rows(factory) == 0


# Finding 3 (major): raw audio must not survive a crash -------------------------------

def test_stale_temp_audio_is_removed_and_fresh_audio_is_kept(tmp_path, monkeypatch):
    monkeypatch.setenv("ODYSSEUS_STT_TMP_DIR", str(tmp_path / "stt-tmp"))
    tmp_dir = stt_mod.stt_tmp_dir()
    stale = tmp_dir / f"{stt_mod.STT_TMP_PREFIX}crashed.webm"
    fresh = tmp_dir / f"{stt_mod.STT_TMP_PREFIX}inflight.webm"
    other = tmp_dir / "unrelated.txt"
    for path in (stale, fresh, other):
        path.write_bytes(b"audio")
    old = time.time() - 3600
    os.utime(stale, (old, old))
    os.utime(other, (old, old))

    assert stt_mod.purge_stale_temp_audio() == 1  # simulates the next start-up after a kill
    assert not stale.exists() and fresh.exists() and other.exists()


def test_service_start_purges_audio_left_by_a_killed_process(tmp_path, monkeypatch):
    monkeypatch.setenv("ODYSSEUS_STT_TMP_DIR", str(tmp_path / "stt-tmp"))
    leftover = stt_mod.stt_tmp_dir() / f"{stt_mod.STT_TMP_PREFIX}killed.webm"
    leftover.write_bytes(b"household audio")
    old = time.time() - 3600
    os.utime(leftover, (old, old))
    stt_mod.STTService()
    assert not leftover.exists()


def test_local_transcription_leaves_no_audio_file_on_success_or_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("ODYSSEUS_STT_TMP_DIR", str(tmp_path / "stt-tmp"))
    service = stt_mod.STTService()

    class Seg:
        text = " hello "

    class Info:
        language = "en"
        language_probability = 0.99

    class Good:
        def transcribe(self, path, **kwargs):
            assert os.path.dirname(path) == str(tmp_path / "stt-tmp")
            return [Seg()], Info()

    class Bad:
        def transcribe(self, path, **kwargs):
            raise RuntimeError("model crashed")

    monkeypatch.setattr(service, "_get_whisper", lambda: Good())
    assert service._transcribe_local(b"audio") == "hello"
    monkeypatch.setattr(service, "_get_whisper", lambda: Bad())
    assert service._transcribe_local(b"audio") is None
    assert list((tmp_path / "stt-tmp").iterdir()) == []


# Finding 4 (major): retention enforced on reads, shortened windows, backlogs ------------

def test_expired_rows_are_not_readable_even_if_no_ingest_has_run(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory, days=14)
    long_ago = utcnow_naive() - timedelta(days=20)
    with factory() as db:
        svc.ingest_event(db, owner="alice", event_id="stale-1", text="from three weeks ago", now=long_ago)
        svc.ingest_event(db, owner="alice", event_id="live-1", text="from today")
        # Nothing has purged yet, but the read already enforces the window.
        assert [e["event_id"] for e in svc.query_events(db, "alice")["events"]] == ["live-1"]
        assert svc.find_event(db, "alice", "misumi", "stale-1") is None
    client = make_client(factory, monkeypatch, stt=FakeSTT())
    headers = {"x-test-owner": "alice"}
    assert client.get("/misumi/transcript/stale-1", headers=headers).status_code == 404
    assert "from three weeks ago" not in client.get("/misumi/transcript/export", headers=headers).text


def test_shortening_the_window_hides_rows_immediately(tmp_path):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory, days=30)
    with factory() as db:
        svc.ingest_event(db, owner="alice", event_id="e5", text="five days old",
                         now=utcnow_naive() - timedelta(days=5))
        assert len(svc.query_events(db, "alice")["events"]) == 1
        svc.set_policy(db, "alice", transcript_retention_days=2)
        assert svc.query_events(db, "alice")["events"] == []  # no purge ran; the read enforces it


def test_backlog_beyond_one_batch_drains_in_bounded_batches(tmp_path):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory, days=1)
    old = utcnow_naive() - timedelta(days=9)
    with factory() as db:
        for index in range(25):
            db.add(TranscriptEvent(owner="alice", domain="misumi", event_id=f"old-{index}",
                                   text=f"old {index}", text_sha256=f"h{index}", persisted_at=old))
        db.commit()
        assert svc.purge_expired(db, "alice", batch=10, max_batches=1) == 10   # one bounded batch
        assert svc.purge_expired(db, "alice", batch=10, max_batches=5) == 15   # drains the rest
        assert db.execute(select(TranscriptEvent)).first() is None


def test_purge_endpoint_drains_and_is_owner_scoped(tmp_path, monkeypatch):
    engine, factory = make_db(tmp_path / "t.db")
    enable_archive(factory, "alice", days=1)
    enable_archive(factory, "bob", days=1)
    old = utcnow_naive() - timedelta(days=5)
    with factory() as db:
        for owner in ("alice", "bob"):
            db.add(TranscriptEvent(owner=owner, domain="misumi", event_id="o1", text="x",
                                   text_sha256="h", persisted_at=old))
        db.commit()
    client = make_client(factory, monkeypatch, stt=FakeSTT())
    assert client.post("/misumi/transcript/purge", headers={"x-test-owner": "alice"}).json()["removed"] == 1
    assert count_rows(factory, "alice") == 0 and count_rows(factory, "bob") == 1


# Finding 6 (minor): ordinary household credential phrasing ------------------------------

@pytest.mark.parametrize("phrase", [
    "My Wi-Fi key is abcd1234",
    "the wifi password is on the fridge",
    "the door code is 4821",
    "my pin is 1234",
    "router passcode ready for the guests",
])
def test_household_credential_phrasing_is_refused(phrase):
    assert svc.looks_credential_shaped(phrase)


@pytest.mark.parametrize("phrase", [
    "the key is on the table",
    "we should fix the code review process tomorrow",
    "put the pin cushion in the drawer",
    "the router is blinking again",
])
def test_ordinary_speech_is_not_refused(phrase):
    assert not svc.looks_credential_shaped(phrase)

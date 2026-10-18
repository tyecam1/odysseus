"""Backup/restore drill for the durable Misumi transcript archive.

Programme: ``misumi-long-horizon-programme`` (Phase 4, first slice). Task context:
``docs/misumi-durable-transcript-runtime.md`` ("Permanent transcript retention" and
"Failure semantics"); backup tool: ``docs/backup-restore.md``.

This drives the *existing* ``scripts/odysseus-backup`` (snapshot, verify, restore)
against a disposable, file-backed archive, in both layouts: ``<repo>/data`` and an external directory named by
``ODYSSEUS_DATA_DIR`` (how the household deployment runs). It adds no store, tool or mechanism. It
proves what the runtime document asserts but nothing exercised before:

* the archive survives snapshot -> destroy -> restore row for row (full-row parity,
  content hash, per-owner isolation, SQLite integrity);
* the idempotency key and the conflict guard still hold on the restored database, so
  the interface box's outbox replaying events after a restore cannot duplicate or
  overwrite anything;
* a ``permanent`` retention policy and an old row both survive a restore and are not
  purged by it;
* the stated recovery point: writes made after the snapshot are NOT recovered by the
  restore (they are replayed by the client), and the pre-restore data is stashed for
  rollback.

Everything runs in ``tmp_path``; nothing touches ``data/`` or a real archive.
"""

import hashlib
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from core.database import Base, MisumiRetentionPolicy, TranscriptEvent, utcnow_naive
from src import misumi_transcripts as svc
from tests.helpers.cli_loader import load_script

EVENTS_TABLE = TranscriptEvent.__table__
POLICY_TABLE = MisumiRetentionPolicy.__table__

ALICE_COUNT = 12
BOB_COUNT = 6
OLD_EVENT_ID = "drill-alice-old-400d"


def _factory(db_path):
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 30}
    )
    Base.metadata.create_all(engine, tables=[EVENTS_TABLE, POLICY_TABLE])
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _dump(factory):
    """Every column of every row (including the integer ``seq`` and all timestamps)."""
    with factory() as db:
        events = [tuple(r) for r in db.execute(select(EVENTS_TABLE).order_by(EVENTS_TABLE.c.seq)).all()]
        policies = [tuple(r) for r in db.execute(select(POLICY_TABLE).order_by(POLICY_TABLE.c.owner)).all()]
    return events, policies


def _digest(rows):
    return hashlib.sha256(json.dumps(rows, default=str).encode("utf-8")).hexdigest()


class Drill:
    """A disposable repository root with a real ``data/app.db`` and the real backup script."""

    def __init__(self, root, monkeypatch, capsys, external):
        self.root = root
        self.capsys = capsys
        if external:
            # The production layout: the runtime's data lives outside the release checkout and is named by
            # ODYSSEUS_DATA_DIR (the household deployment's -DataRoot). The tool must find it from the variable.
            self.data = root / "AppData" / "Odysseus" / "Misumi"
            self.data.mkdir(parents=True)
            monkeypatch.setenv("ODYSSEUS_DATA_DIR", str(self.data))
            self.backup = load_script("odysseus-backup")
            assert self.backup._DATA_DIR == self.data
        else:
            self.data = root / "data"
            self.data.mkdir()
            monkeypatch.delenv("ODYSSEUS_DATA_DIR", raising=False)
            self.backup = load_script("odysseus-backup")
            monkeypatch.setattr(self.backup, "_REPO_ROOT", root)
            monkeypatch.setattr(self.backup, "_DATA_DIR", self.data)
        self.db_path = self.data / "app.db"
        monkeypatch.setattr(self.backup, "_BACKUP_DIR", root / "backups")
        self.engine, self.factory = _factory(self.db_path)

    # -- the real tool -----------------------------------------------------------------
    def _run(self, fn, **kwargs):
        fn(SimpleNamespace(pretty=False, **kwargs))
        return json.loads(self.capsys.readouterr().out.strip().splitlines()[-1])

    def snapshot(self):
        out = self.root / "off-box" / "snapshot.tar.gz"  # outside data/, as the tool requires
        res = self._run(self.backup.cmd_snapshot, out=str(out),
                        include_research=False, include_attachments=False)
        assert res["ok"] is True
        return out

    def verify(self, path):
        return self._run(self.backup.cmd_verify, path=str(path))

    def restore(self, path):
        self.engine.dispose()
        return self._run(self.backup.cmd_restore, path=str(path), yes=True)

    def reopen(self):
        self.engine.dispose()
        self.engine, self.factory = _factory(self.db_path)

    def destroy_live_archive(self):
        """Simulate losing the live database file (and any SQLite side files)."""
        self.engine.dispose()
        for suffix in ("", "-wal", "-shm", "-journal"):
            target = self.db_path.with_name(self.db_path.name + suffix)
            if target.exists():
                target.unlink()

    # -- fixture data ------------------------------------------------------------------
    def seed(self):
        with self.factory() as db:
            svc.set_policy(db, "alice", transcript_archive=True, transcript_retention_mode="permanent")
            svc.set_policy(db, "bob", transcript_archive=True, transcript_retention_days=14)
            for i in range(ALICE_COUNT):
                svc.ingest_event(
                    db, owner="alice", event_id=f"drill-alice-{i:02d}",
                    text=f"kitchen note {i}: café ✓ reorder oat milk",
                    capture_mode="ambient", source="audio-upload",
                    stt_provider="local", stt_model="base.en", stt_host="desktop-in7o23d",
                    stt_latency_ms=700 + i,
                )
            for i in range(BOB_COUNT):
                svc.ingest_event(
                    db, owner="bob", event_id=f"drill-bob-{i:02d}",
                    text=f"bob's own line {i}", capture_mode="ptt", source="audio-upload",
                    stt_provider="local", stt_model="base.en", stt_host="desktop-in7o23d",
                )
            # A row far older than any finite window: only a permanent policy keeps it.
            svc.ingest_event(
                db, owner="alice", event_id=OLD_EVENT_ID, text="a note from over a year ago",
                capture_mode="ambient", now=utcnow_naive() - timedelta(days=400),
            )


@pytest.fixture(params=["in-tree", "external"])
def drill(request, tmp_path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    d = Drill(root, monkeypatch, capsys, external=request.param == "external")
    d.seed()
    yield d
    d.engine.dispose()


def test_restore_is_row_for_row_identical(drill):
    before_events, before_policies = _dump(drill.factory)
    assert len(before_events) == ALICE_COUNT + BOB_COUNT + 1

    archive = drill.snapshot()
    assert drill.verify(archive)["ok"] is True

    drill.destroy_live_archive()
    assert not drill.db_path.exists()
    restored = drill.restore(archive)
    assert restored["ok"] is True
    drill.reopen()

    after_events, after_policies = _dump(drill.factory)
    assert after_events == before_events  # every column, including seq and persisted_at
    assert after_policies == before_policies
    assert _digest(after_events) == _digest(before_events)
    with drill.factory() as db:
        assert db.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
        assert db.execute(text("PRAGMA foreign_key_check")).all() == []


def test_owner_isolation_and_attribution_survive_restore(drill):
    archive = drill.snapshot()
    drill.destroy_live_archive()
    drill.restore(archive)
    drill.reopen()
    with drill.factory() as db:
        alice = svc.query_events(db, "alice", limit=200)["events"]
        bob = svc.query_events(db, "bob", limit=200)["events"]
    alice_ids = {e["event_id"] for e in alice}
    bob_ids = {e["event_id"] for e in bob}
    assert len(alice_ids) == ALICE_COUNT + 1 and len(bob_ids) == BOB_COUNT
    assert alice_ids.isdisjoint(bob_ids)
    assert all(e["event_id"].startswith("drill-bob-") for e in bob)
    attributed = [e for e in alice if e["event_id"].startswith("drill-alice-") and e["event_id"] != OLD_EVENT_ID]
    assert attributed and all(e["stt"]["host"] == "desktop-in7o23d" for e in attributed)


def test_permanent_policy_and_old_row_survive_restore_and_are_not_purged(drill):
    archive = drill.snapshot()
    drill.destroy_live_archive()
    drill.restore(archive)
    drill.reopen()
    with drill.factory() as db:
        assert svc.get_policy(db, "alice")["transcript_retention_mode"] == "permanent"
        assert svc.get_policy(db, "bob")["transcript_retention_mode"] == "finite"
        assert svc.purge_expired(db, "alice") == 0
        assert OLD_EVENT_ID in {e["event_id"] for e in svc.query_events(db, "alice", limit=200)["events"]}
        # A stray days-only change must still not turn the restored permanent archive into a deleting one.
        assert svc.set_policy(db, "alice", transcript_retention_days=14)["transcript_retention_mode"] == "permanent"


def test_replay_after_restore_is_idempotent_and_conflicts_are_still_refused(drill):
    before_events, _ = _dump(drill.factory)
    archive = drill.snapshot()
    drill.destroy_live_archive()
    drill.restore(archive)
    drill.reopen()

    with drill.factory() as db:
        # The interface box replays everything it still holds, by the same event ids.
        for i in range(ALICE_COUNT):
            res = svc.ingest_event(db, owner="alice", event_id=f"drill-alice-{i:02d}",
                                   text=f"kitchen note {i}: café ✓ reorder oat milk")
            assert res.deduplicated is True
        for i in range(BOB_COUNT):
            res = svc.ingest_event(db, owner="bob", event_id=f"drill-bob-{i:02d}",
                                   text=f"bob's own line {i}", capture_mode="ptt")
            assert res.deduplicated is True
        # Same id, different text is never overwritten, even after a restore.
        with pytest.raises(svc.EventConflict):
            svc.ingest_event(db, owner="alice", event_id="drill-alice-00", text="something else entirely")
    after_events, _ = _dump(drill.factory)
    assert after_events == before_events  # replay changed nothing

    # The unique key itself came back with the schema: a raw duplicate insert is refused by the database.
    with drill.factory() as db:
        db.add(TranscriptEvent(owner="alice", domain="misumi", event_id="drill-alice-01", text="dup",
                               text_sha256="x", capture_mode="ambient", source="text-event",
                               persisted_at=utcnow_naive(), state="persisted"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_recovery_point_is_the_snapshot_and_the_stash_allows_rollback(drill):
    archive = drill.snapshot()
    with drill.factory() as db:
        svc.ingest_event(db, owner="alice", event_id="drill-after-snapshot",
                         text="said after the snapshot was taken", capture_mode="ambient")
    assert len(_dump(drill.factory)[0]) == ALICE_COUNT + BOB_COUNT + 2

    result = drill.restore(archive)
    drill.reopen()

    # Stated recovery point: the write made after the snapshot is not in the restored archive...
    with drill.factory() as db:
        assert svc.find_event(db, "alice", "misumi", "drill-after-snapshot") is None
    assert len(_dump(drill.factory)[0]) == ALICE_COUNT + BOB_COUNT + 1

    # ...but the previous data directory was stashed untouched, so the restore can be rolled back.
    stash = result["previous_data_stashed_at"]
    assert stash and ".before-restore-" in stash
    stashed_engine, stashed_factory = _factory(f"{stash}/app.db")
    try:
        with stashed_factory() as db:
            assert svc.find_event(db, "alice", "misumi", "drill-after-snapshot") is not None
    finally:
        stashed_engine.dispose()

    # ...and the client's replay of that lost event persists it exactly once (it was never stored here).
    with drill.factory() as db:
        first = svc.ingest_event(db, owner="alice", event_id="drill-after-snapshot",
                                 text="said after the snapshot was taken", capture_mode="ambient")
        again = svc.ingest_event(db, owner="alice", event_id="drill-after-snapshot",
                                 text="said after the snapshot was taken", capture_mode="ambient")
    assert first.deduplicated is False and again.deduplicated is True
    assert len(_dump(drill.factory)[0]) == ALICE_COUNT + BOB_COUNT + 2

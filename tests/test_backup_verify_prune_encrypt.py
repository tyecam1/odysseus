"""odysseus-backup: self-verification, manifests, exclusions, retention pruning and the age encryption hook.

Programme: ``misumi-long-horizon-programme`` Phase 4 (recoverability). The snapshot of a permanent transcript
archive must never be reported as good unless it was read back and its databases integrity-checked; a restore
must refuse a bad archive before it touches live data. ``age`` is replaced by a shim in these tests: the hook's
contract (fail closed, plaintext never at the output path, identity required to restore) is tested here, the
real ``age`` binary is not.
"""

import json
import os
import sqlite3
import stat
import sys
import tarfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.helpers.cli_loader import load_script

needs_posix = pytest.mark.skipif(sys.platform == "win32", reason="uses a POSIX shebang shim for age")


def _load(monkeypatch, data_dir):
    monkeypatch.setenv("ODYSSEUS_DATA_DIR", str(data_dir))
    return load_script("odysseus-backup")


def _args(**kw):
    base = dict(pretty=False, out=None, include_research=False, include_attachments=False)
    base.update(kw)
    return SimpleNamespace(**base)


def _run(capsys, fn, **kw):
    fn(_args(**kw) if "path" not in kw and "dir" not in kw else SimpleNamespace(pretty=False, **kw))
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _refused(capsys, fn, **kw):
    with pytest.raises(SystemExit):
        fn(SimpleNamespace(pretty=False, **kw) if "path" in kw or "dir" in kw else _args(**kw))
    return capsys.readouterr().err


def _make_db(path: Path, rows: int = 40):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    with conn:
        conn.execute("CREATE TABLE t (k INTEGER PRIMARY KEY, v TEXT)")
        conn.executemany("INSERT INTO t (v) VALUES (?)", [("row %d " % i + "x" * 400,) for i in range(rows)])
    conn.close()


@pytest.fixture()
def world(tmp_path, monkeypatch):
    data = tmp_path / "AppData" / "Misumi"
    _make_db(data / "app.db")
    (data / ".app_key").write_bytes(b"k" * 44)
    (data / "settings.json").write_text('{"a": 1}', encoding="utf-8")
    (data / "stray.db").write_bytes(b"not a sqlite database")
    for rel in ("cache/c.bin", "tts_cache/t.wav", "stt-tmp/s.wav", "models/m.bin",
                "chroma/idx.bin", "memory_vectors/v.bin", "rag/r.bin", "logs/a.log", "skills/cache/keep.txt"):
        f = data / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"data")
    backup = _load(monkeypatch, data)
    monkeypatch.setattr(backup, "_BACKUP_DIR", tmp_path / "backups")
    return SimpleNamespace(tmp=tmp_path, data=data, backup=backup, out=tmp_path / "off-box" / "snap.tar.gz")


def _names(archive: Path):
    with tarfile.open(archive, "r:gz") as tar:
        return {m.name for m in tar.getmembers() if m.isfile()}


# ---- snapshot verifies itself and writes a manifest ---------------------------------------------

def test_snapshot_reports_verified_with_a_matching_manifest(world, capsys):
    res = _run(capsys, world.backup.cmd_snapshot, out=str(world.out))
    assert res["verified"] is True and res["encrypted"] is False
    assert {d["name"] for d in res["databases"]} == {"data/app.db", "data/stray.db"}
    manifest = json.loads(Path(res["manifest"]).read_text(encoding="utf-8"))
    assert manifest["archive_sha256"] == res["sha256"] == world.backup._sha256(world.out)
    assert manifest["archive_bytes"] == world.out.stat().st_size and manifest["verified"] is True
    app = next(d for d in manifest["databases"] if d["name"] == "data/app.db")
    assert app["integrity"] == "ok" and app["tables"] == {"t": 40}
    assert next(d for d in manifest["databases"] if d["name"] == "data/stray.db")["integrity"] == "not-sqlite"
    assert manifest["excluded"] == [] and manifest["encrypted"] is False


def test_the_old_call_shape_without_the_new_arguments_still_works(world, capsys):
    ns = SimpleNamespace(pretty=False, out=str(world.out), include_research=False, include_attachments=False)
    world.backup.cmd_snapshot(ns)
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["ok"] is True


# ---- exclusions ---------------------------------------------------------------------------------

def test_a_bare_exclude_name_matches_only_the_top_level_directory(world, capsys):
    _run(capsys, world.backup.cmd_snapshot, out=str(world.out), exclude=["cache"])
    names = _names(world.out)
    assert "data/cache/c.bin" not in names
    assert "data/skills/cache/keep.txt" in names  # a nested directory that merely shares the name is kept


def test_a_path_prefix_exclude_matches_that_subtree(world, capsys):
    _run(capsys, world.backup.cmd_snapshot, out=str(world.out), exclude=["skills/cache"])
    names = _names(world.out)
    assert "data/skills/cache/keep.txt" not in names and "data/cache/c.bin" in names


def test_exclude_rebuildable_skips_only_the_listed_caches_and_never_indexes_or_state(world, capsys):
    res = _run(capsys, world.backup.cmd_snapshot, out=str(world.out), exclude_rebuildable=True)
    names = _names(world.out)
    for gone in ("data/cache/c.bin", "data/tts_cache/t.wav", "data/stt-tmp/s.wav", "data/models/m.bin"):
        assert gone not in names
    for kept in ("data/app.db", "data/.app_key", "data/settings.json", "data/chroma/idx.bin",
                 "data/memory_vectors/v.bin", "data/rag/r.bin", "data/logs/a.log"):
        assert kept in names, kept
    assert set(res["excluded"]) == {"cache", "tts_cache", "stt-tmp", "models"}


# ---- verification catches what the old tool would have reported as success ------------------------

def _corrupting_copy(real_copy):
    def copy(src, dst):
        real_copy(src, dst)
        if dst.name == "app.db":
            raw = bytearray(dst.read_bytes())
            for i in range(len(raw) // 2, len(raw) // 2 + 4096):
                raw[i] = 0xFF  # a torn page in the middle, header intact
            dst.write_bytes(bytes(raw))
    return copy


def test_a_corrupt_database_in_the_snapshot_is_detected_deleted_and_the_command_fails(world, capsys, monkeypatch):
    monkeypatch.setattr(world.backup, "_sqlite_safe_copy", _corrupting_copy(world.backup._sqlite_safe_copy))
    err = _refused(capsys, world.backup.cmd_snapshot, out=str(world.out))
    assert "failed verification and was deleted" in err and "data/app.db" in err
    assert not world.out.exists()
    assert not Path(str(world.out) + ".manifest.json").exists()


def test_a_real_sqlite_database_is_never_raw_copied_when_the_backup_api_fails(world, monkeypatch):
    class Conn:
        def backup(self, other):
            raise sqlite3.OperationalError("database is locked")

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    shim = SimpleNamespace(connect=lambda p: Conn(), OperationalError=sqlite3.OperationalError,
                           DatabaseError=sqlite3.DatabaseError)
    monkeypatch.setattr(world.backup, "sqlite3", shim)
    with pytest.raises(sqlite3.OperationalError):
        world.backup.cmd_snapshot(_args(out=str(world.out)))
    assert not world.out.exists()  # the old behaviour silently fell back to a byte copy and reported ok


def test_a_stray_non_sqlite_db_file_is_still_copied_as_bytes(world, capsys):
    _run(capsys, world.backup.cmd_snapshot, out=str(world.out))
    with tarfile.open(world.out, "r:gz") as tar:
        assert tar.extractfile("data/stray.db").read() == b"not a sqlite database"


# ---- restore refuses a bad archive before touching live data ---------------------------------------

def _tamper_database(world, source: Path, dest: Path):
    """Rewrite the archive with a database whose pages are damaged (header intact), no manifest."""
    with tarfile.open(source, "r:gz") as tin, tarfile.open(dest, "w:gz") as tout:
        for m in tin.getmembers():
            data = tin.extractfile(m).read() if m.isfile() else None
            if m.name == "data/app.db":
                raw = bytearray(data)
                for i in range(len(raw) // 2, len(raw) // 2 + 4096):
                    raw[i] = 0xFF
                data = bytes(raw)
                m.size = len(data)
            if data is None:
                tout.addfile(m)
            else:
                import io
                tout.addfile(m, io.BytesIO(data))


def test_restore_refuses_an_archive_with_a_damaged_database_and_changes_nothing(world, capsys):
    _run(capsys, world.backup.cmd_snapshot, out=str(world.out))
    bad = world.tmp / "bad.tar.gz"
    _tamper_database(world, world.out, bad)
    before = (world.data / "app.db").read_bytes()
    err = _refused(capsys, world.backup.cmd_restore, path=str(bad), yes=True)
    assert "refusing to restore" in err and "nothing was changed" in err
    assert (world.data / "app.db").read_bytes() == before
    assert not list(world.data.parent.glob("*before-restore*"))  # never even stashed


def test_restore_refuses_an_archive_that_no_longer_matches_its_manifest(world, capsys):
    _run(capsys, world.backup.cmd_snapshot, out=str(world.out))
    with open(world.out, "ab") as f:
        f.write(b"\0")  # modified after it was written
    err = _refused(capsys, world.backup.cmd_restore, path=str(world.out), yes=True)
    assert "does not match its manifest" in err


def test_restore_refuses_a_truncated_archive(world, capsys):
    _run(capsys, world.backup.cmd_snapshot, out=str(world.out))
    Path(str(world.out) + ".manifest.json").unlink()
    raw = world.out.read_bytes()
    world.out.write_bytes(raw[: len(raw) // 2])
    err = _refused(capsys, world.backup.cmd_restore, path=str(world.out), yes=True)
    assert "refusing to restore" in err and "archive unreadable" in err


def test_restore_of_a_good_archive_still_round_trips_and_reports_databases_verified(world, capsys):
    _run(capsys, world.backup.cmd_snapshot, out=str(world.out))
    conn = sqlite3.connect(str(world.data / "app.db"))
    with conn:
        conn.execute("DELETE FROM t")
    conn.close()
    res = _run(capsys, world.backup.cmd_restore, path=str(world.out), yes=True)
    assert res["databases_verified"] == 2
    conn = sqlite3.connect(str(world.data / "app.db"))
    try:
        assert conn.execute("SELECT count(*) FROM t").fetchone()[0] == 40
    finally:
        conn.close()
    stash = Path(res["previous_data_stashed_at"])
    assert stash.name.startswith("Misumi.before-restore-")


def test_a_failure_during_extraction_names_the_intact_previous_data(world, capsys, monkeypatch):
    _run(capsys, world.backup.cmd_snapshot, out=str(world.out))

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(world.backup, "_extract_restore_members", boom)
    err = _refused(capsys, world.backup.cmd_restore, path=str(world.out), yes=True)
    assert "extract failed: disk full" in err and "previous data is intact at" in err
    stash = next(world.data.parent.glob("Misumi.before-restore-*"))
    assert (stash / "app.db").exists()


# ---- verify -------------------------------------------------------------------------------------

def test_verify_default_output_is_unchanged_and_reports_the_manifest_check(world, capsys):
    _run(capsys, world.backup.cmd_snapshot, out=str(world.out))
    res = _run(capsys, world.backup.cmd_verify, path=str(world.out))
    assert res["ok"] is True and res["first"].startswith("data") and res["manifest_checked"] is True
    assert "databases" not in res


def test_verify_deep_reports_each_database_and_fails_on_damage(world, capsys):
    _run(capsys, world.backup.cmd_snapshot, out=str(world.out))
    res = _run(capsys, world.backup.cmd_verify, path=str(world.out), deep=True)
    assert {d["name"]: d["integrity"] for d in res["databases"]} == {"data/app.db": "ok", "data/stray.db": "not-sqlite"}
    bad = world.tmp / "bad.tar.gz"
    _tamper_database(world, world.out, bad)
    assert "failed verification" in _refused(capsys, world.backup.cmd_verify, path=str(bad), deep=True)


def test_verify_of_an_archive_without_a_manifest_does_not_claim_it_checked_one(world, capsys):
    _run(capsys, world.backup.cmd_snapshot, out=str(world.out))
    Path(str(world.out) + ".manifest.json").unlink()
    assert "manifest_checked" not in _run(capsys, world.backup.cmd_verify, path=str(world.out))


def test_list_hides_manifests(world, capsys):
    backups = world.tmp / "backups"
    backups.mkdir()
    (backups / "a.tar.gz").write_bytes(b"x")
    (backups / "a.tar.gz.manifest.json").write_text("{}")
    out = _run(capsys, world.backup.cmd_list)
    assert [e["name"] for e in out] == ["a.tar.gz"]


# ---- retention ----------------------------------------------------------------------------------

def _snap_names(directory: Path, stamps):
    for s in stamps:
        for suffix in ("", ".manifest.json"):
            (directory / f"odysseus-backup-{s}.tar.gz{suffix}").write_bytes(b"x")


STAMPS = {
    "A": "20261002-120000",  # Fri W40, newest
    "B": "20261002-080000",  # same day, older
    "C": "20261001-120000",  # Thu W40
    "D": "20260930-120000",  # Wed W40, newest of September
    "E": "20260923-120000",  # Wed W39
    "F": "20260901-120000",  # September, older
    "G": "20260815-120000",  # August
}


def test_prune_keeps_the_newest_of_each_period_and_deletes_the_rest_with_their_manifests(world, capsys):
    d = world.tmp / "keep"
    d.mkdir()
    _snap_names(d, STAMPS.values())
    (d / "notes.txt").write_text("not a snapshot")
    (d / "odysseus-backup-garbage.tar.gz").write_bytes(b"x")  # does not match the strict name pattern
    res = _run(capsys, world.backup.cmd_prune, dir=str(d), keep_daily=2, keep_weekly=2, keep_monthly=2, yes=True)
    kept = {k["name"]: k["because"] for k in res["kept"]}
    assert set(kept) == {f"odysseus-backup-{STAMPS[k]}.tar.gz" for k in "ACDE"}
    assert kept[f"odysseus-backup-{STAMPS['A']}.tar.gz"] == ["newest", "daily", "weekly", "monthly"]
    assert kept[f"odysseus-backup-{STAMPS['C']}.tar.gz"] == ["daily"]
    assert kept[f"odysseus-backup-{STAMPS['E']}.tar.gz"] == ["weekly"]
    assert kept[f"odysseus-backup-{STAMPS['D']}.tar.gz"] == ["monthly"]
    assert set(res["deleted"]) == {f"odysseus-backup-{STAMPS[k]}.tar.gz" for k in "BFG"}
    left = {p.name for p in d.iterdir()}
    assert {f"odysseus-backup-{STAMPS[k]}.tar.gz" + s for k in "ACDE" for s in ("", ".manifest.json")} <= left
    assert not any(STAMPS[k] in n for k in "BFG" for n in left)  # manifests went with them
    assert {"notes.txt", "odysseus-backup-garbage.tar.gz"} <= left  # never touched


def test_prune_is_a_dry_run_unless_told_otherwise(world, capsys):
    d = world.tmp / "keep"
    d.mkdir()
    _snap_names(d, STAMPS.values())
    before = {p.name for p in d.iterdir()}
    res = _run(capsys, world.backup.cmd_prune, dir=str(d), keep_daily=1, keep_weekly=1, keep_monthly=1, yes=False)
    assert res["dry_run"] is True and res["would_delete"]
    assert {p.name for p in d.iterdir()} == before


def test_prune_never_deletes_the_newest_snapshot_even_with_everything_set_to_zero(world, capsys):
    d = world.tmp / "keep"
    d.mkdir()
    _snap_names(d, STAMPS.values())
    res = _run(capsys, world.backup.cmd_prune, dir=str(d), keep_daily=0, keep_weekly=0, keep_monthly=0, yes=True)
    assert [k["name"] for k in res["kept"]] == [f"odysseus-backup-{STAMPS['A']}.tar.gz"]
    assert (d / f"odysseus-backup-{STAMPS['A']}.tar.gz").exists()


def test_prune_on_an_empty_or_missing_directory(world, capsys):
    d = world.tmp / "empty"
    d.mkdir()
    res = _run(capsys, world.backup.cmd_prune, dir=str(d), keep_daily=7, keep_weekly=4, keep_monthly=12, yes=True)
    assert res["kept"] == [] and res["deleted"] == []
    assert "no directory" in _refused(capsys, world.backup.cmd_prune, dir=str(world.tmp / "nope"),
                                      keep_daily=7, keep_weekly=4, keep_monthly=12, yes=True)


def test_gfs_selection_across_a_year_keeps_a_bounded_number(world):
    day = datetime(2026, 10, 2, 12)
    snaps = [(day - timedelta(days=i), Path(f"s{i}")) for i in range(400)]  # newest first
    keep = world.backup._gfs_keep(snaps, 7, 4, 12)
    assert 12 <= len(keep) <= 7 + 4 + 12 + 1
    assert Path("s0") in keep and Path("s399") not in keep


# ---- encryption hook (age shim) -----------------------------------------------------------------

AGE_SHIM = """#!/usr/bin/env python3
import os, sys
a = sys.argv[1:]
log = os.environ.get("FAKE_AGE_LOG")
if log:
    open(log, "a").write(" ".join(a) + "\\n")
if os.environ.get("FAKE_AGE_FAIL"):
    sys.stderr.write("boom\\n")
    sys.exit(3)
def opt(flag):
    return a[a.index(flag) + 1]
out, src = opt("-o"), a[-1]
data = open(src, "rb").read()
if "-d" in a:
    if not os.path.exists(opt("-i")):
        sys.stderr.write("no identity\\n"); sys.exit(1)
    assert data.startswith(b"FAKE-AGE\\n"), "not an age file"
    open(out, "wb").write(bytes(b ^ 0x5A for b in data[9:]))
else:
    if not os.path.exists(opt("-R")):
        sys.stderr.write("no recipients\\n"); sys.exit(1)
    open(out, "wb").write(b"FAKE-AGE\\n" + bytes(b ^ 0x5A for b in data))
"""


@pytest.fixture()
def age(world, monkeypatch):
    bindir = world.tmp / "bin"
    bindir.mkdir()
    shim = bindir / "age"
    shim.write_text(AGE_SHIM)
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    log = world.tmp / "age.log"
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_AGE_LOG", str(log))
    recipients = world.tmp / "recipients.txt"
    recipients.write_text("age1fake")
    identity = world.tmp / "identity.txt"
    identity.write_text("AGE-SECRET-KEY-FAKE")
    return SimpleNamespace(log=log, recipients=recipients, identity=identity)


@needs_posix
def test_encrypted_snapshot_never_leaves_plaintext_at_the_output_path(world, age, capsys):
    res = _run(capsys, world.backup.cmd_snapshot, out=str(world.out), encrypt_recipients=str(age.recipients))
    out = Path(res["path"])
    assert out.name == "snap.tar.gz.age" and res["encrypted"] is True and res["verified"] is True
    assert out.read_bytes().startswith(b"FAKE-AGE\n")
    assert not world.out.exists()  # no plaintext snap.tar.gz anywhere in the output directory
    assert sorted(p.name for p in out.parent.iterdir()) == ["snap.tar.gz.age", "snap.tar.gz.age.manifest.json"]
    manifest = json.loads(Path(res["manifest"]).read_text(encoding="utf-8"))
    assert manifest["encrypted"] is True and manifest["archive_sha256"] == world.backup._sha256(out)
    assert manifest["plaintext_sha256"] and manifest["plaintext_sha256"] != manifest["archive_sha256"]
    assert "-R" in age.log.read_text() and str(age.recipients) in age.log.read_text()
    # The plaintext tarball handed to age is a different file in a different (temporary) directory, so the
    # plaintext never exists under the output name, even transiently.
    call = age.log.read_text().strip().splitlines()[-1].split()
    plain_in, enc_out = Path(call[-1]), Path(call[call.index("-o") + 1])
    assert enc_out == out and plain_in != out and plain_in.parent != out.parent


@needs_posix
def test_encrypted_round_trip_needs_the_identity_and_restores_the_data(world, age, capsys):
    res = _run(capsys, world.backup.cmd_snapshot, out=str(world.out), encrypt_recipients=str(age.recipients))
    enc = res["path"]
    shallow = _run(capsys, world.backup.cmd_verify, path=enc)
    assert shallow["encrypted"] is True and shallow["manifest_checked"] is True and "checksum" in shallow["note"]
    deep = _run(capsys, world.backup.cmd_verify, path=enc, deep=True, decrypt_identity=str(age.identity))
    assert {d["name"] for d in deep["databases"]} == {"data/app.db", "data/stray.db"}
    assert "needs --decrypt-identity" in _refused(capsys, world.backup.cmd_verify, path=enc, deep=True)

    assert "pass --decrypt-identity" in _refused(capsys, world.backup.cmd_restore, path=enc, yes=True)
    conn = sqlite3.connect(str(world.data / "app.db"))
    with conn:
        conn.execute("DELETE FROM t")
    conn.close()
    _run(capsys, world.backup.cmd_restore, path=enc, yes=True, decrypt_identity=str(age.identity))
    conn = sqlite3.connect(str(world.data / "app.db"))
    try:
        assert conn.execute("SELECT count(*) FROM t").fetchone()[0] == 40
    finally:
        conn.close()


@needs_posix
def test_requesting_encryption_without_age_fails_closed_before_writing_anything(world, capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    recipients = world.tmp / "r.txt"
    recipients.write_text("x")
    err = _refused(capsys, world.backup.cmd_snapshot, out=str(world.out), encrypt_recipients=str(recipients))
    assert "refusing to write an unencrypted snapshot" in err
    assert not world.out.parent.exists() or not list(world.out.parent.iterdir())


@needs_posix
def test_a_missing_recipients_file_is_refused(world, age, capsys):
    err = _refused(capsys, world.backup.cmd_snapshot, out=str(world.out), encrypt_recipients=str(world.tmp / "nope.txt"))
    assert "no recipients file" in err


@needs_posix
def test_an_age_failure_leaves_no_output_and_fails(world, age, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_AGE_FAIL", "1")
    err = _refused(capsys, world.backup.cmd_snapshot, out=str(world.out), encrypt_recipients=str(age.recipients))
    assert "age failed (exit 3)" in err and "boom" in err
    out_dir = world.out.parent
    assert not out_dir.exists() or not [p for p in out_dir.iterdir() if not p.name.endswith(".tmp")]

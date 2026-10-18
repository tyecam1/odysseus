"""odysseus-backup: honouring a deletion (``prune --all``) and keeping the age private identity off the host."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.helpers.cli_loader import load_script


def _load(monkeypatch, data_dir):
    monkeypatch.setenv("ODYSSEUS_DATA_DIR", str(data_dir))
    return load_script("odysseus-backup")


def _run(capsys, fn, **kw):
    fn(SimpleNamespace(pretty=False, **kw))
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _snapshots(directory: Path, stamps):
    for s in stamps:
        for suffix in ("", ".manifest.json"):
            (directory / f"odysseus-backup-{s}.tar.gz{suffix}").write_bytes(b"x")


STAMPS = ["20261002-120000", "20261001-120000", "20260930-120000"]


def test_prune_all_dry_run_lists_every_snapshot_and_deletes_nothing(tmp_path, monkeypatch, capsys):
    backup = _load(monkeypatch, tmp_path / "data")
    _snapshots(tmp_path, STAMPS)
    before = {p.name for p in tmp_path.iterdir()}
    res = _run(capsys, backup.cmd_prune, dir=str(tmp_path), keep_daily=7, keep_weekly=4, keep_monthly=12, all=True, yes=False)
    assert res["dry_run"] is True and res["kept"] == []
    assert sorted(res["would_delete"]) == sorted(f"odysseus-backup-{s}.tar.gz" for s in STAMPS)
    assert {p.name for p in tmp_path.iterdir()} == before


def test_prune_all_yes_deletes_every_snapshot_and_manifest_including_the_newest(tmp_path, monkeypatch, capsys):
    backup = _load(monkeypatch, tmp_path / "data")
    _snapshots(tmp_path, STAMPS)
    (tmp_path / "notes.txt").write_text("keep")
    (tmp_path / "odysseus-backup-garbage.tar.gz").write_bytes(b"x")
    res = _run(capsys, backup.cmd_prune, dir=str(tmp_path), keep_daily=7, keep_weekly=4, keep_monthly=12, all=True, yes=True)
    assert len(res["deleted"]) == 3 and res["kept"] == []
    assert {p.name for p in tmp_path.iterdir()} == {"notes.txt", "odysseus-backup-garbage.tar.gz"}


def test_without_all_the_newest_snapshot_is_still_always_kept(tmp_path, monkeypatch, capsys):
    backup = _load(monkeypatch, tmp_path / "data")
    _snapshots(tmp_path, STAMPS)
    res = _run(capsys, backup.cmd_prune, dir=str(tmp_path), keep_daily=0, keep_weekly=0, keep_monthly=0, yes=True)
    assert [k["name"] for k in res["kept"]] == ["odysseus-backup-20261002-120000.tar.gz"]


def _snapshot_args(tmp_path, recipients):
    return SimpleNamespace(pretty=False, out=str(tmp_path / "off" / "s.tar.gz"), include_research=False,
                           include_attachments=False, encrypt_recipients=str(recipients))


def test_a_recipients_file_holding_a_private_identity_is_refused_before_anything_else(tmp_path, monkeypatch, capsys):
    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.json").write_text("{}")
    backup = _load(monkeypatch, data)
    monkeypatch.setattr(backup, "_BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))  # age is absent: the identity check must come first
    bad = tmp_path / "recipients.txt"
    bad.write_text("age1publicrecipient\nAGE-SECRET-KEY-1ABCDEF\n")
    with pytest.raises(SystemExit):
        backup.cmd_snapshot(_snapshot_args(tmp_path, bad))
    err = capsys.readouterr().err
    assert "AGE-SECRET-KEY" in err and "password manager" in err
    assert "not installed" not in err  # the identity check ran before the age lookup
    assert not (tmp_path / "off").exists()  # nothing was written


def test_a_public_only_recipients_file_passes_the_identity_check(tmp_path, monkeypatch):
    backup = _load(monkeypatch, tmp_path / "data")
    ok = tmp_path / "recipients.txt"
    ok.write_text("# personal off-site key\nage1publicrecipient0123456789\n")
    backup._check_recipients_public(ok)  # does not raise
    with pytest.raises(SystemExit):
        backup._check_recipients_public(tmp_path / "missing.txt")

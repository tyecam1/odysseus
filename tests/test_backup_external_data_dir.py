"""``scripts/odysseus-backup`` must back up and restore the directory the runtime actually uses.

The runtime reads its data directory from ``ODYSSEUS_DATA_DIR`` (``src/constants.py``). The household
deployment on the home host sets it (``odysseus-host.ps1 -DataRoot``), so its data lives outside the release
checkout. The tool used to hard-code ``<repo>/data``, so run from a release checkout it would have snapshotted
the checkout's own, empty ``data/`` and reported success. These tests pin the corrected behaviour.
"""

import json
import os
import sqlite3
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.helpers.cli_loader import load_script


def _load(monkeypatch, data_dir=None):
    if data_dir is None:
        monkeypatch.delenv("ODYSSEUS_DATA_DIR", raising=False)
    else:
        monkeypatch.setenv("ODYSSEUS_DATA_DIR", str(data_dir))
    return load_script("odysseus-backup")


def _run(capsys, fn, **kwargs):
    fn(SimpleNamespace(pretty=False, **kwargs))
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _populate(data_dir: Path, marker: str):
    data_dir.mkdir(parents=True)
    conn = sqlite3.connect(str(data_dir / "app.db"))
    with conn:
        conn.execute("CREATE TABLE t (k TEXT PRIMARY KEY, v TEXT)")
        conn.execute("INSERT INTO t VALUES ('marker', ?)", (marker,))
    conn.close()
    (data_dir / "memory.json").write_text(json.dumps({"marker": marker}), encoding="utf-8")


def _marker(data_dir: Path) -> str:
    conn = sqlite3.connect(str(data_dir / "app.db"))
    try:
        return conn.execute("SELECT v FROM t WHERE k='marker'").fetchone()[0]
    finally:
        conn.close()


def test_data_dir_defaults_to_the_repo_data_directory_when_unset(monkeypatch):
    backup = _load(monkeypatch, None)
    assert backup._DATA_DIR == backup._REPO_ROOT / "data"


def test_odysseus_data_dir_overrides_the_default(monkeypatch, tmp_path):
    external = tmp_path / "AppData" / "Misumi"
    backup = _load(monkeypatch, external)
    assert backup._DATA_DIR == external
    assert backup._DATA_DIR != backup._REPO_ROOT / "data"


def test_snapshot_and_restore_round_trip_an_out_of_tree_data_directory(monkeypatch, tmp_path, capsys):
    external = tmp_path / "AppData" / "Misumi"  # deliberately not named "data"
    _populate(external, "before")
    backup = _load(monkeypatch, external)
    monkeypatch.setattr(backup, "_BACKUP_DIR", tmp_path / "backups")
    stashes_in_checkout_before = set(backup._REPO_ROOT.glob("*before-restore*"))

    archive = tmp_path / "off-box" / "snapshot.tar.gz"
    snap = _run(capsys, backup.cmd_snapshot, out=str(archive), include_research=False, include_attachments=False)
    assert snap["ok"] is True
    with tarfile.open(archive, "r:gz") as tar:
        names = {m.name for m in tar.getmembers() if m.isfile()}
    assert names == {"data/app.db", "data/memory.json"}  # layout is data/... whatever the directory is called

    # The live data is changed after the snapshot; restoring must bring back the snapshot and keep the old state.
    conn = sqlite3.connect(str(external / "app.db"))
    with conn:
        conn.execute("UPDATE t SET v='after' WHERE k='marker'")
    conn.close()
    restored = _run(capsys, backup.cmd_restore, path=str(archive), yes=True)

    assert _marker(external) == "before"
    assert json.loads((external / "memory.json").read_text(encoding="utf-8")) == {"marker": "before"}
    stash = Path(restored["previous_data_stashed_at"])
    assert stash.parent == external.parent and stash.name.startswith("Misumi.before-restore-")
    assert _marker(stash) == "after"
    # Nothing was written into the release checkout.
    assert set(backup._REPO_ROOT.glob("*before-restore*")) == stashes_in_checkout_before


def test_restore_into_a_missing_out_of_tree_directory_recreates_it(monkeypatch, tmp_path, capsys):
    external = tmp_path / "AppData" / "Misumi"
    _populate(external, "kept")
    backup = _load(monkeypatch, external)
    monkeypatch.setattr(backup, "_BACKUP_DIR", tmp_path / "backups")
    archive = tmp_path / "off-box" / "snapshot.tar.gz"
    _run(capsys, backup.cmd_snapshot, out=str(archive), include_research=False, include_attachments=False)

    os.rename(external, tmp_path / "lost")  # the live data directory is gone
    restored = _run(capsys, backup.cmd_restore, path=str(archive), yes=True)
    assert restored["previous_data_stashed_at"] is None
    assert _marker(external) == "kept"


def test_a_tarball_in_the_old_data_layout_still_restores_into_an_external_directory(monkeypatch, tmp_path, capsys):
    source = tmp_path / "repo" / "data"
    _populate(source, "legacy")
    legacy = tmp_path / "legacy.tar.gz"
    with tarfile.open(legacy, "w:gz") as tar:  # exactly what the tool wrote before this change
        tar.add(source / "app.db", arcname="data/app.db")
        tar.add(source / "memory.json", arcname="data/memory.json")

    external = tmp_path / "AppData" / "Misumi"
    backup = _load(monkeypatch, external)
    monkeypatch.setattr(backup, "_BACKUP_DIR", tmp_path / "backups")
    _run(capsys, backup.cmd_restore, path=str(legacy), yes=True)
    assert _marker(external) == "legacy"


def test_snapshot_output_inside_the_external_data_directory_is_refused(monkeypatch, tmp_path):
    external = tmp_path / "AppData" / "Misumi"
    _populate(external, "x")
    backup = _load(monkeypatch, external)
    monkeypatch.setattr(backup, "_BACKUP_DIR", tmp_path / "backups")
    with pytest.raises(SystemExit):
        backup.cmd_snapshot(SimpleNamespace(pretty=False, out=str(external / "snap.tar.gz"),
                                            include_research=False, include_attachments=False))


def test_path_traversal_entries_are_still_rejected_before_anything_is_touched(monkeypatch, tmp_path):
    external = tmp_path / "AppData" / "Misumi"
    _populate(external, "intact")
    evil = tmp_path / "evil.tar.gz"
    payload = tmp_path / "payload.txt"
    payload.write_text("x", encoding="utf-8")
    with tarfile.open(evil, "w:gz") as tar:
        tar.add(payload, arcname="data/../../escaped.txt")
    backup = _load(monkeypatch, external)
    with pytest.raises(SystemExit):
        backup.cmd_restore(SimpleNamespace(pretty=False, path=str(evil), yes=True))
    assert _marker(external) == "intact"  # validation ran before the data directory was stashed
    assert not (tmp_path / "escaped.txt").exists()

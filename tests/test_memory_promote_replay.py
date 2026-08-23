"""Tests for scripts/memory_promote_replay.py — the CLI wrapper over
src/memory_outbox.replay() (Workstream I's promotion/checkpoint/replay
procedure)."""
import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location(
    "memory_promote_replay", PROJECT_ROOT / "scripts" / "memory_promote_replay.py"
)
mpr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mpr)

from src.misumi_memory import MisumiMemory  # noqa: E402


def test_replay_via_cli_applies_and_is_idempotent(tmp_path, capsys, monkeypatch):
    source_root = tmp_path / "lab"
    target_root = tmp_path / "home"
    source = MisumiMemory(root=source_root)
    source.capture("a fact worth promoting", persona="kurisu")

    monkeypatch.setattr(sys, "argv", [
        "memory_promote_replay.py", "--source", str(source_root), "--target", str(target_root),
    ])
    rc1 = mpr.main()
    capsys.readouterr()
    rc2 = mpr.main()
    out2 = capsys.readouterr().out

    assert rc1 == 0 and rc2 == 0
    assert "0 record(s) newly applied" in out2

    target = MisumiMemory(root=target_root)
    records, _ = target.raw_records("capsules")
    assert len(records) == 1


def test_replay_via_cli_json_output(tmp_path, capsys, monkeypatch):
    source_root = tmp_path / "lab"
    target_root = tmp_path / "home"
    MisumiMemory(root=source_root).capture("another fact", persona="kurisu")

    monkeypatch.setattr(sys, "argv", [
        "memory_promote_replay.py", "--source", str(source_root), "--target", str(target_root), "--json",
    ])
    rc = mpr.main()
    out = capsys.readouterr().out

    assert rc == 0
    payload = json.loads(out)
    assert payload["capsules"]["applied"] == 1


def test_replay_via_cli_warns_on_conflicting_ids(tmp_path, capsys, monkeypatch):
    """Workstream I: 'backup/restore and conflict checks' — a diverging
    same-id record on both sides must surface as an operator-visible
    warning in the plain-text CLI output, not just in --json."""
    source_root = tmp_path / "lab"
    target_root = tmp_path / "home"
    source = MisumiMemory(root=source_root)
    target = MisumiMemory(root=target_root)

    cap = source.capture("needs confirmation", persona="kurisu")
    diverged = dict(cap)
    diverged["summary"] = "a different summary than the source has"
    target.append_record("capsules", diverged)

    monkeypatch.setattr(sys, "argv", [
        "memory_promote_replay.py", "--source", str(source_root), "--target", str(target_root),
    ])
    rc = mpr.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "WARNING" in out
    assert "1 record(s) exist on both sides" in out


def test_missing_source_root_fails_cleanly(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "memory_promote_replay.py",
        "--source", str(tmp_path / "does-not-exist"),
        "--target", str(tmp_path / "home"),
    ])
    rc = mpr.main()
    assert rc == 2

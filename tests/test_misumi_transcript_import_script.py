import datetime
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "misumi_transcript_import.py"


def _load():
    spec = importlib.util.spec_from_file_location("misumi_transcript_import", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_only_completed_days_are_selected_and_nothing_is_deleted(tmp_path):
    module = _load()
    today = datetime.date(2026, 10, 1)
    for name in ("ambient-2026-09-29.jsonl", "ambient-2026-09-30.jsonl", "ambient-2026-10-01.jsonl",
                 "ambient-2026-10-02.jsonl", "ambient-not-a-date.jsonl", "_pull.log", "notes.txt"):
        (tmp_path / name).write_text('{"at": "x"}\n', encoding="utf-8")
    selected = [path.name for _, path in module.completed_day_files(tmp_path, today)]
    assert selected == ["ambient-2026-09-29.jsonl", "ambient-2026-09-30.jsonl"]  # today and future skipped
    assert len(list(tmp_path.iterdir())) == 7  # selection never removes anything


def test_dry_run_needs_no_token_and_sends_nothing(tmp_path, capsys, monkeypatch):
    module = _load()
    monkeypatch.delenv("ODYSSEUS_API_TOKEN", raising=False)
    (tmp_path / "ambient-2020-01-01.jsonl").write_text('{"at":"2020-01-01T00:00:00Z","text":"a"}\n', encoding="utf-8")
    monkeypatch.setattr(module, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not post")))
    assert module.main(["--dir", str(tmp_path), "--base-url", "http://x", "--dry-run"]) == 0
    assert "1 windows (dry run)" in capsys.readouterr().out

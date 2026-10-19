"""Recurring Instagram import registration and accounting coverage."""

from __future__ import annotations

import json
import stat

from src.instagram_import_job import (
    JOB_ID,
    append_import_run,
    instagram_import_job_registration,
    last_import_run,
    run_instagram_import,
)


def _record(timestamp: str, **counts):
    return {
        "timestamp": timestamp,
        "created": counts.get("created", 0),
        "revised": counts.get("revised", 0),
        "unchanged": counts.get("unchanged", 0),
        "failed": counts.get("failed", 0),
        "duration_ms": counts.get("duration_ms", 1),
    }


def test_job_registration_is_six_hour_local_only_scheduler_job(monkeypatch, tmp_path):
    exports = tmp_path / "exports"
    monkeypatch.setenv("ODYSSEUS_INSTAGRAM_EXPORTS_DIR", str(exports))
    monkeypatch.delenv("ODYSSEUS_INSTAGRAM_IMPORT_INTERVAL_HOURS", raising=False)

    registration = instagram_import_job_registration()

    assert registration["id"] == JOB_ID
    assert registration["interval_seconds"] == 6 * 60 * 60
    assert registration["run_on_start"] is True
    assert registration["runner"] is run_instagram_import
    assert registration["exports_dir"] == exports
    assert registration["uses_model_inference"] is False
    assert registration["allows_network_egress"] is False

    monkeypatch.setenv("ODYSSEUS_INSTAGRAM_IMPORT_INTERVAL_HOURS", "1.5")
    assert instagram_import_job_registration()["interval_seconds"] == 5400.0


def test_accounting_log_appends_privately_and_last_run_queries(tmp_path):
    run_log = tmp_path / "governed" / "instagram" / "import-runs.jsonl"
    first = _record("2026-10-19T00:00:00Z", created=2)
    second = _record("2026-10-19T06:00:00Z", unchanged=2)

    first_line = append_import_run(first, run_log)
    second_line = append_import_run(second, run_log)

    assert run_log.read_text(encoding="utf-8").splitlines() == [first_line, second_line]
    assert json.loads(first_line) == first
    assert last_import_run(run_log) == second
    assert stat.S_IMODE(run_log.stat().st_mode) == 0o600
    assert stat.S_IMODE(run_log.parent.stat().st_mode) == 0o700


def test_unchanged_import_is_counted_as_a_clean_noop(tmp_path):
    snapshot = tmp_path / "exports" / "2026-10-18"
    snapshot.mkdir(parents=True)
    (snapshot / "saved_posts.json").write_text("[]", encoding="utf-8")
    (snapshot / "saved_collections.json").write_text("[]", encoding="utf-8")
    calls = []

    def unchanged(posts, collections):
        calls.append((posts, collections))
        return {
            "counts": {
                "created": 0,
                "revised": 0,
                "unchanged": 1772,
                "processed": 1772,
                "failed": 0,
            }
        }

    run_log = tmp_path / "data" / "instagram" / "runs.jsonl"
    accounting = run_instagram_import(tmp_path / "exports", run_log, importer=unchanged)

    assert len(calls) == 1
    assert accounting["created"] == 0
    assert accounting["revised"] == 0
    assert accounting["unchanged"] == 1772
    assert accounting["failed"] == 0
    assert last_import_run(run_log) == accounting


def test_missing_exports_directory_is_clean_zero_count_run(tmp_path, caplog):
    run_log = tmp_path / "data" / "instagram" / "runs.jsonl"

    accounting = run_instagram_import(tmp_path / "missing", run_log)

    assert {key: accounting[key] for key in ("created", "revised", "unchanged", "failed")} == {
        "created": 0,
        "revised": 0,
        "unchanged": 0,
        "failed": 0,
    }
    assert last_import_run(run_log) == accounting
    assert not [record for record in caplog.records if record.levelname in {"WARNING", "ERROR"}]

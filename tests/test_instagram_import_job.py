"""Recurring Instagram import registration and accounting coverage."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import stat
import time

from src.instagram_import_job import (
    JOB_ID,
    append_import_run,
    instagram_import_job_registration,
    last_import_run,
    run_instagram_import,
)
from src.task_scheduler import TaskScheduler


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


def _scheduler_with_instagram_runner(runner):
    scheduler = TaskScheduler(session_manager=None)
    scheduler._instagram_import_registration = {
        "id": JOB_ID,
        "interval_seconds": 6 * 60 * 60,
        "runner": runner,
        "exports_dir": "/exports",
        "run_log_path": "/run-log",
    }
    scheduler._instagram_import_next_monotonic = 0.0
    return scheduler


async def _wait_for_import_to_finish(scheduler):
    for _ in range(100):
        if not scheduler._instagram_import_in_flight:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Instagram import did not finish")


def _stub_to_thread(monkeypatch):
    async def run_stubbed(func, *args):
        result = func(*args)
        if inspect.isawaitable(result):
            return await result
        return result

    monkeypatch.setattr("src.task_scheduler.asyncio.to_thread", run_stubbed)


async def test_slow_import_does_not_block_scheduler_tick(monkeypatch):
    _stub_to_thread(monkeypatch)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_runner(_exports_dir, _run_log_path):
        started.set()
        await release.wait()
        return _record("2026-10-19T00:00:00Z")

    scheduler = _scheduler_with_instagram_runner(slow_runner)
    before = time.monotonic()
    try:
        await asyncio.wait_for(scheduler._run_instagram_import_if_due(), timeout=0.25)
        elapsed = time.monotonic() - before

        assert elapsed < 0.25
        assert scheduler._instagram_import_in_flight is True
        await asyncio.wait_for(started.wait(), timeout=1)
    finally:
        release.set()
        await _wait_for_import_to_finish(scheduler)


async def test_overlapping_instagram_import_trigger_is_skipped(monkeypatch):
    _stub_to_thread(monkeypatch)
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def slow_runner(_exports_dir, _run_log_path):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return _record("2026-10-19T00:00:00Z")

    scheduler = _scheduler_with_instagram_runner(slow_runner)
    try:
        await scheduler._run_instagram_import_if_due()
        first_task = scheduler._instagram_import_task
        await asyncio.wait_for(started.wait(), timeout=1)

        scheduler._instagram_import_next_monotonic = 0.0
        await scheduler._run_instagram_import_if_due()

        assert calls == 1
        assert scheduler._instagram_import_task is first_task
        assert scheduler._instagram_import_next_monotonic > time.monotonic()
    finally:
        release.set()
        await _wait_for_import_to_finish(scheduler)


async def test_instagram_import_exception_is_logged_and_not_propagated(caplog, monkeypatch):
    _stub_to_thread(monkeypatch)

    def failing_runner(_exports_dir, _run_log_path):
        raise RuntimeError("stubbed import failure")

    scheduler = _scheduler_with_instagram_runner(failing_runner)
    caplog.set_level(logging.ERROR, logger="src.task_scheduler")

    await scheduler._run_instagram_import_if_due()
    await _wait_for_import_to_finish(scheduler)

    assert scheduler._instagram_import_task is None
    assert "Infrastructure job instagram_saved_import failed" in caplog.text
    assert "stubbed import failure" in caplog.text

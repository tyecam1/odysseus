from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone

import pytest

from src.drm_runtime_guard import check_drm_runtime_guard
from src.task_scheduler import TaskScheduler, _model_task_timeout_seconds


ALLOWLIST = "version: 1\nactions:\n  validate:\n    enabled: true\n  task-transition:\n    enabled: false\n"
NOW = datetime(2026, 6, 22, 18, 0, tzinfo=timezone.utc)


def _vault(tmp_path, *, enabled=None, generated_at="2026-06-22T17:00:00Z"):
    config = tmp_path / "automation/config"
    heartbeats = tmp_path / "automation/review/routine-reports/odysseus-heartbeat"
    config.mkdir(parents=True)
    heartbeats.mkdir(parents=True)
    (config / "odysseus_actions.yaml").write_text(ALLOWLIST, encoding="utf-8")
    digest = hashlib.sha256(ALLOWLIST.encode("utf-8")).hexdigest()
    payload = {
        "report_kind": "odysseus-heartbeat",
        "generated_at": generated_at,
        "actions_yaml_sha256": digest,
        "enabled_actions": ["validate"] if enabled is None else enabled,
    }
    (heartbeats / "2026-06-22.heartbeat.json").write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


def test_guard_accepts_current_hash_matching_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setenv("ODYSSEUS_DRM_VAULT_ROOT", str(_vault(tmp_path)))
    assert check_drm_runtime_guard("DRM Validate", now=NOW) == (
        True,
        "current heartbeat and allowlist verified",
    )


@pytest.mark.parametrize(
    "enabled,generated_at,reason",
    [
        (["task-transition"], "2026-06-22T17:00:00Z", "enabled_actions exceed"),
        (["validate"], "2026-06-20T00:00:00Z", "heartbeat is stale"),
    ],
)
def test_guard_fails_closed_on_drift_or_staleness(tmp_path, monkeypatch, enabled, generated_at, reason):
    monkeypatch.setenv("ODYSSEUS_DRM_VAULT_ROOT", str(_vault(tmp_path, enabled=enabled, generated_at=generated_at)))
    allowed, message = check_drm_runtime_guard("DRM Validate", now=NOW)
    assert not allowed
    assert reason in message


def test_guard_requires_configuration_for_drm_only(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_DRM_VAULT_ROOT", raising=False)
    assert check_drm_runtime_guard("Calendar Classify Events", now=NOW)[0]
    assert not check_drm_runtime_guard("DRM Validate", now=NOW)[0]


def test_model_timeout_defaults_to_one_hour(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_MODEL_TASK_TIMEOUT_SECONDS", raising=False)
    assert _model_task_timeout_seconds() == 3600
    monkeypatch.setenv("ODYSSEUS_MODEL_TASK_TIMEOUT_SECONDS", "900")
    assert _model_task_timeout_seconds() == 900


@pytest.mark.asyncio
async def test_liveness_emits_periodic_progress():
    scheduler = TaskScheduler.__new__(TaskScheduler)
    messages = []
    scheduler._set_run_progress = lambda run_id, message: messages.append((run_id, message))
    task = asyncio.create_task(scheduler._emit_run_liveness("run-1", "Long task", interval_seconds=0.01))
    await asyncio.sleep(0.025)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert messages
    assert messages[0][0] == "run-1"
    assert "liveness" in messages[0][1]

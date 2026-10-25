"""Browser-independent coverage for the Instagram export acquisition job."""

from __future__ import annotations

import inspect
import json
import stat
import types
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from src.instagram_export_job import (
    DEFAULT_INTERVAL_HOURS,
    JOB_ID,
    MetaSessionExpired,
    ZipValidationError,
    _download_destination,
    _is_allowed_inbox_url,
    _looks_like_inbox_login,
    acknowledge_operator_auth,
    instagram_export_job_registration,
    run_instagram_export_job,
    save_acquisition_state,
    validate_and_stage_archive,
)
from src.task_scheduler import TaskScheduler


NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


def _state(name: str, **values):
    return {
        "version": 1,
        "state": name,
        "cycle_id": "cycle-test",
        "updated_at": "2026-10-24T12:00:00Z",
        "retry_count": 0,
        "seen_notification_ids": [],
        **values,
    }


def _archive(path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("connections/saved/saved_posts.json", "[]")
        archive.writestr("connections/saved/saved_collections.json", "[]")
    return path


def test_registration_is_weekly_policy_gated_and_model_free(monkeypatch, tmp_path):
    monkeypatch.delenv("ODYSSEUS_INSTAGRAM_EXPORT_INTERVAL_HOURS", raising=False)
    monkeypatch.setenv("ODYSSEUS_INSTAGRAM_EXPORTS_DIR", str(tmp_path / "exports"))
    registration = instagram_export_job_registration()

    assert registration["id"] == JOB_ID
    assert registration["interval_seconds"] == DEFAULT_INTERVAL_HOURS * 60 * 60
    assert registration["pending_poll_interval_seconds"] == 15 * 60
    assert registration["run_on_start"] is True
    assert registration["uses_model_inference"] is False
    assert registration["allows_network_egress"] is True
    assert registration["network_policy"] == "policy-gated-playwright"
    assert registration["exports_dir"] == tmp_path / "exports"


def test_inbox_url_policy_is_strict_and_https_only():
    assert _is_allowed_inbox_url("https://mail.google.com/mail/u/0/#inbox") is True
    assert _is_allowed_inbox_url("http://mail.google.com/mail/u/0/#inbox") is False
    assert _is_allowed_inbox_url("https://mail.google.com/arbitrary") is False
    assert _is_allowed_inbox_url("https://accounts.google.com/signin") is False
    assert _is_allowed_inbox_url("https://evil.example/mail/u/0/#inbox") is False
    assert _is_allowed_inbox_url("https://mail.google.com:invalid/mail/u/0/") is False
    assert _looks_like_inbox_login("https://accounts.google.com/signin/v2") is True


def test_pending_export_prevents_duplicate_request(tmp_path):
    calls = {"request": 0, "inbox": 0}

    def request(_profile):
        calls["request"] += 1
        return {"submitted_at": "2026-10-24T12:00:00Z", "request_id": "r1"}

    def inbox(_profile):
        calls["inbox"] += 1
        return []

    kwargs = {
        "state_path": tmp_path / "data" / "instagram" / "acquisition-state.json",
        "exports_dir": tmp_path / "exports",
        "profile_dir": tmp_path / "profile",
        "requester": request,
        "inbox_checker": inbox,
        "now": NOW,
    }
    first = run_instagram_export_job(**kwargs)
    second = run_instagram_export_job(**kwargs)

    assert first["state"] == second["state"] == "awaiting_email"
    assert calls == {"request": 1, "inbox": 2}
    assert stat.S_IMODE((tmp_path / "data/instagram/acquisition-state.json").stat().st_mode) == 0o600


def test_cross_process_style_lock_serializes_concurrent_requesters(tmp_path):
    state_path = tmp_path / "state.json"
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def request(_profile):
        calls.append("request")
        entered.set()
        assert release.wait(5)
        return {"submitted_at": "2026-10-24T12:00:00Z"}

    def run():
        return run_instagram_export_job(
            state_path,
            tmp_path / "exports",
            tmp_path / "profile",
            requester=request,
            inbox_checker=lambda _profile: [],
            now=NOW,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run)
        assert entered.wait(5)
        second = pool.submit(run)
        release.set()
        assert first.result(timeout=5)["state"] == "awaiting_email"
        assert second.result(timeout=5)["state"] == "awaiting_email"
    assert calls == ["request"]


def test_restart_recovers_mid_awaiting_email_and_completes(tmp_path):
    state_path = tmp_path / "data" / "instagram" / "acquisition-state.json"
    save_acquisition_state(
        _state("awaiting_email", requested_at="2026-10-24T11:00:00Z"),
        state_path,
    )
    source = _archive(tmp_path / "download.zip")
    download_calls = []

    def download(notification, _profile, _quarantine):
        download_calls.append(notification["id"])
        return source

    result = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        requester=lambda _profile: pytest.fail("restart must not submit another request"),
        inbox_checker=lambda _profile: [
            {
                "id": "message-1",
                "received_at": "2026-10-24T11:30:00Z",
                "download_url": "https://accountscenter.instagram.com/info_and_permissions/dyi/ready",
            }
        ],
        downloader=download,
        now=NOW,
    )

    assert result["state"] == "complete"
    assert download_calls == ["message-1"]
    snapshot = tmp_path / "exports" / "20261024T110000Z"
    assert (snapshot / "saved_posts.json").read_text(encoding="utf-8") == "[]"
    assert (snapshot / "saved_collections.json").read_text(encoding="utf-8") == "[]"
    sidecar = json.loads(next(snapshot.glob("*.provenance.json")).read_text(encoding="utf-8"))
    assert len(sidecar["sha256"]) == 64
    assert sidecar["notification_id"] == "message-1"


def test_delayed_missing_and_duplicate_notifications_are_handled_once(tmp_path):
    state_path = tmp_path / "state.json"
    save_acquisition_state(
        _state("awaiting_email", requested_at="2026-10-24T10:00:00Z"),
        state_path,
    )

    missing = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        inbox_checker=lambda _profile: [],
        now=NOW,
    )
    assert missing["state"] == "awaiting_email"
    assert missing["inbox_checks"] == 1

    source = _archive(tmp_path / "ready.zip")
    downloaded = []
    old = {
        "id": "old-message",
        "received_at": "2026-10-24T09:59:59Z",
        "download_url": "https://accountscenter.instagram.com/info_and_permissions/dyi/old",
    }
    ready = {
        "id": "ready-message",
        "received_at": "2026-10-24T11:30:00Z",
        "download_url": "https://accountscenter.instagram.com/info_and_permissions/dyi/ready",
    }
    complete = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        inbox_checker=lambda _profile: [old, ready, dict(ready)],
        downloader=lambda notification, _profile, _quarantine: (
            downloaded.append(notification["id"]) or source
        ),
        now=NOW + timedelta(minutes=5),
    )

    assert complete["state"] == "complete"
    assert downloaded == ["ready-message"]
    assert complete["seen_notification_ids"] == ["old-message", "ready-message"]


def test_notification_without_verified_received_time_is_not_selected(tmp_path):
    state_path = tmp_path / "state.json"
    save_acquisition_state(
        _state("awaiting_email", requested_at="2026-10-24T10:00:00Z"),
        state_path,
    )
    downloads = []
    result = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        inbox_checker=lambda _profile: [
            {
                "id": "unverified-time",
                "received_at": "not-a-timestamp",
                "download_url": "https://accountscenter.instagram.com/info_and_permissions/dyi/old",
            }
        ],
        downloader=lambda *_args: downloads.append("downloaded"),
        now=NOW,
    )
    assert result["state"] == "awaiting_email"
    assert downloads == []


def test_expired_session_becomes_needs_operator_auth_and_records_gate(tmp_path):
    state_path = tmp_path / "data" / "instagram" / "acquisition-state.json"
    gate_log = tmp_path / "data" / "instagram" / "operator-gates.jsonl"

    def expired(_profile):
        raise MetaSessionExpired("login redirect")

    result = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "missing-profile",
        requester=expired,
        gate_log_path=gate_log,
        now=NOW,
    )

    assert result["state"] == "needs_operator_auth"
    assert result["operator_gate"]["reason"] == "meta_session_expired_or_profile_missing"
    assert "meta_export_login_session.py" in result["operator_gate"]["required_action"]
    assert json.loads(gate_log.read_text(encoding="utf-8"))["kind"] == "operator_gate"
    assert stat.S_IMODE(gate_log.stat().st_mode) == 0o600

    # Once the explicit login gate is resolved, the known pre-submit request
    # transition is attempted once rather than incorrectly waiting forever.
    (tmp_path / "profile").mkdir()
    requests = []
    still_gated = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        requester=lambda _profile: (
            requests.append("submitted")
            or {"submitted_at": "2026-10-24T12:05:00Z"}
        ),
        inbox_checker=lambda _profile: [],
        gate_log_path=gate_log,
        now=NOW + timedelta(minutes=5),
    )
    assert still_gated["state"] == "needs_operator_auth"
    assert requests == []

    acknowledge_operator_auth(state_path, now=NOW + timedelta(minutes=6))
    resumed = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        requester=lambda _profile: (
            requests.append("submitted")
            or {"submitted_at": "2026-10-24T12:07:00Z"}
        ),
        inbox_checker=lambda _profile: [],
        gate_log_path=gate_log,
        now=NOW + timedelta(minutes=7),
    )
    assert resumed["state"] == "awaiting_email"
    assert requests == ["submitted"]


def test_missing_profile_becomes_needs_operator_auth_without_importing_playwright(tmp_path):
    result = run_instagram_export_job(
        tmp_path / "state.json",
        tmp_path / "exports",
        tmp_path / "definitely-missing-profile",
        now=NOW,
    )
    assert result["state"] == "needs_operator_auth"
    assert result["operator_gate"]["reason"] == "meta_session_expired_or_profile_missing"


def test_inbox_session_gate_records_the_inbox_specific_operator_action(tmp_path):
    from src.instagram_export_job import InboxSessionExpired

    state_path = tmp_path / "state.json"
    save_acquisition_state(
        _state("awaiting_email", requested_at="2026-10-24T10:00:00Z"),
        state_path,
    )
    result = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        inbox_checker=lambda _profile: (_ for _ in ()).throw(
            InboxSessionExpired("Google sign-in redirect")
        ),
        now=NOW,
    )
    assert result["state"] == "needs_operator_auth"
    assert result["operator_gate"]["reason"] == "inbox_session_expired"
    assert "configured inbox" in result["operator_gate"]["required_action"]


def test_restart_in_downloading_reuses_completed_quarantine_file(tmp_path):
    notification = {
        "id": "download-recovery",
        "download_url": "https://accountscenter.instagram.com/info_and_permissions/dyi/ready",
    }
    quarantine = tmp_path / "quarantine"
    quarantine.mkdir()
    destination = _download_destination(notification, quarantine)
    _archive(destination)
    state_path = tmp_path / "state.json"
    save_acquisition_state(
        _state(
            "downloading",
            requested_at="2026-10-24T10:00:00Z",
            notification=notification,
            download_destination=str(destination),
        ),
        state_path,
    )
    result = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        downloader=lambda *_args: pytest.fail("completed download must be reused"),
        quarantine_dir=quarantine,
        now=NOW,
    )
    assert result["state"] == "complete"


def test_zip_validation_failure_uses_bounded_exponential_retries(tmp_path):
    state_path = tmp_path / "state.json"
    invalid = tmp_path / "not-a-zip.bin"
    invalid.write_bytes(b"not a zip")
    save_acquisition_state(
        _state(
            "validating",
            downloaded_archive=str(invalid),
            requested_at="2026-10-24T10:00:00Z",
            notification={"id": "n1"},
        ),
        state_path,
    )

    result = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        now=NOW,
    )
    assert result["state"] == "transient_failure"
    assert result["resume_state"] == "validating"
    assert result["retry_count"] == 1
    assert result["next_retry_at"] == "2026-10-24T12:01:00Z"
    assert result["last_error"]["type"] == "ZipValidationError"

    # Retry at each due time; the fifth failure is retained but no sixth
    # automatic attempt is scheduled.
    cursor = NOW
    for delay in (60, 120, 240, 480):
        cursor += timedelta(seconds=delay)
        result = run_instagram_export_job(
            state_path,
            tmp_path / "exports",
            tmp_path / "profile",
            now=cursor,
        )
    assert result["retry_count"] == 5
    assert result["retry_exhausted"] is True
    assert result["next_retry_at"] is None


def test_validate_archive_rejects_duplicate_required_members(tmp_path):
    archive_path = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("a/saved_posts.json", "[]")
        archive.writestr("b/saved_posts.json", "[]")
        archive.writestr("a/saved_collections.json", "[]")
    with pytest.raises(ZipValidationError, match="duplicate required member"):
        validate_and_stage_archive(archive_path, tmp_path / "exports", now=NOW)


def test_validate_archive_rejects_required_member_zip_bomb_ratio(tmp_path):
    archive_path = tmp_path / "bomb.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("saved_posts.json", b" " * (1024 * 1024))
        archive.writestr("saved_collections.json", "[]")
    with pytest.raises(ZipValidationError, match="compression ratio"):
        validate_and_stage_archive(archive_path, tmp_path / "exports", now=NOW)


def test_archive_publication_is_idempotent_after_state_write_crash(tmp_path):
    source = _archive(tmp_path / "download.zip")
    kwargs = {
        "now": NOW,
        "requested_at": "2026-10-24T11:00:00Z",
        "notification_id": "notification-1",
    }
    first = validate_and_stage_archive(source, tmp_path / "exports", **kwargs)
    second = validate_and_stage_archive(source, tmp_path / "exports", **kwargs)
    assert second == first
    assert len([path for path in (tmp_path / "exports").iterdir() if not path.name.startswith(".")]) == 1


def test_state_file_corruption_is_preserved_and_fails_closed(tmp_path):
    state_path = tmp_path / "data" / "instagram" / "acquisition-state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{broken", encoding="utf-8")
    requests = []

    result = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "missing-profile",
        requester=lambda _profile: requests.append("requested"),
        now=NOW,
    )

    assert result["state"] == "needs_operator_auth"
    assert result["operator_gate"]["reason"] == "acquisition_state_corrupt"
    assert requests == []
    assert list(state_path.parent.glob("acquisition-state.json.corrupt-*"))
    assert json.loads(state_path.read_text(encoding="utf-8"))["state"] == "needs_operator_auth"


async def test_scheduler_dispatches_export_registration_without_blocking(monkeypatch):
    scheduler = TaskScheduler(session_manager=None)
    calls = []

    def runner(state_path, exports_dir, profile_dir):
        calls.append((state_path, exports_dir, profile_dir))
        return {"state": "awaiting_email"}

    scheduler._instagram_export_registration = {
        "id": JOB_ID,
        "interval_seconds": DEFAULT_INTERVAL_HOURS * 60 * 60,
        "runner": runner,
        "state_path": "/state",
        "exports_dir": "/exports",
        "profile_dir": "/profile",
    }
    scheduler._instagram_export_next_monotonic = 0.0

    async def immediate(func, *args):
        value = func(*args)
        return await value if inspect.isawaitable(value) else value

    monkeypatch.setattr("src.task_scheduler.asyncio.to_thread", immediate)
    await scheduler._run_instagram_export_if_due()
    await scheduler._instagram_export_task

    assert calls == [("/state", "/exports", "/profile")]
    assert scheduler._instagram_export_next_monotonic > 0


from src.instagram_export_job import (
    DEFAULT_INTERVAL_HOURS,
    JOB_ID,
    MetaSessionExpired,
    ZipValidationError,
    _download_destination,
    _is_allowed_inbox_url,
    _looks_like_inbox_login,
    acknowledge_operator_auth,
    instagram_export_job_registration,
    run_instagram_export_job,
    save_acquisition_state,
    validate_and_stage_archive,
)
from src.task_scheduler import TaskScheduler


NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


def _state(name: str, **values):
    return {
        "version": 1,
        "state": name,
        "cycle_id": "cycle-test",
        "updated_at": "2026-10-24T12:00:00Z",
        "retry_count": 0,
        "seen_notification_ids": [],
        **values,
    }


def _archive(path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("connections/saved/saved_posts.json", "[]")
        archive.writestr("connections/saved/saved_collections.json", "[]")
    return path


def test_registration_is_weekly_policy_gated_and_model_free(monkeypatch, tmp_path):
    monkeypatch.delenv("ODYSSEUS_INSTAGRAM_EXPORT_INTERVAL_HOURS", raising=False)
    monkeypatch.setenv("ODYSSEUS_INSTAGRAM_EXPORTS_DIR", str(tmp_path / "exports"))
    registration = instagram_export_job_registration()

    assert registration["id"] == JOB_ID
    assert registration["interval_seconds"] == DEFAULT_INTERVAL_HOURS * 60 * 60
    assert registration["pending_poll_interval_seconds"] == 15 * 60
    assert registration["run_on_start"] is True
    assert registration["uses_model_inference"] is False
    assert registration["allows_network_egress"] is True
    assert registration["network_policy"] == "policy-gated-playwright"
    assert registration["exports_dir"] == tmp_path / "exports"


def test_inbox_url_policy_is_strict_and_https_only():
    assert _is_allowed_inbox_url("https://mail.google.com/mail/u/0/#inbox") is True
    assert _is_allowed_inbox_url("http://mail.google.com/mail/u/0/#inbox") is False
    assert _is_allowed_inbox_url("https://mail.google.com/arbitrary") is False
    assert _is_allowed_inbox_url("https://accounts.google.com/signin") is False
    assert _is_allowed_inbox_url("https://evil.example/mail/u/0/#inbox") is False
    assert _is_allowed_inbox_url("https://mail.google.com:invalid/mail/u/0/") is False
    assert _looks_like_inbox_login("https://accounts.google.com/signin/v2") is True


def test_pending_export_prevents_duplicate_request(tmp_path):
    calls = {"request": 0, "inbox": 0}

    def request(_profile):
        calls["request"] += 1
        return {"submitted_at": "2026-10-24T12:00:00Z", "request_id": "r1"}

    def inbox(_profile):
        calls["inbox"] += 1
        return []

    kwargs = {
        "state_path": tmp_path / "data" / "instagram" / "acquisition-state.json",
        "exports_dir": tmp_path / "exports",
        "profile_dir": tmp_path / "profile",
        "requester": request,
        "inbox_checker": inbox,
        "now": NOW,
    }
    first = run_instagram_export_job(**kwargs)
    second = run_instagram_export_job(**kwargs)

    assert first["state"] == second["state"] == "awaiting_email"
    assert calls == {"request": 1, "inbox": 2}
    assert stat.S_IMODE((tmp_path / "data/instagram/acquisition-state.json").stat().st_mode) == 0o600


def test_cross_process_style_lock_serializes_concurrent_requesters(tmp_path):
    state_path = tmp_path / "state.json"
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def request(_profile):
        calls.append("request")
        entered.set()
        assert release.wait(5)
        return {"submitted_at": "2026-10-24T12:00:00Z"}

    def run():
        return run_instagram_export_job(
            state_path,
            tmp_path / "exports",
            tmp_path / "profile",
            requester=request,
            inbox_checker=lambda _profile: [],
            now=NOW,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run)
        assert entered.wait(5)
        second = pool.submit(run)
        release.set()
        assert first.result(timeout=5)["state"] == "awaiting_email"
        assert second.result(timeout=5)["state"] == "awaiting_email"
    assert calls == ["request"]


def test_restart_recovers_mid_awaiting_email_and_completes(tmp_path):
    state_path = tmp_path / "data" / "instagram" / "acquisition-state.json"
    save_acquisition_state(
        _state("awaiting_email", requested_at="2026-10-24T11:00:00Z"),
        state_path,
    )
    source = _archive(tmp_path / "download.zip")
    download_calls = []

    def download(notification, _profile, _quarantine):
        download_calls.append(notification["id"])
        return source

    result = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        requester=lambda _profile: pytest.fail("restart must not submit another request"),
        inbox_checker=lambda _profile: [
            {
                "id": "message-1",
                "received_at": "2026-10-24T11:30:00Z",
                "download_url": "https://accountscenter.instagram.com/info_and_permissions/dyi/ready",
            }
        ],
        downloader=download,
        now=NOW,
    )

    assert result["state"] == "complete"
    assert download_calls == ["message-1"]
    snapshot = tmp_path / "exports" / "20261024T110000Z"
    assert (snapshot / "saved_posts.json").read_text(encoding="utf-8") == "[]"
    assert (snapshot / "saved_collections.json").read_text(encoding="utf-8") == "[]"
    sidecar = json.loads(next(snapshot.glob("*.provenance.json")).read_text(encoding="utf-8"))
    assert len(sidecar["sha256"]) == 64
    assert sidecar["notification_id"] == "message-1"


def test_delayed_missing_and_duplicate_notifications_are_handled_once(tmp_path):
    state_path = tmp_path / "state.json"
    save_acquisition_state(
        _state("awaiting_email", requested_at="2026-10-24T10:00:00Z"),
        state_path,
    )

    missing = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        inbox_checker=lambda _profile: [],
        now=NOW,
    )
    assert missing["state"] == "awaiting_email"
    assert missing["inbox_checks"] == 1

    source = _archive(tmp_path / "ready.zip")
    downloaded = []
    old = {
        "id": "old-message",
        "received_at": "2026-10-24T09:59:59Z",
        "download_url": "https://accountscenter.instagram.com/info_and_permissions/dyi/old",
    }
    ready = {
        "id": "ready-message",
        "received_at": "2026-10-24T11:30:00Z",
        "download_url": "https://accountscenter.instagram.com/info_and_permissions/dyi/ready",
    }
    complete = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        inbox_checker=lambda _profile: [old, ready, dict(ready)],
        downloader=lambda notification, _profile, _quarantine: (
            downloaded.append(notification["id"]) or source
        ),
        now=NOW + timedelta(minutes=5),
    )

    assert complete["state"] == "complete"
    assert downloaded == ["ready-message"]
    assert complete["seen_notification_ids"] == ["old-message", "ready-message"]


def test_notification_without_verified_received_time_is_not_selected(tmp_path):
    state_path = tmp_path / "state.json"
    save_acquisition_state(
        _state("awaiting_email", requested_at="2026-10-24T10:00:00Z"),
        state_path,
    )
    downloads = []
    result = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        inbox_checker=lambda _profile: [
            {
                "id": "unverified-time",
                "received_at": "not-a-timestamp",
                "download_url": "https://accountscenter.instagram.com/info_and_permissions/dyi/old",
            }
        ],
        downloader=lambda *_args: downloads.append("downloaded"),
        now=NOW,
    )
    assert result["state"] == "awaiting_email"
    assert downloads == []


def test_expired_session_becomes_needs_operator_auth_and_records_gate(tmp_path):
    state_path = tmp_path / "data" / "instagram" / "acquisition-state.json"
    gate_log = tmp_path / "data" / "instagram" / "operator-gates.jsonl"

    def expired(_profile):
        raise MetaSessionExpired("login redirect")

    result = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "missing-profile",
        requester=expired,
        gate_log_path=gate_log,
        now=NOW,
    )

    assert result["state"] == "needs_operator_auth"
    assert result["operator_gate"]["reason"] == "meta_session_expired_or_profile_missing"
    assert "meta_export_login_session.py" in result["operator_gate"]["required_action"]
    assert json.loads(gate_log.read_text(encoding="utf-8"))["kind"] == "operator_gate"
    assert stat.S_IMODE(gate_log.stat().st_mode) == 0o600

    # Once the explicit login gate is resolved, the known pre-submit request
    # transition is attempted once rather than incorrectly waiting forever.
    (tmp_path / "profile").mkdir()
    requests = []
    still_gated = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        requester=lambda _profile: (
            requests.append("submitted")
            or {"submitted_at": "2026-10-24T12:05:00Z"}
        ),
        inbox_checker=lambda _profile: [],
        gate_log_path=gate_log,
        now=NOW + timedelta(minutes=5),
    )
    assert still_gated["state"] == "needs_operator_auth"
    assert requests == []

    acknowledge_operator_auth(state_path, now=NOW + timedelta(minutes=6))
    resumed = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        requester=lambda _profile: (
            requests.append("submitted")
            or {"submitted_at": "2026-10-24T12:07:00Z"}
        ),
        inbox_checker=lambda _profile: [],
        gate_log_path=gate_log,
        now=NOW + timedelta(minutes=7),
    )
    assert resumed["state"] == "awaiting_email"
    assert requests == ["submitted"]


def test_missing_profile_becomes_needs_operator_auth_without_importing_playwright(tmp_path):
    result = run_instagram_export_job(
        tmp_path / "state.json",
        tmp_path / "exports",
        tmp_path / "definitely-missing-profile",
        now=NOW,
    )
    assert result["state"] == "needs_operator_auth"
    assert result["operator_gate"]["reason"] == "meta_session_expired_or_profile_missing"


def test_inbox_session_gate_records_the_inbox_specific_operator_action(tmp_path):
    from src.instagram_export_job import InboxSessionExpired

    state_path = tmp_path / "state.json"
    save_acquisition_state(
        _state("awaiting_email", requested_at="2026-10-24T10:00:00Z"),
        state_path,
    )
    result = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        inbox_checker=lambda _profile: (_ for _ in ()).throw(
            InboxSessionExpired("Google sign-in redirect")
        ),
        now=NOW,
    )
    assert result["state"] == "needs_operator_auth"
    assert result["operator_gate"]["reason"] == "inbox_session_expired"
    assert "configured inbox" in result["operator_gate"]["required_action"]


def test_restart_in_downloading_reuses_completed_quarantine_file(tmp_path):
    notification = {
        "id": "download-recovery",
        "download_url": "https://accountscenter.instagram.com/info_and_permissions/dyi/ready",
    }
    quarantine = tmp_path / "quarantine"
    quarantine.mkdir()
    destination = _download_destination(notification, quarantine)
    _archive(destination)
    state_path = tmp_path / "state.json"
    save_acquisition_state(
        _state(
            "downloading",
            requested_at="2026-10-24T10:00:00Z",
            notification=notification,
            download_destination=str(destination),
        ),
        state_path,
    )
    result = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        downloader=lambda *_args: pytest.fail("completed download must be reused"),
        quarantine_dir=quarantine,
        now=NOW,
    )
    assert result["state"] == "complete"


def test_zip_validation_failure_uses_bounded_exponential_retries(tmp_path):
    state_path = tmp_path / "state.json"
    invalid = tmp_path / "not-a-zip.bin"
    invalid.write_bytes(b"not a zip")
    save_acquisition_state(
        _state(
            "validating",
            downloaded_archive=str(invalid),
            requested_at="2026-10-24T10:00:00Z",
            notification={"id": "n1"},
        ),
        state_path,
    )

    result = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "profile",
        now=NOW,
    )
    assert result["state"] == "transient_failure"
    assert result["resume_state"] == "validating"
    assert result["retry_count"] == 1
    assert result["next_retry_at"] == "2026-10-24T12:01:00Z"
    assert result["last_error"]["type"] == "ZipValidationError"

    # Retry at each due time; the fifth failure is retained but no sixth
    # automatic attempt is scheduled.
    cursor = NOW
    for delay in (60, 120, 240, 480):
        cursor += timedelta(seconds=delay)
        result = run_instagram_export_job(
            state_path,
            tmp_path / "exports",
            tmp_path / "profile",
            now=cursor,
        )
    assert result["retry_count"] == 5
    assert result["retry_exhausted"] is True
    assert result["next_retry_at"] is None


def test_validate_archive_rejects_duplicate_required_members(tmp_path):
    archive_path = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("a/saved_posts.json", "[]")
        archive.writestr("b/saved_posts.json", "[]")
        archive.writestr("a/saved_collections.json", "[]")
    with pytest.raises(ZipValidationError, match="duplicate required member"):
        validate_and_stage_archive(archive_path, tmp_path / "exports", now=NOW)


def test_validate_archive_rejects_required_member_zip_bomb_ratio(tmp_path):
    archive_path = tmp_path / "bomb.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("saved_posts.json", b" " * (1024 * 1024))
        archive.writestr("saved_collections.json", "[]")
    with pytest.raises(ZipValidationError, match="compression ratio"):
        validate_and_stage_archive(archive_path, tmp_path / "exports", now=NOW)


def test_archive_publication_is_idempotent_after_state_write_crash(tmp_path):
    source = _archive(tmp_path / "download.zip")
    kwargs = {
        "now": NOW,
        "requested_at": "2026-10-24T11:00:00Z",
        "notification_id": "notification-1",
    }
    first = validate_and_stage_archive(source, tmp_path / "exports", **kwargs)
    second = validate_and_stage_archive(source, tmp_path / "exports", **kwargs)
    assert second == first
    assert len([path for path in (tmp_path / "exports").iterdir() if not path.name.startswith(".")]) == 1


def test_state_file_corruption_is_preserved_and_fails_closed(tmp_path):
    state_path = tmp_path / "data" / "instagram" / "acquisition-state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{broken", encoding="utf-8")
    requests = []

    result = run_instagram_export_job(
        state_path,
        tmp_path / "exports",
        tmp_path / "missing-profile",
        requester=lambda _profile: requests.append("requested"),
        now=NOW,
    )

    assert result["state"] == "needs_operator_auth"
    assert result["operator_gate"]["reason"] == "acquisition_state_corrupt"
    assert requests == []
    assert list(state_path.parent.glob("acquisition-state.json.corrupt-*"))
    assert json.loads(state_path.read_text(encoding="utf-8"))["state"] == "needs_operator_auth"


async def test_scheduler_dispatches_export_registration_without_blocking(monkeypatch):
    scheduler = TaskScheduler(session_manager=None)
    calls = []

    def runner(state_path, exports_dir, profile_dir):
        calls.append((state_path, exports_dir, profile_dir))
        return {"state": "awaiting_email"}

    scheduler._instagram_export_registration = {
        "id": JOB_ID,
        "interval_seconds": DEFAULT_INTERVAL_HOURS * 60 * 60,
        "runner": runner,
        "state_path": "/state",
        "exports_dir": "/exports",
        "profile_dir": "/profile",
    }
    scheduler._instagram_export_next_monotonic = 0.0

    async def immediate(func, *args):
        value = func(*args)
        return await value if inspect.isawaitable(value) else value

    monkeypatch.setattr("src.task_scheduler.asyncio.to_thread", immediate)
    await scheduler._run_instagram_export_if_due()
    await scheduler._instagram_export_task

    assert calls == [("/state", "/exports", "/profile")]
    assert scheduler._instagram_export_next_monotonic > 0



def test_scheduler_honours_persisted_next_scheduled_at_after_restart(monkeypatch):
    """P2 regression: a restart must re-arm at the persisted weekly deadline
    (86400s away), not a fresh full interval (604800s)."""
    import asyncio
    import src.task_scheduler as ts

    scheduler = TaskScheduler(session_manager=None)

    def runner(state_path, exports_dir, profile_dir):
        return {"state": "complete", "next_scheduled_at": "2026-10-31T12:00:00Z"}

    scheduler._instagram_export_registration = {
        "id": JOB_ID,
        "interval_seconds": DEFAULT_INTERVAL_HOURS * 60 * 60,
        "runner": runner,
        "state_path": "/state",
        "exports_dir": "/exports",
        "profile_dir": "/profile",
    }

    fake_now = datetime(2026, 10, 30, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        ts, "datetime",
        type("FakeDatetime", (datetime,), {"now": classmethod(lambda cls, tz=None: fake_now)}),
    )
    monkeypatch.setattr(ts.time, "monotonic", lambda: 1000.0)

    result = {"state": "complete", "next_scheduled_at": "2026-10-31T12:00:00Z"}
    fake_task = types.SimpleNamespace(cancelled=lambda: False, result=lambda: result)
    scheduler._instagram_export_done(fake_task)

    delay = scheduler._instagram_export_next_monotonic - 1000.0
    assert delay == 86400.0
    assert delay != DEFAULT_INTERVAL_HOURS * 60 * 60


"""Durable, model-free acquisition job for Instagram Saved exports.

The scheduler invokes this controller weekly.  Each invocation performs only
the currently persisted transition(s); a request is recorded as ``requesting``
*before* the Meta UI is touched, so a restart can never submit a second export
when the first submission is uncertain or still pending.

Browser operations are deliberately isolated behind policy-gated Playwright
adapters.  Packet 1 does not execute them.  In particular, the live inbox
message format is intentionally not parsed yet: ``check_meta_export_inbox``
opens only the configured, allow-listed authenticated inbox and returns no
notifications until a later packet verifies that format against a real
message.  Tests inject deterministic adapters and never launch a browser.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import shutil
import stat
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping, Optional
from urllib.parse import urlparse

from src.constants import DATA_DIR
from src.instagram_import_job import DEFAULT_EXPORTS_DIR
from src.misumi_state_io import DEFAULT_LOCK_TIMEOUT_S, _os_lock, _os_unlock
from src.meta_export_automation import (
    PROFILE_DIR,
    MetaSessionExpired,
    _guard,
    _guarded_goto,
    _install_navigation_guard,
)
from src.private_state_io import check_private_path, private_dir as _private_dir, private_file


logger = logging.getLogger(__name__)

JOB_ID = "instagram_saved_export"
DEFAULT_INTERVAL_HOURS = 7 * 24.0
DEFAULT_PENDING_POLL_MINUTES = 15.0
DEFAULT_STATE_PATH = Path(DATA_DIR) / "instagram" / "acquisition-state.json"
DEFAULT_GATE_LOG = Path(DATA_DIR) / "instagram" / "operator-gates.jsonl"
DEFAULT_QUARANTINE_DIR = Path(DATA_DIR) / "instagram" / "acquisition-quarantine"

STATE_VERSION = 1
STATES = frozenset(
    {
        "scheduled",
        "requesting",
        "awaiting_email",
        "downloading",
        "validating",
        "complete",
        "transient_failure",
        "needs_operator_auth",
    }
)
MAX_TRANSIENT_RETRIES = 5
RETRY_BASE_SECONDS = 60.0
RETRY_MAX_SECONDS = 60.0 * 60.0
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 10_000
MAX_REQUIRED_JSON_BYTES = 256 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200

_INBOX_ALLOWED_HOSTS_AND_PREFIXES: dict[str, tuple[str, ...]] = {
    # Packet 1 supports the currently configured authenticated Gmail surface
    # only.  Adding another provider requires explicit path evidence and tests.
    "mail.google.com": ("/mail/",),
}


class ZipValidationError(ValueError):
    """The downloaded file is not a safe, usable Instagram Saved archive."""


class InboxSessionExpired(MetaSessionExpired):
    """The configured authenticated inbox requires an explicit login refresh."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(now: datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _positive_hours(value: Optional[str]) -> float:
    try:
        hours = float(value) if value is not None else DEFAULT_INTERVAL_HOURS
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_HOURS
    return hours if hours > 0 else DEFAULT_INTERVAL_HOURS


def _positive_minutes(value: Optional[str]) -> float:
    try:
        minutes = float(value) if value is not None else DEFAULT_PENDING_POLL_MINUTES
    except (TypeError, ValueError):
        return DEFAULT_PENDING_POLL_MINUTES
    return minutes if minutes > 0 else DEFAULT_PENDING_POLL_MINUTES


def instagram_export_job_registration() -> dict[str, Any]:
    """Return the weekly scheduler registration for the acquisition job."""
    interval_hours = _positive_hours(
        os.getenv("ODYSSEUS_INSTAGRAM_EXPORT_INTERVAL_HOURS")
    )
    return {
        "id": JOB_ID,
        "interval_seconds": interval_hours * 60 * 60,
        "pending_poll_interval_seconds": _positive_minutes(
            os.getenv("ODYSSEUS_INSTAGRAM_EXPORT_POLL_INTERVAL_MINUTES")
        ) * 60,
        "run_on_start": True,
        "runner": run_instagram_export_job,
        "state_path": DEFAULT_STATE_PATH,
        "exports_dir": Path(
            os.getenv("ODYSSEUS_INSTAGRAM_EXPORTS_DIR") or DEFAULT_EXPORTS_DIR
        ),
        "profile_dir": Path(
            os.getenv("ODYSSEUS_META_EXPORT_BROWSER_PROFILE") or PROFILE_DIR
        ),
        "uses_model_inference": False,
        "allows_network_egress": True,
        "network_policy": "policy-gated-playwright",
    }



def _fsync_dir(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def _acquisition_lock(state_path: Path, *, timeout: float = DEFAULT_LOCK_TIMEOUT_S):
    """Serialize transitions on the same lock inode on POSIX and Windows."""
    if not math.isfinite(timeout) or timeout < 0:
        raise ValueError("acquisition lock timeout must be finite and nonnegative")
    lock_path = state_path.parent / f".{state_path.name}.lock"
    with private_file(lock_path, os.O_RDWR | os.O_CREAT) as fd:
        _os_lock(fd, timeout)
        try:
            yield
        finally:
            _os_unlock(fd, close=False)


def save_acquisition_state(
    state: Mapping[str, Any],
    path: str | os.PathLike[str] = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    """Persist state 0600 using fsync + atomic sibling replacement."""
    target = Path(path)
    _private_dir(target.parent)
    if target.exists() or target.is_symlink():
        check_private_path(target)
    payload = dict(state)
    payload["version"] = STATE_VERSION
    if payload.get("state") not in STATES:
        raise ValueError(f"invalid Instagram acquisition state: {payload.get('state')!r}")
    tmp = target.parent / f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        with private_file(tmp, flags) as fd:
            with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(tmp, target)
        _fsync_dir(target.parent)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
    return payload


def _append_operator_gate(
    gate: Mapping[str, Any], gate_log_path: str | os.PathLike[str]
) -> None:
    path = Path(gate_log_path)
    _private_dir(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    with private_file(path, flags) as fd:
        with os.fdopen(fd, "a", encoding="utf-8", closefd=False) as handle:
            handle.write(json.dumps(dict(gate), sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def _new_state(now: datetime) -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "state": "scheduled",
        "cycle_id": uuid.uuid4().hex,
        "updated_at": _iso(now),
        "retry_count": 0,
        "seen_notification_ids": [],
    }


def _operator_gate_state(
    *,
    now: datetime,
    reason: str,
    detail: str,
    resume_state: str,
    required_action: Optional[str] = None,
    previous: Optional[Mapping[str, Any]] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    gate = {
        "kind": "operator_gate",
        "reason": reason,
        "detail": detail,
        "required_action": required_action or (
            "Re-authenticate the existing Meta account with "
            "scripts/meta_export_login_session.py; do not create another account, "
            "then run `python -m src.instagram_export_job --acknowledge-auth`."
        ),
        "recorded_at": _iso(now),
    }
    state = dict(previous or _new_state(now))
    state.update(
        {
            "state": "needs_operator_auth",
            "resume_state": resume_state,
            "operator_gate": gate,
            "operator_auth_acknowledged_at": None,
            "updated_at": _iso(now),
        }
    )
    return state, gate


def load_acquisition_state(
    path: str | os.PathLike[str] = DEFAULT_STATE_PATH,
    *,
    gate_log_path: str | os.PathLike[str] | None = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Read restart state, failing closed and preserving corrupt input.

    A corrupt file could have represented a pending request.  Resetting it to
    ``scheduled`` would risk a duplicate Meta request, so corruption recovery
    deliberately creates ``needs_operator_auth`` and preserves the original as
    a timestamped ``.corrupt-*`` sibling for diagnosis.
    """
    current = now or _utcnow()
    target = Path(path)
    if target.exists() or target.is_symlink():
        check_private_path(target.parent)
        check_private_path(target)
    try:
        with target.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        if not isinstance(state, dict) or state.get("state") not in STATES:
            raise ValueError("invalid state document")
        return state
    except FileNotFoundError:
        return _new_state(current)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _private_dir(target.parent)
        preserved = target.with_name(
            f"{target.name}.corrupt-{current.strftime('%Y%m%dT%H%M%SZ')}"
        )
        try:
            os.replace(target, preserved)
            os.chmod(preserved, 0o600)
            _fsync_dir(target.parent)
        except OSError:
            preserved = target
        state, gate = _operator_gate_state(
            now=current,
            reason="acquisition_state_corrupt",
            detail=(
                f"Could not safely establish whether an export request is pending; "
                f"preserved state at {preserved}: {type(exc).__name__}."
            ),
            resume_state="awaiting_email",
            required_action=(
                "Inspect the preserved corrupt acquisition state and establish "
                "whether a Meta request is pending before manually resolving this gate."
            ),
        )
        gate_path = Path(gate_log_path) if gate_log_path else target.parent / DEFAULT_GATE_LOG.name
        save_acquisition_state(state, target)
        _append_operator_gate(gate, gate_path)
        return state


def _is_allowed_inbox_url(url: str) -> bool:
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.username or parsed.password or port:
        return False
    prefixes = _INBOX_ALLOWED_HOSTS_AND_PREFIXES.get(parsed.hostname or "")
    return bool(prefixes and any((parsed.path or "/").startswith(prefix) for prefix in prefixes))


def _guarded_inbox_goto(page: Any, url: str) -> None:
    if not _is_allowed_inbox_url(url):
        raise ValueError(f"refusing non-allow-listed inbox URL: {url!r}")
    page.goto(url, wait_until="domcontentloaded")
    if not _is_allowed_inbox_url(page.url):
        raise ValueError(f"inbox navigation escaped the strict allow-list: {page.url!r}")


def _looks_like_inbox_login(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in {
        "accounts.google.com",
        "signin.google.com",
    }


def _require_profile(profile_dir: Path) -> None:
    if not profile_dir.exists():
        raise MetaSessionExpired(
            f"no persisted browser profile found at {profile_dir}; run "
            "scripts/meta_export_login_session.py and authenticate the existing account"
        )


def submit_meta_export_request(profile_dir: Path) -> dict[str, Any]:
    """Submit exactly one narrow Saved-items export via guarded Playwright."""
    _require_profile(profile_dir)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(str(profile_dir), headless=True)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            _install_navigation_guard(context, page)
            _guarded_goto(page, "https://accountscenter.instagram.com/")
            page.get_by_text("Your information and permissions", exact=False).click()
            page.get_by_text("Download or transfer information", exact=False).click()
            page.get_by_text("Create export", exact=False).click()
            page.get_by_text("Instagram", exact=False).click()
            page.get_by_text("Some of your information", exact=False).click()
            page.get_by_text("Saved", exact=False).click()
            page.get_by_text("Next", exact=False).click()
            page.get_by_text("Submit request", exact=False).click()
            _guard(page.url)
        finally:
            context.close()
    return {"submitted_at": _iso(_utcnow())}


def check_meta_export_inbox(profile_dir: Path) -> list[dict[str, Any]]:
    """Open the authenticated inbox under a strict navigation policy.

    Packet 1 intentionally returns no messages: the real Meta notification
    format/selectors must be verified in a later packet before parsing is
    enabled.  This stub still proves that any future check occurs only through
    the authenticated, policy-gated Playwright context.
    """
    _require_profile(profile_dir)
    inbox_url = os.getenv(
        "ODYSSEUS_INSTAGRAM_EXPORT_INBOX_URL",
        "https://mail.google.com/mail/u/0/#inbox",
    )
    if not _is_allowed_inbox_url(inbox_url):
        raise ValueError("ODYSSEUS_INSTAGRAM_EXPORT_INBOX_URL is not allow-listed")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(str(profile_dir), headless=True)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            guard_state = _install_navigation_guard(
                context, page, is_allowed=_is_allowed_inbox_url
            )
            try:
                _guarded_inbox_goto(page, inbox_url)
            except Exception as exc:
                attempted = [*guard_state.blocked_urls, str(page.url or "")]
                if any(_looks_like_inbox_login(url) for url in attempted):
                    raise InboxSessionExpired(
                        "the authenticated inbox session redirected to Google sign-in; "
                        "refresh the existing browser profile before resuming"
                    ) from exc
                raise
            # Later packet: verify the live inbox/message shape, then return
            # stable {id, received_at, download_url} records from that evidence.
            return []
        finally:
            context.close()


def download_meta_export(
    notification: Mapping[str, Any], profile_dir: Path, quarantine_dir: Path
) -> Path:
    """Download one allow-listed Meta link from a verified notification."""
    _require_profile(profile_dir)
    url = str(notification.get("download_url") or "")
    _guard(url)
    _private_dir(quarantine_dir)
    destination = _download_destination(notification, quarantine_dir)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(str(profile_dir), headless=True)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            _install_navigation_guard(context, page)
            with page.expect_download() as download_info:
                _guarded_goto(page, url)
            download = download_info.value
            partial = destination.with_name(
                f".{destination.name}.{os.getpid()}.{uuid.uuid4().hex}.part"
            )
            try:
                download.save_as(partial)
                os.chmod(partial, 0o600)
                with partial.open("rb") as handle:
                    os.fsync(handle.fileno())
                os.replace(partial, destination)
            finally:
                try:
                    partial.unlink()
                except FileNotFoundError:
                    pass
            _fsync_dir(quarantine_dir)
            return destination
        finally:
            context.close()


def _download_destination(
    notification: Mapping[str, Any], quarantine_dir: Path
) -> Path:
    identity = _notification_key(notification)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return quarantine_dir / f"instagram-export-{digest}.zip"


def _safe_saved_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    if len(archive.infolist()) > MAX_ARCHIVE_ENTRIES:
        raise ZipValidationError(
            f"archive has too many entries (maximum {MAX_ARCHIVE_ENTRIES})"
        )
    required: dict[str, zipfile.ZipInfo] = {}
    for info in archive.infolist():
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ZipValidationError(f"unsafe archive member: {info.filename!r}")
        mode = (info.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK:
            raise ZipValidationError(f"archive symlink is not permitted: {info.filename!r}")
        name = path.name
        if name in {"saved_posts.json", "saved_collections.json"}:
            if info.file_size > MAX_REQUIRED_JSON_BYTES:
                raise ZipValidationError(f"required member is too large: {name}")
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > MAX_COMPRESSION_RATIO:
                raise ZipValidationError(f"required member compression ratio is unsafe: {name}")
            if name in required:
                raise ZipValidationError(f"duplicate required member: {name}")
            required[name] = info
    missing = {"saved_posts.json", "saved_collections.json"} - set(required)
    if missing:
        raise ZipValidationError(f"archive missing required members: {sorted(missing)}")
    return required


def validate_and_stage_archive(
    archive_path: str | os.PathLike[str],
    exports_dir: str | os.PathLike[str],
    *,
    now: Optional[datetime] = None,
    requested_at: Optional[str] = None,
    notification_id: Optional[str] = None,
) -> dict[str, Any]:
    """Validate, move, and expose only the two JSON files the importer uses.

    The visible snapshot directory is published with one directory rename.
    Re-entry after a crash recognizes an already-published provenance record,
    making the ``validating`` transition idempotent even if state persistence
    was the last operation interrupted.
    """
    source = Path(archive_path)
    current = now or _utcnow()
    root = Path(exports_dir)
    _private_dir(root)
    stamp = _parse_iso(requested_at) or current
    base = stamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # If publication completed but the following state write did not, return
    # the same result instead of creating a duplicate snapshot.  At least one
    # acquisition identity field is required before considering a match.
    if requested_at or notification_id:
        for candidate in sorted(root.glob(f"{base}*")):
            if not candidate.is_dir() or candidate.name.startswith("."):
                continue
            for sidecar in candidate.glob("*.provenance.json"):
                try:
                    provenance = json.loads(sidecar.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if (
                    provenance.get("requested_at") == requested_at
                    and provenance.get("notification_id") == notification_id
                    and (candidate / "saved_posts.json").is_file()
                    and (candidate / "saved_collections.json").is_file()
                ):
                    destination = candidate / str(provenance.get("archive") or "")
                    if destination.is_file():
                        if source.is_file() and source != destination:
                            source.unlink()
                            _fsync_dir(source.parent)
                        return {
                            "snapshot_dir": str(candidate),
                            "archive_path": str(destination),
                            "provenance_path": str(sidecar),
                            "sha256": provenance["sha256"],
                        }

    if not source.is_file() or not zipfile.is_zipfile(source):
        raise ZipValidationError(f"not a readable ZIP archive: {source}")
    if source.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ZipValidationError(
            f"archive exceeds the {MAX_ARCHIVE_BYTES}-byte validation limit"
        )

    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    sha256 = digest.hexdigest()

    with zipfile.ZipFile(source) as archive:
        required = _safe_saved_members(archive)
        decoded: dict[str, bytes] = {}
        for name, info in required.items():
            content = archive.read(info)
            try:
                value = json.loads(content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ZipValidationError(f"{name} is not valid UTF-8 JSON") from exc
            if not isinstance(value, list):
                raise ZipValidationError(f"{name} must contain a JSON list")
            decoded[name] = content

    snapshot = root / base
    counter = 1
    while snapshot.exists():
        snapshot = root / f"{base}-{counter}"
        counter += 1
    staging = root / f".{snapshot.name}.{uuid.uuid4().hex}.tmp"
    _private_dir(staging)
    archive_name = source.name if source.suffix.lower() == ".zip" else "instagram-export.zip"
    provenance = {
        "archive": archive_name,
        "sha256": sha256,
        "size_bytes": source.stat().st_size,
        "requested_at": requested_at,
        "notification_id": notification_id,
        "validated_at": _iso(current),
        "acquisition": "official Meta self-service Instagram Saved export",
    }
    try:
        destination = staging / archive_name
        shutil.copyfile(source, destination)
        os.chmod(destination, 0o600)
        with destination.open("rb") as handle:
            os.fsync(handle.fileno())
        for name, content in decoded.items():
            output = staging / name
            fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, "wb", closefd=False) as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                os.close(fd)

        sidecar = staging / f"{destination.name}.provenance.json"
        fd = os.open(sidecar, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as handle:
                json.dump(provenance, handle, sort_keys=True, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(fd)
        _fsync_dir(staging)
        os.replace(staging, snapshot)
        _fsync_dir(root)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    source.unlink()
    _fsync_dir(source.parent)
    destination = snapshot / archive_name
    sidecar = snapshot / sidecar.name
    return {
        "snapshot_dir": str(snapshot),
        "archive_path": str(destination),
        "provenance_path": str(sidecar),
        "sha256": sha256,
    }


def _notification_key(notification: Mapping[str, Any]) -> str:
    return str(
        notification.get("id")
        or notification.get("message_id")
        or notification.get("download_url")
        or ""
    )


def _select_notification(
    notifications: Iterable[Mapping[str, Any]], state: Mapping[str, Any]
) -> tuple[Optional[dict[str, Any]], list[str]]:
    seen = {str(value) for value in state.get("seen_notification_ids", [])}
    requested = _parse_iso(state.get("requested_at"))
    candidates: dict[str, dict[str, Any]] = {}
    for raw in notifications:
        if not isinstance(raw, Mapping):
            continue
        notification = dict(raw)
        key = _notification_key(notification)
        if not key or key in seen:
            continue
        received = _parse_iso(notification.get("received_at"))
        if requested is not None:
            if received is None:
                # Recency is an evidence gate: a notification without a valid
                # timestamp cannot be attributed to this request cycle.
                continue
            if received < requested:
                seen.add(key)
                continue
        if not notification.get("download_url"):
            continue
        candidates.setdefault(key, notification)
    if not candidates:
        return None, sorted(seen)
    # Deterministic newest-first choice; duplicate rows with the same stable key
    # collapse above and cannot cause a second download.
    selected_key, selected = max(
        candidates.items(), key=lambda item: str(item[1].get("received_at") or "")
    )
    seen.add(selected_key)
    return selected, sorted(seen)


def _persist(
    document: dict[str, Any], path: Path, now: datetime, **changes: Any
) -> dict[str, Any]:
    document.update(changes)
    document["updated_at"] = _iso(now)
    return save_acquisition_state(document, path)


def _transient_failure(
    state: dict[str, Any], path: Path, now: datetime, resume_state: str, exc: Exception
) -> dict[str, Any]:
    attempt = int(state.get("retry_count") or 0) + 1
    exhausted = attempt >= MAX_TRANSIENT_RETRIES
    delay = min(RETRY_BASE_SECONDS * (2 ** (attempt - 1)), RETRY_MAX_SECONDS)
    retry_at = None if exhausted else _iso(datetime.fromtimestamp(now.timestamp() + delay, timezone.utc))
    return _persist(
        state,
        path,
        now,
        state="transient_failure",
        resume_state=resume_state,
        retry_count=attempt,
        next_retry_at=retry_at,
        retry_exhausted=exhausted,
        last_error={"type": type(exc).__name__, "message": str(exc)},
    )


def acknowledge_operator_auth(
    state_path: str | os.PathLike[str] = DEFAULT_STATE_PATH,
    *,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Record explicit completion of the login gate without launching a browser."""
    current = now or _utcnow()
    state_file = Path(state_path)
    with _acquisition_lock(state_file):
        state = load_acquisition_state(state_file, now=current)
        if state.get("state") != "needs_operator_auth":
            return state
        if state.get("operator_gate", {}).get("reason") == "acquisition_state_corrupt":
            return state
        return _persist(
            state,
            state_file,
            current,
            operator_auth_acknowledged_at=_iso(current),
        )


def _run_instagram_export_job_locked(
    state_path: str | os.PathLike[str] = DEFAULT_STATE_PATH,
    exports_dir: str | os.PathLike[str] | None = None,
    profile_dir: str | os.PathLike[str] | None = None,
    *,
    requester: Callable[[Path], Mapping[str, Any]] = submit_meta_export_request,
    inbox_checker: Callable[[Path], Iterable[Mapping[str, Any]]] = check_meta_export_inbox,
    downloader: Callable[[Mapping[str, Any], Path, Path], Path] = download_meta_export,
    validator: Callable[..., Mapping[str, Any]] = validate_and_stage_archive,
    now: Optional[datetime] = None,
    gate_log_path: str | os.PathLike[str] | None = None,
    quarantine_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Advance the durable acquisition state machine without model inference."""
    current = now or _utcnow()
    state_file = Path(state_path)
    gate_path = Path(gate_log_path) if gate_log_path else state_file.parent / DEFAULT_GATE_LOG.name
    export_root = Path(exports_dir) if exports_dir is not None else instagram_export_job_registration()["exports_dir"]
    profile = Path(profile_dir) if profile_dir is not None else instagram_export_job_registration()["profile_dir"]
    quarantine = Path(quarantine_dir) if quarantine_dir is not None else state_file.parent / DEFAULT_QUARANTINE_DIR.name
    state = load_acquisition_state(state_file, gate_log_path=gate_path, now=current)
    loaded_state = state["state"]
    fresh_request = False

    if loaded_state == "needs_operator_auth":
        # A missing profile cannot recover without the recorded human gate.  If
        # it now exists, retry the exact interrupted state and let the guarded
        # adapter verify whether the authenticated session is genuinely valid.
        if (
            not state.get("operator_auth_acknowledged_at")
            or not profile.exists()
            or state.get("operator_gate", {}).get("reason") == "acquisition_state_corrupt"
        ):
            return state
        resume_state = state.get("resume_state") or "awaiting_email"
        state = _persist(
            state,
            state_file,
            current,
            state=resume_state,
            operator_gate=None,
        )
        # submit_meta_export_request raises MetaSessionExpired during the
        # authenticated entry navigation, before it reaches "Submit request".
        # Once the explicit operator gate has been resolved, that pre-submit
        # state is therefore safe to attempt exactly once.
        fresh_request = resume_state == "requesting"

    if state["state"] == "transient_failure":
        if state.get("retry_exhausted"):
            return state
        retry_at = _parse_iso(state.get("next_retry_at"))
        if retry_at is not None and current < retry_at:
            return state
        state = _persist(
            state,
            state_file,
            current,
            state=state.get("resume_state") or "awaiting_email",
            next_retry_at=None,
        )

    if state["state"] == "complete":
        next_scheduled = _parse_iso(state.get("next_scheduled_at"))
        if next_scheduled is not None and current < next_scheduled:
            return state
        state = _new_state(current)
        save_acquisition_state(state, state_file)

    if state["state"] == "scheduled":
        fresh_request = True
        state = _persist(
            state,
            state_file,
            current,
            state="requesting",
            request_started_at=_iso(current),
        )

    try:
        if state["state"] == "requesting":
            if fresh_request:
                request_result = dict(requester(profile) or {})
                requested_at = request_result.get("submitted_at") or _iso(current)
                state = _persist(
                    state,
                    state_file,
                    current,
                    state="awaiting_email",
                    requested_at=requested_at,
                    request_result=request_result,
                    retry_count=0,
                )
            else:
                # Restart recovery is deliberately conservative: state was
                # durable before submission began, so an indeterminate request
                # is treated as pending and is never re-submitted.
                state = _persist(
                    state,
                    state_file,
                    current,
                    state="awaiting_email",
                    requested_at=state.get("request_started_at") or _iso(current),
                    request_recovered_after_restart=True,
                )

        if state["state"] == "awaiting_email":
            notifications = list(inbox_checker(profile) or [])
            selected, seen = _select_notification(notifications, state)
            if selected is None:
                return _persist(
                    state,
                    state_file,
                    current,
                    seen_notification_ids=seen,
                    inbox_checks=int(state.get("inbox_checks") or 0) + 1,
                    last_inbox_check_at=_iso(current),
                )
            state = _persist(
                state,
                state_file,
                current,
                state="downloading",
                notification=selected,
                seen_notification_ids=seen,
            )

        if state["state"] == "downloading":
            destination = Path(
                state.get("download_destination")
                or _download_destination(state["notification"], quarantine)
            )
            state = _persist(
                state,
                state_file,
                current,
                download_destination=str(destination),
            )
            downloaded = (
                destination
                if destination.is_file()
                else downloader(state["notification"], profile, quarantine)
            )
            state = _persist(
                state,
                state_file,
                current,
                state="validating",
                downloaded_archive=str(downloaded),
            )

        if state["state"] == "validating":
            result = dict(
                validator(
                    state["downloaded_archive"],
                    export_root,
                    now=current,
                    requested_at=state.get("requested_at"),
                    notification_id=_notification_key(state.get("notification") or {}),
                )
            )
            next_scheduled = datetime.fromtimestamp(
                current.timestamp()
                + _positive_hours(os.getenv("ODYSSEUS_INSTAGRAM_EXPORT_INTERVAL_HOURS"))
                * 60
                * 60,
                timezone.utc,
            )
            return _persist(
                state,
                state_file,
                current,
                state="complete",
                completed_at=_iso(current),
                next_scheduled_at=_iso(next_scheduled),
                result=result,
                retry_count=0,
                next_retry_at=None,
            )
    except MetaSessionExpired as exc:
        resume_state = state.get("state") or "awaiting_email"
        inbox_expired = isinstance(exc, InboxSessionExpired)
        gated, gate = _operator_gate_state(
            now=current,
            reason=(
                "inbox_session_expired"
                if inbox_expired
                else "meta_session_expired_or_profile_missing"
            ),
            detail=str(exc),
            resume_state=resume_state,
            required_action=(
                "Re-authenticate the configured inbox in the existing private browser "
                "profile, then run `python -m src.instagram_export_job "
                "--acknowledge-auth`."
                if inbox_expired
                else None
            ),
            previous=state,
        )
        save_acquisition_state(gated, state_file)
        _append_operator_gate(gate, gate_path)
        return gated
    except Exception as exc:
        logger.warning("Instagram export acquisition transient failure: %s", type(exc).__name__)
        return _transient_failure(state, state_file, current, state.get("state") or loaded_state, exc)

    return state


def run_instagram_export_job(
    state_path: str | os.PathLike[str] = DEFAULT_STATE_PATH,
    exports_dir: str | os.PathLike[str] | None = None,
    profile_dir: str | os.PathLike[str] | None = None,
    *,
    requester: Callable[[Path], Mapping[str, Any]] = submit_meta_export_request,
    inbox_checker: Callable[[Path], Iterable[Mapping[str, Any]]] = check_meta_export_inbox,
    downloader: Callable[[Mapping[str, Any], Path, Path], Path] = download_meta_export,
    validator: Callable[..., Mapping[str, Any]] = validate_and_stage_archive,
    now: Optional[datetime] = None,
    gate_log_path: str | os.PathLike[str] | None = None,
    quarantine_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Advance one cycle while holding the cross-process state transition lock."""
    state_file = Path(state_path)
    with _acquisition_lock(state_file):
        return _run_instagram_export_job_locked(
            state_file,
            exports_dir,
            profile_dir,
            requester=requester,
            inbox_checker=inbox_checker,
            downloader=downloader,
            validator=validator,
            now=now,
            gate_log_path=gate_log_path,
            quarantine_dir=quarantine_dir,
        )


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-path", default=str(DEFAULT_STATE_PATH))
    parser.add_argument(
        "--acknowledge-auth",
        action="store_true",
        help="acknowledge that the recorded browser authentication gate was completed",
    )
    args = parser.parse_args(argv)
    if not args.acknowledge_auth:
        parser.error("no action selected; use --acknowledge-auth")
    state = acknowledge_operator_auth(args.state_path)
    print(json.dumps(state, sort_keys=True, separators=(",", ":")))
    return 0 if state.get("operator_auth_acknowledged_at") else 1


if __name__ == "__main__":
    raise SystemExit(_main())


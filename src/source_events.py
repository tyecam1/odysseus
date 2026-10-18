"""Generic external-ingest SourceEvent adapter contract (P1).

This module is deliberately source-agnostic: it does NOT know how to parse
Instagram exports, WhatsApp exports, or any other originating format. It only
provides the neutral contract a future format-specific importer calls once it
has already extracted (source, external_id, content) from whatever it reads.

Storage philosophy mirrors src/attachment_refs.py: large/raw payloads never
sit in the SQLite row. `record_source_event` stores a sha256 checksum of the
normalized content plus a small caller-supplied pointer (`metadata`
-> `payload_ref`), never the raw content itself. Callers must not pass raw
exported media, raw private message text, or secrets as `metadata` — only a
small stable reference (e.g. a file path, an attachment id, a byte offset).

Idempotency: importing the same (source, external_id, identical content)
twice returns/updates the same row rather than creating a duplicate — backed
by a partial unique index on (source, external_id) in core.database.SourceEvent
for rows that carry an external_id.

Revision detection: a repeat (source, external_id) with a different
content_hash is recorded (not silently ignored, not silently clobbered) by
keeping the prior hash in `prior_content_hash` and bumping `revision_count`.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.constants import DATA_DIR

# Hard cap on the serialized size of caller-supplied `metadata` (stored as
# `payload_ref`). Enforces this module's own stated invariant that
# `metadata` is a small pointer, never raw content — without a cap nothing
# actually stopped a caller from passing megabytes of data through.
MAX_PAYLOAD_REF_BYTES = 4096
SOURCE_EVENT_PAYLOAD_DIR = Path(DATA_DIR) / "source_event_payloads"


class SourceEventValidationError(ValueError):
    """Raised for malformed input to record_source_event.

    A ValueError subclass (not a bare Exception) so callers can catch it
    specifically while it still satisfies generic `except ValueError`
    handling used elsewhere in the codebase.
    """


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_content(content: Any) -> str:
    """Return a deterministic string form of `content` for hashing.

    Strings are stripped (so trivial leading/trailing whitespace differences
    don't register as a "revision"). Non-string content is canonicalized as
    sorted-key JSON, mirroring src/bbc/store.py's `_canonical_json` /
    `content_hash` convention.
    """
    if isinstance(content, str):
        return content.strip()
    return json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash_content(content: Any) -> str:
    normalized = _normalize_content(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _lstat_payload_component(path: Path, *, directory: bool) -> os.stat_result | None:
    """Return an un-followed stat for one payload path component.

    Payload-store paths are derived from hashes, but an attacker able to place
    a symlink in the store must not be able to redirect writes or chmod calls.
    """
    try:
        result = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise SourceEventValidationError(
            f"cannot validate payload-store path component: {path}"
        ) from exc
    if stat.S_ISLNK(result.st_mode):
        raise SourceEventValidationError(
            f"payload-store path component must not be a symlink: {path}"
        )
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected_type(result.st_mode):
        kind = "directory" if directory else "regular file"
        raise SourceEventValidationError(
            f"payload-store path component must be a {kind}: {path}"
        )
    return result


def _ensure_payload_directory(path: Path, *, parents: bool = False) -> None:
    """Create one store directory and verify it without following links."""
    existing = _lstat_payload_component(path, directory=True)
    if existing is None:
        try:
            path.mkdir(parents=parents, exist_ok=True)
        except OSError as exc:
            raise SourceEventValidationError(
                f"cannot create payload-store directory: {path}"
            ) from exc
        # mkdir(exist_ok=True) can lose a race to another creator.  Treat the
        # result exactly like an existing component and fail closed on links.
        if _lstat_payload_component(path, directory=True) is None:
            raise SourceEventValidationError(
                f"payload-store directory disappeared after creation: {path}"
            )


def _chmod_payload_component(path: Path, mode: int, *, directory: bool) -> None:
    """Apply a POSIX mode through a verified descriptor, never through a link."""
    before = _lstat_payload_component(path, directory=directory)
    if before is None:
        raise SourceEventValidationError(
            f"payload-store path component disappeared before chmod: {path}"
        )
    if os.name == "nt":
        # Mirrors core.platform_compat.safe_chmod: POSIX modes do not map to
        # Windows ACLs, while the no-link validation above remains required.
        return

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    if directory:
        flags |= getattr(os, "O_DIRECTORY", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise SourceEventValidationError(
            f"cannot safely open payload-store path component: {path}"
        ) from exc
    try:
        opened = os.fstat(fd)
        expected_type = stat.S_ISDIR if directory else stat.S_ISREG
        if (
            opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or not expected_type(opened.st_mode)
        ):
            raise SourceEventValidationError(
                f"payload-store path component changed during validation: {path}"
            )
        os.fchmod(fd, mode)
    except SourceEventValidationError:
        raise
    except OSError as exc:
        raise SourceEventValidationError(
            f"cannot safely chmod payload-store path component: {path}"
        ) from exc
    finally:
        os.close(fd)


def _write_payload_atomically(path: Path, content: bytes) -> None:
    """Create a private temp file exclusively and atomically install it."""
    temporary = path.parent / f".source-event-payload-{uuid.uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    # POSIX O_CREAT|O_EXCL already refuses a final-component symlink.  Add
    # O_NOFOLLOW where available as defence in depth; platforms without it
    # retain the exclusive-create guarantee and the lstat/fstat checks below.
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd: int | None = None
    installed = False
    try:
        fd = os.open(temporary, flags, 0o600)
        created = os.fstat(fd)
        if not stat.S_ISREG(created.st_mode):
            raise SourceEventValidationError(
                f"payload-store temporary path is not a regular file: {temporary}"
            )
        if os.name != "nt":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

        verified = _lstat_payload_component(temporary, directory=False)
        if verified is None or (
            verified.st_dev != created.st_dev or verified.st_ino != created.st_ino
        ):
            raise SourceEventValidationError(
                f"payload-store temporary file changed during write: {temporary}"
            )

        # Refuse an already-present final symlink.  If one appears after this
        # check, os.replace replaces the link itself rather than its referent.
        _lstat_payload_component(path, directory=False)
        os.replace(temporary, path)
        installed = True

        final = _lstat_payload_component(path, directory=False)
        if final is None or final.st_dev != created.st_dev or final.st_ino != created.st_ino:
            raise SourceEventValidationError(
                f"payload-store file changed during atomic installation: {path}"
            )
    except SourceEventValidationError:
        raise
    except OSError as exc:
        raise SourceEventValidationError(
            f"cannot safely write payload-store file: {path}"
        ) from exc
    finally:
        if fd is not None:
            os.close(fd)
        if not installed:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def store_source_event_payload(
    source: str,
    external_id: str,
    payload: Any,
    *,
    root: Optional[Path] = None,
) -> dict[str, str]:
    """Persist a raw/private payload outside SQL and return its small pointer.

    Files are content-addressed beneath the governed application data
    directory.  Neither the source identifier nor the external identifier is
    used verbatim in a filename.  The returned relative path and checksum are
    safe to place in ``SourceEvent.payload_ref``; the payload itself is not.
    """
    _validate_inputs(source, external_id, payload)
    normalized = _normalize_content(payload)
    payload_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    identity_hash = hashlib.sha256(
        f"{source.strip()}\0{external_id.strip()}".encode("utf-8")
    ).hexdigest()
    payload_root = Path(root) if root is not None else SOURCE_EVENT_PAYLOAD_DIR
    relative_path = Path(identity_hash[:2]) / identity_hash / f"{payload_hash}.json"
    path = payload_root / relative_path

    prefix_directory = payload_root / identity_hash[:2]
    identity_directory = prefix_directory / identity_hash
    _ensure_payload_directory(payload_root, parents=True)
    _ensure_payload_directory(prefix_directory)
    _ensure_payload_directory(identity_directory)

    directories = (payload_root, prefix_directory, identity_directory)
    for directory in directories:
        _chmod_payload_component(directory, 0o700, directory=True)

    # Re-lstat every component immediately before the write.  This both
    # enforces the fail-closed contract and narrows the race window after the
    # directory creation/chmod operations above.
    for directory in directories:
        if _lstat_payload_component(directory, directory=True) is None:
            raise SourceEventValidationError(
                f"payload-store directory disappeared before write: {directory}"
            )
    existing = _lstat_payload_component(path, directory=False)
    if existing is None:
        _write_payload_atomically(path, normalized.encode("utf-8"))

    # Re-assert the invariant for content-addressed files created by an older
    # run with a different umask/implementation as well as newly written ones.
    _chmod_payload_component(path, 0o600, directory=False)

    return {
        "kind": "source_event_payload",
        "path": relative_path.as_posix(),
        "sha256": payload_hash,
    }


def read_source_event_payload(
    payload_ref: dict[str, Any] | str,
    *,
    root: Optional[Path] = None,
) -> Any:
    """Resolve and checksum-verify a pointer from ``store_source_event_payload``."""
    if isinstance(payload_ref, str):
        try:
            payload_ref = json.loads(payload_ref)
        except json.JSONDecodeError as exc:
            raise SourceEventValidationError("payload_ref is not valid JSON") from exc
    if not isinstance(payload_ref, dict) or payload_ref.get("kind") != "source_event_payload":
        raise SourceEventValidationError("payload_ref is not a source-event payload pointer")
    relative_value = payload_ref.get("path")
    expected_hash = payload_ref.get("sha256")
    if not isinstance(relative_value, str) or not isinstance(expected_hash, str):
        raise SourceEventValidationError("payload_ref requires string path and sha256 fields")

    payload_root = (Path(root) if root is not None else SOURCE_EVENT_PAYLOAD_DIR).resolve()
    relative_path = Path(relative_value)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise SourceEventValidationError("payload_ref path must stay inside the payload store")
    path = (payload_root / relative_path).resolve()
    try:
        path.relative_to(payload_root)
    except ValueError as exc:
        raise SourceEventValidationError("payload_ref path must stay inside the payload store") from exc

    raw = path.read_bytes()
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != expected_hash:
        raise SourceEventValidationError("payload_ref checksum does not match stored payload")
    return json.loads(raw.decode("utf-8"))


def _validate_inputs(source: Any, external_id: Any, content: Any) -> None:
    if not isinstance(source, str) or not source.strip():
        raise SourceEventValidationError("record_source_event requires a non-empty 'source'")
    if not isinstance(external_id, str) or not external_id.strip():
        raise SourceEventValidationError("record_source_event requires a non-empty 'external_id'")
    if content is None:
        raise SourceEventValidationError("record_source_event requires non-empty 'content'")
    if isinstance(content, str) and not content.strip():
        raise SourceEventValidationError("record_source_event requires non-empty 'content'")
    if isinstance(content, (list, dict)) and not content:
        raise SourceEventValidationError("record_source_event requires non-empty 'content'")


def _payload_ref_json(metadata: Optional[dict]) -> Optional[str]:
    """Serialize the caller-supplied small pointer/metadata dict.

    `metadata` is a pointer, never the payload itself — this function does
    not accept or store raw content/secrets, only whatever small reference
    dict the caller passes.
    """
    if metadata is None:
        return None
    if not isinstance(metadata, dict):
        raise SourceEventValidationError("record_source_event 'metadata' must be a dict when provided")
    serialized = json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    size = len(serialized.encode("utf-8"))
    if size > MAX_PAYLOAD_REF_BYTES:
        raise SourceEventValidationError(
            f"record_source_event 'metadata' serializes to {size} bytes, "
            f"exceeding the {MAX_PAYLOAD_REF_BYTES}-byte small-pointer-only limit "
            "(pass a reference such as a file path or attachment id, not raw content)"
        )
    return serialized


def record_source_event(
    source: str,
    external_id: str,
    content: Any,
    metadata: Optional[dict] = None,
):
    """Record (or update) a SourceEvent for one externally-ingested item.

    Deterministic, idempotent contract for future format-specific importers
    (Instagram, WhatsApp, ...) — this function itself performs no parsing of
    any particular source format.

    Behavior:
      - Normalizes and sha256-hashes `content`; the raw content is never
        persisted, only the hash plus `metadata` (stored as `payload_ref`).
      - If no row exists yet for (source, external_id): creates one.
      - If a row exists and its content_hash matches: no-op, returns the
        existing row unchanged (idempotent on identical repeat input).
      - If a row exists and its content_hash differs: records this as a
        revision — the prior hash moves to `prior_content_hash`,
        `revision_count` increments, `status` becomes "revised", and the row
        is updated in place (same id).

    Raises SourceEventValidationError (a ValueError subclass) for missing
    `source`, missing `external_id`, or empty/missing `content`.
    """
    _validate_inputs(source, external_id, content)
    # Normalize before storing/querying too, not just for validation, so
    # e.g. "instagram" and " instagram " are the same identity rather than
    # silently creating separate rows.
    source = source.strip()
    external_id = external_id.strip()
    payload_ref = _payload_ref_json(metadata)
    content_hash = _hash_content(content)

    # Imported lazily so importing this module doesn't force core.database's
    # (and its transitive engine/env) import at module load time for callers
    # that only need the exception type or hashing helpers.
    from core.database import SessionLocal, SourceEvent

    db = SessionLocal()
    try:
        existing = (
            db.query(SourceEvent)
            .filter(SourceEvent.source == source, SourceEvent.external_id == external_id)
            .first()
        )
        now = _utcnow_naive()

        if existing is None:
            row = SourceEvent(
                id=str(uuid.uuid4()),
                source=source,
                external_id=external_id,
                content_hash=content_hash,
                domain="neutral",
                sensitivity="normal",
                payload_ref=payload_ref,
                received_at=now,
                status="received",
                prior_content_hash=None,
                revision_count=0,
            )
            db.add(row)
        elif existing.content_hash == content_hash:
            # Identical repeat import: no-op, return the same row untouched.
            row = existing
        else:
            # Content revision: record the trail, never silently overwrite.
            existing.prior_content_hash = existing.content_hash
            existing.content_hash = content_hash
            existing.payload_ref = payload_ref
            existing.received_at = now
            existing.status = "revised"
            existing.revision_count = (existing.revision_count or 0) + 1
            row = existing

        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

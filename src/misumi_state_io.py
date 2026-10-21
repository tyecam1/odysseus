"""Cross-process-safe, fail-closed file state for Misumi adaptation stores (round-5 repair, 2026-10-15).

The persona-state, routing-adaptation and ratification-dialogue stores keep small JSON documents and append-only JSONL logs
under one directory each. More than one process (uvicorn workers, a restarted service, an operator script) may touch the
same directory, so every read-modify-write must be serialised across processes, not only across threads, and a damaged file
must never be mistaken for an empty one (an empty candidates file would let the next write wipe every rejection).

Guarantees of :class:`StateDir`:

* one exclusive lock per directory, held across processes (``fcntl.flock`` on POSIX, ``msvcrt.locking`` on Windows - both
  released by the OS if the holder dies, so there is no stale-lock guessing) and re-entrant within a thread;
* JSON documents are replaced atomically (temp file in the same directory, flush, fsync, ``os.replace``);
* JSONL records are appended with ONE ``os.write`` of one complete line under the lock;
* corruption fails CLOSED: the damaged file is moved into ``quarantine/`` (bytes preserved), a ``STATE_CORRUPT.json`` marker
  is written, and every later read or write of that directory raises :class:`StateCorruptError` until an operator repairs the
  store and removes the marker. Nothing is ever treated as empty because it could not be parsed.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Iterator

if os.name == "nt":  # pragma: no cover - exercised on Windows
    import msvcrt
else:  # pragma: no cover - exercised on POSIX
    import fcntl

MARKER = "STATE_CORRUPT.json"
LOCK_NAME = ".state.lock"
DEFAULT_LOCK_TIMEOUT_S = 2.0  # round 6: a turn degrades (no learned behaviour) rather than hanging; MISUMI_STATE_LOCK_TIMEOUT_S


def lock_timeout_s() -> float:
    try:
        return max(0.05, float(os.getenv("MISUMI_STATE_LOCK_TIMEOUT_S") or DEFAULT_LOCK_TIMEOUT_S))
    except ValueError:
        return DEFAULT_LOCK_TIMEOUT_S


class StateBudget:
    """One lock-wait budget for a whole request (round 7): every lock acquisition in the request draws from it, so a request
    waits at most ``seconds`` in total however many stores it touches - not ``seconds`` per attempt."""

    def __init__(self, seconds: float | None = None):
        self.remaining = lock_timeout_s() if seconds is None else float(seconds)

    def spend(self, waited: float) -> None:
        self.remaining = max(0.0, self.remaining - max(0.0, waited))


_BUDGET: "contextvars.ContextVar[StateBudget | None]" = contextvars.ContextVar("misumi_state_budget", default=None)


@contextlib.contextmanager
def state_budget(budget: StateBudget) -> Iterator[StateBudget]:
    """Run the enclosed state work against ``budget`` (set it inside the worker thread that does the work)."""
    token = _BUDGET.set(budget)
    try:
        yield budget
    finally:
        _BUDGET.reset(token)


class StateUnavailable(RuntimeError):
    """Adaptation state cannot be used right now. Callers degrade: no learned behaviour, no capture; operator API -> 503."""


class StateCorruptError(StateUnavailable):
    """The store is quarantined (a file could not be parsed). Capture, promotion and learned behaviour must stop."""


class StateLockTimeout(StateUnavailable):
    """The cross-process lock could not be taken in time; the operation did not happen."""


_registry_guard = threading.Lock()
_thread_locks: dict[str, threading.RLock] = {}
_held = threading.local()  # per-thread {lock path: (depth, fd)}


def _thread_lock(key: str) -> threading.RLock:
    with _registry_guard:
        lock = _thread_locks.get(key)
        if lock is None:
            lock = _thread_locks[key] = threading.RLock()
        return lock


def _os_lock(fd: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            if os.name == "nt":
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise StateLockTimeout(f"could not lock adaptation state within {timeout:.1f}s") from None
            time.sleep(0.005)


def _os_unlock(fd: int) -> None:
    try:
        if os.name == "nt":
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


class StateDir:
    """One state directory: a cross-process lock, atomic JSON documents, append-only JSONL logs, fail-closed reads."""

    def __init__(self, root: str | Path, lock_timeout: float | None = None):
        self.root = Path(root)
        self._lock_timeout = lock_timeout
        self._lock_path = str((self.root / LOCK_NAME).absolute())

    @property
    def lock_timeout(self) -> float:
        return self._lock_timeout if self._lock_timeout is not None else lock_timeout_s()

    # ---------- locking ----------

    @contextlib.contextmanager
    def locked(self) -> Iterator[None]:
        held = getattr(_held, "locks", None)
        if held is None:
            held = _held.locks = {}
        key = self._lock_path
        if key in held:  # re-entrant within this thread: the OS lock is already ours
            held[key][0] += 1
            try:
                yield
            finally:
                held[key][0] -= 1
            return
        thread_lock = _thread_lock(key)
        budget = _BUDGET.get()
        timeout = self.lock_timeout if budget is None else min(self.lock_timeout, budget.remaining)
        if timeout <= 0:
            raise StateLockTimeout("the request's state lock budget is spent")
        started = time.monotonic()
        try:
            if not thread_lock.acquire(timeout=timeout):
                raise StateLockTimeout(f"could not lock adaptation state within {timeout:.1f}s (held in this process)")
        finally:
            if budget is not None:
                budget.spend(time.monotonic() - started)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            fd = os.open(key, os.O_RDWR | os.O_CREAT, 0o600)
            started = time.monotonic()
            try:
                _os_lock(fd, timeout if budget is None else max(0.0, min(timeout, budget.remaining)))
            except BaseException:
                os.close(fd)
                raise
            finally:
                if budget is not None:
                    budget.spend(time.monotonic() - started)
            held[key] = [1, fd]
            try:
                yield
            finally:
                del held[key]
                _os_unlock(fd)
        finally:
            thread_lock.release()

    # ---------- health ----------

    @property
    def marker_path(self) -> Path:
        return self.root / MARKER

    def check_healthy(self) -> None:
        if self.marker_path.exists():
            try:
                detail = json.loads(self.marker_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                detail = {}
            raise StateCorruptError(
                f"adaptation state at {self.root} is quarantined ({detail.get('file', 'unknown file')}: "
                f"{detail.get('error', 'unreadable')}); an operator must repair it and remove {MARKER}"
            )

    def _quarantine(self, name: str, error: str) -> None:
        source = self.root / name
        qdir = self.root / "quarantine"
        qdir.mkdir(parents=True, exist_ok=True)
        moved = qdir / f"{name}.{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.{uuid.uuid4().hex[:8]}.corrupt"
        try:
            os.replace(source, moved)
        except OSError:
            moved = Path("(could not move; left in place)")
        self._write_atomic(self.marker_path, json.dumps({
            "file": name, "moved_to": str(moved), "error": error[:300],
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "action": "capture, promotion and learned behaviour are refused until an operator repairs the store",
        }, indent=2) + "\n")

    # ---------- documents ----------

    def read_json(self, name: str) -> dict[str, Any] | None:
        """The parsed document, None when it does not exist. Corrupt -> quarantine + StateCorruptError (never 'empty')."""
        with self.locked():
            self.check_healthy()
            path = self.root / name
            try:
                raw = path.read_bytes()
            except FileNotFoundError:
                return None
            try:
                value = json.loads(raw.decode("utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("top-level value is not an object")
            except ValueError as exc:  # JSONDecodeError and UnicodeDecodeError are ValueErrors
                self._quarantine(name, f"{type(exc).__name__}: {exc}")
                raise StateCorruptError(f"{name} is corrupt and was quarantined: {exc}") from exc
            return value

    def write_json(self, name: str, data: dict[str, Any]) -> None:
        with self.locked():
            self.check_healthy()
            self._write_atomic(self.root / name, json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n")

    def _write_atomic(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        try:
            os.write(fd, text.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        for attempt in range(50):  # Windows: a virus scanner or indexer may hold the target briefly
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 49:
                    with contextlib.suppress(OSError):
                        os.unlink(tmp)
                    raise
                time.sleep(0.02)

    # ---------- append-only logs ----------

    def append_jsonl(self, name: str, record: dict[str, Any]) -> None:
        line = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        with self.locked():
            self.check_healthy()
            self.root.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(self.root / name), os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0), 0o600)
            try:
                written = os.write(fd, line)  # one write of one whole line
                if written != len(line):
                    raise OSError(f"short append to {name}: {written} of {len(line)} bytes")
                os.fsync(fd)
            finally:
                os.close(fd)

    def read_jsonl(self, name: str) -> list[dict[str, Any]]:
        """Every record of a log ([] only when the log does not exist). Any bad line -> quarantine + StateCorruptError."""
        with self.locked():
            self.check_healthy()
            try:
                raw = (self.root / name).read_bytes()
            except FileNotFoundError:
                return []
            rows: list[dict[str, Any]] = []
            try:
                text = raw.decode("utf-8")
                if text and not text.endswith("\n"):
                    raise ValueError("last record is incomplete (no trailing newline)")
                for number, line in enumerate(text.split("\n"), start=1):
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError(f"line {number} is not an object")
                    rows.append(value)
            except ValueError as exc:
                self._quarantine(name, f"{type(exc).__name__}: {exc}")
                raise StateCorruptError(f"{name} is corrupt and was quarantined: {exc}") from exc
            return rows

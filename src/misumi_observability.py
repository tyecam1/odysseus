"""Structured, local-only Misumi event logging."""

from __future__ import annotations

import contextlib
import contextvars
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from src.constants import DATA_DIR


EVENT_FIELDS = (
    "request_id", "persona", "persona_source", "routing", "routing_adaptation",
    "selected_skill_ids", "selected_tools",
    "blocked_tools", "task_id", "files_read", "files_changed", "model",
    "backend", "latency_ms", "outcome", "error", "blocker", "approval_mode",
)


# A demonstration run writes to its own session log instead of the shared operational log (see src/misumi_demo.py).
_SCOPED_PATH: "contextvars.ContextVar[Optional[Path]]" = contextvars.ContextVar("misumi_event_log_scope", default=None)


class MisumiEventLog:
    def __init__(self, path: Optional[str | Path] = None):
        self.path = Path(path or os.getenv("MISUMI_EVENT_LOG") or Path(DATA_DIR) / "misumi" / "events.jsonl")
        self._lock = threading.Lock()

    @contextlib.contextmanager
    def scoped(self, path: str | Path):
        """Within this context (and tasks/threads it starts) emit() and recent() use ``path``; the shared log is neither read nor written."""
        token = _SCOPED_PATH.set(Path(path))
        try:
            yield
        finally:
            _SCOPED_PATH.reset(token)

    @staticmethod
    def request_id() -> str:
        return uuid.uuid4().hex

    def emit(self, event: Dict[str, object]) -> Dict[str, object]:
        record = {field: event.get(field) for field in EVENT_FIELDS}
        record.update({"timestamp": time.time(), "event": event.get("event") or "request"})
        target = _SCOPED_PATH.get() or self.path
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return record

    def recent(self, limit: int = 50) -> List[Dict[str, object]]:
        target = _SCOPED_PATH.get() or self.path
        if not target.is_file():
            return []
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        result = []
        for line in lines[-max(1, min(int(limit), 500)):]:
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    result.append(value)
            except json.JSONDecodeError:
                continue
        return result

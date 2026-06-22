"""Fail-closed heartbeat guard for vault-backed DRM action tasks."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ACTION_RE = re.compile(r"^  ([A-Za-z0-9][A-Za-z0-9_-]*):\s*(?:#.*)?$")
_ENABLED_RE = re.compile(r"^    enabled:\s*(true|false)\b")


def _parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _allowlist(path: Path) -> dict[str, bool]:
    actions: dict[str, bool] = {}
    in_actions = False
    current = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("actions:"):
            in_actions = True
            current = ""
            continue
        if in_actions and line and not line.startswith(" "):
            break
        if not in_actions:
            continue
        match = _ACTION_RE.match(line)
        if match:
            current = match.group(1)
            actions[current] = False
            continue
        enabled = _ENABLED_RE.match(line)
        if current and enabled:
            actions[current] = enabled.group(1) == "true"
    return actions


def _allowlist_hash(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_drm_runtime_guard(task_name: str, *, now: datetime | None = None) -> tuple[bool, str]:
    """Return whether a DRM action may run under the configured vault heartbeat."""
    if not str(task_name or "").strip().lower().startswith("drm "):
        return True, "not-a-drm-task"
    vault_root = Path(os.environ.get("ODYSSEUS_DRM_VAULT_ROOT", "")).expanduser()
    if not str(vault_root) or str(vault_root) == ".":
        return False, "ODYSSEUS_DRM_VAULT_ROOT is not configured"
    allowlist_path = vault_root / "automation/config/odysseus_actions.yaml"
    heartbeat_dir = vault_root / "automation/review/routine-reports/odysseus-heartbeat"
    if not allowlist_path.is_file():
        return False, f"DRM allowlist missing: {allowlist_path}"
    candidates = sorted(heartbeat_dir.glob("*.heartbeat.json")) if heartbeat_dir.is_dir() else []
    if not candidates:
        return False, f"DRM heartbeat missing: {heartbeat_dir}"
    try:
        payload = json.loads(candidates[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"DRM heartbeat unreadable: {exc}"
    if payload.get("report_kind") != "odysseus-heartbeat":
        return False, "DRM heartbeat report_kind is invalid"
    generated = _parse_time(payload.get("generated_at"))
    if generated is None:
        return False, "DRM heartbeat generated_at is invalid"
    current = now or datetime.now(timezone.utc)
    max_age_minutes = max(1, int(os.environ.get("ODYSSEUS_DRM_HEARTBEAT_MAX_AGE_MINUTES", "1800")))
    if (current.astimezone(timezone.utc) - generated).total_seconds() / 60 > max_age_minutes:
        return False, "DRM heartbeat is stale"
    if payload.get("actions_yaml_sha256") != _allowlist_hash(allowlist_path):
        return False, "DRM heartbeat allowlist hash mismatch"
    actions = _allowlist(allowlist_path)
    enabled = payload.get("enabled_actions")
    if not isinstance(enabled, list) or any(not actions.get(str(name), False) for name in enabled):
        return False, "DRM heartbeat enabled_actions exceed the committed allowlist"
    return True, "current heartbeat and allowlist verified"

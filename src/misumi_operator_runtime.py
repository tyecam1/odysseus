"""Durable operator-conference events and bounded Misumi heartbeat loops.

This module is intentionally side-effect small: append-only JSONL state, proposal-only
heartbeat output, and no production mutation path. Routes and CLI wrappers can use the
same store, which makes the operator lifecycle testable without the web app running.
"""

from __future__ import annotations

import json
import os
import re
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from src.constants import DATA_DIR


PERSONAS = {
    "aoteru", "lelouch", "kurisu", "misato", "jin", "erwin", "l",
    "ginko", "sanji", "ichigo", "giorno", "operator",
}
CONFERENCE_STATUSES = {"pending", "responded", "expired", "cancelled"}
LOOP_MODES = {"observe", "propose"}
DEFAULT_HEARTBEAT_ENABLED = (os.getenv("MISUMI_HEARTBEAT_ENABLED", "0") or "").lower() in {
    "1", "true", "yes", "on",
}


@dataclass(frozen=True)
class LoopManifest:
    loop_id: str
    owner_persona: str
    purpose: str
    interval_seconds: int
    timeout_seconds: int
    max_budget_tokens: int
    enabled: bool = DEFAULT_HEARTBEAT_ENABLED
    mode: str = "propose"

    def as_dict(self) -> Dict[str, object]:
        return {
            "loop_id": self.loop_id,
            "owner_persona": self.owner_persona,
            "purpose": self.purpose,
            "interval_seconds": self.interval_seconds,
            "timeout_seconds": self.timeout_seconds,
            "max_budget_tokens": self.max_budget_tokens,
            "enabled": self.enabled,
            "permission_mode": self.mode,
        }


DEFAULT_LOOP_MANIFESTS: Tuple[LoopManifest, ...] = (
    LoopManifest(
        "interaction_friction_loop", "aoteru",
        "Detect failed handoffs, dead UI actions, repeated confusion, unanswered operator requests, and missing persona tools.",
        3600, 60, 1200,
    ),
    LoopManifest(
        "persona_contract_loop", "aoteru",
        "Check recent outputs against persona contracts and flag identity drift, especially Aoteru/Misumi confusion.",
        7200, 60, 1200,
    ),
    LoopManifest(
        "operator_handoff_loop", "lelouch",
        "Audit claims that an operator, persona, or tool will act and verify whether a real event or response occurred.",
        3600, 60, 1000,
    ),
    LoopManifest(
        "usability_improvement_loop", "giorno",
        "Review interface friction, 1024x768 readability, blocked actions, and repeated corrections. Produce UI proposals only.",
        7200, 60, 1200,
    ),
    LoopManifest(
        "persona_function_loop", "lelouch",
        "Identify missing persona-specific route/tool contracts without installing new powers.",
        86400, 90, 1400,
    ),
    LoopManifest(
        "regression_guard_loop", "ichigo",
        "Run lightweight guard checks for identity, loop truthfulness, LAN boundaries, token exposure, and unratified writes.",
        3600, 45, 900,
    ),
    LoopManifest(
        "proposal_consolidation_loop", "kurisu",
        "Deduplicate heartbeat outputs into a rolling proposal ledger and mark human-ratification requirements.",
        86400, 90, 1400,
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: object) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def new_id(prefix: str) -> str:
    return f"{prefix}-{int(datetime.now(timezone.utc).timestamp())}-{uuid.uuid4().hex[:8]}"


def short_text(value: object, limit: int = 900) -> str:
    text = re.sub(r"<think>.*?</think>", "", str(value or ""), flags=re.I | re.S)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip()


def runtime_root(root: Optional[Path | str] = None) -> Path:
    return Path(root) if root is not None else Path(DATA_DIR) / "misumi" / "runtime"


class JsonlStore:
    def __init__(self, root: Optional[Path | str] = None):
        self.root = runtime_root(root)

    def _path(self, name: str) -> Path:
        return self.root / f"{name}.jsonl"

    def append(self, name: str, record: Dict[str, object]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self._path(name).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()

    def fold(self, name: str) -> Tuple[List[Dict[str, object]], int]:
        path = self._path(name)
        if not path.is_file():
            return [], 0
        latest: Dict[str, Dict[str, object]] = {}
        corrupt = 0
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                        raise ValueError("invalid row")
                    latest[row["id"]] = row
                except Exception:
                    corrupt += 1
        return list(latest.values()), corrupt


class OperatorConferenceStore:
    """Append-only operator conference lifecycle.

    This is the missing contract behind Aoteru saying the Operator will confer:
    every such claim must be backed by one pending/responded/expired/cancelled event.
    """

    def __init__(self, root: Optional[Path | str] = None):
        self.store = JsonlStore(root)

    def create(
        self,
        *,
        requesting_persona: str,
        reason: str,
        context_summary: str = "",
        urgency: str = "normal",
        timeout_seconds: int = 600,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, object]:
        persona = str(requesting_persona or "").strip().lower()
        if persona not in PERSONAS:
            raise ValueError(f"unknown requesting persona: {requesting_persona}")
        reason_text = short_text(reason, 500)
        if not reason_text:
            raise ValueError("reason must be non-empty")
        timeout = max(30, min(int(timeout_seconds or 600), 24 * 3600))
        now = utc_now()
        record: Dict[str, object] = {
            "id": new_id("opconf"),
            "event_id": None,
            "requesting_persona": persona,
            "reason": reason_text,
            "context_summary": short_text(context_summary, 1600),
            "urgency": str(urgency or "normal")[:40],
            "created_at": now,
            "updated_at": now,
            "status": "pending",
            "timeout_seconds": timeout,
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=timeout)).isoformat().replace("+00:00", "Z"),
            "session_id": session_id,
            "correlation_id": correlation_id,
            "response": None,
            "response_payload": None,
            "responder": None,
            "writes_allowed": False,
        }
        record["event_id"] = record["id"]
        self.store.append("operator_conferences", record)
        return record

    def _expire_if_needed(self, record: Dict[str, object], now: Optional[datetime] = None) -> Dict[str, object]:
        if record.get("status") != "pending":
            return record
        expires = parse_utc(record.get("expires_at"))
        if not expires:
            created = parse_utc(record.get("created_at")) or datetime.now(timezone.utc)
            expires = created + timedelta(seconds=int(record.get("timeout_seconds") or 600))
        current = now or datetime.now(timezone.utc)
        if current <= expires:
            return record
        changed = dict(record)
        changed.update({"status": "expired", "updated_at": utc_now(), "timeout_result": "operator did not respond before timeout"})
        self.store.append("operator_conferences", changed)
        return changed

    def list(self, status: Optional[str] = None) -> Tuple[List[Dict[str, object]], int]:
        records, corrupt = self.store.fold("operator_conferences")
        now = datetime.now(timezone.utc)
        rows = [self._expire_if_needed(dict(item), now=now) for item in records]
        if status:
            if status not in CONFERENCE_STATUSES:
                raise ValueError(f"unknown conference status: {status}")
            rows = [item for item in rows if item.get("status") == status]
        rows.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return rows, corrupt

    def get(self, event_id: str) -> Dict[str, object]:
        rows, _ = self.list()
        found = next((item for item in rows if item.get("id") == event_id or item.get("event_id") == event_id), None)
        if not found:
            raise KeyError(event_id)
        return found

    def respond(self, event_id: str, *, response: str, responder: str = "operator", payload: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        current = self.get(event_id)
        if current.get("status") != "pending":
            raise ValueError(f"conference is not pending: {current.get('status')}")
        response_text = short_text(response, 3000)
        if not response_text:
            raise ValueError("response must be non-empty")
        changed = dict(current)
        changed.update({
            "status": "responded",
            "updated_at": utc_now(),
            "response": response_text,
            "response_payload": dict(payload or {}),
            "responder": short_text(responder, 80) or "operator",
        })
        self.store.append("operator_conferences", changed)
        return changed

    def cancel(self, event_id: str, *, reason: str = "cancelled") -> Dict[str, object]:
        current = self.get(event_id)
        if current.get("status") != "pending":
            raise ValueError(f"conference is not pending: {current.get('status')}")
        changed = dict(current)
        changed.update({"status": "cancelled", "updated_at": utc_now(), "cancel_reason": short_text(reason, 400)})
        self.store.append("operator_conferences", changed)
        return changed

    def metrics(self) -> Dict[str, object]:
        rows, corrupt = self.list()
        pending = [item for item in rows if item.get("status") == "pending"]
        return {
            "pending_count": len(pending),
            "responded_count": sum(1 for item in rows if item.get("status") == "responded"),
            "expired_count": sum(1 for item in rows if item.get("status") == "expired"),
            "cancelled_count": sum(1 for item in rows if item.get("status") == "cancelled"),
            "newest_pending": pending[0] if pending else None,
            "corrupt_lines": corrupt,
            "writes_allowed": False,
        }


class HeartbeatRuntime:
    """Proposal-only heartbeat loop registry and one-shot runner."""

    def __init__(self, root: Optional[Path | str] = None, manifests: Iterable[LoopManifest] = DEFAULT_LOOP_MANIFESTS):
        self.root = runtime_root(root) / "heartbeat"
        self.store = JsonlStore(runtime_root(root))
        self.manifests = {item.loop_id: item for item in manifests}

    @property
    def proposal_dir(self) -> Path:
        return self.root / "proposals"

    def _lock_path(self, loop_id: str) -> Path:
        return self.root / "locks" / f"{loop_id}.lock"

    def _last_for(self, loop_id: str) -> Dict[str, object]:
        runs, _ = self.store.fold("heartbeat_runs")
        selected = [item for item in runs if item.get("loop_id") == loop_id]
        selected.sort(key=lambda item: str(item.get("started_at", "")), reverse=True)
        return selected[0] if selected else {}

    def _provider_status(self) -> Dict[str, object]:
        provider = (os.getenv("MISUMI_HEARTBEAT_PROVIDER") or os.getenv("MISUMI_LLM") or os.getenv("ODYSSEUS_LLM") or "deterministic").strip()
        model = (os.getenv("MISUMI_HEARTBEAT_MODEL") or os.getenv("MISUMI_MODEL") or "").strip() or None
        endpoint = (os.getenv("MISUMI_HEARTBEAT_URL") or os.getenv("MISUMI_MODEL_URL") or os.getenv("MISUMI_OLLAMA_URL") or "").strip() or None
        token_env = (os.getenv("MISUMI_HEARTBEAT_TOKEN_ENV") or "").strip() or None
        return {
            "provider": provider,
            "model": model,
            "endpoint_configured": bool(endpoint),
            "token_source": token_env,
            "token_exposed_to_browser": False,
            "mode": "proposal-only",
        }

    def status(self) -> Dict[str, object]:
        loops = []
        for loop_id, manifest in self.manifests.items():
            last = self._last_for(loop_id)
            lock_path = self._lock_path(loop_id)
            running = lock_path.exists()
            loops.append({
                **manifest.as_dict(),
                "registered": True,
                "currently_running": running,
                "lock_state": "locked" if running else "clear",
                "lock_file": str(lock_path),
                "last_successful_run": last.get("finished_at") if last.get("status") == "success" else None,
                "last_failed_run": last.get("finished_at") if last.get("status") == "failed" else None,
                "last_output_artifact": last.get("output_artifact"),
                "next_scheduled_run": None,
                "backend": self._provider_status(),
            })
        return {
            "status": "ready",
            "heartbeat_enabled": DEFAULT_HEARTBEAT_ENABLED,
            "loops": loops,
            "registered_count": len(loops),
            "enabled_count": sum(1 for item in loops if item.get("enabled")),
            "running_count": sum(1 for item in loops if item.get("currently_running")),
            "proposal_count": len(list(self.proposal_dir.glob("*.json"))) if self.proposal_dir.is_dir() else 0,
            "writes_allowed": False,
            "provider": self._provider_status(),
        }

    def run_once(self, loop_id: str, *, input_summary: str = "") -> Dict[str, object]:
        if loop_id not in self.manifests:
            raise KeyError(loop_id)
        manifest = self.manifests[loop_id]
        if manifest.mode not in LOOP_MODES:
            raise ValueError("heartbeat loop mode must be observe/propose")
        lock = self._lock_path(loop_id)
        lock.parent.mkdir(parents=True, exist_ok=True)
        if lock.exists():
            raise RuntimeError(f"loop already running: {loop_id}")
        started = utc_now()
        run_id = new_id("hbrun")
        try:
            lock.write_text(json.dumps({"run_id": run_id, "loop_id": loop_id, "started_at": started}), encoding="utf-8")
            self.proposal_dir.mkdir(parents=True, exist_ok=True)
            proposal = {
                "id": new_id("proposal"),
                "run_id": run_id,
                "loop_id": loop_id,
                "owner_persona": manifest.owner_persona,
                "created_at": utc_now(),
                "mode": manifest.mode,
                "status": "proposal",
                "requires_human_ratification": True,
                "writes_allowed": False,
                "provider": self._provider_status(),
                "source_host": socket.gethostname(),
                "input_summary": short_text(input_summary, 1600),
                "finding": deterministic_finding(loop_id, input_summary),
                "recommended_next_step": deterministic_next_step(loop_id),
                "rollback_path": "Delete this proposal artifact. No production state was modified.",
            }
            artifact = self.proposal_dir / f"{proposal['created_at'].replace(':', '').replace('-', '')}-{loop_id}-{proposal['id']}.json"
            artifact.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            run = {
                "id": run_id,
                "loop_id": loop_id,
                "started_at": started,
                "finished_at": utc_now(),
                "status": "success",
                "output_artifact": str(artifact),
                "permission_mode": manifest.mode,
                "writes_allowed": False,
            }
            self.store.append("heartbeat_runs", run)
            return {"run": run, "proposal": proposal}
        except Exception as exc:
            run = {
                "id": run_id,
                "loop_id": loop_id,
                "started_at": started,
                "finished_at": utc_now(),
                "status": "failed",
                "error": type(exc).__name__,
                "message": short_text(str(exc), 400),
                "permission_mode": manifest.mode,
                "writes_allowed": False,
            }
            self.store.append("heartbeat_runs", run)
            raise
        finally:
            try:
                lock.unlink()
            except FileNotFoundError:
                pass

    def proposals(self, limit: int = 20) -> List[Dict[str, object]]:
        if not self.proposal_dir.is_dir():
            return []
        rows: List[Dict[str, object]] = []
        for path in sorted(self.proposal_dir.glob("*.json"), reverse=True)[: max(1, min(int(limit), 100))]:
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
                row["path"] = str(path)
                rows.append(row)
            except Exception:
                rows.append({"path": str(path), "status": "corrupt"})
        return rows


def deterministic_finding(loop_id: str, input_summary: str) -> str:
    base = short_text(input_summary, 600)
    if loop_id == "operator_handoff_loop":
        return "Audit operator claims against durable conference events. Any claim without event_id is a fake affordance."
    if loop_id == "regression_guard_loop":
        return "Run identity, loop-status, LAN boundary, secret exposure, and unratified-write checks before any deploy."
    if loop_id == "proposal_consolidation_loop":
        return "Merge duplicate heartbeat proposals and keep ratification requirements explicit."
    if base:
        return f"Review observed friction: {base}"
    return "No fresh log summary was supplied; generate a proposal from the loop contract only."


def deterministic_next_step(loop_id: str) -> str:
    if loop_id == "operator_handoff_loop":
        return "Require Aoteru to create /misumi/operator-conferences before claiming the Operator will confer."
    if loop_id == "interaction_friction_loop":
        return "Surface pending operator conferences and failed handoffs in the interface status panel."
    if loop_id == "persona_contract_loop":
        return "Reject persona text that implies authority or action without a structured route/tool result."
    if loop_id == "usability_improvement_loop":
        return "Keep heartbeat/operator UI readable at 1024x768 with large text and few counters."
    if loop_id == "persona_function_loop":
        return "Draft missing persona tool contracts as proposals only; do not install powers automatically."
    if loop_id == "regression_guard_loop":
        return "Run tests before deploy and block any browser-visible token or autonomous production write."
    return "Append proposal to the ledger and wait for human ratification."

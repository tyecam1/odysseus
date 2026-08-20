"""estate_router.py — central model+host routing authority.

docs/aoteru-model-host-routing-contract.md (Phase B of the long-horizon
continuation contract). One routing authority for Odysseus: resolves
WHERE (host, via config/estate.yaml + ParkLease availability) before WHAT
(model/mechanism, via config/models.yaml's evidence-backed capability
aliases). Deliberately extends existing surfaces rather than duplicating
them — confirmed by a targeted audit before this file was written:

- `core.database.ModelEndpoint` / `src.llm_core.list_model_ids` remain the
  live model *inventory*; this module does not re-discover models, it
  resolves an *alias* to whatever `config/models.yaml` already records as
  evidence-backed.
- `src.llm_core` remains the actual provider-call layer; this module never
  makes an HTTP call to a model provider itself.
- `routes/task_routes.py`'s `ScheduledTask`/`TaskRun` remain the cron/event
  automation system; `core.database.RoutingDecision` is a separate,
  smaller outcome log for ad-hoc routing decisions, not a second job queue.
- `src.misumi_task_router` remains persona/task-file dispatch (a different
  concern entirely) and is untouched by this module.

Lab-first: only the `lab` host role is ever actually eligible right now
(`home` fails the live reachability check honestly, same as
`scripts/agent`'s dispatch logic) — this module still goes through the
same `eligible_hosts()` a future multi-host scoring pass would extend,
rather than hardcoding "always lab".
"""
from __future__ import annotations

import socket
import uuid
from pathlib import Path
from typing import Optional

import yaml

from src.runtime_paths import get_app_root

_CONFIG_DIR = Path(get_app_root()) / "config"


class RoutingConfigError(RuntimeError):
    """A registry file the router depends on is missing/malformed. Raised
    deliberately (P9 fault test: "stale inventory") rather than letting a
    raw YAML parser exception surface as an unhandled 500 — a config
    problem should fail as a clear, catchable error, not a stack trace."""


def _load_yaml(name: str) -> dict:
    path = _CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        return {}
    try:
        with path.open() as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise RoutingConfigError(f"config/{name}.yaml is malformed: {e}") from e


def host_reachable(host: dict, live_hostname: str) -> tuple[bool, str]:
    """Shared with `scripts/agent`, which imports this function directly
    rather than maintaining its own copy — a second, slightly-different
    reachability rule would itself be the kind of duplicate authority the
    routing contract forbids."""
    if host.get("hostname") == live_hostname:
        return True, "this host"
    if not host.get("tailscale"):
        return False, f"{host['id']!r} is not a tailnet member"
    dns = host.get("tailscale_dns")
    if not dns:
        return False, f"{host['id']!r} has no tailscale_dns recorded in config/estate.yaml"
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(4)
    try:
        s.connect((dns, 22))
        return True, "SSH port reachable over the tailnet"
    except OSError as e:
        return False, f"unreachable: {e}"
    finally:
        s.close()


def eligible_hosts(repo_id: Optional[str] = None) -> list[dict]:
    """Hard host-eligibility filter (contract's "Eligibility and scoring").
    The interface role is never a candidate (invariant 9: "The
    laptop/interface is the human control surface, not a normal execution
    worker"). If `repo_id` is given, a host also becomes ineligible when a
    *different* host already holds an active ParkLease for that repo —
    routing never widens write authority (invariant 10)."""
    estate = _load_yaml("estate")
    live_hostname = socket.gethostname()
    out = []
    for host in estate.get("hosts", []):
        if host.get("role") not in ("lab", "home"):
            continue
        reachable, reason = host_reachable(host, live_hostname)
        entry = {"host_id": host["id"], "role": host.get("role"), "eligible": reachable, "reason": reason}
        if reachable and repo_id:
            from core.database import ParkLease, get_db_session
            with get_db_session() as db:
                conflicting = db.query(ParkLease).filter(
                    ParkLease.repo_id == repo_id,
                    ParkLease.status == "active",
                    ParkLease.host_id != host["id"],
                ).first()
            if conflicting is not None:
                entry["eligible"] = False
                entry["reason"] = f"repo {repo_id!r} is parked on {conflicting.host_id!r}, not here"
        out.append(entry)
    return out


_OLLAMA_BASE = "http://127.0.0.1:11434"


def _ollama_model_live(model: str, timeout: float = 3.0) -> tuple[bool, str]:
    """Bounded live check against the local Ollama registry (P9 fault
    test: "model/runtime failure"). A static `binding` in
    config/models.yaml is evidence the model was benchmarked once, not
    evidence it is loadable right now — Ollama could be stopped, or the
    model could have been removed since. Only applies to local/Ollama-
    style bindings; a future paid-provider binding would need its own
    liveness check rather than reusing this one blindly."""
    import httpx
    try:
        resp = httpx.get(f"{_OLLAMA_BASE}/api/tags", timeout=timeout)
        resp.raise_for_status()
    except (httpx.HTTPError, OSError) as e:
        return False, f"Ollama unreachable at {_OLLAMA_BASE}: {e}"
    names = {m.get("name") for m in resp.json().get("models", [])}
    if model in names:
        return True, "live"
    return False, f"configured as {model!r} in config/models.yaml but not currently listed by Ollama"


def resolve_alias(alias: str) -> dict:
    """WHAT half: resolve a capability alias to a concrete model from
    config/models.yaml's evidence-backed bindings. Never a hardcoded brand
    in this function — an unbound alias fails truthfully rather than
    guessing a model. A bound alias is additionally checked live before
    being reported resolved — a config binding alone is not proof the
    model is actually available right now (see `_ollama_model_live`)."""
    models = _load_yaml("models")
    entry = next((c for c in models.get("capabilities", []) if c["alias"] == alias), None)
    if entry is None:
        return {"alias": alias, "resolved": False, "reason": f"unknown alias {alias!r}"}
    binding = entry.get("binding")
    if binding is None:
        return {
            "alias": alias, "resolved": False,
            "reason": "no evidence-backed binding yet — see config/models.yaml",
        }
    live, live_reason = _ollama_model_live(binding)
    if not live:
        return {
            "alias": alias, "resolved": False, "concrete_model": binding,
            "reason": f"bound but not currently live: {live_reason}",
        }
    return {"alias": alias, "resolved": True, "concrete_model": binding, "evidence": entry.get("evidence")}


def _record_decision(task: dict, *, host_id, executor, model_alias, concrete_model, status) -> str:
    """Telemetry is a side effect of routing, not the routing decision
    itself (P9 fault test: "partial result handling") — a caller who
    successfully got a route back must not lose that answer just because
    the telemetry write failed (DB unavailable, disk full, a threading/
    pooling quirk under a test's in-memory SQLite). Logged, not silently
    swallowed: a caller that actually needs to know telemetry didn't
    persist can check for the `decision-unrecorded-` id prefix."""
    from core.database import RoutingDecision, get_db_session
    decision_id = str(uuid.uuid4())
    try:
        with get_db_session() as db:
            db.add(RoutingDecision(
                id=decision_id,
                task_class=task.get("task_class") or "unclassified",
                complexity=task.get("complexity"),
                consequence=task.get("consequence"),
                host_id=host_id or "none",
                executor=executor,
                model_alias=model_alias,
                concrete_model=concrete_model,
                status=status,
            ))
    except Exception:
        import logging
        logging.getLogger(__name__).exception("routing_decisions write failed; route result is unaffected")
        return f"decision-unrecorded-{decision_id}"
    return decision_id


def resolve_route(task: dict) -> dict:
    """The routing API: canonical task envelope in, route out (docs/
    aoteru-model-host-routing-contract.md's "Canonical task envelope" /
    acceptance criterion #1). Resolves host before model (invariant 2).
    Records the decision to `routing_decisions` regardless of outcome —
    even a failed/blocked resolution is telemetry.

    Only the fields actually used by this lab-first implementation are
    required: `task_class` (str), optional `repo`, optional
    `requirements.capabilities` (list of alias names — only the first is
    used today; multi-capability tasks are future work). Everything else
    in the contract's full envelope schema is accepted and ignored rather
    than rejected, so callers can send the full envelope now without this
    module needing to understand every field yet.
    """
    repo_id = task.get("repo")
    hosts = eligible_hosts(repo_id)
    eligible = [h for h in hosts if h["eligible"]]

    if not eligible:
        decision_id = _record_decision(
            task, host_id=None, executor="none", model_alias=None,
            concrete_model=None, status="blocked",
        )
        return {
            "ok": False,
            "error": "no eligible host",
            "hosts_checked": hosts,
            "decision_id": decision_id,
        }

    # Lab-first: exactly one worker role is ever reachable, so there is
    # nothing to score among yet. This still goes through eligible_hosts()
    # rather than a hardcoded "lab" — a future multi-host scoring pass
    # extends the selection here, it doesn't redesign the function.
    host = eligible[0]

    capabilities = (task.get("requirements") or {}).get("capabilities") or []
    alias = capabilities[0] if capabilities else None
    alias_result = resolve_alias(alias) if alias else {"resolved": False, "reason": "no capability requested"}

    if alias is None:
        executor, status = "deterministic", "complete"
    elif alias_result.get("resolved"):
        executor, status = "local", "complete"
    else:
        executor, status = "none", "needs_escalation"

    decision_id = _record_decision(
        task, host_id=host["host_id"], executor=executor, model_alias=alias,
        concrete_model=alias_result.get("concrete_model"), status=status,
    )

    return {
        "ok": status != "needs_escalation",
        "route": {
            "host": host["host_id"],
            "executor": executor,
            "model_alias": alias,
            "concrete_model": alias_result.get("concrete_model"),
        },
        "hosts_checked": hosts,
        "alias_resolution": alias_result,
        "decision_id": decision_id,
    }

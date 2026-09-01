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

import json
import re
import socket
import uuid
from pathlib import Path
from typing import Optional

import yaml

from src.runtime_paths import get_app_root
from src.park_lease_ops import active_lease_for_repo
from src import worktree_ops

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
    routing contract forbids.

    Explicit `verified: false` (config/estate.yaml) is a hard gate checked
    before reachability, not after: a host that merely answers on the
    tailnet is not the same claim as a host whose identity has actually
    been confirmed (finding: "a newly reachable but unverified home host
    must never become eligible automatically"). A host with no `verified`
    key at all defaults to verified — this is the existing lab/interface
    convention, not a new category; only hosts that explicitly opt out
    (currently just the home host) are affected."""
    if host.get("verified", True) is False:
        return False, f"{host['id']!r} is not verified (config/estate.yaml verified: false) — reachability alone is not sufficient"
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


_HOST_LOCAL_ROOT_VAR_RE = re.compile(r"\$\{(\w+)\}")


def resolve_repo_path(repo_id: str) -> Optional[str]:
    """Resolve a `config/repositories.yaml` repo id to a real, existing
    filesystem path on THIS host, using the same `${ROOT_VAR}/...`
    template + `~/.aoteru/config.local.json` root-var convention
    `scripts/agent`'s `_resolve_repos`/`_resolve_path` already use —
    reused here (not re-derived) so a paid-escalation task grounded in a
    specific repo (docs/aoteru-final-convergence-activation.agent-
    task.md item 4: 'a task that cannot read its repo is a failed
    qualification') actually gets pointed at that repo's real directory
    instead of an empty scratch dir. Returns None if the repo id is
    unknown, its root var isn't set on this host, or the resolved path
    doesn't exist — never guesses."""
    registry = _load_yaml("repositories")
    entry = next((r for r in registry.get("repos", []) if r.get("id") == repo_id), None)
    if entry is None:
        return None
    template = entry.get("path")
    if not template:
        return None
    match = _HOST_LOCAL_ROOT_VAR_RE.search(template)
    if not match:
        return template if Path(template).exists() else None
    var = match.group(1)
    host_local_path = Path.home() / ".aoteru" / "config.local.json"
    try:
        host_local = json.loads(host_local_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    root = host_local.get(var)
    if not root:
        return None
    suffix = template[match.end():].lstrip("/\\")
    resolved = str(Path(root) / Path(suffix))
    return resolved if Path(resolved).exists() else None


def current_host_id() -> Optional[str]:
    """The `config/estate.yaml` host id matching the hostname this process
    is actually running on, or None if this host isn't registered at all.
    Shared identity lookup (Workstream B: the HTTP park/heartbeat/release
    surface needs the same "which host is this" resolution `scripts/agent`
    already does for its CLI subcommands, via a different code path since
    that script isn't an importable module) — kept here rather than
    duplicated at the route, for the same reason `host_reachable` already
    is."""
    estate = _load_yaml("estate")
    live_hostname = socket.gethostname()
    for host in estate.get("hosts", []):
        if host.get("hostname") == live_hostname:
            return host["id"]
    return None


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
            from core.database import ParkLease, get_db_session, park_lease_is_stale
            with get_db_session() as db:
                conflicting = db.query(ParkLease).filter(
                    ParkLease.repo_id == repo_id,
                    ParkLease.status == "active",
                    ParkLease.host_id != host["id"],
                ).first()
                # A stale lease (holder crashed/killed, heartbeat never
                # renewed — see park_lease_is_stale) does not get to block
                # routing forever; only a lease that is still actually
                # alive widens no other host's write authority (invariant
                # 10 is about live conflicts, not abandoned ones). This is
                # a read-only check — reclaiming the row itself still only
                # happens through `agent park`'s explicit reclaim path.
                if conflicting is not None and park_lease_is_stale(conflicting):
                    conflicting = None
            if conflicting is not None:
                entry["eligible"] = False
                entry["reason"] = f"repo {repo_id!r} is parked on {conflicting.host_id!r}, not here"
        out.append(entry)
    return out


_STALE_ACTIVE_SESSION_SECONDS = 300


def reconcile_stale_sessions(db, LogicalSession) -> int:
    """Sweep any `logical_sessions` row still `active` with no
    `claude_session_id` recorded past a bounded staleness window to
    `failed` (P5, Laptop Claude routing skill's session-mapping rule;
    core.database.LogicalSession's docstring covers the write-time half
    of this invariant). Centralized here — same reason `host_reachable`
    lives in this module rather than in `scripts/agent` — so `agent claude
    where` (local CLI) and `/api/estate/sessions` (HTTP, this module) read
    one reconciliation rule, not two that could drift apart."""
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=_STALE_ACTIVE_SESSION_SECONDS)
    stale = db.query(LogicalSession).filter(
        LogicalSession.status == "active",
        LogicalSession.claude_session_id.is_(None),
        LogicalSession.created_at < cutoff,
    ).all()
    for row in stale:
        row.status = "failed"
        row.last_result = json.dumps({
            "reconciled": True,
            "reason": "stale active session with no claude_session_id recorded within "
                      f"{_STALE_ACTIVE_SESSION_SECONDS}s — launch never confirmed",
        })
    return len(stale)


def active_logical_sessions() -> list[dict]:
    """Estate-wide active `LogicalSession` view — the laptop `where` mode
    (execution contract's "Laptop Claude routing skill — required UX").
    The checkout-free laptop client (companion/laptop_client/aoteru.py)
    has no local `core.database` to query directly, so this is also the
    body of `GET /api/estate/sessions` (routes/estate_routing_routes.py);
    `scripts/agent`'s `agent claude where` reads the same rows locally."""
    from core.database import LogicalSession, get_db_session
    with get_db_session() as db:
        reconcile_stale_sessions(db, LogicalSession)
        rows = db.query(LogicalSession).filter(LogicalSession.status == "active").all()
        return [{
            "id": r.id, "host_id": r.host_id, "repo_id": r.repo_id, "engine": r.engine,
            "claude_session_id": r.claude_session_id, "last_result": r.last_result,
        } for r in rows]


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


_EXPERIMENT_RESERVATION_PATH = Path.home() / ".aoteru" / "experiment_reservation.json"


def experiment_priority_active() -> tuple[bool, str]:
    """P12.4: robotics experiments outrank background Aoteru model use
    (boundary 5). Two independent signals, either is sufficient — an
    explicit host-local reservation file the operator/experiment tooling
    sets (`~/.aoteru/experiment_reservation.json`, never committed, same
    host-local convention as `~/.aoteru/config.local.json`), or live
    measured evidence: a non-Ollama process already holding significant
    GPU memory on this shared RTX 3080. Prefers this simple signal pair
    over a scheduler redesign — no existing host-load/reservation
    mechanism was found in a targeted search of src/ and core/ before
    this was added."""
    if _EXPERIMENT_RESERVATION_PATH.exists():
        try:
            import json
            data = json.loads(_EXPERIMENT_RESERVATION_PATH.read_text())
        except Exception:
            data = {}
        if data.get("active"):
            return True, data.get("reason") or "experiment_reservation.json: active"

    import subprocess
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return False, "no reservation; nvidia-smi unavailable for live GPU load check"
    if proc.returncode == 0:
        for line in proc.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                continue
            pid, name, mem = parts[0], parts[1], parts[2]
            if "ollama" in name.lower():
                continue
            try:
                mem_mib = float(mem)
            except ValueError:
                continue
            if mem_mib >= 500:
                return True, f"live GPU load: non-ollama process {name!r} (pid {pid}) using {mem_mib:.0f}MiB"
    return False, "no reservation; no significant non-ollama GPU load"


def resolve_alias(alias: str) -> dict:
    """WHAT half: resolve a capability alias to a concrete model from
    config/models.yaml's evidence-backed bindings. Never a hardcoded brand
    in this function — an unbound alias fails truthfully rather than
    guessing a model. A bound alias is additionally checked live before
    being reported resolved — a config binding alone is not proof the
    model is actually available right now (see `_ollama_model_live`).

    P12.4: an alias tagged `gpu_priority: yield_to_experiment` in
    config/models.yaml fails truthfully (not silently) while
    `experiment_priority_active()` says an experiment is reserved/active
    — heavy background inference must not contend with a live robotics
    experiment for the one shared RTX 3080. Aliases without that tag
    (`local-fast`, `code-fast`) are unaffected; idle-state routing is
    unaffected either way."""
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
    if entry.get("gpu_priority") == "yield_to_experiment":
        active, reason = experiment_priority_active()
        if active:
            return {
                "alias": alias, "resolved": False, "concrete_model": binding,
                "reason": f"withheld — experiment priority active ({reason})",
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
    persist can check for the `decision-unrecorded-` id prefix.

    `nondelegation_reason` is re-validated here, not trusted from the
    caller — `delegation_preflight`'s own validation only guards its own
    `/api/estate/preflight` entry point; a caller reaching this function
    through `resolve_route`/`run_task` (`/api/estate/route`,
    `/api/estate/run`) directly must not be able to stamp an unvalidated
    or junk reason onto telemetry and have it read as a legitimate
    controller retention (task's completion gate #5: the reason must be
    genuine, not merely present)."""
    from core.database import RoutingDecision, get_db_session
    from src.delegation_preflight import _valid_nondelegation_reason
    raw_reason = task.get("nondelegation_reason")
    nondelegation_reason = raw_reason.strip() if _valid_nondelegation_reason(raw_reason) else None
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
                nondelegation_reason=nondelegation_reason,
                recommended_route=task.get("recommended_route"),
                actual_route=task.get("actual_route"),
                status=status,
            ))
    except Exception:
        import logging
        logging.getLogger(__name__).exception("routing_decisions write failed; route result is unaffected")
        return f"decision-unrecorded-{decision_id}"
    return decision_id


_UNVERIFIABLE_BUDGET_FIELDS = (
    "max_worker_calls", "max_paid_calls", "max_frontier_calls",
    "max_context_tokens", "latency_priority",
)


def resolve_route(task: dict, *, record_decision: bool = True) -> dict:
    """The routing API: canonical task envelope in, route out (docs/
    aoteru-model-host-routing-contract.md's "Canonical task envelope" /
    acceptance criterion #1). Resolves host before model (invariant 2).
    Records the decision to `routing_decisions` regardless of outcome —
    even a failed/blocked resolution is telemetry.

    `record_decision=False` is reserved for delegation preflight, which
    inspects a prospective route without creating a duplicate unit row;
    the later `run_task` dispatch records the actual recommendation and
    outcome. Controller-retained preflight units are recorded directly by
    the preflight module because no worker dispatch follows them.

    Recognizes, beyond `task_class`/`repo`/`requirements.capabilities`:

    - `placement.requested_host`: an explicit non-"auto" value narrows
      eligibility to that host and fails truthfully (not a silent
      fallback to whatever else is eligible) if it isn't eligible —
      silently substituting a different host would violate the caller's
      explicit constraint.
    - `requirements.capabilities` (plural): *every* requested alias must
      resolve, not just the first — a task needing two capabilities where
      only one is bound is not actually routable.
    - `requirements.context_tokens`: checked against the resolved model's
      *known* context window (`src.model_context.get_context_length_known`
      — same "known vs fallback" distinction that module already draws)
      when a local alias is resolved; an unknown window is reported as
      unverified, never silently assumed adequate.
    - `routing.quality_floor`: config/models.yaml carries no numeric
      quality score (P7's evidence is single-prompt prose, not a
      benchmarked floor) — an explicit floor request always fails
      truthfully as unverifiable rather than fabricating a pass.
    - `budget.*`: no call/quota accounting exists yet in this lab-first
      slice; any budget field present is reported back under
      `unverified_constraints` rather than silently ignored, so a caller
      can see plainly that it wasn't actually enforced.

    Everything else in the contract's full envelope schema is accepted
    and ignored rather than rejected, so callers can send the real
    envelope now without this module needing to understand every field.
    """
    repo_id = task.get("repo")
    hosts = eligible_hosts(repo_id)
    eligible = [h for h in hosts if h["eligible"]]

    requested_host = (task.get("placement") or {}).get("requested_host")
    if requested_host and requested_host != "auto":
        narrowed = [h for h in eligible if h["host_id"] == requested_host or h["role"] == requested_host]
        if not narrowed:
            decision_id = _record_decision(
                task, host_id=None, executor="none", model_alias=None,
                concrete_model=None, status="blocked",
            ) if record_decision else None
            return {
                "ok": False,
                "error": f"requested host {requested_host!r} is not eligible",
                "reason": f"requested host {requested_host!r} failed live eligibility checks",
                "verification_outcome": None,
                "escalation_reason": "worker_failed",
                "hosts_checked": hosts,
                "decision_id": decision_id,
            }
        eligible = narrowed

    if not eligible:
        decision_id = _record_decision(
            task, host_id=None, executor="none", model_alias=None,
            concrete_model=None, status="blocked",
        ) if record_decision else None
        return {
            "ok": False,
            "error": "no eligible host",
            "reason": "no lab/home worker passed the live host eligibility checks",
            "verification_outcome": None,
            "escalation_reason": "worker_failed",
            "hosts_checked": hosts,
            "decision_id": decision_id,
        }

    # Lab-first: exactly one worker role is ever reachable, so there is
    # nothing to score among yet. This still goes through eligible_hosts()
    # rather than a hardcoded "lab" — a future multi-host scoring pass
    # extends the selection here, it doesn't redesign the function.
    host = eligible[0]

    capabilities = (task.get("requirements") or {}).get("capabilities") or []
    capability_resolutions = [resolve_alias(a) for a in capabilities]
    alias = capabilities[0] if capabilities else None
    alias_result = capability_resolutions[0] if capability_resolutions else {
        "resolved": False, "reason": "no capability requested",
    }
    all_resolved = bool(capability_resolutions) and all(r.get("resolved") for r in capability_resolutions)

    unverified_constraints = [
        f"budget.{field}" for field in _UNVERIFIABLE_BUDGET_FIELDS
        if (task.get("budget") or {}).get(field) is not None
    ]

    quality_floor = (task.get("routing") or {}).get("quality_floor")
    quality_floor_error = None
    if quality_floor:
        # Never fabricate a quality floor pass: config/models.yaml has no
        # benchmarked numeric quality score to check it against.
        quality_floor_error = (
            f"quality_floor {quality_floor!r} requested but no benchmarked quality "
            f"score exists in config/models.yaml to verify it against"
        )

    context_tokens = (task.get("requirements") or {}).get("context_tokens")
    context_error = None
    context_note = None
    if context_tokens and alias and alias_result.get("resolved"):
        from src.model_context import get_context_length_known
        window, known = get_context_length_known(_OLLAMA_BASE, alias_result["concrete_model"])
        if known and context_tokens > window:
            context_error = (
                f"requirements.context_tokens={context_tokens} exceeds "
                f"{alias_result['concrete_model']!r}'s known context window of {window}"
            )
        elif not known:
            context_note = f"requested context_tokens={context_tokens} could not be verified (unknown context window)"

    if not capabilities:
        executor, status = "deterministic", "complete"
    elif quality_floor_error or context_error:
        executor, status = "none", "needs_escalation"
    elif all_resolved:
        executor, status = "local", "complete"
    else:
        executor, status = "none", "needs_escalation"

    decision_id = _record_decision(
        task, host_id=host["host_id"], executor=executor, model_alias=alias,
        concrete_model=alias_result.get("concrete_model"), status=status,
    ) if record_decision else None

    if executor == "deterministic":
        route_reason = f"{host['host_id']} is eligible; no model capability was requested"
    elif executor == "local":
        route_reason = f"{host['host_id']} is eligible; all requested aliases resolve to live local models"
    else:
        unresolved = next((r.get("reason") for r in capability_resolutions if not r.get("resolved")), None)
        route_reason = f"{host['host_id']} is eligible; local capability needs escalation: {unresolved or 'constraint failed'}"

    result = {
        "ok": status != "needs_escalation",
        "route": {
            "host": host["host_id"],
            "executor": executor,
            "model_alias": alias,
            "concrete_model": alias_result.get("concrete_model"),
            "reason": route_reason,
        },
        "reason": route_reason,
        "verification_outcome": None,
        "escalation_reason": (
            "quality_floor_not_met" if quality_floor_error else
            "context_limit" if context_error else
            "insufficient_capability" if status == "needs_escalation" else None
        ),
        "hosts_checked": hosts,
        "alias_resolution": alias_result,
        "capability_resolutions": capability_resolutions,
        "decision_id": decision_id,
    }
    if quality_floor_error:
        result["quality_floor_error"] = quality_floor_error
    if context_error:
        result["context_error"] = context_error
    if context_note:
        result["context_note"] = context_note
    if unverified_constraints:
        result["unverified_constraints"] = unverified_constraints
    return result


def _update_decision_outcome(decision_id: str, *, status: str, deterministic_gate: str,
                             latency_ms: Optional[int] = None, escalation_reason: Optional[str] = None,
                             executor: Optional[str] = None, escalated: Optional[bool] = None,
                             actual_route: Optional[str] = None,
                             verification_outcome: Optional[str] = None) -> None:
    """Execution happens after `resolve_route()` already wrote its
    decision row — update that same row with the real outcome rather than
    writing a second telemetry row for one routed task (`RoutingDecision`
    is 'one row per routed task', not one row per stage). Same
    swallow-and-log discipline as `_record_decision`: a telemetry update
    failing must not turn an actually-successful execution into a
    reported failure."""
    if decision_id.startswith("decision-unrecorded-"):
        return  # the routing write itself already failed; nothing to update
    from core.database import RoutingDecision, get_db_session
    try:
        with get_db_session() as db:
            row = db.query(RoutingDecision).filter(RoutingDecision.id == decision_id).first()
            if row is not None:
                row.status = status
                row.deterministic_gate = deterministic_gate
                if latency_ms is not None:
                    row.latency_ms = latency_ms
                if escalation_reason is not None:
                    row.escalation_reason = escalation_reason
                if executor is not None:
                    row.executor = executor
                if escalated is not None:
                    row.escalated = escalated
                if actual_route is not None:
                    row.actual_route = actual_route
                if verification_outcome is not None:
                    row.verification_outcome = verification_outcome
    except Exception:
        import logging
        logging.getLogger(__name__).exception("routing_decisions outcome update failed; execution result is unaffected")


def _retryable_local_error(exc: Exception) -> bool:
    """Classify a local-execution failure as retryable. Only transient
    transport failures (connection refused/reset, DNS hiccup, upstream
    timeout) qualify — a bad request, an auth failure, or any other
    deterministic upstream rejection would fail identically on a second
    attempt and just doubles latency for no benefit."""
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    text = str(exc).lower()
    return any(marker in text for marker in (
        "connection refused", "connection reset", "connection aborted",
        "timed out", "timeout", "temporarily unavailable",
    ))


def execute_local(concrete_model: str, objective: "str | list[dict]", *, timeout: float = 60.0,
                   max_retries: int = 1) -> dict:
    """WHAT actually happens once WHERE+WHAT have been resolved: the one
    provider-neutral bounded execution/result path this lab-first slice
    can run for real right now (no claude/codex binary or paid
    ModelEndpoint available — see scripts/agent's cmd_claude). Reuses
    `src.llm_core.llm_call` — the actual provider-call layer — rather than
    a second HTTP client living in this module; "provider-neutral" because
    `llm_call` already dispatches on URL shape, so a future non-Ollama
    local runtime needs no new code here. Bounded by `timeout` (llm_call's
    own `timeout` kwarg) so a hung/slow local model can't hang the caller
    indefinitely; every failure mode (timeout, connection refused,
    malformed upstream response) is caught and returned as a clean
    `{"ok": False, "error": ...}` rather than a raised exception, matching
    every other truthful-failure surface in this module.

    `objective` also accepts the OpenAI-style multimodal content list
    `llm_call`/`estimate_tokens` already understand (P12.2, docs/aoteru-
    p12-active-estate-convergence.md): `[{"type": "text", ...},
    {"type": "image_url", "image_url": {"url": "data:..."}}, ...]`. This
    was already structurally true before P12.2 — `objective` was always
    passed straight into `messages[0]["content"]` unmodified, and both
    `estimate_tokens` (src/model_context.py) and `llm_call`'s multimodal
    conversion already branch on `isinstance(content, list)` — P12.2's
    contribution is verifying and documenting that fact so callers stop
    bypassing this function for vision (see
    scripts/run_lm4_production_canary.py's `run_vision_task`, written
    before this was confirmed). Plain-string callers are unaffected.

    `max_retries` (default 1) bounds retry of transient transport
    failures only (`_retryable_local_error`: connection refused/reset,
    timeout) — free local calls, so retrying costs latency, not money.
    A deterministic upstream rejection (`HTTPException`, e.g. bad
    request/model-not-found) never retries. The paid path
    (`execute_codex`) intentionally has no retry logic at all — never
    blindly repeat a paid prompt (Workstream C invariant)."""
    from fastapi import HTTPException

    from src.llm_core import llm_call
    from src.model_context import select_bounded_context

    import time
    messages = [{"role": "user", "content": objective}]
    started = time.monotonic()
    # Bound the context request to what this actual objective needs (see
    # select_bounded_context) rather than the model's full advertised window —
    # requesting the full window regardless of prompt size is real, measured
    # LM1 evidence of production overhead/timeouts, not a hypothetical.
    num_ctx = select_bounded_context(_OLLAMA_BASE, concrete_model, messages)
    attempts = 0
    last_error: Optional[dict] = None
    while attempts <= max_retries:
        attempts += 1
        try:
            output = llm_call(_OLLAMA_BASE, concrete_model, messages, timeout=int(timeout), num_ctx=num_ctx)
        except HTTPException as e:
            # A deterministic upstream rejection (bad request, model not
            # found, etc.) — retrying would not change it.
            return {"ok": False, "error": f"{e.status_code}: {e.detail}", "retries": attempts - 1,
                    "latency_ms": int((time.monotonic() - started) * 1000)}
        except Exception as e:
            last_error = {"ok": False, "error": str(e), "retries": attempts - 1,
                           "latency_ms": int((time.monotonic() - started) * 1000)}
            if attempts <= max_retries and _retryable_local_error(e):
                continue
            return last_error
        return {"ok": True, "output": output, "retries": attempts - 1,
                "latency_ms": int((time.monotonic() - started) * 1000)}
    return last_error  # pragma: no cover — loop always returns above


def _resolve_codex_binary() -> tuple[Optional[str], str]:
    """Which `codex` binary to actually invoke (docs/aoteru-final-
    convergence-activation.agent-task.md item 4: "prefer fixing/updating
    tooling over disabling the sandbox"). The system PATH copy on this
    host (apt bubblewrap 0.6.1 + an old global npm codex-cli 0.116.0) was
    confirmed broken — `bwrap: Unknown option --argv0` — because the
    installed codex-cli predates upstream's current bubblewrap-
    compatibility path, NOT because sandboxing itself is unsafe here.
    Global npm upgrade requires root (EACCES, confirmed) and was not
    attempted with sudo/bypass. A user-local install
    (`npm install --prefix ~/.local/codex-cli @openai/codex@latest`, no
    root needed) fixed it — confirmed live: codex-cli 0.149.0 read this
    repo's real files under the exact same `--sandbox read-only`
    invocation with no bwrap error. Prefer that local install if present;
    fall back to the system PATH copy otherwise (still `--sandbox
    read-only` either way — this only changes which binary answers the
    same call, never the flags/isolation)."""
    local_candidate = Path.home() / ".local" / "codex-cli" / "node_modules" / ".bin" / "codex"
    if local_candidate.exists():
        return str(local_candidate), "user-local (~/.local/codex-cli, no sudo/global-policy change)"
    import shutil
    system_candidate = shutil.which("codex")
    if system_candidate:
        return system_candidate, "system PATH"
    return None, "not found (checked user-local and system PATH)"


def _codex_available() -> tuple[bool, str]:
    """Host-local credential/runtime check for the `codex` CLI paid
    worker (P12.3, docs/aoteru-p12-active-estate-convergence.md). Never
    prints/reads the credential contents — only that a `codex` binary
    resolves (see `_resolve_codex_binary`) and `~/.codex/auth.json`
    exists, the same "host-local auth, no secrets moved between hosts"
    discipline as every other credential check in this codebase."""
    binary, _source = _resolve_codex_binary()
    if not binary:
        return False, "codex binary not found (checked user-local install and system PATH)"
    auth_path = Path.home() / ".codex" / "auth.json"
    if not auth_path.exists():
        return False, "no ~/.codex/auth.json on this host — codex is not logged in"
    return True, binary


def _execute_codex_with_sandbox(objective: str, *, sandbox: str, provider: str,
                                timeout: float = 180.0, cwd: Optional[str] = None) -> dict:
    """Share bounded CLI mechanics without making sandbox choice policy.

    Only the public advisory/write functions choose the sandbox. Keeping
    credential checks, ephemeral execution, timeout, and error handling in
    one place prevents the narrow write lane drifting from the established
    paid-worker behavior.
    """
    import os
    import signal
    import subprocess
    import tempfile
    import time

    available, detail = _codex_available()
    if not available:
        return {"ok": False, "error": f"codex unavailable: {detail}", "provider": provider}
    codex_binary = detail  # _codex_available() returns the resolved binary path on success

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="p12-codex-") as scratch:
        out_path = str(Path(scratch) / "codex-last-message.txt")
        try:
            proc = subprocess.Popen(
                [
                    codex_binary, "exec",
                    "--sandbox", sandbox,
                    "--ephemeral",
                    "--skip-git-repo-check",
                    "-C", cwd or scratch,
                    "-o", out_path,
                    objective,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            # start_new_session=True makes the new process group's id equal
            # to the leader's pid at the moment of creation. Capture it now
            # rather than rediscovering it via os.getpgid(proc.pid) after a
            # timeout: if the leader (e.g. a wrapper that forks a detached
            # child and exits itself) has already exited by then, its pid no
            # longer resolves to a live process and getpgid raises
            # ProcessLookupError - silently leaving any surviving descendant
            # (which inherited the same pgid, independent of the leader
            # continuing to exist) unkilled.
            process_group_id = proc.pid
            stdout, stderr = proc.communicate(timeout=timeout)
            latency_ms = int((time.monotonic() - started) * 1000)
            if proc.returncode != 0:
                return {
                    "ok": False, "provider": provider, "latency_ms": latency_ms,
                    "error": f"codex exec exited {proc.returncode}: {(stderr or '')[-500:]}",
                    "codex_binary": codex_binary,
                }
            output = Path(out_path).read_text().strip() if Path(out_path).exists() else ""
            return {"ok": True, "provider": provider, "output": output, "latency_ms": latency_ms,
                    "codex_binary": codex_binary}
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process_group_id, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError:
                pass
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            return {"ok": False, "provider": provider, "error": f"codex exec timed out after {timeout}s",
                    "latency_ms": int((time.monotonic() - started) * 1000)}
        except Exception as e:
            return {"ok": False, "provider": provider, "error": str(e),
                    "latency_ms": int((time.monotonic() - started) * 1000)}


def execute_codex(objective: str, *, timeout: float = 180.0, cwd: Optional[str] = None) -> dict:
    """Run the existing paid Codex lane as bounded, read-only advice.

    This remains the default escalation contract: bounded, ephemeral, and
    `--sandbox read-only`, so existing callers receive advisory output and
    cannot mutate a repo. It does not rely on a ParkLease; implementation
    authority is isolated in `execute_codex_write`.
    """
    return _execute_codex_with_sandbox(
        objective, sandbox="read-only", provider="codex", timeout=timeout, cwd=cwd,
    )


def _codex_write_authority(repo_id: str, host_id: str) -> dict:
    """Resolve the repo and prove its existing lease without acquiring one."""
    if resolve_repo_path(repo_id) is None:
        return {"ok": False, "error": f"implementation mode cannot resolve registered repo {repo_id!r} on this host"}
    lease = active_lease_for_repo(repo_id, host_id)
    if lease is None:
        return {
            "ok": False,
            "error": f"implementation mode requires an active non-stale lease for {repo_id!r} held by {host_id!r}",
        }
    if lease.get("allowed_write_scope") != "repo":
        return {"ok": False, "error": f"active lease for {repo_id!r} does not grant repo write scope"}
    branch = lease.get("branch")
    if not branch:
        return {"ok": False, "error": f"active lease for {repo_id!r} is missing an enforced branch"}
    lease_path = lease.get("worktree_path")
    if not lease_path:
        return {"ok": False, "error": f"active lease for {repo_id!r} has no worktree_path"}
    if worktree_ops.is_live_checkout_path(repo_id, lease_path):
        return {"ok": False, "error": f"refusing implementation mode in live registered checkout for {repo_id!r}"}
    verification = worktree_ops.verify_worktree(repo_id, lease_path, branch)
    if not verification["ok"]:
        return {
            "ok": False,
            "error": f"active lease worktree for {repo_id!r} failed verification: {verification['reason']}",
        }
    return {"ok": True, "cwd": verification["path"], "lease_id": lease["lease_id"]}


def execute_codex_write(objective: str, *, repo_id: str, host_id: str,
                        timeout: float = 180.0) -> dict:
    """Run Codex workspace-write inside a previously validated lease.

    This function independently proves the active lease and resolved
    worktree so direct Python callers cannot bypass `run_task`'s gate. It
    deliberately cannot acquire or broaden write authority.
    """
    authority = _codex_write_authority(repo_id, host_id)
    if not authority["ok"]:
        return {
            "ok": False, "provider": "codex-write",
            "authority_denied": True, "error": authority["error"],
        }
    return _execute_codex_with_sandbox(
        objective, sandbox="workspace-write", provider="codex-write", timeout=timeout,
        cwd=authority["cwd"],
    )


# Provider dispatch table (Workstream C: "cheap/strong paid capability
# aliases via config, not hardcoded names"). The *selection* of which
# provider backs a given alias, and what name gets recorded as
# executor/concrete_model, comes from config/models.yaml
# (paid_providers/default_paid_provider/per-alias paid_provider) via
# `_resolve_paid_provider` below — this dict is only the unavoidable code
# side (an actual callable can't live in YAML). Only `codex` has a real
# implementation today; adding a second provider means adding both a real
# `execute_<provider>` function and an entry here, not just a config line.
#
# Maps provider name -> this module's own function *name* rather than the
# function object directly, resolved via globals() at call time — tests
# (and any future caller) monkeypatch `estate_router.execute_codex` the
# same way they already monkeypatch `execute_local`; binding the object
# here at import time would silently stop honouring that patch.
_PAID_PROVIDER_FUNCTION_NAMES = {"codex": "execute_codex"}
_PAID_PROVIDER_WRITE_FUNCTION_NAMES = {"codex": "execute_codex_write"}


def _resolve_paid_provider(alias: Optional[str]) -> dict:
    """Which paid provider backs `alias`'s escalation, read from
    config/models.yaml rather than hardcoded. Resolution order: the
    alias's own `paid_provider` (if the alias is registered and sets
    one) -> `default_paid_provider` -> unresolved (a caller with no paid
    provider configured at all gets a truthful failure, not a silent
    guess). Returns `{"provider": name, "concrete_model_label": label}`
    or `{"provider": None, "reason": ...}`."""
    models = _load_yaml("models")
    entry = next((c for c in models.get("capabilities", []) if c.get("alias") == alias), None) if alias else None
    provider_name = (entry or {}).get("paid_provider") or models.get("default_paid_provider")
    if not provider_name:
        return {"provider": None, "reason": "no paid_provider configured for this alias and no default_paid_provider set"}
    registry = {p["name"]: p for p in models.get("paid_providers", []) if p.get("name")}
    provider_entry = registry.get(provider_name, {})
    return {
        "provider": provider_name,
        "concrete_model_label": provider_entry.get("concrete_model_label", provider_name),
    }


def run_task(task: dict) -> dict:
    """Closes the execution gap: `resolve_route()` alone only answers
    WHERE+WHAT, it never calls a model. `run_task()` routes first (same
    `resolve_route()`, unchanged — deterministic-first and parking/domain
    gates are untouched), then actually executes when the resolved
    executor is `local`. A `deterministic` route has no model to call and
    is returned as `executed: False` (there was nothing to execute — the
    route itself already is the answer, same as before this function
    existed).

    P12.3: a `needs_escalation` route (typically an unbound/unavailable
    local capability, e.g. `code-strong`) is executed against the
    provider-neutral paid worker (`execute_codex`, currently the only
    paid mechanism with a live host-local credential — see
    `_codex_available`) only when the caller opts in via
    `task["routing"]["allow_paid_escalation"]: true`. This is
    evidence-triggered escalation, not automatic paid fallback for every
    routine task (invariant 11, escalation_triggers in
    config/routing.yaml) — a caller that does not ask for paid escalation
    still gets the prior honest `executed: False` result. Preserves the
    economic ladder (deterministic -> qualified local -> paid): this
    branch is only reached once the local route has already failed.

    The deterministic gate applied to a local execution result is
    intentionally minimal and does not fabricate a quality floor (that
    would need real benchmark evidence, per config/models.yaml's own
    convention) — it only checks the model actually returned a non-empty
    response, the cheapest real signal available before any task-specific
    verification exists.

    `task["objective"]` accepts a plain string (unchanged) or an
    OpenAI-style multimodal content list (P12.2) — see `execute_local`'s
    docstring. All current capability aliases, including `vision`, now
    traverse this one route/job/telemetry path; a caller no longer needs
    to bypass to `resolve_route()` + `llm_call` directly for image input.

    `routing.mode: implementation` selects the separate Codex workspace-
    write lane only after this host proves it already holds a live repo
    lease. Missing repo, path, host identity, or lease fails closed; the
    advisory paid lane above remains unchanged when mode is absent.
    """
    task = dict(task)
    if not task.get("recommended_route"):
        from src.delegation_preflight import recommended_lane_for_task
        task["recommended_route"] = recommended_lane_for_task(task)
    route = resolve_route(task)
    executor = (route.get("route") or {}).get("executor")
    if executor != "local":
        routing = task.get("routing") or {}
        allow_paid = routing.get("allow_paid_escalation")
        implementation_mode = routing.get("mode") == "implementation"
        if route.get("route", {}).get("executor") == "none" and route.get("decision_id") \
                and allow_paid and (task.get("objective") is not None):
            provider_choice = _resolve_paid_provider(route["route"].get("model_alias"))
            provider_name = provider_choice.get("provider")
            provider_functions = (
                _PAID_PROVIDER_WRITE_FUNCTION_NAMES if implementation_mode
                else _PAID_PROVIDER_FUNCTION_NAMES
            )
            provider_fn_name = provider_functions.get(provider_name)
            provider_fn = globals().get(provider_fn_name) if provider_fn_name else None
            if provider_name is None or provider_fn is None:
                return {**route, "executed": False, "execution_error": provider_choice.get(
                    "reason", f"paid provider {provider_name!r} has no "
                    f"{'write ' if implementation_mode else ''}implementation",
                )}
            objective = task.get("objective")
            paid_objective = objective if isinstance(objective, str) else str(objective)
            # Ground the paid worker in the task's actual repo if one was
            # named (docs/aoteru-final-convergence-activation.agent-
            # task.md item 4: "a task that cannot read its repo is a
            # failed qualification, even if the CLI process exits zero").
            # Without this, execute_codex() defaults to an empty scratch
            # dir regardless of what repo the task is about — confirmed
            # live: a real repo_reconnaissance task previously reported
            # 'No src/ directory found' because it was never pointed at
            # the repo at all. resolve_repo_path() returns None (no cwd
            # override) for an unknown/unresolved repo id rather than
            # guessing a path.
            repo_cwd = resolve_repo_path(task.get("repo")) if task.get("repo") else None
            executor_name = provider_name
            if implementation_mode:
                executor_name = f"{provider_name}-write"
                error = None
                repo_id = task.get("repo")
                host_id = current_host_id()
                if not repo_id:
                    error = "implementation mode requires task.repo and an existing active write lease"
                elif host_id is None:
                    error = "implementation mode requires this backend host to be registered in config/estate.yaml"
                elif route["route"].get("host") != host_id:
                    error = (
                        f"implementation route selected {route['route'].get('host')!r}, but the "
                        f"write executor runs on lease holder {host_id!r}"
                    )
                if error:
                    _update_decision_outcome(
                        route["decision_id"], status="blocked", deterministic_gate="fail",
                        escalation_reason="write_lease_missing", escalated=True,
                        verification_outcome="fail",
                    )
                    return {
                        **route, "ok": False, "executed": False,
                        "execution_error": error,
                        "escalation_reason": "write_lease_missing",
                        "verification_outcome": "fail",
                    }
                result = provider_fn(paid_objective, repo_id=repo_id, host_id=host_id)
                if result.get("authority_denied"):
                    _update_decision_outcome(
                        route["decision_id"], status="blocked", deterministic_gate="fail",
                        escalation_reason="write_lease_missing", escalated=True,
                        verification_outcome="fail",
                    )
                    return {
                        **route, "ok": False, "executed": False,
                        "execution_error": result["error"],
                        "escalation_reason": "write_lease_missing",
                        "verification_outcome": "fail",
                    }
            else:
                result = provider_fn(paid_objective, cwd=repo_cwd)
            gate = "pass" if result.get("ok") and (result.get("output") or "").strip() else "fail"
            _update_decision_outcome(
                route["decision_id"],
                status="complete" if gate == "pass" else "failed",
                deterministic_gate=gate,
                latency_ms=result.get("latency_ms"),
                escalation_reason="insufficient_capability" if gate == "pass" else "worker_failed",
                executor=executor_name,
                escalated=True,
                actual_route=executor_name,
                verification_outcome=gate,
            )
            reason = (
                f"local capability was insufficient; {executor_name} executed on "
                f"{route['route']['host']}" + (" under the active repo lease" if implementation_mode else " read-only")
            )
            route = {
                **route, "ok": gate == "pass", "reason": reason,
                "route": {
                    **route["route"], "executor": executor_name,
                    "concrete_model": provider_choice["concrete_model_label"],
                    "reason": reason,
                },
            }
            return {
                **route, "executed": True, "execution": result,
                "deterministic_gate": gate, "verification_outcome": gate,
                "escalation_reason": "insufficient_capability" if gate == "pass" else "worker_failed",
            }
        return {**route, "executed": False}

    concrete_model = route["route"]["concrete_model"]
    objective = task.get("objective")
    if not objective:
        return {**route, "executed": False, "execution_error": "no objective provided to execute"}

    result = execute_local(concrete_model, objective)
    gate = "pass" if result.get("ok") and (result.get("output") or "").strip() else "fail"
    _update_decision_outcome(
        route["decision_id"],
        status="complete" if gate == "pass" else "failed",
        deterministic_gate=gate,
        latency_ms=result.get("latency_ms"),
        escalation_reason=None if gate == "pass" else "worker_failed",
        actual_route="local",
        verification_outcome=gate,
    )
    return {
        **route, "executed": True, "execution": result,
        "deterministic_gate": gate, "verification_outcome": gate,
        "escalation_reason": None if gate == "pass" else "worker_failed",
    }

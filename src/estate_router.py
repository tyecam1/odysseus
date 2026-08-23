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


_UNVERIFIABLE_BUDGET_FIELDS = (
    "max_worker_calls", "max_paid_calls", "max_frontier_calls",
    "max_context_tokens", "latency_priority",
)


def resolve_route(task: dict) -> dict:
    """The routing API: canonical task envelope in, route out (docs/
    aoteru-model-host-routing-contract.md's "Canonical task envelope" /
    acceptance criterion #1). Resolves host before model (invariant 2).
    Records the decision to `routing_decisions` regardless of outcome —
    even a failed/blocked resolution is telemetry.

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
            )
            return {
                "ok": False,
                "error": f"requested host {requested_host!r} is not eligible",
                "hosts_checked": hosts,
                "decision_id": decision_id,
            }
        eligible = narrowed

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
    )

    result = {
        "ok": status != "needs_escalation",
        "route": {
            "host": host["host_id"],
            "executor": executor,
            "model_alias": alias,
            "concrete_model": alias_result.get("concrete_model"),
        },
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
                             executor: Optional[str] = None, escalated: Optional[bool] = None) -> None:
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


def _codex_available() -> tuple[bool, str]:
    """Host-local credential/runtime check for the `codex` CLI paid
    worker (P12.3, docs/aoteru-p12-active-estate-convergence.md). Never
    prints/reads the credential contents — only that `codex` is on PATH
    and `~/.codex/auth.json` exists, the same "host-local auth, no
    secrets moved between hosts" discipline as every other credential
    check in this codebase."""
    import shutil
    binary = shutil.which("codex")
    if not binary:
        return False, "codex binary not found on PATH"
    auth_path = Path.home() / ".codex" / "auth.json"
    if not auth_path.exists():
        return False, "no ~/.codex/auth.json on this host — codex is not logged in"
    return True, binary


def execute_codex(objective: str, *, timeout: float = 180.0, cwd: Optional[str] = None) -> dict:
    """The provider-neutral paid worker mechanism (P12.3): smallest
    extension of the existing `codex` CLI already installed/authenticated
    on this host, selected by this router the same way `execute_local`
    is — not a second orchestrator. Runs bounded and read-only
    (`--sandbox read-only`, `--ephemeral`, no persisted session state) so
    a paid escalation can never itself become an unreviewed mutation;
    P3's parking/lease authority still gates any real repo mutation a
    human/task later decides to make from codex's answer. Every failure
    mode (binary missing, not authenticated, timeout, non-zero exit) is
    returned as a clean `{"ok": False, "error": ...}`, matching
    `execute_local`'s truthful-failure convention rather than raising."""
    import subprocess
    import tempfile
    import time

    available, detail = _codex_available()
    if not available:
        return {"ok": False, "error": f"codex unavailable: {detail}", "provider": "codex"}

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="p12-codex-") as scratch:
        out_path = str(Path(scratch) / "codex-last-message.txt")
        try:
            proc = subprocess.run(
                [
                    "codex", "exec",
                    "--sandbox", "read-only",
                    "--ephemeral",
                    "--skip-git-repo-check",
                    "-C", cwd or scratch,
                    "-o", out_path,
                    objective,
                ],
                capture_output=True, text=True, timeout=timeout,
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            if proc.returncode != 0:
                return {
                    "ok": False, "provider": "codex", "latency_ms": latency_ms,
                    "error": f"codex exec exited {proc.returncode}: {(proc.stderr or '')[-500:]}",
                }
            output = Path(out_path).read_text().strip() if Path(out_path).exists() else ""
            return {"ok": True, "provider": "codex", "output": output, "latency_ms": latency_ms}
        except subprocess.TimeoutExpired:
            return {"ok": False, "provider": "codex", "error": f"codex exec timed out after {timeout}s",
                    "latency_ms": int((time.monotonic() - started) * 1000)}
        except Exception as e:
            return {"ok": False, "provider": "codex", "error": str(e),
                    "latency_ms": int((time.monotonic() - started) * 1000)}


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
    """
    route = resolve_route(task)
    executor = (route.get("route") or {}).get("executor")
    if executor != "local":
        allow_paid = (task.get("routing") or {}).get("allow_paid_escalation")
        if route.get("route", {}).get("executor") == "none" and route.get("decision_id") \
                and allow_paid and (task.get("objective") is not None):
            objective = task.get("objective")
            paid_objective = objective if isinstance(objective, str) else str(objective)
            result = execute_codex(paid_objective)
            gate = "pass" if result.get("ok") and (result.get("output") or "").strip() else "fail"
            _update_decision_outcome(
                route["decision_id"],
                status="complete" if gate == "pass" else "failed",
                deterministic_gate=gate,
                latency_ms=result.get("latency_ms"),
                escalation_reason="insufficient_capability" if gate == "pass" else "worker_failed",
                executor="codex",
                escalated=True,
            )
            route = {**route, "ok": gate == "pass",
                     "route": {**route["route"], "executor": "codex", "concrete_model": "codex-cli"}}
            return {**route, "executed": True, "execution": result, "deterministic_gate": gate}
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
    )
    return {**route, "executed": True, "execution": result, "deterministic_gate": gate}

"""estate_routing_routes.py — HTTP surface for the central model+host
routing authority (docs/aoteru-model-host-routing-contract.md, Phase B).

Thin wrapper over `src.estate_router` — no routing logic lives here. This
is what acceptance criterion #1 ("One Odysseus-owned routing API accepts
the canonical task envelope and returns a host+mechanism+model route")
resolves to at the HTTP layer.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Union

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from src.auth_helpers import require_user
from src.estate_router import (
    RoutingConfigError,
    current_host_id,
    eligible_hosts,
    resolve_alias,
    resolve_route,
    run_task,
)
from src.park_lease_ops import NoActiveLease, active_leases_summary, heartbeat_repo, release_repo

# Bounds the serialized size of `objective` (text or a multimodal content
# list — a few embedded base64 images can legitimately be several MB).
# Nothing downstream currently caps this: select_bounded_context()
# (src/model_context.py) only bounds the *requested context window*, not
# the size of the HTTP payload/prompt actually sent — an oversized
# objective would still be fully constructed and shipped to a shared,
# expensive resource (Ollama on the lab GPU) before any model-side limit
# kicks in. 8 MB comfortably covers a handful of realistic photos plus a
# long text prompt while still rejecting a clearly abusive payload.
_MAX_OBJECTIVE_BYTES = 8 * 1024 * 1024


def _scope_owner(request: Request, allowed: set[str]) -> str:
    """Authorize an estate-routing call. A session-cookie caller (the
    operator using the web UI) is unrestricted, same as every other scoped
    route family (see routes/codex_routes.py's identical helper) — scope
    gating exists for API tokens (e.g. a laptop thin-client credential,
    Workstream B) so a token minted for one purpose can't silently also
    drive paid escalation/execution on the estate."""
    if getattr(request.state, "api_token", False):
        scopes = set(getattr(request.state, "api_token_scopes", []) or [])
        if not scopes.intersection(allowed):
            required = " or ".join(sorted(allowed))
            raise HTTPException(403, f"API token missing required scope: {required}")
        return getattr(request.state, "api_token_owner", None) or "api-token"
    return require_user(request)


def _route_call(fn, *args, **kwargs):
    """P9 fault test ("stale inventory"): a malformed registry file must
    fail as a clean, informative error — not an unhandled 500 with a raw
    YAML-parser traceback."""
    try:
        return fn(*args, **kwargs)
    except RoutingConfigError as e:
        raise HTTPException(503, str(e)) from e


class TaskEnvelopeRequirements(BaseModel):
    capabilities: List[str] = Field(default_factory=list)
    context_tokens: Optional[int] = None


class TaskEnvelope(BaseModel):
    """Accepts the full canonical envelope shape (docs/aoteru-model-host-
    routing-contract.md "Canonical task envelope") but only task_class,
    repo, and requirements.capabilities are used by this lab-first
    implementation — everything else is accepted and ignored rather than
    rejected, so callers can send the real envelope now."""
    task_class: str = "unclassified"
    repo: Optional[str] = None
    complexity: Optional[str] = None
    consequence: Optional[str] = None
    requirements: TaskEnvelopeRequirements = Field(default_factory=TaskEnvelopeRequirements)


class RunTaskEnvelope(TaskEnvelope):
    """Same envelope, plus `objective` — the actual prompt text to execute
    once routing resolves a `local` route. Optional because a caller may
    legitimately only want the route (deterministic/needs_escalation
    tasks have nothing to execute anyway).

    `allow_paid_escalation` surfaces `run_task()`'s existing opt-in gate
    (src/estate_router.py) at the HTTP layer — previously only reachable
    from Python callers, so no HTTP caller (including a future laptop
    thin client, Workstream B) could ever trigger the governed paid
    (Codex) lane. Still requires the `estate:execute` scope this whole
    endpoint already requires; this field does not grant any new
    authority, it only unlocks routing behaviour that authority already
    permits.

    BUG FIX (found live this session, Workstream J validation): this
    field was accidentally dropped entirely by the same commit that added
    `allow_paid_escalation` — pydantic v2 silently ignores an unknown
    kwarg by default (no error), so every `objective` an HTTP caller sent
    (including companion/laptop_client/aoteru.py's `ask` command) was
    dropped before it ever reached `run_task()`, which then correctly
    reported 'no objective provided to execute' for every single HTTP
    `/api/estate/run` call since that commit. Restored, and widened to
    also accept the OpenAI-style multimodal content list `run_task()`/
    `execute_local()` already support (P12.2) — the original field was
    `Optional[str]` only, which never covered multimodal even before this
    regression, a separate pre-existing gap fixed here at the same time
    rather than left half-fixed."""
    objective: Optional[Union[str, List[Dict[str, object]]]] = None
    allow_paid_escalation: bool = False

    @field_validator("objective")
    @classmethod
    def _bounded_objective_size(cls, value):
        if value is None:
            return value
        size = len(value.encode("utf-8")) if isinstance(value, str) else len(json.dumps(value).encode("utf-8"))
        if size > _MAX_OBJECTIVE_BYTES:
            raise ValueError(
                f"objective is {size} bytes, exceeding the {_MAX_OBJECTIVE_BYTES}-byte limit "
                "— this endpoint executes against a shared lab resource, not a bulk-upload surface"
            )
        return value

    def to_task(self) -> dict:
        task = self.model_dump(exclude={"allow_paid_escalation"})
        task["routing"] = {"allow_paid_escalation": self.allow_paid_escalation}
        return task


def setup_estate_routing_routes() -> APIRouter:
    router = APIRouter(prefix="/api/estate", tags=["estate-routing"])

    @router.post("/route")
    async def route_task(request: Request, envelope: TaskEnvelope):
        _scope_owner(request, {"estate:read", "estate:execute"})
        task = envelope.model_dump()
        return _route_call(resolve_route, task)

    @router.post("/run")
    async def run_task_route(request: Request, envelope: RunTaskEnvelope):
        """Closes the 'resolves routes but does not execute them' gap at
        the HTTP layer: routes the envelope, then actually executes it
        when the resolved route is `local` — the only executor with a
        live runtime in this environment (docs/aoteru-lab-execution-
        convergence.md finding #6)."""
        _scope_owner(request, {"estate:execute"})
        task = envelope.to_task()
        return _route_call(run_task, task)

    @router.get("/route/hosts")
    async def route_hosts(request: Request, repo: Optional[str] = None):
        _scope_owner(request, {"estate:read", "estate:execute"})
        return {"hosts": _route_call(eligible_hosts, repo)}

    @router.get("/route/alias/{alias}")
    async def route_alias(request: Request, alias: str):
        _scope_owner(request, {"estate:read", "estate:execute"})
        return _route_call(resolve_alias, alias)

    @router.get("/park/status")
    async def park_status(request: Request):
        """HTTP-facing park/status surface for the mobile UI (Workstream H
        next_action, same underlying gap Workstream B recorded) — the
        estate-wide active-lease view `agent status` already shows an
        operator, now reachable from a scoped API token too (e.g. the
        companion mobile frontend, once it wires this in) without needing
        a full repo checkout/CLI on the caller's device."""
        _scope_owner(request, {"estate:read", "estate:execute"})
        return {"active_park_leases": active_leases_summary()}

    @router.post("/park/{repo_id}/heartbeat")
    async def park_heartbeat(request: Request, repo_id: str):
        """HTTP surface for `agent heartbeat` (Workstream B next_action:
        "a park/release/heartbeat HTTP surface so the client can cover
        those scripts/agent subcommands too"). Scoped to the host this
        server process is actually running on — a remote caller (e.g. the
        laptop thin client) renews the lease this host holds, it cannot
        renew a lease on a host it isn't. `park` itself is deliberately not
        exposed here yet: acquiring a lease also needs repo-path resolution
        and a git-clean check, both currently CLI-only
        (scripts/agent's _resolve_repos/_git_is_clean) — heartbeat/release
        only need the lease row, already reused via src.park_lease_ops."""
        _scope_owner(request, {"estate:execute"})
        host_id = current_host_id()
        try:
            return {"ok": True, **heartbeat_repo(repo_id, host_id=host_id)}
        except NoActiveLease as e:
            raise HTTPException(409, str(e)) from e

    @router.post("/park/{repo_id}/release")
    async def park_release(request: Request, repo_id: str):
        """HTTP surface for `agent release` — see park_heartbeat above for
        why `park` itself isn't exposed yet."""
        _scope_owner(request, {"estate:execute"})
        host_id = current_host_id()
        try:
            return {"ok": True, **release_repo(repo_id, host_id=host_id)}
        except NoActiveLease as e:
            raise HTTPException(409, str(e)) from e

    return router

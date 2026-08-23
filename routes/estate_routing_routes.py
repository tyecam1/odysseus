"""estate_routing_routes.py — HTTP surface for the central model+host
routing authority (docs/aoteru-model-host-routing-contract.md, Phase B).

Thin wrapper over `src.estate_router` — no routing logic lives here. This
is what acceptance criterion #1 ("One Odysseus-owned routing API accepts
the canonical task envelope and returns a host+mechanism+model route")
resolves to at the HTTP layer.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.auth_helpers import require_user
from src.estate_router import RoutingConfigError, eligible_hosts, resolve_alias, resolve_route, run_task


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
    permits."""
    allow_paid_escalation: bool = False

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

    return router

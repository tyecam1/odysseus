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

from src.estate_router import RoutingConfigError, eligible_hosts, resolve_alias, resolve_route


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


def setup_estate_routing_routes() -> APIRouter:
    router = APIRouter(prefix="/api/estate", tags=["estate-routing"])

    @router.post("/route")
    async def route_task(request: Request, envelope: TaskEnvelope):
        task = envelope.model_dump()
        return _route_call(resolve_route, task)

    @router.get("/route/hosts")
    async def route_hosts(request: Request, repo: Optional[str] = None):
        return {"hosts": _route_call(eligible_hosts, repo)}

    @router.get("/route/alias/{alias}")
    async def route_alias(request: Request, alias: str):
        return _route_call(resolve_alias, alias)

    return router

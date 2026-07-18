"""Authenticated BBC Odysseus v1 API and live ship shell routes."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from core.constants import BASE_DIR, DATA_DIR
from src.app_helpers import serve_html_with_nonce
from src.bbc.auth import bbc_caller_grants, require_bbc_access
from src.bbc.runtime import BBCRuntime, build_runtime
from src.bbc.models import WorkNode, WorkStream


class CapabilityInvocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inputs: Dict[str, Any] = Field(default_factory=dict)


class NavigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: str = Field(min_length=1, max_length=160)
    destination: str = Field(min_length=1, max_length=160)
    path: list[str] = Field(default_factory=list, max_length=40)
    duration_ms: int = Field(default=0, ge=0, le=3_600_000)


class _LazyRuntime:
    """Avoid creating the BBC database merely by importing the application."""

    def __init__(self):
        self._runtime: BBCRuntime | None = None
        self._lock = threading.Lock()

    def __getattr__(self, name: str):
        if self._runtime is None:
            with self._lock:
                if self._runtime is None:
                    self._runtime = build_runtime(data_dir=DATA_DIR, app_root=BASE_DIR)
        return getattr(self._runtime, name)


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(404, str(exc).strip("'"))
    if isinstance(exc, FileNotFoundError):
        return HTTPException(503, str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(403, str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(400, str(exc))
    return HTTPException(409, str(exc))


def setup_bbc_routes(runtime: BBCRuntime | None = None) -> APIRouter:
    runtime = runtime or _LazyRuntime()
    router = APIRouter(tags=["bbc-v1"])

    @router.get("/bbc", include_in_schema=False)
    async def bbc_shell(request: Request):
        require_bbc_access(request, "read")
        return serve_html_with_nonce(request, str(Path(BASE_DIR) / "static" / "bbc" / "index.html"))

    @router.get("/api/bbc/v1/schemas")
    async def schemas(request: Request):
        require_bbc_access(request, "read")
        return await asyncio.to_thread(lambda: runtime.schemas())

    @router.get("/api/bbc/v1/health")
    async def health(request: Request):
        require_bbc_access(request, "read")
        return await asyncio.to_thread(lambda: runtime.health())

    @router.get("/api/bbc/v1/ship")
    async def ship(request: Request):
        require_bbc_access(request, "read")
        return await asyncio.to_thread(lambda: runtime.ship())

    @router.get("/api/bbc/v1/repositories")
    async def repositories(request: Request):
        require_bbc_access(request, "read")
        return {"systems": await asyncio.to_thread(lambda: runtime.adapters.systems())}

    @router.get("/api/bbc/v1/repositories/{repository_id}")
    async def repository(request: Request, repository_id: str):
        actor = require_bbc_access(request, "read")
        try:
            snapshot = await asyncio.to_thread(lambda: runtime.refresh_repository(repository_id, actor=actor))
            return snapshot.system
        except Exception as exc:
            raise _http_error(exc) from exc

    @router.get("/api/bbc/v1/repositories/{repository_id}/work-nodes")
    async def work_nodes(request: Request, repository_id: str, include_archived: bool = False):
        actor = require_bbc_access(request, "read")
        try:
            snapshot = await asyncio.to_thread(lambda: runtime.refresh_repository(repository_id, actor=actor))
        except Exception as exc:
            raise _http_error(exc) from exc
        if include_archived:
            nodes = [
                WorkNode.model_validate(item)
                for item in runtime.store.list_entities("work_node")
                if item.get("repository_id") == repository_id
            ]
            stored_streams = [
                WorkStream.model_validate(item)
                for item in runtime.store.list_entities("work_stream")
                if item.get("repository_id") == repository_id
            ]
        else:
            nodes = [
                node for node in snapshot.nodes
                if not node.archived and not node.superseded
            ]
            stored_streams = list(snapshot.streams)
        visible = {node.id for node in nodes}
        streams = [
            stream.model_copy(update={"node_ids": [node_id for node_id in stream.node_ids if node_id in visible]})
            for stream in stored_streams
            if any(node_id in visible for node_id in stream.node_ids)
        ]
        return {"system": snapshot.system, "streams": streams, "nodes": nodes}

    @router.get("/api/bbc/v1/repositories/{repository_id}/resolve")
    async def resolve_work_node(request: Request, repository_id: str, q: str = Query(min_length=1, max_length=240)):
        require_bbc_access(request, "read")
        try:
            return await asyncio.to_thread(lambda: runtime.resolve_work_node(repository_id, q))
        except Exception as exc:
            raise _http_error(exc) from exc

    @router.get("/api/bbc/v1/capabilities")
    async def capabilities(request: Request, q: str = "", limit: int = Query(default=20, ge=1, le=100)):
        require_bbc_access(request, "read")
        summaries = await asyncio.to_thread(lambda: runtime.capabilities.search(q, limit=limit))
        return {"capabilities": summaries, "detail_loaded": False}

    @router.get("/api/bbc/v1/capabilities/{capability_id}")
    async def capability_detail(request: Request, capability_id: str):
        require_bbc_access(request, "read")
        try:
            return await asyncio.to_thread(lambda: runtime.capabilities.detail(capability_id))
        except Exception as exc:
            raise _http_error(exc) from exc

    @router.post("/api/bbc/v1/capabilities/{capability_id}/invoke")
    async def invoke_capability(request: Request, capability_id: str, payload: CapabilityInvocationRequest):
        actor = require_bbc_access(request, "invoke")
        grants = bbc_caller_grants(request)
        try:
            return await asyncio.to_thread(lambda: runtime.invoke_capability(
                capability_id, payload.inputs, actor=actor, caller_grants=grants,
            ))
        except Exception as exc:
            raise _http_error(exc) from exc

    @router.get("/api/bbc/v1/navigation-transactions")
    async def navigation_transactions(request: Request):
        require_bbc_access(request, "read")
        transactions = await asyncio.to_thread(lambda: runtime.store.list_entities("navigation_transaction"))
        return {"transactions": transactions}

    @router.post("/api/bbc/v1/navigation-transactions", status_code=201)
    async def create_navigation(request: Request, payload: NavigationRequest):
        actor = require_bbc_access(request, "write")
        return await asyncio.to_thread(lambda: runtime.create_navigation(
            actor=actor, origin=payload.origin, destination=payload.destination,
            path=payload.path, duration_ms=payload.duration_ms,
        ))

    @router.get("/api/bbc/v1/audit")
    async def audit_events(
        request: Request,
        after: int = Query(default=0, ge=0),
        limit: int = Query(default=200, ge=1, le=1000),
        capability_id: str | None = None,
    ):
        require_bbc_access(request, "read")
        events = await asyncio.to_thread(
            lambda: runtime.store.list_audit(after=after, limit=limit, capability_id=capability_id)
        )
        return {"events": events}

    @router.get("/api/bbc/v1/state/events")
    async def state_events(
        request: Request,
        after: int = Query(default=0, ge=0),
        limit: int = Query(default=200, ge=1, le=1000),
    ):
        require_bbc_access(request, "read")
        events, latest_sequence = await asyncio.to_thread(lambda: (
            runtime.store.list_events(after=after, limit=limit),
            runtime.store.latest_event_sequence(),
        ))
        return {"events": events, "latest_sequence": latest_sequence}

    return router

"""Authenticated BBC Odysseus v1 API and live ship shell routes."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Path as ApiPath, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from core.constants import BASE_DIR, DATA_DIR
from src.app_helpers import serve_html_with_nonce
from src.bbc.auth import bbc_caller_grants, require_bbc_access
from src.bbc.runtime import BBCRuntime, build_runtime
from src.bbc.models import NavigationTransactionState, RoomConferenceState, WorkNode, WorkStream


TRANSACTION_ID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"


class CapabilityInvocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inputs: Dict[str, Any] = Field(default_factory=dict)


class NavigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    origin: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    destination: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    path: list[str] = Field(default_factory=list, max_length=40)
    duration_ms: int = Field(default=0, ge=0, le=3_600_000)


class NavigationTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: NavigationTransactionState
    expected_version: int = Field(ge=1)
    interruption_reason: str | None = Field(default=None, min_length=1, max_length=500)


class NavigationIntentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str | None = Field(default=None, min_length=1, max_length=200)
    repository_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")


class NavigationIntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=500)
    source: str = Field(default="typed", pattern=r"^(typed|voice)$")
    context: NavigationIntentContext = Field(default_factory=NavigationIntentContext)


class RoomConferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    objective: str = Field(min_length=1, max_length=500)
    repository_id: str | None = Field(
        default=None, pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$"
    )
    work_node_id: str | None = Field(default=None, min_length=1, max_length=200)
    trigger_navigation_transaction_id: str | None = Field(
        default=None, pattern=TRANSACTION_ID_PATTERN
    )
    max_visitors: int = Field(default=2, ge=0, le=2)


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
        require_bbc_access(request, "read")
        try:
            snapshot = await asyncio.to_thread(lambda: runtime.repository_snapshot(repository_id))
            return snapshot.system
        except Exception as exc:
            raise _http_error(exc) from exc

    @router.post("/api/bbc/v1/repositories/{repository_id}/refresh")
    async def refresh_repository(request: Request, repository_id: str):
        actor = require_bbc_access(request, "write")
        try:
            snapshot = await asyncio.to_thread(
                lambda: runtime.refresh_repository(repository_id, actor=actor)
            )
        except Exception as exc:
            raise _http_error(exc) from exc
        return {
            "system": snapshot.system,
            "streams": snapshot.streams,
            "nodes": snapshot.nodes,
        }

    @router.get("/api/bbc/v1/repositories/{repository_id}/work-nodes")
    async def work_nodes(request: Request, repository_id: str, include_archived: bool = False):
        require_bbc_access(request, "read")
        try:
            snapshot = await asyncio.to_thread(lambda: runtime.repository_snapshot(repository_id))
        except Exception as exc:
            raise _http_error(exc) from exc
        if include_archived:
            historical_nodes = [
                WorkNode.model_validate(item)
                for item in runtime.store.list_entities("work_node")
                if item.get("repository_id") == repository_id
                and (item.get("archived") or item.get("superseded"))
            ]
            current_ids = {node.id for node in snapshot.nodes}
            nodes = [
                *snapshot.nodes,
                *(node for node in historical_nodes if node.id not in current_ids),
            ]
            stream_by_id = {stream.id: stream for stream in snapshot.streams}
            for stream in [
                WorkStream.model_validate(item)
                for item in runtime.store.list_entities("work_stream")
                if item.get("repository_id") == repository_id
            ]:
                stream_by_id.setdefault(stream.id, stream)
            stored_streams = list(stream_by_id.values())
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

    @router.post("/api/bbc/v1/navigation-intents")
    async def resolve_navigation_intent(request: Request, payload: NavigationIntentRequest):
        require_bbc_access(request, "read")
        try:
            return await asyncio.to_thread(lambda: runtime.resolve_navigation_intent(
                payload.text, source=payload.source,
                context=payload.context.model_dump(exclude_none=True),
            ))
        except Exception as exc:
            raise _http_error(exc) from exc

    @router.get("/api/bbc/v1/navigation-transactions/{transaction_id}")
    async def navigation_transaction(
        request: Request,
        transaction_id: str = ApiPath(pattern=TRANSACTION_ID_PATTERN),
    ):
        require_bbc_access(request, "read")
        try:
            return await asyncio.to_thread(lambda: runtime.navigation_transaction(transaction_id))
        except Exception as exc:
            raise _http_error(exc) from exc

    @router.post("/api/bbc/v1/navigation-transactions", status_code=201)
    async def create_navigation(request: Request, payload: NavigationRequest):
        actor = require_bbc_access(request, "write")
        try:
            return await asyncio.to_thread(lambda: runtime.create_navigation(
                actor=actor, persona_id=payload.persona_id,
                origin=payload.origin, destination=payload.destination,
                path=payload.path, duration_ms=payload.duration_ms,
            ))
        except Exception as exc:
            raise _http_error(exc) from exc

    @router.patch("/api/bbc/v1/navigation-transactions/{transaction_id}")
    async def transition_navigation(
        request: Request,
        payload: NavigationTransitionRequest,
        transaction_id: str = ApiPath(pattern=TRANSACTION_ID_PATTERN),
    ):
        actor = require_bbc_access(request, "write")
        try:
            return await asyncio.to_thread(lambda: runtime.transition_navigation(
                transaction_id, payload.state, actor=actor,
                expected_version=payload.expected_version,
                interruption_reason=payload.interruption_reason,
            ))
        except Exception as exc:
            raise _http_error(exc) from exc

    @router.get("/api/bbc/v1/persona-locations")
    async def persona_locations(request: Request):
        require_bbc_access(request, "read")
        locations = await asyncio.to_thread(runtime.persona_locations)
        return {"locations": locations}

    @router.get("/api/bbc/v1/persona-locations/{persona_id}")
    async def persona_location(
        request: Request,
        persona_id: str = ApiPath(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$"),
    ):
        require_bbc_access(request, "read")
        try:
            return await asyncio.to_thread(lambda: runtime.persona_location(persona_id))
        except Exception as exc:
            raise _http_error(exc) from exc

    @router.get("/api/bbc/v1/room-conferences")
    async def room_conferences(
        request: Request,
        room_id: str | None = Query(default=None, pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$"),
        state: RoomConferenceState | None = None,
        limit: int = Query(default=20, ge=1, le=100),
    ):
        require_bbc_access(request, "read")
        conferences = await asyncio.to_thread(
            lambda: runtime.room_conferences(room_id=room_id, state=state, limit=limit)
        )
        return {"conferences": conferences}

    @router.get("/api/bbc/v1/room-conferences/{conference_id}")
    async def room_conference(
        request: Request,
        conference_id: str = ApiPath(pattern=TRANSACTION_ID_PATTERN),
    ):
        require_bbc_access(request, "read")
        try:
            return await asyncio.to_thread(lambda: runtime.room_conference(conference_id))
        except Exception as exc:
            raise _http_error(exc) from exc

    @router.post("/api/bbc/v1/room-conferences", status_code=201)
    async def create_room_conference(request: Request, payload: RoomConferenceRequest):
        actor = require_bbc_access(request, "write")
        require_bbc_access(request, "invoke")
        grants = bbc_caller_grants(request)
        try:
            return await asyncio.to_thread(lambda: runtime.run_room_conference(
                actor=actor,
                room_id=payload.room_id,
                objective=payload.objective,
                repository_id=payload.repository_id,
                work_node_id=payload.work_node_id,
                trigger_navigation_transaction_id=payload.trigger_navigation_transaction_id,
                max_visitors=payload.max_visitors,
                caller_grants=grants,
            ))
        except Exception as exc:
            raise _http_error(exc) from exc

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

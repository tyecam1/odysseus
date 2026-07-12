"""Misumi operator-conference and heartbeat runtime routes.

Mount from app.py with:

    from routes.misumi_operator_runtime_routes import setup_misumi_operator_runtime_routes
    app.include_router(setup_misumi_operator_runtime_routes())

The route module is deliberately separated from routes/misumi_routes.py so the
large compatibility surface is not destructively rewritten by connector-only
changes.
"""

from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.middleware import require_admin
from src.misumi_operator_runtime import HeartbeatRuntime, OperatorConferenceStore


class OperatorConferenceCreateRequest(BaseModel):
    requesting_persona: str = "aoteru"
    reason: str
    context_summary: str = ""
    urgency: str = "normal"
    timeout_seconds: int = Field(default=600, ge=30, le=86400)
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None


class OperatorConferenceResponseRequest(BaseModel):
    response: str
    responder: str = "operator"
    response_payload: Dict[str, object] = Field(default_factory=dict)


class OperatorConferenceCancelRequest(BaseModel):
    reason: str = "cancelled"


class HeartbeatRunRequest(BaseModel):
    loop_id: str
    input_summary: str = ""


def _require_api_scope(request: Request, required: str) -> None:
    """Mirror Misumi's API-token scope guard without importing private closures."""
    if not getattr(request.state, "api_token", False):
        return
    scopes = set(getattr(request.state, "api_token_scopes", []) or [])
    accepted = {"*", "admin", "misumi", required}
    if required == "misumi:read":
        accepted.add("chat")
    if not scopes.intersection(accepted):
        raise HTTPException(403, f"API token requires {required} scope")


def setup_misumi_operator_runtime_routes(root=None) -> APIRouter:
    router = APIRouter(prefix="/misumi", tags=["misumi-runtime"])
    conferences = OperatorConferenceStore(root)
    heartbeat = HeartbeatRuntime(root)

    def safe_call(operation, *args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except KeyError as exc:
            raise HTTPException(404, "Operator runtime record not found") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(503, "Misumi operator runtime store is unavailable") from exc

    @router.get("/operator-conferences")
    async def list_operator_conferences(request: Request, status: Optional[str] = None):
        _require_api_scope(request, "misumi:read")
        rows, corrupt = safe_call(conferences.list, status=status)
        return {"events": rows, "corrupt_lines": corrupt, "writes_allowed": False}

    @router.post("/operator-conferences")
    async def create_operator_conference(request: Request, body: OperatorConferenceCreateRequest):
        _require_api_scope(request, "misumi:execute")
        return safe_call(
            conferences.create,
            requesting_persona=body.requesting_persona,
            reason=body.reason,
            context_summary=body.context_summary,
            urgency=body.urgency,
            timeout_seconds=body.timeout_seconds,
            session_id=body.session_id,
            correlation_id=body.correlation_id,
        )

    @router.get("/operator-conferences/{event_id}")
    async def get_operator_conference(request: Request, event_id: str):
        _require_api_scope(request, "misumi:read")
        return safe_call(conferences.get, event_id)

    @router.post("/operator-conferences/{event_id}/respond")
    async def respond_operator_conference(request: Request, event_id: str, body: OperatorConferenceResponseRequest):
        require_admin(request)
        return safe_call(
            conferences.respond,
            event_id,
            response=body.response,
            responder=body.responder,
            payload=body.response_payload,
        )

    @router.post("/operator-conferences/{event_id}/cancel")
    async def cancel_operator_conference(request: Request, event_id: str, body: OperatorConferenceCancelRequest):
        require_admin(request)
        return safe_call(conferences.cancel, event_id, reason=body.reason)

    @router.get("/operator-conferences/metrics/summary")
    async def operator_conference_metrics(request: Request):
        _require_api_scope(request, "misumi:read")
        return safe_call(conferences.metrics)

    @router.get("/heartbeat/status")
    async def heartbeat_status(request: Request):
        _require_api_scope(request, "misumi:read")
        return heartbeat.status()

    @router.post("/heartbeat/run-once")
    async def heartbeat_run_once(request: Request, body: HeartbeatRunRequest):
        require_admin(request)
        return safe_call(heartbeat.run_once, body.loop_id, input_summary=body.input_summary)

    @router.get("/heartbeat/proposals")
    async def heartbeat_proposals(request: Request, limit: int = 20):
        _require_api_scope(request, "misumi:read")
        return {"proposals": heartbeat.proposals(limit), "writes_allowed": False}

    return router

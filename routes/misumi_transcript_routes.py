"""Misumi durable transcript routes.

Mount from app.py with:

    from routes.misumi_transcript_routes import setup_misumi_transcript_routes
    app.include_router(setup_misumi_transcript_routes(stt_service=stt_service))

Sequence these routes make true for microphone speech:

    capture -> transcribe -> DURABLY PERSIST -> acknowledge -> wake/intent -> optional response

A transcript is acknowledged (``persisted: true``) only after the database
commit. A non-wake utterance is still stored; the wake decision is attached
afterwards (PATCH .../wake) and never decides retention. Raw audio is held in
memory for one request and never stored. Household audio may only be processed
on a registered ``home`` host (``data_locality: home-lan``): any other host
refuses the audio endpoint before reading the upload, and there is no fallback.

Disabled by default on every deployment (``ODYSSEUS_MISUMI_TRANSCRIPT_ENABLED``)
and additionally gated per owner by the transcript-archive policy.
"""

from __future__ import annotations

import logging
import os
import socket
import time
from typing import Callable, Optional, Tuple

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from src import misumi_transcripts as svc
from src.upload_limits import STT_MAX_AUDIO_BYTES, read_upload_limited

logger = logging.getLogger(__name__)

DOMAIN = svc.DEFAULT_DOMAIN


class TranscriptEventRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=svc.MAX_EVENT_ID_CHARS)
    text: str = Field(min_length=1, max_length=svc.MAX_TEXT_CHARS)
    capture_mode: str = "ambient"
    source: str = "text-event"
    capture_started_at: Optional[str] = None
    capture_ended_at: Optional[str] = None
    persona: Optional[str] = Field(default=None, max_length=48)


class WakeRequest(BaseModel):
    matched: bool
    intent: Optional[str] = Field(default=None, max_length=64)
    session_id: Optional[str] = Field(default=None, max_length=120)
    response_request_id: Optional[str] = Field(default=None, max_length=120)


class PolicyRequest(BaseModel):
    transcript_archive: Optional[bool] = None
    transcript_retention_days: Optional[int] = Field(default=None, ge=1, le=svc.RETENTION_MAX_DAYS)


class ImportRequest(BaseModel):
    lines: list[str] = Field(max_length=5000)
    box_id: str = Field(default="interface-box", max_length=48)


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


def _owner(request: Request) -> Optional[str]:
    if getattr(request.state, "api_token", False):
        return getattr(request.state, "api_token_owner", None)
    return getattr(request.state, "current_user", None)


def _runtime_enabled() -> bool:
    return os.getenv("ODYSSEUS_MISUMI_TRANSCRIPT_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _host_role(host_id: Optional[str]) -> Optional[str]:
    if not host_id:
        return None
    try:
        from src.estate_router import _load_yaml

        for host in _load_yaml("estate").get("hosts", []):
            if host.get("id") == host_id:
                return host.get("role")
    except Exception:  # a registry that cannot be read must not widen where audio may go
        logger.warning("estate registry unreadable while resolving host role", exc_info=True)
    return None


def default_audio_locality() -> Tuple[bool, Optional[str], str]:
    """``data_locality: home-lan``: household audio may execute only on a registered
    home host. ``ODYSSEUS_TRANSCRIPT_AUDIO_HOSTS`` (comma-separated host ids, or ``*``)
    is an explicit operator override for development and tests, never a default.
    Returns (allowed, host_id, reason)."""
    try:
        from src.estate_router import current_host_id

        host_id = current_host_id()
    except Exception:
        host_id = None
    allowed = {item.strip() for item in os.getenv("ODYSSEUS_TRANSCRIPT_AUDIO_HOSTS", "").split(",") if item.strip()}
    if "*" in allowed or (host_id and host_id in allowed):
        return True, host_id or socket.gethostname(), "explicit operator override"
    role = _host_role(host_id)
    if role == "home":
        return True, host_id, "registered home host"
    return False, host_id, f"host role {role or 'unregistered'} is not 'home' (data_locality: home-lan)"


def setup_misumi_transcript_routes(
    *,
    stt_service=None,
    session_factory: Optional[Callable] = None,
    audio_locality: Optional[Callable[[], Tuple[bool, Optional[str], str]]] = None,
) -> APIRouter:
    router = APIRouter(prefix="/misumi/transcript", tags=["misumi-transcript"])

    def new_session():
        factory = session_factory
        if factory is None:
            from core.database import SessionLocal

            factory = SessionLocal
        return factory()

    def locality():
        return (audio_locality or default_audio_locality)()

    def require_enabled() -> None:
        if not _runtime_enabled():
            raise HTTPException(503, {"state": "runtime_disabled",
                                      "detail": "Misumi transcript runtime is disabled on this host"})

    def with_db(operation):
        db = new_session()
        try:
            return operation(db)
        finally:
            db.close()

    def refusal(exc: svc.TranscriptError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"persisted": False, "state": exc.code, "detail": str(exc)},
        )

    def persisted_body(result: svc.IngestResult) -> dict:
        """Serialise INSIDE the session: after commit the row's attributes are
        expired and a closed session cannot reload them."""
        return {"persisted": True, "state": "persisted", "deduplicated": result.deduplicated,
                **svc.event_dict(result.event)}

    @router.post("/events")
    def post_event(request: Request, body: TranscriptEventRequest):
        """Text-only ingest (the box's forwarded windows, imports, tests). The audio
        endpoint is the only one that touches STT."""
        _require_api_scope(request, "misumi:execute")
        require_enabled()
        owner = _owner(request)
        started = svc.parse_timestamp(body.capture_started_at)
        ended = svc.parse_timestamp(body.capture_ended_at)

        def run(db):
            return persisted_body(svc.ingest_event(
                db, owner=owner, domain=DOMAIN, event_id=body.event_id, text=body.text,
                capture_mode=body.capture_mode, source=body.source,
                capture_started_at=started, capture_ended_at=ended, persona=body.persona,
            ))

        try:
            return with_db(run)
        except svc.TranscriptError as exc:
            return refusal(exc)
        except Exception:
            logger.exception("transcript commit failed")
            raise HTTPException(503, {"persisted": False, "state": "persist_failed"})

    @router.post("/audio")
    async def post_audio(
        request: Request,
        file: UploadFile = File(...),
        event_id: str = Form(...),
        capture_mode: str = Form("ambient"),
        capture_started_at: Optional[str] = Form(None),
        capture_ended_at: Optional[str] = Form(None),
        persona: Optional[str] = Form(None),
    ):
        """Atomic audio -> durable transcript. Success is returned only after commit;
        a retry of the same event_id returns the stored row and never re-runs STT."""
        _require_api_scope(request, "misumi:execute")
        require_enabled()
        owner = _owner(request)

        allowed, host_id, reason = locality()
        if not allowed:
            raise HTTPException(403, {"persisted": False, "state": "audio_locality_refused",
                                      "detail": reason, "host_id": host_id})

        def reconcile(db):
            existing = svc.lookup_existing(db, owner, DOMAIN, event_id)
            return persisted_body(svc.IngestResult(existing, True)) if existing is not None else None

        already = await run_in_threadpool(lambda: with_db(reconcile))
        if already is not None:
            return already

        if stt_service is None or not stt_service.available:
            raise HTTPException(503, {"persisted": False, "state": "stt_unavailable"})

        audio = await read_upload_limited(file, STT_MAX_AUDIO_BYTES, "Audio file")
        if not audio:
            raise HTTPException(400, {"persisted": False, "state": "empty_audio"})

        started_clock = time.monotonic()
        try:
            text = await run_in_threadpool(stt_service.transcribe, audio)
        except Exception:
            logger.exception("transcription raised")
            raise HTTPException(502, {"persisted": False, "state": "stt_failed"})
        latency_ms = int((time.monotonic() - started_clock) * 1000)
        if text is None:
            raise HTTPException(502, {"persisted": False, "state": "stt_failed"})
        if not str(text).strip():
            return JSONResponse(status_code=200, content={"persisted": False, "state": "no_speech",
                                                          "event_id": event_id})

        settings = {}
        try:
            settings = stt_service._load_settings()  # provider/model attribution only
        except Exception:
            settings = {}
        provider = settings.get("stt_provider")
        model = settings.get("stt_model") or settings.get("whisper_model_size")

        started = svc.parse_timestamp(capture_started_at)
        ended = svc.parse_timestamp(capture_ended_at)

        def run(db):
            return persisted_body(svc.ingest_event(
                db, owner=owner, domain=DOMAIN, event_id=event_id, text=str(text),
                capture_mode=capture_mode, source="audio-upload",
                capture_started_at=started, capture_ended_at=ended, persona=persona,
                stt_provider=provider, stt_model=model, stt_host=host_id, stt_latency_ms=latency_ms,
            ))

        try:
            return await run_in_threadpool(lambda: with_db(run))
        except svc.TranscriptError as exc:
            return refusal(exc)
        except Exception:
            logger.exception("transcript commit failed")
            raise HTTPException(503, {"persisted": False, "state": "persist_failed"})

    @router.patch("/{event_id}/wake")
    def patch_wake(request: Request, event_id: str, body: WakeRequest):
        _require_api_scope(request, "misumi:execute")
        require_enabled()
        owner = _owner(request)

        def run(db):
            event = svc.attach_wake(
                db, owner, DOMAIN, event_id, matched=body.matched, intent=body.intent,
                session_id=body.session_id, response_request_id=body.response_request_id,
            )
            return svc.event_dict(event)

        try:
            return with_db(run)
        except svc.TranscriptError as exc:
            return refusal(exc)

    @router.get("")
    def list_events(
        request: Request,
        since: Optional[str] = None,
        until: Optional[str] = None,
        after_seq: Optional[int] = Query(default=None, ge=0),
        before_seq: Optional[int] = Query(default=None, ge=0),
        limit: int = Query(default=svc.QUERY_DEFAULT_LIMIT, ge=1, le=svc.QUERY_MAX_LIMIT),
        order: str = Query(default="desc", pattern="^(asc|desc)$"),
    ):
        _require_api_scope(request, "misumi:read")
        require_enabled()
        owner = _owner(request)
        return with_db(lambda db: svc.query_events(
            db, owner, DOMAIN, since=svc.parse_timestamp(since), until=svc.parse_timestamp(until),
            after_seq=after_seq, before_seq=before_seq, limit=limit, newest_first=(order == "desc"),
        ))

    @router.get("/export")
    def export(
        request: Request,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = Query(default=svc.EXPORT_MAX_LIMIT, ge=1, le=svc.EXPORT_MAX_LIMIT),
        format: str = Query(default="jsonl", pattern="^(jsonl|md)$"),
    ):
        _require_api_scope(request, "misumi:read")
        require_enabled()
        owner = _owner(request)
        body = with_db(lambda db: svc.export_events(
            db, owner, DOMAIN, since=svc.parse_timestamp(since), until=svc.parse_timestamp(until),
            limit=limit, fmt=format,
        ))
        media = "text/markdown" if format == "md" else "application/x-ndjson"
        return PlainTextResponse(body, media_type=media)

    @router.get("/policy")
    def get_policy(request: Request):
        _require_api_scope(request, "misumi:read")
        require_enabled()
        owner = _owner(request)
        return with_db(lambda db: svc.get_policy(db, owner))

    @router.put("/policy")
    def put_policy(request: Request, body: PolicyRequest):
        _require_api_scope(request, "misumi:execute")
        require_enabled()
        owner = _owner(request)
        return with_db(lambda db: svc.set_policy(
            db, owner, transcript_archive=body.transcript_archive,
            transcript_retention_days=body.transcript_retention_days))

    @router.post("/import")
    def import_box(request: Request, body: ImportRequest):
        """Idempotent import of completed interface-box day files (compat Stage A)."""
        _require_api_scope(request, "misumi:execute")
        require_enabled()
        owner = _owner(request)
        return with_db(lambda db: svc.import_box_lines(
            db, owner=owner, lines=body.lines, domain=DOMAIN, box_id=body.box_id))

    @router.get("/{event_id}")
    def get_event(request: Request, event_id: str):
        _require_api_scope(request, "misumi:read")
        require_enabled()
        owner = _owner(request)

        def run(db):
            event = svc.find_event(db, owner, DOMAIN, event_id)
            if event is None:
                raise HTTPException(404, {"state": "event_not_found"})
            return svc.event_dict(event)

        return with_db(run)

    return router

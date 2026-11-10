"""Operator controls for durable, explicitly activated lazy usage runs."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, StrictInt

from core.database import LazyUsageRun, get_db_session
from routes.estate_routing_routes import _scope_owner
from src import lazy_usage_runtime as runtime


class Activation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo_scope: list[str] | None = None
    budget_overrides: dict[str, StrictInt] | None = None


class RunControl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str


def setup_lazy_usage_routes():
    router = APIRouter(prefix="/api/lazy-usage", tags=["lazy-usage"])

    @router.post("/start")
    def start(request: Request, activation: Activation):
        owner = _scope_owner(request, {"estate:execute"})
        try:
            with get_db_session() as db:
                return runtime.activate_run(db, owner, activation.repo_scope, activation.budget_overrides)
        except runtime.RunError as exc:
            raise HTTPException(exc.status_code, exc.detail) from exc

    @router.get("/status")
    def status(request: Request, run_id: str | None = None):
        owner = _scope_owner(request, {"estate:read", "estate:execute"})
        with get_db_session() as db:
            if run_id:
                try:
                    return runtime.run_dict(runtime._load(db, run_id, owner))
                except runtime.RunError as exc:
                    raise HTTPException(exc.status_code, exc.detail) from exc
            run = db.query(LazyUsageRun).filter_by(created_by=owner).order_by(LazyUsageRun.created_at.desc()).first()
            return runtime.run_dict(run) if run else {"state": None, "counters": {}, "budgets": {},
                                                     "checkpoint": {}, "owed_reviews": []}

    @router.get("/history")
    def history(request: Request, limit: int = 20):
        owner = _scope_owner(request, {"estate:read", "estate:execute"})
        with get_db_session() as db:
            rows = db.query(LazyUsageRun).filter_by(created_by=owner).order_by(
                LazyUsageRun.created_at.desc()).limit(max(1, min(limit, 100))).all()
            return {"runs": [runtime.run_dict(run) for run in rows]}

    def control(request, payload, function):
        owner = _scope_owner(request, {"estate:execute"})
        try:
            with get_db_session() as db:
                return function(db, payload.run_id, owner)
        except runtime.RunError as exc:
            raise HTTPException(exc.status_code, exc.detail) from exc

    @router.post("/stop")
    def stop(request: Request, payload: RunControl):
        return control(request, payload, runtime.stop_run)

    @router.post("/pause")
    def pause(request: Request, payload: RunControl):
        return control(request, payload, runtime.pause_run)

    @router.post("/resume")
    def resume(request: Request, payload: RunControl):
        return control(request, payload, runtime.resume_run)

    return router

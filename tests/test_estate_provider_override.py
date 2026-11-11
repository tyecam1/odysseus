"""Admin evidence overrides and S6 finalization HTTP contracts."""
import json
import os
from types import SimpleNamespace
from datetime import timedelta

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()
import core.database as cdb
from src import estate_router
from routes.estate_routing_routes import setup_estate_routing_routes
from routes.api_token_routes import _normalize_scopes


@pytest.fixture
def api(monkeypatch):
    factory, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", factory)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    app = FastAPI()
    app.state.auth_manager = SimpleNamespace(is_configured=True, is_admin=lambda owner: owner == "operator")

    @app.middleware("http")
    async def identity(request: Request, call_next):
        request.state.api_token = True
        request.state.current_user = "api"
        request.state.api_token_owner = request.headers.get("x-owner", "operator")
        request.state.api_token_id = "test-token-id"
        request.state.api_token_scopes = request.headers.get("x-scopes", "estate:admin").split(",")
        return await call_next(request)

    app.include_router(setup_estate_routing_routes())
    with TestClient(app) as client:
        yield client, factory
    engine.dispose()
    os.unlink(tmpfile.name)


def exhaust(factory, provider):
    with factory() as db:
        db.add(cdb.RoutingDecision(id="exhausted-" + provider, task_class="provider_outcome", executor=provider,
            host_id="lab", status="failed", escalation_reason=json.dumps({"provider_health": {
                "state": "quota_exhausted", "reason": "provider usage limit; host wall-clock reset",
                "retry_after": (cdb.utcnow_naive() + timedelta(days=1)).isoformat() + "+00:00",
                "retry_after_assumed": False}})))
        db.commit()


def test_override_reopens_only_named_provider_and_audits_identity(api):
    client, factory = api
    for provider in ("codex", "glm"):
        exhaust(factory, provider)
        assert not estate_router.provider_allows_dispatch(provider)["allowed"]
    result = client.post("/api/estate/provider-health/codex/override", json={"reason": "Observed live lab capacity"})
    assert result.status_code == 200
    assert result.json()["state"] == "ok"
    assert result.json()["retry_after_assumed"] is False
    assert estate_router.provider_allows_dispatch("codex")["allowed"]
    assert not estate_router.provider_allows_dispatch("glm")["allowed"]
    with factory() as db:
        rows = db.query(cdb.RoutingDecision).all()
        assert len(rows) == 3  # exhausted evidence is retained
        row = db.get(cdb.RoutingDecision, result.json()["decision_id"])
        audit = json.loads(row.escalation_reason)
        assert audit["requested_by"] == "operator"
        assert audit["api_token_id"] == "test-token-id"
        assert audit["provider_health"]["reason"] == "operator-authorized override: Observed live lab capacity"
    assert client.get("/api/estate/provider-health/codex", headers={"x-scopes": "estate:read"}).json()["allowed"]
    assert _normalize_scopes("estate:admin") == ["estate:admin"]


@pytest.mark.parametrize("scopes,owner", [("estate:execute", "operator"), ("estate:read", "operator"),
                                          ("estate:admin", "ordinary"), ("estate:admin", ""), ("", "operator")])
def test_override_requires_admin_scope_and_current_admin_owner(api, scopes, owner):
    client, factory = api
    response = client.post("/api/estate/provider-health/codex/override", json={"reason": "observed"},
                           headers={"x-scopes": scopes, "x-owner": owner})
    assert response.status_code == 403
    with factory() as db:
        assert db.query(cdb.RoutingDecision).count() == 0


@pytest.mark.parametrize("body", [{}, {"reason": ""}, {"reason": "  "}, {"reason": "x" * 2001}])
def test_override_requires_bounded_reason(api, body):
    client, factory = api
    assert client.post("/api/estate/provider-health/codex/override", json=body).status_code == 422
    with factory() as db:
        assert db.query(cdb.RoutingDecision).count() == 0


def test_unknown_provider_and_rate_limit(api):
    client, factory = api
    assert client.post("/api/estate/provider-health/made-up/override", json={"reason": "observed"}).status_code == 404
    assert client.get("/api/estate/provider-health/made-up").status_code == 404
    for _ in range(5):
        assert client.post("/api/estate/provider-health/codex/override", json={"reason": "observed"}).status_code == 200
    assert client.post("/api/estate/provider-health/codex/override", json={"reason": "observed"}).status_code == 429
    with factory() as db:
        assert db.query(cdb.RoutingDecision).count() == 5


def test_finalize_derives_authority_from_row_and_uses_control_plane(api, monkeypatch):
    client, factory = api
    with factory() as db:
        db.add(cdb.EstateExecution(id="E1", objective="bounded", repo_id="odysseus", host_id="lab",
                                  executor="codex-write", provider="codex",
                                  lifecycle_state="succeeded", worktree_resolution="unresolved"))
        db.commit()
    calls = []
    monkeypatch.setattr(estate_router, "finalize_execution", lambda **kw: (calls.append(kw), {"finalized": True})[1])
    response = client.post("/api/estate/run/E1/finalize", json={"commit_message": "Exact\nmessage"},
                           headers={"x-scopes": "estate:execute"})
    assert response.status_code == 200
    assert calls == [{"execution_id": "E1", "repo_id": "odysseus", "host_id": "lab", "commit_message": "Exact\nmessage"}]
    assert client.post("/api/estate/run/E1/finalize", json={}, headers={"x-scopes": "estate:read"}).status_code == 403
    assert client.post("/api/estate/run/missing/finalize", json={}, headers={"x-scopes": "estate:execute"}).status_code == 404
    monkeypatch.setattr(estate_router, "finalize_execution", lambda **kw: {"finalized": False, "reason": "lease drift"})
    assert client.post("/api/estate/run/E1/finalize", json={}, headers={"x-scopes": "estate:execute"}).status_code == 409


@pytest.mark.parametrize("owner,auth_enabled,expected", [("operator", "true", 200),
    ("ordinary", "true", 403), (None, "false", 403)])
def test_override_uses_existing_cookie_admin_gate_and_requires_audit_identity(api, monkeypatch, owner, auth_enabled, expected):
    _, factory = api
    monkeypatch.setenv("AUTH_ENABLED", auth_enabled)
    app = FastAPI()
    app.state.auth_manager = SimpleNamespace(is_configured=True, is_admin=lambda user: user == "operator")

    @app.middleware("http")
    async def cookie_identity(request: Request, call_next):
        request.state.current_user = owner
        request.state.api_token = False
        return await call_next(request)

    app.include_router(setup_estate_routing_routes())
    with TestClient(app) as client:
        response = client.post("/api/estate/provider-health/codex/override", json={"reason": "Observed capacity"})
    assert response.status_code == expected
    with factory() as db:
        assert db.query(cdb.RoutingDecision).count() == (1 if expected == 200 else 0)

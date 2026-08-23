"""Tests for routes/estate_routing_routes.py's auth/scope gate and envelope
handling — previously untested at the HTTP layer (only src/estate_router.py
itself had coverage; the route wrapper did not).

Regression coverage for Workstream B/C
(docs/aoteru-long-horizon-autonomous-convergence.agent-task.md): a laptop
thin client authenticates with a bearer API token, so /api/estate/* must be
properly scope-gated (an unscoped token, or one scoped for something else
entirely, must not be able to drive estate routing/execution), and
`allow_paid_escalation` must actually reach `run_task()`'s existing opt-in
gate rather than being silently dropped by the envelope.
"""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes.estate_routing_routes import RunTaskEnvelope, TaskEnvelope, _scope_owner, setup_estate_routing_routes


def _cookie_request(*, current_user="operator"):
    return SimpleNamespace(
        state=SimpleNamespace(current_user=current_user, api_token=False),
    )


def _api_token_request(*, scopes=None, owner="operator"):
    return SimpleNamespace(
        state=SimpleNamespace(
            current_user="api",
            api_token=True,
            api_token_scopes=scopes or [],
            api_token_owner=owner,
        ),
    )


class TestScopeGate:
    def test_cookie_session_always_allowed(self):
        req = _cookie_request()
        assert _scope_owner(req, {"estate:execute"}) == "operator"

    def test_api_token_with_required_scope_allowed(self):
        req = _api_token_request(scopes=["estate:execute"])
        assert _scope_owner(req, {"estate:execute"}) == "operator"

    def test_api_token_with_read_only_scope_rejected_for_execute(self):
        req = _api_token_request(scopes=["estate:read"])
        with pytest.raises(HTTPException) as exc:
            _scope_owner(req, {"estate:execute"})
        assert exc.value.status_code == 403

    def test_api_token_with_unrelated_scope_rejected(self):
        """A token minted for e.g. chat/companion pairing must not silently
        also be able to drive estate execution — the exact gap this scope
        gate closes."""
        req = _api_token_request(scopes=["chat"])
        with pytest.raises(HTTPException) as exc:
            _scope_owner(req, {"estate:read", "estate:execute"})
        assert exc.value.status_code == 403

    def test_api_token_with_no_scopes_rejected(self):
        req = _api_token_request(scopes=[])
        with pytest.raises(HTTPException):
            _scope_owner(req, {"estate:read", "estate:execute"})

    def test_read_scope_sufficient_for_read_endpoints(self):
        req = _api_token_request(scopes=["estate:read"])
        assert _scope_owner(req, {"estate:read", "estate:execute"}) == "operator"


class TestRunTaskEnvelope:
    def test_objective_reaches_task_dict(self):
        """Regression test: a prior edit to add allow_paid_escalation
        accidentally dropped the `objective` field from RunTaskEnvelope
        entirely. Pydantic v2 silently ignores an unknown constructor
        kwarg (no error raised), so the field's *absence* was invisible
        at construction time — every HTTP /api/estate/run caller's
        objective was dropped before reaching run_task(), which then
        correctly reported 'no objective provided to execute' for every
        single call. Found live this session (Workstream J validation),
        fixed, and this assertion is what should have caught it the first
        time: check the objective key is actually present with the right
        value, not just that routing/allow_paid_escalation looks right."""
        envelope = RunTaskEnvelope(task_class="code", objective="do the thing")
        task = envelope.to_task()
        assert task["objective"] == "do the thing"

    def test_multimodal_objective_reaches_task_dict(self):
        content = [{"type": "text", "text": "describe this"},
                   {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]
        envelope = RunTaskEnvelope(task_class="code", objective=content)
        task = envelope.to_task()
        assert task["objective"] == content

    def test_allow_paid_escalation_defaults_false(self):
        envelope = RunTaskEnvelope(task_class="code", objective="do the thing")
        task = envelope.to_task()
        assert task["routing"] == {"allow_paid_escalation": False}

    def test_allow_paid_escalation_true_reaches_task_dict(self):
        """The exact field src.estate_router.run_task() reads via
        task.get('routing', {}).get('allow_paid_escalation') — previously
        unreachable from any HTTP caller since RunTaskEnvelope had no such
        field at all."""
        envelope = RunTaskEnvelope(
            task_class="code", objective="do the thing", allow_paid_escalation=True,
        )
        task = envelope.to_task()
        assert task["routing"] == {"allow_paid_escalation": True}
        assert "allow_paid_escalation" not in task, (
            "the top-level pydantic field must not leak into the task dict "
            "alongside the nested routing.allow_paid_escalation"
        )

    def test_task_envelope_still_has_no_objective_field(self):
        """Plain TaskEnvelope (route-only, no execution) is unaffected by
        the RunTaskEnvelope subclass addition."""
        envelope = TaskEnvelope(task_class="code")
        assert not hasattr(envelope, "objective")


class TestRunRouteEndToEnd:
    """Real HTTP round trip through the FastAPI route, not just the
    Pydantic model in isolation — the objective-field regression above
    would NOT have been caught by a model-only test that never serialised
    a real HTTP request body through the actual route handler."""

    def _client(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "false")
        app = FastAPI()
        app.include_router(setup_estate_routing_routes())
        return TestClient(app)

    def test_post_run_objective_reaches_run_task(self, monkeypatch):
        client = self._client(monkeypatch)
        captured = {}

        def fake_run_task(task):
            captured.update(task)
            return {"ok": True, "executed": False}

        import routes.estate_routing_routes as mod
        monkeypatch.setattr(mod, "run_task", fake_run_task)

        response = client.post("/api/estate/run", json={
            "task_class": "code", "objective": "a real HTTP request body",
        })

        assert response.status_code == 200
        assert captured.get("objective") == "a real HTTP request body", (
            "the exact regression: objective must survive a real JSON "
            "request body all the way into the dict run_task() receives"
        )

    def test_post_run_multimodal_objective_reaches_run_task(self, monkeypatch):
        client = self._client(monkeypatch)
        captured = {}

        def fake_run_task(task):
            captured.update(task)
            return {"ok": True, "executed": False}

        import routes.estate_routing_routes as mod
        monkeypatch.setattr(mod, "run_task", fake_run_task)

        content = [{"type": "text", "text": "describe"},
                   {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]
        response = client.post("/api/estate/run", json={"task_class": "code", "objective": content})

        assert response.status_code == 200
        assert captured.get("objective") == content

    def test_oversized_objective_rejected_before_reaching_run_task(self, monkeypatch):
        """This endpoint executes against a shared lab GPU — nothing
        downstream (select_bounded_context only bounds the requested
        context window, not the payload actually sent) previously capped
        objective size, so a 20MB+ objective would be fully constructed
        and shipped to Ollama before any model-side limit kicked in."""
        client = self._client(monkeypatch)
        called = {"n": 0}

        import routes.estate_routing_routes as mod
        monkeypatch.setattr(mod, "run_task", lambda task: called.__setitem__("n", called["n"] + 1) or {"ok": True})

        huge = "x" * 20_000_000
        response = client.post("/api/estate/run", json={"task_class": "code", "objective": huge})

        assert response.status_code == 422
        assert called["n"] == 0, "run_task must never be reached for an oversized objective"

    def test_reasonably_sized_objective_still_accepted(self, monkeypatch):
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod
        monkeypatch.setattr(mod, "run_task", lambda task: {"ok": True})

        response = client.post("/api/estate/run", json={"task_class": "code", "objective": "a" * 10_000})
        assert response.status_code == 200

    def test_malformed_objective_type_rejected_cleanly(self, monkeypatch):
        client = self._client(monkeypatch)
        response = client.post("/api/estate/run", json={"task_class": "code", "objective": 12345})
        assert response.status_code == 422


class TestParkHeartbeatReleaseRoutes:
    """HTTP surface for `agent heartbeat`/`agent release` (Workstream B
    next_action: "a park/release/heartbeat HTTP surface so the client can
    cover those scripts/agent subcommands too"). Both routes delegate to
    src.park_lease_ops (the same authority scripts/agent's CLI now also
    uses) and resolve the acting host_id via src.estate_router.
    current_host_id() rather than trusting a caller-supplied host."""

    def _client(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "false")
        app = FastAPI()
        app.include_router(setup_estate_routing_routes())
        return TestClient(app)

    def test_heartbeat_renews_lease_on_this_host(self, monkeypatch):
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod

        monkeypatch.setattr(mod, "current_host_id", lambda: "test-lab")
        captured = {}

        def fake_heartbeat_repo(repo_id, host_id=None):
            captured["repo_id"] = repo_id
            captured["host_id"] = host_id
            return {"lease_id": "abc", "repo_id": repo_id, "host_id": host_id, "heartbeat_at": "2026-01-01T00:00:00"}
        monkeypatch.setattr(mod, "heartbeat_repo", fake_heartbeat_repo)

        response = client.post("/api/estate/park/my-repo/heartbeat")

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["lease_id"] == "abc"
        assert captured == {"repo_id": "my-repo", "host_id": "test-lab"}

    def test_heartbeat_no_active_lease_returns_409(self, monkeypatch):
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod

        monkeypatch.setattr(mod, "current_host_id", lambda: "test-lab")

        def boom(repo_id, host_id=None):
            raise mod.NoActiveLease(f"no active lease for {repo_id!r}")
        monkeypatch.setattr(mod, "heartbeat_repo", boom)

        response = client.post("/api/estate/park/my-repo/heartbeat")
        assert response.status_code == 409

    def test_release_releases_lease_on_this_host(self, monkeypatch):
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod

        monkeypatch.setattr(mod, "current_host_id", lambda: "test-lab")
        captured = {}

        def fake_release_repo(repo_id, host_id=None):
            captured["repo_id"] = repo_id
            captured["host_id"] = host_id
            return {"lease_id": "abc", "repo_id": repo_id, "host_id": host_id}
        monkeypatch.setattr(mod, "release_repo", fake_release_repo)

        response = client.post("/api/estate/park/my-repo/release")

        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert captured == {"repo_id": "my-repo", "host_id": "test-lab"}

    def test_release_no_active_lease_returns_409(self, monkeypatch):
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod

        monkeypatch.setattr(mod, "current_host_id", lambda: "test-lab")

        def boom(repo_id, host_id=None):
            raise mod.NoActiveLease(f"no active lease for {repo_id!r}")
        monkeypatch.setattr(mod, "release_repo", boom)

        response = client.post("/api/estate/park/my-repo/release")
        assert response.status_code == 409

    def test_heartbeat_requires_estate_execute_scope(self, monkeypatch):
        """A read-only estate:read token must not be able to mutate a
        lease — same scope discipline as /api/estate/run."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        app = FastAPI()
        app.include_router(setup_estate_routing_routes())
        client = TestClient(app, raise_server_exceptions=False)

        @app.middleware("http")
        async def _inject_token(request, call_next):
            request.state.api_token = True
            request.state.api_token_scopes = ["estate:read"]
            request.state.api_token_owner = "laptop"
            return await call_next(request)

        response = client.post("/api/estate/park/my-repo/heartbeat")
        assert response.status_code == 403

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
import asyncio
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes.estate_routing_routes import (
    RunTaskEnvelope,
    TaskEnvelope,
    _scope_owner,
    setup_estate_routing_routes,
)


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

    def test_implementation_mode_reaches_nested_routing_dict(self):
        envelope = RunTaskEnvelope(
            task_class="code", objective="implement", allow_paid_escalation=True,
            mode="implementation",
        )
        task = envelope.to_task()
        assert task["routing"] == {
            "allow_paid_escalation": True,
            "mode": "implementation",
        }

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

    def _app(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "false")
        app = FastAPI()
        app.include_router(setup_estate_routing_routes())
        return app

    def _endpoint(self, app, path, method):
        def _iter_routes(routes):
            for route in routes:
                original_router = getattr(route, "original_router", None)
                if original_router is not None:
                    yield from _iter_routes(original_router.routes)
                    continue
                yield route

        for route in _iter_routes(app.router.routes):
            if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
                return route.endpoint
        raise AssertionError(f"route {method} {path} not found")

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

    @pytest.mark.asyncio
    async def test_run_route_offloads_blocking_run_task_from_event_loop(self, monkeypatch):
        app = self._app(monkeypatch)
        run_endpoint = self._endpoint(app, "/api/estate/run", "POST")
        hosts_endpoint = self._endpoint(app, "/api/estate/route/hosts", "GET")
        import routes.estate_routing_routes as mod

        def fake_run_task(task):
            time.sleep(0.5)
            return {"ok": True, "executed": True}

        monkeypatch.setattr(mod, "run_task", fake_run_task)
        monkeypatch.setattr(mod, "eligible_hosts", lambda repo=None: [{"host_id": "test-lab", "eligible": True}])

        req = _cookie_request()
        start = time.monotonic()
        slow_call = asyncio.create_task(run_endpoint(req, RunTaskEnvelope(task_class="code", objective="slow")))
        await asyncio.sleep(0.05)
        yielded_after = time.monotonic() - start
        hosts_started = time.monotonic()
        hosts_result = await hosts_endpoint(req, None)
        hosts_elapsed = time.monotonic() - hosts_started

        assert yielded_after < 0.3, "event loop should stay responsive while run_task sleeps in a worker thread"
        assert hosts_elapsed < 0.1
        assert hosts_result == {"hosts": [{"host_id": "test-lab", "eligible": True}]}
        assert slow_call.done() is False
        await slow_call

    def test_execution_route_uses_a_single_watchdog_regardless_of_mode(self, monkeypatch):
        """Controller review of an earlier amendment: asyncio.wait_for()
        around asyncio.to_thread() cannot forcibly terminate the worker
        thread it wraps - a timeout only stops awaiting it, the underlying
        execution keeps running to its own natural completion regardless.
        A shorter "ordinary mode" bound therefore does not save anything -
        it just makes the client give up early while the real work
        continues unseen server-side. There must be exactly one watchdog,
        set above every executor's own worst-case bound, applied
        identically whether or not mode == "implementation"."""
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod

        monkeypatch.setattr(mod, "_EXECUTION_ROUTE_TIMEOUT", 1.0)
        monkeypatch.setattr(mod, "run_task", lambda task: time.sleep(1.4) or {"ok": True})

        ordinary = client.post("/api/estate/run", json={"task_class": "code", "objective": "advise"})
        implementation = client.post("/api/estate/run", json={
            "task_class": "code", "objective": "implement", "mode": "implementation",
        })

        assert ordinary.status_code == 504
        assert implementation.status_code == 504
        assert ordinary.json() == {"detail": "Request exceeded 1s timeout"}
        assert implementation.json() == {"detail": "Request exceeded 1s timeout"}, (
            "implementation mode must not get its own separate, shorter-labelled "
            "watchdog value - both modes share the exact same bound"
        )

    def test_execution_route_never_times_out_while_worker_stays_within_its_declared_bound(self, monkeypatch):
        """The actual proof that a route timeout cannot fire while its
        executor is still legitimately within the supported timeout
        hierarchy (worker-owned bound < route watchdog < client timeout):
        simulate a worker that takes just under the (test-shrunk) route
        watchdog, matching how a real worker respecting its own bound
        would behave, and confirm the response is the real result, never
        a 504 - there is no "request ends while execution survives" gap
        as long as the hierarchy holds."""
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod

        monkeypatch.setattr(mod, "_EXECUTION_ROUTE_TIMEOUT", 3.0)
        monkeypatch.setattr(mod, "run_task", lambda task: time.sleep(2.5) or {"ok": True, "executed": True})

        response = client.post("/api/estate/run", json={"task_class": "code", "objective": "advise"})

        assert response.status_code == 200
        assert response.json() == {"ok": True, "executed": True}

    def test_execution_route_watchdog_exceeds_every_real_executor_bound(self):
        """Structural proof against the actual (unmocked) production
        constants, not shrunk test values: worker-owned hard bound <
        route watchdog < client timeout must hold by construction. Reads
        each executor's own default via introspection rather than
        hardcoding the numbers again here, so this fails the moment
        someone raises a worker bound without also raising the watchdog."""
        import inspect

        import routes.estate_routing_routes as mod
        import src.estate_router as estate_router_mod

        codex_timeout = inspect.signature(estate_router_mod.execute_codex).parameters["timeout"].default
        codex_write_timeout = inspect.signature(estate_router_mod.execute_codex_write).parameters["timeout"].default
        local_sig = inspect.signature(estate_router_mod.execute_local).parameters
        local_worst_case = local_sig["timeout"].default * (1 + local_sig["max_retries"].default)

        assert mod._EXECUTION_ROUTE_TIMEOUT > codex_timeout
        assert mod._EXECUTION_ROUTE_TIMEOUT > codex_write_timeout
        assert mod._EXECUTION_ROUTE_TIMEOUT > local_worst_case

    def test_implementation_mode_invalid_lease_failure_does_not_take_timeout_path(self, monkeypatch):
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod

        monkeypatch.setattr(mod, "_EXECUTION_ROUTE_TIMEOUT", 2.0)
        started = time.monotonic()
        monkeypatch.setattr(mod, "run_task", lambda task: {
            "ok": False,
            "executed": False,
            "execution_error": "implementation mode requires an active non-stale lease for 'test-repo' held by 'test-lab'",
            "escalation_reason": "write_lease_missing",
            "verification_outcome": "fail",
        })

        response = client.post("/api/estate/run", json={
            "task_class": "bounded_code_implementation",
            "objective": "implement",
            "repo": "test-repo",
            "mode": "implementation",
        })

        assert time.monotonic() - started < 0.5
        assert response.status_code == 200
        assert response.json()["execution_error"] == (
            "implementation mode requires an active non-stale lease for 'test-repo' held by 'test-lab'"
        )
        assert response.json()["escalation_reason"] == "write_lease_missing"


class TestDelegationPreflightRoute:
    def _client(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "false")
        app = FastAPI()
        app.include_router(setup_estate_routing_routes())
        return TestClient(app)

    def test_post_preflight_passes_units_to_classifier(self, monkeypatch):
        client = self._client(monkeypatch)
        captured = {}
        import routes.estate_routing_routes as mod

        def fake_preflight(units):
            captured["units"] = units
            return {"ok": True, "snapshot": {"eligible_hosts": []}, "units": []}

        monkeypatch.setattr(mod, "delegation_preflight", fake_preflight)
        response = client.post("/api/estate/preflight", json={"units": [{
            "task_class": "bounded_code_implementation",
            "repo": "odysseus",
            "capabilities": ["code-strong"],
            "objective": "implement it",
        }]})

        assert response.status_code == 200
        assert captured["units"][0]["task_class"] == "bounded_code_implementation"
        assert captured["units"][0]["capabilities"] == ["code-strong"]

    def test_post_preflight_rejects_empty_unit_list(self, monkeypatch):
        client = self._client(monkeypatch)
        response = client.post("/api/estate/preflight", json={"units": []})
        assert response.status_code == 422


class TestParkAcquireRoute:
    """POST /api/estate/park/{repo_id} — docs/aoteru-final-convergence-
    activation.agent-task.md item D: safe remote lease acquisition. The
    caller supplies only a repo_id; path resolution and the git-clean
    check happen server-side via src.park_lease_ops.park_repo_by_id."""

    def _client(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "false")
        app = FastAPI()
        app.include_router(setup_estate_routing_routes())
        return TestClient(app)

    def test_park_acquires_a_lease(self, monkeypatch):
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod

        monkeypatch.setattr(mod, "current_host_id", lambda: "test-lab")
        captured = {}

        def fake_park_repo_by_id(repo_id, host_id, *, branch=None, session_id=None):
            captured.update(repo_id=repo_id, host_id=host_id, branch=branch)
            return {"lease_id": "abc", "repo_id": repo_id, "host_id": host_id,
                    "worktree_path": "/real/path", "branch": branch, "session_id": None,
                    "reclaimed_stale_lease": None}
        monkeypatch.setattr(mod, "park_repo_by_id", fake_park_repo_by_id)

        response = client.post("/api/estate/park/my-repo", params={"branch": "main"})

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["worktree_path"] == "/real/path"
        assert captured == {"repo_id": "my-repo", "host_id": "test-lab", "branch": "main"}

    def test_park_unresolvable_repo_returns_404(self, monkeypatch):
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod

        monkeypatch.setattr(mod, "current_host_id", lambda: "test-lab")

        def boom(repo_id, host_id, *, branch=None, session_id=None):
            raise mod.RepoNotResolvable(f"{repo_id!r} is not registered")
        monkeypatch.setattr(mod, "park_repo_by_id", boom)

        response = client.post("/api/estate/park/unknown-repo")
        assert response.status_code == 404

    def test_park_dirty_worktree_returns_409(self, monkeypatch):
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod

        monkeypatch.setattr(mod, "current_host_id", lambda: "test-lab")

        def boom(repo_id, host_id, *, branch=None, session_id=None):
            raise mod.RepoNotClean(f"refusing to park {repo_id!r}: dirty")
        monkeypatch.setattr(mod, "park_repo_by_id", boom)

        response = client.post("/api/estate/park/my-repo")
        assert response.status_code == 409

    def test_park_conflict_returns_409(self, monkeypatch):
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod

        monkeypatch.setattr(mod, "current_host_id", lambda: "test-lab")

        def boom(repo_id, host_id, *, branch=None, session_id=None):
            raise mod.ParkConflict(f"{repo_id!r} already parked")
        monkeypatch.setattr(mod, "park_repo_by_id", boom)

        response = client.post("/api/estate/park/my-repo")
        assert response.status_code == 409

    def test_park_worktree_verification_error_returns_409(self, monkeypatch):
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod

        monkeypatch.setattr(mod, "current_host_id", lambda: "test-lab")

        def boom(repo_id, host_id, *, branch=None, session_id=None):
            raise mod.WorktreeVerificationError(f"refusing to park {repo_id!r} on branch 'main': verification failed")
        monkeypatch.setattr(mod, "park_repo_by_id", boom)

        response = client.post("/api/estate/park/my-repo", params={"branch": "main"})
        assert response.status_code == 409
        assert response.json()["detail"] == "refusing to park 'my-repo' on branch 'main': verification failed"

    def test_park_unregistered_host_returns_503(self, monkeypatch):
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod

        monkeypatch.setattr(mod, "current_host_id", lambda: None)

        response = client.post("/api/estate/park/my-repo")
        assert response.status_code == 503

    def test_park_requires_estate_execute_scope(self, monkeypatch):
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

        response = client.post("/api/estate/park/my-repo")
        assert response.status_code == 403


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

    def test_park_status_returns_active_leases_summary(self, monkeypatch):
        client = self._client(monkeypatch)
        import routes.estate_routing_routes as mod

        monkeypatch.setattr(mod, "active_leases_summary", lambda: [
            {"repo_id": "odysseus", "host_id": "hz2-workstation", "heartbeat_at": "2026-01-01T00:00:00", "stale": False},
        ])

        response = client.get("/api/estate/park/status")

        assert response.status_code == 200
        body = response.json()
        assert body["active_park_leases"][0]["repo_id"] == "odysseus"

    def test_park_status_requires_scope(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "true")
        app = FastAPI()
        app.include_router(setup_estate_routing_routes())
        client = TestClient(app, raise_server_exceptions=False)

        @app.middleware("http")
        async def _inject_token(request, call_next):
            request.state.api_token = True
            request.state.api_token_scopes = ["chat"]
            request.state.api_token_owner = "companion"
            return await call_next(request)

        response = client.get("/api/estate/park/status")
        assert response.status_code == 403


class TestDecisionLookupRoute:
    """GET /api/estate/decision/{decision_id} — Workstream K's 'logs/
    result pointers surface': every POST /api/estate/run response already
    returns a decision_id, this looks it back up afterward."""

    def _client(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "false")
        app = FastAPI()
        app.include_router(setup_estate_routing_routes())
        return TestClient(app)

    def test_get_decision_returns_the_row(self, monkeypatch):
        client = self._client(monkeypatch)
        import src.routing_evaluator as routing_evaluator

        monkeypatch.setattr(routing_evaluator, "get_decision_by_id", lambda decision_id: {
            "id": decision_id, "task_class": "coding", "executor": "local", "status": "complete",
        })

        response = client.get("/api/estate/decision/some-id")

        assert response.status_code == 200
        assert response.json()["id"] == "some-id"

    def test_get_decision_unknown_id_returns_404(self, monkeypatch):
        client = self._client(monkeypatch)
        import src.routing_evaluator as routing_evaluator

        monkeypatch.setattr(routing_evaluator, "get_decision_by_id", lambda decision_id: None)

        response = client.get("/api/estate/decision/does-not-exist")
        assert response.status_code == 404

    def test_get_decision_requires_scope(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "true")
        app = FastAPI()
        app.include_router(setup_estate_routing_routes())
        client = TestClient(app, raise_server_exceptions=False)

        @app.middleware("http")
        async def _inject_token(request, call_next):
            request.state.api_token = True
            request.state.api_token_scopes = ["chat"]
            request.state.api_token_owner = "companion"
            return await call_next(request)

        response = client.get("/api/estate/decision/some-id")
        assert response.status_code == 403

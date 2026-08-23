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
from fastapi import HTTPException

from routes.estate_routing_routes import RunTaskEnvelope, TaskEnvelope, _scope_owner


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

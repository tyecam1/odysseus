"""POST /misumi/route-explain: stateless base-persona/team inspection with explicit omissions."""

import hashlib
import socket
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import routes.misumi_routes as misumi_routes
from routes.misumi_routes import _team_plan, setup_misumi_routes
from services.memory.skills import SkillsManager
from src.misumi_household import HouseholdReadOnlyAdapter, infer_household_domain
from src.misumi_persona_routing import resolve_auto_lead
from src.misumi_persona_state import is_reserved_turn


def _configure_roots(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(tmp_path / "no-household-here"))
    monkeypatch.setenv("MISUMI_ROUTING_STATE_ROOT", str(data_root / "routing"))
    monkeypatch.setenv("MISUMI_PERSONA_STATE_ROOT", str(data_root / "persona-state"))
    monkeypatch.setenv("MISUMI_DIALOGUE_STATE_ROOT", str(data_root / "dialogue"))
    monkeypatch.setenv("MISUMI_EVENT_LOG", str(data_root / "events.jsonl"))
    return data_root


@pytest.fixture()
def client(tmp_path, monkeypatch):
    data_root = _configure_roots(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(setup_misumi_routes(SkillsManager(str(data_root))))
    test_client = TestClient(app)
    test_client.fixture_data_root = data_root
    return test_client


@pytest.fixture()
def authenticated_client(tmp_path, monkeypatch):
    """Exercise the route behind a synthetic bearer boundary, as existing Misumi scope tests do."""
    data_root = _configure_roots(tmp_path, monkeypatch)
    app = FastAPI()
    credentials = {
        "ody_route_explain_unrelated_fixture": ["todos:read"],
        "ody_route_explain_read_fixture": ["misumi:read"],
    }

    @app.middleware("http")
    async def synthetic_bearer(request, call_next):
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"error": "Not authenticated"})
        token = authorization.removeprefix("Bearer ")
        scopes = credentials.get(token)
        if scopes is None:
            return JSONResponse(status_code=401, content={"error": "Invalid API token"})
        request.state.current_user = "api"
        request.state.api_token = True
        request.state.api_token_owner = "route-explain-test"
        request.state.api_token_scopes = list(scopes)
        return await call_next(request)

    app.include_router(setup_misumi_routes(SkillsManager(str(data_root))))
    return TestClient(app)


def explain(client, prompt, persona=None):
    body = {"prompt": prompt}
    if persona is not None:
        body["persona"] = persona
    response = client.post("/misumi/route-explain", json=body)
    assert response.status_code == 200, response.text
    return response.json()


PROMPTS = [
    "Aoteru, help me plan a small dinner party this Saturday: the menu, a tidy-up schedule, and some music.",
    "What is on the shopping list?",
    "Jin, play something by Miles Davis.",
    "Ask Kurisu and Lelouch to help me reorganise the kitchen and set a cleaning rota.",
    "In two sentences, what is the difference between a stack and a queue?",
]


@pytest.mark.parametrize("prompt", PROMPTS)
def test_the_explanation_is_exactly_what_the_routing_code_decides(client, prompt):
    body = explain(client, prompt)
    lead, routing = resolve_auto_lead(prompt, prior_lead=None)
    assert body["lead"]["persona"] == lead and body["lead"]["source"] == "auto"
    assert body["lead"]["method"] == str((routing or {}).get("method") or "")
    assert body["lead"]["reasons"] == [str(item) for item in ((routing or {}).get("reasons") or [])]
    team = _team_plan(prompt, lead)
    assert body["team"] == {key: team.get(key) for key in ("decision", "supports", "excluded", "reasons")}
    assert body["team"]["decision"] in {"solo", "team"}
    assert body["household_domain"] == infer_household_domain(prompt)
    assert body["safety"]["reserved_turn"] == bool(is_reserved_turn(prompt))


def test_it_is_deterministic_and_repeatable(client):
    assert explain(client, PROMPTS[0]) == explain(client, PROMPTS[0]) == explain(client, PROMPTS[0])


def test_a_named_request_forms_a_team_and_a_plain_one_stays_solo(client):
    named = explain(client, PROMPTS[3])
    assert named["team"]["decision"] == "team" and named["team"]["supports"], named["team"]
    solo = explain(client, PROMPTS[4])
    assert solo["team"]["decision"] == "solo" and solo["team"]["supports"] == []


def test_a_caller_selected_persona_is_honoured_and_labelled(client):
    body = explain(client, "What is on the shopping list?", persona="sanji")
    assert body["lead"]["persona"] == "sanji" and body["lead"]["source"] == "caller"
    assert body["lead"]["method"] == "caller-selected" and body["lead"]["reasons"]


def _tree_snapshot(root: Path):
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): (
            "directory" if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()
        )
        for path in root.rglob("*")
    }


def test_it_never_calls_a_model_touches_the_network_reads_household_records_or_writes_state(client, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("route-explain must not open a network connection")

    def forbidden(*args, **kwargs):
        raise AssertionError("route-explain crossed an omitted execution boundary")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(misumi_routes, "_model_turn", forbidden)
    monkeypatch.setattr(misumi_routes, "_consult_persona", forbidden)
    for method in (
        "iter_files", "read", "search", "item_index", "resolve_question", "mentions_recorded_item", "resolution_hits",
    ):
        monkeypatch.setattr(HouseholdReadOnlyAdapter, method, forbidden)
    before = _tree_snapshot(client.fixture_data_root)
    body = explain(client, "What is on the shopping list?")
    assert _tree_snapshot(client.fixture_data_root) == before
    assert body["executes_model"] is False and body["writes_state"] is False
    text = str(body).lower()
    assert not any(word in text for word in ("snippet", "sources", "desk", "household/"))   # a domain id only, never content
    assert body["household_domain"] == "shopping"


def test_a_persisted_follow_up_can_diverge_from_the_stateless_preview(client):
    personas = {
        "aoteru": {"routing": {"intents": ["default"]}},
        "kurisu": {"routing": {"intents": ["archive"]}},
    }
    carried, carried_routing = resolve_auto_lead("And then?", personas, prior_lead="kurisu")
    assert carried == "kurisu" and carried_routing["reasons"] == ["carry:kurisu"]

    body = explain(client, "And then?")
    assert body["lead"]["persona"] == "aoteru"
    assert body["preview"] == {
        "scope": "base-persona-and-team",
        "omits": [
            "persisted_lead",
            "learned_routing",
            "household_resolution",
            "tool_dispatch",
            "post_reply_consultation",
        ],
    }


def test_household_domain_is_only_a_label_and_execution_is_explicitly_omitted(client):
    body = explain(client, "What is on the shopping list?")
    assert body["household_domain"] == "shopping"
    assert {"household_resolution", "tool_dispatch"} <= set(body["preview"]["omits"])
    assert body["executes_model"] is False and body["writes_state"] is False
    assert "source" not in body and "sources" not in body


def test_the_response_shape_is_closed(client):
    body = explain(client, PROMPTS[1])
    assert set(body) == {"executes_model", "writes_state", "preview", "lead", "team", "household_domain", "safety"}
    assert set(body["preview"]) == {"scope", "omits"}
    assert set(body["lead"]) == {"persona", "source", "method", "reasons"}
    assert set(body["team"]) == {"decision", "supports", "excluded", "reasons"}
    assert set(body["safety"]) == {"reserved_turn", "learned_routing_withheld"}


def test_a_missing_token_is_rejected(authenticated_client):
    payload = {"prompt": "Explain a stack"}
    assert authenticated_client.post("/misumi/route-explain", json=payload).status_code == 401


def test_an_insufficient_token_scope_is_rejected(authenticated_client):
    denied = authenticated_client.post(
        "/misumi/route-explain",
        json={"prompt": "Explain a stack"},
        headers={"Authorization": "Bearer ody_route_explain_unrelated_fixture"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "API token requires misumi:read scope"


def test_a_misumi_read_token_is_permitted(authenticated_client):
    allowed = authenticated_client.post(
        "/misumi/route-explain",
        json={"prompt": "Explain a stack"},
        headers={"Authorization": "Bearer ody_route_explain_read_fixture"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["preview"]["scope"] == "base-persona-and-team"


@pytest.mark.parametrize("payload", [{}, {"prompt": ""}, {"prompt": "   "}, {"prompt": "x" * 4001}])
def test_an_empty_or_oversized_prompt_is_rejected(client, payload):
    assert client.post("/misumi/route-explain", json=payload).status_code == 422

"""POST /misumi/route-explain: a read-only inspection of the deterministic routing decision (no model, no state, no household data)."""

import socket

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.misumi_routes import _team_plan, setup_misumi_routes
from services.memory.skills import SkillsManager
from src.misumi_household import infer_household_domain
from src.misumi_persona_routing import resolve_auto_lead
from src.misumi_persona_state import is_reserved_turn


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(tmp_path / "no-household-here"))
    app = FastAPI()
    app.include_router(setup_misumi_routes(SkillsManager(str(tmp_path / "data"))))
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


def test_it_never_calls_a_model_touches_the_network_or_reads_household_data(client, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("route-explain must not open a network connection")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    body = explain(client, "What is on the shopping list?")
    assert body["executes_model"] is False and body["writes_state"] is False
    text = str(body).lower()
    assert not any(word in text for word in ("snippet", "sources", "desk", "household/"))   # a domain id only, never content
    assert body["household_domain"] == "shopping"


def test_the_response_shape_is_closed(client):
    body = explain(client, PROMPTS[1])
    assert set(body) == {"executes_model", "writes_state", "lead", "team", "household_domain", "safety"}
    assert set(body["lead"]) == {"persona", "source", "method", "reasons"}
    assert set(body["team"]) == {"decision", "supports", "excluded", "reasons"}
    assert set(body["safety"]) == {"reserved_turn", "learned_routing_withheld"}


@pytest.mark.parametrize("payload", [{}, {"prompt": ""}, {"prompt": "   "}, {"prompt": "x" * 4001}])
def test_an_empty_or_oversized_prompt_is_rejected(client, payload):
    assert client.post("/misumi/route-explain", json=payload).status_code == 422

"""Conversation-session history is a separate dimension from semantic retention.

`retention_mode` controls semantic memory/artifacts; `history_mode` controls the
ordinary conversation session history. Omitting `history_mode` keeps the
historical coupling on purpose (see routes.misumi_routes._persists_history).
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.models import Session
from routes import misumi_routes
from services.memory.skills import SkillsManager
from src import endpoint_resolver, llm_core


class FakeSessionManager:
    def __init__(self):
        self.sessions = {}

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def create_session(self, session_id, name, endpoint_url, model, rag=False, owner=None):
        session = Session(session_id, name, endpoint_url, model, rag=rag, owner=owner)
        self.sessions[session_id] = session
        return session

    def add_message(self, session_id, message):
        self.sessions[session_id].history.append(message)


class FakeChatProcessor:
    def build_context_preface(self, prompt, session, **kwargs):
        return ([{"role": "system", "content": "native memory context"}], [], [])


def _client(tmp_path, monkeypatch):
    household = tmp_path / "household"
    household.mkdir()
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(household))
    monkeypatch.setattr(endpoint_resolver, "resolve_endpoint",
                        lambda *args, **kwargs: ("http://model.test", "model", {}))

    async def model_call(url, model, messages, **kwargs):
        return '{"answer":"noted","memory":null,"artifact":null}'

    monkeypatch.setattr(llm_core, "llm_call_async", model_call)
    sessions = FakeSessionManager()
    app = FastAPI()
    app.include_router(misumi_routes.setup_misumi_routes(
        SkillsManager(str(tmp_path / "skills")),
        session_manager=sessions,
        chat_processor=FakeChatProcessor(),
        memory_root=tmp_path / "passive-memory",
    ))
    return TestClient(app), sessions


def _respond(client, **fields):
    payload = {"prompt": "remember that the boiler is serviced in March", "persona": "kurisu",
               "session_id": "misumi-h", **fields}
    response = client.post("/misumi/respond", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_default_behaviour_is_unchanged_history_and_memory_both_auto(tmp_path, monkeypatch):
    client, sessions = _client(tmp_path, monkeypatch)
    body = _respond(client)
    assert body["history_persisted"] is True
    assert len(sessions.sessions["misumi-h"].history) == 2


def test_legacy_retention_off_without_history_mode_still_stores_nothing(tmp_path, monkeypatch):
    # Clients written before the split use retention_mode "off" to mean "store nothing".
    client, sessions = _client(tmp_path, monkeypatch)
    body = _respond(client, retention_mode="off")
    assert body["history_persisted"] is False
    assert "misumi-h" not in sessions.sessions


def test_explicit_history_survives_semantic_memory_being_off(tmp_path, monkeypatch):
    client, sessions = _client(tmp_path, monkeypatch)
    body = _respond(client, retention_mode="off", history_mode="auto")
    assert body["history_persisted"] is True
    assert len(sessions.sessions["misumi-h"].history) == 2  # ordinary history kept
    # semantic memory and artifacts stayed off while ordinary history was kept
    assert body["retention"] == {"memory": {"status": "disabled"}, "artifact": {"status": "disabled"}}


def test_history_can_be_off_while_semantic_retention_stays_auto(tmp_path, monkeypatch):
    client, sessions = _client(tmp_path, monkeypatch)
    body = _respond(client, retention_mode="auto", history_mode="off")
    assert body["history_persisted"] is False
    assert "misumi-h" not in sessions.sessions


def test_persist_turn_false_is_always_incognito(tmp_path, monkeypatch):
    client, sessions = _client(tmp_path, monkeypatch)
    for fields in ({"history_mode": "auto"}, {"retention_mode": "auto", "history_mode": "auto"}, {}):
        body = _respond(client, persist_turn=False, **fields)
        assert body["history_persisted"] is False
    assert "misumi-h" not in sessions.sessions

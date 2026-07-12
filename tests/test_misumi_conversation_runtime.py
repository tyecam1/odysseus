import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.models import Session
from routes import misumi_routes
from services.memory.skills import SkillsManager
from src import endpoint_resolver, llm_core
from src.memory import MemoryManager


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


def test_interface_session_history_reaches_the_next_model_turn(tmp_path, monkeypatch):
    household = tmp_path / "household"
    household.mkdir()
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(household))
    monkeypatch.setattr(
        endpoint_resolver,
        "resolve_endpoint",
        lambda *args, **kwargs: ("http://model.test", "model", {}),
    )
    calls = []

    async def model_call(url, model, messages, **kwargs):
        calls.append(messages)
        number = len(calls)
        return '{"answer":"answer %d","memory":null,"artifact":null}' % number

    monkeypatch.setattr(llm_core, "llm_call_async", model_call)
    sessions = FakeSessionManager()
    app = FastAPI()
    app.include_router(misumi_routes.setup_misumi_routes(
        SkillsManager(str(tmp_path / "skills")),
        session_manager=sessions,
        chat_processor=FakeChatProcessor(),
        memory_root=tmp_path / "passive-memory",
    ))
    client = TestClient(app)

    first = client.post("/misumi/respond", json={
        "prompt": "first turn", "persona": "kurisu",
        "session_id": "misumi-test", "retention_mode": "auto",
    }).json()
    second = client.post("/misumi/respond", json={
        "prompt": "second turn", "persona": "kurisu",
        "session_id": first["session_id"], "retention_mode": "auto",
    }).json()

    assert second["text"] == "answer 2"
    assert any(message.get("content") == "first turn" for message in calls[1])
    assert any(message.get("content") == "answer 1" for message in calls[1])
    assert len(sessions.sessions["misumi-test"].history) == 4

    client.post("/misumi/respond", json={
        "prompt": "health ping", "persona": "kurisu",
        "session_id": "misumi-test", "persist_turn": False,
    })
    assert len(sessions.sessions["misumi-test"].history) == 4
    assert not any(message.get("content") == "first turn" for message in calls[2])


def test_durable_memory_is_saved_to_native_memory_and_deduplicated(tmp_path):
    manager = MemoryManager(str(tmp_path))
    turn = {
        "memory": {"text": "The user prefers punchy seasoning.", "category": "preference"},
        "artifact": None,
    }
    kwargs = dict(
        prompt="Remember that I prefer punchy seasoning",
        turn=turn,
        retention_mode="auto",
        owner="owner",
        session_id=None,
        memory_manager=manager,
        memory_vector=None,
        session_manager=None,
    )

    first = asyncio.run(misumi_routes._apply_retention(**kwargs))
    second = asyncio.run(misumi_routes._apply_retention(**kwargs))

    assert first["memory"]["status"] == "saved"
    assert second["memory"]["status"] == "duplicate"
    assert manager.load(owner="owner")[0]["category"] == "preference"


def test_high_confidence_model_decision_can_capture_an_implicit_stable_fact(tmp_path):
    manager = MemoryManager(str(tmp_path))
    result = asyncio.run(misumi_routes._apply_retention(
        prompt="My cat is called Pixel.",
        turn={
            "memory": {
                "text": "The user's cat is called Pixel.",
                "category": "fact",
                "confidence": 0.96,
            },
            "artifact": None,
        },
        retention_mode="auto",
        owner="owner",
        session_id=None,
        memory_manager=manager,
        memory_vector=None,
        session_manager=None,
    ))

    assert result["memory"]["status"] == "saved"


def test_structured_model_none_is_not_overridden_by_keyword_fallback():
    turn = misumi_routes._parse_model_turn(
        '{"answer":"Understood.","memory":null,"artifact":null}',
        "I like this transient option",
    )

    assert turn["retention_decided"] is True
    assert turn["memory"] is None
    assert turn["artifact"] is None


def test_sensitive_memory_and_artifact_are_blocked(tmp_path):
    manager = MemoryManager(str(tmp_path))
    result = asyncio.run(misumi_routes._apply_retention(
        prompt="Remember my API key and save it as a document",
        turn={
            "memory": {"text": "API key is secret", "category": "fact"},
            "artifact": {"title": "Credentials", "content": "API key is secret"},
        },
        retention_mode="auto",
        owner="owner",
        session_id="session",
        memory_manager=manager,
        memory_vector=None,
        session_manager=object(),
    ))

    assert result["memory"] == {"status": "blocked", "reason": "sensitive-content"}
    assert result["artifact"] == {"status": "blocked", "reason": "sensitive-content"}
    assert manager.load(owner="owner") == []


def test_requested_artifact_uses_existing_document_tool(tmp_path, monkeypatch):
    calls = []

    async def create_document(self, content, ctx):
        calls.append((content, ctx))
        return {"doc_id": "doc-1", "title": "Cleaning plan"}

    monkeypatch.setattr(
        "src.agent_tools.document_tools.CreateDocumentTool.execute",
        create_document,
    )
    monkeypatch.setattr(misumi_routes, "_existing_document", lambda *args: None)
    result = asyncio.run(misumi_routes._apply_retention(
        prompt="Create a document with our cleaning plan",
        turn={
            "memory": None,
            "artifact": {"title": "Cleaning plan", "content": "# Cleaning plan\n\n- Kitchen"},
        },
        retention_mode="auto",
        owner="owner",
        session_id="session",
        memory_manager=None,
        memory_vector=None,
        session_manager=object(),
    ))

    assert result["artifact"] == {"status": "created", "doc_id": "doc-1", "title": "Cleaning plan"}
    assert calls[0][1] == {"session_id": "session", "owner": "owner"}


def test_exact_duplicate_artifact_reuses_existing_document(monkeypatch):
    monkeypatch.setattr(
        misumi_routes,
        "_existing_document",
        lambda *args: {"doc_id": "existing-doc", "title": "Cleaning plan"},
    )
    result = asyncio.run(misumi_routes._apply_retention(
        prompt="Create a document with our cleaning plan",
        turn={
            "memory": None,
            "artifact": {"title": "Cleaning plan", "content": "# Cleaning plan\n\n- Kitchen"},
        },
        retention_mode="auto",
        owner="owner",
        session_id="session",
        memory_manager=None,
        memory_vector=None,
        session_manager=object(),
    ))

    assert result["artifact"] == {
        "status": "duplicate",
        "doc_id": "existing-doc",
        "title": "Cleaning plan",
    }

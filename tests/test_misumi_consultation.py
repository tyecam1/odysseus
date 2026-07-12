import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import misumi_routes
from services.memory.skills import SkillsManager
from src import endpoint_resolver, llm_core, seed_order_context
from src.misumi_memory import MisumiMemory


PERSONAS = """\
personas:
  aoteru:
    role: head-human-interfacer
    consults: [kurisu, misato, ichigo, giorno, erwin]
    routing: {intents: [coordinate]}
  lelouch:
    role: operator
    consults: [aoteru]
    routing: {intents: [implementation, deployment]}
  kurisu:
    role: archivist
    consults: [aoteru]
    routing: {intents: [evidence]}
  misato:
    role: caretaker
    consults: [aoteru]
    routing: {intents: [routine]}
  ichigo:
    role: guardian
    consults: [aoteru]
    routing: {intents: [hardware]}
  giorno:
    role: creative-spawner
    consults: [aoteru]
    routing: {intents: [experiment]}
  erwin:
    role: deputy-general
    consults: [aoteru]
    routing: {intents: [risk]}
"""


def _client(tmp_path: Path, monkeypatch, llm_call, *, consult="true"):
    household = tmp_path / "household"
    household.mkdir()
    root = tmp_path / "seed"
    persona_path = root / "config" / "personas.yaml"
    persona_path.parent.mkdir(parents=True)
    persona_path.write_text(PERSONAS, encoding="utf-8")
    memory_root = tmp_path / "memory"

    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(household))
    monkeypatch.setenv("MISUMI_EVENT_LOG", str(tmp_path / "events.jsonl"))
    monkeypatch.setenv("MISUMI_CONSULT", consult)
    monkeypatch.setattr("src.persona_capabilities._resolve_seed_root", lambda: root)
    monkeypatch.setattr(seed_order_context, "build_seed_order_context", lambda: "SEED ORDER")
    monkeypatch.setattr(
        endpoint_resolver,
        "resolve_endpoint",
        lambda *args, **kwargs: ("http://model.test/v1/chat/completions", "model", {}),
    )
    monkeypatch.setattr(llm_core, "llm_call_async", llm_call)
    app = FastAPI()
    app.include_router(misumi_routes.setup_misumi_routes(
        SkillsManager(str(tmp_path / "skills")), memory_root=memory_root
    ))
    return TestClient(app), MisumiMemory(memory_root)


def _is_consult(messages):
    return any("internal consultation" in str(message.get("content")) for message in messages)


def _consult_persona(messages):
    system = " ".join(str(message.get("content")) for message in messages if message.get("role") == "system")
    return next(name for name in ("kurisu", "lelouch", "misato", "ichigo", "giorno", "erwin") if f"You are {name}," in system)


def test_plan_consults_named_then_intent_and_records_linked_handoffs(tmp_path, monkeypatch):
    calls = []

    async def llm_call(url, model, messages, **kwargs):
        calls.append((messages, kwargs))
        if not _is_consult(messages):
            joined = " ".join(str(message.get("content")) for message in messages)
            assert "Record the assumptions" in joined
            assert "Stage the implementation" in joined
            return '{"answer":"Synthesized plan.","memory":null,"artifact":null}'
        persona = _consult_persona(messages)
        return {"kurisu": "Record the assumptions. Then review evidence.", "lelouch": "Stage the implementation. Then verify it."}[persona]

    client, memory = _client(tmp_path, monkeypatch, llm_call)
    body = client.post("/misumi/respond", json={"prompt": "Ask Kurisu and Lelouch to plan the deployment approach", "persona": "aoteru"}).json()

    assert [item["persona"] for item in body["consulted"]] == ["kurisu", "lelouch"]
    assert body["text"] == "Synthesized plan."
    assert body["capsule_id"]
    assert len(body["handoff_ids"]) == 2
    assert [call[1]["max_tokens"] for call in calls] == [240, 240, 700]
    assert [call[1]["timeout"] for call in calls] == [10, 10, 25]
    capsules, _ = memory.capsules()
    handoffs, _ = memory.handoffs()
    assert capsules[0]["id"] == body["capsule_id"]
    assert capsules[0]["type"] == "decision"
    assert capsules[0]["source"] == "consultation"
    assert capsules[0]["persona_primary"] == "aoteru"
    assert {item["capsule_id"] for item in handoffs} == {body["capsule_id"]}
    assert {item["status"] for item in handoffs} == {"resolved"}
    assert {item["to_persona"] for item in handoffs} == {"kurisu", "lelouch"}


def test_five_named_candidates_are_capped_at_two(tmp_path, monkeypatch):
    consulted = []

    async def llm_call(url, model, messages, **kwargs):
        if not _is_consult(messages):
            return '{"answer":"Synthesized.","memory":null,"artifact":null}'
        persona = _consult_persona(messages)
        consulted.append(persona)
        return "Review the proposal."

    client, _ = _client(tmp_path, monkeypatch, llm_call)
    body = client.post("/misumi/respond", json={"prompt": "Kurisu, Misato, Ichigo, Giorno, and Erwin: consider the approach", "persona": "aoteru"}).json()

    assert consulted == ["kurisu", "misato"]
    assert [item["persona"] for item in body["consulted"]] == ["kurisu", "misato"]


def test_non_aoteru_never_consults(tmp_path, monkeypatch):
    calls = 0

    async def llm_call(url, model, messages, **kwargs):
        nonlocal calls
        calls += 1
        return '{"answer":"Primary reply.","memory":null,"artifact":null}'

    client, memory = _client(tmp_path, monkeypatch, llm_call)
    body = client.post("/misumi/respond", json={"prompt": "Plan the deployment approach", "persona": "lelouch"}).json()

    assert calls == 1
    assert body["consulted"] == []
    assert body["capsule_id"] is None
    assert memory.capsules() == ([], 0)


def test_kill_switch_preserves_legacy_response_and_writes_nothing(tmp_path, monkeypatch):
    async def llm_call(url, model, messages, **kwargs):
        return '{"answer":"Legacy reply.","memory":null,"artifact":null}'

    monkeypatch.setattr(misumi_routes.MisumiEventLog, "request_id", lambda self: "request-1")
    client, memory = _client(tmp_path, monkeypatch, llm_call, consult="false")
    body = client.post("/misumi/respond", json={"prompt": "Plan deployment", "persona": "aoteru"}).json()

    assert body["text"] == "Legacy reply."
    assert body["source"] == "model"
    assert body["node"] == "odysseus"
    assert body["retention"] == {"memory": {"status": "none"}, "artifact": {"status": "none"}}
    assert "consulted" not in body
    assert memory.capsules() == ([], 0)
    assert memory.handoffs() == ([], 0)


def test_failed_consult_is_logged_and_has_no_handoff(tmp_path, monkeypatch, caplog):
    async def llm_call(url, model, messages, **kwargs):
        if not _is_consult(messages):
            return '{"answer":"Synthesized deployment.","memory":null,"artifact":null}'
        if _consult_persona(messages) == "kurisu":
            raise RuntimeError("consult unavailable")
        return "Stage the implementation."

    client, memory = _client(tmp_path, monkeypatch, llm_call)
    with caplog.at_level(logging.WARNING, logger=misumi_routes.__name__):
        body = client.post("/misumi/respond", json={"prompt": "Kurisu and Lelouch: plan deployment", "persona": "aoteru"}).json()

    assert [item["persona"] for item in body["consulted"]] == ["lelouch"]
    assert body["text"] == "Synthesized deployment."
    assert "consult unavailable" in caplog.text
    handoffs, _ = memory.handoffs()
    assert len(handoffs) == 1
    assert handoffs[0]["to_persona"] == "lelouch"


def test_degraded_primary_reply_never_consults(tmp_path, monkeypatch):
    async def unused_call(url, model, messages, **kwargs):
        raise AssertionError("consultation model must not be called")

    client, memory = _client(tmp_path, monkeypatch, unused_call)

    monkeypatch.setattr(misumi_routes, "_resolve_model_endpoint", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    body = client.post("/misumi/respond", json={"prompt": "Plan deployment", "persona": "aoteru"}).json()

    assert "no working model backend" in body["text"]
    assert body["consulted"] == []
    assert memory.capsules() == ([], 0)


def test_contribution_text_is_not_executed_as_a_handoff_action(tmp_path, monkeypatch):
    async def llm_call(url, model, messages, **kwargs):
        if not _is_consult(messages):
            return '{"answer":"Do not send anything.","memory":null,"artifact":null}'
        return "Email the landlord with the plan. Then wait."

    client, memory = _client(tmp_path, monkeypatch, llm_call)
    body = client.post("/misumi/respond", json={"prompt": "Kurisu and Lelouch: plan the approach", "persona": "aoteru"}).json()

    assert len(body["handoff_ids"]) == 2
    handoffs, _ = memory.handoffs()
    assert all("email" not in item["action"].lower() for item in handoffs)
    assert {item["status"] for item in handoffs} == {"resolved"}


def test_consultation_keeps_all_legacy_response_fields(tmp_path, monkeypatch):
    async def llm_call(url, model, messages, **kwargs):
        return '{"answer":"Primary reply.","memory":null,"artifact":null}' if not _is_consult(messages) else "Review the plan."

    client, _ = _client(tmp_path, monkeypatch, llm_call)
    body = client.post("/misumi/respond", json={"prompt": "Plan deployment", "persona": "aoteru", "mood": "steady"}).json()

    assert {
        "text", "state", "mood", "source", "persona", "who", "audio_url",
        "voice", "tts_provider", "request_id", "sources",
    }.issubset(body)
    assert body["state"] == "speaking"
    assert body["mood"] == "steady"
    assert body["source"] == "model"
    assert body["node"] == "odysseus"

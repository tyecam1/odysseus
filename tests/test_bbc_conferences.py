from pathlib import Path
import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.bbc_routes import setup_bbc_routes
from src.bbc.adapters import (
    HomeBaseRepositoryAdapter,
    ObsidianPhDRepositoryAdapter,
    OdysseusRepositoryAdapter,
    RepositoryAdapterRegistry,
)
from src.bbc.runtime import BBCRuntime
from src.bbc.store import BBCStateStore


PERSONAS = """\
version: '0.1'
personas:
  aoteru:
    name: Aoteru Misumi
    role: Integrative Authority
    archetype: governance and system coherence
    skills: [integration summaries, boundary review]
    consults: [kurisu, erwin]
    routing:
      intents: [integration, standards]
  erwin:
    name: Erwin Smith
    role: Risk Strategist
    archetype: priority and risk reviewer
    skills: [blocker review, cost-of-delay assessment]
    consults: [aoteru]
    routing:
      intents: [risk, strategy]
  kurisu:
    name: Makise Kurisu
    role: Scientific Archivist
    archetype: evidence and uncertainty specialist
    skills: [source-linked archiving, contradiction tracking]
    consults: [aoteru]
    routing:
      intents: [evidence, research, archive]
  lelouch:
    name: Lelouch Lamperouge
    role: Workflow Commander
    archetype: task and process designer
    skills: [workflow design, task decomposition]
    consults: [aoteru]
    routing:
      intents: [workflow, implementation]
"""


def _git_repo(path: Path) -> Path:
    subprocess.run(["git", "init", "--quiet", str(path)], check=True, capture_output=True)
    return path


def _conference_runtime(tmp_path: Path, monkeypatch) -> tuple[BBCRuntime, TestClient, object]:
    odysseus = _git_repo(tmp_path / "odysseus")
    homebase = _git_repo(tmp_path / "homebase")
    vault = _git_repo(tmp_path / "vault")
    (odysseus / "ROADMAP.md").write_text("# Runtime\n", encoding="utf-8")
    (homebase / "config").mkdir()
    (homebase / "config" / "personas.yaml").write_text(PERSONAS, encoding="utf-8")
    (homebase / "agent-tasks" / "inbox").mkdir(parents=True)
    (homebase / "agent-tasks" / "inbox" / "task.md").write_text(
        "---\nstatus: open\n---\n# Runtime integration\n", encoding="utf-8"
    )
    (vault / "10-inbox").mkdir()
    (vault / "10-inbox" / "s2-e1.md").write_text(
        """---
artifact_type: work-item
status: active
next_action: Verify the physical acquisition interface.
blocked_by:
  - interface-box-offline
dependencies:
  - GrapheneOS capture client
acceptance_evidence:
  - A timestamped real-device acquisition result
---
# S2-E1 physical acquisition

Validate live robot sensor acquisition through the interface box and GrapheneOS device.
""",
        encoding="utf-8",
    )
    adapters = RepositoryAdapterRegistry((
        OdysseusRepositoryAdapter(odysseus),
        HomeBaseRepositoryAdapter(homebase),
        ObsidianPhDRepositoryAdapter(vault),
    ))
    runtime = BBCRuntime(store=BBCStateStore(tmp_path / "bbc.db"), adapters=adapters)
    node = runtime.refresh_repository("obsidian-phd").nodes[0]
    planned = runtime.create_navigation(
        actor="operator",
        persona_id="aoteru",
        origin=runtime.persona_location("aoteru").room_id,
        destination="research",
        path=[],
        duration_ms=0,
    )
    runtime.transition_navigation(planned.id, "in_progress", actor="operator", expected_version=1)
    runtime.transition_navigation(planned.id, "completed", actor="operator", expected_version=2)
    monkeypatch.setenv("AUTH_ENABLED", "false")
    app = FastAPI()
    app.include_router(setup_bbc_routes(runtime))
    return runtime, TestClient(app), node


def test_persona_projection_is_bounded_derived_and_preserves_live_location(tmp_path, monkeypatch):
    runtime, _client, _node = _conference_runtime(tmp_path, monkeypatch)
    projections = runtime.persona_projections()
    assert [persona.id for persona in projections] == ["aoteru", "erwin", "kurisu", "lelouch"]
    assert all(persona.source_ref == "repo://misumi-homebase/config/personas.yaml" for persona in projections)
    assert runtime.persona_location("kurisu").room_id in {"archive", "research"}
    assert runtime.persona_location("aoteru").room_id == "research"

    rebuilt = BBCRuntime(store=BBCStateStore(runtime.store.path), adapters=runtime.adapters)
    assert rebuilt.persona_location("aoteru").room_id == "research"


@pytest.mark.parametrize("content, message", [
    ("personas: []\n", "personas mapping"),
    ("personas:\n  Bad ID!:\n    name: Bad\n    role: Bad\n", "invalid id"),
    ("personas:\n  bad:\n    name: Bad\n    role: Bad\n    archetype: '" + ("x" * 161) + "'\n", "archetype"),
])
def test_persona_projection_rejects_malformed_registry(tmp_path, content, message):
    root = _git_repo(tmp_path / "homebase")
    (root / "config").mkdir()
    (root / "config" / "personas.yaml").write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        HomeBaseRepositoryAdapter(root).personas()


def test_persona_projection_rejects_oversized_registry(tmp_path):
    root = _git_repo(tmp_path / "homebase")
    (root / "config").mkdir()
    (root / "config" / "personas.yaml").write_text("#" + ("x" * 256_001), encoding="utf-8")
    with pytest.raises(ValueError, match="exceeds adapter limit"):
        HomeBaseRepositoryAdapter(root).personas()


def test_conference_server_selects_bounded_roles_and_stages_exact_evidence(tmp_path, monkeypatch):
    runtime, client, node = _conference_runtime(tmp_path, monkeypatch)
    response = client.post("/api/bbc/v1/room-conferences", json={
        "room_id": "research",
        "objective": "Assess S2-E1 evidence, blockers, and the next safe action.",
        "repository_id": "obsidian-phd",
        "work_node_id": node.id,
        "max_visitors": 2,
    })
    assert response.status_code == 201, response.text
    conference = response.json()
    assert conference["state"] == "completed" and conference["version"] == 3
    assert conference["participant_ids"][0] == "aoteru"
    assert 1 <= len(conference["visitor_ids"]) <= 2
    assert set(conference["visitor_ids"]).issubset(set(conference["participant_ids"]))
    assert len(conference["participants"]) <= 4
    assert len({item["role"] for item in conference["participants"]}) == len(conference["participants"])
    assert all(len(item["output_contract"]) <= 300 for item in conference["participants"])
    assert all(len(item["findings"]) <= 2 for item in conference["contributions"])
    assert conference["synthesis"]["disagreements"]
    assert conference["synthesis"]["uncertainty"]
    assert conference["synthesis"]["actions_executed"] is False
    assert len(conference["synthesis"]["provenance"]) == len(set(conference["synthesis"]["provenance"]))

    packet = runtime.store.get_entity("retrieval_packet", conference["retrieval_packet_id"])
    assert packet["repository_id"] == "obsidian-phd"
    assert packet["token_estimate"] <= 4096
    assert "S2-E1 physical acquisition" in packet["evidence"][0]
    pointer = runtime.store.get_entity("memory_pointer", packet["pointer_ids"][0])
    assert pointer["repository_id"] == "obsidian-phd"
    assert pointer["sensitivity"] == "research"

    capability_ids = [item.capability_id for item in runtime.store.list_audit(limit=1000)]
    assert "bbc.repository.inspect" in capability_ids
    assert "bbc.room_conference.execute" in capability_ids
    events = [
        item.event_type for item in runtime.store.list_events(limit=1000)
        if item.entity_type == "room_conference" and item.entity_id == conference["id"]
    ]
    assert events == [
        "room_conference.planned", "room_conference.started", "room_conference.completed",
    ]
    assert all(runtime.store.verify_event_chains().values())
    assert client.get(f"/api/bbc/v1/room-conferences/{conference['id']}").json() == conference


def test_conference_request_cannot_choose_personas_or_cross_boundaries(tmp_path, monkeypatch):
    _runtime, client, node = _conference_runtime(tmp_path, monkeypatch)
    injected = client.post("/api/bbc/v1/room-conferences", json={
        "room_id": "research",
        "objective": "Inspect S2-E1",
        "participant_ids": ["attacker"],
    })
    assert injected.status_code == 422
    assert client.patch("/api/bbc/v1/room-conferences/00000000-0000-4000-8000-000000000000", json={}).status_code == 405
    assert client.post("/api/bbc/v1/room-conferences", json={
        "room_id": "research", "objective": "Inspect S2-E1",
        "repository_id": "obsidian-phd",
    }).status_code == 400
    assert client.post("/api/bbc/v1/room-conferences", json={
        "room_id": "research", "objective": "Inspect S2-E1",
        "repository_id": "misumi-homebase", "work_node_id": node.id,
    }).status_code == 404
    assert client.post("/api/bbc/v1/room-conferences", json={
        "room_id": "bridge", "objective": "Run outside the active room",
    }).status_code == 400


def test_conference_requires_write_and_invoke_scopes(tmp_path, monkeypatch):
    runtime, _client, node = _conference_runtime(tmp_path, monkeypatch)
    app = FastAPI()

    @app.middleware("http")
    async def write_only_token(request, call_next):
        request.state.api_token = True
        request.state.api_token_owner = "write-only"
        request.state.api_token_scopes = ["bbc:write"]
        return await call_next(request)

    app.include_router(setup_bbc_routes(runtime))
    response = TestClient(app).post("/api/bbc/v1/room-conferences", json={
        "room_id": "research", "objective": "Inspect S2-E1",
        "repository_id": "obsidian-phd", "work_node_id": node.id,
    })
    assert response.status_code == 403
    assert runtime.room_conferences(room_id="research") == []


def test_conference_dependency_failure_is_visible_and_never_claims_action(tmp_path, monkeypatch):
    runtime, client, node = _conference_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(
        runtime,
        "_stage_conference_memory",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("inspection unavailable")),
    )
    response = client.post("/api/bbc/v1/room-conferences", json={
        "room_id": "research", "objective": "Inspect S2-E1",
        "repository_id": "obsidian-phd", "work_node_id": node.id,
    })
    assert response.status_code == 409
    conferences = runtime.room_conferences(room_id="research")
    failed = conferences[-1]
    assert failed.state == "failed"
    assert "inspection unavailable" in failed.failure_reason
    assert failed.synthesis is None and failed.completed_at is None
    assert runtime.store.list_entities("memory_pointer") == []
    assert runtime.store.list_entities("retrieval_packet") == []
    capability_ids = [item.capability_id for item in runtime.store.list_audit(limit=1000)]
    assert "bbc.room_conference.fail" in capability_ids
    assert "bbc.room_conference.execute" not in capability_ids


def test_conference_completion_rolls_back_memory_state_and_audit_together(tmp_path, monkeypatch):
    runtime, client, node = _conference_runtime(tmp_path, monkeypatch)
    original = runtime.store._append_audit_in_transaction

    def fail_execute(*args, **kwargs):
        if kwargs.get("capability_id") == "bbc.room_conference.execute":
            raise RuntimeError("execute audit unavailable")
        return original(*args, **kwargs)

    monkeypatch.setattr(runtime.store, "_append_audit_in_transaction", fail_execute)
    response = client.post("/api/bbc/v1/room-conferences", json={
        "room_id": "research", "objective": "Inspect S2-E1",
        "repository_id": "obsidian-phd", "work_node_id": node.id,
    })
    assert response.status_code == 409
    failed = runtime.room_conferences(room_id="research")[-1]
    assert failed.state == "failed" and failed.completed_at is None
    assert runtime.store.list_entities("memory_pointer") == []
    assert runtime.store.list_entities("retrieval_packet") == []
    assert not any(
        item.event_type == "room_conference.completed"
        for item in runtime.store.list_events(limit=1000)
    )
    assert not any(
        item.capability_id == "bbc.room_conference.execute"
        for item in runtime.store.list_audit(limit=1000)
    )
    assert all(runtime.store.verify_event_chains().values())

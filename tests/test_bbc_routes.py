from pathlib import Path
import sqlite3
import subprocess

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from routes.bbc_routes import setup_bbc_routes
from src.bbc.adapters import (
    HomeBaseRepositoryAdapter,
    ObsidianPhDRepositoryAdapter,
    OdysseusRepositoryAdapter,
    RepositoryAdapterRegistry,
)
from src.bbc.auth import bbc_caller_grants, require_bbc_access
from src.bbc.runtime import BBCRuntime
from src.bbc.store import BBCStateStore, StateConflict


def runtime_fixture(tmp_path: Path) -> BBCRuntime:
    roots = [tmp_path / name for name in ("odysseus", "homebase", "vault")]
    for root in roots:
        subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
    (roots[0] / "ROADMAP.md").write_text("# Roadmap\n\n## Runtime\n- Live node\n", encoding="utf-8")
    (roots[1] / "agent-tasks" / "inbox").mkdir(parents=True)
    (roots[1] / "agent-tasks" / "inbox" / "task.md").write_text("---\nstatus: open\n---\n# Home task\n", encoding="utf-8")
    (roots[2] / "10-inbox").mkdir()
    (roots[2] / "10-inbox" / "research.md").write_text("---\nartifact_type: work-item\nstatus: open\n---\n# Research task\n", encoding="utf-8")
    adapters = RepositoryAdapterRegistry((
        OdysseusRepositoryAdapter(roots[0]), HomeBaseRepositoryAdapter(roots[1]), ObsidianPhDRepositoryAdapter(roots[2]),
    ))
    return BBCRuntime(store=BBCStateStore(tmp_path / "bbc.db"), adapters=adapters)


def test_versioned_routes_expose_live_data_and_navigation_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    app = FastAPI()
    runtime = runtime_fixture(tmp_path)
    app.include_router(setup_bbc_routes(runtime))
    client = TestClient(app)

    schemas = client.get("/api/bbc/v1/schemas")
    assert schemas.status_code == 200
    assert schemas.json()["schema_version"] == 1
    assert "WorkNode" in schemas.json()["models"]

    work = client.get("/api/bbc/v1/repositories/odysseus/work-nodes")
    assert work.status_code == 200
    assert work.json()["nodes"][0]["title"] == "Live node"
    assert work.json()["nodes"][0]["available_actions"] == [{
        "id": "inspect-source",
        "label": "Inspect authoritative source",
        "capability_id": "bbc.repository.inspect",
        "approval_class": "automatic",
        "read_only": True,
    }]
    assert runtime.store.list_entities("work_node") == []

    ingested = client.post("/api/bbc/v1/repositories/odysseus/refresh")
    assert ingested.status_code == 200
    assert ingested.json()["nodes"][0]["title"] == "Live node"
    assert runtime.store.list_entities("work_node")[0]["title"] == "Live node"

    navigation = client.post("/api/bbc/v1/navigation-transactions", json={
        "persona_id": "aoteru", "origin": "bridge", "destination": "research",
        "path": [], "duration_ms": 900,
    })
    assert navigation.status_code == 201
    assert navigation.json()["state"] == "planned"
    assert navigation.json()["path"] == ["bridge", "research"]
    audit = client.get("/api/bbc/v1/audit").json()["events"]
    assert audit[-1]["capability_id"] == "bbc.navigation.plan"


def test_capability_route_returns_real_failure_and_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    app = FastAPI()
    runtime = runtime_fixture(tmp_path)
    app.include_router(setup_bbc_routes(runtime))
    client = TestClient(app)
    response = client.post(
        "/api/bbc/v1/capabilities/bbc.repository.inspect/invoke",
        json={"inputs": {"repository_id": "unknown"}},
    )
    assert response.status_code == 404
    events = client.get("/api/bbc/v1/audit").json()["events"]
    assert events[-1]["result"] == "failed"


def test_bearer_tokens_are_scope_checked_at_route_boundary():
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("127.0.0.1", 1), "app": FastAPI()}
    request = Request(scope)
    request.state.api_token = True
    request.state.api_token_owner = "owner"
    request.state.api_token_scopes = ["bbc:read"]
    assert require_bbc_access(request, "read") == "owner"
    try:
        require_bbc_access(request, "invoke")
    except Exception as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("read-only bearer token unexpectedly gained invoke access")


def test_bearer_invoke_scope_derives_capability_grant_without_bypassing_scope_gate():
    scope = {"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("127.0.0.1", 1), "app": FastAPI()}
    request = Request(scope)
    request.state.api_token = True
    request.state.api_token_owner = "owner"
    request.state.api_token_scopes = ["bbc:invoke"]
    assert require_bbc_access(request, "invoke") == "owner"
    assert "repository:read" in bbc_caller_grants(request)
    try:
        require_bbc_access(request, "write")
    except Exception as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("invoke-only bearer token unexpectedly gained write access")


def test_unknown_repository_never_accepts_a_client_root(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    app = FastAPI()
    app.include_router(setup_bbc_routes(runtime_fixture(tmp_path)))
    client = TestClient(app)
    response = client.get("/api/bbc/v1/repositories/C:%5Csecrets/work-nodes")
    assert response.status_code in {404, 405}


def test_removed_source_is_archived_with_lineage_and_available_only_in_history(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    runtime = runtime_fixture(tmp_path)
    app = FastAPI()
    app.include_router(setup_bbc_routes(runtime))
    client = TestClient(app)
    first = client.post("/api/bbc/v1/repositories/odysseus/refresh").json()["nodes"]
    assert len(first) == 1
    (tmp_path / "odysseus" / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    assert client.get("/api/bbc/v1/repositories/odysseus/work-nodes").json()["nodes"] == []
    assert client.post("/api/bbc/v1/repositories/odysseus/refresh").status_code == 200
    assert client.get("/api/bbc/v1/repositories/odysseus/work-nodes").json()["nodes"] == []
    history = client.get("/api/bbc/v1/repositories/odysseus/work-nodes?include_archived=true").json()["nodes"]
    assert len(history) == 1
    assert history[0]["archived"] and history[0]["state"] == "archived"
    assert history[0]["lineage"][0].startswith("source-removed:")


def test_repository_gets_are_read_only_and_refresh_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    runtime = runtime_fixture(tmp_path)
    app = FastAPI()
    app.include_router(setup_bbc_routes(runtime))
    client = TestClient(app)
    before = runtime.store.latest_event_sequence()

    assert client.get("/api/bbc/v1/repositories/odysseus").status_code == 200
    assert client.get("/api/bbc/v1/repositories/odysseus/work-nodes").status_code == 200
    assert client.get(
        "/api/bbc/v1/repositories/odysseus/work-nodes?include_archived=true"
    ).status_code == 200
    assert runtime.store.latest_event_sequence() == before

    assert client.post("/api/bbc/v1/repositories/odysseus/refresh").status_code == 200
    assert runtime.store.latest_event_sequence() > before


def test_health_reports_canonical_state_tampering(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    runtime = runtime_fixture(tmp_path)
    with sqlite3.connect(runtime.store.path) as connection:
        connection.execute(
            "UPDATE canonical_state SET state_json = '{}' "
            "WHERE entity_type = 'ship' AND entity_id = 'bbc-odysseus'"
        )
    app = FastAPI()
    app.include_router(setup_bbc_routes(runtime))

    response = TestClient(app).get("/api/bbc/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    database = response.json()["checks"]["database"]
    assert database["ok"] is False
    assert database["canonical_state"]["hashes"] is False


def test_paused_nodes_remain_visible_in_normal_results(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    runtime = runtime_fixture(tmp_path)
    task = tmp_path / "homebase" / "agent-tasks" / "inbox" / "task.md"
    task.write_text("---\nstatus: paused\n---\n# Paused home task\n", encoding="utf-8")
    app = FastAPI()
    app.include_router(setup_bbc_routes(runtime))
    response = TestClient(app).get("/api/bbc/v1/repositories/misumi-homebase/work-nodes")
    assert response.status_code == 200
    assert response.json()["nodes"][0]["state"] == "paused"


def test_state_event_contract_exposes_latest_sequence_not_first_page_event(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    runtime = runtime_fixture(tmp_path)
    runtime.store.upsert_entity("example", "one", {"value": 1})
    runtime.store.upsert_entity("example", "two", {"value": 2})
    app = FastAPI()
    app.include_router(setup_bbc_routes(runtime))
    payload = TestClient(app).get("/api/bbc/v1/state/events?limit=1").json()
    assert len(payload["events"]) == 1
    assert payload["latest_sequence"] == runtime.store.latest_event_sequence()
    assert payload["latest_sequence"] > payload["events"][0]["sequence"]


def test_queue_move_updates_one_stored_node_with_retained_provenance_and_state_event(tmp_path):
    runtime = runtime_fixture(tmp_path)
    first = runtime.refresh_repository("misumi-homebase").nodes[0]
    source = tmp_path / "homebase" / "agent-tasks" / "inbox" / "task.md"
    destination = tmp_path / "homebase" / "agent-tasks" / "done" / "task.md"
    destination.parent.mkdir()
    source.rename(destination)
    second = runtime.refresh_repository("misumi-homebase").nodes[0]
    stored = [
        item for item in runtime.store.list_entities("work_node")
        if item["repository_id"] == "misumi-homebase"
    ]
    assert first.id == second.id
    assert len(stored) == 1
    assert stored[0]["state"] == "completed"
    assert {item["path"] for item in stored[0]["provenance"]} == {
        "agent-tasks/inbox/task.md",
        "agent-tasks/done/task.md",
    }
    transitions = [
        event for event in runtime.store.list_events()
        if event.entity_type == "work_node" and event.entity_id == first.id
    ]
    assert [event.payload["state"]["state"] for event in transitions] == ["active", "completed"]


def _navigation_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    runtime = runtime_fixture(tmp_path)
    app = FastAPI()
    app.include_router(setup_bbc_routes(runtime))
    return runtime, TestClient(app)


def test_navigation_lifecycle_is_versioned_atomic_and_persistent(tmp_path, monkeypatch):
    runtime, client = _navigation_client(tmp_path, monkeypatch)
    planned_response = client.post("/api/bbc/v1/navigation-transactions", json={
        "persona_id": "kurisu", "origin": "bridge", "destination": "archive",
        "path": [], "duration_ms": 1200,
    })
    assert planned_response.status_code == 201
    planned = planned_response.json()
    assert planned["actor"] != planned["persona_id"]
    assert planned["path"] == ["bridge", "observatory", "archive"]
    assert planned["version"] == 1 and planned["started_at"] is None
    url = f"/api/bbc/v1/navigation-transactions/{planned['id']}"

    started_response = client.patch(url, json={"state": "in_progress", "expected_version": 1})
    assert started_response.status_code == 200
    started = started_response.json()
    assert started["version"] == 2 and started["started_at"]
    assert started["completed_at"] is None
    location = client.get("/api/bbc/v1/persona-locations/kurisu").json()
    assert location["room_id"] == "bridge"
    assert location["navigation_transaction_id"] == planned["id"]
    assert client.get("/api/bbc/v1/ship").json()["active_room_id"] == "bridge"

    completed_response = client.patch(url, json={"state": "completed", "expected_version": 2})
    assert completed_response.status_code == 200
    completed = completed_response.json()
    assert completed["version"] == 3 and completed["completed_at"]
    assert completed["updated_at"] != planned["updated_at"]
    retry = client.patch(url, json={"state": "completed", "expected_version": 2})
    assert retry.status_code == 200
    assert retry.json() == completed
    assert client.patch(url, json={"state": "completed", "expected_version": 1}).status_code == 409
    location = client.get("/api/bbc/v1/persona-locations/kurisu").json()
    assert location["room_id"] == "archive" and location["navigation_transaction_id"] is None
    assert client.get("/api/bbc/v1/ship").json()["active_room_id"] == "archive"
    assert client.get("/api/bbc/v1/persona-locations").json()["locations"] == [location]

    transition_events = [
        event.event_type for event in runtime.store.list_events(limit=1000)
        if event.entity_type == "navigation_transaction" and event.entity_id == planned["id"]
    ]
    assert transition_events == ["navigation.planned", "navigation.started", "navigation.completed"]
    completion_audit = runtime.store.list_audit(limit=1000)[-1]
    assert completion_audit.capability_id == "bbc.navigation.complete"
    assert {
        f"state://navigation_transaction/{planned['id']}",
        "state://persona_location/kurisu",
        "state://ship/bbc-odysseus",
    }.issubset(set(completion_audit.evidence))

    rebuilt = BBCRuntime(store=BBCStateStore(runtime.store.path), adapters=runtime.adapters)
    assert rebuilt.ship().active_room_id == "archive"
    assert rebuilt.persona_location("kurisu").room_id == "archive"


@pytest.mark.parametrize("payload", [
    {"persona_id": "aoteru", "origin": "bridge", "destination": "unknown", "path": []},
    {"persona_id": "aoteru", "origin": "bridge", "destination": "bridge", "path": []},
    {"persona_id": "aoteru", "origin": "bridge", "destination": "archive", "path": ["bridge", "archive"]},
    {"persona_id": "aoteru", "origin": "bridge", "destination": "archive", "path": ["bridge", "observatory", "bridge", "archive"]},
    {"persona_id": "aoteru", "origin": "bridge", "destination": "archive", "path": ["observatory", "archive"]},
])
def test_navigation_rejects_unknown_noop_and_invalid_paths(tmp_path, monkeypatch, payload):
    _runtime, client = _navigation_client(tmp_path, monkeypatch)
    response = client.post("/api/bbc/v1/navigation-transactions", json={**payload, "duration_ms": 10})
    assert response.status_code == 400


def test_navigation_stale_version_interruption_and_terminal_immutability(tmp_path, monkeypatch):
    runtime, client = _navigation_client(tmp_path, monkeypatch)
    planned = client.post("/api/bbc/v1/navigation-transactions", json={
        "persona_id": "aoteru", "origin": "bridge", "destination": "research",
        "path": [], "duration_ms": 0,
    }).json()
    url = f"/api/bbc/v1/navigation-transactions/{planned['id']}"
    assert client.patch(url, json={"state": "in_progress", "expected_version": 2}).status_code == 409
    assert runtime.navigation_transaction(planned["id"]).state == "planned"
    assert client.patch(url, json={"state": "interrupted", "expected_version": 1}).status_code == 400

    interrupted = client.patch(url, json={
        "state": "interrupted", "expected_version": 1,
        "interruption_reason": "operator changed destination",
    })
    assert interrupted.status_code == 200
    assert interrupted.json()["version"] == 2 and interrupted.json()["interrupted_at"]
    event_count = runtime.store.latest_event_sequence()
    replay = client.patch(url, json={
        "state": "interrupted", "expected_version": 2,
        "interruption_reason": "operator changed destination",
    })
    assert replay.status_code == 200 and replay.json()["version"] == 2
    assert runtime.store.latest_event_sequence() == event_count
    assert client.patch(url, json={"state": "in_progress", "expected_version": 2}).status_code == 409
    stale_replay = client.patch(url, json={
        "state": "interrupted", "expected_version": 1,
        "interruption_reason": "operator changed destination",
    })
    assert stale_replay.status_code == 200 and stale_replay.json()["version"] == 2
    assert runtime.store.latest_event_sequence() == event_count


def test_navigation_optimistic_conflict_and_atomic_rollback(tmp_path, monkeypatch):
    runtime = runtime_fixture(tmp_path)
    second_runtime = BBCRuntime(store=BBCStateStore(runtime.store.path), adapters=runtime.adapters)
    planned = runtime.create_navigation(
        actor="operator", persona_id="aoteru", origin="bridge", destination="research",
        path=[], duration_ms=100,
    )
    started = runtime.transition_navigation(
        planned.id, "in_progress", actor="operator", expected_version=1,
    )
    with pytest.raises(StateConflict, match="stale navigation version"):
        second_runtime.transition_navigation(
            planned.id, "interrupted", actor="operator", expected_version=1,
            interruption_reason="stale client",
        )

    event_count = runtime.store.latest_event_sequence()
    audit_count = len(runtime.store.list_audit(limit=1000))
    monkeypatch.setattr(
        runtime.store, "_append_audit_in_transaction",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        runtime.transition_navigation(
            planned.id, "completed", actor="operator", expected_version=started.version,
        )
    assert runtime.navigation_transaction(planned.id).state == "in_progress"
    assert runtime.persona_location("aoteru").room_id == "bridge"
    assert runtime.ship().active_room_id == "bridge"
    assert runtime.store.latest_event_sequence() == event_count
    assert len(runtime.store.list_audit(limit=1000)) == audit_count


def test_global_navigation_intent_resolves_rooms_repositories_and_real_work(tmp_path, monkeypatch):
    runtime, client = _navigation_client(tmp_path, monkeypatch)
    research = tmp_path / "vault" / "10-inbox" / "research.md"
    research.write_text(
        "---\nartifact_type: work-item\nstatus: open\n---\n# S2-E1 perception hardware setup\n",
        encoding="utf-8",
    )
    room = client.post("/api/bbc/v1/navigation-intents", json={
        "text": "go to enginering", "source": "voice",
    })
    assert room.status_code == 200
    assert room.json()["status"] == "resolved"
    assert room.json()["arrival_room_id"] == "engineering"

    repository = client.post("/api/bbc/v1/navigation-intents", json={"text": "open the PhD system"})
    assert repository.json()["target"]["id"] == "obsidian-phd"
    assert repository.json()["arrival_room_id"] == "observatory"

    work = client.post("/api/bbc/v1/navigation-intents", json={"text": "plot a course to S2-E1"})
    assert work.json()["status"] == "resolved"
    assert work.json()["target"]["repository_id"] == "obsidian-phd"
    assert work.json()["arrival_room_id"] == "research"
    assert client.post("/api/bbc/v1/navigation-intents", json={"text": "hello there"}).json()["status"] == "unsupported"
    assert client.post("/api/bbc/v1/navigation-intents", json={
        "text": "inspect this node", "context": {"untrusted": "value"},
    }).status_code == 422

    planned = runtime.create_navigation(
        actor="operator", persona_id="kurisu", origin="bridge", destination="archive",
        path=[], duration_ms=0,
    )
    runtime.transition_navigation(planned.id, "in_progress", actor="operator", expected_version=1)
    runtime.transition_navigation(planned.id, "completed", actor="operator", expected_version=2)
    visit = client.post("/api/bbc/v1/navigation-intents", json={"text": "visit Kurisu"}).json()
    assert visit["status"] == "resolved" and visit["arrival_room_id"] == "archive"

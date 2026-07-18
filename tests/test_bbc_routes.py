from pathlib import Path
import subprocess

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
from src.bbc.store import BBCStateStore


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

    navigation = client.post("/api/bbc/v1/navigation-transactions", json={
        "origin": "bridge", "destination": "odysseus:node", "path": ["bridge", "observatory"], "duration_ms": 900,
    })
    assert navigation.status_code == 201
    assert navigation.json()["state"] == "planned"
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
    first = client.get("/api/bbc/v1/repositories/odysseus/work-nodes").json()["nodes"]
    assert len(first) == 1
    (tmp_path / "odysseus" / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    assert client.get("/api/bbc/v1/repositories/odysseus/work-nodes").json()["nodes"] == []
    history = client.get("/api/bbc/v1/repositories/odysseus/work-nodes?include_archived=true").json()["nodes"]
    assert len(history) == 1
    assert history[0]["archived"] and history[0]["state"] == "archived"
    assert history[0]["lineage"][0].startswith("source-removed:")


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

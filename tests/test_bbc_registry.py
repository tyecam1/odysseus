import json
from pathlib import Path
import subprocess

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.bbc_routes import setup_bbc_routes
from src.bbc.adapters import (
    HomeBaseRepositoryAdapter,
    ObsidianPhDRepositoryAdapter,
    OdysseusRepositoryAdapter,
    RepositoryAdapterRegistry,
)
from src.bbc.capabilities import CapabilityRegistry
from src.bbc.models import Capability, CapabilityHealth
from src.bbc.registry import build_universal_registry
from src.bbc.runtime import BBCRuntime
from src.bbc.store import BBCStateStore


class FakeSkills:
    def __init__(self):
        self.rows = [{
            "name": "research-check",
            "description": "Check research evidence",
            "owner": "operator",
            "status": "published",
            "version": "1.2.0",
            "category": "research",
            "requires_toolsets": ["repository:read"],
            "procedure": ["Read the authoritative source.", "Report uncertainty."],
            "verification": ["Cite the source."],
        }]

    def load_all(self):
        return list(self.rows)


class FakeMcp:
    def get_all_tools(self, disabled_map=None):
        disabled_map = disabled_map or {}
        return [{
            "server_id": "notes",
            "server_name": "Notes MCP",
            "name": "inspect_note",
            "qualified_name": "mcp__notes__inspect_note",
            "description": "Inspect one note",
            "input_schema": {"type": "object", "properties": {"id": {"type": "string"}}},
            "is_disabled": "inspect_note" in disabled_map.get("notes", set()),
        }]

    def get_server_status(self, server_id):
        return {"status": "connected"}


class FakeMemoryProvider:
    provider_id = "native"
    display_name = "Odysseus native memory"
    enabled = True
    memory_vector = None

    def get_tool_schemas(self):
        return [{"name": "recall_memory", "input_schema": {"type": "object"}}]


class FakeMemoryRegistry:
    def all(self):
        return [FakeMemoryProvider()]


def database_snapshot():
    return {
        "mcp_servers": [{
            "id": "notes", "name": "Notes MCP", "transport": "stdio",
            "is_enabled": True, "disabled_tools": None,
        }],
        "automations": [{
            "id": "morning", "name": "Morning brief", "task_type": "action",
            "action": "daily_brief", "schedule": "daily", "trigger_type": "schedule",
            "trigger_event": None, "status": "active", "owner": "operator",
            "model": None, "output_target": "session",
        }],
        "model_runtimes": [{
            "id": "local", "name": "Local Ollama", "is_enabled": True,
            "cached_models": json.dumps(["qwen3:8b"]), "pinned_models": None,
            "model_type": "llm", "endpoint_kind": "local",
            "model_refresh_mode": "auto", "supports_tools": True, "owner": None,
        }],
    }


def capability_registry():
    registry = CapabilityRegistry()
    registry.register(Capability(
        id="example.inspect", version="1.0.0", name="Example inspection",
        description="Inspect an authorised target", owner="odysseus",
        scope=["repository", "read-only"], permissions=["repository:read"],
        health=CapabilityHealth(state="healthy"), context_cost=120,
        provenance=["tests/test_bbc_registry.py"], licence="AGPL-3.0-or-later",
        inputs_schema={"type": "object"}, outputs_schema={"type": "object"},
        instructions="Inspect only the selected target.",
    ))
    return registry


def projected_registry(tmp_path: Path):
    (tmp_path / "integrations.json").write_text(json.dumps([{
        "id": "rss", "name": "RSS", "enabled": True,
        "description": "Read household feeds", "preset": "miniflux",
        "auth_type": "header", "api_key": "encrypted-secret-material",
        "base_url": "https://private.example.invalid",
    }]), encoding="utf-8")
    return build_universal_registry(
        app_root=tmp_path,
        data_dir=tmp_path,
        capabilities=capability_registry(),
        skills_manager=FakeSkills(),
        mcp_manager=FakeMcp(),
        memory_provider_registry=FakeMemoryRegistry(),
        database_reader=database_snapshot,
        task_definitions={
            "daily_brief": "Build a bounded morning digest",
            "run_local": "Run a script on the host",
        },
    )


def test_projection_covers_all_runtime_registry_kinds_and_is_live(tmp_path):
    registry = projected_registry(tmp_path)
    kinds = {entry.kind for entry in registry.search(limit=200)}
    assert kinds == {
        "capability", "skill", "mcp_tool", "task_definition", "automation",
        "memory_system", "model_runtime", "connector",
    }
    assert registry.status()["ok"]

    registry.skills_manager.rows.append({
        "name": "new-live-skill", "description": "Added after first projection",
        "owner": "operator", "status": "draft",
    })
    assert registry.search("new-live-skill")[0].id == "skill:operator:new-live-skill"


def test_search_is_compact_and_detail_loads_schema_and_instructions_lazily(tmp_path):
    registry = projected_registry(tmp_path)
    skill_summary = registry.search("research-check")[0].model_dump()
    assert "instructions" not in skill_summary
    assert "schema" not in skill_summary
    assert "metadata" not in skill_summary
    assert skill_summary["availability"]["state"] == "available"
    assert skill_summary["risk"]["permissions"] == ["repository:read"]

    skill_detail = registry.detail("skill:operator:research-check")
    assert "Read the authoritative source" in skill_detail.instructions
    mcp_detail = registry.detail("mcp:notes:inspect_note")
    assert mcp_detail.definition_schema["properties"]["id"]["type"] == "string"
    assert mcp_detail.risk.level == "low"


def test_projection_never_returns_connector_secrets_or_endpoint_locations(tmp_path):
    registry = projected_registry(tmp_path)
    rendered = registry.detail("connector:rss").model_dump_json()
    assert "encrypted-secret-material" not in rendered
    assert "private.example.invalid" not in rendered
    assert '"credentials_configured":true' in rendered


def test_risk_and_availability_are_machine_readable(tmp_path):
    registry = projected_registry(tmp_path)
    dangerous = registry.detail("task-definition:run_local")
    assert dangerous.risk.level == "high"
    assert "host:write" in dangerous.risk.permissions
    automation = registry.detail("automation:morning")
    assert automation.availability.state == "available"
    assert automation.risk.level == "medium"
    model = registry.detail("model-runtime:local")
    assert model.risk.level == "low"
    assert model.metadata["models"] == ["qwen3:8b"]


def test_registry_routes_preserve_compact_summary_and_support_kind_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    root = tmp_path / "repo"
    homebase = tmp_path / "homebase"
    vault = tmp_path / "vault"
    subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "init", "--quiet", str(homebase)], check=True, capture_output=True)
    subprocess.run(["git", "init", "--quiet", str(vault)], check=True, capture_output=True)
    (root / "ROADMAP.md").write_text("# Runtime\n", encoding="utf-8")
    registry = projected_registry(tmp_path)
    runtime = BBCRuntime(
        store=BBCStateStore(tmp_path / "bbc.db"),
        adapters=RepositoryAdapterRegistry((
            OdysseusRepositoryAdapter(root),
            HomeBaseRepositoryAdapter(homebase),
            ObsidianPhDRepositoryAdapter(vault),
        )),
        registry=registry,
    )
    app = FastAPI()
    app.include_router(setup_bbc_routes(runtime))
    client = TestClient(app)

    response = client.get("/api/bbc/v1/registry?kind=skill")
    assert response.status_code == 200
    payload = response.json()
    assert payload["detail_loaded"] is False
    assert {entry["kind"] for entry in payload["entries"]} == {"skill"}
    assert "instructions" not in payload["entries"][0]
    assert payload["counts"]["connector"] == 1

    detail = client.get("/api/bbc/v1/registry/skill:operator:research-check")
    assert detail.status_code == 200
    assert "Read the authoritative source" in detail.json()["instructions"]

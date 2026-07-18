from pathlib import Path
import subprocess

import pytest

from src.bbc.adapters import (
    HomeBaseRepositoryAdapter,
    ObsidianPhDRepositoryAdapter,
    OdysseusRepositoryAdapter,
    RepositoryAdapterRegistry,
)
from src.bbc.capabilities import CapabilityRegistry, build_capability_registry
from src.bbc.models import Capability, CapabilityHealth
from src.bbc.runtime import BBCRuntime
from src.bbc.store import BBCStateStore


def configured_adapters(tmp_path: Path) -> RepositoryAdapterRegistry:
    odysseus = tmp_path / "odysseus"
    homebase = tmp_path / "homebase"
    vault = tmp_path / "vault"
    for root in (odysseus, homebase, vault):
        subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
    (odysseus / "ROADMAP.md").write_text("# Roadmap\n\n## Runtime\n- Inspect this runtime\n", encoding="utf-8")
    tasks = homebase / "agent-tasks" / "inbox"
    tasks.mkdir(parents=True)
    (tasks / "household.md").write_text("---\nstatus: open\n---\n# Inspect household runtime\n", encoding="utf-8")
    inbox = vault / "10-inbox"
    inbox.mkdir()
    (inbox / "research.md").write_text("---\nartifact_type: work-item\nstatus: open\n---\n# Inspect research runtime\n", encoding="utf-8")
    return RepositoryAdapterRegistry((
        OdysseusRepositoryAdapter(odysseus),
        HomeBaseRepositoryAdapter(homebase),
        ObsidianPhDRepositoryAdapter(vault),
    ))


def test_search_is_compact_and_detail_is_lazy(tmp_path):
    registry = build_capability_registry(configured_adapters(tmp_path))
    summary = registry.search("repository")[0].model_dump()
    assert summary["id"] == "bbc.repository.inspect"
    assert "inputs_schema" not in summary
    assert "instructions" not in summary
    detail = registry.detail("bbc.repository.inspect")
    assert detail.inputs_schema["properties"]["repository_id"]
    assert set(detail.target_adapters) == {"odysseus", "misumi-homebase", "obsidian-phd"}


def test_registry_deduplicates_identical_records_and_rejects_conflicts():
    registry = CapabilityRegistry()
    capability = Capability(
        id="example.read", version="1", name="Example", description="Read example", owner="odysseus",
        scope=["example"], permissions=["read"], health=CapabilityHealth(state="healthy"), context_cost=1,
        provenance=["test"], licence="AGPL-3.0-or-later", inputs_schema={}, outputs_schema={},
    )
    assert registry.register(capability)
    assert not registry.register(capability)
    with pytest.raises(ValueError, match="conflicting duplicate"):
        registry.register(capability.model_copy(update={"description": "Different"}))


@pytest.mark.parametrize("repository_id", ["odysseus", "misumi-homebase", "obsidian-phd"])
def test_safe_shared_inspection_runs_against_every_adapter_and_audits(tmp_path, repository_id):
    adapters = configured_adapters(tmp_path)
    runtime = BBCRuntime(store=BBCStateStore(tmp_path / "state.db"), adapters=adapters)
    response = runtime.invoke_capability(
        "bbc.repository.inspect",
        {"repository_id": repository_id, "query": "runtime", "limit": 5},
        actor="tester",
        caller_grants={"repository:read"},
    )
    assert response["result"]["repository_id"] == repository_id
    assert response["result"]["mode"] == "search"
    assert response["result"]["hits"]
    assert response["audit"]["result"] == "succeeded"
    assert response["audit"]["rollback_ref"] == "not-required:read-only"


def test_failed_inspection_emits_failure_not_fake_success(tmp_path):
    runtime = BBCRuntime(store=BBCStateStore(tmp_path / "state.db"), adapters=configured_adapters(tmp_path))
    with pytest.raises(KeyError, match="unknown or unauthorised"):
        runtime.invoke_capability(
            "bbc.repository.inspect", {"repository_id": "other"}, actor="tester",
            caller_grants={"repository:read"},
        )
    audits = runtime.store.list_audit()
    assert len(audits) == 1
    assert audits[0].result == "failed"
    assert audits[0].evidence == ["KeyError"]


def test_inspection_redacts_credentials_from_reads_and_search_results(tmp_path):
    runtime = BBCRuntime(store=BBCStateStore(tmp_path / "state.db"), adapters=configured_adapters(tmp_path))
    task = tmp_path / "homebase" / "agent-tasks" / "inbox" / "household.md"
    task.write_text(
        "---\nstatus: open\n---\n# Inspect runtime\npassword: exposed-value\nAPI_KEY=sk-proj-abcdefghijklmnop\n",
        encoding="utf-8",
    )
    read = runtime.invoke_capability(
        "bbc.repository.inspect",
        {"repository_id": "misumi-homebase", "relative_path": "agent-tasks/inbox/household.md"},
        actor="tester",
        caller_grants={"repository:read"},
    )["result"]["text"]
    search = runtime.invoke_capability(
        "bbc.repository.inspect",
        {"repository_id": "misumi-homebase", "query": "password"},
        actor="tester",
        caller_grants={"repository:read"},
    )["result"]["hits"][0]["snippet"]
    assert "exposed-value" not in read + search
    assert "sk-proj" not in read + search
    assert "[REDACTED]" in read + search


def test_capability_permissions_are_enforced_and_denials_are_audited(tmp_path):
    runtime = BBCRuntime(store=BBCStateStore(tmp_path / "state.db"), adapters=configured_adapters(tmp_path))
    with pytest.raises(PermissionError, match="repository:read"):
        runtime.invoke_capability(
            "bbc.repository.inspect",
            {"repository_id": "odysseus"},
            actor="tester",
            caller_grants={"bbc:invoke"},
        )
    assert runtime.store.list_audit()[-1].result == "denied"


def test_adapter_dependent_capability_health_is_truthful(tmp_path):
    adapters = configured_adapters(tmp_path)
    unavailable = ObsidianPhDRepositoryAdapter(tmp_path / "missing", strict=False)
    mixed = RepositoryAdapterRegistry((
        adapters.get("odysseus"), adapters.get("misumi-homebase"), unavailable,
    ))
    detail = build_capability_registry(mixed).detail("bbc.repository.inspect")
    assert detail.health.state == "degraded"
    assert "obsidian-phd" in detail.health.detail


def test_replacement_metadata_rejects_missing_targets_mismatched_overlap_and_cycles():
    registry = CapabilityRegistry()
    common = dict(
        version="1", description="Example", owner="odysseus", scope=["example"],
        permissions=["read"], health=CapabilityHealth(state="healthy"), context_cost=1,
        provenance=["test"], licence="AGPL-3.0-or-later", inputs_schema={}, outputs_schema={},
    )
    with pytest.raises(ValueError, match="replacement target"):
        registry.register(Capability(
            id="old", name="Old", overlap_group="group", replacement_status="replaced",
            replaced_by="missing", **common,
        ))
    registry.register(Capability(id="new", name="New", overlap_group="group", **common))
    with pytest.raises(ValueError, match="overlap_group"):
        registry.register(Capability(
            id="old", name="Old", overlap_group="other", replacement_status="replaced",
            replaced_by="new", **common,
        ))
    # Validate cycles even if persisted registry data is corrupted outside register().
    registry._details["new"] = registry._details["new"].model_copy(update={"replaced_by": "new"})
    with pytest.raises(ValueError, match="cycle"):
        registry.validate()


def test_worknode_fields_are_redacted_before_return_and_persistence(tmp_path):
    adapters = configured_adapters(tmp_path)
    task = tmp_path / "homebase" / "agent-tasks" / "inbox" / "household.md"
    task.write_text(
        "---\ntitle: API key: sk-proj-abcdefghijklmnop\nstatus: open\n"
        "owner: password=owner-secret\nacceptance_evidence: [secret: evidence-secret]\n---\n"
        "# API key: sk-proj-abcdefghijklmnop\n## Objective\npassword: outcome-secret\n"
        "## Next action\naccess_token=action-secret\n",
        encoding="utf-8",
    )
    runtime = BBCRuntime(store=BBCStateStore(tmp_path / "redacted.db"), adapters=adapters)
    node = runtime.refresh_repository("misumi-homebase").nodes[0]
    returned = node.model_dump_json()
    persisted = str(runtime.store.get_entity("work_node", node.id))
    for secret in ("sk-proj", "owner-secret", "evidence-secret", "outcome-secret", "action-secret"):
        assert secret not in returned + persisted
    assert "REDACTED" in returned


def test_repository_search_obeys_aggregate_file_and_byte_budget(tmp_path, monkeypatch):
    import src.bbc.adapters as adapter_module

    adapters = configured_adapters(tmp_path)
    tasks = tmp_path / "homebase" / "agent-tasks" / "inbox"
    for index in range(5):
        (tasks / f"extra-{index}.md").write_text("needle " + ("x" * 80), encoding="utf-8")
    monkeypatch.setattr(adapter_module, "MAX_INSPECTION_FILES", 3)
    monkeypatch.setattr(adapter_module, "MAX_INSPECTION_TOTAL_BYTES", 260)
    result = adapters.get("misumi-homebase").inspect(query="needle", limit=50)
    budget = result["inspection"]
    assert budget["files_scanned"] <= 3
    assert budget["bytes_scanned"] <= 260
    assert budget["truncated"]

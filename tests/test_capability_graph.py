from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from src.capability_graph.adapters.base import (
    AdapterResult,
    SourceAdapter,
    edge_id,
    sha256_file,
    source_identity,
)
from src.capability_graph.adapters.agent_task_adapter import AgentTaskAdapter
from src.capability_graph.adapters.model_policy_adapter import ModelPolicyAdapter
from src.capability_graph.adapters.repo_contract_adapter import RepoContractAdapter
from src.capability_graph.adapters.skill_adapter import SkillAdapter
from src.capability_graph.adapters.yaml_subset import parse_yaml_subset
from src.capability_graph.builder import build_graph
from src.capability_graph.constants import PROVENANCE_FIELDS
from src.capability_graph.errors import (
    AdapterError,
    DuplicateNodeError,
    EvaluationError,
    NoSourcesError,
    ProvenanceError,
    SchemaMismatchError,
    StaleGraphError,
    ValidationError,
)
from src.capability_graph.evaluation import evaluate_cases
from src.capability_graph.freshness import GraphFreshness, check_freshness
from src.capability_graph.model import CapabilityGraph, Edge, Node, Provenance
from src.capability_graph.queries import (
    QUERY_EDGE_TYPES,
    QUERY_NAMES,
    execute_query,
    explain_route,
)
from src.capability_graph.storage import SourceRecord, export_graph, save_graph
from src.capability_graph.validation import validate_graph


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "capability_graph" / "sources"
REAL_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "capability_graph" / "real_obsidian_phd"
REAL_PACKET_ROOT = REAL_FIXTURE_ROOT / "agent-tasks"
HELD_OUT = Path(__file__).parent / "evaluation" / "capability_graph_held_out.json"


def _copy_sources(tmp_path: Path) -> Path:
    root = tmp_path / "sources"
    shutil.copytree(FIXTURE_ROOT, root)
    return root


def _provenance(path: str = "source.md", adapter: str = "test_adapter") -> Provenance:
    return Provenance(
        source_repo="test-repo",
        source_path=path,
        source_revision="revision-1",
        source_sha256=hashlib.sha256(path.encode()).hexdigest(),
        extracted_at="2026-08-02T00:00:00+00:00",
        adapter_name=adapter,
        adapter_version="1.0.0",
    )


def _node(node_id: str, node_type: str, **attributes) -> Node:
    return Node(node_id, node_type, attributes, _provenance())


def _edge(edge_type: str, source: str, target: str, ordinal: int = 0, **attributes) -> Edge:
    return Edge(
        edge_id(edge_type, source, target, ordinal),
        edge_type,
        source,
        target,
        attributes,
        _provenance(),
    )


def test_determinism_two_builds_have_identical_export_bytes(tmp_path):
    root = _copy_sources(tmp_path)
    first_db = tmp_path / "first.db"
    second_db = tmp_path / "second.db"
    first_json = tmp_path / "first.json"
    second_json = tmp_path / "second.json"

    build_graph([root], first_db)
    build_graph([root], second_db)
    export_graph(first_db, first_json)
    export_graph(second_db, second_json)

    assert first_json.read_bytes() == second_json.read_bytes()
    document = json.loads(first_json.read_text(encoding="utf-8"))
    assert "generated_at" not in document
    assert first_json.with_name("first.json.metadata.json").exists()


def test_real_source_determinism_two_builds_have_identical_export_bytes(tmp_path):
    first_db = tmp_path / "real-first.db"
    second_db = tmp_path / "real-second.db"
    first_json = tmp_path / "real-first.json"
    second_json = tmp_path / "real-second.json"

    build_graph([REAL_PACKET_ROOT], first_db)
    build_graph([REAL_PACKET_ROOT], second_db)
    export_graph(first_db, first_json)
    export_graph(second_db, second_json)

    assert first_json.read_bytes() == second_json.read_bytes()


@pytest.mark.parametrize("missing", PROVENANCE_FIELDS)
def test_provenance_completeness_missing_any_field_fails(missing):
    data = _provenance().to_dict()
    data.pop(missing)

    with pytest.raises(ProvenanceError, match="incomplete provenance"):
        Node("node", "action", {}, data).validate()


def test_node_reasoning_text_fields_are_rejected():
    with pytest.raises(ValidationError, match="forbidden reasoning field"):
        Node("node", "action", {"chain_of_thought": "hidden"}, _provenance()).validate()


def test_freshness_change_refuses_query_and_allow_stale_labels_answer(tmp_path):
    root = _copy_sources(tmp_path)
    db = tmp_path / "graph.db"
    build_graph([root], db)
    source = root / "2026-08-02-demo.agent-task.md"
    source.write_text(source.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")

    report = check_freshness(db, [root])
    assert report.freshness is GraphFreshness.STALE
    assert any(item.source_path == "2026-08-02-demo.agent-task.md" and item.status == "changed" for item in report.sources)
    with pytest.raises(TypeError):
        bool(report.freshness)
    with pytest.raises(StaleGraphError, match="stale graph refused"):
        execute_query(db, "what-should-handle", route_id="task-class:demo")

    answer = execute_query(
        db,
        "what-should-handle",
        route_id="task-class:demo",
        allow_stale=True,
    )
    assert answer["freshness"] == "stale"


def test_new_supported_source_marks_graph_stale(tmp_path):
    root = _copy_sources(tmp_path)
    db = tmp_path / "graph.db"
    build_graph([root], db)
    extra = root / "skills" / "extra" / "SKILL.md"
    extra.parent.mkdir(parents=True)
    extra.write_text("---\nname: extra\ndescription: extra skill\n---\n", encoding="utf-8")

    report = check_freshness(db, [root])

    assert report.freshness is GraphFreshness.STALE
    assert any(item.source_path.endswith("skills/extra/SKILL.md") and item.status == "changed" for item in report.sources)


def test_real_source_freshness_detects_changed_packet(tmp_path):
    root = tmp_path / "real-source"
    shutil.copytree(REAL_PACKET_ROOT, root)
    db = tmp_path / "real-graph.db"
    build_graph([root], db)
    packet = root / "done" / "2026-08-02-lab-vault-clone-recovery.agent-task.md"
    packet.write_text(packet.read_text(encoding="utf-8") + "\n<!-- changed -->\n", encoding="utf-8")

    report = check_freshness(db, [root])

    assert report.freshness is GraphFreshness.STALE
    assert any(
        item.source_path.endswith(packet.name) and item.status == "changed"
        for item in report.sources
    )


def test_authority_conflict_reports_both_provenance_records():
    graph = CapabilityGraph()
    allow_provenance = _provenance("allow.md")
    deny_provenance = _provenance("deny.md")
    graph.add_node(Node("actor", "authority", {}, allow_provenance))
    graph.add_node(Node("allow", "permission", {"path": "src/**"}, allow_provenance))
    graph.add_node(Node("deny", "permission", {"path": "src/private/**"}, deny_provenance))
    graph.add_edge(Edge("allow-edge", "may_write", "actor", "allow", {"path": "src/**"}, allow_provenance))
    graph.add_edge(Edge("deny-edge", "forbids", "actor", "deny", {"path": "src/private/**"}, deny_provenance))

    with pytest.raises(ValidationError) as raised:
        validate_graph(graph)

    message = str(raised.value)
    assert "authority conflict" in message
    assert "allow.md" in message
    assert "deny.md" in message
    assert allow_provenance.source_sha256 in message
    assert deny_provenance.source_sha256 in message


def test_routes_to_cycle_fails_build_validation():
    graph = CapabilityGraph()
    graph.extend(
        [_node("route:a", "task_class"), _node("route:b", "task_class")],
        [_edge("routes_to", "route:a", "route:b"), _edge("routes_to", "route:b", "route:a")],
    )

    with pytest.raises(ValidationError, match="routes_to cycle"):
        validate_graph(graph)


def test_escalates_to_cycle_fails_build_validation():
    graph = CapabilityGraph()
    graph.extend(
        [_node("escalation:a", "escalation"), _node("escalation:b", "escalation")],
        [
            _edge("escalates_to", "escalation:a", "escalation:b"),
            _edge("escalates_to", "escalation:b", "escalation:a"),
        ],
    )

    with pytest.raises(ValidationError, match="escalates_to cycle"):
        validate_graph(graph)


def test_cycle_and_reachability_validation_use_standard_library_fallback(monkeypatch):
    monkeypatch.setattr("src.capability_graph.validation._networkx", lambda: None)
    graph = CapabilityGraph()
    graph.extend(
        [_node("route:a", "task_class"), _node("route:b", "task_class")],
        [_edge("routes_to", "route:a", "route:b"), _edge("routes_to", "route:b", "route:a")],
    )

    with pytest.raises(ValidationError, match="routes_to cycle"):
        validate_graph(graph)

    reachability_graph = CapabilityGraph()
    reachability_graph.extend(
        [_node("action", "action"), _node("gate", "human_gate")],
        [_edge("requires", "action", "gate")],
    )
    with pytest.raises(ValidationError, match="without an escalates_to path"):
        validate_graph(reachability_graph)


def test_reachable_human_gate_without_escalation_fails():
    graph = CapabilityGraph()
    graph.extend(
        [_node("action", "action"), _node("gate", "human_gate")],
        [_edge("requires", "action", "gate")],
    )

    with pytest.raises(ValidationError, match="without an escalates_to path"):
        validate_graph(graph)


def test_duplicate_node_id_with_differing_attributes_fails():
    graph = CapabilityGraph()
    graph.add_node(Node("same", "action", {"name": "first"}, _provenance("first.md")))

    with pytest.raises(DuplicateNodeError, match="differing attributes"):
        graph.add_node(Node("same", "action", {"name": "second"}, _provenance("second.md")))


def test_adapter_fail_closed_on_malformed_discovered_source(tmp_path):
    root = tmp_path / "source"
    skill = root / "broken" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("name: missing-frontmatter", encoding="utf-8")
    adapter = SkillAdapter()
    identity = source_identity(root, [skill])

    with pytest.raises(AdapterError, match="frontmatter is required"):
        adapter.run(root, identity)


def test_agent_task_candidate_filter_skips_schema_documentation(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "agent-task-frontmatter-schema.md").write_text(
        "# Agent-task schema\n",
        encoding="utf-8",
    )
    (root / "not-actually-a-packet.agent-task.md").write_text(
        "# Ordinary note with a misleading filename\n",
        encoding="utf-8",
    )

    assert AgentTaskAdapter().discover(root) == ()


def test_agent_task_candidate_filter_includes_grandfathered_packet_name(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    packet = root / "legacy-task.md"
    packet.write_text(
        "---\nartifact_type: workflow\ntask_schema: agent-task/v1\n---\n",
        encoding="utf-8",
    )

    assert AgentTaskAdapter().discover(root) == (packet,)


def test_skill_candidate_filter_skips_evidence_filename_ending_in_skill(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    evidence = root / "process-description-to-parametric-tactile-skill.md"
    evidence.write_text(
        "---\nartifact_type: evidence\ntitle: Tactile skill evidence\n---\n",
        encoding="utf-8",
    )

    assert SkillAdapter().discover(root) == ()


def test_agent_task_optional_lists_normalize_absent_and_null(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    packet = root / "2026-08-02-optional-lists.agent-task.md"
    packet.write_text(
        """---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-08-02-optional-lists
title: Exercise optional lists
status: ready
priority: low
task_type: validation
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V0_AUTO
risk_level: low
approval_required: false
source_traceability_required: true
repo: example/repo
allowed_paths:
denied_paths: null
inputs: ~
outputs: []
duplicates:
---
""",
        encoding="utf-8",
    )
    adapter = AgentTaskAdapter()
    identity = source_identity(root, [packet])

    result = adapter.run(root, identity)

    assert {node.type for node in result.nodes} == {
        "action",
        "model_profile",
        "precondition",
        "repository",
        "task_class",
        "validator",
    }
    assert {edge.type for edge in result.edges} == {
        "requires",
        "routes_to",
        "uses_model",
        "validated_by",
    }


def test_agent_task_emits_requires_only_for_true_schema_requirements(tmp_path):
    source = (FIXTURE_ROOT / "2026-08-02-demo.agent-task.md").read_text(
        encoding="utf-8"
    )
    source = source.replace("requires_zotero: false", "requires_zotero: true")
    source = source.replace("requires_web: false", "requires_web: true")
    root = tmp_path / "source"
    root.mkdir()
    packet = root / "2026-08-02-demo.agent-task.md"
    packet.write_text(source, encoding="utf-8")
    adapter = AgentTaskAdapter()
    identity = source_identity(root, [packet])

    result = adapter.run(root, identity)
    requires = [edge for edge in result.edges if edge.type == "requires"]
    preconditions = {
        node.attributes["source_field"]
        for node in result.nodes
        if node.type == "precondition"
    }

    assert len(requires) == 3
    assert preconditions == {
        "requires_zotero",
        "requires_web",
        "source_traceability_required",
    }


def test_agent_task_present_wrong_list_type_still_fails(tmp_path):
    source = (FIXTURE_ROOT / "2026-08-02-demo.agent-task.md").read_text(encoding="utf-8")
    source = source.replace("supersedes: []", "supersedes: not-a-list")
    root = tmp_path / "source"
    root.mkdir()
    packet = root / "2026-08-02-demo.agent-task.md"
    packet.write_text(source, encoding="utf-8")
    adapter = AgentTaskAdapter()
    identity = source_identity(root, [packet])

    with pytest.raises(AdapterError, match="supersedes must be a list"):
        adapter.run(root, identity)


def test_yaml_subset_folded_blocker_does_not_consume_following_keys():
    document = parse_yaml_subset(
        """blocker: >-
  The Beaver/Zotero MCP exposes only read tools plus create_note. It has no
  tool to create, rename, move, or delete collections or to relocate items, so
  reorganising the library through the MCP is not currently possible. Blocked
  pending a Zotero-write capability (Zotero API write integration or a future
  MCP tool). Until then, only a non-mutating proposed mapping can be produced.
allowed_paths:
  - automation/review/zotero-alignment/2026-06-23-zotero-library-vault-alignment-plan.md
denied_paths: []
""",
        "exact blocker",
    )

    assert document["blocker"] == (
        "The Beaver/Zotero MCP exposes only read tools plus create_note. It has no "
        "tool to create, rename, move, or delete collections or to relocate items, so "
        "reorganising the library through the MCP is not currently possible. Blocked "
        "pending a Zotero-write capability (Zotero API write integration or a future "
        "MCP tool). Until then, only a non-mutating proposed mapping can be produced."
    )
    assert document["allowed_paths"] == [
        "automation/review/zotero-alignment/2026-06-23-zotero-library-vault-alignment-plan.md"
    ]
    assert document["denied_paths"] == []
    assert "supersedes" not in document


@pytest.mark.parametrize(
    ("indicator", "expected"),
    ((">", "first second\n"), (">-", "first second"), ("|", "first\nsecond\n"), ("|-", "first\nsecond")),
)
def test_yaml_subset_block_scalar_styles_and_chomping(indicator, expected):
    document = parse_yaml_subset(
        f"value: {indicator}\n  first\n  second\nfollowing: intact\n",
        indicator,
    )

    assert document == {"value": expected, "following": "intact"}


def test_agent_task_fails_closed_on_malformed_packet(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    packet = root / "2026-08-02-malformed.agent-task.md"
    packet.write_text(
        "---\nartifact_type: agent-task\ntask_schema: agent-task/v2\n---\n# Missing fields\n",
        encoding="utf-8",
    )
    adapter = AgentTaskAdapter()
    identity = source_identity(root, [packet])

    with pytest.raises(AdapterError, match="requires non-empty task_id"):
        adapter.run(root, identity)


def test_repo_contract_fails_closed_on_malformed_contract(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    contract = root / "AGENTS.md"
    contract.write_text("No Markdown contract heading", encoding="utf-8")
    adapter = RepoContractAdapter()
    identity = source_identity(root, [contract])

    with pytest.raises(AdapterError, match="heading required"):
        adapter.run(root, identity)


def test_model_policy_fails_closed_on_malformed_real_shape(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    policy = root / "model_execution_policy.yaml"
    policy.write_text("version: 1\nroles: []\n", encoding="utf-8")
    adapter = ModelPolicyAdapter()
    identity = source_identity(root, [policy])

    with pytest.raises(AdapterError, match="roles must be a non-empty mapping"):
        adapter.run(root, identity)


def test_empty_source_root_is_explicit_no_sources_error(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()

    with pytest.raises(NoSourcesError, match="no-sources"):
        build_graph([root], tmp_path / "graph.db")

    assert not (tmp_path / "graph.db").exists()


def test_all_four_adapters_build_fixture_and_emit_declared_types(tmp_path):
    root = _copy_sources(tmp_path)
    result = build_graph([root], tmp_path / "graph.db")

    assert result.adapter_counts == {
        "agent_task_adapter": 1,
        "model_policy_adapter": 1,
        "repo_contract_adapter": 1,
        "skill_adapter": 1,
    }
    assert result.node_counts == {
        "action": 1,
        "artifact": 1,
        "authority": 1,
        "context_source": 1,
        "human_gate": 1,
        "model_profile": 2,
        "permission": 5,
        "precondition": 1,
        "repository": 2,
        "skill": 1,
        "task_class": 1,
        "tool": 2,
        "validator": 1,
    }
    assert result.edge_counts == {
        "forbids": 2,
        "may_write": 2,
        "produces": 1,
        "reads": 2,
        "requires": 1,
        "routes_to": 1,
        "uses_model": 2,
        "uses_tool": 2,
        "validated_by": 1,
    }


def test_real_obsidian_phd_build_has_substantive_counts_by_type(tmp_path):
    result = build_graph([REAL_PACKET_ROOT], tmp_path / "real.db")

    assert result.adapter_counts == {"agent_task_adapter": 152}
    minimum_nodes = {
        "action": 152,
        "artifact": 300,
        "context_source": 663,
        "human_gate": 2,
        "model_profile": 6,
        "permission": 1685,
        "precondition": 152,
        "repository": 3,
        "task_class": 50,
        "validator": 3,
    }
    minimum_edges = {
        "escalates_to": 286,
        "forbids": 1327,
        "may_write": 358,
        "produces": 300,
        "reads": 663,
        "requires": 152,
        "routes_to": 152,
        "uses_model": 152,
        "validated_by": 152,
    }
    for node_type, minimum in minimum_nodes.items():
        assert result.node_counts.get(node_type, 0) >= minimum, node_type
    for edge_type, minimum in minimum_edges.items():
        assert result.edge_counts.get(edge_type, 0) >= minimum, edge_type


@pytest.mark.parametrize("query_name", QUERY_NAMES)
def test_all_eleven_named_queries_have_stable_output_shape(tmp_path, query_name):
    root = _copy_sources(tmp_path)
    db = tmp_path / "graph.db"
    build_graph([root], db)

    answer = execute_query(db, query_name, route_id="task-class:demo")

    assert list(answer) == ["query", "route_id", "freshness", "computation", "result"]
    assert answer["query"] == query_name
    assert answer["route_id"] == "task-class:demo"
    assert answer["freshness"] == "current"
    assert answer["computation"]["edge_types"] == {
        edge_type: answer["computation"]["edge_types"][edge_type]
        for edge_type in QUERY_EDGE_TYPES[query_name]
    }
    if answer["computation"]["state"] == "computed":
        assert answer["computation"]["reason"] is None
        assert answer["computation"]["missing_edge_types"] == []
        assert isinstance(answer["result"], dict)
    else:
        assert answer["computation"]["state"] == "not-computed"
        assert answer["computation"]["reason"] == "no-such-relation"
        assert answer["computation"]["missing_edge_types"]
        assert answer["result"] is None


def test_every_named_query_declares_its_relation_scope():
    assert set(QUERY_EDGE_TYPES) == set(QUERY_NAMES)


def test_query_with_unemitted_relation_is_explicitly_not_computed(tmp_path):
    root = _copy_sources(tmp_path)
    db = tmp_path / "graph.db"
    build_graph([root], db)

    answer = execute_query(db, "what-fallback-applies", route_id="task-class:demo")

    assert answer["computation"] == {
        "state": "not-computed",
        "reason": "no-such-relation",
        "edge_types": {"falls_back_to": 0},
        "missing_edge_types": ["falls_back_to"],
    }
    assert answer["result"] is None


def test_empty_list_means_relation_exists_but_route_has_no_matches(tmp_path):
    root = _copy_sources(tmp_path)
    original = (root / "2026-08-02-demo.agent-task.md").read_text(encoding="utf-8")
    no_writes = original.replace(
        "task_id: 2026-08-02-demo",
        "task_id: 2026-08-02-no-writes",
    ).replace(
        "task_type: demo",
        "task_type: no-writes",
    ).replace(
        "allowed_paths:\n  - output/**",
        "allowed_paths: []",
    ).replace(
        "denied_paths:\n  - canonical/**",
        "denied_paths: []",
    )
    (root / "2026-08-02-no-writes.agent-task.md").write_text(
        no_writes,
        encoding="utf-8",
    )
    db = tmp_path / "graph.db"
    build_graph([root], db)

    answer = execute_query(
        db,
        "which-permissions-required",
        route_id="task-class:no-writes",
    )

    assert answer["computation"]["state"] == "computed"
    assert answer["computation"]["edge_types"]["may_write"] > 0
    assert answer["computation"]["edge_types"]["forbids"] > 0
    assert answer["result"] == {"permissions": []}


def test_real_packet_permissions_query_is_non_empty_and_relation_labelled(tmp_path):
    db = tmp_path / "real-permissions.db"
    result = build_graph([REAL_PACKET_ROOT], db)

    assert result.adapter_counts == {"agent_task_adapter": 152}
    answer = execute_query(
        db,
        "which-permissions-required",
        route_id="task-class:literature-integrity-audit",
    )
    permissions = answer["result"]["permissions"]

    assert answer["computation"]["state"] == "computed"
    assert permissions
    assert len(permissions) == 35
    assert {item["relation"] for item in permissions} == {"may_write", "forbids"}
    assert all(item["permission"]["type"] == "permission" for item in permissions)


def test_explain_returns_actual_edge_path_with_provenance(tmp_path):
    root = _copy_sources(tmp_path)
    db = tmp_path / "graph.db"
    build_graph([root], db)

    explanation = explain_route(db, "task-class:demo")
    paths = explanation["result"]["paths"]

    assert paths
    assert paths[0]["nodes"][0]["id"] == "task-class:demo"
    assert paths[0]["nodes"][-1]["id"] == "action:2026-08-02-demo"
    assert paths[0]["edges"][0]["type"] == "routes_to"
    assert set(paths[0]["edges"][0]["provenance"]) == set(PROVENANCE_FIELDS)
    assert "rationale" not in explanation["result"]


def _write_evaluation_graph(tmp_path: Path) -> Path:
    root = tmp_path / "eval-source"
    root.mkdir()
    source = root / "agent-task-eval.json"
    source.write_text('{"schema_version": 1}', encoding="utf-8")
    identity = source_identity(root, [source])
    provenance = Provenance(
        identity.source_repo,
        source.relative_to(root).as_posix(),
        identity.source_revision,
        sha256_file(source),
        identity.extracted_at,
        "agent_task_adapter",
        "1.0.0",
    )
    graph = CapabilityGraph()
    nodes = [
        Node("route:held-out", "task_class", {"name": "held out"}, provenance),
        Node("action:held-out", "action", {"name": "handle"}, provenance),
        Node("route:blocked", "task_class", {"name": "blocked"}, provenance),
        Node("action:blocked", "action", {"name": "blocked action"}, provenance),
        Node("failure:block", "failure_mode", {"name": "policy block"}, provenance),
    ]
    edges = [
        Edge("route-held", "routes_to", "route:held-out", "action:held-out", {}, provenance),
        Edge("route-blocked", "routes_to", "route:blocked", "action:blocked", {}, provenance),
        Edge("block", "blocked_by", "action:blocked", "failure:block", {}, provenance),
    ]
    graph.extend(nodes, edges)
    validate_graph(graph)
    db = tmp_path / "evaluation.db"
    save_graph(db, graph, [SourceRecord(
        identity.source_repo,
        source.relative_to(root).as_posix(),
        identity.source_revision,
        sha256_file(source),
        str(root),
        "agent_task_adapter",
    )])
    return db


def test_held_out_evaluation_passes_with_two_refusal_cases(tmp_path):
    cases = json.loads(HELD_OUT.read_text(encoding="utf-8"))["cases"]
    assert sum("expected_refusal" in case for case in cases) >= 2
    db = tmp_path / "real-evaluation.db"
    build_graph([REAL_PACKET_ROOT], db)

    result = evaluate_cases(db, HELD_OUT)

    assert result["passed"] == len(cases)
    assert result["failed"] == 0
    assert [item["outcome"] for item in result["cases"]].count("refused") >= 2


def test_evaluation_fails_if_graph_answers_expected_refusal(tmp_path):
    db = _write_evaluation_graph(tmp_path)
    cases = tmp_path / "bad-held-out.json"
    cases.write_text(json.dumps({"cases": [{
        "id": "must-refuse",
        "input_question": "What should handle this request?",
        "route_id": "route:held-out",
        "expected_refusal": "unroutable",
    }]}), encoding="utf-8")

    with pytest.raises(EvaluationError, match="expected unroutable refusal but graph answered"):
        evaluate_cases(db, cases)


def test_existing_mismatched_sqlite_schema_fails_closed(tmp_path):
    db = tmp_path / "old.db"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE old_schema (id INTEGER)")
        connection.execute("PRAGMA user_version = 99")

    with pytest.raises(SchemaMismatchError, match="schema version mismatch"):
        build_graph([_copy_sources(tmp_path)], db)


# --- Mutation-testing findings, 2026-08-03 ------------------------------------
# Six guards were mutation-tested by disabling each raise in turn and running
# the suite. Results and their correct interpretation:
#
#   authority-conflict raise        KILLED
#   cycle-detection raise           KILLED
#   human-gate escalation raise     KILLED
#   duplicate source identity       SURVIVED -- see the note below the tests
#   no-sources: zero nodes          SURVIVED individually
#   no-sources: no supported files  SURVIVED individually
#
# The two no-sources survivals are NOT a coverage gap. They are redundant
# guards that mask each other: with either one disabled, the other still
# catches an empty root. Disabling BOTH fails two tests, so the behaviour --
# an empty or unproductive source root raises an explicit NoSourcesError and
# never yields a graph that reports success -- is genuinely enforced and
# tested.
#
# That distinction matters generally: a surviving mutant can mean "redundant
# guard" as well as "untested guard", and only a combined mutation
# distinguishes them. Reading every survival as a gap overstates the problem.


class _ClaimsFileEmitsNothing(SourceAdapter):
    """Discovers a real file but emits no nodes or edges for it."""

    name = "empty_adapter"
    version = "1.0.0"
    node_types = frozenset()
    edge_types = frozenset()

    def discover(self, root):
        return tuple(sorted(root.rglob("*.md")))

    def parse(self, path, identity):
        return AdapterResult(nodes=(), edges=(), source_paths=(path,))


def test_sources_present_but_zero_nodes_raises_no_sources(tmp_path):
    """A root whose adapters emit nothing must fail, not yield an empty graph.

    Mutation: deleting the "adapters produced zero nodes" raise previously left
    the suite green. This is the more dangerous of the two no-sources paths -- a
    zero-node graph reporting success would answer every permission query with
    an empty result.
    """
    root = tmp_path / "unclaimed"
    root.mkdir()
    (root / "README.md").write_text("# not a capability source\n", encoding="utf-8")

    with pytest.raises((NoSourcesError, ValidationError)) as excinfo:
        build_graph([root], tmp_path / "out.db", adapters=(_ClaimsFileEmitsNothing(),))
    message = str(excinfo.value)
    assert "no-sources" in message or "emitted no provenance" in message


# NOT TESTED: the "duplicate source identity with differing records" guard in
# builder.py survived mutation (disabling its raise left the suite green), and
# an attempt to reach it through the public build_graph() API did not trigger
# it: two adapters sharing a name and claiming one path, differing only in
# source_revision, build without error. The guard may be unreachable from the
# public path and therefore defensive-only. Recorded rather than papered over
# with a test that exercises a reimplementation of the condition.

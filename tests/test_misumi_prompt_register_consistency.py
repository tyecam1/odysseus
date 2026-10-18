"""The Misumi long-horizon programme's register entry, evolution graph, prompt files and application traces agree.

Each rated application must be reachable from the active head with an identical rating, every version must point at a
file that exists, exactly one version is active, and the active prompt names itself. Nothing here judges the prompt's
content; it keeps the evidence layer (docs/initialising-prompt-register.md) from drifting.
"""

from pathlib import Path

import pytest
import yaml

from src.prompt_evolution import calculated_overall

ROOT = Path(__file__).resolve().parents[1]
PROMPT_ID = "misumi-long-horizon-programme"


def _load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def entry():
    register = _load(ROOT / "config" / "initialising-prompts.yaml")
    found = [p for p in register["prompts"] if p.get("prompt_id") == PROMPT_ID]
    assert len(found) == 1, "the programme must have exactly one register entry"
    return found[0]


@pytest.fixture(scope="module")
def graph(entry):
    return _load(ROOT / entry["graph_path"])


def _nodes(graph, node_type):
    return [n for n in graph["nodes"] if n["type"] == node_type]


def test_exactly_one_version_is_active_and_it_is_the_declared_one(entry):
    versions = entry["versions"]
    active = [v for v in versions if v["status"] == "active"]
    assert [v["version"] for v in active] == [entry["active_version"]]
    assert entry["version"] == entry["active_version"] == max(v["version"] for v in versions)
    assert all(v["status"] == "superseded" for v in versions if v["version"] != entry["active_version"])
    assert entry["prompt_path"] == active[0]["prompt_path"]


def test_every_version_file_exists_and_the_chain_is_unbroken(entry):
    versions = sorted(entry["versions"], key=lambda v: v["version"])
    assert [v["version"] for v in versions] == list(range(1, len(versions) + 1))
    for v in versions:
        assert (ROOT / v["prompt_path"]).is_file(), v["prompt_path"]
        if v["version"] > 1:
            assert v["parent_version"] == v["version"] - 1
            assert v["derived_from_applications"], f"v{v['version']} must name the applications it derives from"
    assert sorted(entry["supersedes"]) == list(range(1, entry["active_version"]))


def test_the_active_prompt_names_its_own_version(entry):
    text = (ROOT / entry["prompt_path"]).read_text(encoding="utf-8")
    assert f"Prompt identity: `{PROMPT_ID}@v{entry['active_version']}`" in text


def test_graph_head_matches_the_register_and_versions_match_their_files(entry, graph):
    assert graph["prompt_id"] == PROMPT_ID
    assert graph["active_head"] == f"prompt:v{entry['active_version']}"
    by_version = {v["version"]: v for v in entry["versions"]}
    graph_versions = _nodes(graph, "prompt_version")
    assert sorted(n["version"] for n in graph_versions) == sorted(by_version)
    for node in graph_versions:
        assert node["path"] == by_version[node["version"]]["prompt_path"]
        assert node["status"] == by_version[node["version"]]["status"]
        assert node.get("parent_version") == by_version[node["version"]].get("parent_version")


def test_every_application_trace_exists_and_matches_its_graph_node(entry, graph):
    edges = graph["edges"]
    for node in _nodes(graph, "application"):
        trace_path = ROOT / node["trace_path"]
        assert trace_path.is_file(), node["trace_path"]
        trace = _load(trace_path)
        assert trace["application_id"] == node["application_id"]
        assert trace["prompt_id"] == PROMPT_ID
        assert node["trace_path"].startswith(entry["application_trace_prefix"])
        applied_to = [e["from"] for e in edges if e["to"] == node["id"] and e["type"] == "applied"]
        assert applied_to == [f"prompt:v{trace['prompt_version']}"]
        rating = trace["rating"]
        assert calculated_overall(trace) == rating["agent_overall"], "agent_overall must be the mean of the five dimensions"
        for key, value in node["rating"].items():
            assert rating[key] == value, f"{node['application_id']}: graph rating {key} differs from the trace"
        assert sorted(node["failure_tags"]) == sorted(trace["failure_tags"])


def test_every_evolution_event_closes_its_loop_into_a_version(graph):
    edges = graph["edges"]
    for event in _nodes(graph, "evolution_event"):
        incoming = [e for e in edges if e["to"] == event["id"] and e["type"] == "observed"]
        assert [e["from"] for e in incoming] == [f"application:{event['evidence_application']}"]
        outgoing = [e for e in edges if e["from"] == event["id"]]
        assert len(outgoing) == 1 and outgoing[0]["type"] in ("derived_child", "reinforced")
        if event["decision"] == "evolve":
            assert outgoing[0]["type"] == "derived_child" and outgoing[0]["to"].startswith("prompt:v")
            assert event["targets"], "an evolve decision must state its targets"


def test_every_derived_version_binds_to_the_application_that_produced_it(entry, graph):
    apps = {n["application_id"] for n in _nodes(graph, "application")}
    for v in entry["versions"]:
        for app in v.get("derived_from_applications", []):
            assert app in apps, f"v{v['version']} derives from {app}, which has no application node"


def test_protected_invariants_are_recorded_for_the_active_head(entry, graph):
    validation = graph["guardrail_validation"][f"prompt:v{entry['active_version']}"]
    assert validation and all(value is True for value in validation.values())

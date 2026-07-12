from pathlib import Path

from src.persona_capabilities import (
    capability_summary,
    consult_edges,
    repository_capabilities,
    routing_intents,
)


PERSONAS = """\
personas:
  aoteru:
    role: head-human-interfacer
    skills: [routing, triage]
    owns: [coordination]
    consults: [kurisu]
    escalates_to: [user]
    routing:
      intents: [dispatch, clarify]
  sanji:
    role: chef
    skills: [cooking, shopping]
    owns: [food]
    consults: [misato]
    escalates_to: [aoteru]
    routing:
      intents: [meal-planning, pantry]
"""


def _root(tmp_path: Path, monkeypatch, content: str = PERSONAS) -> Path:
    root = tmp_path / "flat-knowledgebase"
    path = root / "config" / "personas.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    monkeypatch.setattr("src.persona_capabilities._resolve_seed_root", lambda: root)
    return root


def _registry(root: Path, content: str) -> None:
    (root / "config" / "capabilities.yaml").write_text(content, encoding="utf-8")


def test_capability_summary_returns_none_when_file_missing(tmp_path, monkeypatch):
    root = tmp_path / "flat-knowledgebase"
    root.mkdir()
    monkeypatch.setattr("src.persona_capabilities._resolve_seed_root", lambda: root)

    assert capability_summary("sanji") is None


def test_capability_summary_returns_none_for_malformed_yaml(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch, "personas: [unterminated")

    assert capability_summary("sanji") is None


def test_panel_persona_summary_includes_capabilities_and_interface(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)

    summary = capability_summary("sanji")

    assert summary is not None
    assert "Role: chef" in summary
    assert "Skills: cooking, shopping" in summary
    assert "Stewarded domains: food" in summary
    assert "Consults: misato" in summary
    assert "Escalates to: aoteru" in summary
    assert "Routing intents: meal-planning, pantry" in summary
    assert "Interface panel: food/PANTRY" in summary
    assert len(summary.splitlines()) <= 13


def test_aoteru_summary_includes_routing_and_one_passive_memory_line(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)

    summary = capability_summary("aoteru")

    assert summary is not None
    assert "Head-interfacer routing:" in summary
    assert "keeps a local passive memory" in summary
    assert "capture, open-loops, and glance" in summary
    assert "never writes to the household" in summary
    assert sum("Passive memory:" in line for line in summary.splitlines()) == 1
    assert len(summary.splitlines()) <= 13


def test_consult_edges_and_routing_intents_use_cached_persona_data(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)

    assert consult_edges("aoteru") == ["kurisu"]
    assert routing_intents("sanji") == ["meal-planning", "pantry"]


def test_consult_edges_returns_none_when_missing_or_malformed(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch, "personas:\n  aoteru:\n    role: head\n")
    assert consult_edges("aoteru") is None

    (root / "config" / "personas.yaml").write_text(
        "personas:\n  aoteru:\n    role: head\n    consults: {bad: value}\n",
        encoding="utf-8",
    )
    assert consult_edges("aoteru") is None


def test_repository_capabilities_project_owner_consult_and_external(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch)
    _registry(
        root,
        """\
groups:
  - id: household-tools
    owner: sanji
    consults: [aoteru]
external_patterns:
  - id: langgraph-state-machine
    owner: aoteru
    consults: [sanji]
    disposition: adopted_pattern
""",
    )

    assert repository_capabilities("sanji") == {
        "groups": ["household-tools (owner)"],
        "external_patterns": ["langgraph-state-machine (adopted_pattern)"],
    }
    assert repository_capabilities("aoteru") == {
        "groups": ["household-tools (consult)"],
        "external_patterns": ["langgraph-state-machine (adopted_pattern)"],
    }

    summary = capability_summary("sanji")
    assert "Capability stewardship: household-tools (owner)" in summary
    assert "External patterns: langgraph-state-machine (adopted_pattern)" in summary
    assert "context, not tool authority" in summary
    assert len(summary.splitlines()) <= 13


def test_missing_or_malformed_registry_degrades_without_losing_persona(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch)
    assert repository_capabilities("sanji") is None
    assert "Role: chef" in capability_summary("sanji")

    _registry(root, "groups: bad\nexternal_patterns: []\n")
    assert repository_capabilities("sanji") is None
    assert "Capability stewardship:" not in capability_summary("sanji")


def test_repository_capabilities_bound_long_group_lists(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch)
    groups = "\n".join(
        f"  - id: group-{index}\n    owner: sanji\n    consults: []" for index in range(6)
    )
    _registry(root, f"groups:\n{groups}\nexternal_patterns: []\n")

    projected = repository_capabilities("sanji")
    assert projected is not None
    assert projected["groups"][-1] == "+2 more"
    assert len(projected["groups"]) == 5

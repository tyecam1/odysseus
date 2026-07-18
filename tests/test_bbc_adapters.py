from pathlib import Path
import subprocess

import pytest

from src.bbc.adapters import (
    HomeBaseRepositoryAdapter,
    ObsidianPhDRepositoryAdapter,
    OdysseusRepositoryAdapter,
    RepositoryAdapterRegistry,
)


def repository(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
    return root


def test_odysseus_adapter_parses_real_roadmap_shape_with_stable_identity(tmp_path):
    root = repository(tmp_path, "odysseus")
    (root / "ROADMAP.md").write_text(
        "# Roadmap\n\n## High Priority\n\n- First production check\n- [x] Archived check\n\n## Backend\n\n- Migrate state safely\n",
        encoding="utf-8",
    )
    adapter = OdysseusRepositoryAdapter(root)
    first = adapter.snapshot()
    second = adapter.snapshot()
    assert [node.id for node in first.nodes] == [node.id for node in second.nodes]
    assert len(first.streams) == 2
    assert len(first.nodes) == 3
    archived = next(node for node in first.nodes if node.title == "Archived check")
    assert archived.archived and archived.state == "completed"
    assert all(link.startswith("repo://odysseus/") for node in first.nodes for link in node.source_links)


def test_homebase_adapter_maps_queue_state_dependency_and_archive(tmp_path):
    root = repository(tmp_path, "homebase")
    inbox = root / "agent-tasks" / "inbox"
    done = root / "agent-tasks" / "done"
    inbox.mkdir(parents=True)
    done.mkdir(parents=True)
    (inbox / "build-runtime.md").write_text(
        "---\ntitle: Build runtime\nstatus: in-progress\ndependencies:\n  - agent-tasks/inbox/prepare.md\n---\n# Build runtime\n\n## Objective\nShip the runtime.\n\n## Done when\n- Tests pass.\n",
        encoding="utf-8",
    )
    (inbox / "prepare.md").write_text("---\nstatus: blocked-human\n---\n# Prepare host\n", encoding="utf-8")
    (done / "old.md").write_text("---\nstatus: done\n---\n# Old path\n", encoding="utf-8")
    snapshot = HomeBaseRepositoryAdapter(root).snapshot()
    build = next(node for node in snapshot.nodes if node.title == "Build runtime")
    prepare = next(node for node in snapshot.nodes if node.title == "Prepare host")
    old = next(node for node in snapshot.nodes if node.title == "Old path")
    assert build.state == "active"
    assert build.dependency_ids == [prepare.id]
    assert build.acceptance_evidence == ["Tests pass."]
    assert prepare.state == "blocked"
    assert old.archived


def test_obsidian_alias_resolution_returns_structured_ambiguity_without_guessing(tmp_path):
    root = repository(tmp_path, "vault")
    inbox = root / "10-inbox"
    complete = inbox / "complete"
    complete.mkdir(parents=True)
    (inbox / "backlog.md").write_text("---\nartifact_type: backlog\n---\n# Backlog\n", encoding="utf-8")
    (inbox / "lab.md").write_text(
        "---\nartifact_type: work-item\nstatus: open\nproject: phd-research\n---\n# S2-E1 lab triage\n",
        encoding="utf-8",
    )
    (inbox / "metrology.md").write_text(
        "---\nartifact_type: work-item\nstatus: ready-to-send\nproject: phd-research\n---\n# S2-E1 metrology review\n",
        encoding="utf-8",
    )
    (complete / "old.md").write_text(
        "---\nartifact_type: work-item\nstatus: complete\nproject: phd-research\n---\n# S2-E1 old framing\n",
        encoding="utf-8",
    )
    adapter = ObsidianPhDRepositoryAdapter(root)
    resolution = adapter.resolve("S2-E1")
    assert resolution.status == "ambiguous"
    assert resolution.canonical_node_id is None
    assert len(resolution.candidates) == 3
    assert all(candidate.provenance for candidate in resolution.candidates)
    assert any("old framing" in candidate.title for candidate in resolution.candidates)


def test_adapter_rejects_non_repository_and_path_traversal(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(ValueError, match="not a Git repository"):
        OdysseusRepositoryAdapter(plain)

    fake = tmp_path / "fake"
    fake.mkdir()
    (fake / ".git").mkdir()
    with pytest.raises(ValueError, match="not a Git repository"):
        OdysseusRepositoryAdapter(fake)

    root = repository(tmp_path, "odysseus")
    (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    adapter = OdysseusRepositoryAdapter(root)
    with pytest.raises(ValueError, match="traversal"):
        adapter.inspect(relative_path="../secret.md")
    with pytest.raises(ValueError, match="authoritative"):
        (root / "README.md").write_text("not a work source", encoding="utf-8")
        adapter.inspect(relative_path="README.md")


def test_environment_registry_rejects_invalid_config_as_unavailable_health(tmp_path, monkeypatch):
    odysseus = repository(tmp_path, "odysseus-env")
    (odysseus / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    monkeypatch.setenv("BBC_MISUMI_ROOT", str(tmp_path / "not-a-repository"))
    monkeypatch.delenv("MISUMI_HOUSEHOLD_ROOT", raising=False)
    monkeypatch.delenv("MISUMI_SOURCE_ROOT", raising=False)
    registry = RepositoryAdapterRegistry.from_environment(odysseus_root=odysseus)
    misumi = next(system for system in registry.systems() if system.id == "misumi-homebase")
    assert misumi.configured
    assert not misumi.reachable
    assert "not a directory" in misumi.error


def test_real_checkout_roadmap_fixture_is_ingested_read_only():
    root = Path(__file__).parents[1]
    adapter = OdysseusRepositoryAdapter(root)
    before = (root / "ROADMAP.md").read_bytes()
    snapshot = adapter.snapshot()
    after = (root / "ROADMAP.md").read_bytes()
    assert snapshot.system.reachable
    assert snapshot.nodes
    assert before == after


def test_adapter_accepts_real_git_worktree(tmp_path):
    root = repository(tmp_path, "main")
    subprocess.run(["git", "-C", str(root), "config", "user.email", "bbc@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "BBC tests"], check=True)
    (root / "ROADMAP.md").write_text("# Roadmap\n\n## Runtime\n- Worktree node\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "ROADMAP.md"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "--quiet", "-m", "fixture"], check=True)
    worktree = tmp_path / "worktree"
    subprocess.run(
        ["git", "-C", str(root), "worktree", "add", "--quiet", "--detach", str(worktree)],
        check=True,
    )
    assert OdysseusRepositoryAdapter(worktree).snapshot().nodes[0].title == "Worktree node"


@pytest.mark.parametrize(
    ("adapter_type", "active_rel", "complete_rel", "frontmatter"),
    [
        (
            HomeBaseRepositoryAdapter,
            "agent-tasks/inbox/move-me.md",
            "agent-tasks/done/move-me.md",
            "---\ntitle: Move me\n---\n# Move me\n",
        ),
        (
            ObsidianPhDRepositoryAdapter,
            "10-inbox/move-me.md",
            "10-inbox/complete/move-me.md",
            "---\ntitle: Move me\nartifact_type: work-item\n---\n# Move me\n",
        ),
    ],
)
def test_queue_moves_keep_queue_neutral_identity(adapter_type, active_rel, complete_rel, frontmatter, tmp_path):
    root = repository(tmp_path, "queue-move")
    active = root / active_rel
    complete = root / complete_rel
    active.parent.mkdir(parents=True, exist_ok=True)
    active.write_text(frontmatter, encoding="utf-8")
    before = adapter_type(root).snapshot().nodes[0]
    complete.parent.mkdir(parents=True, exist_ok=True)
    active.rename(complete)
    after = adapter_type(root).snapshot().nodes[0]
    assert before.id == after.id
    assert before.canonical_key == after.canonical_key
    assert after.state == "completed"
    assert after.provenance[0].path == complete_rel


def test_explicit_source_id_precedes_path_identity(tmp_path):
    root = repository(tmp_path, "explicit-id")
    first = root / "agent-tasks" / "inbox" / "first-name.md"
    first.parent.mkdir(parents=True)
    first.write_text("---\nsource_id: TASK-42\ntitle: Stable task\n---\n", encoding="utf-8")
    before = HomeBaseRepositoryAdapter(root).snapshot().nodes[0]
    renamed = first.with_name("renamed.md")
    first.rename(renamed)
    after = HomeBaseRepositoryAdapter(root).snapshot().nodes[0]
    assert before.id == after.id
    assert after.canonical_key == "source-id:task-42"


def test_obsidian_dependencies_resolve_only_to_canonical_nodes_and_links_stay_links(tmp_path):
    root = repository(tmp_path, "edges")
    inbox = root / "10-inbox"
    inbox.mkdir()
    (inbox / "parent.md").write_text(
        "---\nartifact_type: work-item\ntitle: Parent\nblocks: [10-inbox/reverse.md]\n"
        "related: [10-inbox/child.md]\nsource_notes: [04-supportDesign/evidence.md]\n---\n",
        encoding="utf-8",
    )
    (inbox / "child.md").write_text(
        "---\nartifact_type: work-item\ntitle: Child\nparent_work_item: 10-inbox/parent.md\n"
        "dependencies: [missing.md]\n---\n",
        encoding="utf-8",
    )
    (inbox / "blocked.md").write_text(
        "---\nartifact_type: work-item\ntitle: Blocked\nstatus: blocked\n"
        "blocked_by: [10-inbox/parent.md, missing.md]\n---\n",
        encoding="utf-8",
    )
    (inbox / "reverse.md").write_text(
        "---\nartifact_type: work-item\ntitle: Reverse\n---\n",
        encoding="utf-8",
    )
    snapshot = ObsidianPhDRepositoryAdapter(root).snapshot()
    nodes = {node.title: node for node in snapshot.nodes}
    assert nodes["Child"].dependency_ids == [nodes["Parent"].id]
    assert nodes["Blocked"].dependency_ids == [nodes["Parent"].id]
    assert nodes["Blocked"].blocker_ids == [nodes["Parent"].id]
    assert nodes["Reverse"].dependency_ids == [nodes["Parent"].id]
    assert nodes["Parent"].dependency_ids == []
    assert "repo://obsidian-phd/10-inbox/child.md" in nodes["Parent"].source_links
    all_ids = {node.id for node in snapshot.nodes}
    assert all(edge in all_ids for node in snapshot.nodes for edge in node.dependency_ids + node.blocker_ids)


def test_real_s2_e1_shape_uses_hierarchy_and_backlog_evidence(tmp_path):
    root = repository(tmp_path, "s2")
    inbox = root / "10-inbox"
    inbox.mkdir()
    target_name = "s2-e1-perception-experiment-hardware-and-measurement-setup.md"
    (inbox / "backlog.md").write_text(
        f"---\nartifact_type: backlog\n---\n# Backlog\n- S2-E1 experiment — `10-inbox/{target_name}`\n"
        "- S2-E1 CAD — `10-inbox/s2-e1-cad.md`\n",
        encoding="utf-8",
    )
    (inbox / target_name).write_text(
        "---\nartifact_type: work-item\nstatus: active\ntitle: S2-E1 physical acquisition\n---\n",
        encoding="utf-8",
    )
    (inbox / "s2-e1-cad.md").write_text(
        f"---\nartifact_type: work-item\nstatus: active\ntitle: S2-E1 CAD support\n"
        f"parent_work_item: 10-inbox/{target_name}\n---\n",
        encoding="utf-8",
    )
    (inbox / "incidental.md").write_text(
        "---\nartifact_type: work-item\nstatus: active\ntitle: Unrelated item\n---\n# Unrelated\nBody mentions S2-E1 only.\n",
        encoding="utf-8",
    )
    adapter = ObsidianPhDRepositoryAdapter(root)
    resolution = adapter.resolve("S2-E1")
    assert resolution.status == "resolved"
    node = next(node for node in adapter.snapshot().nodes if node.id == resolution.canonical_node_id)
    assert node.provenance[0].path == f"10-inbox/{target_name}"
    assert any(item.source_kind == "obsidian-backlog-index" for item in node.provenance)
    assert all(candidate.title != "Unrelated item" for candidate in resolution.candidates)


def test_unsupported_authoritative_alias_collision_remains_ambiguous(tmp_path):
    root = repository(tmp_path, "collision")
    inbox = root / "10-inbox"
    inbox.mkdir()
    for suffix in ("one", "two"):
        (inbox / f"s9-e1-{suffix}.md").write_text(
            f"---\nartifact_type: work-item\nstatus: active\ntitle: S9-E1 {suffix}\n---\n",
            encoding="utf-8",
        )
    resolution = ObsidianPhDRepositoryAdapter(root).resolve("S9-E1")
    assert resolution.status == "ambiguous"
    assert resolution.canonical_node_id is None

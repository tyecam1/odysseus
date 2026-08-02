"""Adapter for SKILL.md frontmatter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import AdapterError
from ..model import Edge, Node
from .base import (
    AdapterResult,
    SourceAdapter,
    SourceIdentity,
    edge_id,
    provenance_for,
    read_source,
    stable_id,
)
from .yaml_subset import split_frontmatter


def _allowed_tools(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value):
        return [item.strip() for item in value]
    raise AdapterError("skill_adapter: allowed-tools must be a string or list of strings")


class SkillAdapter(SourceAdapter):
    name = "skill_adapter"
    node_types = frozenset({"skill", "tool"})
    edge_types = frozenset({"uses_tool"})

    def discover(self, root: Path) -> tuple[Path, ...]:
        return tuple(sorted(
            (
                path for path in root.rglob("*.md")
                if path.is_file() and path.name.upper() == "SKILL.MD"
            ),
            key=lambda path: path.relative_to(root).as_posix(),
        ))

    def parse(self, path: Path, identity: SourceIdentity) -> AdapterResult:
        text = read_source(path, self.name)
        frontmatter, _body = split_frontmatter(text, str(path))
        name = frontmatter.get("name")
        description = frontmatter.get("description")
        if not isinstance(name, str) or not name.strip():
            raise AdapterError(f"{self.name}: {path} requires frontmatter name")
        if not isinstance(description, str) or not description.strip():
            raise AdapterError(f"{self.name}: {path} requires frontmatter description")
        tools = _allowed_tools(
            frontmatter.get("allowed-tools", frontmatter.get("allowed_tools"))
        )
        provenance = provenance_for(path, identity, self.name, self.version)
        relative = path.relative_to(identity.root).as_posix()
        skill_id = str(frontmatter.get("id") or f"skill:{stable_id(relative)}")
        node = Node(
            skill_id,
            "skill",
            {"name": name.strip(), "description": description.strip()},
            provenance,
        )
        nodes = [node]
        edges: list[Edge] = []
        for ordinal, tool_name in enumerate(sorted(set(tools))):
            tool_id = f"tool:{stable_id(tool_name)}"
            nodes.append(Node(tool_id, "tool", {"name": tool_name}, provenance))
            edges.append(Edge(
                edge_id("uses_tool", skill_id, tool_id, ordinal),
                "uses_tool",
                skill_id,
                tool_id,
                {},
                provenance,
            ))
        return AdapterResult(tuple(nodes), tuple(edges), (path,))


adapter = SkillAdapter()

"""Adapter for AGENTS.md-family repository operating contracts."""

from __future__ import annotations

import re
from pathlib import Path

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


_CONTRACT_NAMES = frozenset({
    "AGENTS.md",
    "AGENT.md",
    "CLAUDE.md",
    "OPERATING-CONTRACT.md",
    "OPERATING_CONTRACT.md",
})

_HEADING_MODES = (
    ("may_write", ("may write", "writable", "write authority", "allowed writes")),
    ("forbids", ("forbid", "do not write", "must not write", "prohibited")),
    ("reads", (
        "read first",
        "must read",
        "required reading",
        "required context",
        "start here",
        "architecture control surface",
    )),
    ("human_gate", (
        "human gate",
        "human-gated",
        "human decision",
        "approval required",
        "ask first",
    )),
)


def _mode_for_heading(heading: str) -> str | None:
    normalized = heading.lower().strip("# ")
    for mode, phrases in _HEADING_MODES:
        if any(phrase in normalized for phrase in phrases):
            return mode
    return None


def _clean_bullet(value: str) -> str:
    value = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", value.strip())
    value = value.strip().strip("`").strip()
    if value.startswith("[") and "](" in value:
        value = value.split("](", 1)[1].rstrip(")")
    return value


def _inline_paths(value: str) -> list[str]:
    paths = []
    for candidate in re.findall(r"`([^`]+)`", value):
        candidate = candidate.strip()
        if (
            "/" in candidate
            or "\\" in candidate
            or "*" in candidate
            or candidate.lower().endswith((".md", ".json", ".yaml", ".yml"))
        ):
            paths.append(candidate)
    return paths


def _values_for_directive(value: str) -> list[str]:
    return _inline_paths(value) or [_clean_bullet(value)]


def _sections(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {mode: [] for mode, _ in _HEADING_MODES}
    mode: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            mode = _mode_for_heading(line)
            continue
        is_list_item = bool(re.match(r"^(?:[-*+]|\d+[.)])\s+", line))
        value = _clean_bullet(line)
        if mode and (is_list_item or (mode == "reads" and _inline_paths(value))):
            selected = [value] if mode == "human_gate" else _values_for_directive(value)
            found[mode].extend(item for item in selected if item)
            continue
        if re.search(r"(?:always\s+)?require(?:s)? approval\s*:\s*$", line, re.I):
            mode = "human_gate"
            continue
        direct = re.match(
            r"^[-*+]\s*(may write|write|forbidden|forbid|do not write|read first|must read|human gate|approval)\s*:\s*(.+)$",
            line,
            flags=re.IGNORECASE,
        )
        if direct:
            label, value = direct.groups()
            lower = label.lower()
            direct_mode = (
                "may_write" if lower in {"may write", "write"}
                else "forbids" if lower in {"forbidden", "forbid", "do not write"}
                else "reads" if lower in {"read first", "must read"}
                else "human_gate"
            )
            found[direct_mode].append(_clean_bullet(value))
            continue

        for clause in re.split(r"(?<=[.!?])\s+", value):
            lower = clause.lower()
            if any(phrase in lower for phrase in (
                "must go to",
                "belongs under",
                "belong under",
                "write only to",
                "writes stay under",
                "may write",
            )):
                # Write authority must resolve to an explicit path.  A prose
                # phrase such as "bounded canonical families" is a condition,
                # not an executable path grant.
                conditional = any(marker in lower for marker in (
                    " after ",
                    " if ",
                    " when ",
                    " with approval",
                    "exception",
                ))
                if not conditional:
                    found["may_write"].extend(_inline_paths(clause))
            if (
                any(phrase in lower for phrase in (
                    "do not write",
                    "must not write",
                    "must not modify",
                    "must not mutate",
                    "never writes",
                    "never write",
                    "read-only",
                ))
                or ("never" in lower and any(
                    verb in lower for verb in ("merge", "promote", "delete", "rename", "emit")
                ))
            ):
                found["forbids"].extend(_values_for_directive(clause))
    return found


class RepoContractAdapter(SourceAdapter):
    name = "repo_contract_adapter"
    node_types = frozenset({"repository", "authority", "permission", "human_gate"})
    edge_types = frozenset({"forbids", "may_write", "reads"})

    def discover(self, root: Path) -> tuple[Path, ...]:
        return tuple(sorted(
            (
                path for path in root.rglob("*.md")
                if path.name.upper() in {name.upper() for name in _CONTRACT_NAMES}
                or path.name.upper().endswith("-AGENTS.MD")
            ),
            key=lambda path: path.relative_to(root).as_posix(),
        ))

    def parse(self, path: Path, identity: SourceIdentity) -> AdapterResult:
        text = read_source(path, self.name)
        if not re.search(r"^#{1,6}\s+\S", text, flags=re.MULTILINE):
            raise AdapterError(f"{self.name}: malformed contract {path}: heading required")
        provenance = provenance_for(path, identity, self.name, self.version)
        relative = path.relative_to(identity.root).as_posix()
        repo_id = f"repository:{stable_id(identity.source_repo)}"
        authority_id = f"authority:{stable_id(identity.source_repo)}:{stable_id(relative)}"
        nodes = [
            Node(repo_id, "repository", {"name": identity.source_repo}, provenance),
            Node(
                authority_id,
                "authority",
                {"contract_path": relative, "repository_id": repo_id},
                provenance,
            ),
        ]
        edges: list[Edge] = []
        sections = _sections(text)
        for mode in ("may_write", "forbids", "reads"):
            for ordinal, value in enumerate(sorted(set(sections[mode]))):
                permission_id = (
                    f"permission:{stable_id(identity.source_repo)}:{mode}:{stable_id(value)}"
                )
                nodes.append(Node(
                    permission_id,
                    "permission",
                    {"mode": mode, "path": value},
                    provenance,
                ))
                edges.append(Edge(
                    edge_id(mode, authority_id, permission_id, ordinal),
                    mode,
                    authority_id,
                    permission_id,
                    {"path": value},
                    provenance,
                ))
        for value in sorted(set(sections["human_gate"])):
            gate_id = f"human-gate:{stable_id(identity.source_repo)}:{stable_id(value)}"
            nodes.append(Node(gate_id, "human_gate", {"decision": value}, provenance))
        return AdapterResult(tuple(nodes), tuple(edges), (path,))


adapter = RepoContractAdapter()

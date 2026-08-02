"""In-memory model for the derived procedural capability graph."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

from .constants import (
    EDGE_TYPES,
    FORBIDDEN_REASONING_KEYS,
    NODE_TYPES,
    PROVENANCE_FIELDS,
)
from .errors import DuplicateNodeError, ProvenanceError, ValidationError


def _plain_dict(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(child)
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        children = [_canonical_value(child) for child in value]
        return sorted(
            children,
            key=lambda child: json.dumps(
                child,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    return value


def _find_forbidden_key(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).strip().lower().replace(" ", "_")
            if normalized in FORBIDDEN_REASONING_KEYS:
                return str(key)
            found = _find_forbidden_key(child)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for child in value:
            found = _find_forbidden_key(child)
            if found:
                return found
    return None


@dataclass(frozen=True)
class Provenance:
    source_repo: str
    source_path: str
    source_revision: str
    source_sha256: str
    extracted_at: str
    adapter_name: str
    adapter_version: str

    def validate(self) -> None:
        data = asdict(self)
        missing = [name for name in PROVENANCE_FIELDS if not str(data.get(name, "")).strip()]
        if missing:
            raise ProvenanceError(f"incomplete provenance; missing: {', '.join(missing)}")
        if len(self.source_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.source_sha256.lower()):
            raise ProvenanceError("source_sha256 must be a complete lowercase SHA-256 digest")

    def to_dict(self) -> dict[str, str]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Provenance":
        missing = [name for name in PROVENANCE_FIELDS if name not in value]
        if missing:
            raise ProvenanceError(f"incomplete provenance; missing: {', '.join(missing)}")
        provenance = cls(**{name: str(value[name]) for name in PROVENANCE_FIELDS})
        provenance.validate()
        return provenance


@dataclass(frozen=True)
class Node:
    id: str
    type: str
    attributes: Mapping[str, Any] = field(default_factory=dict)
    provenance: Provenance | Mapping[str, Any] | None = None

    def validate(self) -> None:
        if not self.id.strip():
            raise ValidationError("node id is required")
        if self.type not in NODE_TYPES:
            raise ValidationError(f"unsupported node type {self.type!r}")
        if self.provenance is None:
            raise ProvenanceError(f"node {self.id!r} has no provenance")
        provenance = self.provenance
        if not isinstance(provenance, Provenance):
            provenance = Provenance.from_mapping(provenance)
        provenance.validate()
        forbidden = _find_forbidden_key(self.attributes)
        if forbidden:
            raise ValidationError(
                f"node {self.id!r} contains forbidden reasoning field {forbidden!r}"
            )

    def normalized(self) -> "Node":
        provenance = self.provenance
        if not isinstance(provenance, Provenance):
            provenance = Provenance.from_mapping(provenance or {})
        node = Node(self.id, self.type, _plain_dict(self.attributes), provenance)
        node.validate()
        return node

    def to_dict(self) -> dict[str, Any]:
        node = self.normalized()
        return {
            "id": node.id,
            "type": node.type,
            "attributes": _canonical_value(node.attributes),
            "provenance": node.provenance.to_dict(),
        }


@dataclass(frozen=True)
class Edge:
    id: str
    type: str
    source: str
    target: str
    attributes: Mapping[str, Any] = field(default_factory=dict)
    provenance: Provenance | Mapping[str, Any] | None = None

    def validate(self) -> None:
        if not self.id.strip():
            raise ValidationError("edge id is required")
        if self.type not in EDGE_TYPES:
            raise ValidationError(f"unsupported edge type {self.type!r}")
        if not self.source.strip() or not self.target.strip():
            raise ValidationError(f"edge {self.id!r} requires source and target")
        if self.provenance is None:
            raise ProvenanceError(f"edge {self.id!r} has no provenance")
        provenance = self.provenance
        if not isinstance(provenance, Provenance):
            provenance = Provenance.from_mapping(provenance)
        provenance.validate()

    def normalized(self) -> "Edge":
        provenance = self.provenance
        if not isinstance(provenance, Provenance):
            provenance = Provenance.from_mapping(provenance or {})
        edge = Edge(
            self.id,
            self.type,
            self.source,
            self.target,
            _plain_dict(self.attributes),
            provenance,
        )
        edge.validate()
        return edge

    def to_dict(self) -> dict[str, Any]:
        edge = self.normalized()
        return {
            "id": edge.id,
            "type": edge.type,
            "source": edge.source,
            "target": edge.target,
            "attributes": _canonical_value(edge.attributes),
            "provenance": edge.provenance.to_dict(),
        }


class CapabilityGraph:
    """Validated graph assembly with deterministic duplicate handling."""

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}

    def add_node(self, node: Node) -> None:
        node = node.normalized()
        existing = self.nodes.get(node.id)
        if existing is None:
            self.nodes[node.id] = node
            return
        if existing.type != node.type or dict(existing.attributes) != dict(node.attributes):
            raise DuplicateNodeError(
                "duplicate node id with differing attributes: "
                f"{node.id!r}; first={existing.to_dict()!r}; second={node.to_dict()!r}"
            )
        if existing.provenance.to_dict() != node.provenance.to_dict():
            # Equal semantic emissions are allowed. Select one source deterministically.
            chosen = min((existing, node), key=lambda item: tuple(item.provenance.to_dict().values()))
            self.nodes[node.id] = chosen

    def add_edge(self, edge: Edge) -> None:
        edge = edge.normalized()
        existing = self.edges.get(edge.id)
        if existing is None:
            self.edges[edge.id] = edge
            return
        if existing.to_dict() != edge.to_dict():
            raise ValidationError(
                f"duplicate edge id with differing values: {edge.id!r}"
            )

    def extend(self, nodes: Iterable[Node], edges: Iterable[Edge]) -> None:
        for node in nodes:
            self.add_node(node)
        for edge in edges:
            self.add_edge(edge)

    def validate_references(self) -> None:
        for node in self.nodes.values():
            node.validate()
        for edge in self.edges.values():
            edge.validate()
            missing = [endpoint for endpoint in (edge.source, edge.target) if endpoint not in self.nodes]
            if missing:
                raise ValidationError(
                    f"edge {edge.id!r} references missing node(s): {', '.join(missing)}"
                )

"""Fail-closed graph validation, including authority and topology conflicts."""

from __future__ import annotations

import fnmatch
import json
from collections import defaultdict, deque

from .errors import ValidationError
from .model import CapabilityGraph, Edge


def _networkx():
    try:
        import networkx as nx
    except ImportError as exc:
        return None
    return nx


def _literal_prefix(pattern: str) -> str:
    normalized = pattern.replace("\\", "/").lstrip("./")
    wildcard_positions = [
        position for token in ("*", "?", "[")
        if (position := normalized.find(token)) >= 0
    ]
    if wildcard_positions:
        normalized = normalized[: min(wildcard_positions)]
    return normalized.rstrip("/")


def paths_overlap(first: str, second: str) -> bool:
    """Conservatively decide whether two path scopes can cover one target."""
    a = first.replace("\\", "/").lstrip("./").rstrip("/")
    b = second.replace("\\", "/").lstrip("./").rstrip("/")
    if a == b or fnmatch.fnmatchcase(a, b) or fnmatch.fnmatchcase(b, a):
        return True
    prefix_a = _literal_prefix(a)
    prefix_b = _literal_prefix(b)
    # A suffix-only glob such as ``**/*.pdf`` has no literal directory
    # prefix.  Without a concrete candidate path, its intersection with a
    # directory allowlist cannot be established from prefixes alone.  Exact
    # and direct fnmatch coverage were already checked above.
    if not prefix_a or not prefix_b:
        return False
    return (
        prefix_a == prefix_b
        or prefix_a.startswith(prefix_b + "/")
        or prefix_b.startswith(prefix_a + "/")
    )


def _edge_path(edge: Edge, graph: CapabilityGraph) -> str:
    target = graph.nodes[edge.target]
    return str(edge.attributes.get("path") or target.attributes.get("path") or "")


def validate_authority_conflicts(graph: CapabilityGraph) -> None:
    may_write = [edge for edge in graph.edges.values() if edge.type == "may_write"]
    forbids = [edge for edge in graph.edges.values() if edge.type == "forbids"]
    for allowed in may_write:
        for forbidden in forbids:
            if allowed.source != forbidden.source:
                continue
            if not paths_overlap(_edge_path(allowed, graph), _edge_path(forbidden, graph)):
                continue
            records = {
                "may_write": allowed.provenance.to_dict(),
                "forbids": forbidden.provenance.to_dict(),
            }
            raise ValidationError(
                "authority conflict for actor "
                f"{allowed.source!r}: overlapping may_write {_edge_path(allowed, graph)!r} "
                f"and forbids {_edge_path(forbidden, graph)!r}; provenance="
                f"{json.dumps(records, sort_keys=True)}"
            )


def _typed_edges(graph: CapabilityGraph, edge_type: str) -> list[tuple[str, str]]:
    return [
        (edge.source, edge.target)
        for edge in graph.edges.values()
        if edge.type == edge_type
    ]


def _fallback_cycle(nodes: set[str], edges: list[tuple[str, str]]) -> list[str] | None:
    outgoing: dict[str, list[str]] = defaultdict(list)
    for source, target in edges:
        outgoing[source].append(target)
    for targets in outgoing.values():
        targets.sort()
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            start = stack.index(node)
            return [*stack[start:], node]
        if node in visited:
            return None
        visiting.add(node)
        stack.append(node)
        for target in outgoing.get(node, []):
            cycle = visit(target)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in sorted(nodes):
        cycle = visit(node)
        if cycle:
            return cycle
    return None


def _find_cycle(graph: CapabilityGraph, edge_type: str) -> list[str] | None:
    nx = _networkx()
    edges = _typed_edges(graph, edge_type)
    if nx is None:
        return _fallback_cycle(set(graph.nodes), edges)
    digraph = nx.DiGraph()
    digraph.add_nodes_from(graph.nodes)
    digraph.add_edges_from(edges)
    try:
        cycle = nx.find_cycle(digraph, orientation="original")
    except nx.NetworkXNoCycle:
        return None
    return [*[str(part[0]) for part in cycle], str(cycle[-1][1])]


def _has_path(nodes: set[str], edges: list[tuple[str, str]], source: str, target: str) -> bool:
    nx = _networkx()
    if nx is not None:
        digraph = nx.DiGraph()
        digraph.add_nodes_from(nodes)
        digraph.add_edges_from(edges)
        return bool(nx.has_path(digraph, source, target))
    outgoing: dict[str, list[str]] = defaultdict(list)
    for first, second in edges:
        outgoing[first].append(second)
    queue = deque([source])
    seen = {source}
    while queue:
        current = queue.popleft()
        if current == target:
            return True
        for child in outgoing.get(current, []):
            if child not in seen:
                seen.add(child)
                queue.append(child)
    return False


def validate_cycles(graph: CapabilityGraph) -> None:
    for edge_type in ("routes_to", "escalates_to"):
        cycle = _find_cycle(graph, edge_type)
        if cycle:
            raise ValidationError(f"{edge_type} cycle detected: {' -> '.join(cycle)}")


def validate_human_gate_escalation(graph: CapabilityGraph) -> None:
    nodes = set(graph.nodes)
    all_edges = [(edge.source, edge.target) for edge in graph.edges.values()]
    escalation_edges = [
        (edge.source, edge.target)
        for edge in graph.edges.values()
        if edge.type == "escalates_to"
    ]
    actions = [node.id for node in graph.nodes.values() if node.type == "action"]
    gates = [node.id for node in graph.nodes.values() if node.type == "human_gate"]
    for action in actions:
        for gate in gates:
            if _has_path(nodes, all_edges, action, gate) and not _has_path(
                nodes, escalation_edges, action, gate
            ):
                raise ValidationError(
                    f"human gate {gate!r} is reachable from action {action!r} "
                    "without an escalates_to path"
                )


def validate_graph(graph: CapabilityGraph) -> None:
    graph.validate_references()
    validate_authority_conflicts(graph)
    validate_cycles(graph)
    validate_human_gate_escalation(graph)

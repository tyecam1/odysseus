"""Eleven stable named capability-graph queries and provenance explanations."""

from __future__ import annotations

import re
from collections import Counter, deque
from pathlib import Path
from typing import Any, Callable

from .errors import QueryRefusedError, StaleGraphError
from .freshness import FreshnessReport, GraphFreshness, check_freshness
from .model import CapabilityGraph, Edge, Node
from .storage import load_graph


QUERY_NAMES = {
    "what-should-handle": "What should handle this request?",
    "which-repository-owns": "Which repository owns it?",
    "what-must-be-read-first": "What must be read first?",
    "which-model-skill-tool": "Which model, skill and tool are appropriate?",
    "which-permissions-required": "Which permissions are required?",
    "what-may-be-written": "What may be written?",
    "which-validator-proves-completion": "Which validator proves completion?",
    "what-fallback-applies": "What fallback applies?",
    "which-human-decision-required": "Which human decision is required?",
    "why-route-selected": "Why was this route selected?",
    "route-status": "Is the route current, superseded or blocked?",
}

# Every relation a named query filters on must be declared here.  Query
# execution uses this declaration to distinguish a computed empty result from
# a graph in which the required relation was never emitted at all.
QUERY_EDGE_TYPES: dict[str, tuple[str, ...]] = {
    "what-should-handle": ("routes_to",),
    "which-repository-owns": (),
    "what-must-be-read-first": ("reads",),
    "which-model-skill-tool": ("uses_model", "uses_skill", "uses_tool"),
    "which-permissions-required": ("may_write", "forbids"),
    "what-may-be-written": ("may_write",),
    "which-validator-proves-completion": ("validated_by",),
    "what-fallback-applies": ("falls_back_to",),
    "which-human-decision-required": ("escalates_to",),
    "why-route-selected": ("routes_to",),
    "route-status": ("blocked_by", "supersedes"),
}


def _normalize_question(value: str) -> str:
    value = value.strip()
    for name, question in QUERY_NAMES.items():
        if value.lower().rstrip("?") == question.lower().rstrip("?"):
            return name
        if value.lower().replace("_", "-") == name:
            return name
    raise QueryRefusedError(
        f"unknown named query {value!r}; expected one of: {', '.join(QUERY_NAMES)}"
    )


def _summary(node: Node) -> dict[str, Any]:
    return {"id": node.id, "type": node.type, "attributes": dict(node.attributes)}


def _edge_record(edge: Edge) -> dict[str, Any]:
    return {
        "id": edge.id,
        "type": edge.type,
        "source": edge.source,
        "target": edge.target,
        "attributes": dict(edge.attributes),
        "provenance": edge.provenance.to_dict(),
    }


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 1}


def resolve_route(graph: CapabilityGraph, route_id: str | None, request: str | None = None) -> Node:
    if route_id:
        node = graph.nodes.get(route_id)
        if not node or node.type not in {"intent", "task_class"}:
            raise QueryRefusedError(f"unroutable: no route {route_id!r}")
        return node
    routes = sorted(
        (node for node in graph.nodes.values() if node.type in {"intent", "task_class"}),
        key=lambda node: node.id,
    )
    if request:
        wanted = _tokens(request)
        scored: list[tuple[int, Node]] = []
        for node in routes:
            searchable = " ".join(
                str(value)
                for key, value in node.attributes.items()
                if key in {"name", "description", "keywords"}
            )
            score = len(wanted.intersection(_tokens(f"{node.id} {searchable}")))
            if score:
                scored.append((score, node))
        if scored:
            best = max(score for score, _node in scored)
            winners = [node for score, node in scored if score == best]
            if len(winners) == 1:
                return winners[0]
            raise QueryRefusedError("unroutable: request matches multiple routes equally")
    if len(routes) == 1:
        return routes[0]
    raise QueryRefusedError("unroutable: an explicit route id is required")


def _outgoing(graph: CapabilityGraph, source_ids: set[str], edge_types: set[str] | None = None) -> list[Edge]:
    return sorted(
        (
            edge for edge in graph.edges.values()
            if edge.source in source_ids and (edge_types is None or edge.type in edge_types)
        ),
        key=lambda edge: edge.id,
    )


def _reachable(graph: CapabilityGraph, start: str) -> set[str]:
    found = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for edge in _outgoing(graph, {current}):
            if edge.target not in found:
                found.add(edge.target)
                queue.append(edge.target)
    return found


def _route_state(graph: CapabilityGraph, route: Node) -> str:
    scope = _reachable(graph, route.id)
    if any(edge.type == "blocked_by" and edge.source in scope for edge in graph.edges.values()):
        return "blocked"
    if any(edge.type == "supersedes" and edge.target == route.id for edge in graph.edges.values()):
        return "superseded"
    return "current"


def _refuse_blocked(graph: CapabilityGraph, route: Node, query_name: str) -> None:
    if query_name != "route-status" and _route_state(graph, route) == "blocked":
        raise QueryRefusedError(f"blocked: route {route.id!r} is blocked")


def _targets(graph: CapabilityGraph, edges: list[Edge]) -> list[dict[str, Any]]:
    return [_summary(graph.nodes[edge.target]) for edge in edges]


def _relation_targets(graph: CapabilityGraph, edges: list[Edge]) -> list[dict[str, Any]]:
    return [
        {"relation": edge.type, "permission": _summary(graph.nodes[edge.target])}
        for edge in edges
    ]


def _scope_edges(graph: CapabilityGraph, route: Node, edge_type: str) -> list[Edge]:
    return _outgoing(graph, _reachable(graph, route.id), {edge_type})


def _q_handle(graph: CapabilityGraph, route: Node) -> dict[str, Any]:
    edges = _scope_edges(graph, route, "routes_to")
    if not edges:
        raise QueryRefusedError(f"unroutable: route {route.id!r} has no routes_to edge")
    return {"handlers": _targets(graph, edges)}


def _q_repository(graph: CapabilityGraph, route: Node) -> dict[str, Any]:
    explicit = route.attributes.get("repository_id")
    repositories: list[Node] = []
    if explicit and explicit in graph.nodes and graph.nodes[str(explicit)].type == "repository":
        repositories.append(graph.nodes[str(explicit)])
    if not repositories:
        source_repo = route.provenance.source_repo
        repositories = [
            node for node in graph.nodes.values()
            if node.type == "repository"
            and (
                node.provenance.source_repo == source_repo
                or node.attributes.get("name") == source_repo
            )
        ]
    return {"repositories": [_summary(node) for node in sorted(repositories, key=lambda node: node.id)]}


def _same_repo_authorities(graph: CapabilityGraph, route: Node) -> set[str]:
    return {
        node.id for node in graph.nodes.values()
        if node.type == "authority" and node.provenance.source_repo == route.provenance.source_repo
    }


def _q_reads(graph: CapabilityGraph, route: Node) -> dict[str, Any]:
    sources = _reachable(graph, route.id) | _same_repo_authorities(graph, route)
    edges = _outgoing(graph, sources, {"reads"})
    return {"context_sources": _targets(graph, edges)}


def _q_model_skill_tool(graph: CapabilityGraph, route: Node) -> dict[str, Any]:
    scope = _reachable(graph, route.id)
    models = _targets(graph, _outgoing(graph, scope, {"uses_model"}))
    skills = _targets(graph, _outgoing(graph, scope, {"uses_skill"}))
    skill_ids = {item["id"] for item in skills}
    tools = _targets(graph, _outgoing(graph, scope | skill_ids, {"uses_tool"}))
    return {"models": models, "skills": skills, "tools": tools}


def _q_permissions(graph: CapabilityGraph, route: Node) -> dict[str, Any]:
    edges = _outgoing(
        graph,
        _reachable(graph, route.id),
        {"may_write", "forbids"},
    )
    return {"permissions": _relation_targets(graph, edges)}


def _q_writes(graph: CapabilityGraph, route: Node) -> dict[str, Any]:
    sources = _reachable(graph, route.id) | _same_repo_authorities(graph, route)
    return {"write_scopes": _targets(graph, _outgoing(graph, sources, {"may_write"}))}


def _q_validators(graph: CapabilityGraph, route: Node) -> dict[str, Any]:
    return {"validators": _targets(graph, _scope_edges(graph, route, "validated_by"))}


def _q_fallback(graph: CapabilityGraph, route: Node) -> dict[str, Any]:
    return {"fallbacks": _targets(graph, _scope_edges(graph, route, "falls_back_to"))}


def _q_human(graph: CapabilityGraph, route: Node) -> dict[str, Any]:
    return {"human_gates": _targets(graph, _scope_edges(graph, route, "escalates_to"))}


def _route_paths(graph: CapabilityGraph, route: Node) -> list[dict[str, Any]]:
    route_edges = {edge.id: edge for edge in graph.edges.values() if edge.type == "routes_to"}
    outgoing: dict[str, list[Edge]] = {}
    for edge in route_edges.values():
        outgoing.setdefault(edge.source, []).append(edge)
    for edges in outgoing.values():
        edges.sort(key=lambda edge: edge.id)
    paths: list[dict[str, Any]] = []

    def walk(node_id: str, node_ids: list[str], edges: list[Edge]) -> None:
        next_edges = outgoing.get(node_id, [])
        if not next_edges:
            if edges:
                paths.append({
                    "nodes": [_summary(graph.nodes[item]) for item in node_ids],
                    "edges": [_edge_record(edge) for edge in edges],
                })
            return
        for edge in next_edges:
            walk(edge.target, [*node_ids, edge.target], [*edges, edge])

    walk(route.id, [route.id], [])
    return paths


def _q_why(graph: CapabilityGraph, route: Node) -> dict[str, Any]:
    paths = _route_paths(graph, route)
    if not paths:
        raise QueryRefusedError(
            f"unroutable: route {route.id!r} has no edge-supported provenance path"
        )
    return {"paths": paths}


def _q_status(graph: CapabilityGraph, route: Node) -> dict[str, Any]:
    return {"status": _route_state(graph, route)}


_IMPLEMENTATIONS: dict[str, Callable[[CapabilityGraph, Node], dict[str, Any]]] = {
    "what-should-handle": _q_handle,
    "which-repository-owns": _q_repository,
    "what-must-be-read-first": _q_reads,
    "which-model-skill-tool": _q_model_skill_tool,
    "which-permissions-required": _q_permissions,
    "what-may-be-written": _q_writes,
    "which-validator-proves-completion": _q_validators,
    "what-fallback-applies": _q_fallback,
    "which-human-decision-required": _q_human,
    "why-route-selected": _q_why,
    "route-status": _q_status,
}


def execute_query(
    db_path: Path,
    question: str,
    *,
    route_id: str | None = None,
    request: str | None = None,
    allow_stale: bool = False,
    sources: list[Path] | None = None,
) -> dict[str, Any]:
    graph, _records = load_graph(Path(db_path))
    freshness = check_freshness(Path(db_path), sources)
    if freshness.freshness is GraphFreshness.STALE and not allow_stale:
        raise StaleGraphError("stale graph refused; pass --allow-stale to inspect labelled results")
    query_name = _normalize_question(question)
    route = resolve_route(graph, route_id, request)
    _refuse_blocked(graph, route, query_name)
    graph_edge_counts = Counter(edge.type for edge in graph.edges.values())
    scoped_edge_types = QUERY_EDGE_TYPES[query_name]
    edge_counts = {
        edge_type: graph_edge_counts.get(edge_type, 0)
        for edge_type in scoped_edge_types
    }
    missing_edge_types = [
        edge_type for edge_type, count in edge_counts.items() if count == 0
    ]
    computation = {
        "state": "not-computed" if missing_edge_types else "computed",
        "reason": "no-such-relation" if missing_edge_types else None,
        "edge_types": edge_counts,
        "missing_edge_types": missing_edge_types,
    }
    return {
        "query": query_name,
        "route_id": route.id,
        "freshness": freshness.freshness.value,
        "computation": computation,
        "result": (
            None
            if missing_edge_types
            else _IMPLEMENTATIONS[query_name](graph, route)
        ),
    }


def explain_route(
    db_path: Path,
    route_id: str,
    *,
    allow_stale: bool = False,
    sources: list[Path] | None = None,
) -> dict[str, Any]:
    return execute_query(
        db_path,
        "why-route-selected",
        route_id=route_id,
        allow_stale=allow_stale,
        sources=sources,
    )

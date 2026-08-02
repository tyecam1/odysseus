"""Adapter for Markdown agent-task packets using schema v1 or v2 frontmatter."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

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


_TASK_SUFFIX = ".agent-task.md"
_SCHEMAS = frozenset({"agent-task/v1", "agent-task/v2"})
_VERIFICATION_ROUTES = frozenset({
    "V0_AUTO",
    "V1_LLM_VERIFIED",
    "V2_HUMAN_VERIFIED",
    "V3_BLOCKED",
})
_V2_ARCHITECTURES = frozenset({
    "single",
    "single-plus-verifier",
    "coordinated-2",
    "parallel-n",
})
_V2_EXECUTION_HOSTS = frozenset({"laptop", "compute-box", "cloud"})
_REQUIRED_STRINGS = (
    "task_id",
    "title",
    "status",
    "priority",
    "task_type",
    "executor",
    "verification_route",
    "risk_level",
)
_CAPABILITY_BOOLEANS = (
    "requires_remote_compute",
    "requires_local_model",
    "requires_zotero",
    "requires_mcp",
    "requires_web",
    "source_traceability_required",
)
_OPTIONAL_LISTS = (
    "allowed_paths",
    "denied_paths",
    "inputs",
    "outputs",
    "supersedes",
    "duplicates",
)


def _candidate(path: Path) -> bool:
    """Select named packets plus grandfathered packets with explicit schema markers."""
    if not path.is_file():
        return False
    named_packet = path.name.lower().endswith(_TASK_SUFFIX)
    try:
        with path.open("r", encoding="utf-8") as handle:
            prefix = handle.read(64 * 1024)
    except (OSError, UnicodeError):
        return False
    frontmatter_match = re.match(r"^---\s*\r?\n(.*?)\r?\n---(?:\r?\n|$)", prefix, re.DOTALL)
    if not frontmatter_match:
        return False
    frontmatter = frontmatter_match.group(1)
    artifact_match = re.search(
        r"(?m)^artifact_type:\s*['\"]?(agent-task|workflow)['\"]?\s*(?:#.*)?$",
        frontmatter,
    )
    schema_match = re.search(
        r"(?m)^task_schema:\s*['\"]?(agent-task/[^'\"\s#]+)['\"]?\s*(?:#.*)?$",
        frontmatter,
    )
    if artifact_match and schema_match and schema_match.group(1) in _SCHEMAS:
        return True
    # A packet-shaped filename with either explicit task marker is parsed
    # fail-closed so malformed schema/content cannot disappear from the build.
    return bool(named_packet and (artifact_match or schema_match))


def _required_string(document: Mapping[str, Any], key: str, path: Path) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AdapterError(f"agent_task_adapter: {path} requires non-empty {key}")
    return value.strip()


def _optional_string_list(
    value: Any,
    label: str,
    path: Path,
    *,
    allow_labeled_references: bool = False,
) -> list[str]:
    """Normalize omitted/YAML-null lists while rejecting present wrong types."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise AdapterError(f"agent_task_adapter: {path} {label} must be a list")
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
            continue
        if allow_labeled_references and isinstance(item, Mapping) and len(item) == 1:
            reference_label, reference_value = next(iter(item.items()))
            if (
                isinstance(reference_label, str)
                and reference_label.strip()
                and isinstance(reference_value, (str, int, float))
                and not isinstance(reference_value, bool)
                and str(reference_value).strip()
            ):
                result.append(f"{reference_label.strip()}: {str(reference_value).strip()}")
                continue
        raise AdapterError(
            f"agent_task_adapter: {path} {label} must contain only non-empty strings"
        )
    return result


def _named_validators(document: Mapping[str, Any], path: Path) -> list[tuple[str, str]]:
    raw = document.get("validators", document.get("validator"))
    if raw is None:
        return []
    values = raw if isinstance(raw, list) else [raw]
    result: list[tuple[str, str]] = []
    for index, value in enumerate(values):
        if isinstance(value, str) and value.strip():
            name = value.strip()
            result.append((f"validator:named:{stable_id(name)}", name))
            continue
        if isinstance(value, Mapping):
            name = value.get("name")
            validator_id = value.get("id")
            if isinstance(name, str) and name.strip():
                normalized_id = (
                    str(validator_id).strip()
                    if isinstance(validator_id, str) and validator_id.strip()
                    else f"validator:named:{stable_id(name)}"
                )
                result.append((normalized_id, name.strip()))
                continue
        raise AdapterError(
            f"agent_task_adapter: {path} validator {index} must have a non-empty name"
        )
    return result


def _human_gates(document: Mapping[str, Any], path: Path) -> list[str]:
    raw = document.get("human_gates", document.get("human_gate"))
    if raw is None:
        return []
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list):
        values = raw
    else:
        raise AdapterError(
            f"agent_task_adapter: {path} human_gates must be a string or list"
        )
    if not all(isinstance(item, str) and item.strip() for item in values):
        raise AdapterError(
            f"agent_task_adapter: {path} human_gates must contain non-empty strings"
        )
    return [str(item).strip() for item in values]


def _validate_packet(
    document: Mapping[str, Any],
    path: Path,
    *,
    default_repo: str,
) -> dict[str, Any]:
    artifact_type = document.get("artifact_type")
    if artifact_type not in {"agent-task", "workflow"}:
        raise AdapterError(
            f"agent_task_adapter: {path} artifact_type must be agent-task or workflow"
        )
    schema = document.get("task_schema")
    if schema not in _SCHEMAS:
        raise AdapterError(
            f"agent_task_adapter: {path} has unsupported or missing task_schema"
        )
    values = {key: _required_string(document, key, path) for key in _REQUIRED_STRINGS}
    for key, fallback in (("execution_mode", "unspecified"), ("repo", default_repo)):
        raw = document.get(key)
        if raw is None and schema == "agent-task/v1":
            values[key] = fallback
        else:
            values[key] = _required_string(document, key, path)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*", values["task_id"]):
        raise AdapterError(f"agent_task_adapter: {path} has invalid task_id")
    if values["verification_route"] not in _VERIFICATION_ROUTES:
        raise AdapterError(f"agent_task_adapter: {path} has invalid verification_route")
    if not isinstance(document.get("approval_required"), bool):
        raise AdapterError(f"agent_task_adapter: {path} approval_required must be boolean")
    values["approval_required"] = document["approval_required"]
    for key in _CAPABILITY_BOOLEANS:
        raw = document.get(key)
        if raw is None and schema == "agent-task/v1":
            values[key] = False
        elif not isinstance(raw, bool):
            raise AdapterError(f"agent_task_adapter: {path} {key} must be boolean")
        else:
            values[key] = raw
    for key in _OPTIONAL_LISTS:
        values[key] = _optional_string_list(
            document.get(key),
            key,
            path,
            allow_labeled_references=key in {"inputs", "outputs"},
        )
    result_path = document.get("result_path")
    if result_path is None:
        values["result_path"] = ""
    elif not isinstance(result_path, str):
        raise AdapterError(f"agent_task_adapter: {path} result_path must be a string")
    else:
        values["result_path"] = result_path.strip()

    if schema == "agent-task/v2":
        architecture = document.get("architecture")
        if architecture is not None and architecture not in _V2_ARCHITECTURES:
            raise AdapterError(f"agent_task_adapter: {path} has invalid architecture")
        execution_host = document.get("execution_host")
        if execution_host is not None and execution_host not in _V2_EXECUTION_HOSTS:
            raise AdapterError(f"agent_task_adapter: {path} has invalid execution_host")
        if architecture and architecture != "single":
            reason = document.get("coordination_reason")
            if not isinstance(reason, str) or not reason.strip():
                raise AdapterError(
                    f"agent_task_adapter: {path} coordinated architecture requires coordination_reason"
                )
    return values


class AgentTaskAdapter(SourceAdapter):
    name = "agent_task_adapter"
    node_types = frozenset({
        "task_class",
        "action",
        "precondition",
        "validator",
        "artifact",
        "permission",
        "context_source",
        "human_gate",
        "repository",
        "model_profile",
    })
    edge_types = frozenset({
        "routes_to",
        "requires",
        "may_write",
        "forbids",
        "reads",
        "produces",
        "validated_by",
        "escalates_to",
        "uses_model",
    })

    def discover(self, root: Path) -> tuple[Path, ...]:
        return tuple(sorted(
            (path for path in root.rglob("*.md") if _candidate(path)),
            key=lambda path: path.relative_to(root).as_posix(),
        ))

    def parse(self, path: Path, identity: SourceIdentity) -> AdapterResult:
        text = read_source(path, self.name)
        document, _body = split_frontmatter(text, str(path))
        values = _validate_packet(document, path, default_repo=identity.source_repo)
        provenance = provenance_for(path, identity, self.name, self.version)

        task_id = values["task_id"]
        task_class_id = f"task-class:{stable_id(values['task_type'])}"
        action_id = f"action:{stable_id(task_id)}"
        repository_id = f"repository:{stable_id(values['repo'])}"
        executor_id = f"model:executor:{stable_id(values['executor'])}"
        relative = path.relative_to(identity.root).as_posix()

        task_attributes = {
            "name": values["task_type"],
        }
        action_attributes: dict[str, Any] = {
            "name": values["title"],
            "task_id": task_id,
            "task_schema": document["task_schema"],
            "packet_path": relative,
            "status": values["status"],
            "priority": values["priority"],
            "execution_mode": values["execution_mode"],
            "risk_level": values["risk_level"],
            "repository_id": repository_id,
        }
        for key in ("architecture", "execution_host"):
            if key in document:
                action_attributes[key] = document[key]

        nodes: list[Node] = [
            Node(task_class_id, "task_class", task_attributes, provenance),
            Node(action_id, "action", action_attributes, provenance),
            Node(repository_id, "repository", {"name": values["repo"]}, provenance),
            Node(
                executor_id,
                "model_profile",
                {"name": values["executor"], "kind": "executor"},
                provenance,
            ),
        ]
        edges: list[Edge] = [
            Edge(
                edge_id("routes_to", task_class_id, action_id),
                "routes_to",
                task_class_id,
                action_id,
                {},
                provenance,
            ),
            Edge(
                edge_id("uses_model", action_id, executor_id),
                "uses_model",
                action_id,
                executor_id,
                {},
                provenance,
            ),
        ]

        for ordinal, capability_field in enumerate(_CAPABILITY_BOOLEANS):
            if not values[capability_field]:
                continue
            capability = capability_field.removeprefix("requires_").removesuffix(
                "_required"
            )
            precondition_id = (
                f"precondition:{stable_id(task_id)}:{stable_id(capability_field)}"
            )
            nodes.append(Node(
                precondition_id,
                "precondition",
                {
                    "name": capability_field.replace("_", " "),
                    "capability": capability,
                    "source_field": capability_field,
                },
                provenance,
            ))
            edges.append(Edge(
                edge_id("requires", action_id, precondition_id, ordinal),
                "requires",
                action_id,
                precondition_id,
                {"source_field": capability_field},
                provenance,
            ))

        for edge_type, node_type, items in (
            ("may_write", "permission", values["allowed_paths"]),
            ("forbids", "permission", values["denied_paths"]),
            ("reads", "context_source", values["inputs"]),
        ):
            for ordinal, item in enumerate(sorted(set(items))):
                node_id = (
                    f"{node_type}:{stable_id(task_id)}:{edge_type}:{stable_id(item)}"
                )
                attributes = {"path": item}
                if node_type == "permission":
                    attributes["mode"] = edge_type
                nodes.append(Node(node_id, node_type, attributes, provenance))
                edges.append(Edge(
                    edge_id(edge_type, action_id, node_id, ordinal),
                    edge_type,
                    action_id,
                    node_id,
                    {"path": item},
                    provenance,
                ))

        artifact_roles: dict[str, set[str]] = {}
        for output in values["outputs"]:
            artifact_roles.setdefault(output, set()).add("output")
        if values["result_path"]:
            artifact_roles.setdefault(values["result_path"], set()).add("result")
        for ordinal, artifact in enumerate(sorted(artifact_roles)):
            artifact_id = f"artifact:{stable_id(task_id)}:{stable_id(artifact)}"
            nodes.append(Node(
                artifact_id,
                "artifact",
                {"path": artifact, "roles": sorted(artifact_roles[artifact])},
                provenance,
            ))
            edges.append(Edge(
                edge_id("produces", action_id, artifact_id, ordinal),
                "produces",
                action_id,
                artifact_id,
                {},
                provenance,
            ))

        verification_route = values["verification_route"]
        validator_values = [(
            f"validator:verification-route:{stable_id(verification_route)}",
            verification_route,
        ), *_named_validators(document, path)]
        for ordinal, (validator_id, validator_name) in enumerate(validator_values):
            nodes.append(Node(
                validator_id,
                "validator",
                {"name": validator_name, "kind": "verification_route" if ordinal == 0 else "named"},
                provenance,
            ))
            edges.append(Edge(
                edge_id("validated_by", action_id, validator_id, ordinal),
                "validated_by",
                action_id,
                validator_id,
                {},
                provenance,
            ))

        gate_names = _human_gates(document, path)
        if values["approval_required"]:
            gate_names.append("approval required")
        if "HUMAN" in verification_route:
            gate_names.append(verification_route)
        for ordinal, gate_name in enumerate(sorted(set(gate_names))):
            gate_id = f"human-gate:{stable_id(gate_name)}"
            nodes.append(Node(gate_id, "human_gate", {"decision": gate_name}, provenance))
            edges.append(Edge(
                edge_id("escalates_to", action_id, gate_id, ordinal),
                "escalates_to",
                action_id,
                gate_id,
                {},
                provenance,
            ))

        return AdapterResult(tuple(nodes), tuple(edges), (path,))


adapter = AgentTaskAdapter()

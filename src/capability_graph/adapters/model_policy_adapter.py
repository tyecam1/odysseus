"""Adapter for routing/model-execution policy YAML."""

from __future__ import annotations

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
from .yaml_subset import parse_yaml_subset


_NAMES = frozenset({
    "model-policy.yaml",
    "model-policy.yml",
    "model_policy.yaml",
    "model_policy.yml",
    "model-routing.yaml",
    "model-routing.yml",
    "model_execution_policy.yaml",
    "model_execution_policy.yml",
})


def _profiles(value: Any) -> list[tuple[str, dict[str, Any]]]:
    if isinstance(value, Mapping):
        return [
            (str(profile_id), dict(attrs) if isinstance(attrs, Mapping) else {"model": attrs})
            for profile_id, attrs in value.items()
        ]
    if isinstance(value, list):
        result = []
        for item in value:
            if not isinstance(item, Mapping) or not item.get("id"):
                raise AdapterError("model_policy_adapter: every model profile requires id")
            result.append((str(item["id"]), {str(k): v for k, v in item.items() if k != "id"}))
        return result
    raise AdapterError("model_policy_adapter: model_profiles must be a mapping or list")


def _routes(value: Any) -> list[tuple[str, str]]:
    if isinstance(value, Mapping):
        return [(str(source), str(profile)) for source, profile in value.items()]
    if isinstance(value, list):
        result = []
        for item in value:
            if not isinstance(item, Mapping):
                raise AdapterError("model_policy_adapter: route must be a mapping")
            source = item.get("route_id", item.get("task_class", item.get("action")))
            profile = item.get("model_profile", item.get("profile"))
            if not source or not profile:
                raise AdapterError("model_policy_adapter: route requires route_id/task_class and model_profile")
            result.append((str(source), str(profile)))
        return result
    raise AdapterError("model_policy_adapter: routes must be a mapping or list")


class ModelPolicyAdapter(SourceAdapter):
    name = "model_policy_adapter"
    node_types = frozenset({"model_profile"})
    edge_types = frozenset({"uses_model"})

    def discover(self, root: Path) -> tuple[Path, ...]:
        return tuple(sorted(
            (path for path in root.rglob("*") if path.is_file() and path.name.lower() in _NAMES),
            key=lambda path: path.relative_to(root).as_posix(),
        ))

    def parse(self, path: Path, identity: SourceIdentity) -> AdapterResult:
        text = read_source(path, self.name)
        document = parse_yaml_subset(text, str(path))
        if not isinstance(document, Mapping):
            raise AdapterError(f"{self.name}: policy must be a mapping")
        version = document.get("schema_version", document.get("version"))
        if version not in {1, "1", "v1"}:
            raise AdapterError(f"{self.name}: unsupported or missing schema_version")
        provenance = provenance_for(path, identity, self.name, self.version)

        # Retain the original compact routing shape as a supported explicit
        # format, but parse the external repository's execution-policy shape
        # directly when it declares roles/subscriptions/compute_box.
        if "model_profiles" in document or "routes" in document:
            if "model_profiles" not in document or "routes" not in document:
                raise AdapterError(f"{self.name}: model_profiles and routes are both required")
            profiles = _profiles(document["model_profiles"])
            routes = _routes(document["routes"])
            if not profiles or not routes:
                raise AdapterError(f"{self.name}: model_profiles and routes must be non-empty")
            nodes: list[Node] = []
            profile_ids: set[str] = set()
            for profile_id, attributes in profiles:
                normalized_id = profile_id if profile_id.startswith("model:") else f"model:{stable_id(profile_id)}"
                if not attributes.get("model"):
                    raise AdapterError(f"{self.name}: profile {profile_id!r} requires model")
                nodes.append(Node(normalized_id, "model_profile", attributes, provenance))
                profile_ids.add(normalized_id)
            edges: list[Edge] = []
            for ordinal, (source, profile) in enumerate(routes):
                target = profile if profile.startswith("model:") else f"model:{stable_id(profile)}"
                if target not in profile_ids:
                    raise AdapterError(f"{self.name}: route references unknown profile {profile!r}")
                edges.append(Edge(
                    edge_id("uses_model", source, target, ordinal),
                    "uses_model",
                    source,
                    target,
                    {},
                    provenance,
                ))
            return AdapterResult(tuple(nodes), tuple(edges), (path,))

        if not any(key in document for key in ("roles", "subscriptions", "compute_box")):
            raise AdapterError(
                f"{self.name}: policy requires model_profiles/routes or execution-policy sections"
            )

        nodes: list[Node] = []
        edges: list[Edge] = []
        roles = document.get("roles")
        if roles is not None:
            if not isinstance(roles, Mapping) or not roles:
                raise AdapterError(f"{self.name}: roles must be a non-empty mapping")
            for role_name, attributes in roles.items():
                if role_name == "preference_order":
                    if not (
                        isinstance(attributes, list)
                        and all(isinstance(item, str) and item.strip() for item in attributes)
                    ):
                        raise AdapterError(
                            f"{self.name}: roles.preference_order must be a list of strings"
                        )
                    continue
                if not isinstance(attributes, Mapping):
                    raise AdapterError(f"{self.name}: role {role_name!r} must be a mapping")
                role_id = f"model:role:{stable_id(str(role_name))}"
                nodes.append(Node(
                    role_id,
                    "model_profile",
                    {"name": str(role_name), "kind": "role", **dict(attributes)},
                    provenance,
                ))

        subscriptions = document.get("subscriptions")
        if subscriptions is not None:
            if not isinstance(subscriptions, Mapping) or not subscriptions:
                raise AdapterError(f"{self.name}: subscriptions must be a non-empty mapping")
            for subscription_name, attributes in subscriptions.items():
                if not isinstance(attributes, Mapping):
                    raise AdapterError(
                        f"{self.name}: subscription {subscription_name!r} must be a mapping"
                    )
                subscription_id = f"model:subscription:{stable_id(str(subscription_name))}"
                nodes.append(Node(
                    subscription_id,
                    "model_profile",
                    {"name": str(subscription_name), "kind": "subscription", **dict(attributes)},
                    provenance,
                ))
                required_model = attributes.get("model_required")
                if required_model is not None:
                    if not isinstance(required_model, str) or not required_model.strip():
                        raise AdapterError(
                            f"{self.name}: subscription {subscription_name!r} model_required must be a string"
                        )
                    model_id = f"model:{stable_id(required_model)}"
                    nodes.append(Node(
                        model_id,
                        "model_profile",
                        {"name": required_model, "kind": "model"},
                        provenance,
                    ))
                    edges.append(Edge(
                        edge_id("uses_model", subscription_id, model_id),
                        "uses_model",
                        subscription_id,
                        model_id,
                        {},
                        provenance,
                    ))

        compute_box = document.get("compute_box")
        if compute_box is not None:
            if not isinstance(compute_box, Mapping):
                raise AdapterError(f"{self.name}: compute_box must be a mapping")
            allowlist = compute_box.get("model_allowlist")
            if not (
                isinstance(allowlist, list)
                and allowlist
                and all(isinstance(item, str) and item.strip() for item in allowlist)
            ):
                raise AdapterError(
                    f"{self.name}: compute_box.model_allowlist must be a non-empty list of strings"
                )
            host_id = "model:execution-host:compute-box"
            nodes.append(Node(
                host_id,
                "model_profile",
                {"name": "compute-box", "kind": "execution_host"},
                provenance,
            ))
            for ordinal, model_name in enumerate(sorted(set(allowlist))):
                model_id = f"model:{stable_id(model_name)}"
                nodes.append(Node(
                    model_id,
                    "model_profile",
                    {"name": model_name, "kind": "model"},
                    provenance,
                ))
                edges.append(Edge(
                    edge_id("uses_model", host_id, model_id, ordinal),
                    "uses_model",
                    host_id,
                    model_id,
                    {},
                    provenance,
                ))

        if not nodes:
            raise AdapterError(f"{self.name}: execution policy emitted no model profiles")
        return AdapterResult(tuple(nodes), tuple(edges), (path,))


adapter = ModelPolicyAdapter()

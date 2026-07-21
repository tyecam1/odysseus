"""Read-only projection of the live Odysseus runtime registry.

The projection deliberately keeps discovery summaries small. Potentially large
tool schemas and skill instructions are only returned by ``detail`` and no
provider is imported or executed as part of discovery.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import yaml

from .capabilities import CapabilityRegistry
from .models import (
    RegistryAvailability,
    RegistryEntryDetail,
    RegistryEntryKind,
    RegistryEntrySummary,
    RegistryProvenance,
    RegistryRisk,
)


DatabaseReader = Callable[[], Mapping[str, list[Mapping[str, Any]]]]
_SAFE_ID = re.compile(r"[^a-z0-9._-]+")
_HIGH_RISK_ACTIONS = {"ssh_command", "run_script", "run_local", "cookbook_serve"}
_EXTERNAL_ACTIONS = {
    "draft_email_replies", "email_auto_translate", "extract_email_events",
    "summarize_emails", "check_email_urgency",
}


def _id_part(value: Any) -> str:
    cleaned = _SAFE_ID.sub("-", str(value or "unknown").casefold()).strip("-._")
    return (cleaned or "unknown")[:100]


def _entry_id(kind: str, *parts: Any) -> str:
    return ":".join([kind, *(_id_part(part) for part in parts)])[:240]


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _bounded_text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _string_list(value: Any, *, limit: int = 24) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item)[:160] for item in value if str(item).strip()][:limit]


def _instructions_from_skill(row: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for heading, field in (
        ("When to use", "when_to_use"),
        ("Procedure", "procedure"),
        ("Pitfalls", "pitfalls"),
        ("Verification", "verification"),
    ):
        value = row.get(field)
        if isinstance(value, list):
            text = "\n".join(f"- {item}" for item in value if str(item).strip())
        else:
            text = _bounded_text(value, 5_000)
        if text:
            parts.append(f"## {heading}\n{text}")
    return "\n\n".join(parts)[:20_000]


def _default_database_reader() -> Mapping[str, list[Mapping[str, Any]]]:
    """Read only non-secret registry columns from the authoritative database."""

    from core.database import McpServer, ModelEndpoint, ScheduledTask, SessionLocal

    session = SessionLocal()
    try:
        return {
            "mcp_servers": [
                {
                    "id": item.id,
                    "name": item.name,
                    "transport": item.transport,
                    "is_enabled": bool(item.is_enabled),
                    "disabled_tools": item.disabled_tools,
                }
                for item in session.query(McpServer).all()
            ],
            "model_runtimes": [
                {
                    "id": item.id,
                    "name": item.name,
                    "is_enabled": bool(item.is_enabled),
                    "cached_models": item.cached_models,
                    "pinned_models": item.pinned_models,
                    "model_type": item.model_type,
                    "endpoint_kind": item.endpoint_kind,
                    "model_refresh_mode": item.model_refresh_mode,
                    "supports_tools": item.supports_tools,
                    "owner": item.owner,
                }
                for item in session.query(ModelEndpoint).all()
            ],
            "automations": [
                {
                    "id": item.id,
                    "name": item.name,
                    "task_type": item.task_type,
                    "action": item.action,
                    "schedule": item.schedule,
                    "trigger_type": item.trigger_type,
                    "trigger_event": item.trigger_event,
                    "status": item.status,
                    "owner": item.owner,
                    "model": item.model,
                    "output_target": item.output_target,
                }
                for item in session.query(ScheduledTask).all()
            ],
        }
    finally:
        session.close()


class UniversalRegistry:
    """Live, deterministic, secret-free projection of runtime definitions."""

    def __init__(
        self,
        *,
        app_root: str | Path,
        data_dir: str | Path,
        capabilities: CapabilityRegistry | None = None,
        skills_manager: Any = None,
        mcp_manager: Any = None,
        memory_provider_registry: Any = None,
        database_reader: DatabaseReader | None = None,
        task_definitions: Mapping[str, str] | None = None,
    ):
        self.app_root = Path(app_root).resolve()
        self.data_dir = Path(data_dir).resolve()
        self.capabilities = capabilities
        self.skills_manager = skills_manager
        self.mcp_manager = mcp_manager
        self.memory_provider_registry = memory_provider_registry
        self.database_reader = database_reader or _default_database_reader
        self.task_definitions = dict(task_definitions) if task_definitions is not None else None
        self._source_errors: dict[str, str] = {}

    @staticmethod
    def _summary(detail: RegistryEntryDetail) -> RegistryEntrySummary:
        return RegistryEntrySummary(**detail.model_dump(exclude={"metadata", "definition_schema", "instructions"}))

    def _project(self) -> dict[str, RegistryEntryDetail]:
        self._source_errors = {}
        database: Mapping[str, list[Mapping[str, Any]]] = {}
        try:
            database = self.database_reader()
        except Exception as exc:  # one unavailable source must not hide the others
            self._source_errors["database"] = f"{type(exc).__name__}: {exc}"[:500]

        groups: Iterable[tuple[str, Callable[[], Iterable[RegistryEntryDetail]]]] = (
            ("capabilities", self._capability_entries),
            ("skills", self._skill_entries),
            ("mcp", lambda: self._mcp_entries(database.get("mcp_servers", []))),
            ("tasks", self._task_entries),
            ("automations", lambda: self._automation_entries(database.get("automations", []))),
            ("memory", self._memory_entries),
            ("models", lambda: self._model_entries(database.get("model_runtimes", []))),
            ("connectors", self._connector_entries),
        )
        projected: dict[str, RegistryEntryDetail] = {}
        for source, provider in groups:
            try:
                for entry in provider():
                    previous = projected.get(entry.id)
                    if previous is not None and previous.model_dump(mode="json") != entry.model_dump(mode="json"):
                        raise ValueError(f"conflicting registry entry id: {entry.id}")
                    projected[entry.id] = entry
            except Exception as exc:
                self._source_errors[source] = f"{type(exc).__name__}: {exc}"[:500]
        return projected

    def search(
        self,
        query: str = "",
        *,
        kind: RegistryEntryKind | str | None = None,
        limit: int = 50,
    ) -> list[RegistryEntrySummary]:
        terms = [term.casefold() for term in str(query or "").split() if term.strip()]
        target_kind = RegistryEntryKind(kind).value if kind is not None else None
        ranked: list[tuple[int, str, RegistryEntrySummary]] = []
        for entry in self._project().values():
            if target_kind is not None and entry.kind != target_kind:
                continue
            haystack = " ".join((entry.id, entry.name, entry.description, " ".join(entry.scope))).casefold()
            score = sum(3 if term in entry.id.casefold() else 1 for term in terms if term in haystack)
            if terms and not score:
                continue
            ranked.append((score, entry.id, self._summary(entry)))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in ranked[:max(1, min(int(limit), 200))]]

    def detail(self, entry_id: str) -> RegistryEntryDetail:
        try:
            return self._project()[entry_id]
        except KeyError as exc:
            raise KeyError(f"unknown registry entry: {entry_id}") from exc

    def entries(self) -> list[RegistryEntryDetail]:
        """Every entry the live projection can currently produce.

        Uncapped and unranked, unlike ``search``: callers resolving declarations
        need the whole projection, not a discovery slice of it.
        """

        return list(self._project().values())

    def entry_ids(self) -> set[str]:
        """Ids the live projection can currently produce, with no size cap.

        ``search`` is deliberately limited and ranked for discovery; resolving a
        declared reference must see every entry, so this stays separate.
        """

        return set(self._project())

    def status(self) -> dict[str, Any]:
        entries = self._project().values()
        counts = Counter(str(entry.kind) for entry in entries)
        return {
            "ok": not self._source_errors,
            "entry_count": sum(counts.values()),
            "counts": dict(sorted(counts.items())),
            "source_errors": dict(self._source_errors),
        }

    def _capability_entries(self) -> Iterable[RegistryEntryDetail]:
        if self.capabilities is None:
            return []
        entries = []
        for summary in self.capabilities.search(limit=100):
            detail = self.capabilities.detail(summary.id)
            health_state = {
                "healthy": "available", "degraded": "degraded",
                "unavailable": "unavailable", "unknown": "unknown",
            }[detail.health.state]
            entries.append(RegistryEntryDetail(
                id=_entry_id("capability", detail.id),
                kind="capability",
                name=detail.name,
                description=detail.description,
                version=detail.version,
                owner=detail.owner,
                scope=detail.scope,
                availability=RegistryAvailability(state=health_state, detail=detail.health.detail or ""),
                risk=RegistryRisk(
                    level="low" if all(permission.endswith(":read") for permission in detail.permissions) else "medium",
                    reasons=["Invokable runtime capability; permissions are enforced server-side."],
                    permissions=detail.permissions,
                ),
                provenance=[RegistryProvenance(source="capability_registry", reference=item) for item in detail.provenance],
                context_cost=detail.context_cost,
                metadata={
                    "capability_id": detail.id,
                    "licence": detail.licence,
                    "dependencies": detail.dependencies,
                    "target_adapters": detail.target_adapters,
                    "tests": detail.tests,
                    "replacement_status": detail.replacement_status,
                },
                schema={"inputs": detail.inputs_schema, "outputs": detail.outputs_schema},
                instructions=detail.instructions,
            ))
        return entries

    def _skill_entries(self) -> Iterable[RegistryEntryDetail]:
        rows: list[Mapping[str, Any]] = []
        if self.skills_manager is not None:
            rows.extend(self.skills_manager.load_all())
        entries = [self._skill_entry(row, source="runtime_skill_store") for row in rows]

        bundle_root = self.app_root / "integrations"
        if bundle_root.is_dir():
            for path in sorted(bundle_root.glob("*/skills/**/SKILL.md")):
                try:
                    resolved = path.resolve()
                    resolved.relative_to(bundle_root.resolve())
                    if path.stat().st_size > 256_000:
                        continue
                    text = path.read_text(encoding="utf-8")
                    frontmatter: Mapping[str, Any] = {}
                    body = text
                    if text.startswith("---\n") and "\n---\n" in text[4:]:
                        raw, body = text[4:].split("\n---\n", 1)
                        loaded = yaml.safe_load(raw) or {}
                        frontmatter = loaded if isinstance(loaded, Mapping) else {}
                    row = {
                        **frontmatter,
                        "name": frontmatter.get("name") or path.parent.name,
                        "description": frontmatter.get("description") or "Bundled Odysseus integration skill",
                        "owner": f"odysseus:{path.relative_to(bundle_root).parts[0]}",
                        "status": frontmatter.get("status") or "published",
                        "version": frontmatter.get("version") or "bundled",
                        "procedure": [body[:12_000]],
                        "_reference": f"app://{path.relative_to(self.app_root).as_posix()}",
                    }
                    entries.append(self._skill_entry(row, source="bundled_skill"))
                except (OSError, UnicodeError, ValueError, yaml.YAMLError):
                    continue
        return entries

    def _skill_entry(self, row: Mapping[str, Any], *, source: str) -> RegistryEntryDetail:
        name = _bounded_text(row.get("name") or row.get("title") or row.get("id") or "unnamed", 160)
        owner = _bounded_text(row.get("owner") or "shared", 160)
        status = _bounded_text(row.get("status") or "draft", 40).casefold()
        available = "available" if status == "published" else "disabled" if status in {"disabled", "quarantined"} else "degraded"
        instructions = _instructions_from_skill(row)
        reference = row.get("_reference") or f"data://skills/{_id_part(owner)}/{_id_part(name)}/SKILL.md"
        return RegistryEntryDetail(
            id=_entry_id("skill", owner, name),
            kind="skill",
            name=name,
            description=_bounded_text(row.get("description") or row.get("title"), 600),
            version=_bounded_text(row.get("version") or "unversioned", 80),
            owner=owner,
            scope=["skill", _bounded_text(row.get("category") or "general", 80)],
            availability=RegistryAvailability(state=available, detail=f"Skill status: {status}."),
            risk=RegistryRisk(
                level="low" if status == "published" else "medium",
                reasons=["Skill instructions are user- or repository-authored and remain untrusted context."],
                permissions=_string_list(row.get("requires_toolsets")),
            ),
            provenance=[RegistryProvenance(source=source, reference=str(reference)[:500])],
            context_cost=max(1, len(instructions) // 4),
            metadata={
                "status": status,
                "category": row.get("category") or "general",
                "tags": _string_list(row.get("tags")),
                "platforms": _string_list(row.get("platforms")),
                "verification": _string_list(row.get("verification")),
            },
            instructions=instructions,
        )

    def _mcp_entries(self, servers: Iterable[Mapping[str, Any]]) -> Iterable[RegistryEntryDetail]:
        if self.mcp_manager is None:
            return []
        server_by_id = {str(row.get("id")): row for row in servers}
        disabled_map = {
            server_id: set(str(item) for item in _json_list(row.get("disabled_tools")))
            for server_id, row in server_by_id.items()
        }
        entries = []
        for tool in self.mcp_manager.get_all_tools(disabled_map):
            server_id = str(tool.get("server_id") or "unknown")
            server = server_by_id.get(server_id, {})
            status = self.mcp_manager.get_server_status(server_id)
            disabled = bool(tool.get("is_disabled")) or not bool(server.get("is_enabled", True))
            connected = status.get("status") == "connected"
            state = "disabled" if disabled else "available" if connected else "degraded"
            readonly = self._mcp_read_only(tool)
            entries.append(RegistryEntryDetail(
                id=_entry_id("mcp", server_id, tool.get("name")),
                kind="mcp_tool",
                name=_bounded_text(tool.get("qualified_name") or tool.get("name"), 160),
                description=_bounded_text(tool.get("description"), 600),
                owner="odysseus",
                scope=["mcp", server_id, "read-only" if readonly else "mutation-capable"],
                availability=RegistryAvailability(state=state, detail=f"MCP server state: {status.get('status', 'unknown')}"),
                risk=RegistryRisk(
                    level="low" if readonly else "high",
                    reasons=["MCP tool is classified read-only." if readonly else "MCP tool may cause external or persistent changes."],
                    permissions=["mcp:invoke", "external:read" if readonly else "external:write"],
                ),
                provenance=[RegistryProvenance(source="mcp_manager", reference=f"database://mcp_servers/{server_id}")],
                context_cost=max(1, len(json.dumps(tool.get("input_schema") or {}, default=str)) // 4),
                metadata={
                    "server_id": server_id,
                    "server_name": tool.get("server_name") or server.get("name") or server_id,
                    "transport": server.get("transport") or "unknown",
                    "read_only": readonly,
                },
                schema=dict(tool.get("input_schema") or {}),
            ))
        return entries

    @staticmethod
    def _mcp_read_only(tool: Mapping[str, Any]) -> bool:
        try:
            from src.mcp_manager import mcp_tool_is_readonly
            return bool(mcp_tool_is_readonly(dict(tool)))
        except Exception:
            name = str(tool.get("name") or "").casefold()
            return name.startswith(("get", "list", "read", "search", "find", "inspect", "view"))

    def _task_entries(self) -> Iterable[RegistryEntryDetail]:
        definitions = self.task_definitions
        if definitions is None:
            from src.builtin_actions import BUILTIN_ACTION_INFO
            definitions = BUILTIN_ACTION_INFO
        entries = []
        for name, description in sorted(definitions.items()):
            if name in _HIGH_RISK_ACTIONS:
                risk = RegistryRisk(
                    level="high", reasons=["Definition can execute code, launch services, or reach another host."],
                    permissions=["task:execute", "host:write"],
                )
            elif name in _EXTERNAL_ACTIONS:
                risk = RegistryRisk(
                    level="medium", reasons=["Definition reads or prepares data for an external service."],
                    permissions=["task:execute", "external:read"],
                )
            else:
                risk = RegistryRisk(
                    level="low", reasons=["Definition is bounded to an Odysseus maintenance workflow."],
                    permissions=["task:execute"],
                )
            entries.append(RegistryEntryDetail(
                id=_entry_id("task-definition", name),
                kind="task_definition",
                name=name,
                description=_bounded_text(description, 600),
                owner="odysseus",
                scope=["automation", "builtin-action"],
                availability=RegistryAvailability(state="available", detail="Registered in BUILTIN_ACTIONS."),
                risk=risk,
                provenance=[RegistryProvenance(source="builtin_action_registry", reference=f"app://src/builtin_actions.py#{name}")],
                metadata={"action": name},
            ))
        return entries

    def _automation_entries(self, rows: Iterable[Mapping[str, Any]]) -> Iterable[RegistryEntryDetail]:
        entries = []
        for row in rows:
            status = str(row.get("status") or "unknown").casefold()
            state = "available" if status == "active" else "disabled" if status in {"paused", "completed"} else "unknown"
            action = str(row.get("action") or "")
            high = action in _HIGH_RISK_ACTIONS
            entries.append(RegistryEntryDetail(
                id=_entry_id("automation", row.get("id")),
                kind="automation",
                name=_bounded_text(row.get("name") or row.get("id"), 160),
                description=f"{row.get('task_type') or 'llm'} automation; trigger={row.get('trigger_type') or 'schedule'}."[:600],
                owner=_bounded_text(row.get("owner") or "shared", 160),
                scope=["automation", str(row.get("trigger_type") or "schedule")[:80]],
                availability=RegistryAvailability(state=state, detail=f"Automation status: {status}."),
                risk=RegistryRisk(
                    level="high" if high else "medium",
                    reasons=["Configured automation can run without an interactive request."],
                    permissions=["task:execute", "host:write"] if high else ["task:execute"],
                ),
                provenance=[RegistryProvenance(source="task_scheduler", reference=f"database://scheduled_tasks/{row.get('id')}")],
                metadata={
                    "task_type": row.get("task_type"), "action": row.get("action"),
                    "schedule": row.get("schedule"), "trigger_type": row.get("trigger_type"),
                    "trigger_event": row.get("trigger_event"), "status": status,
                    "model": row.get("model"), "output_target": row.get("output_target"),
                },
            ))
        return entries

    def _memory_entries(self) -> Iterable[RegistryEntryDetail]:
        if self.memory_provider_registry is None:
            return [RegistryEntryDetail(
                id="memory-system:native",
                kind="memory_system",
                name="Odysseus native memory",
                description="Built-in owner-scoped factual and event memory.",
                owner="odysseus",
                scope=["memory", "owner-scoped"],
                availability=RegistryAvailability(state="unknown", detail="Live provider registry was not supplied."),
                risk=RegistryRisk(level="medium", reasons=["Memory may contain operator-private data."], permissions=["memory:read", "memory:write"]),
                provenance=[RegistryProvenance(source="memory_provider_registry", reference="app://src/memory_provider.py#NativeMemoryProvider")],
                metadata={"provider_id": "native"},
            )]
        entries = []
        for provider in self.memory_provider_registry.all():
            enabled = bool(getattr(provider, "enabled", True))
            vector = getattr(provider, "memory_vector", None)
            healthy = bool(getattr(vector, "healthy", True)) if vector is not None else True
            state = "disabled" if not enabled else "available" if healthy else "degraded"
            schemas = provider.get_tool_schemas()
            entries.append(RegistryEntryDetail(
                id=_entry_id("memory-system", provider.provider_id),
                kind="memory_system",
                name=_bounded_text(provider.display_name, 160),
                description="Provider-neutral staged memory retrieval and persistence.",
                owner="odysseus",
                scope=["memory", "owner-scoped", str(provider.provider_id)[:80]],
                availability=RegistryAvailability(state=state, detail="Provider is enabled." if enabled else "Provider is disabled."),
                risk=RegistryRisk(level="medium", reasons=["Memory may contain operator-private data."], permissions=["memory:read", "memory:write"]),
                provenance=[RegistryProvenance(source="memory_provider_registry", reference=f"runtime://memory/{provider.provider_id}")],
                context_cost=max(1, len(json.dumps(schemas, default=str)) // 4),
                metadata={"provider_id": provider.provider_id, "tool_names": [self._schema_name(item) for item in schemas]},
                schema={"tools": schemas},
            ))
        return entries

    @staticmethod
    def _schema_name(schema: Mapping[str, Any]) -> str:
        function = schema.get("function") if isinstance(schema, Mapping) else None
        return str(schema.get("name") or (function or {}).get("name") or "unknown")

    def _model_entries(self, rows: Iterable[Mapping[str, Any]]) -> Iterable[RegistryEntryDetail]:
        entries = []
        for row in rows:
            enabled = bool(row.get("is_enabled", True))
            runtime_kind = str(row.get("endpoint_kind") or "auto")
            models = [str(item)[:200] for item in [*_json_list(row.get("cached_models")), *_json_list(row.get("pinned_models"))]]
            models = list(dict.fromkeys(models))[:100]
            entries.append(RegistryEntryDetail(
                id=_entry_id("model-runtime", row.get("id")),
                kind="model_runtime",
                name=_bounded_text(row.get("name") or row.get("id"), 160),
                description=f"{row.get('model_type') or 'llm'} model runtime with {len(models)} cached or pinned model(s).",
                owner=_bounded_text(row.get("owner") or "shared", 160),
                scope=["models", str(row.get("model_type") or "llm")[:80], runtime_kind[:80]],
                availability=RegistryAvailability(state="available" if enabled else "disabled", detail="Configured and enabled." if enabled else "Configured but disabled."),
                risk=RegistryRisk(
                    level="low" if runtime_kind == "local" else "medium",
                    reasons=["Model prompts may leave the host." if runtime_kind != "local" else "Runtime is classified as local."],
                    permissions=["model:invoke"],
                ),
                provenance=[RegistryProvenance(source="model_endpoint_registry", reference=f"database://model_endpoints/{row.get('id')}")],
                metadata={
                    "models": models, "model_type": row.get("model_type") or "llm",
                    "endpoint_kind": runtime_kind, "refresh_mode": row.get("model_refresh_mode") or "auto",
                    "supports_tools": row.get("supports_tools"),
                },
            ))
        return entries

    def _connector_entries(self) -> Iterable[RegistryEntryDetail]:
        path = self.data_dir / "integrations.json"
        if not path.is_file():
            return []
        if path.stat().st_size > 2_000_000:
            raise ValueError("integrations registry exceeds the safe projection size")
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ValueError("integrations registry must contain a list")
        entries = []
        for row in loaded:
            if not isinstance(row, Mapping):
                continue
            connector_id = row.get("id") or row.get("name")
            enabled = bool(row.get("enabled", True))
            has_auth = bool(row.get("api_key")) or str(row.get("auth_type") or "none") != "none"
            entries.append(RegistryEntryDetail(
                id=_entry_id("connector", connector_id),
                kind="connector",
                name=_bounded_text(row.get("name") or connector_id, 160),
                description=_bounded_text(row.get("description"), 600),
                owner="odysseus",
                scope=["connector", "network", str(row.get("preset") or "custom")[:80]],
                availability=RegistryAvailability(state="available" if enabled else "disabled", detail="Configured and enabled." if enabled else "Configured but disabled."),
                risk=RegistryRisk(
                    level="high" if has_auth else "medium",
                    reasons=["Connector can make network requests; credentials are retained server-side."],
                    permissions=["network:access", "secret:brokered"] if has_auth else ["network:access"],
                ),
                provenance=[RegistryProvenance(source="integration_registry", reference=f"data://integrations.json#{_id_part(connector_id)}")],
                metadata={
                    "preset": row.get("preset"), "auth_type": row.get("auth_type") or "none",
                    "credentials_configured": has_auth,
                },
            ))
        return entries


def build_universal_registry(
    *,
    app_root: str | Path,
    data_dir: str | Path,
    capabilities: CapabilityRegistry | None = None,
    skills_manager: Any = None,
    mcp_manager: Any = None,
    memory_provider_registry: Any = None,
    database_reader: DatabaseReader | None = None,
    task_definitions: Mapping[str, str] | None = None,
) -> UniversalRegistry:
    return UniversalRegistry(
        app_root=app_root,
        data_dir=data_dir,
        capabilities=capabilities,
        skills_manager=skills_manager,
        mcp_manager=mcp_manager,
        memory_provider_registry=memory_provider_registry,
        database_reader=database_reader,
        task_definitions=task_definitions,
    )

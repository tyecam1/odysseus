"""Read-only, path-confined repository adapters for BBC Odysseus v1."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import yaml
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Mapping, Optional, Protocol, Sequence

from .difficulty import score_difficulty
from .models import (
    AmbiguityCandidate,
    DifficultyComponents,
    PersonaProjection,
    Provenance,
    RepositorySystem,
    WorkNode,
    WorkNodeResolution,
    WorkNodeState,
    WorkStream,
)


READABLE_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".tsv"}
MAX_SOURCE_BYTES = 512_000
MAX_INSPECTION_BYTES = 64_000
MAX_INSPECTION_FILES = 200
MAX_INSPECTION_TOTAL_BYTES = 2_000_000
MAX_PERSONA_REGISTRY_BYTES = 256_000
_FRONTMATTER = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|\Z)", re.S)
_HEADING = re.compile(r"^#\s+(.+?)\s*$", re.M)
_CODE_ALIAS = re.compile(r"\b[A-Z]\d+(?:-[A-Z]\d+)+\b", re.I)
_LINK_PATH = re.compile(r"(?:`|\[\[)([^`\]|#]+\.md)(?:\|[^\]]+)?(?:`|\]\])", re.I)
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----", re.I | re.S)
_TOKEN = re.compile(r"\b(?:sk(?:-proj)?-|ody_)[A-Za-z0-9_-]{12,}\b")
_NAMED_SECRET = re.compile(
    r"(?i)\b(api[ _-]?key|access[ _-]?token|password|passphrase|secret)\b(\s*[:=]\s*)([^\s,;]{4,})"
)


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:80] or "item"


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def redact_sensitive_text(value: str) -> str:
    value = _PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", value)
    value = _TOKEN.sub("[REDACTED TOKEN]", value)
    return _NAMED_SECRET.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value)


def _stable_id(prefix: str, *parts: str) -> str:
    material = "\0".join(parts)
    return f"{prefix}:{hashlib.sha256(material.encode()).hexdigest()[:20]}"


def _clean_scalar(value: str) -> Any:
    value = value.split(" #", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "yes"}:
        return True
    if lowered in {"false", "no"}:
        return False
    if lowered in {"null", "none", "~"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        return [_clean_scalar(item) for item in value[1:-1].split(",") if item.strip()]
    return value


def parse_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    """Parse the small YAML subset used by the three repository work queues.

    It intentionally does not construct arbitrary YAML objects or tags. Unknown
    nested mappings are retained as bounded strings; top-level scalar/list
    fields used by adapters are parsed deterministically.
    """

    match = _FRONTMATTER.match(text)
    if not match:
        return {}, text
    result: Dict[str, Any] = {}
    active_list: Optional[str] = None
    for raw_line in match.group(1).splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        list_match = re.match(r"^\s+-\s+(.+?)\s*$", raw_line)
        if list_match and active_list:
            result.setdefault(active_list, []).append(_clean_scalar(list_match.group(1)))
            continue
        field = re.match(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*$", raw_line)
        if not field:
            active_list = None
            continue
        key, value = field.groups()
        if not value:
            result[key] = []
            active_list = key
        else:
            result[key] = _clean_scalar(value)
            active_list = None
    return result, text[match.end():]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _first_heading(body: str, fallback: str) -> str:
    match = _HEADING.search(body)
    return match.group(1).strip() if match else fallback


def _section(body: str, names: Sequence[str], *, limit: int = 700) -> str:
    wanted = "|".join(re.escape(name) for name in names)
    match = re.search(
        rf"^##+\s+(?:{wanted})\s*$\s*(.*?)(?=^##+\s|\Z)",
        body,
        re.I | re.M | re.S,
    )
    if not match:
        return ""
    text = re.sub(r"\s+", " ", match.group(1)).strip()
    return text[:limit].rstrip()


def _bullets(text: str, names: Sequence[str], *, limit: int = 8) -> list[str]:
    wanted = "|".join(re.escape(name) for name in names)
    match = re.search(
        rf"^##+\s+(?:{wanted})\s*$\s*(.*?)(?=^##+\s|\Z)",
        text,
        re.I | re.M | re.S,
    )
    if not match:
        return []
    return [
        re.sub(r"\s+", " ", item).strip()[:400]
        for item in re.findall(r"^\s*[-*]\s+(?:\[[ xX]\]\s*)?(.+)$", match.group(1), re.M)
    ][:limit]


def _normalise_state(raw: Any, parent: str = "") -> WorkNodeState:
    value = str(raw or parent or "planned").strip().lower().replace("_", "-")
    if value in {"done", "complete", "completed", "closed", "resolved"}:
        return WorkNodeState.completed
    if "supersed" in value:
        return WorkNodeState.superseded
    if value in {"archive", "archived"}:
        return WorkNodeState.archived
    if "blocked" in value or "human-gated" in value:
        return WorkNodeState.blocked
    if value in {"review", "ready-for-review", "ready-to-send", "approval"}:
        return WorkNodeState.review
    if value in {"paused", "pause", "on-hold", "deferred", "proposed"}:
        return WorkNodeState.paused
    if value in {"active", "open", "in-progress", "inbox", "execute", "started"}:
        return WorkNodeState.active
    return WorkNodeState.planned


def _difficulty(
    meta: Mapping[str, Any],
    body: str,
    state: WorkNodeState,
    dependencies: Sequence[str],
    *,
    blocker_count: int = 0,
):
    lowered = body.lower()
    blockers = len(re.findall(r"\b(blocked|blocker|cannot|can't|unavailable|missing)\b", lowered))
    external = bool(re.search(r"\b(human|operator|supervisor|external|vendor|email|send|purchase|lab access)\b", lowered))
    cross_repo = bool(re.search(r"\b(repository|repo|odysseus|misumi|homebase|obsidian)\b", lowered)) and bool(dependencies)
    uncertainty = len(re.findall(r"\b(uncertain|unknown|pending|decide|decision|ambigu|tbd|open question)\b", lowered))
    test_mentions = len(re.findall(r"\b(test|validation|verify|evidence)\b", lowered))
    deploy = bool(re.search(r"\b(deploy|host|device|production|service|lan|mobile)\b", lowered))
    rollback = bool(re.search(r"\b(delete|migrat|replace|rollback|irreversible|secret|credential)\b", lowered))
    complexity = len(body) // 3500 + len(dependencies) * 2
    components = DifficultyComponents(
        blocker_severity=min(100, (35 if state == WorkNodeState.blocked else 0) + blockers * 12),
        blocker_count=min(100, blocker_count),
        external_dependency=65 if external else 0,
        cross_repository_dependency=60 if cross_repo else 0,
        unresolved_uncertainty=min(100, uncertainty * 12),
        test_gap=15 if test_mentions else 60,
        deployment_surface=65 if deploy else 10,
        rollback_risk=60 if rollback else 10,
        implementation_complexity=min(100, 15 + complexity * 8),
    )
    rationale = []
    if state == WorkNodeState.blocked:
        rationale.append("The authoritative source marks this node blocked.")
    if external:
        rationale.append("The source identifies a human or external dependency.")
    if dependencies:
        rationale.append(f"The source references {len(dependencies)} dependency artifact(s).")
    if uncertainty:
        rationale.append("The source contains unresolved decisions or uncertainty.")
    return score_difficulty(components, rationale=rationale)


@dataclass(frozen=True)
class RepositorySnapshot:
    system: RepositorySystem
    streams: tuple[WorkStream, ...]
    nodes: tuple[WorkNode, ...]


@dataclass(frozen=True)
class _NodeDraft:
    node: WorkNode
    dependencies: tuple[str, ...] = ()
    blocked_by: tuple[str, ...] = ()
    blocks: tuple[str, ...] = ()
    parent_work_items: tuple[str, ...] = ()
    body: str = ""
    meta: Mapping[str, Any] | None = None


class RepositoryAdapter(Protocol):
    repository_id: str

    def status(self) -> RepositorySystem: ...
    def snapshot(self) -> RepositorySnapshot: ...
    def resolve(self, query: str) -> WorkNodeResolution: ...
    def inspect(self, *, query: str = "", relative_path: str = "", limit: int = 20) -> Dict[str, Any]: ...


class ReadOnlyRepositoryAdapter(ABC):
    repository_id: str
    display_name: str
    adapter_name: str

    def __init__(self, root: str | Path | None, *, strict: bool = True):
        self._configured = bool(root)
        self._configuration_error: str | None = None
        self.root = Path(root).expanduser().resolve() if root else None
        self._hierarchy_parent_ids: set[str] = set()
        self._index_node_ids: set[str] = set()
        try:
            self._validate_root()
        except ValueError as exc:
            if strict:
                raise
            self._configuration_error = str(exc)
            self.root = None

    def _validate_root(self) -> None:
        if self.root is None:
            return
        if not self.root.is_dir():
            raise ValueError(f"configured {self.repository_id} root is not a directory")
        try:
            result = subprocess.run(
                [
                    "git",
                    "-c",
                    f"safe.directory={self.root}",
                    "-C",
                    str(self.root),
                    "rev-parse",
                    "--show-toplevel",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError(f"configured {self.repository_id} root could not be validated by Git") from exc
        if result.returncode != 0 or not result.stdout.strip():
            raise ValueError(f"configured {self.repository_id} root is not a Git repository")
        top_level = Path(result.stdout.strip()).resolve()
        if os.path.normcase(str(top_level)) != os.path.normcase(str(self.root)):
            raise ValueError(f"configured {self.repository_id} root must be the Git top-level")

    def _resolve_path(self, relative_path: str) -> Path:
        if self.root is None:
            raise FileNotFoundError(f"{self.repository_id} is not configured")
        raw = str(relative_path or "").replace("\\", "/").strip().lstrip("/")
        if not raw or any(part in {"", ".", ".."} or part.startswith(".") for part in raw.split("/")):
            raise ValueError("empty, hidden, and traversal paths are not readable")
        path = (self.root / raw).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("path escapes configured repository") from exc
        if path.suffix.lower() not in READABLE_SUFFIXES:
            raise ValueError("unsupported repository file type")
        return path

    def _revision(self) -> Optional[str]:
        if self.root is None:
            return None
        try:
            result = subprocess.run(
                ["git", "-c", f"safe.directory={self.root}", "-C", str(self.root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            return None

    @abstractmethod
    def source_files(self) -> Iterable[Path]:
        raise NotImplementedError

    @abstractmethod
    def snapshot(self) -> RepositorySnapshot:
        raise NotImplementedError

    def _source_path(self, path: Path) -> str:
        if self.root is None:
            raise FileNotFoundError(self.repository_id)
        resolved = path.resolve()
        try:
            return resolved.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise ValueError("source path escapes configured repository") from exc

    def _read_source(self, path: Path) -> str:
        relative = self._source_path(path)
        safe = self._resolve_path(relative)
        if not safe.is_file():
            raise FileNotFoundError(relative)
        if safe.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("repository source file exceeds adapter limit")
        return safe.read_text(encoding="utf-8", errors="replace")

    def _provenance(self, path: Path, text: str, kind: str, line_start: int | None = None, line_end: int | None = None) -> Provenance:
        return Provenance(
            repository_id=self.repository_id,
            path=redact_sensitive_text(self._source_path(path)),
            line_start=line_start,
            line_end=line_end,
            source_kind=kind,
            content_hash=_hash_text(text),
        )

    def _queue_neutral_source_key(self, relative_path: str) -> str:
        """Return identity that excludes lifecycle queue directories.

        homeBase moves items between ``agent-tasks/<queue>/`` directories and
        Obsidian moves completed items below ``10-inbox/complete/``. Those
        locations describe state, not source identity.
        """

        parts = relative_path.replace("\\", "/").split("/")
        if self.repository_id == "misumi-homebase" and len(parts) >= 3 and parts[0].casefold() == "agent-tasks":
            parts = [parts[0], *parts[2:]]
        elif (
            self.repository_id == "obsidian-phd"
            and len(parts) >= 3
            and parts[0].casefold() == "10-inbox"
            and parts[1].casefold() == "complete"
        ):
            parts = [parts[0], *parts[2:]]
        return "/".join(parts).casefold()

    @staticmethod
    def _explicit_source_id(meta: Mapping[str, Any]) -> str:
        for key in ("source_id", "source-id", "work_item_id", "work-item-id", "task_id", "id"):
            values = _as_list(meta.get(key))
            if values:
                return redact_sensitive_text(values[0])[:240]
        return ""

    @staticmethod
    def _normalise_reference(reference: str) -> str:
        value = redact_sensitive_text(str(reference or "")).strip().strip("`\"'")
        if value.startswith("[[") and value.endswith("]]" ):
            value = value[2:-2].split("|", 1)[0]
        if value.startswith("repo://"):
            value = value.split("/", 3)[-1]
        value = value.split("#", 1)[0].replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        return value.casefold()

    def _reference_link(self, reference: str) -> str | None:
        value = self._normalise_reference(reference)
        if not value or value.startswith("../") or "/../" in f"/{value}":
            return None
        return f"repo://{self.repository_id}/{value}"

    def status(self) -> RepositorySystem:
        if self.root is None:
            return RepositorySystem(
                id=self.repository_id,
                name=self.display_name,
                adapter=self.adapter_name,
                configured=self._configured,
                reachable=False,
                error=self._configuration_error or "repository root is not configured",
            )
        try:
            snapshot = self.snapshot()
            return snapshot.system
        except (OSError, ValueError) as exc:
            return RepositorySystem(
                id=self.repository_id,
                name=self.display_name,
                adapter=self.adapter_name,
                configured=True,
                reachable=False,
                revision=self._revision(),
                error=str(exc)[:240],
            )

    def resolve(self, query: str) -> WorkNodeResolution:
        needle = str(query or "").strip()
        if not needle:
            return WorkNodeResolution(query=needle, status="not_found", reason="A non-empty node title or alias is required.")
        normalized = needle.casefold()
        nodes = self.snapshot().nodes
        matches = [
            node for node in nodes
            if normalized == node.canonical_key.casefold()
            or normalized == node.title.casefold()
            or any(normalized == alias.casefold() for alias in node.aliases)
        ]
        executable_states = {
            WorkNodeState.planned,
            WorkNodeState.active,
            WorkNodeState.paused,
            WorkNodeState.blocked,
            WorkNodeState.review,
        }
        executable = [
            node for node in matches
            if node.state in executable_states and not node.archived and not node.superseded
        ]
        candidates = [
            AmbiguityCandidate(
                node_id=node.id,
                title=node.title,
                state=node.state,
                archived=node.archived,
                superseded=node.superseded,
                provenance=node.provenance,
            )
            for node in matches
        ]
        if len(executable) == 1:
            return WorkNodeResolution(
                query=needle,
                status="resolved",
                canonical_node_id=executable[0].id,
                candidates=candidates,
                reason="Exactly one non-archived source artifact identifies this executable node.",
            )
        hierarchy_matches = [node for node in executable if node.id in self._hierarchy_parent_ids]
        if len(hierarchy_matches) == 1:
            canonical = hierarchy_matches[0]
            evidence = " and is retained by the authoritative backlog index" if canonical.id in self._index_node_ids else ""
            return WorkNodeResolution(
                query=needle,
                status="resolved",
                canonical_node_id=canonical.id,
                candidates=candidates,
                reason=(
                    "Exactly one matching executable node is the explicit parent_work_item "
                    f"of another canonical node{evidence}."
                ),
            )
        if candidates:
            return WorkNodeResolution(
                query=needle,
                status="ambiguous",
                candidates=candidates,
                reason="Multiple authoritative artifacts match; no canonical executable node was guessed.",
            )
        return WorkNodeResolution(query=needle, status="not_found", reason="No authoritative work node matches the query.")

    def inspect(self, *, query: str = "", relative_path: str = "", limit: int = 20) -> Dict[str, Any]:
        bounded_limit = max(1, min(int(limit), 50))
        if relative_path:
            path = self._resolve_path(relative_path)
            allowed = {self._source_path(candidate) for candidate in self.source_files()}
            rel = self._source_path(path)
            if rel not in allowed:
                raise ValueError("path is outside this adapter's authoritative inspection surface")
            if not path.is_file() or path.stat().st_size > MAX_INSPECTION_BYTES:
                raise ValueError("inspection target is missing or exceeds the read limit")
            text = path.read_text(encoding="utf-8", errors="replace")
            return {"repository_id": self.repository_id, "mode": "read", "path": rel, "text": redact_sensitive_text(text)}
        if query:
            terms = [term.casefold() for term in re.findall(r"[A-Za-z0-9_-]{2,}", query)][:12]
            hits = []
            files_scanned = 0
            bytes_scanned = 0
            truncated = False
            for path in self.source_files():
                if files_scanned >= MAX_INSPECTION_FILES:
                    truncated = True
                    break
                size = path.stat().st_size
                if size > MAX_SOURCE_BYTES:
                    continue
                if bytes_scanned + size > MAX_INSPECTION_TOTAL_BYTES:
                    truncated = True
                    break
                text = self._read_source(path)
                files_scanned += 1
                bytes_scanned += size
                for line_number, line in enumerate(text.splitlines(), 1):
                    score = sum(term in line.casefold() for term in terms)
                    if score:
                        hits.append({
                            "path": self._source_path(path),
                            "line": line_number,
                            "score": score,
                            "snippet": redact_sensitive_text(line.strip())[:360],
                        })
            hits.sort(key=lambda hit: (-hit["score"], hit["path"], hit["line"]))
            return {
                "repository_id": self.repository_id,
                "mode": "search",
                "query": redact_sensitive_text(query),
                "hits": hits[:bounded_limit],
                "inspection": {
                    "files_scanned": files_scanned,
                    "bytes_scanned": bytes_scanned,
                    "file_budget": MAX_INSPECTION_FILES,
                    "byte_budget": MAX_INSPECTION_TOTAL_BYTES,
                    "truncated": truncated,
                },
            }
        snapshot = self.snapshot()
        return {
            "repository_id": self.repository_id,
            "mode": "summary",
            "revision": snapshot.system.revision,
            "work_stream_count": len(snapshot.streams),
            "work_node_count": len(snapshot.nodes),
            "source_paths": [self._source_path(path) for path in self.source_files()][:bounded_limit],
        }

    def _node_from_markdown(
        self,
        path: Path,
        *,
        stream_key: str,
        source_kind: str,
        default_state: str = "planned",
    ) -> _NodeDraft:
        text = self._read_source(path)
        # All human-readable WorkNode fields are derived only from redacted text.
        # The provenance hash still identifies the unmodified source bytes.
        raw_meta, _ = parse_frontmatter(text)
        meta, body = parse_frontmatter(redact_sensitive_text(text))
        rel = self._source_path(path)
        safe_rel = redact_sensitive_text(rel)
        title = str(meta.get("title") or _first_heading(body, path.stem.replace("-", " ").title())).strip()
        state = _normalise_state(meta.get("status") or meta.get("state"), default_state)
        location_state = _normalise_state(None, default_state)
        if (
            self.repository_id == "obsidian-phd" and "/complete/" in f"/{rel.casefold()}"
        ) or (
            self.repository_id == "misumi-homebase"
            and default_state.casefold() in {"done", "complete", "completed", "blocked-human", "review"}
        ):
            state = location_state
        raw_dependencies = _as_list(meta.get("dependencies")) + _as_list(meta.get("depends_on"))
        raw_dependencies.extend(
            match.group(1)
            for match in _LINK_PATH.finditer(_section(body, ("Dependencies",), limit=3000))
        )
        blocked_by = _as_list(meta.get("blocked_by"))
        blocked_by.extend(
            match.group(1)
            for match in _LINK_PATH.finditer(_section(body, ("Blockers",), limit=3000))
        )
        parent_work_items = _as_list(meta.get("parent_work_item"))
        blocks = _as_list(meta.get("blocks"))
        outcome = (
            str(meta.get("outcome") or "").strip()
            or _section(body, ("Outcome", "Objective", "Purpose", "What", "Expected output"))
            or title
        )
        next_action = str(meta.get("next_action") or "").strip() or _section(
            body, ("Next action", "Next executable action", "Human tasks", "Implementation phases"), limit=420
        )
        evidence = _as_list(meta.get("acceptance_evidence")) or _bullets(
            body, ("Done when", "Validation checklist", "Validation criteria", "Acceptance evidence")
        )
        explicit_source_id = self._explicit_source_id(meta)
        raw_source_id = ""
        for key in ("source_id", "source-id", "work_item_id", "work-item-id", "task_id", "id"):
            values = _as_list(raw_meta.get(key))
            if values:
                raw_source_id = values[0]
                break
        explicit_aliases = _as_list(meta.get("aliases")) + _as_list(meta.get("alias"))
        authoritative_identifier_text = "\n".join([title, safe_rel, explicit_source_id, *explicit_aliases])
        aliases = {alias.upper() for alias in _CODE_ALIAS.findall(authoritative_identifier_text)}
        aliases.update(redact_sensitive_text(alias)[:240] for alias in explicit_aliases if alias)
        if explicit_source_id:
            aliases.add(explicit_source_id)
            canonical_key = f"source-id:{explicit_source_id.casefold()}"
            identity_material = f"source-id:{raw_source_id.casefold()}"
        else:
            canonical_key = self._queue_neutral_source_key(safe_rel)
            identity_material = self._queue_neutral_source_key(rel)
        archived = state in {WorkNodeState.completed, WorkNodeState.archived} or "/complete/" in f"/{rel.casefold()}"
        superseded = state == WorkNodeState.superseded or "/superseded/" in f"/{rel.casefold()}"
        lineage = _as_list(meta.get("supersedes")) + _as_list(meta.get("superseded_by"))
        stream_id = f"ws:{self.repository_id}:{_slug(stream_key)}"
        related_links = []
        for key in ("related", "source_notes"):
            related_links.extend(_as_list(meta.get(key)))
        source_links = [f"repo://{self.repository_id}/{safe_rel}"]
        source_links.extend(filter(None, (self._reference_link(item) for item in related_links)))
        node = WorkNode(
            id=_stable_id("wn", self.repository_id, identity_material),
            repository_id=self.repository_id,
            stream_id=stream_id,
            canonical_key=canonical_key,
            aliases=sorted(aliases, key=str.casefold),
            title=title[:240],
            outcome=outcome[:800],
            state=state,
            owner=str(meta.get("owner") or meta.get("routed_to") or meta.get("owner_target") or "").strip() or None,
            next_action=next_action[:500] or None,
            blocker_ids=[],
            dependency_ids=[],
            acceptance_evidence=evidence,
            source_links=sorted(set(source_links)),
            provenance=[self._provenance(path, text, source_kind)],
            lineage=lineage,
            archived=archived,
            superseded=superseded,
            difficulty=_difficulty(meta, body, state, (), blocker_count=0),
        )
        return _NodeDraft(
            node=node,
            dependencies=tuple(raw_dependencies),
            blocked_by=tuple(blocked_by),
            blocks=tuple(blocks),
            parent_work_items=tuple(parent_work_items),
            body=body,
            meta=meta,
        )

    def _snapshot(self, items: Sequence[WorkNode | _NodeDraft]) -> RepositorySnapshot:
        if self._configuration_error:
            raise ValueError(self._configuration_error)
        if self.root is None:
            raise FileNotFoundError(f"{self.repository_id} repository root is not configured")
        drafts = [item if isinstance(item, _NodeDraft) else _NodeDraft(node=item) for item in items]

        # A queue move is one source changing lifecycle location, not two nodes.
        # If both paths briefly coexist, prefer the live copy and retain all provenance.
        by_id: Dict[str, list[_NodeDraft]] = {}
        for draft in drafts:
            by_id.setdefault(draft.node.id, []).append(draft)
        merged: list[_NodeDraft] = []
        for same_identity in by_id.values():
            preferred = max(
                same_identity,
                key=lambda draft: (not draft.node.archived, not draft.node.superseded, draft.node.canonical_key),
            )
            provenance = {
                (entry.repository_id, entry.path, entry.line_start, entry.line_end, entry.source_kind, entry.content_hash): entry
                for draft in same_identity for entry in draft.node.provenance
            }
            node = preferred.node.model_copy(update={
                "aliases": sorted({alias for draft in same_identity for alias in draft.node.aliases}, key=str.casefold),
                "source_links": sorted({link for draft in same_identity for link in draft.node.source_links}),
                "provenance": list(provenance.values()),
                "lineage": sorted({item for draft in same_identity for item in draft.node.lineage}),
            })
            merged.append(_NodeDraft(
                node=node,
                dependencies=tuple({ref for draft in same_identity for ref in draft.dependencies}),
                blocked_by=tuple({ref for draft in same_identity for ref in draft.blocked_by}),
                blocks=tuple({ref for draft in same_identity for ref in draft.blocks}),
                parent_work_items=tuple({ref for draft in same_identity for ref in draft.parent_work_items}),
                body=preferred.body,
                meta=preferred.meta,
            ))

        reference_index: Dict[str, set[str]] = {}

        def index(reference: str, node_id: str) -> None:
            key = self._normalise_reference(reference)
            if key:
                reference_index.setdefault(key, set()).add(node_id)

        for draft in merged:
            node = draft.node
            index(node.canonical_key, node.id)
            index(node.title, node.id)
            for alias in node.aliases:
                index(alias, node.id)
            for provenance in node.provenance:
                index(provenance.path, node.id)
                index(self._queue_neutral_source_key(provenance.path), node.id)
                index(Path(provenance.path).stem, node.id)

        def resolve_reference(reference: str) -> str | None:
            matches = reference_index.get(self._normalise_reference(reference), set())
            return next(iter(matches)) if len(matches) == 1 else None

        dependency_ids: Dict[str, set[str]] = {draft.node.id: set() for draft in merged}
        blocker_ids: Dict[str, set[str]] = {draft.node.id: set() for draft in merged}
        hierarchy_parent_ids: set[str] = set()
        for draft in merged:
            node_id = draft.node.id
            for reference in (*draft.dependencies, *draft.parent_work_items):
                target = resolve_reference(reference)
                if target and target != node_id:
                    dependency_ids[node_id].add(target)
            for reference in draft.parent_work_items:
                target = resolve_reference(reference)
                if target and target != node_id:
                    hierarchy_parent_ids.add(target)
            for reference in draft.blocked_by:
                target = resolve_reference(reference)
                if target and target != node_id:
                    dependency_ids[node_id].add(target)
                    blocker_ids[node_id].add(target)
            for reference in draft.blocks:
                target = resolve_reference(reference)
                if target and target != node_id:
                    dependency_ids[target].add(node_id)

        self._hierarchy_parent_ids = hierarchy_parent_ids
        nodes = []
        for draft in merged:
            node = draft.node
            dependencies = sorted(dependency_ids[node.id])
            blockers = sorted(blocker_ids[node.id])
            nodes.append(node.model_copy(update={
                "dependency_ids": dependencies,
                "blocker_ids": blockers,
                "difficulty": _difficulty(
                    draft.meta or {}, draft.body, node.state, dependencies, blocker_count=len(blockers),
                ),
            }))

        grouped: Dict[str, list[WorkNode]] = {}
        for node in nodes:
            grouped.setdefault(node.stream_id, []).append(node)
        streams = tuple(
            WorkStream(
                id=stream_id,
                repository_id=self.repository_id,
                title=stream_id.rsplit(":", 1)[-1].replace("-", " ").title(),
                lane=lane,
                node_ids=[node.id for node in sorted(stream_nodes, key=lambda item: item.canonical_key)],
            )
            for lane, (stream_id, stream_nodes) in enumerate(sorted(grouped.items()))
        )
        executable_states = {
            WorkNodeState.planned,
            WorkNodeState.active,
            WorkNodeState.paused,
            WorkNodeState.blocked,
            WorkNodeState.review,
        }
        ambiguity_count = len({
            alias for node in nodes for alias in node.aliases
            if sum(
                alias in other.aliases and other.state in executable_states and not other.archived and not other.superseded
                for other in nodes
            ) > 1
        })
        system = RepositorySystem(
            id=self.repository_id,
            name=self.display_name,
            adapter=self.adapter_name,
            configured=self._configured,
            reachable=True,
            revision=self._revision(),
            work_stream_count=len(streams),
            work_node_count=len(nodes),
            ambiguity_count=ambiguity_count,
        )
        return RepositorySnapshot(system=system, streams=streams, nodes=tuple(sorted(nodes, key=lambda node: node.canonical_key)))


class HomeBaseRepositoryAdapter(ReadOnlyRepositoryAdapter):
    repository_id = "misumi-homebase"
    display_name = "Misumi / homeBase"
    adapter_name = "homebase-agent-tasks-v1"

    def personas(self) -> tuple[PersonaProjection, ...]:
        """Return a bounded read-only projection of HomeBase persona canon."""

        if self.root is None:
            return ()
        path = self._resolve_path("config/personas.yaml")
        if not path.is_file():
            return ()
        if path.stat().st_size > MAX_PERSONA_REGISTRY_BYTES:
            raise ValueError("persona registry exceeds adapter limit")
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValueError("persona registry is malformed") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("personas"), dict):
            raise ValueError("persona registry must contain a personas mapping")
        raw_personas = payload["personas"]
        if len(raw_personas) > 40:
            raise ValueError("persona registry exceeds persona limit")

        def text(value: Any, field: str, limit: int) -> str:
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
                raise ValueError(f"persona {field} is invalid")
            return value.strip()

        def strings(value: Any, field: str, limit: int) -> list[str]:
            if value is None:
                return []
            if not isinstance(value, list) or len(value) > limit:
                raise ValueError(f"persona {field} is invalid")
            result = []
            for item in value:
                if not isinstance(item, str) or not item.strip() or len(item.strip()) > 200:
                    raise ValueError(f"persona {field} contains an invalid value")
                result.append(item.strip())
            return result

        def optional_text(value: Any, field: str, limit: int) -> str:
            if value is None:
                return ""
            if not isinstance(value, str) or len(value.strip()) > limit:
                raise ValueError(f"persona {field} is invalid")
            return value.strip()

        projections = []
        for persona_id, raw in sorted(raw_personas.items()):
            if not isinstance(persona_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}", persona_id):
                raise ValueError("persona registry contains an invalid id")
            if not isinstance(raw, dict):
                raise ValueError(f"persona {persona_id} must be a mapping")
            routing = raw.get("routing") or {}
            if not isinstance(routing, dict):
                raise ValueError(f"persona {persona_id} routing is invalid")
            projections.append(PersonaProjection(
                id=persona_id,
                name=text(raw.get("name"), "name", 120),
                role=text(raw.get("role"), "role", 160),
                archetype=optional_text(raw.get("archetype"), "archetype", 160),
                skills=strings(raw.get("skills"), "skills", 24),
                consults=strings(raw.get("consults"), "consults", 16),
                intents=strings(routing.get("intents"), "routing intents", 24),
                source_ref="repo://misumi-homebase/config/personas.yaml",
            ))
        return tuple(projections)

    def source_files(self) -> Iterable[Path]:
        if self.root is None:
            return ()
        task_root = self.root / "agent-tasks"
        return tuple(sorted(path for path in task_root.rglob("*.md") if path.is_file() and path.name != ".gitkeep")) if task_root.is_dir() else ()

    def snapshot(self) -> RepositorySnapshot:
        nodes = [
            self._node_from_markdown(
                path,
                stream_key=path.parent.name,
                source_kind="homebase-agent-task",
                default_state=path.parent.name,
            )
            for path in self.source_files()
        ]
        return self._snapshot(nodes)


class ObsidianPhDRepositoryAdapter(ReadOnlyRepositoryAdapter):
    repository_id = "obsidian-phd"
    display_name = "Obsidian-PhD"
    adapter_name = "obsidian-work-item-v1"

    def source_files(self) -> Iterable[Path]:
        if self.root is None:
            return ()
        inbox = self.root / "10-inbox"
        if not inbox.is_dir():
            return ()
        selected = []
        backlog = inbox / "backlog.md"
        if backlog.is_file():
            selected.append(backlog)
        for path in inbox.rglob("*.md"):
            if path == backlog or any(part.startswith(".") for part in path.relative_to(self.root).parts):
                continue
            try:
                resolved = path.resolve()
                resolved.relative_to(self.root)
                text = resolved.read_text(encoding="utf-8", errors="replace")[:8192]
            except (OSError, ValueError):
                continue
            meta, _ = parse_frontmatter(redact_sensitive_text(text))
            if str(meta.get("artifact_type") or "").strip().casefold() == "work-item":
                selected.append(path)
        return tuple(sorted(set(selected)))

    def snapshot(self) -> RepositorySnapshot:
        drafts: list[_NodeDraft] = []
        backlog_path: Path | None = None
        for path in self.source_files():
            if path.name == "backlog.md":
                backlog_path = path
                continue
            text = self._read_source(path)
            meta, _ = parse_frontmatter(redact_sensitive_text(text))
            stream = str(meta.get("project") or meta.get("drm_phase") or path.parent.name)
            drafts.append(self._node_from_markdown(
                path,
                stream_key=stream,
                source_kind="obsidian-work-item",
                default_state=path.parent.name,
            ))

        self._index_node_ids = set()
        if backlog_path:
            backlog_text = self._read_source(backlog_path)
            paths: Dict[str, set[int]] = {}
            for index, draft in enumerate(drafts):
                for provenance in draft.node.provenance:
                    for reference in (
                        provenance.path,
                        self._queue_neutral_source_key(provenance.path),
                    ):
                        paths.setdefault(self._normalise_reference(reference), set()).add(index)
            for line_number, line in enumerate(backlog_text.splitlines(), 1):
                for match in _LINK_PATH.finditer(line):
                    candidates = paths.get(self._normalise_reference(match.group(1)), set())
                    if len(candidates) != 1:
                        continue
                    draft_index = next(iter(candidates))
                    draft = drafts[draft_index]
                    index_provenance = self._provenance(
                        backlog_path,
                        line,
                        "obsidian-backlog-index",
                        line_number,
                        line_number,
                    )
                    drafts[draft_index] = _NodeDraft(
                        node=draft.node.model_copy(update={
                            "provenance": [*draft.node.provenance, index_provenance],
                        }),
                        dependencies=draft.dependencies,
                        blocked_by=draft.blocked_by,
                        blocks=draft.blocks,
                        parent_work_items=draft.parent_work_items,
                        body=draft.body,
                        meta=draft.meta,
                    )
                    self._index_node_ids.add(draft.node.id)
        return self._snapshot(drafts)


class OdysseusRepositoryAdapter(ReadOnlyRepositoryAdapter):
    repository_id = "odysseus"
    display_name = "Odysseus"
    adapter_name = "odysseus-roadmap-v1"

    def source_files(self) -> Iterable[Path]:
        if self.root is None:
            return ()
        roadmap = self.root / "ROADMAP.md"
        return (roadmap,) if roadmap.is_file() else ()

    def snapshot(self) -> RepositorySnapshot:
        files = tuple(self.source_files())
        if not files:
            return self._snapshot([])
        path = files[0]
        text = self._read_source(path)
        safe_text = redact_sensitive_text(text)
        nodes: list[WorkNode] = []
        current_stream = "roadmap"
        lines = safe_text.splitlines()
        index = 0
        while index < len(lines):
            line = lines[index]
            heading = re.match(r"^##\s+(.+?)\s*$", line)
            if heading:
                current_stream = heading.group(1)
                index += 1
                continue
            bullet = re.match(r"^[-*]\s+(?:\[([ xX])\]\s*)?(.+?)\s*$", line)
            if not bullet:
                index += 1
                continue
            checked, first = bullet.groups()
            parts = [first]
            end = index + 1
            while end < len(lines) and (lines[end].startswith("  ") or not lines[end].strip()):
                if lines[end].strip():
                    parts.append(lines[end].strip())
                end += 1
            title = re.sub(r"\s+", " ", " ".join(parts)).strip()
            state = (
                WorkNodeState.completed
                if checked and checked.casefold() == "x"
                else WorkNodeState.paused
                if "not the focus" in current_stream.casefold() or "defer" in current_stream.casefold()
                else WorkNodeState.planned
            )
            canonical = f"ROADMAP.md#{_slug(current_stream)}/{_slug(title)}"
            aliases = sorted({alias.upper() for alias in _CODE_ALIAS.findall(title)})
            nodes.append(WorkNode(
                id=_stable_id("wn", self.repository_id, canonical.casefold()),
                repository_id=self.repository_id,
                stream_id=f"ws:{self.repository_id}:{_slug(current_stream)}",
                canonical_key=canonical.casefold(),
                aliases=aliases,
                title=title[:240],
                outcome=title[:800],
                state=state,
                next_action=title[:500] if state != WorkNodeState.completed else None,
                acceptance_evidence=[],
                source_links=[f"repo://{self.repository_id}/ROADMAP.md#L{index + 1}"],
                provenance=[self._provenance(path, "\n".join(parts), "odysseus-roadmap", index + 1, end)],
                archived=state == WorkNodeState.completed,
                superseded=False,
                difficulty=_difficulty({}, title, state, []),
            ))
            index = end
        return self._snapshot(nodes)


class RepositoryAdapterRegistry:
    """Server-owned mapping from stable repository IDs to confined adapters."""

    def __init__(self, adapters: Iterable[ReadOnlyRepositoryAdapter]):
        self._adapters = {adapter.repository_id: adapter for adapter in adapters}
        if len(self._adapters) != 3:
            raise ValueError("exactly one adapter for each BBC v1 repository is required")

    @classmethod
    def from_environment(cls, *, odysseus_root: str | Path) -> "RepositoryAdapterRegistry":
        def configured(*names: str) -> Optional[str]:
            for name in names:
                value = (os.getenv(name) or "").strip()
                if value:
                    return value
            return None

        return cls((
            OdysseusRepositoryAdapter(configured("BBC_ODYSSEUS_ROOT") or odysseus_root, strict=False),
            HomeBaseRepositoryAdapter(configured("BBC_MISUMI_ROOT", "MISUMI_HOUSEHOLD_ROOT", "MISUMI_SOURCE_ROOT"), strict=False),
            ObsidianPhDRepositoryAdapter(configured("BBC_OBSIDIAN_PHD_ROOT", "OBSIDIAN_PHD_ROOT"), strict=False),
        ))

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def get(self, repository_id: str) -> ReadOnlyRepositoryAdapter:
        try:
            return self._adapters[repository_id]
        except KeyError as exc:
            raise KeyError(f"unknown or unauthorised repository: {repository_id}") from exc

    def systems(self) -> list[RepositorySystem]:
        return [self._adapters[key].status() for key in sorted(self._adapters)]

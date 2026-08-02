"""Shared deterministic source-adapter helpers."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..constants import ADAPTER_VERSION
from ..errors import AdapterError
from ..model import Edge, Node, Provenance


@dataclass(frozen=True)
class SourceIdentity:
    root: Path
    source_repo: str
    source_revision: str
    extracted_at: str


@dataclass(frozen=True)
class AdapterResult:
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    source_paths: tuple[Path, ...]


class SourceAdapter:
    name = "source_adapter"
    version = ADAPTER_VERSION
    node_types: frozenset[str] = frozenset()
    edge_types: frozenset[str] = frozenset()

    def discover(self, root: Path) -> tuple[Path, ...]:
        raise NotImplementedError

    def parse(self, path: Path, identity: SourceIdentity) -> AdapterResult:
        raise NotImplementedError

    def run(self, root: Path, identity: SourceIdentity) -> AdapterResult:
        paths = self.discover(root)
        nodes: list[Node] = []
        edges: list[Edge] = []
        for path in paths:
            result = self.parse(path, identity)
            if path not in result.source_paths:
                raise AdapterError(f"{self.name}: parser did not account for {path}")
            for node in result.nodes:
                if node.type not in self.node_types:
                    raise AdapterError(
                        f"{self.name}: emitted undeclared node type {node.type!r}"
                    )
            for edge in result.edges:
                if edge.type not in self.edge_types:
                    raise AdapterError(
                        f"{self.name}: emitted undeclared edge type {edge.type!r}"
                    )
            nodes.extend(result.nodes)
            edges.extend(result.edges)
        return AdapterResult(tuple(nodes), tuple(edges), paths)


def read_source(path: Path, adapter_name: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AdapterError(f"{adapter_name}: cannot read {path}: {exc}") from exc
    if not text.strip():
        raise AdapterError(f"{adapter_name}: malformed empty source {path}")
    return text


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def provenance_for(
    path: Path,
    identity: SourceIdentity,
    adapter_name: str,
    adapter_version: str = ADAPTER_VERSION,
) -> Provenance:
    try:
        relative = path.resolve().relative_to(identity.root.resolve()).as_posix()
    except ValueError as exc:
        raise AdapterError(f"source escapes root: {path}") from exc
    return Provenance(
        source_repo=identity.source_repo,
        source_path=relative,
        source_revision=identity.source_revision,
        source_sha256=sha256_file(path),
        extracted_at=identity.extracted_at,
        adapter_name=adapter_name,
        adapter_version=adapter_version,
    )


def stable_id(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._:/-]+", "-", str(value).strip())
    return value.strip("-").lower()


def edge_id(edge_type: str, source: str, target: str, ordinal: int = 0) -> str:
    return f"edge:{edge_type}:{stable_id(source)}:{stable_id(target)}:{ordinal}"


def _run_git(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode:
        return None
    return completed.stdout.strip() or None


def source_identity(root: Path, discovered: Iterable[Path]) -> SourceIdentity:
    root = root.resolve()
    paths = tuple(sorted((path.resolve() for path in discovered), key=lambda p: p.as_posix()))
    revision = _run_git(root, "rev-parse", "HEAD")
    remote = _run_git(root, "config", "--get", "remote.origin.url")
    if revision:
        committed_at = _run_git(root, "show", "-s", "--format=%cI", revision)
        extracted_at = committed_at or "1970-01-01T00:00:00+00:00"
    else:
        tree = hashlib.sha256()
        latest_ns = 0
        for path in paths:
            relative = path.relative_to(root).as_posix()
            tree.update(relative.encode("utf-8"))
            tree.update(b"\0")
            tree.update(bytes.fromhex(sha256_file(path)))
            latest_ns = max(latest_ns, path.stat().st_mtime_ns)
        revision = f"sha256:{tree.hexdigest()}"
        extracted_at = datetime.fromtimestamp(
            latest_ns / 1_000_000_000 if latest_ns else 0,
            tz=timezone.utc,
        ).isoformat()
    source_repo = remote or root.name
    return SourceIdentity(root, source_repo, revision, extracted_at)


def parse_json_source(text: str, path: Path, adapter_name: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"{adapter_name}: malformed JSON {path}: {exc}") from exc


def require_mapping(value: Any, label: str, adapter_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AdapterError(f"{adapter_name}: {label} must be a mapping")
    return value


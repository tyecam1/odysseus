"""Versioned SQLite persistence and deterministic JSON export."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .constants import SCHEMA_VERSION
from .errors import SchemaMismatchError, ValidationError
from .model import CapabilityGraph, Edge, Node, Provenance


@dataclass(frozen=True)
class SourceRecord:
    source_repo: str
    source_path: str
    source_revision: str
    source_sha256: str
    source_root: str
    adapter_name: str

    def to_dict(self, *, include_root: bool = False) -> dict[str, str]:
        value = {
            "source_repo": self.source_repo,
            "source_path": self.source_path,
            "source_revision": self.source_revision,
            "source_sha256": self.source_sha256,
            "adapter_name": self.adapter_name,
        }
        if include_root:
            value["source_root"] = self.source_root
        return value


def _atomic_write_text(path: Path, text: str) -> None:
    """Atomically write a graph export without importing the application stack."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    try:
        with temp.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def assert_schema_compatible(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        return
    with closing(_connect(path)) as connection:
        tables = _tables(connection)
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if tables and version != SCHEMA_VERSION:
        raise SchemaMismatchError(
            f"schema version mismatch: database={version}, expected={SCHEMA_VERSION}"
        )


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE sources (
            source_repo TEXT NOT NULL,
            source_path TEXT NOT NULL,
            source_revision TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            source_root TEXT NOT NULL,
            adapter_name TEXT NOT NULL,
            PRIMARY KEY (source_repo, source_path, adapter_name)
        );
        CREATE TABLE nodes (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            attributes_json TEXT NOT NULL,
            provenance_json TEXT NOT NULL
        );
        CREATE TABLE edges (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            source TEXT NOT NULL REFERENCES nodes(id),
            target TEXT NOT NULL REFERENCES nodes(id),
            attributes_json TEXT NOT NULL,
            provenance_json TEXT NOT NULL
        );
        CREATE INDEX edges_type_source_idx ON edges(type, source);
        CREATE INDEX edges_type_target_idx ON edges(type, target);
        """
    )
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def deterministic_document(
    graph: CapabilityGraph,
    sources: Iterable[SourceRecord],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "sources": [
            source.to_dict()
            for source in sorted(
                sources,
                key=lambda item: (
                    item.source_repo,
                    item.source_path,
                    item.adapter_name,
                ),
            )
        ],
        "nodes": [graph.nodes[node_id].to_dict() for node_id in sorted(graph.nodes)],
        "edges": [graph.edges[edge_id].to_dict() for edge_id in sorted(graph.edges)],
    }


def deterministic_bytes(graph: CapabilityGraph, sources: Iterable[SourceRecord]) -> bytes:
    return (
        json.dumps(
            deterministic_document(graph, sources),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def save_graph(path: Path, graph: CapabilityGraph, sources: Iterable[SourceRecord]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_schema_compatible(path)
    source_list = tuple(sources)
    export_hash = hashlib.sha256(deterministic_bytes(graph, source_list)).hexdigest()
    temp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    if temp.exists():
        temp.unlink()
    try:
        with closing(_connect(temp)) as connection, connection:
            _create_schema(connection)
            connection.executemany(
                "INSERT INTO metadata(key, value) VALUES (?, ?)",
                (
                    ("build_complete", "1"),
                    ("determinism_sha256", export_hash),
                    ("schema_version", str(SCHEMA_VERSION)),
                ),
            )
            connection.executemany(
                """INSERT INTO sources(
                       source_repo, source_path, source_revision, source_sha256,
                       source_root, adapter_name
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        item.source_repo,
                        item.source_path,
                        item.source_revision,
                        item.source_sha256,
                        item.source_root,
                        item.adapter_name,
                    )
                    for item in sorted(
                        source_list,
                        key=lambda item: (item.source_repo, item.source_path, item.adapter_name),
                    )
                ],
            )
            connection.executemany(
                "INSERT INTO nodes(id, type, attributes_json, provenance_json) VALUES (?, ?, ?, ?)",
                [
                    (
                        node.id,
                        node.type,
                        json.dumps(dict(node.attributes), sort_keys=True, separators=(",", ":")),
                        json.dumps(node.provenance.to_dict(), sort_keys=True, separators=(",", ":")),
                    )
                    for node in (graph.nodes[node_id] for node_id in sorted(graph.nodes))
                ],
            )
            connection.executemany(
                """INSERT INTO edges(
                       id, type, source, target, attributes_json, provenance_json
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        edge.id,
                        edge.type,
                        edge.source,
                        edge.target,
                        json.dumps(dict(edge.attributes), sort_keys=True, separators=(",", ":")),
                        json.dumps(edge.provenance.to_dict(), sort_keys=True, separators=(",", ":")),
                    )
                    for edge in (graph.edges[edge_id] for edge_id in sorted(graph.edges))
                ],
            )
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def load_graph(path: Path) -> tuple[CapabilityGraph, tuple[SourceRecord, ...]]:
    path = path.resolve()
    if not path.exists():
        raise ValidationError(f"graph database does not exist: {path}")
    assert_schema_compatible(path)
    graph = CapabilityGraph()
    with closing(_connect(path)) as connection:
        metadata = {row["key"]: row["value"] for row in connection.execute("SELECT key, value FROM metadata")}
        if metadata.get("build_complete") != "1":
            raise ValidationError("graph database is not marked build_complete")
        for row in connection.execute("SELECT * FROM nodes ORDER BY id"):
            graph.add_node(Node(
                row["id"],
                row["type"],
                json.loads(row["attributes_json"]),
                Provenance.from_mapping(json.loads(row["provenance_json"])),
            ))
        for row in connection.execute("SELECT * FROM edges ORDER BY id"):
            graph.add_edge(Edge(
                row["id"],
                row["type"],
                row["source"],
                row["target"],
                json.loads(row["attributes_json"]),
                Provenance.from_mapping(json.loads(row["provenance_json"])),
            ))
        sources = tuple(SourceRecord(**dict(row)) for row in connection.execute(
            "SELECT * FROM sources ORDER BY source_repo, source_path, adapter_name"
        ))
    graph.validate_references()
    actual_hash = hashlib.sha256(deterministic_bytes(graph, sources)).hexdigest()
    if metadata.get("determinism_sha256") != actual_hash:
        raise ValidationError("graph database determinism hash does not match its contents")
    return graph, sources


def export_graph(db_path: Path, out_path: Path) -> str:
    graph, sources = load_graph(db_path)
    payload = deterministic_bytes(graph, sources)
    digest = hashlib.sha256(payload).hexdigest()
    _atomic_write_text(out_path, payload.decode("utf-8"))
    sidecar = out_path.with_name(f"{out_path.name}.metadata.json")
    _atomic_write_text(
        sidecar,
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "sha256": digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n",
    )
    return digest

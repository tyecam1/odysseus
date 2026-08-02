"""Capability-graph build orchestration."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .adapters import DEFAULT_ADAPTERS
from .adapters.base import SourceAdapter, source_identity
from .errors import NoSourcesError, ValidationError
from .model import CapabilityGraph
from .storage import SourceRecord, save_graph
from .validation import validate_graph


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BuildResult:
    db_path: Path
    graph: CapabilityGraph
    sources: tuple[SourceRecord, ...]
    adapter_counts: dict[str, int]

    @property
    def node_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(node.type for node in self.graph.nodes.values()).items()))

    @property
    def edge_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(edge.type for edge in self.graph.edges.values()).items()))


def discover_sources(
    roots: Iterable[Path],
    adapters: Sequence[SourceAdapter] = DEFAULT_ADAPTERS,
) -> dict[Path, dict[str, tuple[Path, ...]]]:
    discovered: dict[Path, dict[str, tuple[Path, ...]]] = {}
    for raw_root in roots:
        root = Path(raw_root).resolve()
        if not root.exists() or not root.is_dir():
            raise NoSourcesError(f"no-sources: source root is not a directory: {root}")
        discovered[root] = {adapter.name: adapter.discover(root) for adapter in adapters}
    return discovered


def build_graph(
    roots: Iterable[Path],
    out_path: Path,
    adapters: Sequence[SourceAdapter] = DEFAULT_ADAPTERS,
) -> BuildResult:
    roots = tuple(Path(root).resolve() for root in roots)
    if not roots:
        raise NoSourcesError("no-sources: at least one source root is required")
    discovered = discover_sources(roots, adapters)
    total_sources = sum(
        len(paths)
        for adapter_paths in discovered.values()
        for paths in adapter_paths.values()
    )
    if total_sources == 0:
        raise NoSourcesError("no-sources: no supported capability source files found")

    graph = CapabilityGraph()
    source_records: dict[tuple[str, str, str], SourceRecord] = {}
    adapter_counts: Counter[str] = Counter()
    adapter_by_name = {adapter.name: adapter for adapter in adapters}
    for root in roots:
        all_paths = sorted({
            path
            for paths in discovered[root].values()
            for path in paths
        }, key=lambda path: path.relative_to(root).as_posix())
        identity = source_identity(root, all_paths)
        for adapter_name in sorted(adapter_by_name):
            adapter = adapter_by_name[adapter_name]
            if not discovered[root][adapter_name]:
                continue
            result = adapter.run(root, identity)
            graph.extend(result.nodes, result.edges)
            adapter_counts[adapter.name] += len(result.source_paths)
            for path in result.source_paths:
                relative = path.relative_to(root).as_posix()
                emitted = [
                    item.provenance
                    for item in (*result.nodes, *result.edges)
                    if item.provenance.source_path == relative
                ]
                if not emitted:
                    raise ValidationError(
                        f"adapter {adapter.name} accounted for {relative} but emitted no provenance"
                    )
                provenance = emitted[0]
                record = SourceRecord(
                    provenance.source_repo,
                    provenance.source_path,
                    provenance.source_revision,
                    provenance.source_sha256,
                    str(root),
                    adapter.name,
                )
                key = (record.source_repo, record.source_path, record.adapter_name)
                existing = source_records.get(key)
                if existing and existing != record:
                    raise ValidationError(f"duplicate source identity with differing records: {key!r}")
                source_records[key] = record

    if not graph.nodes:
        raise NoSourcesError("no-sources: adapters produced zero nodes")
    validate_graph(graph)
    records = tuple(source_records[key] for key in sorted(source_records))
    save_graph(Path(out_path), graph, records)
    result = BuildResult(Path(out_path).resolve(), graph, records, dict(sorted(adapter_counts.items())))
    logger.info(
        "Built capability graph at %s from %d sources (%d nodes, %d edges)",
        result.db_path,
        len(records),
        len(graph.nodes),
        len(graph.edges),
    )
    return result

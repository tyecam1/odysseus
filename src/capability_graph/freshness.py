"""Source hash verification with explicit current/stale result types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Sequence

from .adapters import DEFAULT_ADAPTERS
from .adapters.base import SourceAdapter, sha256_file, source_identity
from .builder import discover_sources
from .storage import SourceRecord, load_graph


class GraphFreshness(str, Enum):
    CURRENT = "current"
    STALE = "stale"

    def __bool__(self) -> bool:
        raise TypeError("GraphFreshness cannot be coerced to bool; compare the enum explicitly")


@dataclass(frozen=True)
class SourceCheck:
    source_repo: str
    source_path: str
    adapter_name: str
    status: str
    stored_sha256: str | None
    actual_sha256: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "source_repo": self.source_repo,
            "source_path": self.source_path,
            "adapter_name": self.adapter_name,
            "status": self.status,
            "stored_sha256": self.stored_sha256,
            "actual_sha256": self.actual_sha256,
        }


@dataclass(frozen=True)
class FreshnessReport:
    freshness: GraphFreshness
    sources: tuple[SourceCheck, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "freshness": self.freshness.value,
            "sources": [item.to_dict() for item in self.sources],
        }


def _provided_roots(sources: Iterable[Path] | None, records: tuple[SourceRecord, ...]) -> tuple[Path, ...]:
    if sources is not None:
        return tuple(Path(root).resolve() for root in sources)
    return tuple(sorted({Path(record.source_root).resolve() for record in records}, key=str))


def check_freshness(
    db_path: Path,
    sources: Iterable[Path] | None = None,
    adapters: Sequence[SourceAdapter] = DEFAULT_ADAPTERS,
) -> FreshnessReport:
    _graph, records = load_graph(Path(db_path))
    roots = _provided_roots(sources, records)
    discovered = discover_sources(roots, adapters) if roots else {}

    checks: list[SourceCheck] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        candidates = [root / Path(record.source_path) for root in roots]
        existing = next((path for path in candidates if path.is_file()), None)
        if existing is None:
            checks.append(SourceCheck(
                record.source_repo,
                record.source_path,
                record.adapter_name,
                "missing",
                record.source_sha256,
                None,
            ))
        else:
            actual = sha256_file(existing)
            checks.append(SourceCheck(
                record.source_repo,
                record.source_path,
                record.adapter_name,
                "current" if actual == record.source_sha256 else "changed",
                record.source_sha256,
                actual,
            ))
        seen.add((record.source_repo, record.source_path, record.adapter_name))

    adapters_by_name = {adapter.name: adapter for adapter in adapters}
    for root in roots:
        all_paths = sorted({path for paths in discovered[root].values() for path in paths})
        if not all_paths:
            continue
        identity = source_identity(root, all_paths)
        for adapter_name, paths in discovered[root].items():
            if adapter_name not in adapters_by_name:
                continue
            for path in paths:
                relative = path.relative_to(root).as_posix()
                key = (identity.source_repo, relative, adapter_name)
                if key in seen:
                    continue
                checks.append(SourceCheck(
                    identity.source_repo,
                    relative,
                    adapter_name,
                    "changed",
                    None,
                    sha256_file(path),
                ))
                seen.add(key)

    checks.sort(key=lambda item: (item.source_repo, item.source_path, item.adapter_name))
    freshness = (
        GraphFreshness.CURRENT
        if checks and all(item.status == "current" for item in checks)
        else GraphFreshness.STALE
    )
    return FreshnessReport(freshness, tuple(checks))


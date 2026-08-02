"""Immutable snapshot, quarantine, and record storage."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

from core.atomic_io import atomic_write_json
from src.constants import (
    PROMPT_INGESTION_ADAPTATIONS_DIR,
    PROMPT_INGESTION_EVALUATIONS_DIR,
    PROMPT_INGESTION_QUARANTINE_DIR,
    PROMPT_INGESTION_RECORDS_DIR,
    PROMPT_INGESTION_SNAPSHOTS_DIR,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelinePaths:
    snapshots: Path = Path(PROMPT_INGESTION_SNAPSHOTS_DIR)
    quarantine: Path = Path(PROMPT_INGESTION_QUARANTINE_DIR)
    records: Path = Path(PROMPT_INGESTION_RECORDS_DIR)
    adaptations: Path = Path(PROMPT_INGESTION_ADAPTATIONS_DIR)
    evaluations: Path = Path(PROMPT_INGESTION_EVALUATIONS_DIR)

    @classmethod
    def under(cls, data_dir: Path) -> "PipelinePaths":
        root = Path(data_dir) / "prompt_ingestion"
        return cls(
            snapshots=root / "snapshots",
            quarantine=root / "quarantine",
            records=root / "records",
            adaptations=root / "adaptations",
            evaluations=root / "evaluations",
        )


def iter_source_files(source: Path) -> Iterable[Tuple[str, Path]]:
    root = source.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"local snapshot source is not a directory: {source}")
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ValueError(f"snapshot source contains a symlink: {path}")
        if not path.is_file():
            continue
        resolved = path.resolve(strict=True)
        if os.path.commonpath((str(root), str(resolved))) != str(root):
            raise ValueError(f"snapshot path escapes source root: {path}")
        yield path.relative_to(root).as_posix(), path


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    files = list(iter_source_files(root))
    if not files:
        raise ValueError("snapshot source contains no files")
    for relative, path in files:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def create_snapshot(source: Path, paths: PipelinePaths) -> tuple[str, Path, str]:
    snapshot_id = uuid.uuid4().hex
    snapshot_root = paths.snapshots / snapshot_id
    content_root = snapshot_root / "content"
    content_root.mkdir(parents=True, exist_ok=False)
    file_count = 0
    for relative, source_file in iter_source_files(source):
        destination = content_root / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as output:
            output.write(source_file.read_bytes())
        file_count += 1
    source_hash = tree_hash(content_root)
    manifest = {
        "snapshot_id": snapshot_id,
        "source_kind": "local-fixture" if "fixture" in str(source).lower() else "local-directory",
        "source": str(source.resolve()),
        "source_hash": source_hash,
        "file_count": file_count,
    }
    with (snapshot_root / "manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    return snapshot_id, content_root, source_hash


def quarantine_snapshot(snapshot_id: str, paths: PipelinePaths) -> Path:
    source = paths.snapshots / snapshot_id / "content"
    if not source.is_dir():
        raise FileNotFoundError(f"snapshot does not exist: {snapshot_id}")
    destination = paths.quarantine / snapshot_id / "content"
    destination.parent.mkdir(parents=True, exist_ok=False)
    shutil.copytree(source, destination)
    if tree_hash(destination) != tree_hash(source):
        raise IOError("quarantine copy hash mismatch")
    return destination


def save_json(path: Path, payload: dict) -> None:
    atomic_write_json(str(path), payload, indent=2)

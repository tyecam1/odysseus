"""Deterministic recurring runner for local Instagram DYI exports.

The task scheduler owns the cadence; this module owns one bounded import run
and its private accounting log.  It deliberately has no model or network
dependencies.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import stat
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from src.constants import DATA_DIR


logger = logging.getLogger(__name__)

JOB_ID = "instagram_saved_import"
DEFAULT_INTERVAL_HOURS = 6.0
DEFAULT_EXPORTS_DIR = Path.home() / "data" / "ingestion" / "instagram" / "exports"
DEFAULT_RUN_LOG = Path(DATA_DIR) / "instagram" / "import-runs.jsonl"

_COUNT_KEYS = ("created", "revised", "unchanged", "superseded", "failed")


def _positive_hours(value: Optional[str]) -> float:
    try:
        hours = float(value) if value is not None else DEFAULT_INTERVAL_HOURS
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_HOURS
    return hours if hours > 0 else DEFAULT_INTERVAL_HOURS


def instagram_import_job_registration() -> dict[str, Any]:
    """Return the scheduler-facing, configuration-resolved job shape."""
    interval_hours = _positive_hours(
        os.getenv("ODYSSEUS_INSTAGRAM_IMPORT_INTERVAL_HOURS")
    )
    return {
        "id": JOB_ID,
        "interval_seconds": interval_hours * 60 * 60,
        "run_on_start": True,
        "runner": run_instagram_import,
        "exports_dir": Path(
            os.getenv("ODYSSEUS_INSTAGRAM_EXPORTS_DIR") or DEFAULT_EXPORTS_DIR
        ),
        "run_log_path": DEFAULT_RUN_LOG,
        "uses_model_inference": False,
        "allows_network_egress": False,
    }


def _private_parent(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.chmod(0o700)
    except OSError:
        # The file itself is still opened with a strict mode below.  Some
        # mounted filesystems do not support POSIX directory chmod.
        pass


def append_import_run(
    accounting: dict[str, Any], run_log_path: str | os.PathLike[str] = DEFAULT_RUN_LOG
) -> str:
    """Append one compact JSON line and return the exact line written."""
    path = Path(run_log_path)
    _private_parent(path.parent)
    line = json.dumps(accounting, sort_keys=True, separators=(",", ":"))
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, stat.S_IRUSR | stat.S_IWUSR)
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "a", encoding="utf-8", closefd=False) as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    return line


def last_import_run(
    run_log_path: str | os.PathLike[str] = DEFAULT_RUN_LOG,
) -> Optional[dict[str, Any]]:
    """Return the most recent valid accounting record, or ``None``."""
    path = Path(run_log_path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _export_pairs(exports_dir: Path) -> list[tuple[Path, Path]]:
    if not exports_dir.is_dir():
        return []
    return [
        (posts_path, posts_path.with_name("saved_collections.json"))
        for posts_path in sorted(exports_dir.rglob("saved_posts.json"))
    ]


def run_instagram_import(
    exports_dir: str | os.PathLike[str] | None = None,
    run_log_path: str | os.PathLike[str] | None = None,
    *,
    importer: Optional[Callable[..., dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Import each permalink's newest occurrence and append per-run counts.

    A missing directory or a directory with no ``saved_posts.json`` is a
    successful zero-count run. File-level failures count once and do not stop
    later snapshots from being processed. The injectable importer remains a
    two-argument test seam; canonical selection and freshness enforcement are
    properties of the production importer path.
    """
    started = time.monotonic()
    registration = instagram_import_job_registration()
    export_root = Path(exports_dir) if exports_dir is not None else registration["exports_dir"]
    log_path = Path(run_log_path) if run_log_path is not None else registration["run_log_path"]
    default_importer = importer is None
    if default_importer:
        from src.instagram_importer import import_instagram_saved_export

        importer = import_instagram_saved_export

    counts = {key: 0 for key in _COUNT_KEYS}
    pairs = _export_pairs(export_root)
    selected_permalinks = {posts_path: set() for posts_path, _ in pairs}
    scan_errors: dict[Path, Exception] = {}

    if default_importer:
        from src.instagram_importer import _load_list, _parse_saved_posts

        winners: dict[str, tuple[int, Path]] = {}
        for posts_path, collections_path in pairs:
            if not collections_path.is_file():
                continue
            try:
                posts, _ = _parse_saved_posts(
                    _load_list(str(posts_path), "saved-posts"),
                    posts_path.name,
                )
            except Exception as exc:
                scan_errors[posts_path] = exc
                continue
            for permalink, occurrence in posts.items():
                current = winners.get(permalink)
                if current is None or occurrence["timestamp"] >= current[0]:   # a tie goes to the later snapshot
                    winners[permalink] = (
                        occurrence["timestamp"],
                        posts_path,
                    )
        for permalink, (_, posts_path) in winners.items():
            selected_permalinks[posts_path].add(permalink)

    for posts_path, collections_path in pairs:
        if not collections_path.is_file():
            counts["failed"] += 1
            logger.warning(
                "Instagram import skipped %s: sibling saved_collections.json is missing",
                posts_path,
            )
            continue
        if posts_path in scan_errors:
            counts["failed"] += 1
            logger.warning(
                "Instagram import failed for %s: %s",
                posts_path.parent,
                scan_errors[posts_path],
            )
            continue
        try:
            if default_importer:
                result = importer(
                    str(posts_path),
                    str(collections_path),
                    selected_permalinks=selected_permalinks[posts_path],
                    enforce_freshness=True,
                )
            else:
                result = importer(str(posts_path), str(collections_path))
        except Exception as exc:
            counts["failed"] += 1
            logger.warning("Instagram import failed for %s: %s", posts_path.parent, exc)
            continue
        result_counts = result.get("counts") if isinstance(result, dict) else {}
        for key in _COUNT_KEYS:
            value = result_counts.get(key, 0) if isinstance(result_counts, dict) else 0
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                counts[key] += value

    accounting = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **counts,
        "duration_ms": int((time.monotonic() - started) * 1000),
    }
    line = append_import_run(accounting, log_path)
    logger.info("Instagram import run: %s", line)
    if default_importer:
        # Governed handoff (deterministic, own accounting log beside the run log): a failure never fails the import.
        try:
            from src.instagram_handoff import run_instagram_handoff

            run_instagram_handoff(Path(log_path).parent / "handoff")
        except Exception as exc:
            logger.warning("Instagram handoff failed: %s", type(exc).__name__)
        try:  # owner work items (aggregate digest -> owner-repo pull request); failures retry on the next run
            from src.instagram_work_items import run_instagram_work_items

            logger.info("Instagram work items: %s", run_instagram_work_items(Path(log_path).parent / "handoff"))
        except Exception as exc:
            logger.warning("Instagram work items failed: %s", type(exc).__name__)
    return accounting


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exports-dir", help="root containing Instagram export snapshots")
    parser.add_argument("--run-log", help="override the governed JSONL run log path")
    parser.add_argument(
        "--last-run", action="store_true", help="print the latest accounting record without importing"
    )
    args = parser.parse_args(argv)
    log_path = args.run_log or DEFAULT_RUN_LOG
    if args.last_run:
        record = last_import_run(log_path)
        print(json.dumps(record, sort_keys=True, separators=(",", ":")))
        return 0 if record is not None else 1
    accounting = run_instagram_import(args.exports_dir, log_path)
    print(json.dumps(accounting, sort_keys=True, separators=(",", ":")))
    return 0 if accounting["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_main())

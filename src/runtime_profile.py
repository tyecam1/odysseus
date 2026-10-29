"""Read-only deployment boundary. Validation is deliberately free of writes/imports of DB code."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


SOURCE_ALIASES = {
    "misumi-homebase": ("BBC_MISUMI_ROOT", "MISUMI_HOUSEHOLD_ROOT", "MISUMI_SOURCE_ROOT", "FLAT_KNOWLEDGEBASE_ROOT"),
    "obsidian-phd": ("BBC_OBSIDIAN_PHD_ROOT", "OBSIDIAN_PHD_ROOT"),
    "odysseus": ("BBC_ODYSSEUS_ROOT",),
}
# Estate root variables name parent directories, not BBC Git top levels. They
# never supply a reader source, but opposite inherited roots are still refused.
ESTATE_ROOT_ALIASES = {
    "misumi-homebase": ("HOUSEHOLD_ROOT",),
    "obsidian-phd": ("PHD_ROOT",),
    "odysseus": ("AI_ROOT",),
}
WRITABLE_OVERRIDES = (
    "ODYSSEUS_MAIL_ATTACHMENTS_DIR", "FASTEMBED_CACHE_PATH",
    "DATA_BASE_DIR", "DATA_DATA_DIR", "DATA_UPLOADS_DIR", "DATA_SESSIONS_FILE", "DATA_MEMORY_FILE",
    "DATA_PERSONAL_DIR", "DATA_RUNBOOK_DIR", "MISUMI_EVENT_LOG",
    "ODYSSEUS_INSTAGRAM_EXPORTS_DIR", "ODYSSEUS_META_EXPORT_BROWSER_PROFILE",
)


class ReaderConfigurationError(ValueError):
    pass


def _absolute(value: str, key: str) -> Path:
    path = Path(value)
    if not value or not path.is_absolute():
        raise ReaderConfigurationError(f"reader requires explicit absolute {key}")
    try:
        return path.resolve()
    except (OSError, RuntimeError) as exc:
        raise ReaderConfigurationError(f"reader cannot resolve {key}") from exc


def _within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


@dataclass(frozen=True)
class RuntimeProfile:
    name: str = "joint"
    repository_id: str | None = None
    data_root: Path | None = None
    source_root: Path | None = None

    @property
    def reader(self) -> bool:
        return self.repository_id is not None


def runtime_profile(env: Mapping[str, str] | None = None) -> RuntimeProfile:
    env = os.environ if env is None else env
    name = env.get("ODYSSEUS_RUNTIME_PROFILE", "joint")
    if name == "joint":
        return RuntimeProfile()
    repository_id = {"misumi-reader": "misumi-homebase", "phd-reader": "obsidian-phd"}.get(name)
    if repository_id is None:
        raise ReaderConfigurationError("unknown ODYSSEUS_RUNTIME_PROFILE")
    data = _absolute(env.get("ODYSSEUS_DATA_DIR", ""), "ODYSSEUS_DATA_DIR")
    from src.runtime_paths import get_default_data_dir
    if data == Path(get_default_data_dir()).resolve():
        raise ReaderConfigurationError("reader refuses the legacy joint data root")
    # Reject aliases through symlinks/junctions, including an existing ancestor.
    if data != Path(os.path.abspath(env["ODYSSEUS_DATA_DIR"])):
        raise ReaderConfigurationError("reader data root resolves through an alias")
    for repo, source_aliases in SOURCE_ALIASES.items():
        aliases = (*source_aliases, *ESTATE_ROOT_ALIASES[repo])
        if repo != repository_id and any(env.get(key, "").strip() for key in aliases):
            raise ReaderConfigurationError("reader refuses foreign source root aliases")
    own = [(key, env[key]) for key in SOURCE_ALIASES[repository_id] if env.get(key, "").strip()]
    if not own:
        raise ReaderConfigurationError("reader requires explicit own source root")
    sources = [_absolute(value, key) for key, value in own]
    source = sources[0]
    if any(path != source for path in sources) or not source.is_dir():
        raise ReaderConfigurationError("reader own source aliases must identify one existing directory")
    if _within(data, source) or _within(source, data):
        raise ReaderConfigurationError("reader data and source roots must be separate")
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(source), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode or Path(result.stdout.strip()).resolve() != source:
            raise ReaderConfigurationError("reader source must be a Git top-level directory")
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReaderConfigurationError("reader source could not be validated") from exc
    # No configurable DB authority in a reader, including in-memory, URI and local overrides.
    # Its core DB is always the existing DATA_DIR/app.db, never a shared endpoint.
    if "DATABASE_URL" in env:
        raise ReaderConfigurationError("reader refuses DATABASE_URL; use its private default DB")
    if env.get("AUTH_ENABLED", "true").lower() == "false" or env.get("LOCALHOST_BYPASS", "false").lower() == "true":
        raise ReaderConfigurationError("reader requires authentication without localhost bypass")
    # Pydantic DataConfig accepts case-insensitive DATA_* names on Linux too.
    overrides = {key.upper(): value for key, value in env.items() if key.upper() in WRITABLE_OVERRIDES}
    for key, value in overrides.items():
        if key == "FASTEMBED_CACHE_PATH" and not value:
            continue  # Existing constants intentionally treat empty as the private default.
        if key in WRITABLE_OVERRIDES:
            target = _absolute(value, key)
            if not _within(target, data):
                raise ReaderConfigurationError(f"reader writable override escapes data root: {key}")
    # Check existing descendants before DB migrations/logging/auth can touch them.
    # os.walk does not follow symlink dirs; resolve every entry, including dangling links.
    if data.exists():
        if not data.is_dir():
            raise ReaderConfigurationError("reader data root must be a directory")
        def unreadable(_error):
            raise ReaderConfigurationError("reader data descendants could not be validated")

        for parent, dirs, files in os.walk(data, followlinks=False, onerror=unreadable):
            for entry in (*dirs, *files):
                if not _within((Path(parent) / entry).resolve(), data):
                    raise ReaderConfigurationError("reader data descendant escapes data root")
    return RuntimeProfile(name, repository_id, data, source)


def is_reader() -> bool:
    # Entry guards need no DB/config import and cannot silently accept unknown profiles.
    name = os.environ.get("ODYSSEUS_RUNTIME_PROFILE", "joint")
    if name not in {"joint", "misumi-reader", "phd-reader"}:
        raise ReaderConfigurationError("unknown ODYSSEUS_RUNTIME_PROFILE")
    return name != "joint"


def require_joint() -> None:
    if is_reader():
        raise PermissionError("operation unavailable in reader profile")


def require_repository(repository_id: str) -> None:
    own = {"misumi-reader": "misumi-homebase", "phd-reader": "obsidian-phd"}.get(os.environ.get("ODYSSEUS_RUNTIME_PROFILE"))
    if is_reader() and repository_id != own:
        raise PermissionError("repository unavailable in reader profile")


def require_inspection(capability_id: str, inputs: Mapping) -> None:
    if is_reader():
        if capability_id != "bbc.repository.inspect":
            raise PermissionError("operation unavailable in reader profile")
        require_repository(str(inputs.get("repository_id", "")))


if __name__ == "__main__":
    # Wrapper runs this after dotenv and before its first New-Item/log write.
    from dotenv import load_dotenv
    load_dotenv(encoding="utf-8-sig")
    runtime_profile()

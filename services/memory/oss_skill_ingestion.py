"""Supply-chain boundary for open-source skill bundles.

This module deliberately has no network or execution primitives.  A separate
discovery adapter may download a candidate, but it must resolve the source to
an immutable Git commit before handing the bytes to :class:`OSSSkillIngestion`.
Candidates are retained in quarantine, reviewed as inert data, and only
prompt/data-only bundles may be promoted into the separate release store.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence


_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,126}[a-z0-9])?$")
_GITHUB_RE = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_PROMOTABLE_SUFFIXES = frozenset({
    ".md", ".txt", ".json", ".yaml", ".yml", ".csv",
})
_PROMOTABLE_NAMES = frozenset({"license", "notice", "copying"})
_SCRIPT_SUFFIXES = frozenset({
    ".bat", ".cmd", ".com", ".dll", ".exe", ".jar", ".js", ".mjs",
    ".ps1", ".py", ".rb", ".sh", ".so", ".ts", ".vbs", ".wasm",
})
_PERMISSIVE_LICENSES = frozenset({
    "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0", "ISC", "MIT",
})
_MAX_FILES = 128
_MAX_FILE_BYTES = 500_000
_MAX_BUNDLE_BYTES = 4_000_000
_WINDOWS_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)

_RISK_RULES: tuple[tuple[str, str, str, re.Pattern[str]], ...] = (
    ("secret-access", "high", "possible access to credentials or secrets", re.compile(
        r"(?i)(?:\.env\b|api[_ -]?key|access[_ -]?token|private[_ -]?key|credential|"
        r"keyring|secretservice|windows credential)"
    )),
    ("network", "high", "possible network access", re.compile(
        r"(?i)(?:https?://|\bcurl\b|\bwget\b|requests\.(?:get|post)|"
        r"httpx\.|fetch\s*\(|socket\.|urllib\.)"
    )),
    ("destructive", "high", "possible destructive filesystem or Git action", re.compile(
        r"(?i)(?:\brm\s+-rf\b|Remove-Item\b[^\n]*(?:-Recurse|-Force)|"
        r"git\s+(?:reset\s+--hard|clean\s+-[a-z]*f)|shutil\.rmtree|os\.remove\s*\()"
    )),
    ("prompt-injection", "high", "possible prompt-injection instruction", re.compile(
        r"(?i)(?:ignore\s+(?:all\s+)?(?:(?:previous|prior)(?:\s+system)?|system)\s+instructions|"
        r"reveal\s+(?:the\s+)?system\s+prompt|developer\s+message|bypass\s+(?:the\s+)?policy)"
    )),
    ("persistence", "high", "possible persistence mechanism", re.compile(
        r"(?i)(?:schtasks\b|crontab\b|systemctl\s+enable|Startup\\|"
        r"RunOnce\b|LaunchAgents|authorized_keys)"
    )),
    ("telemetry", "medium", "possible telemetry or external reporting", re.compile(
        r"(?i)(?:telemetry|analytics|sentry|posthog|segment\.io|mixpanel)"
    )),
)


class OSSSkillIngestionError(ValueError):
    """Raised when an intake or state transition fails closed."""


@dataclass(frozen=True)
class Dependency:
    """A dependency declaration; versions must be exact, never ranges/tags."""

    name: str
    version: str
    kind: str = "package"
    source: str = "declared"
    sha256: str | None = None


@dataclass(frozen=True)
class SourceProvenance:
    repository: str
    commit: str
    path: str
    license_spdx: str
    discovered_at: str
    discovered_by: str
    upstream_url: str | None = None
    maintenance_evidence: str | None = None


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    gap_id: str
    capability_ids: tuple[str, ...]
    provenance: SourceProvenance
    dependencies: tuple[Dependency, ...] = field(default_factory=tuple)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(_canonical_json(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def _safe_id(value: str, label: str) -> str:
    supplied = str(value or "").strip()
    normalized = supplied.lower()
    if supplied != normalized or not _ID_RE.fullmatch(normalized):
        raise OSSSkillIngestionError(f"invalid {label}: {value!r}")
    return normalized


def _safe_path(value: str) -> str:
    raw = str(value or "").replace("\\", "/").strip()
    path = PurePosixPath(raw)
    if (
        not raw
        or raw.startswith("/")
        or len(raw) > 512
        or "\x00" in raw
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(
            ":" in part
            or part.endswith((" ", "."))
            or part.split(".", 1)[0].upper() in _WINDOWS_DEVICE_NAMES
            for part in path.parts
        )
    ):
        raise OSSSkillIngestionError(f"unsafe bundle path: {value!r}")
    return path.as_posix()


def _validate_candidate(candidate: Candidate) -> None:
    if not isinstance(candidate, Candidate) or not isinstance(candidate.provenance, SourceProvenance):
        raise OSSSkillIngestionError("candidate and provenance must use the typed intake contract")
    _safe_id(candidate.candidate_id, "candidate_id")
    _safe_id(candidate.gap_id, "gap_id")
    if (
        not candidate.capability_ids
        or isinstance(candidate.capability_ids, (str, bytes))
        or not isinstance(candidate.capability_ids, Sequence)
    ):
        raise OSSSkillIngestionError("at least one capability_id is required")
    for capability_id in candidate.capability_ids:
        _safe_id(capability_id, "capability_id")
    source = candidate.provenance
    required_source_strings = (
        source.repository,
        source.commit,
        source.path,
        source.license_spdx,
        source.discovered_at,
        source.discovered_by,
    )
    if not all(isinstance(value, str) for value in required_source_strings):
        raise OSSSkillIngestionError("provenance fields must be strings")
    if not _GITHUB_RE.fullmatch(source.repository):
        raise OSSSkillIngestionError("repository must be a canonical HTTPS GitHub repository URL")
    if not _COMMIT_RE.fullmatch(source.commit):
        raise OSSSkillIngestionError("source commit must be a lowercase 40-character Git SHA")
    if source.path:
        _safe_path(source.path)
    if not source.license_spdx.strip():
        raise OSSSkillIngestionError("license_spdx is required")
    if not source.discovered_at.strip() or not source.discovered_by.strip():
        raise OSSSkillIngestionError("discovery timestamp and actor are required")
    try:
        discovered_at = datetime.fromisoformat(source.discovered_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise OSSSkillIngestionError("discovered_at must be an ISO-8601 timestamp") from exc
    if discovered_at.tzinfo is None:
        raise OSSSkillIngestionError("discovered_at must include a timezone")
    if source.upstream_url and (
        not source.upstream_url.startswith("https://github.com/")
        or source.commit not in source.upstream_url
    ):
        raise OSSSkillIngestionError("upstream_url must be a GitHub URL pinned to the source commit")
    for dependency in candidate.dependencies:
        if not isinstance(dependency, Dependency):
            raise OSSSkillIngestionError("dependencies must use the typed dependency contract")
        if not all(isinstance(value, str) for value in (
            dependency.name, dependency.version, dependency.kind, dependency.source,
        )):
            raise OSSSkillIngestionError("dependency fields must be strings")
        if not dependency.name.strip() or not dependency.version.strip():
            raise OSSSkillIngestionError("dependencies require name and exact version")
        version = dependency.version.strip()
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}", version)
            or any(marker in version.lower() for marker in ("latest", "main", "master", "head", "dev"))
            or any(part.lower() == "x" for part in re.split(r"[._+-]", version))
        ):
            raise OSSSkillIngestionError(f"dependency {dependency.name!r} is not exactly pinned")
        if dependency.sha256 is not None and not _SHA256_RE.fullmatch(dependency.sha256):
            raise OSSSkillIngestionError(f"dependency {dependency.name!r} has an invalid sha256")


def _normalize_files(files: Mapping[str, str | bytes]) -> dict[str, bytes]:
    if not files or len(files) > _MAX_FILES:
        raise OSSSkillIngestionError(f"bundle must contain 1-{_MAX_FILES} files")
    normalized: dict[str, bytes] = {}
    total = 0
    for supplied_path, supplied_data in files.items():
        path = _safe_path(supplied_path)
        if path in normalized:
            raise OSSSkillIngestionError(f"duplicate bundle path: {path}")
        data = supplied_data.encode("utf-8") if isinstance(supplied_data, str) else bytes(supplied_data)
        if len(data) > _MAX_FILE_BYTES:
            raise OSSSkillIngestionError(f"file exceeds size limit: {path}")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise OSSSkillIngestionError(f"binary or non-UTF-8 file rejected: {path}") from exc
        total += len(data)
        if total > _MAX_BUNDLE_BYTES:
            raise OSSSkillIngestionError("bundle exceeds total size limit")
        normalized[path] = data
    return dict(sorted(normalized.items()))


def _file_manifest(files: Mapping[str, bytes]) -> list[dict[str, object]]:
    return [
        {"path": path, "sha256": _sha256(data), "size": len(data)}
        for path, data in sorted(files.items())
    ]


def _bundle_sha(files: Mapping[str, bytes]) -> str:
    return _sha256(_canonical_json(_file_manifest(files)))


def _is_prompt_or_data(path: str) -> bool:
    pure = PurePosixPath(path)
    return pure.suffix.lower() in _PROMOTABLE_SUFFIXES or pure.name.lower() in _PROMOTABLE_NAMES


def _static_review(
    candidate: Candidate,
    files: Mapping[str, bytes],
    installed_capability_ids: Iterable[str],
) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    scripts: list[str] = []
    for path, data in files.items():
        pure = PurePosixPath(path)
        text = data.decode("utf-8")
        suffix = pure.suffix.lower()
        first_line = text.splitlines()[0] if text.splitlines() else ""
        if suffix in _SCRIPT_SUFFIXES or first_line.startswith("#!") or not _is_prompt_or_data(path):
            scripts.append(path)
            findings.append({
                "rule": "executable-content",
                "severity": "high",
                "path": path,
                "line": 1,
                "message": "candidate code or unsupported file type remains quarantined",
            })
        for rule, severity, message, pattern in _RISK_RULES:
            for line_number, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    findings.append({
                        "rule": rule,
                        "severity": severity,
                        "path": path,
                        "line": line_number,
                        "message": message,
                    })
                    break

    overlap = sorted(set(candidate.capability_ids).intersection(installed_capability_ids))
    if overlap:
        findings.append({
            "rule": "capability-overlap",
            "severity": "high",
            "path": None,
            "line": None,
            "message": f"already installed capability IDs: {', '.join(overlap)}",
        })
    if candidate.provenance.license_spdx not in _PERMISSIVE_LICENSES:
        findings.append({
            "rule": "license-policy",
            "severity": "high",
            "path": None,
            "line": None,
            "message": f"license is outside the configured promotion allowlist: {candidate.provenance.license_spdx}",
        })
    if candidate.dependencies:
        findings.append({
            "rule": "runtime-dependencies",
            "severity": "high",
            "path": None,
            "line": None,
            "message": "prompt/data-only promotion policy does not install dependencies",
        })

    findings.sort(key=lambda item: (
        str(item["path"] or ""), int(item["line"] or 0), str(item["rule"]),
    ))
    promotable = not any(item["severity"] == "high" for item in findings)
    return {
        "review_version": 1,
        "reviewed_at": utc_now(),
        "method": "static-text-only",
        "candidate_code_executed": False,
        "sandbox_status": "not-executed-no-code-sandbox",
        "prompt_data_only": not scripts,
        "script_paths": sorted(scripts),
        "overlap_capability_ids": overlap,
        "findings": findings,
        "policy_result": "eligible-for-explicit-approval" if promotable else "quarantine",
        "promotable": promotable,
    }


def _candidate_from_record(record: Mapping[str, object]) -> Candidate:
    """Reconstruct and validate persisted candidate metadata fail-closed."""
    try:
        provenance_value = record["provenance"]
        dependencies_value = record.get("dependencies") or []
        if not isinstance(provenance_value, Mapping) or not isinstance(dependencies_value, list):
            raise TypeError
        candidate = Candidate(
            candidate_id=str(record["candidate_id"]),
            gap_id=str(record["gap_id"]),
            capability_ids=tuple(str(value) for value in record["capability_ids"]),
            provenance=SourceProvenance(**{
                key: value for key, value in provenance_value.items()
            }),
            dependencies=tuple(Dependency(**value) for value in dependencies_value),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OSSSkillIngestionError("invalid persisted candidate metadata") from exc
    _validate_candidate(candidate)
    return candidate


def _review_policy_projection(review: Mapping[str, object]) -> dict[str, object]:
    """Return the deterministic, security-relevant portion of a review."""
    return {key: value for key, value in review.items() if key != "reviewed_at"}


class OSSSkillIngestion:
    """Filesystem-backed quarantine, promotion, and rollback service.

    ``root`` is service state, not the live skill directory.  Promoted releases
    remain immutable under ``releases``; consumers should resolve the compact
    JSON pointer returned by :meth:`active_release` instead of scanning
    quarantine.  The class never imports or executes candidate files.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.quarantine_root = self.root / "quarantine"
        self.release_root = self.root / "releases"
        self.active_root = self.root / "active"
        self.audit_root = self.root / "audit"
        for path in (self.quarantine_root, self.release_root, self.active_root, self.audit_root):
            path.mkdir(parents=True, exist_ok=True)

    def stage(
        self,
        candidate: Candidate,
        files: Mapping[str, str | bytes],
        *,
        installed_capability_ids: Iterable[str] = (),
    ) -> dict[str, object]:
        """Store and statically review an already-downloaded local bundle."""
        _validate_candidate(candidate)
        normalized = _normalize_files(files)
        bundle_sha = _bundle_sha(normalized)
        installed_snapshot = sorted({str(value) for value in installed_capability_ids})
        candidate_record = json.loads(_canonical_json(asdict(candidate)))
        intake_sha = _sha256(_canonical_json({
            "candidate": candidate_record,
            "bundle_sha256": bundle_sha,
            "installed_capability_ids_at_review": installed_snapshot,
        }))
        intake_id = f"{candidate.candidate_id}--{candidate.provenance.commit}--{intake_sha}"
        intake_path = self.quarantine_root / intake_id
        review = _static_review(candidate, normalized, installed_snapshot)
        manifest = {
            "schema_version": 1,
            "intake_id": intake_id,
            "candidate": candidate_record,
            "bundle_sha256": bundle_sha,
            "intake_sha256": intake_sha,
            "installed_capability_ids_at_review": installed_snapshot,
            "files": _file_manifest(normalized),
            "staged_at": utc_now(),
            "state": "quarantined",
        }

        if intake_path.exists():
            stored = self._load_json(intake_path / "manifest.json")
            if stored.get("intake_sha256") != intake_sha or stored.get("candidate") != manifest["candidate"]:
                raise OSSSkillIngestionError("immutable quarantine intake conflicts with existing state")
            _, verified_manifest, verified_review = self._load_intake(intake_id)
            return {"manifest": verified_manifest, "review": verified_review}

        temp_path = Path(tempfile.mkdtemp(prefix=".intake-", dir=str(self.quarantine_root)))
        try:
            files_path = temp_path / "files"
            for path, data in normalized.items():
                destination = files_path.joinpath(*PurePosixPath(path).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            _write_json_atomic(temp_path / "manifest.json", manifest)
            _write_json_atomic(temp_path / "review.json", review)
            os.replace(temp_path, intake_path)
        finally:
            if temp_path.exists():
                shutil.rmtree(temp_path)
        self._record_event("staged", intake_id=intake_id, candidate_id=candidate.candidate_id)
        return {"manifest": manifest, "review": review}

    def promote(
        self,
        intake_id: str,
        *,
        approved_by: str,
        approval_reason: str,
    ) -> dict[str, object]:
        """Promote an eligible data-only intake after explicit human approval."""
        actor, reason = self._approval(approved_by, approval_reason)
        intake_path, manifest, review = self._load_intake(intake_id)
        if not review.get("promotable") or review.get("policy_result") != "eligible-for-explicit-approval":
            raise OSSSkillIngestionError("candidate failed promotion policy and remains quarantined")
        if review.get("candidate_code_executed") is not False or review.get("prompt_data_only") is not True:
            raise OSSSkillIngestionError("only statically reviewed prompt/data bundles may be promoted")

        candidate_id = _safe_id(manifest["candidate"]["candidate_id"], "candidate_id")
        release_id = f"{manifest['candidate']['provenance']['commit'][:12]}-{manifest['intake_sha256'][:20]}"
        release_path = self.release_root / candidate_id / release_id
        approval = {"approved_by": actor, "reason": reason, "approved_at": utc_now()}
        release_manifest = {
            **manifest,
            "state": "released",
            "release_id": release_id,
            "approval": approval,
            "review_sha256": _sha256(_canonical_json(review)),
            "released_at": utc_now(),
        }
        release_manifest["release_sha256"] = _sha256(_canonical_json(release_manifest))
        if release_path.exists():
            stored = self._load_json(release_path / "manifest.json")
            self._verify_release(release_path, stored)
            if stored.get("bundle_sha256") != manifest["bundle_sha256"]:
                raise OSSSkillIngestionError("immutable release conflicts with existing state")
            release_manifest = stored
        else:
            release_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = Path(tempfile.mkdtemp(prefix=".release-", dir=str(release_path.parent)))
            try:
                shutil.copytree(intake_path / "files", temp_path / "files")
                self._verify_files(temp_path / "files", manifest["files"])
                _write_json_atomic(temp_path / "manifest.json", release_manifest)
                _write_json_atomic(temp_path / "review.json", review)
                os.replace(temp_path, release_path)
            finally:
                if temp_path.exists():
                    shutil.rmtree(temp_path)

        previous = self.active_release(candidate_id)
        pointer = {
            "candidate_id": candidate_id,
            "release_id": release_id,
            "release_path": str(release_path),
            "bundle_sha256": manifest["bundle_sha256"],
            "activated_at": utc_now(),
            "activated_by": actor,
            "reason": reason,
            "previous_release_id": previous.get("release_id") if previous else None,
        }
        _write_json_atomic(self.active_root / f"{candidate_id}.json", pointer)
        self._record_event("promoted", candidate_id=candidate_id, release_id=release_id, actor=actor)
        return {"release": release_manifest, "active": pointer}

    def rollback(
        self,
        candidate_id: str,
        release_id: str,
        *,
        approved_by: str,
        approval_reason: str,
    ) -> dict[str, object]:
        """Atomically repoint a candidate to a previously verified release."""
        candidate_id = _safe_id(candidate_id, "candidate_id")
        release_id = _safe_id(release_id, "release_id")
        actor, reason = self._approval(approved_by, approval_reason)
        release_path = self.release_root / candidate_id / release_id
        if not release_path.is_dir():
            raise OSSSkillIngestionError("rollback release does not exist")
        manifest = self._load_json(release_path / "manifest.json")
        self._verify_release(release_path, manifest)
        current = self.active_release(candidate_id)
        if current and current.get("release_id") == release_id:
            raise OSSSkillIngestionError("requested release is already active")
        pointer = {
            "candidate_id": candidate_id,
            "release_id": release_id,
            "release_path": str(release_path),
            "bundle_sha256": manifest["bundle_sha256"],
            "activated_at": utc_now(),
            "activated_by": actor,
            "reason": reason,
            "previous_release_id": current.get("release_id") if current else None,
            "rollback": True,
        }
        _write_json_atomic(self.active_root / f"{candidate_id}.json", pointer)
        self._record_event("rolled-back", candidate_id=candidate_id, release_id=release_id, actor=actor)
        return pointer

    def active_release(self, candidate_id: str) -> dict[str, object] | None:
        candidate_id = _safe_id(candidate_id, "candidate_id")
        path = self.active_root / f"{candidate_id}.json"
        if not path.is_file():
            return None
        pointer = self._load_json(path)
        release_path = self.release_root / candidate_id / str(pointer["release_id"])
        manifest = self._load_json(release_path / "manifest.json")
        self._verify_release(release_path, manifest)
        if pointer.get("bundle_sha256") != manifest.get("bundle_sha256"):
            raise OSSSkillIngestionError("active release pointer fails integrity verification")
        return pointer

    def _load_intake(self, intake_id: str) -> tuple[Path, dict[str, object], dict[str, object]]:
        if not re.fullmatch(r"[a-z0-9._-]+--[0-9a-f]{40}--[0-9a-f]{64}", str(intake_id or "")):
            raise OSSSkillIngestionError("invalid intake_id")
        path = self.quarantine_root / intake_id
        if not path.is_dir():
            raise OSSSkillIngestionError("quarantine intake does not exist")
        manifest = self._load_json(path / "manifest.json")
        review = self._load_json(path / "review.json")
        if manifest.get("intake_id") != intake_id:
            raise OSSSkillIngestionError("quarantine intake identity mismatch")
        candidate = _candidate_from_record(manifest.get("candidate") or {})
        self._verify_files(path / "files", manifest["files"])
        files = {
            item["path"]: (path / "files").joinpath(*PurePosixPath(item["path"]).parts).read_bytes()
            for item in manifest["files"]
        }
        if manifest.get("bundle_sha256") != _bundle_sha(files):
            raise OSSSkillIngestionError("quarantine bundle hash mismatch")
        installed_snapshot = manifest.get("installed_capability_ids_at_review")
        if not isinstance(installed_snapshot, list):
            raise OSSSkillIngestionError("quarantine capability snapshot is invalid")
        expected_intake_sha = _sha256(_canonical_json({
            "candidate": manifest["candidate"],
            "bundle_sha256": manifest["bundle_sha256"],
            "installed_capability_ids_at_review": installed_snapshot,
        }))
        if manifest.get("intake_sha256") != expected_intake_sha or not intake_id.endswith(expected_intake_sha):
            raise OSSSkillIngestionError("quarantine metadata integrity failure")
        expected_review = _static_review(candidate, files, installed_snapshot)
        if _review_policy_projection(review) != _review_policy_projection(expected_review):
            raise OSSSkillIngestionError("quarantine static review integrity failure")
        return path, manifest, review

    def _verify_release(self, release_path: Path, manifest: Mapping[str, object]) -> None:
        self._verify_files(release_path / "files", manifest["files"])
        supplied_hash = manifest.get("release_sha256")
        unsigned = {key: value for key, value in manifest.items() if key != "release_sha256"}
        if supplied_hash != _sha256(_canonical_json(unsigned)):
            raise OSSSkillIngestionError("release manifest integrity failure")
        expected_release_id = (
            f"{manifest['candidate']['provenance']['commit'][:12]}-"
            f"{manifest['intake_sha256'][:20]}"
        )
        if manifest.get("release_id") != expected_release_id or release_path.name != expected_release_id:
            raise OSSSkillIngestionError("release identity mismatch")

    @staticmethod
    def _approval(approved_by: str, reason: str) -> tuple[str, str]:
        actor = str(approved_by or "").strip()
        explanation = str(reason or "").strip()
        if not actor or len(explanation) < 8:
            raise OSSSkillIngestionError("explicit approver and meaningful approval reason are required")
        return actor, explanation

    @staticmethod
    def _load_json(path: Path) -> dict[str, object]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OSSSkillIngestionError(f"invalid ingestion state: {path.name}") from exc
        if not isinstance(value, dict):
            raise OSSSkillIngestionError(f"invalid ingestion state: {path.name}")
        return value

    @staticmethod
    def _verify_files(root: Path, records: Sequence[Mapping[str, object]]) -> None:
        expected: set[str] = set()
        for item in records:
            path = _safe_path(str(item.get("path") or ""))
            expected.add(path)
            target = root.joinpath(*PurePosixPath(path).parts)
            if not target.is_file():
                raise OSSSkillIngestionError(f"ingestion file missing: {path}")
            data = target.read_bytes()
            if _sha256(data) != item.get("sha256") or len(data) != item.get("size"):
                raise OSSSkillIngestionError(f"ingestion file integrity failure: {path}")
        actual = {
            file.relative_to(root).as_posix()
            for file in root.rglob("*")
            if file.is_file()
        }
        if actual != expected:
            raise OSSSkillIngestionError("ingestion directory contains unmanifested files")

    def _record_event(self, event: str, **details: object) -> None:
        event_id = f"{utc_now().replace(':', '').replace('-', '')}-{os.urandom(8).hex()}"
        _write_json_atomic(
            self.audit_root / f"{event_id}.json",
            {"event": event, "recorded_at": utc_now(), **details},
        )


__all__ = [
    "Candidate",
    "Dependency",
    "OSSSkillIngestion",
    "OSSSkillIngestionError",
    "SourceProvenance",
]

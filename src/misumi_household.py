"""Read-only adapter for the canonical household repository."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional


ALLOWED_SUFFIXES = {".md", ".txt", ".yaml", ".yml", ".json", ".csv", ".tsv"}
DOMAIN_PATHS = {
    "tasks": ("agent-tasks",),
    "food": ("household/food", "household/recipes"),
    "shopping": ("household/food/shopping-list.md",),
    "recipes": ("household/recipes",),
    "cleaning": ("household/cleaning",),
    "records": ("household/records",),
    "plants": ("household/plants",),
    "finances": ("household/finances",),
    "maintenance": (
        "household/maintenance",
        "agent-tasks/inbox",
        "agent-tasks/odysseus",
        "agent-tasks/misumi",
        "agent-tasks/review",
        "agent-tasks/blocked-human",
    ),
}

DOMAIN_TERMS = {
    "shopping": {"shopping", "grocery", "groceries", "buy"},
    "food": {"food", "stock", "inventory", "meal", "meals", "cook", "cooking"},
    "recipes": {"recipe", "recipes"},
    "cleaning": {"clean", "cleaning", "chore", "chores", "rota"},
    "records": {"record", "records", "album", "albums", "music", "play"},
    "plants": {"plant", "plants", "watering", "watered"},
    "finances": {"budget", "finance", "finances", "receipt", "subscription"},
    "maintenance": {"maintenance", "repair", "repairs", "broken", "urgent", "open-loop", "open-loops"},
    "tasks": {"task", "tasks", "blocked", "backlog"},
}


# Words that carry no evidence on their own: a line that shares only these with a question is not an answer to it.
_STOP_TERMS = frozenset({
    "about", "after", "all", "and", "answer", "any", "are", "can", "could", "current", "currently", "data", "did", "does",
    "exists", "explain", "fewer", "for", "from", "has", "have", "how", "in", "into", "is", "its", "language", "may", "more",
    "now", "of", "on", "only", "or", "our", "over", "plain", "please", "reply", "say", "should", "soon", "tell", "than",
    "that", "the", "them", "then", "there", "they", "this", "to", "today", "tomorrow", "tonight", "was", "were", "what",
    "when", "where", "which", "who", "will", "with", "words", "would", "yesterday", "you", "your",
})
_TERM = re.compile(r"[A-Za-z0-9_]{2,}")
# Lines that describe the repository rather than state a household fact: placeholders and to-dos, notes about views or
# features that do not exist yet, and navigation pointers to another file. They are never evidence for an answer.
_NON_FACT_LINE = re.compile(r"\bTODO\b|_TODO_|\bYYYY-MM-DD\b|\bfuture[- ](?:views?|facing|work|features?)\b", re.IGNORECASE)
_POINTER_LINE = re.compile(r"\]\([^)\s]+\.(?:md|ya?ml|csv|tsv|json|txt)\)", re.IGNORECASE)
_DOC_FILES = frozenset({"readme.md"})  # directory documentation, not household data
_ENTRY_START = re.compile(r"^(\s*)-\s+[A-Za-z_][\w-]*:(?:\s|$)")
_EXAMPLE_FLAG = re.compile(r"^\s*(?:-\s+)?example:\s*true\b", re.IGNORECASE)
_ENTRY_KEY = re.compile(r"^\s*(?:-\s+)?(artist|title|name|item|plant|task):\s*(.*?)\s*$", re.IGNORECASE)
_LABEL_ORDER = ("name", "item", "plant", "task", "title", "artist")


def _norm(term: str) -> str:
    """Case-fold and drop a plural 's' so 'records' matches 'record' (applied to question and line alike)."""
    term = term.lower()
    return term[:-1] if len(term) > 3 and term.endswith("s") and not term.endswith("ss") else term


def _yaml_entries(lines: List[str]) -> List[Dict[str, object]]:
    """List entries of a YAML file ('- key: value' blocks): line span, display label and whether it is a demonstration entry."""
    starts = [(index, len(match.group(1))) for index, line in enumerate(lines) if (match := _ENTRY_START.match(line))]
    entries = []
    for start, indent in starts:
        end = len(lines)
        for index in range(start + 1, len(lines)):
            line = lines[index]
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if len(line) - len(line.lstrip()) <= indent:
                end = index
                break
        keys: Dict[str, str] = {}
        for line in lines[start:end]:
            found = _ENTRY_KEY.match(line)
            if found and found.group(1).lower() not in keys:
                keys[found.group(1).lower()] = found.group(2).strip().strip("\"'")
        label = ""
        if keys.get("artist") and keys.get("title"):
            label = f"{keys['artist']} - {keys['title']}"
        else:
            label = next((keys[key] for key in _LABEL_ORDER if keys.get(key)), "")
        entries.append({
            "start": start, "end": end, "label": label,
            "example": any(_EXAMPLE_FLAG.match(line) for line in lines[start:end]),
        })
    return entries


def infer_household_domain(query: str) -> Optional[str]:
    """Return the narrow canonical domain most explicitly named by a request."""
    terms = set(re.findall(r"[A-Za-z0-9_-]{2,}", (query or "").lower()))
    selected = None
    selected_score = 0
    for domain, indicators in DOMAIN_TERMS.items():
        score = len(terms.intersection(indicators))
        if score > selected_score:
            selected = domain
            selected_score = score
    return selected


def configured_household_root() -> Optional[Path]:
    value = (
        os.getenv("MISUMI_HOUSEHOLD_ROOT")
        or os.getenv("FLAT_KNOWLEDGEBASE_ROOT")
        or os.getenv("MISUMI_SOURCE_ROOT")
        or ""
    ).strip()
    if value:
        return Path(value).expanduser()
    home = Path.home()
    for candidate in (
        home / "Documents" / "flat-knowledgebase",
        home / "Documents" / "Claude" / "Projects" / "homeBase",
    ):
        if candidate.is_dir():
            return candidate
    return None


class HouseholdReadOnlyAdapter:
    """Path-confined reader with no mutation API."""

    def __init__(self, root: Optional[Path | str] = None):
        configured = Path(root).expanduser() if root else configured_household_root()
        self.root = configured.resolve() if configured else None

    @property
    def reachable(self) -> bool:
        return bool(self.root and self.root.is_dir())

    def _resolve(self, relative: str | Path) -> Path:
        if not self.root:
            raise FileNotFoundError("household repository is not configured")
        raw = str(relative or "").replace("\\", "/").strip().lstrip("/")
        if not raw or raw.startswith(".") or "/." in raw:
            raise ValueError("hidden or empty paths are not readable")
        candidate = (self.root / raw).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("path escapes household repository") from exc
        if candidate.suffix.lower() not in ALLOWED_SUFFIXES:
            raise ValueError("unsupported household file type")
        return candidate

    def domains(self) -> List[Dict[str, object]]:
        result = []
        for name, entries in DOMAIN_PATHS.items():
            present = False
            if self.root:
                present = any((self.root / entry).exists() for entry in entries)
            result.append({"id": name, "present": present, "paths": list(entries)})
        return result

    def iter_files(self, domain: Optional[str] = None) -> Iterable[Path]:
        if not self.root:
            return []
        entries = DOMAIN_PATHS.get(domain, ()) if domain else ("household", "agent-tasks")
        seen = set()
        files: List[Path] = []
        for entry in entries:
            base = (self.root / entry).resolve()
            try:
                base.relative_to(self.root)
            except ValueError:
                continue
            candidates = [base] if base.is_file() else base.rglob("*") if base.is_dir() else []
            for path in candidates:
                if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
                    continue
                resolved = path.resolve()
                try:
                    resolved.relative_to(self.root)
                except ValueError:
                    continue
                if any(part.startswith(".") for part in resolved.relative_to(self.root).parts):
                    continue
                if resolved not in seen:
                    seen.add(resolved)
                    files.append(resolved)
        return sorted(files)

    def read(self, relative: str, start_line: int = 1, max_lines: int = 80) -> Dict[str, object]:
        path = self._resolve(relative)
        if not path.is_file():
            raise FileNotFoundError(relative)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(start_line))
        count = max(1, min(int(max_lines), 200))
        selected = lines[start - 1:start - 1 + count]
        rel = path.relative_to(self.root).as_posix()
        return {
            "path": rel,
            "line_start": start,
            "line_end": start + len(selected) - 1 if selected else start,
            "text": "\n".join(selected),
        }

    def search(self, query: str, domain: Optional[str] = None, limit: int = 10) -> List[Dict[str, object]]:
        """Lexical lookup over household files that returns evidence or nothing.

        A line qualifies only if it states a household fact (not a placeholder, a note about an unbuilt view, a pointer to
        another file, a comment, or a demonstration entry) and shares enough of the question's content words with it: one
        word for a question of one or two content words, otherwise two.
        """
        terms: List[str] = []
        for raw in _TERM.findall(query or ""):
            if raw.lower() in _STOP_TERMS:
                continue
            term = _norm(raw)
            if term not in terms:
                terms.append(term)
        if not terms:
            return []
        floor = 1 if len(terms) <= 2 else 2
        hits = []
        for path in self.iter_files(domain):
            if path.name.lower() in _DOC_FILES:
                continue
            rel = path.relative_to(self.root).as_posix()
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            structured = path.suffix.lower() in {".yaml", ".yml"}
            entries = _yaml_entries(lines) if structured else []
            for number, line in enumerate(lines, 1):
                stripped = line.strip()
                if not stripped or (structured and stripped.startswith("#")):
                    continue
                if _NON_FACT_LINE.search(line) or _POINTER_LINE.search(line):
                    continue
                entry = next((item for item in entries if item["start"] <= number - 1 < item["end"]), None)
                if entry is not None and entry["example"]:
                    continue
                line_terms = {_norm(term) for term in _TERM.findall(line)}
                matched = sum(1 for term in terms if term in line_terms)
                if matched < floor:
                    continue
                hit: Dict[str, object] = {"path": rel, "line": number, "snippet": stripped[:500], "score": matched}
                if entry is not None and entry["label"]:
                    hit["entry"] = entry["label"]
                hits.append(hit)
        hits.sort(key=lambda item: (-int(item["score"]), str(item["path"]), int(item["line"])))
        return hits[:max(1, min(int(limit), 50))]

    def git_state(self) -> Dict[str, object]:
        if not self.root:
            return {"available": False, "dirty": None, "error": "household repository is not configured"}
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), "status", "--short", "--branch"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            lines = [line for line in result.stdout.splitlines() if line]
            changes = [line for line in lines if not line.startswith("##")]
            return {
                "available": result.returncode == 0,
                "dirty": bool(changes) if result.returncode == 0 else None,
                "summary": lines[:30],
            }
        except Exception as exc:
            return {"available": False, "dirty": None, "error": str(exc)}

    def content_fingerprint(self) -> str:
        """Hash readable canonical content for non-mutation smoke tests."""
        digest = hashlib.sha256()
        for path in self.iter_files():
            digest.update(path.relative_to(self.root).as_posix().encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()

    def status(self) -> Dict[str, object]:
        return {
            "reachable": self.reachable,
            "root": str(self.root) if self.root else None,
            "domains": self.domains(),
            "git": self.git_state(),
            "mode": "read_only",
            "writes_allowed": False,
        }

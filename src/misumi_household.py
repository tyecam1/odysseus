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
    "about", "after", "all", "am", "and", "answer", "any", "are", "been", "being", "can", "could", "current", "currently",
    "data", "did", "do", "does", "doing", "done", "exists", "explain", "fewer", "for", "from", "get", "got", "had", "has",
    "have", "here", "how", "in", "into", "is", "it", "its", "language", "let", "many", "may", "me", "more", "much", "my",
    "no", "not", "now", "of", "off", "on", "only", "or", "other", "our", "out", "over", "plain", "please", "reply", "same",
    "say", "should", "so", "some", "soon", "such", "tell", "than", "that", "the", "them", "then", "there", "they", "this",
    "to", "today", "tomorrow", "tonight", "us", "very", "was", "we", "were", "what", "when", "where", "which", "who",
    "whose", "will", "with", "words", "would", "yesterday", "yet", "you", "your",
})
# Words that may accompany a request to show a whole list or table ("what is on the cleaning rota this week").
_LISTING_FILLER = frozenset({"week", "next", "current"})
# Domain indicator words that are also what a question asks about ("what tasks are blocked?"): they stay evidence terms.
_STATUS_WORDS = frozenset({"blocked", "backlog", "urgent", "open-loop", "open-loops", "broken", "repair", "repairs", "maintenance"})
_TERM = re.compile(r"[A-Za-z0-9_]{2,}")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_TABLE_SEPARATOR = re.compile(r"^\|?[\s:|-]*-[\s:|-]*\|?$")
_HEADING = re.compile(r"^#{1,6}\s")
_FILE_METADATA = re.compile(r"^(?:status|updated|created|version|schema|source)\s*:", re.IGNORECASE)  # file-level, at column 0
_EMPTY_YAML_VALUE = re.compile(r"^(?:-\s+)?[\w-]+:\s*(?:\[\]|\{\}|null|~|\"\"|'')?\s*$", re.IGNORECASE)
# Lines that describe the repository rather than state a household fact: notes about views/features that do not exist yet and
# unfilled template text.
_NOT_BUILT_NOTE = re.compile(
    r"\bfuture[- ](?:views?|facing|features?)\b|\b(?:is|are|will be)\s+(?:a\s+)?future\b|\bfuture:|\bcoming\s+soon\b"
    r"|\bnot\s+yet\s+(?:built|implemented|available|supported)\b|\bplanned:|\bYYYY-MM-DD\b|_populate\b[^_]*_",
    re.IGNORECASE,
)
_TODO = re.compile(r"\bTODO\b|_TODO_")
_DOC_FILES = frozenset({"readme.md"})  # directory documentation, not household data
_ENTRY_START = re.compile(r"^(\s*)-\s+([A-Za-z_][\w-]*:(?:\s|$))")
_EXAMPLE_FLAG = re.compile(r"^example:\s*true\b", re.IGNORECASE)
_ENTRY_KEY = re.compile(r"^(artist|title|name|item|plant|task):\s*(.*?)\s*$", re.IGNORECASE)
_LABEL_ORDER = ("name", "item", "plant", "task", "title", "artist")
_ITEM_LINE = re.compile(r"^(?:[-*+]\s|\d+[.)]\s|\||[\w-]+:\s)")
_LIST_ITEM = re.compile(r"^(?:[-*+]\s|\d+[.)]\s|\|)")  # a bullet, numbered item or table row (not a plain key: value)


def _norm(term: str) -> str:
    """Fold case, plural and common verb endings so 'tomatoes', 'watered' and 'watering' match 'tomato' and 'water'."""
    term = term.lower()
    if len(term) > 4 and term.endswith("ies"):
        return term[:-3] + "y"
    if len(term) > 5 and term.endswith("ing"):
        return term[:-3]
    if len(term) > 4 and term.endswith("ed"):
        return term[:-2]
    if len(term) > 4 and term.endswith("oes"):
        return term[:-2]
    if len(term) > 4 and term.endswith(("shes", "ches", "xes", "zes", "sses")):
        return term[:-2]
    if len(term) > 3 and term.endswith("s") and not term.endswith("ss"):
        return term[:-1]
    return term


def _words(text: str) -> List[str]:
    return [_norm(word) for word in _TERM.findall(text.replace("_", " ").replace("-", " "))]


def _yaml_entries(lines: List[str]) -> List[Dict[str, object]]:
    """List entries of a YAML file ('- key: value' blocks): line span, display label and whether the entry itself is a demonstration.

    Only a key that belongs to the entry itself marks it as an example; an `example: true` inside a nested list does not.
    """
    entries = []
    for start, line in enumerate(lines):
        match = _ENTRY_START.match(line)
        if not match:
            continue
        indent = len(match.group(1))
        after_dash = line[indent + 1:]
        key_column = indent + 1 + (len(after_dash) - len(after_dash.lstrip()))
        end = len(lines)
        for index in range(start + 1, len(lines)):
            other = lines[index]
            if not other.strip() or other.lstrip().startswith("#"):
                continue
            if len(other) - len(other.lstrip()) <= indent:
                end = index
                break
        keys: Dict[str, str] = {}
        example = False
        for number in range(start, end):
            raw = lines[number]
            column = len(raw) - len(raw.lstrip())
            body = raw.strip()
            if number == start:
                body = body[1:].strip()  # the key after the dash is a direct key of this entry
                column = key_column
            elif column != key_column:
                continue
            if _EXAMPLE_FLAG.match(body):
                example = True
            found = _ENTRY_KEY.match(body)
            if found and found.group(1).lower() not in keys:
                keys[found.group(1).lower()] = found.group(2).strip().strip("\"'")
        if keys.get("artist") and keys.get("title"):
            label = f"{keys['artist']} - {keys['title']}"
        else:
            label = next((keys[key] for key in _LABEL_ORDER if keys.get(key)), "")
        entries.append({"start": start, "end": end, "label": label, "example": example})
    return entries


def _entry_text(lines: List[str], entry: Dict[str, object]) -> str:
    """The recorded facts of one YAML entry as one short string ('name: tomatoes; quantity: "1 carton"; moods: late night, focused')."""
    parts: List[str] = []
    key = ""
    nested: List[str] = []

    def flush() -> None:
        if key and nested:
            parts.append(f"{key}: " + ", ".join(nested))
        nested.clear()

    for number in range(int(entry["start"]), int(entry["end"])):
        text = _fact_text(lines[number], True, False)
        raw = lines[number].strip()
        bare = re.match(r"^(?:-\s+)?([\w-]+):\s*(?:#.*)?$", raw)
        if bare:
            flush()
            key = bare.group(1)
            continue
        if not text or text.lstrip("- ").lower().startswith("example:"):
            continue
        if text.startswith("- ") and key and not re.match(r"^-\s+[\w-]+:\s", text):
            nested.append(text[2:].strip().strip("\"'"))
            continue
        flush()
        key = ""
        parts.append(text[2:].strip() if text.startswith("- ") else text)
    flush()
    return "; ".join(parts)[:300]


def _table_context(header: str, row: str) -> str:
    """A table row with its column names ('Task: Bathroom; This week: Alice; Next week: Bob'), or '' when they do not line up."""
    names = [cell.strip() for cell in header.strip().strip("|").split("|")]
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    if len(names) != len(cells) or not any(cells):
        return ""
    return "; ".join(f"{name}: {cell}" for name, cell in zip(names, cells) if name and cell)[:300]


def _fact_text(line: str, structured: bool, table_header: bool) -> str:
    """The part of a line that states a household fact, or '' when the line is structure, a placeholder or a note about the repository."""
    text = line.strip()
    if not text:
        return ""
    if structured:
        if text.startswith("#"):
            return ""
        text = re.sub(r"\s+#.*$", "", text).strip()
        if not text or _EMPTY_YAML_VALUE.match(text) or (_FILE_METADATA.match(line) and not line[:1].isspace()):
            return ""
    else:
        if _HEADING.match(text) or _TABLE_SEPARATOR.match(text) or table_header:
            return ""
    if any(label.strip("`*_ ").lower() == target.rsplit("/", 1)[-1].lower() for label, target in _LINK.findall(text)):
        return ""  # navigation pointer: the link text is the file name
    if _NOT_BUILT_NOTE.search(text):
        return ""
    todos = len(_TODO.findall(text))
    if todos and (todos > 1 or len(re.sub(r"\bTODO\b|_TODO_|[-*\[\]|:=_`]", " ", text).split()) <= 6):
        return ""  # an unfilled placeholder, not a recorded fact
    return text


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

        A line qualifies only if it states a household fact (not a heading, a placeholder, an empty value, a note about an unbuilt
        view, a pointer to another file, a YAML comment, or a demonstration entry) and shares enough of the question's content
        words with it: one word for a question of one or two content words, otherwise two. The domain's own indicator words
        ("records", "stock") select the directory and do not count as evidence. A question that only names a file ("what is on the
        shopping list") lists that file's real items.
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
        domain_terms = {_norm(word) for word in DOMAIN_TERMS.get(domain or "", ()) if word not in _STATUS_WORDS}
        content = [term for term in terms if term not in domain_terms]
        floor = 1 if len(content) <= 2 else 2

        def names_the_file(path: Path) -> bool:
            stem = set(_words(path.stem))
            return bool(stem & set(terms)) and all(
                term in stem or term in domain_terms or term in _LISTING_FILLER for term in terms
            )

        files = [path for path in self.iter_files(domain) if path.name.lower() not in _DOC_FILES]
        listed = [path for path in files if names_the_file(path)]
        if listed:
            files = listed  # the question names a list or table: answer from it alone
        elif not content:
            return []  # only the domain's own words: nothing to look up
        hits = []
        for path in files:
            rel = path.relative_to(self.root).as_posix()
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            path_terms = set(_words(path.stem))
            listing = bool(listed)
            path_bonus = len(path_terms & set(terms))
            structured = path.suffix.lower() in {".yaml", ".yml"}
            entries = _yaml_entries(lines) if structured else []
            table_head = ""
            for number, line in enumerate(lines, 1):
                covering = [item for item in entries if item["start"] <= number - 1 < item["end"]]
                if any(item["example"] for item in covering):
                    continue
                table_header = (
                    not structured and line.lstrip().startswith("|")
                    and number < len(lines) and bool(_TABLE_SEPARATOR.match(lines[number].strip()))
                )
                if table_header:
                    table_head = line
                elif not line.lstrip().startswith("|"):
                    table_head = ""
                text = _fact_text(line, structured, table_header)
                if not text:
                    continue
                line_terms = set(_words(text))
                matched = sum(1 for term in content if term in line_terms)
                item = bool(_ITEM_LINE.match(text))
                if matched < floor and not (listing and _LIST_ITEM.match(text)):
                    continue
                hit: Dict[str, object] = {
                    "path": rel, "line": number, "snippet": text[:500], "score": matched, "_item": item, "_path": path_bonus,
                }
                label = next((str(entry["label"]) for entry in covering if entry["label"]), "")
                if label:
                    hit["entry"] = label
                if covering:
                    context = _entry_text(lines, covering[0])
                elif table_head and text.startswith("|"):
                    context = _table_context(table_head, text)
                else:
                    context = ""
                if context and context != text:
                    hit["context"] = context
                if listing and matched < floor:
                    hit["listed"] = True  # included because the question names this list, not because of a word match
                hits.append(hit)
        # Best match first; among equals prefer recorded items (list entries, table rows, key: value) over prose.
        hits.sort(key=lambda row: (-int(row["score"]), -int(row["_path"]), not row["_item"], str(row["path"]), int(row["line"])))
        for row in hits:
            row.pop("_item")
            row.pop("_path")
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

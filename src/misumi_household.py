"""Read-only adapter for the canonical household repository."""

from __future__ import annotations

import difflib
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
    "an", "as", "at", "be", "by", "if", "up", "just", "also", "go",
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
_EXAMPLE_FLAG = re.compile(r"^example:\s*[\"']?(?:true|yes|y|1)[\"']?\s*(?:#.*)?$", re.IGNORECASE)
_ENTRY_KEY = re.compile(r"^(artist|title|name|item|plant|task):\s*(.*?)\s*$", re.IGNORECASE)
_LABEL_ORDER = ("name", "item", "plant", "task", "title", "artist")
_ITEM_LINE = re.compile(r"^(?:[-*+]\s|\d+[.)]\s|\||[\w-]+:\s)")
_LIST_ITEM = re.compile(r"^(?:[-*+]\s|\d+[.)]\s|\|)")  # a bullet, numbered item or table row (not a plain key: value)


# --- singular/plural normaliser ----------------------------------------------------------------------------------------
# One key per word for its singular and plural spellings. The key is internal (never shown): '-ie' and '-i' endings are
# folded to '-y' so cookie/cookies, chilli/chillies/chillis and pie/pies each share one key whichever rule a plural takes.
_IRREGULAR_PLURALS = {
    "men": "man", "women": "woman", "children": "child", "people": "person", "mice": "mouse", "geese": "goose",
    "teeth": "tooth", "feet": "foot", "oxen": "ox",
    "leaves": "leaf", "loaves": "loaf", "halves": "half", "knives": "knife", "wolves": "wolf", "shelves": "shelf",
    "calves": "calf", "lives": "life", "wives": "wife", "thieves": "thief", "scarves": "scarf", "elves": "elf", "selves": "self",
    "menus": "menu", "emus": "emu", "gurus": "guru", "haikus": "haiku", "tofus": "tofu", "gnus": "gnu", "tutus": "tutu",
    "buses": "bus", "gases": "gas", "lenses": "lens", "quizzes": "quiz", "irises": "iris",
}
_OE_SINGULARS = frozenset({"shoe", "toe", "oboe", "canoe", "hoe", "floe", "sloe", "roe", "doe", "foe"})
_CHE_SINGULARS = frozenset({"quiche", "brioche", "niche", "cache", "creche", "cliche", "moustache", "ache", "headache",
                            "avalanche", "panache", "tranche", "microfiche", "psyche"})
_INVARIANT = frozenset({"series", "species", "news", "molasses"})


def _singular(word: str) -> str:
    """The shared key of a word's singular and plural forms: eggs/egg, tomatoes/tomato, cookies/cookie, olives/olive, loaves/loaf,
    dumplings/dumpling, peaches/peach, quiches/quiche, glasses/glass. Words that only look plural (hummus, couscous) are kept."""
    w = word.lower().replace("’", "'")
    if w.endswith("'s"):
        w = w[:-2]
    w = w.strip("'")
    if w in _IRREGULAR_PLURALS:
        w = _IRREGULAR_PLURALS[w]
    elif len(w) > 3 and w not in _INVARIANT:
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("oes"):
            w = w[:-1] if w[:-1] in _OE_SINGULARS else w[:-2]
        elif w.endswith("ches") and w[:-1] in _CHE_SINGULARS:
            w = w[:-1]
        elif w.endswith(("sses", "shes", "ches", "xes", "zzes")):
            w = w[:-2]
        elif w.endswith("s") and not w.endswith(("ss", "us")):
            w = w[:-1]
    if len(w) > 2 and w.endswith("ie"):
        w = w[:-2] + "y"
    elif len(w) > 2 and w.endswith("i"):
        w = w[:-1] + "y"
    return w


def _norm(term: str) -> str:
    """Fold case, plural and common verb endings so 'tomatoes', 'watered' and 'watering' match 'tomato' and 'water'.

    The plural is folded first (with the tested normaliser above), then verb endings, so both forms of a word always share one
    key: 'dumplings' and 'dumpling' (previously 'dumpling' vs 'dumpl'), 'cookies' and 'cookie' (previously 'cooky' vs 'cookie').
    """
    term = _singular(term)
    if len(term) > 5 and term.endswith("ing"):
        return term[:-3]
    if len(term) > 4 and term.endswith("ed"):
        return term[:-2]
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
        entries.append({"start": start, "end": end, "label": label, "example": example, "key_column": key_column})
    return entries


_NULL_FIELD = re.compile(r"^(?:-\s+)?([\w-]+):\s*(?:null|~|\"\"|''|\[\])\s*(?:#.*)?$", re.IGNORECASE)
_ENTRY_TEXT_LIMIT = 300


def _entry_text(lines: List[str], entry: Dict[str, object], entries: List[Dict[str, object]], asked: Iterable[str] = (),
                matched: Iterable[str] = ()) -> str:
    """The recorded facts of one YAML entry as one short string ('name: tomatoes; quantity: "1 carton"; moods: late night, focused').

    Nested demonstration entries are left out, a field the question asked about that holds null is reported as 'not recorded', and the
    matched facts are always kept (and listed first) even when the entry is long enough to be shortened.
    """
    asked = set(asked)
    skip: set = set()
    for other in entries:
        if other is not entry and other["example"] and entry["start"] <= other["start"] and other["end"] <= entry["end"]:
            skip.update(range(int(other["start"]), int(other["end"])))
    parts: List[str] = []
    key = ""
    nested: List[str] = []

    def flush() -> None:
        if key and nested:
            parts.append(f"{key}: " + ", ".join(nested))
        nested.clear()

    for number in range(int(entry["start"]), int(entry["end"])):
        if number in skip:
            continue
        raw = lines[number].strip()
        empty = _NULL_FIELD.match(re.sub(r"\s+#.*$", "", raw))
        if empty and _norm(empty.group(1)) in asked:
            flush()
            key = ""
            parts.append(f"{empty.group(1)}: not recorded")
            continue
        text = _fact_text(lines[number], True, False)
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
    joined = "; ".join(parts)
    if len(joined) > _ENTRY_TEXT_LIMIT:
        wanted = {(item[2:] if item.startswith("- ") else item).strip() for item in matched}
        parts = [part for part in parts if part in wanted] + [part for part in parts if part not in wanted]
        joined = "; ".join(parts)
        joined = joined[:_ENTRY_TEXT_LIMIT - 1].rstrip() + "…"
    return joined


def _table_context(header: str, row: str) -> str:
    """A table row with its column names ('Task: Bathroom; This week: Alice; Next week: Bob'), or '' when they do not line up."""
    names = [cell.strip() for cell in header.strip().strip("|").split("|")]
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    if len(names) != len(cells) or not any(cells):
        return ""
    return "; ".join(f"{name}: {cell}" for name, cell in zip(names, cells) if name and cell)[:300]


def _value_part(text: str, structured: bool) -> str:
    """For a YAML 'key: value' line, the value (field names do not count as evidence); otherwise the whole text."""
    if not structured:
        return text
    found = re.match(r"^(?:-\s+)?[\w-]+:\s*(.*)$", text)
    return found.group(1) if found else text.lstrip("- ")


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


# --- item resolution for stock questions ---------------------------------------------------------------------------------
# "Do we (still) have any X (left) in stock?" is answered by resolving X to a recorded item, not by counting shared words. The
# question's scaffolding is removed by pattern from the two ends of the question; what is left is the item mention. A mention
# resolves only to a record whose whole name (or alias) has the same words; anything less is reported as unconfirmed.

FOUND, NOT_PRESENT, AMBIGUOUS, UNRESOLVED = "found", "not_present", "ambiguous", "unresolved"
_INVENTORY_FILE = re.compile(r"stock|inventory|pantry|larder|freezer|fridge|cupboard", re.IGNORECASE)
_CONTRACTIONS = (
    (r"\bwe're\b", "we are"), (r"\bwe've\b", "we have"), (r"\bi've\b", "i have"), (r"\bdon't\b", "do not"),
    (r"\bdidn't\b", "did not"), (r"\bhaven't\b", "have not"), (r"\bhasn't\b", "has not"), (r"\bisn't\b", "is not"),
    (r"\baren't\b", "are not"), (r"\bthere's\b", "there is"), (r"\bwhat's\b", "what is"), (r"\bit's\b", "it is"),
)
_QUALIFIERS = r"(?:not|still|currently|even|already|just|all|completely|totally|now)\s+"
_OUT_OF = r"(?:out\s+of|low\s+on|short\s+(?:of|on)|running\s+(?:low\s+on|out\s+of))"
# (pattern, marks the question as a stock question). Each pattern is anchored at the start of what is left.
_SCAFFOLD_PREFIXES = tuple((re.compile(rf"^(?:{pattern})(?:\s+|$)"), trigger) for pattern, trigger in (
    (rf"(?:do|did|does)\s+(?:not\s+)?(?:we|i|you|they)\s+(?:{_QUALIFIERS})*(?:have|has|got|own)", True),
    (rf"(?:have|has)\s+(?:not\s+)?(?:we|i|you)\s+(?:{_QUALIFIERS})*got", True),
    (rf"(?:have|has|did)\s+(?:not\s+)?(?:we|i|you)\s+(?:{_QUALIFIERS})*(?:run|ran|gone|went)\s+out\s+of", True),
    (rf"(?:are|were)\s+(?:not\s+)?(?:we|you)\s+(?:{_QUALIFIERS})*{_OUT_OF}", True),
    (rf"we\s+are\s+(?:{_QUALIFIERS})*{_OUT_OF}", True),
    (rf"we\s+(?:{_QUALIFIERS})*(?:have|got)", True),
    (rf"(?:is|are)\s+there(?:\s+{_QUALIFIERS[:-3]})*", True),
    (r"how\s+(?:much|many)", True),
    (r"what\s+(?:quantity|amount)\s+of", True),
    (r"(?:got|any)", True),
    (r"(?:(?:can|could|would)\s+you\s+(?:please\s+)?)?(?:check|tell\s+me|see|look)(?:\s+(?:if|whether))?", False),
    (r"(?:please|hey|hi|ok|okay|so|um|uh|and|but|also|if|whether|is|are)", False),
    (r"(?:still|even|currently|some|more|enough|a|an|the|of|our|my)", False),
))
_PLACE = r"(?:the\s+|our\s+)?(?:stock|inventory|fridge|freezer|cupboards?|pantry|larder|house|flat|kitchen)"
_SCAFFOLD_SUFFIXES = tuple((re.compile(rf"(?:^|\s+)(?:{pattern})$"), trigger) for pattern, trigger in (
    (r"in\s+stock", True),
    (rf"(?:in|at)\s+{_PLACE}", True),
    (r"at\s+home", True),
    (r"(?:left|remaining)(?:\s+over)?", True),
    (r"(?:do|did)\s+(?:we|i|you)\s+(?:still\s+)?(?:have|got)", True),
    (r"have\s+(?:we|i|you)\s+(?:still\s+)?got", True),
    (r"(?:we|i)\s+(?:still\s+)?(?:have|got)", True),
    (r"(?:is|are)\s+there", True),
    (r"(?:still|anymore|any\s+more|at\s+the\s+moment|right\s+now|now|please|at\s+all|or\s+not|yet|then|currently|today|is|are)",
     False),
))
_WH_QUESTION = re.compile(r"^(?:what|when|where|which|who|whose|why|how)\b(?!\s+(?:much|many)\b)(?!\s+(?:quantity|amount)\s+of\b)")
# A mention containing one of these is not a parsed item name ("food for dinner", "anything to cook"): never a confident "no".
_NON_ITEM_WORDS = frozenset({
    "for", "to", "with", "without", "before", "after", "about", "what", "when", "which", "who", "how", "why", "if", "we", "i",
    "you", "it", "that", "this", "them", "those", "these", "anything", "something", "everything", "nothing", "stuff", "thing",
    "things", "food", "ingredient", "ingredients", "enough", "is", "are", "do", "does", "have", "has", "make", "cook", "can",
    "should", "could", "would", "or", "but", "not",
})
_LINK_WORDS = frozenset({"and", "of", "the", "a", "an", "with", "in", "on"})
_PHRASE_TOKEN = re.compile(r"[^\W_]+(?:'[^\W_]+)?")
_ZERO_QUANTITY = re.compile(
    r"^[\"']?\s*(?:0+(?:\.0+)?(?=\s|$|[\"'])|none\b|zero\b|out\b|empty\b|used\s+up\b|finished\b|run\s+out\b|all\s+gone\b)",
    re.IGNORECASE,
)


def _phrase_tokens(text: str) -> List[str]:
    return _PHRASE_TOKEN.findall((text or "").lower().replace("’", "'").replace("&", " and "))


def phrase_key(text: str) -> tuple:
    """Normalised word sequence of an item name or mention: 'Coconut Milk' -> ('coconut', 'milk'), 'cookies' -> ('cooky',)."""
    return tuple(_singular(token) for token in _phrase_tokens(text))


def stock_item_mention(question: str) -> Optional[Dict[str, object]]:
    """The item a stock question asks about, with the question's scaffolding removed by pattern from both ends.

    Returns None when the text is not a stock question (no presence or quantity phrasing, or an open wh-question such as "what is
    the milk expiry"), otherwise {"mention": "olive oil"} (the mention may be "" when the question names no item).
    """
    text = (question or "").lower().replace("’", "'")
    for pattern, replacement in _CONTRACTIONS:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"[?!.,;:]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if _WH_QUESTION.match(text):
        return None
    triggered = False
    changed = True
    while changed and text:
        changed = False
        for pattern, trigger in _SCAFFOLD_PREFIXES:
            match = pattern.match(text)
            if match and match.end():
                text = text[match.end():].strip()
                triggered = triggered or trigger
                changed = True
                break
        for pattern, trigger in _SCAFFOLD_SUFFIXES:
            match = pattern.search(text)
            if match:
                text = text[:match.start()].strip()
                triggered = triggered or trigger
                changed = True
                break
    if not triggered:
        return None
    return {"mention": text}


def _head(key: tuple) -> str:
    return key[-1] if key else ""


def _contains(outer: tuple, inner: tuple) -> bool:
    """`inner` occurs in `outer` as a whole run of words (token boundaries, same order)."""
    size = len(inner)
    return 0 < size <= len(outer) and any(outer[i:i + size] == inner for i in range(len(outer) - size + 1))


def _near_miss(mention: tuple, key: tuple) -> int:
    """How strongly a record that is NOT an exact match still overlaps the mention (0 = unrelated).

    3: one phrase lies whole inside the other ("olive oil" / "olives", "soy sauce" / "dark soy sauce", "coconut milk" / "milk");
    2: they share a head noun ("chilli sauce" / "hot sauces"); 1: a spelling near-miss ("brocoli" / "broccoli").
    A shared modifier alone ("red peppers" / "red onions") is not a near miss.
    """
    if _contains(mention, key) or _contains(key, mention):
        return 3
    shared = (set(mention) & set(key)) - _LINK_WORDS
    if shared and (_head(mention) in shared or _head(key) in shared):
        return 2
    joined, other = " ".join(mention), " ".join(key)
    if difflib.SequenceMatcher(None, joined, other).ratio() >= 0.85:
        return 1
    for word in mention:
        for recorded in key:
            if len(word) >= 4 and len(recorded) >= 4 and word not in _LINK_WORDS and \
                    difflib.SequenceMatcher(None, word, recorded).ratio() >= 0.85 and (word == _head(mention) or recorded == _head(key)):
                return 1
    return 0


def _entry_fields(lines: List[str], entry: Dict[str, object]) -> Dict[str, object]:
    """Direct fields of one YAML list entry: {'name': ..., 'name@line': 12, 'aliases[]': [...]} (nested entries ignored)."""
    key_column = int(entry["key_column"])
    fields: Dict[str, object] = {}
    current = None
    for number in range(int(entry["start"]), int(entry["end"])):
        raw = lines[number]
        if number == int(entry["start"]):
            body, column = raw.strip()[1:].strip(), key_column
        else:
            body, column = raw.strip(), len(raw) - len(raw.lstrip())
        if not body or body.startswith("#"):
            continue
        body = re.sub(r"\s+#.*$", "", body).strip()
        if column == key_column:
            found = re.match(r"^([\w-]+):\s*(.*)$", body)
            current = found.group(1).lower() if found else None
            if found and current not in fields:
                fields[current] = found.group(2).strip()
                fields[current + "@line"] = number + 1
        elif column > key_column and current and body.startswith("- "):
            fields.setdefault(current + "[]", []).append(body[2:].strip().strip("\"'"))
    return fields


def _unquote(value: object) -> str:
    return str(value or "").strip().strip("\"'").strip()


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
        if domain == "food":
            resolution = self.resolve_item(query, domain)
            if resolution is not None:  # a stock question about one item: answered by entity resolution, never by word overlap
                return self._resolution_hits(resolution)[:max(1, min(int(limit), 50))]
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
        content = [term for term in terms if term not in domain_terms and term not in _LISTING_FILLER]  # "week" is not evidence
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
                line_terms = set(_words(_value_part(text, structured)))  # a field NAME is not evidence, only what it holds
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
                    context = _entry_text(lines, covering[0], entries, terms, [text])
                elif table_head and text.startswith("|"):
                    context = _table_context(table_head, text)
                else:
                    context = ""
                if context and context != text:
                    hit["context"] = context
                if listing and matched < floor:
                    hit["listed"] = True  # included because the question names this list, not because of a word match
                hits.append(hit)
        hits = self._entry_level(hits, files, content, floor, terms) if content else hits
        # Best match first; among equals prefer recorded items (list entries, table rows, key: value) over prose.
        hits.sort(key=lambda row: (-int(row["score"]), -int(row["_path"]), not row["_item"], str(row["path"]), int(row["line"])))
        for row in hits:
            row.pop("_item")
            row.pop("_path")
        return hits[:max(1, min(int(limit), 50))]

    def item_index(self, domain: Optional[str] = "food") -> Dict[str, object]:
        """Canonical index of the recorded items in the domain's inventory files (stock.yaml and the like).

        Each record: stable id (its own `id:` field, else path:line), canonical name, aliases, the whole-phrase keys of the name and
        aliases, the file and line that hold the name, the quantity as recorded, and whether that quantity says it ran out.
        Demonstration entries (`example: true`) and nested entries are not records. `read` lists the inventory files read.
        """
        records: List[Dict[str, object]] = []
        read: List[str] = []
        for path in self.iter_files(domain):
            if path.suffix.lower() not in {".yaml", ".yml"} or not _INVENTORY_FILE.search(path.stem):
                continue
            rel = path.relative_to(self.root).as_posix()
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            read.append(rel)
            entries = _yaml_entries(lines)
            for entry in entries:
                if entry["example"] or any(o is not entry and o["start"] < entry["start"] < o["end"] for o in entries):
                    continue
                fields = _entry_fields(lines, entry)
                name_field = "name" if _unquote(fields.get("name")) else "item" if _unquote(fields.get("item")) else ""
                name = _unquote(fields.get(name_field)) if name_field else ""
                if not name or name.lower() in {"null", "~"}:
                    continue
                aliases = list(fields.get("aliases[]") or []) + list(fields.get("alias[]") or [])
                for field in ("aliases", "alias", "also_known_as"):
                    inline = _unquote(fields.get(field)).strip("[]")
                    aliases.extend(part.strip().strip("\"'") for part in inline.split(",") if part.strip().strip("\"'"))
                keys = []
                for text in [name] + aliases:
                    key = phrase_key(text)
                    if key and key not in keys:
                        keys.append(key)
                quantity = _unquote(fields.get("quantity"))
                if quantity.lower() in {"null", "~"}:
                    quantity = ""
                line = int(fields.get(name_field + "@line") or int(entry["start"]) + 1)
                records.append({
                    "id": _unquote(fields.get("id")) or f"{rel}:{line}", "name": name, "aliases": aliases, "keys": keys,
                    "path": rel, "line": line, "quantity": quantity or None,
                    "category_key": phrase_key(_unquote(fields.get("category")).replace("_", " ")),
                    "out_of_stock": bool(quantity and _ZERO_QUANTITY.match(quantity)),
                    "_entry": entry, "_lines": lines, "_entries": entries,
                })
        return {"records": records, "read": read}

    def resolve_item(self, query: str, domain: Optional[str] = "food") -> Optional[Dict[str, object]]:
        """Resolve the item a stock question names to recorded items, with one of four outcomes.

        found: a record whose name or alias has exactly the mention's words (order-insensitive only when the word multisets are
        equal). ambiguous: no exact record, but records that partly match ("olive oil" vs "olives") - reported as candidates, never
        as yes or no. not_present: the inventory was read, the mention is a parsed item name, nothing matches it and nothing is a
        near miss. unresolved: the question names no recognisable item, or the inventory has no records.
        Returns None when the question is not a stock question or the domain has no inventory file (ordinary lookup applies).
        """
        parsed = stock_item_mention(query)
        if parsed is None:
            return None
        index = self.item_index(domain)
        if not index["read"]:
            return None
        records = index["records"]
        mention = str(parsed["mention"])
        key = phrase_key(mention)
        result: Dict[str, object] = {
            "mention": mention, "key": key, "read": index["read"], "checked": len(records), "records": [], "candidates": [],
        }
        if not records:
            result.update(outcome=UNRESOLVED, reason="the stock inventory has no recorded items")
            return result
        if not key:
            result.update(outcome=UNRESOLVED, reason="the question does not name an item")
            return result
        exact = [r for r in records if any(k == key or sorted(k) == sorted(key) for k in r["keys"])]
        if exact:
            result.update(outcome=FOUND, records=exact)
            return result
        unparsed = len(key) > 5 or bool(set(_phrase_tokens(mention)) & _NON_ITEM_WORDS)
        # In a mention that is not a clean item name ("eggs for breakfast") only whole-phrase or head-noun overlaps are candidates.
        probe = tuple(_singular(t) for t in _phrase_tokens(mention) if t not in _NON_ITEM_WORDS) if unparsed else key
        scored = []
        for record in records:
            strength = max(_near_miss(probe, k) for k in record["keys"]) if probe else 0
            category = record["category_key"]
            if not strength and probe and category and (_contains(category, probe) or _head(category) == _head(probe)):
                strength = 2  # the mention names the record's category ("cheese" for a brie filed under cheese): a candidate, not a no
            if strength and not (unparsed and strength < 2):
                scored.append((-strength, int(record["line"]), record))
        scored.sort(key=lambda row: (row[0], row[1]))
        result["candidates"] = [row[2] for row in scored]
        if unparsed:
            result.update(outcome=UNRESOLVED, reason="the question does not clearly name one item")
        elif scored:
            result.update(outcome=AMBIGUOUS)
        else:
            result.update(outcome=NOT_PRESENT)
        return result

    def _resolution_hits(self, resolution: Dict[str, object]) -> List[Dict[str, object]]:
        """Hits for a resolved stock question. not_present yields none (the caller's explicit no-match reply); ambiguous and
        unresolved yield one hit that says the item is not confirmed, so a partial match is never read out as a yes."""
        outcome = resolution["outcome"]
        mention = str(resolution["mention"])
        hits: List[Dict[str, object]] = []
        if outcome == FOUND:
            for record in resolution["records"]:
                lines, entry = record["_lines"], record["_entry"]
                context = _entry_text(lines, entry, record["_entries"], {"quantity"})
                if record["out_of_stock"]:
                    context += f"; recorded, but out of stock (quantity {record['quantity']})"
                hit = {
                    "path": record["path"], "line": record["line"], "snippet": lines[int(record["line"]) - 1].strip()[:500],
                    "score": len(resolution["key"]), "entry": record["name"], "resolution": FOUND, "record_id": record["id"],
                    "in_stock": False if record["out_of_stock"] else (True if record["quantity"] else None),
                }
                if context:
                    hit["context"] = context
                hits.append(hit)
        elif outcome == AMBIGUOUS:
            candidates = resolution["candidates"][:5]
            lead = candidates[0]
            named = ", ".join(
                f"{c['name']} (line {c['line']})" if c["path"] == lead["path"] else f"{c['name']} ({c['path']} line {c['line']})"
                for c in candidates
            )
            more = f" and {len(resolution['candidates']) - 5} more" if len(resolution["candidates"]) > 5 else ""
            hits.append({
                "path": lead["path"], "line": lead["line"], "score": 0, "resolution": AMBIGUOUS,
                "snippet": (f'Not confirmed: no stock record is named "{mention}". Recorded items that only partly match: {named}{more}.'
                            " I cannot say yes or no from a partial match."),
                "candidates": [{"id": c["id"], "name": c["name"], "path": c["path"], "line": c["line"]} for c in resolution["candidates"]],
            })
        elif outcome == UNRESOLVED:
            read = list(resolution["read"])
            what = f'which recorded item "{mention}" means' if mention else "which item the question asks about"
            reason = str(resolution.get("reason") or "")
            if "no recorded items" in reason:
                text = "Not confirmed: the stock inventory has no recorded items yet, so I cannot say whether it is in stock."
            else:
                text = f"Not confirmed: I could not tell {what}, so I cannot say whether it is in stock ({resolution['checked']} stock records read)."
                if resolution["candidates"]:
                    text += " Recorded items it may mean: " + ", ".join(
                        f"{c['name']} ({c['path']} line {c['line']})" for c in resolution["candidates"][:5]) + "."
            hits.append({
                "path": read[0], "line": 1, "score": 0, "resolution": UNRESOLVED, "snippet": text,
                "candidates": [{"id": c["id"], "name": c["name"], "path": c["path"], "line": c["line"]} for c in resolution["candidates"]],
            })
        return hits

    def _entry_level(self, hits: List[Dict[str, object]], files: List[Path], content: List[str], floor: int,
                     terms: List[str]) -> List[Dict[str, object]]:
        """Score each YAML entry as one unit: words spread over its fields (name: basil, location: kitchen, health: thriving)
        count together, and an entry yields one hit (its best line) instead of one per line."""
        result = [hit for hit in hits if not str(hit["path"]).lower().endswith((".yaml", ".yml"))]
        for path in files:
            if path.suffix.lower() not in {".yaml", ".yml"}:
                continue
            rel = path.relative_to(self.root).as_posix()
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            entries = _yaml_entries(lines)
            file_hits = [hit for hit in hits if hit["path"] == rel]
            outer = [e for e in entries if not any(o is not e and o["start"] <= e["start"] and e["end"] <= o["end"] for o in entries)]
            claimed: set = set()
            for entry in outer:
                if entry["example"]:
                    continue
                span = range(int(entry["start"]), int(entry["end"]))
                words: set = set()
                value_words: set = set()
                best = None
                matched_lines: List[str] = []
                for number in span:
                    if any(o is not entry and o["example"] and o["start"] <= number < o["end"] for o in entries):
                        continue
                    text = _fact_text(lines[number], True, False)
                    if not text:
                        continue
                    line_words = set(_words(text))
                    words |= line_words
                    value_words |= set(_words(_value_part(text, True)))
                    count = sum(1 for term in content if term in set(_words(_value_part(text, True))))
                    if count or any(term in line_words for term in terms):
                        matched_lines.append(text)  # what the question mentions at all stays in the answer, scored or not
                    if count and (best is None or count > best[0]):
                        best = (count, number, text)
                matched = sum(1 for term in content if term in words)
                if matched < floor or best is None or not any(term in value_words for term in content):
                    continue  # at least one question word must be in what the entry holds, not only in a field name
                claimed.update(number + 1 for number in span)
                hit: Dict[str, object] = {
                    "path": rel, "line": best[1] + 1, "snippet": best[2][:500], "score": matched,
                    "_item": True, "_path": len(set(_words(path.stem)) & set(terms)),
                }
                if entry["label"]:
                    hit["entry"] = entry["label"]
                context = _entry_text(lines, entry, entries, terms, matched_lines)
                if context and context != best[2]:
                    hit["context"] = context
                result.append(hit)
            result.extend(hit for hit in file_hits if int(hit["line"]) not in claimed)
        return result

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

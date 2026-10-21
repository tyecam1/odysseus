"""Read-only adapter for the canonical household repository."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import subprocess
import time
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
    "whose", "will", "with", "words", "would", "yesterday", "yet", "you", "your", "need", "needs", "needed",
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
                matched: Iterable[str] = (), hidden: Iterable[int] = ()) -> str:
    """The recorded facts of one YAML entry as one short string ('name: tomatoes; quantity: "1 carton"; moods: late night, focused').

    Nested demonstration entries are left out, a field the question asked about that holds null is reported as 'not recorded', and the
    matched facts are always kept (and listed first) even when the entry is long enough to be shortened.
    """
    asked = set(asked)
    skip: set = set(hidden)
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


# a field or assignment that names a credential/identifier is never a household fact: it is dropped from every search snippet,
# context and quoted line (the item index is allowlisted by field; the lexical fallback is not, so it filters by sensitive name)
# A sensitive word counts as a whole component of a name (wifi_password, home-pin, "Card number"), never inside another word
# (shopping is not a pin).
_SENSITIVE_WORDS = (
    r"pass(?:word|wd|phrase|code)?|pw|pwd|pin|token|secret|api[_ -]?key|credentials?|iban|sort[_ -]?code|card[_ -]?number|"
    r"cvv|cvc|otp|psk|account[_ -]?number|ssn|national[_ -]?insurance|private[_ -]?key|passport|dob|dose|dosage|medication|"
    r"prescription|nhs"
)
_SENSITIVE_ASSIGN = re.compile(
    rf"(?<![A-Za-z0-9])(?:[A-Za-z0-9]+[_ -])*(?:{_SENSITIVE_WORDS})(?:[_ -][A-Za-z0-9]+)*[\"']?\s*[:=]", re.I)

# The field-safety gate for files under the privacy allowlist (_INDEXED_PATH). Every lexical hit, snippet, context and quoted
# line is built only from lines that survive it: a YAML/JSON line is kept when each field it names is in _SAFE_FIELDS (a bare
# key that only groups entries - "items:" over "- name:" blocks - is transparent), and a line that belongs to an unsafe field
# (a nested mapping, a list, a block scalar) goes with it. Allowlist, not blocklist: an unknown field is never shown.
_LINE_KEYS = re.compile(r"(?:^|[{,]\s*|-\s+)[\"']?([\w-]+)[\"']?\s*:(?=\s|$)")
_BARE_KEY = re.compile(r"^(?:-\s+)?[\"']?[\w-]+[\"']?\s*:\s*$")
_ENTRY_LINE = re.compile(r"^-\s+[\"']?[\w-]+[\"']?\s*:")


def _unsafe_lines(lines: List[str]) -> set:
    """Indexes of the lines of a YAML/JSON file that hold, or sit under, a field that is not in _SAFE_FIELDS."""
    unsafe: set = set()
    stack: List[tuple] = []  # (column, safe) of the keys that enclose the current line
    for number, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        body = re.sub(r"\s+#.*$", "", stripped).rstrip(",")
        column = len(raw) - len(raw.lstrip())
        dash = re.match(r"-\s+", body)
        key_column = column + (dash.end() if dash else 0)
        keys = _LINE_KEYS.findall(body)
        if not keys:
            while stack and (stack[-1][0] > column if dash else stack[-1][0] >= column):
                stack.pop()
            if not all(safe for _, safe in stack):
                unsafe.add(number)
            continue
        while stack and stack[-1][0] >= key_column:
            stack.pop()
        listed = all(key.lower().replace("-", "_") in _SAFE_FIELDS for key in keys)
        grouping = False
        if not listed and _BARE_KEY.match(body):
            following = next((lines[i].strip() for i in range(number + 1, len(lines))
                              if lines[i].strip() and not lines[i].strip().startswith("#")), "")
            grouping = bool(_ENTRY_LINE.match(following))
        enclosed = all(safe for _, safe in stack)
        if not (listed or grouping) or not enclosed:
            unsafe.add(number)
        if len(keys) == 1:
            stack.append((key_column, listed or grouping))
    return unsafe


_MASKED_SUFFIXES = {".yaml", ".yml", ".json"}


def _hidden_lines(rel: str, lines: List[str]) -> set:
    """Lines of a file under the privacy allowlist that may not be shown (see _unsafe_lines); none for other files."""
    if Path(rel).suffix.lower() in _MASKED_SUFFIXES and _INDEXED_PATH.search(rel):
        return _unsafe_lines(lines)
    return set()




def _fact_text(line: str, structured: bool, table_header: bool, allow_sensitive: bool = False) -> str:
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
    if not allow_sensitive and _SENSITIVE_ASSIGN.search(text):
        return ""
    if any(label.strip("`*_ ").lower() == target.rsplit("/", 1)[-1].lower() for label, target in _LINK.findall(text)):
        return ""  # navigation pointer: the link text is the file name
    if _NOT_BUILT_NOTE.search(text):
        return ""
    todos = len(_TODO.findall(text))
    if todos and (todos > 1 or len(re.sub(r"\bTODO\b|_TODO_|[-*\[\]|:=_`]", " ", text).split()) <= 6):
        return ""  # an unfilled placeholder, not a recorded fact
    return text


# --- item resolution: an evidence retriever over every household record ------------------------------------------------------
# A question about one item ("Do we have any X left?", "Have we still got X in?", "How many tins of X?", "When does X go off?",
# "Do we need to buy X?") is resolved against an index of EVERY parsed household record (stock, equipment, plants, records, the
# shopping list ...), never by counting shared words. The question's scaffolding is removed by pattern from both ends; what is
# left is the item mention.
#
# The resolver decides only two things on its own: an exact record (name or own alias) is answered from that record, and an
# explicitly scoped question ("... in stock", "... on the shopping list") whose scope files all parsed cleanly may say "I can't
# find X" when no record is even related. Everything else - partial, related, unparsed or unscoped misses - is EVIDENCE: the
# candidate records are handed to the model as quoted data with an instruction to say "I couldn't confirm", never "no".

FOUND, NOT_PRESENT, AMBIGUOUS, UNRESOLVED = "found", "not_present", "ambiguous", "unresolved"
STOCK, SHOPPING = "stock", "shopping"
_INVENTORY_FILE = re.compile(r"stock|inventory|pantry|larder|freezer|fridge|cupboard|spice|herb", re.IGNORECASE)
# The kind of record a file holds, from its name; otherwise its household directory (records, plants, cleaning, food ...).
_FILE_KINDS = (
    (re.compile(r"shopping|grocer", re.IGNORECASE), "shopping"),
    (re.compile(r"equipment|appliance|utensil|tools?\b", re.IGNORECASE), "equipment"),
    (re.compile(r"preference|likes|diet", re.IGNORECASE), "preference"),
    (_INVENTORY_FILE, "stock"),
    (re.compile(r"recipe", re.IGNORECASE), "recipe"),
    (re.compile(r"clean|chore|rota|task", re.IGNORECASE), "cleaning"),
)
# Household areas that never answer "do we have X" (personal profile, money, pending proposals).
# PRIVACY BY ALLOWLIST: only these household paths are ever indexed for item questions (food, kitchen, cleaning, and shopping or
# grocery lists). Profile, finance, health, notes, secrets, records, plants ... are excluded by default, whatever their name.
_INDEXED_PATH = re.compile(
    r"^household/(?:food|kitchen|cleaning)/[^/]+(?:/[^/]+)*$"  # these directories only
    r"|^household/(?:shopping|grocery)[-_]list\.(?:md|txt|ya?ml)$",  # and exactly a top-level shopping list file
    re.IGNORECASE,
)
# Fields of a record that may be shown or given to the model; anything else (password, token, account, phone, dose ...) is never
# printed, whatever file it is in.
_SAFE_FIELDS = frozenset({
    "name", "item", "product", "ingredient", "aliases", "alias", "also_known_as", "aka", "category", "quantity", "qty", "amount",
    "count", "unit", "units", "location", "expiry", "best_before", "use_by", "sell_by", "status", "notes", "capabilities",
    "area", "cadence", "brand", "size",
})
_SIGNATURE_BYTE_BUDGET = 8 * 1024 * 1024  # content digested per lookup for the cache key; beyond it the stat fields alone decide
_CANDIDATE_CAP = 50  # candidate records kept on a resolution (the true count is kept beside them)
_MAX_INDEX_FILE_BYTES = 512 * 1024  # a bigger allowlisted file is not read (reported unreadable)
_MAX_YAML_ALIASES = 50  # more YAML alias references than this: rejected (alias bombs)
_MAX_YAML_DEPTH = 24
_MAX_YAML_NODES = 50000
_INDEX_TIME_BUDGET = 5.0  # seconds; files not reached in time are reported unreadable
_UNREADABLE_SHOWN = 10  # unreadable files named in a reply or in the evidence
_ID_KEYS = ("name", "item", "product", "ingredient")
_INDEX_CACHE: Dict[str, tuple] = {}  # root -> (((path, mtime_ns, ctime_ns, size, content digest), ...), index)
_HIT_CANDIDATES = 5  # candidates named in a not-confirmed reply
_EVIDENCE_CANDIDATES = 8  # candidate records given to the model
_ALIAS_KEYS = ("aliases", "alias", "also_known_as", "aka")
_QUANTITY_KEYS = ("quantity", "qty", "amount", "count")
_CONTRACTIONS = (
    (r"\bwe're\b", "we are"), (r"\bwe've\b", "we have"), (r"\bi've\b", "i have"), (r"\bdon't\b", "do not"),
    (r"\bdidn't\b", "did not"), (r"\bhaven't\b", "have not"), (r"\bhasn't\b", "has not"), (r"\bisn't\b", "is not"),
    (r"\baren't\b", "are not"), (r"\bthere's\b", "there is"), (r"\bwhat's\b", "what is"), (r"\bit's\b", "it is"),
    (r"\bwhere's\b", "where is"), (r"\bhow's\b", "how is"), (r"\bthat's\b", "that is"), (r"\bshouldn't\b", "should not"),
    (r"\bwhich's\b", "which is"), (r"\bwe'd\b", "we would"), (r"\bwhen's\b", "when is"), (r"\bdoesn't\b", "does not"),
    (r"\bgonna\b", "going to"), (r"\bgotta\b", "got to"),
)
_QUALIFIERS = r"(?:not|still|currently|even|already|just|all|completely|totally|now|really|actually)\s+"
_OUT_OF = r"(?:out\s+of|low\s+on|short\s+(?:of|on)|running\s+(?:low\s+on|out\s+of)|nearly\s+out\s+of|almost\s+out\s+of)"
_ACQUIRE = r"(?:buy|get|pick\s+up|order|grab|purchase)"
# A field of a record that a question may ask for ("the quantity of X", "the X expiry").
_FIELD = (r"(?:quantity|amount|number|stock\s+level|level|count|expiry(?:\s+date)?|use[\s-]?by(?:\s+date)?"
          r"|best[\s-]before(?:\s+date)?|sell[\s-]by(?:\s+date)?)")
_UNIT = (r"(?:tins?|cans?|packs?|packets?|bottles?|jars?|bags?|boxes?|cartons?|tubs?|pots?|tubes?|sachets?|blocks?|bunch(?:es)?"
         r"|heads?|bulbs?|cloves?|slices?|pieces?|portions?|kg|kilos?|grams?|g|litres?|liters?|ml|pints?|dozen|punnets?|rolls?)")
# Where an item is kept: "in the fridge", "in the food cupboard", "on the top shelf", "in the kitchen cupboard".
_PLACE_NOUN = (r"(?:fridge|freezer|cupboards?|pantry|larder|kitchen|shelf|shelves|stock|inventory|house|flat|home|drawers?"
               r"|cabinets?|storage|store|cellar|fruit\s+bowl|bread\s+bin|spice\s+rack)")
_NUMBER_WORDS = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve|a\s+few|everyone|us|both\s+of\s+us|people|guests)"
# (pattern, kind it marks: STOCK, SHOPPING or None, and whether it names an explicit scope). Prefixes are anchored at the start of
# what is left and tried in order (shopping, field and unit patterns before the generic ones that would consume part of them).
_SCAFFOLD_PREFIXES = tuple((re.compile(rf"^(?:{pattern})(?:\s+|$)"), kind, scoped) for pattern, kind, scoped in (
    (rf"(?:do|did|does)\s+(?:not\s+)?(?:we|i|you)\s+(?:{_QUALIFIERS})*need(?:\s+to\s+{_ACQUIRE})?", SHOPPING, True),
    (rf"(?:should|shall|must|can|do)\s+(?:not\s+)?(?:we|i)\s+(?:{_QUALIFIERS})*{_ACQUIRE}", SHOPPING, True),
    (rf"(?:we|i)\s+(?:{_QUALIFIERS})*need(?:\s+to\s+{_ACQUIRE})?", SHOPPING, True),
    (rf"need(?:\s+to\s+{_ACQUIRE})?", SHOPPING, True),
    (rf"(?:are|am)\s+(?:we|i)\s+(?:{_QUALIFIERS})*(?:buying|getting|ordering)", SHOPPING, True),
    (rf"(?:do|did|does)\s+(?:not\s+)?(?:we|i|you|they)\s+(?:{_QUALIFIERS})*(?:have|has|got|own|keep|stock)", STOCK, False),
    (rf"(?:we|i)\s+(?:do|did)\s+(?:not\s+)?(?:{_QUALIFIERS})*(?:have|got|own)", STOCK, False),
    (rf"(?:have|has|did)\s+(?:not\s+)?(?:we|i|you)\s+(?:{_QUALIFIERS})*(?:run|ran|gone|went)\s+out\s+of", STOCK, False),
    (rf"(?:have|has)\s+(?:not\s+)?(?:we|i|you)\s+(?:{_QUALIFIERS})*got", STOCK, False),
    (rf"(?:have|has)\s+(?:not\s+)?(?:we|i|you)(?:\s+(?:still|currently|even))?(?=\s+(?:any|some|enough|a|an|the)\b)", STOCK, False),
    (rf"(?:are|were)\s+(?:not\s+)?(?:we|you)\s+(?:{_QUALIFIERS})*{_OUT_OF}", STOCK, False),
    (rf"we\s+are\s+(?:{_QUALIFIERS})*{_OUT_OF}", STOCK, False),
    (rf"(?:we|i)\s+(?:have|had)\s+(?:not\s+)?(?:{_QUALIFIERS})*(?:run|ran)\s+out\s+of", STOCK, False),
    (rf"(?:have|has)\s+(?:not\s+)?(?:we|you|i)\s+(?:{_QUALIFIERS})*(?:used\s+up|used|finished|eaten|drunk)(?:\s+all)?", STOCK, False),
    (rf"we\s+(?:{_QUALIFIERS})*(?:have|got)", STOCK, False),
    (rf"(?:is|are)\s+there(?:\s+{_QUALIFIERS[:-3]})*", STOCK, False),
    (rf"there\s+(?:is|are|was|were)(?:\s+{_QUALIFIERS[:-3]})*", STOCK, False),
    (r"how\s+(?:much|many)", STOCK, False),
    (r"(?:what\s+is\s+|what\s+have\s+we\s+got\s+)?left\s+of", STOCK, False),
    (rf"(?:are\s+we\s+)?(?:{_QUALIFIERS})*{_OUT_OF}", STOCK, False),
    (r"(?:ya|you|u)\s+got", STOCK, False),
    (rf"(?:what|which|how|when)\s+(?:is|are|was|were)\s+(?:the\s+|our\s+)?(?:current\s+)?{_FIELD}\s+(?:of|for|on)", STOCK, False),
    (rf"(?:what|which)\s+{_FIELD}\s+of", STOCK, False),
    (rf"(?:the\s+|our\s+)?(?:current\s+)?{_FIELD}\s+(?:of|for|on)", STOCK, False),
    (r"(?:anything|something)\s+(?:with|containing|that\s+has|made\s+with)", STOCK, False),
    (r"(?:got|any)", STOCK, False),
    (rf"{_UNIT}\s+of", None, False),
    (r"(?:(?:can|could|would)\s+you\s+(?:please\s+)?)?(?:check|tell\s+me|see|look|find\s+out)(?:\s+(?:if|whether))?", None, False),
    (r"when\s+(?:does|do|did|will|is|are|was|were|should)", None, False),
    (r"(?:what|which)(?:\s+(?:kinds?|types?|sorts?|brands?)\s+of)?(?:\s+(?:is|are|was|were))?", None, False),
    (r"(?:please|hey|hi|ok|okay|so|um|uh|and|but|also|if|whether|is|are|has|have|does|do|did)", None, False),
    (r"(?:still|even|currently|some|more|enough|a|an|the|of|our|my)", None, False),
))
_SCAFFOLD_SUFFIXES = tuple((re.compile(rf"(?:^|\s+)(?:{pattern})$"), kind, scoped) for pattern, kind, scoped in (
    (r"on\s+(?:the\s+|our\s+|my\s+)?(?:shopping\s+|grocery\s+)?list", SHOPPING, True),
    (r"(?:for|from)\s+(?:the\s+)?(?:shopping|shop|groceries|supermarket)", SHOPPING, True),
    (rf"(?:do|did|does)\s+(?:we|i)\s+(?:still\s+)?need(?:\s+to\s+{_ACQUIRE})?", SHOPPING, True),
    (r"needs?\s+(?:buying|getting|to\s+be\s+bought)", SHOPPING, True),
    (r"in\s+stock", STOCK, True),
    (rf"(?:in|at|on|inside|from)\s+(?:the\s+|our\s+|my\s+)?(?:[a-z']+\s+){{0,2}}?{_PLACE_NOUN}", STOCK, True),
    (r"at\s+home", STOCK, True),
    (r"(?:left|remaining)(?:\s+over)?", STOCK, False),
    (r"going(?:\s+spare)?|spare|available|about|around|lying\s+around|kicking\s+about|knocking\s+about", STOCK, False),
    (r"or\s+(?:should|shall|do|must|will|can)\s+(?:i|we)\b.*", None, False),
    (r"(?:running|getting|going|almost|nearly|very)\s+(?:low|out|empty|gone|finished)|low|all\s+gone|used\s+up|run\s+out|finished",
     STOCK, False),
    (r"(?:expire|expires|expiring|expired|go\s+off|goes\s+off|going\s+off|gone\s+off|need\s+using(?:\s+up)?"
     r"|need\s+to\s+be\s+used(?:\s+up)?)", STOCK, False),
    (r"(?:do|did)\s+(?:we|i|you)\s+(?:still\s+)?(?:have|got)", STOCK, False),
    (r"have\s+(?:we|i|you)\s+(?:still\s+)?got", STOCK, False),
    (r"(?:we|i)\s+(?:still\s+)?(?:have|got)", STOCK, False),
    (r"(?:is|are)\s+there", STOCK, False),
    (_FIELD, STOCK, False),
    (r"in", STOCK, False),  # "have we still got X in?"
    (r"in\s+(?:it|them)", None, False),
    (rf"for\s+{_NUMBER_WORDS}(?:\s+\w+){{0,2}}", None, False),  # "enough X for 4 people"
    (r"(?:for|to)\s+(?:make|making|cook|cooking|bake|baking|use|using|eat|dinner|lunch|breakfast|tea|supper|tonight|tomorrow"
     r"|the\s+\w+|a\s+\w+)(?:\s+\w+){0,3}", None, False),
    (r"(?:still|anymore|any\s+more|at\s+the\s+moment|right\s+now|now|please|at\s+all|or\s+not|yet|then|currently|today|is|are)",
     None, False),
    # tag questions: "we're out of X, right?", "we have X, don't we?"
    (r"(?:right|correct|yeah|yes|no|or\s+what|(?:is|are|do|does|have|has)(?:\s+not)?\s+(?:it|we|they|there)|(?:isn't|aren't|don't|"
     r"doesn't|haven't|hasn't)\s+(?:it|we|they|there))", None, False),
))
_EXPIRY_WORDS = re.compile(r"expir|go(?:es|ing|ne)?\s+off|best|use[\s-]?by|sell|need")
# A mention made only of these names no item ("anything", "food"): it is a listing or an open question, not an item.
_LISTING_NOUNS = frozenset({
    "anything", "something", "everything", "nothing", "stuff", "item", "thing", "food", "ingredient", "grocery", "one", "what",
})
# A mention containing one of these is not a parsed item name ("eggs and bread or something"): never a confident answer.
_NON_ITEM_WORDS = frozenset({
    "for", "to", "with", "without", "before", "after", "about", "what", "when", "which", "who", "how", "why", "if", "we", "i",
    "you", "it", "that", "this", "them", "those", "these", "anything", "something", "everything", "nothing", "stuff", "thing",
    "things", "food", "ingredient", "ingredients", "enough", "is", "are", "do", "does", "have", "has", "make", "cook", "can",
    "should", "could", "would", "or", "but", "not", "in", "on", "at", "from", "by", "like", "than",
})
_LINK_WORDS = frozenset({"and", "of", "the", "a", "an", "with", "in", "on"})
_PHRASE_TOKEN = re.compile(r"[^\W_]+(?:'[^\W_]+)?")
# Words that may surround an item named with no item phrasing at all ("can i cook spaghetti tonight", "ya got any stock cubes").
_BARE_FILLER = frozenset(_norm(word) for word in (
    "ya", "u", "got", "running", "low", "left", "whats", "what's", "cook", "cooking", "make", "making", "use", "using", "eat",
    "tonight", "tomorrow", "today", "dinner", "lunch", "breakfast", "tea", "some", "any", "there", "the", "a", "an", "of", "for",
    "with", "i", "we", "can", "could", "should", "out", "is", "are", "do", "does", "have", "has", "please", "list",
)) | frozenset(_STOP_TERMS) | frozenset(_norm(word) for domain in ("food", "shopping") for word in DOMAIN_TERMS[domain])
_UNPARSED_LENGTH = 5  # a mention of more words than this is not taken as one item name


def _phrase_tokens(text: str) -> List[str]:
    return _PHRASE_TOKEN.findall((text or "").lower().replace("’", "'").replace("&", " and ").replace("_", " "))


def phrase_key(text: str) -> tuple:
    """Normalised word sequence of an item name or mention: 'Coconut Milk' -> ('coconut', 'milk'), 'cookies' -> ('cooky',)."""
    return tuple(_singular(token) for token in _phrase_tokens(text))


def item_question(question: str) -> Optional[Dict[str, object]]:
    """Parse a question about one item: what it names, whether it asks about stock or the shopping list, and whether it names
    an explicit scope ("in stock", "in the fridge", "on the shopping list", "do we need to buy").

    Returns None when the text has no stock or shopping phrasing at all ("What should I cook tonight?", "What is gochujang?"),
    otherwise {"mention", "kind": "stock"|"shopping", "wh", "field", "scoped"}. The mention is "" when no item is named.
    """
    text = (question or "").lower().replace("’", "'")
    for pattern, replacement in _CONTRACTIONS:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"[?!.,;:\"]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    wh = bool(re.match(r"^(?:what|which)\b", text))
    kinds: set = set()
    field = None
    scoped = False
    changed = True
    while changed and text:
        changed = False
        for pattern, kind, scope in _SCAFFOLD_PREFIXES:
            match = pattern.match(text)
            if match and match.end():
                found_field = re.search(_FIELD, match.group(0))
                field = field or (found_field.group(0) if found_field and kind else None)
                text = text[match.end():].strip()
                if kind:
                    kinds.add(kind)
                scoped = scoped or scope
                changed = True
                break
        for pattern, kind, scope in _SCAFFOLD_SUFFIXES:
            match = pattern.search(text)
            if match:
                stripped = match.group(0).strip()
                if kind and (re.fullmatch(_FIELD, stripped) or _EXPIRY_WORDS.match(stripped)):
                    field = field or ("expiry" if _EXPIRY_WORDS.match(stripped) and not re.fullmatch(_FIELD, stripped) else stripped)
                text = text[:match.start()].strip()
                if kind:
                    kinds.add(kind)
                scoped = scoped or scope
                changed = True
                break
    if not kinds:
        return None
    if text and all(_singular(token) in _LISTING_NOUNS for token in _phrase_tokens(text)):
        text = ""
    kind = SHOPPING if SHOPPING in kinds else STOCK
    return {"mention": text, "kind": kind, "wh": wh, "field": field, "scoped": scoped}


# Phrasing that asks about household stock even when the item part does not parse ("yo do we have saffron", "saffron - got any",
# "did we buy eggs last week", "is the lettuce in the fridge still ok"): such a question always carries the stock guard.
INVENTORY_INTENT = re.compile(
    r"\b(?:do|did|does)\s+(?:not\s+)?we\s+(?:still\s+|last\s+)?(?:have|buy|get|need)\b|\bhave\s+we\s+(?:still\s+)?(?:got|any|run\s+out)\b"
    r"|\bgo(?:es|ne|ing)?\s+off\b|\bin\s+date\b|\bexpir|\buse(?:d)?\s+by\b|\bbest\s+before\b|^\s*got\b"
    r"|\bgot\s+any\b|\bhow\s+(?:many|much)\b|\b(?:is|are)\s+there\b|\bout\s+of\b|\brunning\s+(?:low|out)\b|\bin\s+stock\b"
    r"|\bin\s+the\s+(?:fridge|freezer|cupboard|pantry|larder)\b|\bany\s+\w+(?:\s+\w+)?\s+left\b|\bon\s+the\s+shopping\s+list\b",
    re.IGNORECASE,
)
# Abstract or non-household nouns: "do we have time", "are we low on money", "any plans tonight" are not stock questions.
_NON_PHYSICAL = frozenset({
    "time", "money", "cash", "idea", "plan", "problem", "chance", "minute", "moment", "energy", "room", "space", "news", "word",
    "update", "issue", "question", "choice", "option", "luck", "fun", "break", "holiday", "meeting", "appointment", "guest",
    "people", "visitor", "wifi", "internet", "signal", "weather", "rain", "film", "show", "match", "game", "booking",
    "reservation", "bill", "rent", "job", "work", "homework", "class", "lesson", "school", "sleep", "rest", "plan", "date",
    "day", "week", "weekend", "hour", "mile", "calorie", "lift", "chat", "talk", "petrol", "fuel", "budget", "saving",
})


# Words that qualify an abstract noun without making it a thing ("any time", "free time", "enough money", "a good idea").
_ABSTRACT_MODIFIERS = frozenset({
    "a", "an", "the", "any", "some", "enough", "much", "more", "most", "less", "another", "other", "same", "our", "my", "your",
    "free", "spare", "good", "bad", "great", "nice", "real", "whole", "extra", "little", "few", "lot", "lots", "big", "long",
    "short", "quick", "next", "last", "new", "old", "today", "tonight", "tomorrow", "this", "that", "these", "those",
})


def names_non_physical(mention: str) -> bool:
    """Whether a parsed mention is ENTIRELY abstract ("time", "any free time", "money", "plans") rather than a household item.

    Every meaningful word must be an abstract noun: one abstract word inside a physical item ("energy drinks", "room spray",
    "space heater", "fuel tank cap") does not make the item abstract, so it keeps the stock guard.
    """
    tokens = [token for token in _phrase_tokens(mention) if token not in _ABSTRACT_MODIFIERS]
    return bool(tokens) and all(token in _NON_PHYSICAL or _singular(token) in _NON_PHYSICAL for token in tokens)


def stock_item_mention(question: str) -> Optional[Dict[str, object]]:
    """The item a stock or shopping question asks about ({"mention": "olive oil"}), or None when it is not one."""
    parsed = item_question(question)
    return None if parsed is None else {"mention": parsed["mention"]}


# --- vocabulary: general words, kinds and synonyms (config/misumi_item_vocabulary.yaml) ----------------------------------------
_VOCABULARY_FILE = Path(__file__).resolve().parent.parent / "config" / "misumi_item_vocabulary.yaml"
_VOCABULARY_CACHE: Dict[str, Dict[tuple, set]] = {}


def load_item_vocabulary(path: Optional[Path | str] = None) -> Dict[tuple, set]:
    """{phrase key: related phrase keys} from the vocabulary file: a general word relates to its kinds and each kind to its
    general word (one level, both directions); synonyms relate to each other. Missing or unreadable file: no relations."""
    source = Path(path) if path else _VOCABULARY_FILE
    cache_key = str(source)
    if cache_key in _VOCABULARY_CACHE:
        return _VOCABULARY_CACHE[cache_key]
    related: Dict[tuple, set] = {}

    def link(a: tuple, b: tuple) -> None:
        if a and b and a != b:
            related.setdefault(a, set()).add(b)
            related.setdefault(b, set()).add(a)

    try:
        import yaml  # PyYAML is a core requirement; without it the vocabulary is simply empty

        data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    for general, kinds in (data.get("kinds") or {}).items():
        for kind in kinds or []:
            link(phrase_key(str(general)), phrase_key(str(kind)))
    for group in data.get("synonyms") or []:
        keys = [phrase_key(str(name)) for name in group or []]
        for a in keys:
            for b in keys:
                link(a, b)
    _VOCABULARY_CACHE[cache_key] = related
    return related


def _vocabulary_related(key: tuple, vocabulary: Dict[tuple, set]) -> set:
    """Phrase keys the vocabulary relates to the mention or to a tail of it that keeps its head word ('grated parmesan' ->
    parmesan -> parmigiano, cheese ...). A run without the head is a modifier ('stock photos' is not 'stock')."""
    found: set = set()
    for start in range(len(key)):
        found |= vocabulary.get(key[start:], set())
    return found


def _head(key: tuple) -> str:
    return key[-1] if key else ""


def _contains(outer: tuple, inner: tuple) -> bool:
    """`inner` occurs in `outer` as a whole run of words (token boundaries, same order)."""
    size = len(inner)
    return 0 < size <= len(outer) and any(outer[i:i + size] == inner for i in range(len(outer) - size + 1))


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance (insert, delete, substitute)."""
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def _misspelt(a: str, b: str) -> bool:
    """One word is a bounded misspelling of the other: at most 1 edit for words under 8 letters, 2 for longer; never for words
    of 4 letters or fewer on both sides (too many short real words are one edit apart: time/lime, lamb/lime), while 'brea'
    for 'bread' still counts; and only with the same first letter ('money' is not a misspelling of 'honey')."""
    if a == b or max(len(a), len(b)) < 5 or min(len(a), len(b)) < 4 or a[0] != b[0]:
        return False
    return _edit_distance(a, b) <= (1 if max(len(a), len(b)) < 8 else 2)


def _near_miss(mention: tuple, key: tuple) -> int:
    """How strongly a record that is NOT an exact match still overlaps the mention (0 = unrelated).

    3: one phrase lies whole inside the other ("olive oil" / "olives", "soy sauce" / "dark soy sauce", "coconut milk" / "milk");
    2: they share a head noun ("chilli sauce" / "hot sauces"); 1: a bounded misspelling of the whole phrase or of a head word
    ("brocoli" / "tenderstem broccoli"), or one head word is a whole prefix or suffix of a recorded word ("pepper" /
    "peppercorns"). A shared modifier alone ("red peppers" / "red onions") is not a near miss.
    """
    if _contains(mention, key) or _contains(key, mention):
        return 3
    shared = (set(mention) & set(key)) - _LINK_WORDS
    if shared and (_head(mention) in shared or _head(key) in shared):
        return 2
    if _misspelt(" ".join(mention), " ".join(key)):
        return 1
    for word in mention:
        for recorded in key:
            if word not in _LINK_WORDS and _misspelt(word, recorded) and (word == _head(mention) or recorded == _head(key)):
                return 1
    head = _head(mention)
    if len(head) >= 4 and any(recorded != head and (recorded.startswith(head) or recorded.endswith(head)) for recorded in key):
        return 1
    return 0


def _relation(mention: tuple, record: Dict[str, object], vocabulary: Dict[tuple, set]) -> int:
    """How strongly a record relates to a mention it does not match exactly (0 = unrelated; higher = more likely meant):
    its name or aliases (see _near_miss); its category ("wine" for a pinot filed under wine); the vocabulary ("cheese" -> brie,
    "pasta" -> spaghetti, "sriracha" -> hot sauces, "parmesan" -> Parmigiano Reggiano)."""
    strength = max((_near_miss(mention, key) for key in record["keys"]), default=0)
    category = record.get("category_key") or ()
    if category and (_contains(category, mention) or _head(category) == _head(mention)):
        strength = max(strength, 2)
    for other in _vocabulary_related(mention, vocabulary):
        for key in record["keys"]:
            if other == key or _contains(key, other) or _contains(other, key):
                strength = max(strength, 2)
            elif _head(other) == _head(key):
                strength = max(strength, 1)
        if category and (_contains(category, other) or _head(category) == _head(other)):
            strength = max(strength, 1)
    return strength


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


_EMPTY_VALUES = frozenset({"", "null", "~", "[]", "{}"})


def _scalar(value: object) -> str:
    """A YAML scalar as its text: a double-quoted value has its escapes decoded ('\\"' -> '"'), a single-quoted one its ''."""
    text = str(value if value is not None else "").strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        try:
            return str(json.loads(text)).strip()
        except ValueError:
            return text[1:-1].strip()
    if len(text) >= 2 and text[0] == text[-1] == "'":
        return text[1:-1].replace("''", "'").strip()
    return text


_NUMBER_QUANTITY = re.compile(r"^(\d+(?:\.\d+)?)(?:\s*[a-z]+\.?)?(?:\s|$|[-;,(:])", re.IGNORECASE)
_ZERO_WORDS = re.compile(
    r"^(?:none(?:\s+left)?|no(?:ne)?\s+(?:left|remaining)|no|nil|nothing(?:\s+left)?|zero|(?:all\s+)?out(?:\s+of\s+stock)?|empty"
    r"|(?:all\s+)?gone|(?:all\s+)?used\s+up|all\s+used|finished|(?:run|ran)\s+out|depleted|sold\s+out)$",
    re.IGNORECASE,
)


_UNKNOWN_QUANTITY = frozenset({"", "null", "~", "[]", "{}", "?", "??", "n/a", "na", "tbc", "tbd", "unknown", "unsure", "-", "--",
                               "not sure", "dunno", "check"})
_AMOUNT_WORDS = re.compile(
    r"^(?:half|some|plenty|lots|loads|several|enough|full|nearly\s+full|most|a\s+(?:few|bit|little|lot|couple|handful|bag|tin|jar"
    r"|pack|packet|box|bottle|block|tub|can|carton|loaf|bunch|head)|one|two|three|four|five|six|a\s+\w+\s+of)\b",
    re.IGNORECASE,
)


def quantity_state(value: object) -> Optional[str]:
    """What a recorded quantity says: "out" (none left), "in" (some left) or None (not recorded, or unclear).

    Out only when the WHOLE value says none is left ("none", "nil", "ran out", "out of stock") or is zero with at most a unit
    ("0", "0g", "0 tins left"). In when a positive number (with or without a unit) or an amount phrase ("half a bag") is
    recorded with no word that contradicts it. Everything else is unclear: "?", "n/a", "TBC", mixed prose such as
    "out - spare jar in the garage", "used", "3 empty jars", "0 left, bought 3 today".
    """
    text = re.sub(r"\s+", " ", _scalar(value).strip().lower()).strip(" .!")
    if text in _UNKNOWN_QUANTITY:
        return None
    if _ZERO_WORDS.match(text):
        return "out"  # the whole value says none is left ("none", "ran out", "out of stock")
    number = _NUMBER_QUANTITY.match(text)
    if number:
        rest = text[number.end():].strip()
        if float(number.group(1)) == 0:
            return "out" if re.fullmatch(r"(?:left|remaining|in\s+stock)?", rest) else None  # "0", "0g", "0 tins left"
        return None if re.search(r"\b(?:empty|finished|gone|used|none|out)\b", text) else "in"  # "3 empty jars" is unclear
    return "in" if _AMOUNT_WORDS.match(text) and not re.search(r"\b(?:empty|finished|gone|used|none|out)\b", text) else None


def _matching_lines(unparsed: Dict[str, List[str]], key: tuple, limit: int = 5) -> List[tuple]:
    """Lines of files in an unrecognised layout that mention the item's head word: (file, line, text), for the model."""
    head = _head(key)
    if not head or len(head) < 3:
        return []
    found = []
    for rel in sorted(unparsed):
        for number, line in enumerate(unparsed[rel], 1):
            text = line.strip()
            if text and head in phrase_key(text):
                found.append((rel, number, "" if _SENSITIVE_ASSIGN.search(text) else text[:200]))
                if len(found) >= limit:
                    return found
    return found


def _record_text(record: Dict[str, object]) -> str:
    """What a record says, for any file type: a list item's text, else its name."""
    return str(record.get("text") or record.get("name") or "")


_EVIDENCE_CHARS = 6000  # the whole evidence block given to the model


def _bounded_names(names: List[str]) -> str:
    """At most _UNREADABLE_SHOWN file names, then a count ("a.yaml, b.md … and 1490 more")."""
    shown = ", ".join(names[:_UNREADABLE_SHOWN])
    return shown + (f" … and {len(names) - _UNREADABLE_SHOWN} more" if len(names) > _UNREADABLE_SHOWN else "")


def _field_name(key: str) -> str:
    """A field name as shown: plain names as they are, anything else (spaces, newlines, punctuation) quoted and escaped."""
    return key if re.fullmatch(r"[A-Za-z0-9_-]{1,40}", key) else _quoted(key, 40)


def _quoted(value: object, limit: int = 160) -> str:
    """A recorded value as one quoted, escaped string: household text is DATA, never an instruction to follow."""
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit - 1].rstrip() + "…"
    return json.dumps(text, ensure_ascii=False)


def _record_data(record: Dict[str, object], asked: Optional[str] = None, limit: int = 400) -> str:
    """The direct fields of a record as quoted data ('name: "peas"; quantity: "3 tins"; notes: "..."'). The quantity (and the
    field the question asked for) is reported as 'not recorded' when empty; other empty fields are left out."""
    fields = record.get("_fields") or {}
    wanted = {"quantity"} | ({asked.split()[0].replace("-", "_")} if asked else set())
    parts: List[str] = []
    for key, value in fields.items():
        if key not in _SAFE_FIELDS:
            continue  # never print a field that is not known to be safe (password, account, phone, dose ...)
        if isinstance(value, list):
            values = [_scalar(item) for item in value if _scalar(item).lower() not in _EMPTY_VALUES]
            if values:
                parts.append(f"{_field_name(key)}: " + ", ".join(_quoted(item, 80) for item in values))
            continue
        raw = _scalar(value)
        if raw.lower() in _EMPTY_VALUES:
            if key in wanted or any(key.startswith(word) for word in wanted):
                parts.append(f"{_field_name(key)}: not recorded")
            continue
        parts.append(f"{_field_name(key)}: {_quoted(raw)}")
    if record.get("inherited_category") and "category" not in fields:
        parts.append(f"category: {_quoted(record['inherited_category'])}")
    joined = "; ".join(parts)
    if len(joined) > limit:
        joined = joined[:limit - 1].rstrip() + "…"
    return joined


def _file_kind(rel: str) -> str:
    stem = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    for pattern, kind in _FILE_KINDS:
        if pattern.search(stem):
            return kind
    parts = rel.split("/")
    return parts[1] if len(parts) > 2 else "household"


def _yaml_null(node) -> bool:
    return node.tag.endswith(":null") or str(node.value).strip().lower() in {"", "~", "null"}


def _yaml_records(text: str, rel: str, kind: str) -> Optional[List[Dict[str, object]]]:
    """Every record in one YAML file: any mapping (block or flow style, at any depth) with a name/item/title/plant/task. Nested
    entries inside a record are part of it, not records; a grouping mapping without a name passes its `category` down to the
    records under it. Demonstration mappings (`example: true`) and everything under them are skipped. None if the file does not
    parse."""
    import yaml

    if len(text.encode("utf-8", errors="replace")) > _MAX_INDEX_FILE_BYTES or "\x00" in text:
        return None
    try:
        aliases = sum(1 for token in yaml.scan(text) if isinstance(token, yaml.AliasToken))
        if aliases > _MAX_YAML_ALIASES:
            return None  # an alias bomb or a self-referencing alias: never expanded
        documents = list(yaml.compose_all(text))
    except Exception:
        return None
    records: List[Dict[str, object]] = []
    budget = {"nodes": 0}

    def scalar(node) -> Optional[str]:
        return None if not isinstance(node, yaml.ScalarNode) or _yaml_null(node) else str(node.value).strip()

    def walk(node, category: str, depth: int = 0) -> None:
        budget["nodes"] += 1
        if depth > _MAX_YAML_DEPTH or budget["nodes"] > _MAX_YAML_NODES:
            raise ValueError("YAML structure too deep or too large (a recursive alias ends here too)")
        if isinstance(node, yaml.SequenceNode):
            for child in node.value:
                walk(child, category, depth + 1)
            return
        if not isinstance(node, yaml.MappingNode):
            return
        pairs = [(str(key.value).lower(), key, value) for key, value in node.value if isinstance(key, yaml.ScalarNode)]
        if any(name == "example" and (scalar(value) or "").strip("\"'").lower() in {"true", "yes", "y", "1"}
               for name, _, value in pairs):
            return
        ident = next(((name, key, scalar(value)) for wanted in _ID_KEYS for name, key, value in pairs
                      if name == wanted and scalar(value)), None)
        if ident is None:
            group = next((scalar(value) for name, _, value in pairs if name == "category" and scalar(value)), category)
            for _, _, value in pairs:
                walk(value, group or "", depth + 1)
            return
        fields: Dict[str, object] = {}
        for name, _, value in pairs:
            if isinstance(value, yaml.ScalarNode):
                fields.setdefault(name, "" if _yaml_null(value) else str(value.value))
            elif isinstance(value, yaml.SequenceNode):
                items = [str(item.value) for item in value.value if isinstance(item, yaml.ScalarNode) and not _yaml_null(item)]
                fields.setdefault(name, items)
        label = ident[2]
        if ident[0] == "title" and scalar(dict((n, v) for n, _, v in pairs).get("artist")):
            label = f"{scalar(dict((n, v) for n, _, v in pairs)['artist'])} - {label}"
        aliases: List[str] = []
        for name in _ALIAS_KEYS:
            value = fields.get(name)
            if isinstance(value, list):
                aliases.extend(item.strip() for item in value if item.strip())
            elif isinstance(value, str) and value.strip():
                aliases.extend(part.strip() for part in value.strip("[]").split(",") if part.strip())
        keys: List[tuple] = []
        for name in [ident[2], label] + aliases:
            key = phrase_key(name)
            if key and key not in keys:
                keys.append(key)
        quantity = next((_scalar(fields[name]) for name in _QUANTITY_KEYS if isinstance(fields.get(name), str)), "")
        quantity = "" if quantity.lower() in _EMPTY_VALUES and quantity.lower() != "none" else quantity
        state = quantity_state(quantity) if quantity else None
        line = ident[1].start_mark.line + 1
        own_category = fields.get("category") if isinstance(fields.get("category"), str) else ""
        records.append({
            "id": f"{rel}:{line}", "name": label, "aliases": aliases,
            "keys": keys, "surface": tuple(_phrase_tokens(ident[2])), "path": rel, "line": line, "kind": kind,
            "quantity": quantity or None, "quantity_state": state, "out_of_stock": state == "out",
            "category_key": phrase_key(own_category or category), "inherited_category": category if not own_category else "",
            "_fields": fields,
        })

    for document in documents:
        if document is not None:
            walk(document, "")
    return records


def _list_records(lines: List[str], rel: str, kind: str) -> List[Dict[str, object]]:
    """The items of a Markdown list file (a shopping list): one record per real bullet, checkbox or numbered item, named by the
    text before any detail ("milk - 2 pints" -> milk). Placeholders, headings and notes are not items."""
    records: List[Dict[str, object]] = []
    for number, line in enumerate(lines, 1):
        text = _fact_text(line, False, False)
        found = re.match(r"^(?:[-*+]|\d+[.)])\s+(?:\[([ xX])\]\s+)?(.+)$", text)
        if not found:
            continue
        item = found.group(2).strip()
        name = re.split(r"\s+[-–—]\s+|\s*\(|:\s", item, maxsplit=1)[0].strip().strip("*_`")
        key = phrase_key(name)
        if key:
            records.append({
                "id": f"{rel}:{number}", "name": name, "text": item, "aliases": [], "keys": [key],
                "surface": tuple(_phrase_tokens(name)), "path": rel, "line": number, "kind": kind, "quantity": None,
                "quantity_state": None, "out_of_stock": False, "category_key": (), "inherited_category": "",
                "ticked": (found.group(1) or " ").lower() == "x", "_fields": {},
            })
    return records


def _mark_alias_ownership(records: List[Dict[str, object]]) -> None:
    """An alias is OWNED by a record only when no other record uses the same words (as a name or an alias, in any order or
    number). Only an owned alias may answer for its record; a shared one (`alias_collisions`) only makes candidates."""
    users: Dict[tuple, set] = {}
    for number, record in enumerate(records):
        for key in record["keys"]:
            users.setdefault(tuple(sorted(key)), set()).add(number)
    for number, record in enumerate(records):
        record["owned_aliases"] = [tuple(_phrase_tokens(alias)) for alias in record["aliases"]
                                   if users.get(tuple(sorted(phrase_key(alias))), set()) == {number}]
        record["alias_collisions"] = [key for key in record["keys"][1:] if len(users[tuple(sorted(key))]) > 1]


def _exact_records(surface: tuple, key: tuple, records: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """The records a mention names EXACTLY, or [] - the only matches that may be answered without the model:
    1. the name spelled as asked (case and spacing aside) - every such record, in every file;
    2. an alias spelled as asked that its record owns;
    3. the other grammatical number of a name, words in the same order ("tomato" for "tomatoes"), only when no other record
       shares that head noun ("peppers" is not exact for "pepper" while "red peppers" is also recorded).
    Word-order variants ("milk chocolate" / "chocolate milk") are never exact."""
    spelled = [record for record in records if record["surface"] == surface]
    if spelled:
        return spelled
    owned = [record for record in records if surface in record["owned_aliases"]]
    if owned:
        return owned
    folded = [record for record in records if record["keys"][0] == key]
    if not folded:  # the other number of an owned alias ("eggplants" for an aubergine aliased eggplant)
        folded = [record for record in records if key in {phrase_key(" ".join(alias)) for alias in record["owned_aliases"]}]
    if folded and not any(record not in folded and _head(record["keys"][0]) == _head(key) for record in records):
        return folded
    return []


def _resolve(parsed: Dict[str, object], records: List[Dict[str, object]], vocabulary: Dict[tuple, set]) -> Dict[str, object]:
    """Resolution of one parsed mention against index records (see HouseholdReadOnlyAdapter.resolve_question).

    found: the records the mention names exactly (_exact_records). Anything else is evidence, never an answer: ambiguous (related
    records exist - the candidates), not_present (nothing related was found; never said to the user as "no"), unresolved (no
    item named, no records, or a mention that is not a clean item name).
    """
    mention = str(parsed["mention"])
    key = phrase_key(mention)
    surface = tuple(_phrase_tokens(mention))
    result: Dict[str, object] = {
        "mention": mention, "key": key, "kind": parsed["kind"], "field": parsed.get("field"),
        "checked": len(records), "records": [], "candidates": [], "candidates_total": 0, "strength": 0,
    }
    if not records:
        result.update(outcome=UNRESOLVED, reason="no recorded items")
        return result
    if not key:
        result.update(outcome=UNRESOLVED, reason="the question does not name an item")
        return result
    exact = _exact_records(surface, key, records)
    if exact:
        result.update(outcome=FOUND, records=exact, strength=3)
        return result
    unparsed = len(key) > _UNPARSED_LENGTH or bool(set(_phrase_tokens(mention)) & _NON_ITEM_WORDS)
    # In a mention that is not a clean item name ("calories in an avocado") only strong relations are candidates.
    probe = tuple(_singular(t) for t in _phrase_tokens(mention) if t not in _NON_ITEM_WORDS) if unparsed else key
    scored = []
    for position, record in enumerate(records):
        strength = _relation(probe, record, vocabulary) if probe else 0
        if not unparsed:  # a misspelling is judged on the spelling as asked ("olies" folds to "oly" but is one edit from "olives")
            strength = max(strength, min(1, _near_miss(surface, record["surface"])))
        if strength and not (unparsed and strength < 2):
            scored.append((-strength, position, record))
    scored.sort(key=lambda row: (row[0], row[1]))
    result["candidates"] = [row[2] for row in scored[:_CANDIDATE_CAP]]
    result["candidates_total"] = len(scored)
    result["strength"] = -scored[0][0] if scored else 0
    if unparsed:
        result.update(outcome=UNRESOLVED, reason="the question does not clearly name one item")
    elif scored:
        result.update(outcome=AMBIGUOUS)
    else:
        result.update(outcome=NOT_PRESENT)
    return result


def _record_domain(record: Dict[str, object]) -> str:
    """The household domain a record answers for: the shopping list, a household directory (records, plants ...) or food."""
    if record["kind"] == SHOPPING:
        return "shopping"
    parts = str(record["path"]).split("/")
    directory = parts[1] if len(parts) > 2 else ""
    return directory if directory in DOMAIN_PATHS and directory not in ("food", "recipes") else "food"


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

        In the food and shopping domains a question about one item (or a bare item name) is answered from a record only by
        entity resolution (`resolve_question`) when that is deterministic (an exact record, or an explicitly scoped absence).
        The word-overlap lookup that remains never reads files that hold item records line by line (a named data file is listed
        record by record instead) and needs EVERY content word on a line - so it can never answer "olive oil" with "sesame oil"
        or attribute a record. An unconfirmed item question returns nothing here; the route hands its candidates to the model.
        """
        item_domain = domain in ("food", "shopping")
        if item_domain:
            resolution = self.resolve_question(query, domain, bare=True)
            if resolution is not None and resolution["deterministic"]:
                return self.resolution_hits(resolution)[:max(1, min(int(limit), 50))]
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
        floor = (len(content) or 1) if item_domain else 1 if len(content) <= 2 else 2
        index = self.item_index()
        item_files = {str(record["path"]) for record in index["records"]}

        def names_the_file(path: Path) -> bool:
            stem = set(_words(path.stem))
            return bool(stem & set(terms)) and all(
                term in stem or term in domain_terms or term in _LISTING_FILLER for term in terms
            )

        files = [path for path in self.iter_files(domain) if path.name.lower() not in _DOC_FILES]
        listed = [path for path in files if names_the_file(path)]
        listed_data = [path.relative_to(self.root).as_posix() for path in listed]
        if any(rel in item_files for rel in listed_data):  # a named data file is listed record by record, not its pointer doc
            return self.record_listing([rel for rel in listed_data if rel in item_files], limit)
        if listed:
            files = listed  # the question names a list or table: answer from it alone
        elif not content:
            return []  # only the domain's own words: nothing to look up
        elif item_domain:  # files of item records are answered only by resolution (above) or as a named list, never by line
            files = [path for path in files if path.relative_to(self.root).as_posix() not in item_files]
        hits = []
        for path in files:
            rel = path.relative_to(self.root).as_posix()
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            hidden = _hidden_lines(rel, lines)
            path_terms = set(_words(path.stem))
            listing = bool(listed)
            path_bonus = len(path_terms & set(terms))
            structured = path.suffix.lower() in {".yaml", ".yml"}
            entries = _yaml_entries(lines) if structured else []
            table_head = ""
            for number, line in enumerate(lines, 1):
                if number - 1 in hidden:
                    continue  # a field outside the safe allowlist is never a hit, a snippet or a context
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
                    context = _entry_text(lines, covering[0], entries, terms, [text], hidden)
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

    def _index_candidates(self) -> List[Path]:
        """Household files the item index may read: an ALLOWLIST (household/food, household/kitchen, household/cleaning, and
        shopping or grocery lists anywhere under household/). Everything else - profile, finance, health, notes, secrets, the
        record collection, plants - is never indexed, whatever it is called."""
        files = []
        for path in self.iter_files():
            rel = path.relative_to(self.root).as_posix()
            if _INDEXED_PATH.search(rel) and path.name.lower() not in _DOC_FILES:
                files.append(path)
        return files

    def item_index(self, domain: Optional[str] = None) -> Dict[str, object]:
        """Index of the household records the allowlist admits (`_index_candidates`), cached until a file changes.

        YAML and JSON files are parsed into nodes (block or flow style; nested groups pass their category down; aliases or
        also_known_as as lists or inline; nulls ignored); a record is a mapping with a name, item, product or ingredient.
        Shopping-list Markdown yields one record per list item. Each record: id, name, aliases (and which it owns), phrase keys,
        exact spelling, file, line, kind, quantity and quantity_state, category. `read` lists files whose records were indexed;
        `failed` files that did not parse; `unparsed` maps files in a layout that is not recognised (a name-keyed mapping, a plain
        list, a pantry.md) to their lines - they are NOT treated as read, and their matching lines go to the model as evidence.
        `domain` is accepted for compatibility and ignored. The cache key is every candidate file's (path, mtime, size).
        """
        candidates = self._index_candidates()
        signature = []
        digest_budget = _SIGNATURE_BYTE_BUDGET
        for path in candidates:
            try:
                stat = path.stat()
            except OSError:
                continue
            digest = ""
            if stat.st_size <= min(_MAX_INDEX_FILE_BYTES, digest_budget):
                try:
                    digest = hashlib.blake2b(path.read_bytes(), digest_size=16).hexdigest()
                    digest_budget -= stat.st_size
                except OSError:
                    pass
            # size + mtime alone are not enough: an equal-length edit that restores the mtime must not serve old facts
            signature.append((path.relative_to(self.root).as_posix(), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, digest))
        cache_key = str(self.root)
        cached = _INDEX_CACHE.get(cache_key)
        if cached is not None and cached[0] == tuple(signature):
            return cached[1]
        records: List[Dict[str, object]] = []
        read: List[str] = []
        failed: List[str] = []
        unparsed: Dict[str, List[str]] = {}
        kinds: Dict[str, str] = {}
        deadline = time.monotonic() + _INDEX_TIME_BUDGET
        for path in candidates:
            rel = path.relative_to(self.root).as_posix()
            kind = _file_kind(rel)
            suffix = path.suffix.lower()
            if time.monotonic() > deadline:
                failed.append(rel)  # not reached within the time budget: reported unreadable, never guessed
                continue
            try:
                if path.stat().st_size > _MAX_INDEX_FILE_BYTES:
                    raise ValueError("file too large to index")
                text = path.read_text(encoding="utf-8", errors="replace")
                if suffix in {".yaml", ".yml", ".json"}:
                    found = _yaml_records(text, rel, kind)
                elif kind == SHOPPING and suffix in {".md", ".txt"}:
                    found = _list_records(text.splitlines(), rel, kind)
                else:
                    found = []
            except Exception:  # any failure of one file is that file being unreadable, never a failed turn
                failed.append(rel)
                continue
            if found is None:
                failed.append(rel)
                continue
            if not found:
                lines = text.splitlines()
                if any(_fact_text(line, suffix in {".yaml", ".yml", ".json"}, False, True) for line in lines):
                    unparsed[rel] = lines
                continue
            read.append(rel)
            kinds[rel] = kind
            records.extend(found)
        _mark_alias_ownership(records)
        index = {"records": records, "read": read, "failed": failed, "unparsed": unparsed, "kinds": kinds,
                 "files": [path.relative_to(self.root).as_posix() for path in candidates]}
        _INDEX_CACHE[cache_key] = (tuple(signature), index)
        return index

    def shopping_index(self) -> Dict[str, object]:
        """The shopping-list part of the item index."""
        index = self.item_index()
        files = [rel for rel in index["read"] if index["kinds"][rel] == SHOPPING]
        return {"records": [r for r in index["records"] if r["kind"] == SHOPPING], "read": files,
                "failed": [rel for rel in index["failed"] if _file_kind(rel) == SHOPPING]}

    def resolve_question(self, query: str, domain: Optional[str] = None, bare: bool = False) -> Optional[Dict[str, object]]:
        """Resolve a question about one item against the record index. Returns None when the text is not about one item.

        The result carries `outcome` (found / ambiguous / not_present / unresolved), the found `records`, the `candidates`, and
        `deterministic` - True ONLY for found (an exact record). Nothing else is ever answered without the model: there is no
        deterministic "not present". `evidence` says whether the candidates, unparsed-file lines or unreadable files are worth
        giving to the model; `scoped` whether the question named its scope ("in stock", "in the fridge", "on the shopping list").
        A shopping question ("do we need to buy X", "is X on the shopping list") counts only when the list is named or X is on
        the list (exactly or closely); "we need a holiday" or "should we get a dishwasher" is not one.
        `bare`: text with no item phrasing ("stock cubes", "can i cook spaghetti tonight") is kept only when a run of its words
        is exactly a record's name (used by `search`).
        """
        index = self.item_index()
        parsed = item_question(query)
        if parsed is None:
            if not bare or domain not in ("food", "shopping"):
                return None
            return self._bare_resolution(query, index)
        if parsed["wh"] and not parsed["mention"]:
            return None  # "what is in stock?": a listing question, answered by the list itself
        shopping = parsed["kind"] == SHOPPING
        pool = [r for r in index["records"] if (r["kind"] == SHOPPING) == shopping] if not shopping else index["records"]
        if not index["files"]:
            return None  # no inventory file at all: not a question this household can speak to
        result = _resolve(parsed, pool, load_item_vocabulary())
        if shopping and not re.search(r"\b(?:shopping|grocery)\s+list\b", (query or "").lower()):
            on_list = [r for r in result["records"] + result["candidates"][:3] if r["kind"] == SHOPPING]
            if not (result["outcome"] == FOUND or (on_list and result["strength"] >= 2)):
                return None  # "we need a holiday", "should we get a dishwasher": not a shopping-list question
        result["read"] = list(index["read"])
        result["failed"] = list(index["failed"])
        result["unparsed"] = sorted(index["unparsed"])
        result["unparsed_lines"] = _matching_lines(index["unparsed"], result["key"])
        result["scoped"] = bool(parsed.get("scoped"))
        result["deterministic"] = result["outcome"] == FOUND
        result["domain"] = _record_domain(result["records"][0]) if result["deterministic"] else ("shopping" if shopping else "food")
        result["evidence"] = bool(
            result["outcome"] == AMBIGUOUS or result["scoped"] or result["unparsed_lines"]
        )
        return result

    def _bare_resolution(self, query: str, index: Dict[str, object]) -> Optional[Dict[str, object]]:
        """The longest run of the text's words that is exactly a record's name (or owned alias), as a found resolution."""
        tokens = _phrase_tokens(query)
        records = index["records"]
        for size in range(len(tokens), 0, -1):
            for start in range(len(tokens) - size + 1):
                run = tuple(tokens[start:start + size])
                rest = tokens[:start] + tokens[start + size:]
                if all(word in _STOP_TERMS for word in run) or not all(_norm(word) in _BARE_FILLER for word in rest):
                    continue  # every other word must be filler: "olive oil" is not "olives" plus "oil"
                exact = _exact_records(run, phrase_key(" ".join(run)), records)
                if exact:
                    return {"mention": " ".join(run), "key": phrase_key(" ".join(run)), "kind": STOCK, "field": None,
                            "checked": len(records), "records": exact, "candidates": [], "strength": 3, "outcome": FOUND,
                            "read": list(index["read"]), "failed": list(index["failed"]), "unparsed": sorted(index["unparsed"]),
                            "unparsed_lines": _matching_lines(index["unparsed"], phrase_key(" ".join(run))), "scoped": False,
                            "deterministic": True, "evidence": False,
                            "domain": _record_domain(exact[0])}
        return None

    def mentions_recorded_item(self, text: str) -> bool:
        """Whether any word of the text (not a stop or filler word) is a word of an indexed record's name or alias, in either
        grammatical number ("can i cook with tomato tonight" mentions the tomatoes record)."""
        words = {_singular(token) for token in _phrase_tokens(text)
                 if len(token) >= 3 and token not in _STOP_TERMS and _norm(token) not in _BARE_FILLER}
        return any(words & set(key) for record in self.item_index()["records"] for key in record["keys"])

    def resolve_item(self, query: str, domain: Optional[str] = "food") -> Optional[Dict[str, object]]:
        """Compatibility name for `resolve_question` (stock and shopping questions)."""
        return self.resolve_question(query, domain or "food")

    def resolution_hits(self, resolution: Dict[str, object]) -> List[Dict[str, object]]:
        """Hits for a resolved question. found yields one hit per exact record (all of them, each with its file, line and
        fields as quoted data). Every other outcome yields one hit that says the item is NOT CONFIRMED and lists up to five
        candidates - it never says the item is absent."""
        outcome = resolution["outcome"]
        mention = str(resolution["mention"])
        hits: List[Dict[str, object]] = []
        if outcome == FOUND:
            for record in resolution["records"]:
                if record["kind"] == SHOPPING:
                    state = "ticked (already bought)" if record.get("ticked") else "not ticked yet"
                    context = f"on the shopping list: {_quoted(_record_text(record))} ({state})"
                else:
                    context = _record_data(record, resolution.get("field"))
                    if record["kind"] not in (STOCK, "food"):
                        context = f"{record['kind']} record: {context}"
                    if record["out_of_stock"]:
                        context += f"; recorded, but out of stock (quantity {_quoted(record['quantity'])})"
                if record is resolution["records"][0] and resolution.get("unparsed_lines"):
                    context += "".join(f"; also see {rel} line {number} (not read as a record)" + (f": {_quoted(text)}" if text else "")
                                       for rel, number, text in resolution["unparsed_lines"][:3])
                state = record.get("quantity_state")
                hits.append({
                    "path": record["path"], "line": record["line"], "snippet": context[:500],
                    "score": len(resolution["key"]), "entry": record["name"], "resolution": FOUND, "record_id": record["id"],
                    "in_stock": False if state == "out" else True if state == "in" else None, "context": context,
                    "kind": record["kind"],
                })
            return hits
        candidates = resolution["candidates"][:_HIT_CANDIDATES]
        named = ", ".join(f"{_quoted(c['name'], 80)} ({c['path']} line {c['line']})" for c in candidates)
        total = int(resolution.get("candidates_total") or len(resolution["candidates"]))
        extra = total - len(candidates)
        more = f" and {extra} more" if extra > 0 else ""
        reason = (resolution.get("reason") or f"no household record is named exactly {_quoted(mention, 80)}") if mention \
            else "the question does not name one item"
        text = f"Not confirmed: {reason}."
        text += (f" Recorded items that may be meant: {named}{more}. I cannot say yes or no from a partial or related match."
                 if candidates else " I found no related record, but I cannot say it is absent either.")
        if resolution.get("failed") or resolution.get("unparsed"):
            text += " Some household files could not be read as records: " + _bounded_names(
                list(resolution.get("failed") or []) + list(resolution.get("unparsed") or [])) + "."
        lead = candidates[0] if candidates else {"path": (resolution.get("read") or ["household"])[0], "line": 1}
        hits.append({
            "path": lead["path"], "line": lead["line"], "score": 0, "resolution": outcome if outcome != NOT_PRESENT else UNRESOLVED,
            "snippet": text,
            "candidates": [{"id": c["id"], "name": c["name"], "path": c["path"], "line": c["line"]} for c in candidates],
            "candidates_omitted": max(0, extra),
        })
        return hits

    _resolution_hits = resolution_hits

    def evidence_text(self, resolution: Dict[str, object], limit: Optional[int] = None) -> str:
        """The evidence for an unconfirmed item question, as quoted data lines for the model: the candidate records (file, line,
        kind, fields), matching lines of files in an unrecognised layout, and the files that could not be read."""
        limit = _EVIDENCE_CANDIDATES if limit is None else min(int(limit), _EVIDENCE_CANDIDATES)
        lines = [f"Item asked about (quoted from the question): {_quoted(resolution['mention'], 80)}",
                 f"Outcome of the exact-name lookup: {resolution['outcome']} ({resolution['checked']} records checked)"]
        for record in resolution["candidates"][:limit]:
            data = _record_data(record) if record["kind"] != SHOPPING or "text" not in record else f"text: {_quoted(_record_text(record))}"
            lines.append(f"- {record['path']} line {record['line']} ({record['kind']}): {data}")
        total = int(resolution.get("candidates_total") or len(resolution["candidates"]))
        if total > limit:
            lines.append(f"- and {total - limit} more related records")
        for rel, number, text in resolution.get("unparsed_lines") or []:
            lines.append(f"- {rel} line {number} (file not in a recognised record layout)" + (f": {_quoted(text)}" if text else ""))
        if not resolution["candidates"] and not resolution.get("unparsed_lines"):
            lines.append("- no related record was found")
        unreadable = list(resolution.get("failed") or []) + list(resolution.get("unparsed") or [])
        if unreadable:
            lines.append("Some files could not be read as records: " + _bounded_names(unreadable))
        return "\n".join(lines)[:_EVIDENCE_CHARS]

    def record_listing(self, files: Iterable[str], limit: int = 50) -> List[Dict[str, object]]:
        """The records of the named data files as listing hits ("what is in stock?" lists the stock records, not the pointer
        document next to them): name, plus the quantity when one is recorded."""
        wanted = set(files)
        hits = []
        for record in self.item_index()["records"]:
            if record["path"] not in wanted:
                continue
            if record["kind"] == SHOPPING:
                text = _record_text(record) + (" (ticked)" if record.get("ticked") else "")
            else:
                text = record["name"] + (f" ({_quoted(record['quantity'], 60)})" if record.get("quantity") else "")
            hits.append({"path": record["path"], "line": record["line"], "snippet": text, "score": 0, "listed": True,
                         "entry": record["name"]})
        return hits[:max(1, min(int(limit), 50))]

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
            hidden = _hidden_lines(rel, lines)
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
                    if number in hidden or any(o is not entry and o["example"] and o["start"] <= number < o["end"] for o in entries):
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
                context = _entry_text(lines, entry, entries, terms, matched_lines, hidden)
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

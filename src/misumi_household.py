"""Read-only adapter for the canonical household repository."""

from __future__ import annotations

import difflib
import hashlib
import json
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


# --- item resolution for stock and shopping-list questions --------------------------------------------------------------------
# A question about one item ("Do we have any X left?", "What's the quantity of X in stock?", "Is X running low?", "X in the
# fridge?", "Do we need to buy X?") is answered by resolving X to recorded items, never by counting shared words. The question's
# scaffolding - question words, presence and quantity phrasing, location and container words, field words, a trailing purpose
# ("for dinner") - is removed by pattern from both ends; what is left is the item mention. A mention resolves only to a record
# whose whole name (or its own alias) has the same words. Anything less is reported as unconfirmed with the candidates, and "not
# present" is said only when no record is even related (shared head noun, containment, category, vocabulary relation, spelling).

FOUND, NOT_PRESENT, AMBIGUOUS, UNRESOLVED = "found", "not_present", "ambiguous", "unresolved"
STOCK, SHOPPING = "stock", "shopping"
_INVENTORY_FILE = re.compile(r"stock|inventory|pantry|larder|freezer|fridge|cupboard", re.IGNORECASE)
_CONTRACTIONS = (
    (r"\bwe're\b", "we are"), (r"\bwe've\b", "we have"), (r"\bi've\b", "i have"), (r"\bdon't\b", "do not"),
    (r"\bdidn't\b", "did not"), (r"\bhaven't\b", "have not"), (r"\bhasn't\b", "has not"), (r"\bisn't\b", "is not"),
    (r"\baren't\b", "are not"), (r"\bthere's\b", "there is"), (r"\bwhat's\b", "what is"), (r"\bit's\b", "it is"),
    (r"\bwhere's\b", "where is"), (r"\bhow's\b", "how is"), (r"\bthat's\b", "that is"), (r"\bshouldn't\b", "should not"),
    (r"\bwhich's\b", "which is"), (r"\bwe'd\b", "we would"),
)
_QUALIFIERS = r"(?:not|still|currently|even|already|just|all|completely|totally|now|really|actually)\s+"
_OUT_OF = r"(?:out\s+of|low\s+on|short\s+(?:of|on)|running\s+(?:low\s+on|out\s+of)|nearly\s+out\s+of|almost\s+out\s+of)"
_ACQUIRE = r"(?:buy|get|pick\s+up|order|grab|purchase)"
# A field of a record that a question may ask for ("the quantity of X", "the X expiry").
_FIELD = (r"(?:quantity|amount|number|stock\s+level|level|count|expiry(?:\s+date)?|use[\s-]?by(?:\s+date)?"
          r"|best[\s-]before(?:\s+date)?|sell[\s-]by(?:\s+date)?)")
# Where an item is kept: "in the fridge", "in the food cupboard", "on the top shelf", "in the kitchen cupboard".
_PLACE_NOUN = (r"(?:fridge|freezer|cupboards?|pantry|larder|kitchen|shelf|shelves|stock|inventory|house|flat|home|drawers?"
               r"|cabinets?|storage|store|cellar|fruit\s+bowl|bread\s+bin|spice\s+rack)")
# (pattern, kind it marks: STOCK, SHOPPING or None for scaffolding that does not by itself make an item question).
# Each pattern is anchored at the start of what is left; they are tried in order, so the shopping and field patterns come
# before the generic ones that would otherwise consume part of them.
_SCAFFOLD_PREFIXES = tuple((re.compile(rf"^(?:{pattern})(?:\s+|$)"), kind) for pattern, kind in (
    (rf"(?:do|did|does)\s+(?:not\s+)?(?:we|i|you)\s+(?:{_QUALIFIERS})*need(?:\s+to\s+{_ACQUIRE})?", SHOPPING),
    (rf"(?:should|shall|must|can|do)\s+(?:not\s+)?(?:we|i)\s+(?:{_QUALIFIERS})*{_ACQUIRE}", SHOPPING),
    (rf"(?:we|i)\s+(?:{_QUALIFIERS})*need(?:\s+to\s+{_ACQUIRE})?", SHOPPING),
    (rf"(?:are|am)\s+(?:we|i)\s+(?:{_QUALIFIERS})*(?:buying|getting|ordering)", SHOPPING),
    (rf"(?:do|did|does)\s+(?:not\s+)?(?:we|i|you|they)\s+(?:{_QUALIFIERS})*(?:have|has|got|own|keep|stock)", STOCK),
    (rf"(?:have|has)\s+(?:not\s+)?(?:we|i|you)\s+(?:{_QUALIFIERS})*got", STOCK),
    (rf"(?:have|has|did)\s+(?:not\s+)?(?:we|i|you)\s+(?:{_QUALIFIERS})*(?:run|ran|gone|went)\s+out\s+of", STOCK),
    (rf"(?:are|were)\s+(?:not\s+)?(?:we|you)\s+(?:{_QUALIFIERS})*{_OUT_OF}", STOCK),
    (rf"we\s+are\s+(?:{_QUALIFIERS})*{_OUT_OF}", STOCK),
    (rf"we\s+(?:{_QUALIFIERS})*(?:have|got)", STOCK),
    (rf"(?:is|are)\s+there(?:\s+{_QUALIFIERS[:-3]})*", STOCK),
    (rf"there\s+(?:is|are|was|were)(?:\s+{_QUALIFIERS[:-3]})*", STOCK),  # embedded: "tell me if there is any X"
    (r"how\s+(?:much|many)", STOCK),
    (rf"(?:what|which|how)\s+(?:is|are|was|were)\s+(?:the\s+|our\s+)?(?:current\s+)?{_FIELD}\s+(?:of|for|on)", STOCK),
    (rf"(?:what|which)\s+{_FIELD}\s+of", STOCK),
    (rf"(?:the\s+|our\s+)?(?:current\s+)?{_FIELD}\s+(?:of|for|on)", STOCK),
    (r"(?:got|any)", STOCK),
    (r"(?:(?:can|could|would)\s+you\s+(?:please\s+)?)?(?:check|tell\s+me|see|look|find\s+out)(?:\s+(?:if|whether))?", None),
    (r"(?:what|which)(?:\s+(?:kinds?|types?|sorts?|brands?)\s+of)?(?:\s+(?:is|are|was|were))?", None),
    (r"(?:please|hey|hi|ok|okay|so|um|uh|and|but|also|if|whether|is|are)", None),
    (r"(?:still|even|currently|some|more|enough|a|an|the|of|our|my)", None),
))
_SCAFFOLD_SUFFIXES = tuple((re.compile(rf"(?:^|\s+)(?:{pattern})$"), kind) for pattern, kind in (
    (r"on\s+(?:the\s+|our\s+|my\s+)?(?:shopping\s+|grocery\s+)?list", SHOPPING),
    (r"(?:for|from)\s+(?:the\s+)?(?:shopping|shop|groceries|supermarket)", SHOPPING),
    (rf"(?:do|did|does)\s+(?:we|i)\s+(?:still\s+)?need(?:\s+to\s+{_ACQUIRE})?", SHOPPING),
    (r"needs?\s+(?:buying|getting|to\s+be\s+bought)", SHOPPING),
    (r"in\s+stock", STOCK),
    (rf"(?:in|at|on|inside|from)\s+(?:the\s+|our\s+|my\s+)?(?:[a-z']+\s+){{0,2}}?{_PLACE_NOUN}", STOCK),
    (r"at\s+home", STOCK),
    (r"(?:left|remaining)(?:\s+over)?", STOCK),
    (r"(?:running|getting|going|almost|nearly|very)\s+(?:low|out|empty|gone|finished)|low|all\s+gone|used\s+up|run\s+out|finished",
     STOCK),
    (r"(?:do|did)\s+(?:we|i|you)\s+(?:still\s+)?(?:have|got)", STOCK),
    (r"have\s+(?:we|i|you)\s+(?:still\s+)?got", STOCK),
    (r"(?:we|i)\s+(?:still\s+)?(?:have|got)", STOCK),
    (r"(?:is|are)\s+there", STOCK),
    (_FIELD, STOCK),
    (r"(?:for|to)\s+(?:make|making|cook|cooking|bake|baking|use|using|eat|dinner|lunch|breakfast|tea|supper|tonight|tomorrow"
     r"|the\s+\w+|a\s+\w+)(?:\s+\w+){0,3}", None),
    (r"(?:still|anymore|any\s+more|at\s+the\s+moment|right\s+now|now|please|at\s+all|or\s+not|yet|then|currently|today|is|are)",
     None),
    # tag questions: "we're out of X, right?", "we have X, don't we?"
    (r"(?:right|correct|yeah|yes|no|or\s+what|(?:is|are|do|does|have|has)(?:\s+not)?\s+(?:it|we|they|there)|(?:isn't|aren't|don't|"
     r"doesn't|haven't|hasn't)\s+(?:it|we|they|there))", None),
))
_FIELD_WORD = re.compile(rf"(?:^|\s){_FIELD}$")
# A mention made only of these names no item ("anything", "food"): it is a listing or an open question, not an item.
_LISTING_NOUNS = frozenset({
    "anything", "something", "everything", "nothing", "stuff", "item", "thing", "food", "ingredient", "grocery", "one", "what",
})
# A mention containing one of these is not a parsed item name ("eggs and bread", "anything good"): never a confident "no".
_NON_ITEM_WORDS = frozenset({
    "for", "to", "with", "without", "before", "after", "about", "what", "when", "which", "who", "how", "why", "if", "we", "i",
    "you", "it", "that", "this", "them", "those", "these", "anything", "something", "everything", "nothing", "stuff", "thing",
    "things", "food", "ingredient", "ingredients", "enough", "is", "are", "do", "does", "have", "has", "make", "cook", "can",
    "should", "could", "would", "or", "but", "not",
})
_LINK_WORDS = frozenset({"and", "of", "the", "a", "an", "with", "in", "on"})
_PHRASE_TOKEN = re.compile(r"[^\W_]+(?:'[^\W_]+)?")
# A recorded quantity that says the item has run out: "0", "0 tins", "none", "none left", "no", "nil", "nothing left", "out",
# "out of stock", "empty", "gone", "all gone", "used up", "finished", "run out", "ran out", "depleted", "sold out" - optionally
# followed by a separated remark ("out - buy more", "0 (checked Monday)"). "no idea", "not checked" are NOT zero.
_ZERO_QUANTITY = re.compile(
    r"^[\"']?\s*(?:0+(?:\.0+)?(?:\s+[a-z]+)?|none(?:\s+left)?|no(?:ne)?\s+(?:left|remaining)|no|nil|nothing(?:\s+left)?|zero(?:\s+[a-z]+)?"
    r"|(?:all\s+)?out(?:\s+of\s+stock)?|empty|(?:all\s+)?gone|(?:all\s+)?used(?:\s+up)?|finished|(?:run|ran)\s+out|depleted|sold\s+out)"
    r"\s*[\"']?\s*(?:[-;,(:].*)?$",
    re.IGNORECASE,
)


def _phrase_tokens(text: str) -> List[str]:
    return _PHRASE_TOKEN.findall((text or "").lower().replace("’", "'").replace("&", " and ").replace("_", " "))


def phrase_key(text: str) -> tuple:
    """Normalised word sequence of an item name or mention: 'Coconut Milk' -> ('coconut', 'milk'), 'cookies' -> ('cooky',)."""
    return tuple(_singular(token) for token in _phrase_tokens(text))


def item_question(question: str) -> Optional[Dict[str, object]]:
    """Parse a question about one item: what it names, and whether it asks about stock or the shopping list.

    The scaffolding is removed by pattern from both ends ("what's the quantity of", "do we still have any", "in the food
    cupboard", "running low", "on the shopping list", "expiry", "for dinner"). Returns None when the text has no stock or
    shopping phrasing at all ("What should I cook tonight?", "What is gochujang?"), otherwise
    {"mention": "olive oil", "kind": "stock"|"shopping", "wh": bool, "field": "expiry"|None}. The mention is "" when the
    question names no item ("Do we have any left in stock?", "What do we have in stock?").
    """
    text = (question or "").lower().replace("’", "'")
    for pattern, replacement in _CONTRACTIONS:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"[?!.,;:\"]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    wh = bool(re.match(r"^(?:what|which)\b", text))
    kinds: set = set()
    field = None
    changed = True
    while changed and text:
        changed = False
        for pattern, kind in _SCAFFOLD_PREFIXES:
            match = pattern.match(text)
            if match and match.end():
                found_field = re.search(_FIELD, match.group(0))
                field = field or (found_field.group(0) if found_field and kind else None)
                text = text[match.end():].strip()
                if kind:
                    kinds.add(kind)
                changed = True
                break
        for pattern, kind in _SCAFFOLD_SUFFIXES:
            match = pattern.search(text)
            if match:
                if pattern.pattern.endswith(f"(?:{_FIELD})$"):
                    field = field or match.group(0).strip()
                text = text[:match.start()].strip()
                if kind:
                    kinds.add(kind)
                changed = True
                break
    if not kinds:
        return None
    if text and all(_singular(token) in _LISTING_NOUNS for token in _phrase_tokens(text)):
        text = ""
    return {"mention": text, "kind": SHOPPING if SHOPPING in kinds else STOCK, "wh": wh, "field": field}


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
    """Phrase keys the vocabulary relates to any whole run of words in `key` ('grated parmesan' -> parmigiano, cheese, ...)."""
    found: set = set()
    for size in range(len(key), 0, -1):
        for start in range(len(key) - size + 1):
            found |= vocabulary.get(key[start:start + size], set())
    return found


def _head(key: tuple) -> str:
    return key[-1] if key else ""


def _contains(outer: tuple, inner: tuple) -> bool:
    """`inner` occurs in `outer` as a whole run of words (token boundaries, same order)."""
    size = len(inner)
    return 0 < size <= len(outer) and any(outer[i:i + size] == inner for i in range(len(outer) - size + 1))


def _near_miss(mention: tuple, key: tuple) -> int:
    """How strongly a record that is NOT an exact match still overlaps the mention (0 = unrelated).

    3: one phrase lies whole inside the other ("olive oil" / "olives", "soy sauce" / "dark soy sauce", "coconut milk" / "milk");
    2: they share a head noun ("chilli sauce" / "hot sauces"); 1: a spelling near-miss ("brocoli" / "broccoli", "brocoli" /
    "tenderstem broccoli") or one head word is a whole prefix or suffix of a recorded word ("pepper" / "peppercorns").
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
    for word in (_head(mention),):
        for recorded in key:
            if len(word) >= 4 and word != recorded and (recorded.startswith(word) or recorded.endswith(word)):
                return 1
    for recorded in (_head(key),):
        for word in mention:
            if len(recorded) >= 4 and word != recorded and (word.startswith(recorded) or word.endswith(recorded)):
                return 1
    return 0


def _relation(mention: tuple, record: Dict[str, object], vocabulary: Dict[tuple, set]) -> int:
    """How strongly a record relates to a mention it does not match exactly (0 = unrelated; higher = more likely meant).

    Its name or aliases (see _near_miss); its category ("cheese" for a brie filed under cheese, "dairy" for butter); and the
    vocabulary ("cheese" -> brie, "pasta" -> spaghetti, "sriracha" -> hot sauces, "parmesan" -> Parmigiano Reggiano).
    """
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


_EMPTY_VALUES = frozenset({"", "null", "~", "[]", "{}", "none"})


def _scalar(value: object) -> str:
    """A YAML scalar as its text: a double-quoted value has its escapes decoded ('\\"' -> '"'), a single-quoted one its ''."""
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        try:
            return str(json.loads(text)).strip()
        except ValueError:
            return text[1:-1].strip()
    if len(text) >= 2 and text[0] == text[-1] == "'":
        return text[1:-1].replace("''", "'").strip()
    return text


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
        if key.endswith("@line") or key in {"example", "id"}:
            continue
        if key.endswith("[]"):
            values = [_scalar(item) for item in value if _scalar(item).lower() not in _EMPTY_VALUES]
            if values:
                parts.append(f"{key[:-2]}: " + ", ".join(_quoted(item, 80) for item in values))
            continue
        raw = _scalar(value)
        if raw.lower() in _EMPTY_VALUES:
            if key in wanted or any(key.startswith(word) for word in wanted):
                parts.append(f"{key}: not recorded")
            continue
        parts.append(f"{key}: {_quoted(raw)}")
    joined = "; ".join(parts)
    if len(joined) > limit:
        joined = joined[:limit - 1].rstrip() + "…"
    return joined


def _mark_alias_collisions(records: List[Dict[str, object]]) -> None:
    """Flag each record's alias keys that another record also uses (as its name or an alias): such an alias cannot pick one."""
    owners: Dict[tuple, set] = {}
    for number, record in enumerate(records):
        for key in record["keys"]:
            owners.setdefault(tuple(sorted(key)), set()).add(number)
    for record in records:
        record["alias_collisions"] = [key for key in record["keys"][1:] if len(owners[tuple(sorted(key))]) > 1]


def _same_words(a: tuple, b: tuple) -> bool:
    return a == b or sorted(a) == sorted(b)


def _resolve(parsed: Dict[str, object], index: Dict[str, object], vocabulary: Dict[tuple, set]) -> Dict[str, object]:
    """The four-way resolution of one parsed mention against one item index (see HouseholdReadOnlyAdapter.resolve_item)."""
    records = index["records"]
    mention = str(parsed["mention"])
    key = phrase_key(mention)
    result: Dict[str, object] = {
        "mention": mention, "key": key, "kind": parsed["kind"], "field": parsed.get("field"), "read": index["read"],
        "checked": len(records), "records": [], "candidates": [], "strength": 0,
    }
    if not records:
        result.update(outcome=UNRESOLVED, reason="no recorded items")
        return result
    if not key:
        result.update(outcome=UNRESOLVED, reason="the question does not name an item")
        return result
    by_name = [record for record in records if _same_words(record["keys"][0], key)]
    by_alias = [record for record in records if record not in by_name and any(_same_words(k, key) for k in record["keys"][1:])]
    if by_name:
        result.update(outcome=FOUND, records=by_name, candidates=by_alias, strength=3)
        return result
    if by_alias:
        if len(by_alias) == 1 and not any(_same_words(k, key) for k in by_alias[0]["alias_collisions"]):
            result.update(outcome=FOUND, records=by_alias, strength=3)
        else:
            result.update(outcome=AMBIGUOUS, candidates=by_alias, strength=3,
                          reason=f"{_quoted(mention, 80)} is an alias that more than one record uses")
        return result
    unparsed = len(key) > 5 or bool(set(_phrase_tokens(mention)) & _NON_ITEM_WORDS)
    # In a mention that is not a clean item name ("eggs and bread or something") only strong relations are candidates.
    probe = tuple(_singular(t) for t in _phrase_tokens(mention) if t not in _NON_ITEM_WORDS) if unparsed else key
    scored = []
    for position, record in enumerate(records):
        strength = _relation(probe, record, vocabulary) if probe else 0
        if strength and not (unparsed and strength < 2):
            scored.append((-strength, position, record))
    scored.sort(key=lambda row: (row[0], row[1]))
    result["candidates"] = [row[2] for row in scored]
    result["strength"] = -scored[0][0] if scored else 0
    if unparsed:
        result.update(outcome=UNRESOLVED, reason="the question does not clearly name one item")
    elif scored:
        result.update(outcome=AMBIGUOUS)
    else:
        result.update(outcome=NOT_PRESENT)
    return result


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

        In the food and shopping domains a question about one item (or a bare item name) is answered by entity resolution
        (`resolve_question`), never by word overlap. The word-overlap lookup that remains there can only list a named file or
        quote lines from files that hold no item records (preferences, equipment, recipes), and only when EVERY content word of
        the question is on the line - so it can never answer "olive oil" with "sesame oil" or attribute a stock record.
        """
        item_domain = domain in ("food", "shopping")
        if item_domain:
            resolution = self.resolve_question(query, domain, bare=True)
            if resolution is not None:  # a question about one item: answered by entity resolution, never by word overlap
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
        item_files: set = set()
        if item_domain:
            item_files = set(self.item_index("food")["read"]) | set(self.shopping_index()["read"])

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
        else:  # files of item records are answered only by resolution (above) or as a whole named list, never line by line
            files = [path for path in files if path.relative_to(self.root).as_posix() not in item_files]
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
        """Canonical index of the recorded items in the food inventory files (stock.yaml, freezer.yaml, pantry.yaml and the like).

        Each record: stable id (its own `id:` field, else path:line), canonical name, aliases, the whole-phrase keys of the name
        (first) and aliases, the category key, the file and line that hold the name, the quantity as recorded, whether that quantity
        says it ran out, and `alias_collisions`: its alias keys that another record also uses as a name or alias (such an alias is
        never trusted to pick one record). Demonstration entries (`example: true`) and nested entries are not records. `read` lists
        the inventory files read. The inventory always lives in the food domain, whatever domain the question was filed under.
        """
        records: List[Dict[str, object]] = []
        read: List[str] = []
        for path in self.iter_files("food"):
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
                    "category_key": phrase_key(_unquote(fields.get("category"))),
                    "out_of_stock": bool(quantity and _ZERO_QUANTITY.match(quantity)), "kind": STOCK,
                    "_fields": fields,
                })
        _mark_alias_collisions(records)
        return {"records": records, "read": read}

    def shopping_index(self) -> Dict[str, object]:
        """The items on the shopping list(s): one record per real list item (checkbox, bullet or numbered line), with the item
        name taken before any detail ("milk - 2 pints" -> milk), whether it is ticked, and its file and line. Placeholders,
        headings and notes are not items."""
        records: List[Dict[str, object]] = []
        read: List[str] = []
        for path in self.iter_files("shopping"):
            if path.suffix.lower() not in {".md", ".txt"} or path.name.lower() in _DOC_FILES:
                continue
            rel = path.relative_to(self.root).as_posix()
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            read.append(rel)
            for number, line in enumerate(lines, 1):
                text = _fact_text(line, False, False)
                found = re.match(r"^(?:[-*+]|\d+[.)])\s+(?:\[([ xX])\]\s+)?(.+)$", text)
                if not found:
                    continue
                item = found.group(2).strip()
                name = re.split(r"\s+[-–—]\s+|\s*\(|:\s", item, maxsplit=1)[0].strip().strip("*_`")
                key = phrase_key(name)
                if not key:
                    continue
                records.append({
                    "id": f"{rel}:{number}", "name": name, "text": item, "aliases": [], "keys": [key], "path": rel,
                    "line": number, "quantity": None, "category_key": (), "out_of_stock": False, "kind": SHOPPING,
                    "ticked": (found.group(1) or " ").lower() == "x", "alias_collisions": [], "_fields": {},
                })
        return {"records": records, "read": read}

    def resolve_question(self, query: str, domain: Optional[str] = None, bare: bool = False) -> Optional[Dict[str, object]]:
        """Resolve a question about one item against the stock inventory or the shopping list (see `resolve_item`), deciding
        from the index itself whether the question is a household-inventory question at all.

        - `domain` is the household domain inferred from the question's words, if any. A question filed under food or shopping
          is always answered by resolution (found / ambiguous / not_present / unresolved).
        - A question with no domain word ("Do we have eggs?", "Is X running low?", "X in the fridge?") is an inventory question
          only when its item mention matches a record exactly or by a strong relation; otherwise None (not a household question).
        - A question filed under another domain is taken only on an exact record match.
        - `bare`: when the text has no stock or shopping phrasing at all ("tomato"), the whole text minus question words is
          tried as the mention (used by `search` for the food and shopping domains), and kept only on a match.
        Returns None when the question is not about one item (open or listing questions such as "What do we have in stock?").
        The result carries "domain": "food" or "shopping".
        """
        parsed = item_question(query)
        if parsed is None:
            if not bare or domain not in ("food", "shopping"):
                return None
            indicators = {_singular(word) for word in DOMAIN_TERMS.get(domain, ())}
            words = [token for token in _phrase_tokens(query)
                     if token not in _STOP_TERMS and _singular(token) not in indicators and token not in _LISTING_FILLER]
            parsed = {"mention": " ".join(words), "kind": SHOPPING if domain == "shopping" else STOCK, "wh": False,
                      "field": None, "bare": True}
        if parsed["wh"] and not parsed["mention"]:
            return None  # "what is in stock?": a listing question, answered by the list itself
        index = self.shopping_index() if parsed["kind"] == SHOPPING else self.item_index("food")
        if not index["read"]:
            return None
        result = _resolve(parsed, index, load_item_vocabulary())
        result["domain"] = "shopping" if parsed["kind"] == SHOPPING else "food"
        confirmed = result["outcome"] == FOUND or (result["outcome"] == AMBIGUOUS and result["strength"] >= 2)
        if parsed.get("bare") and not confirmed:
            return None
        if domain in ("food", "shopping"):
            return result
        if domain is None:
            return result if confirmed else None
        return result if result["outcome"] == FOUND else None

    def resolve_item(self, query: str, domain: Optional[str] = "food") -> Optional[Dict[str, object]]:
        """Resolve the item a stock (or shopping-list) question names to recorded items, with one of four outcomes.

        found: every record whose own name, or own alias, has exactly the mention's words (order-insensitive only when the word
        multisets are equal) - all of them, across every inventory file. ambiguous: no such record, but records that are related
        ("olive oil" vs "olives", "cheese" vs brie, "sriracha" vs "hot sauces") - reported as candidates, never as yes or no; also
        when the only exact match is an alias that two records share. not_present: the inventory was read, the mention is a
        parsed item name, and no record is even related. unresolved: the question names no recognisable item, or the inventory
        has no records. Returns None when the question is not about one item or there is no inventory file.
        """
        return self.resolve_question(query, domain or "food")

    def resolution_hits(self, resolution: Dict[str, object]) -> List[Dict[str, object]]:
        """Hits for a resolved question. found yields one hit per matching record (all of them, each with its file, line and
        quantity); not_present yields none (the caller says what was searched); ambiguous and unresolved yield one hit that says
        the item is not confirmed, so a partial match is never read out as a yes. Recorded text is rendered as quoted data."""
        outcome = resolution["outcome"]
        mention = str(resolution["mention"])
        shopping = resolution.get("domain") == "shopping"
        noun = "shopping-list item" if shopping else "stock record"
        hits: List[Dict[str, object]] = []
        if outcome == FOUND:
            for record in resolution["records"]:
                if shopping:
                    state = "ticked (already bought)" if record["ticked"] else "not ticked yet"
                    context = f"on the shopping list: {_quoted(record['text'])} ({state})"
                    in_stock = None
                else:
                    context = _record_data(record, resolution.get("field"))
                    if record["out_of_stock"]:
                        context += f"; recorded, but out of stock (quantity {_quoted(record['quantity'])})"
                    in_stock = False if record["out_of_stock"] else (True if record["quantity"] else None)
                hits.append({
                    "path": record["path"], "line": record["line"], "snippet": context[:500],
                    "score": len(resolution["key"]), "entry": record["name"], "resolution": FOUND, "record_id": record["id"],
                    "in_stock": in_stock, "context": context,
                })
        elif outcome == AMBIGUOUS:
            candidates = resolution["candidates"][:5]
            lead = candidates[0]
            named = ", ".join(f"{_quoted(c['name'], 80)} ({c['path']} line {c['line']})" for c in candidates)
            more = f" and {len(resolution['candidates']) - 5} more" if len(resolution["candidates"]) > 5 else ""
            reason = resolution.get("reason") or f"no {noun} is named {_quoted(mention, 80)}"
            hits.append({
                "path": lead["path"], "line": lead["line"], "score": 0, "resolution": AMBIGUOUS,
                "snippet": (f"Not confirmed: {reason}. Recorded items that may be meant: {named}{more}."
                            " I cannot say yes or no from a partial or related match."),
                "candidates": [{"id": c["id"], "name": c["name"], "path": c["path"], "line": c["line"]} for c in resolution["candidates"]],
            })
        elif outcome == UNRESOLVED:
            read = list(resolution["read"])
            what = f"which recorded item {_quoted(mention, 80)} means" if mention else "which item the question asks about"
            reason = str(resolution.get("reason") or "")
            place = "on the shopping list" if shopping else "in stock"
            if "no recorded items" in reason:
                text = f"Not confirmed: the {'shopping list' if shopping else 'stock inventory'} has no recorded items yet."
            else:
                text = f"Not confirmed: I could not tell {what}, so I cannot say whether it is {place} ({resolution['checked']} {noun}s read)."
                if resolution["candidates"]:
                    text += " Recorded items it may mean: " + ", ".join(
                        f"{_quoted(c['name'], 80)} ({c['path']} line {c['line']})" for c in resolution["candidates"][:5]) + "."
            hits.append({
                "path": read[0], "line": 1, "score": 0, "resolution": UNRESOLVED, "snippet": text,
                "candidates": [{"id": c["id"], "name": c["name"], "path": c["path"], "line": c["line"]} for c in resolution["candidates"]],
            })
        return hits

    _resolution_hits = resolution_hits

    def not_present_text(self, resolution: Dict[str, object]) -> str:
        """What a not_present answer says: the item, the files read and how many records were checked."""
        noun = "shopping-list items" if resolution.get("domain") == "shopping" else "stock records"
        return (f"I can't find {_quoted(resolution['mention'], 80)} in {', '.join(resolution['read'])} "
                f"({resolution['checked']} {noun} read; nothing with a related name, category or alias either).")

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

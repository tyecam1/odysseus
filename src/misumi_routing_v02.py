"""Aoteru routing contract v0.2 - the RATIFIED lead-persona routing algorithm (ratified by the user, 2026-10-06).

Contract: ``docs/core/aoteru-routing-contract-v0.2.md`` in the canonical knowledgebase. This module is the runtime
implementation. v0.1 (``resolve_auto_lead_v01`` in ``src/misumi_persona_routing.py``) is retained verbatim as the immediate
rollback path: ``MISUMI_ROUTING_ALGORITHM=v0.1`` selects exactly v0.1 behaviour and nothing here runs.

Deterministic, stdlib-only, no model calls. Relative to v0.1:

* Persona routes still come from ``config/personas.yaml`` (``routing.intents``) - plus the ratified optional field
  ``routing.aliases``: everyday words that route to a persona at a lower weight (0.75) than a contract intent (1.0).
  There is NO built-in vocabulary here; no separate persona truth store exists.
* Matching is stem-aware (a light, symmetric stemmer) and understands multi-word intents.
* A cue inside a withdrawn span ("don't need X", "no more X", "not the X", "never mind X", "without X") counts for
  nothing; a directive *about* X ("stop reminding me about the rota") still routes to X.
* Bare keyword lists are weak evidence (x0.2 each, total capped at 0.5 - below any single real cue); bracketed text and
  "route/send this to X" / "ignore the routing rules" are not evidence, and what was ignored is recorded (``ignored_meta``).
* A short anaphoric follow-up with no cue of its own may inherit the previous turn's lead when the caller supplies a
  ``prior_lead`` (only from a persisted turn), unless it explicitly changes topic.
* Reserved matters (standards, values, boundaries, ratification, Level 5/6) route to Aoteru first, exactly as in v0.1.
* Manifest order is still the deterministic tie-break.

Provenance reasons name the LITERAL intent/alias that matched (never a stem), so learned routing revisions - which key on
exact ``keyword_present`` cue words - keep their v0.1 semantics. Nothing here migrates or reinterprets a learned revision.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from src.misumi_persona_routing import RESERVED

METHOD = "routing-contract-v0.2"
ALGORITHM = "v0.2"
FALLBACK = "aoteru"
ALIAS_WEIGHT = 0.75
BARE_LIST_WEIGHT = 0.2
BARE_LIST_CAP = 0.5  # a stuffed keyword list in total can never outvote ONE real cue (aliases are 0.75)

_TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_CLAUSE_SPLIT = re.compile(r"[.,;:!?—–]|\s-\s|\b(?:but|then|while|and then)\b")
_META = re.compile(
    r"\[[^\]]*\]|"
    r"\b(?:ignore|override|bypass)\b[^.:;,]*?\b(?:rules?|routing|instructions?)\b[^.:;,]*|"
    r"\b(?:route|send|forward|hand)\s+(?:this|it)\s+to\s+\w+",
    re.IGNORECASE,
)
_NEG_CLAUSE = re.compile(
    r"\b(?:do(?:n't| not)|dont|never)\s+(?:really\s+)?(?:need|want|require|care|worry|bother)\b|"
    r"\bno\s+(?:more|need|longer)\b|"
    r"\bnot\s+(?:asking|interested|talking|looking|after)\b|"
    r"\bnever\s*mind\b|\b(?:forget|ignore|without|instead of)\b",
    re.IGNORECASE,
)
_NEG_NEXT = re.compile(r"\bnot\s+(?:(?:the|a|my|any)\s+)?(\w+)", re.IGNORECASE)
_FOLLOW_ANCHORS = {
    "and", "also", "then", "ok", "okay", "thanks", "thank", "it", "that", "this",
    "them", "those", "again", "more", "another", "same", "tomorrow", "today",
    "tonight", "yesterday", "next", "instead", "please",
}
_FOLLOW_PHRASES = re.compile(r"\b(?:what|how) about\b", re.IGNORECASE)
_TOPIC_CHANGE = re.compile(
    r"\b(?:something else|different (?:topic|subject)|change (?:the )?subject|new topic|"
    r"another topic|unrelated|never ?mind)\b",
    re.IGNORECASE,
)
_FOLLOW_MAX_TOKENS = 8


def stem(word: str) -> str:
    """Light, symmetric stemmer (applied to intents, aliases and prompt tokens)."""
    w = word.lower().replace("'", "")
    for suffix, repl in (("ies", "y"), ("ing", ""), ("ed", ""), ("s", "")):
        if len(w) > len(suffix) + 2 and w.endswith(suffix) and not w.endswith("ss"):
            w = w[: -len(suffix)] + repl
            break
    if len(w) > 4 and w.endswith("e"):  # >4 keeps "note"/"notes" from collapsing to the word "not"
        w = w[:-1]
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "sl":
        w = w[:-1]
    return w


def _gram(phrase: str) -> tuple[str, ...]:
    return tuple(stem(w) for w in _TOKEN.findall(phrase.lower()))


def _strip_meta(text: str) -> tuple[str, list[str]]:
    """Remove meta/injected routing text; return what was ignored so provenance stays auditable."""
    ignored = [m.group(0).strip() for m in _META.finditer(text)]
    return _META.sub(" ", text), ignored


def _words(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def cue_table(personas: Mapping[str, Any]) -> list[tuple[str, dict[tuple[str, ...], tuple[float, str]]]]:
    """Per persona (manifest order): stemmed gram -> (weight, LITERAL label). Intents outrank aliases."""
    table: list[tuple[str, dict[tuple[str, ...], tuple[float, str]]]] = []
    for pid, persona in personas.items():
        routing = persona.get("routing", {}) if isinstance(persona, Mapping) else {}
        routing = routing if isinstance(routing, Mapping) else {}
        cues: dict[tuple[str, ...], tuple[float, str]] = {}
        for word in _words(routing.get("aliases")):
            if _gram(word):
                cues[_gram(word)] = (ALIAS_WEIGHT, word)
        for intent in _words(routing.get("intents")):
            if intent != "default" and _gram(intent):
                cues[_gram(intent)] = (1.0, intent)  # contract intents (incl. phrases) outrank aliases
        table.append((str(pid), cues))
    return table


def _clauses(text: str) -> list[str]:
    return [c for c in (part.strip() for part in _CLAUSE_SPLIT.split(text.lower())) if c]


def _negated_stems(clause: str) -> set[str]:
    negated: set[str] = set()
    match = _NEG_CLAUSE.search(clause)
    if match:
        negated.update(stem(t) for t in _TOKEN.findall(clause[match.end():]))
    for m in _NEG_NEXT.finditer(clause):
        negated.add(stem(m.group(1)))
    return negated


def resolve_lead(
    prompt: str,
    personas: Mapping[str, Any] | None,
    prior_lead: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return ``(persona_id, provenance)`` under routing contract v0.2."""
    text = str(prompt or "")
    base = {"method": METHOD, "algorithm": ALGORITHM}
    if RESERVED.search(text):
        return FALLBACK, {**base, "selected": FALLBACK, "reasons": ["reserved:aoteru"]}

    personas = personas if isinstance(personas, Mapping) else {}
    cleaned, ignored_meta = _strip_meta(text)
    table = cue_table(personas)
    scores: dict[str, float] = {pid: 0.0 for pid, _ in table}
    reasons: dict[str, list[str]] = {pid: [] for pid, _ in table}
    negated_seen: list[str] = []

    for clause in _clauses(cleaned):
        stems = [stem(t) for t in _TOKEN.findall(clause)]
        negated = _negated_stems(clause)
        covered: set[int] = set()
        for _, cues in table:
            for gram in cues:
                for i in range(len(stems) - len(gram) + 1):
                    if tuple(stems[i:i + len(gram)]) == gram:
                        covered.update(range(i, i + len(gram)))
        bare_list = len(stems) >= 3 and len(covered) == len(stems)
        for pid, cues in table:
            seen: set[tuple[str, ...]] = set()
            clause_total = 0.0
            for gram, (base_weight, label) in cues.items():
                for i in range(len(stems) - len(gram) + 1):
                    if tuple(stems[i:i + len(gram)]) != gram or gram in seen:
                        continue
                    seen.add(gram)
                    if any(g in negated for g in gram):
                        negated_seen.append(label)
                        continue
                    add = base_weight * (BARE_LIST_WEIGHT if bare_list else 1.0)
                    if bare_list:
                        add = max(0.0, min(add, BARE_LIST_CAP - clause_total))
                    clause_total += add
                    scores[pid] += add
                    reasons[pid].append(label)

    extras = {"negated": sorted(set(negated_seen)), "ignored_meta": ignored_meta}
    best_id, best_score = FALLBACK, 0.0
    for pid, _ in table:
        if scores[pid] > best_score:  # strict: manifest order breaks ties
            best_id, best_score = pid, scores[pid]
    if best_score > 0:
        return best_id, {**base, "selected": best_id, "reasons": reasons[best_id], **extras}

    tokens = _TOKEN.findall(text.lower())
    anchored = bool(_FOLLOW_PHRASES.search(text)) or any(t in _FOLLOW_ANCHORS for t in tokens)
    if (
        prior_lead and prior_lead != FALLBACK and prior_lead in scores and anchored
        and len(tokens) <= _FOLLOW_MAX_TOKENS and not _TOPIC_CHANGE.search(text)
    ):
        return prior_lead, {**base, "selected": prior_lead, "reasons": [f"carry:{prior_lead}"], **extras}
    return FALLBACK, {**base, "selected": FALLBACK, "reasons": ["fallback:aoteru"], **extras}

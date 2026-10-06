"""PROPOSAL ONLY - candidate lead-persona routing algorithms for application -09.

Nothing in the runtime imports this module. ``src/misumi_persona_routing.py``
remains the only router wired into ``/misumi/respond`` and it implements the
ratified Aoteru routing contract v0.1. A candidate here may only be *measured*
against the labelled corpus (``evals/misumi-routing``). Activating any of them
changes the mapping the contract ratifies, so it requires an explicit contract
amendment ratified by the user (see ``automation/review/misumi-routing-v0.2-amendment-proposal.md``).

Candidate ``routing-candidate-v0.2-proposal`` is deterministic, stdlib-only,
makes no model calls and keeps every v0.1 invariant:

* reserved matters (standards, values, boundaries, ratification, Level 5/6)
  route to Aoteru before anything else, exactly as in v0.1;
* contract intents are matched first-class; inflected forms are matched via a
  light, symmetric stemmer (``cleaned`` -> ``cleaning``);
* an *alias lexicon* (household vocabulary inferred from, but not part of, the
  ratified intents) contributes at a lower weight than a contract intent;
* a cue inside a negated/withdrawn span ("don't need ...", "not the ...",
  "never mind the ...") contributes nothing;
* bare keyword lists and bracketed/meta routing instructions are treated as
  weak or non-evidence (keyword-injection hardening);
* a short anaphoric follow-up with no cue of its own may inherit the previous
  lead persona, unless it explicitly changes topic;
* manifest order is still the deterministic tie-break.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from src.misumi_persona_routing import RESERVED

METHOD = "routing-candidate-v0.2-proposal"
FALLBACK = "aoteru"
ALIAS_WEIGHT = 0.75
BARE_LIST_WEIGHT = 0.2
BARE_LIST_CAP = 0.5  # a stuffed keyword list in total can never outvote ONE real cue (aliases are 0.75)

# Household vocabulary beyond the ratified intents (live manifest, 2026-10-06: several everyday words an earlier,
# drifted reference table had as intents - budget, bills, garden, chores, leftovers, deadline, blocked, growth -
# are not production intents, so they are restored here as lower-weight aliases). Deliberately general
# (not derived item-by-item from the corpus) and lower weight than intents.
# Generic verbs ("plan", "charge") and nouns ("document") are excluded: they hijack the
# domain noun that should lead ("plan meals" must not route on "plan" - corpus item c05).
ALIASES: dict[str, list[str]] = {
    "lelouch": ["procedure", "checklist", "runbook", "pipeline", "sop"],
    "kurisu": ["notes", "minutes", "remember", "conversation", "saved"],
    "misato": ["bin", "bins", "dishes", "dishwasher", "laundry", "tidy", "mess",
               "hoover", "vacuum", "mop", "washing", "housework", "chores"],
    "jin": ["vinyl", "album", "albums", "song", "songs", "stereo", "playlist",
            "band", "gig", "turntable"],
    "erwin": ["roadmap", "prioritise", "prioritize", "goals", "tradeoff", "quarter"],
    "l": ["spending", "charged", "payment", "invoice", "invoices", "bank",
          "money", "cost", "expense", "expenses", "subscription", "overspend", "billing", "budget", "bills"],
    "ginko": ["plant", "water", "herbs", "tomatoes", "seedlings", "leaves", "compost",
              "soil", "greenhouse", "weeds", "windowsill", "garden"],
    "sanji": ["dinner", "lunch", "breakfast", "cook", "cooking", "fridge", "groceries",
              "milk", "meal", "recipe", "shop", "supper", "pantry", "ingredients", "leftovers"],
    "ichigo": ["stuck", "wedged", "asap", "overdue", "emergency", "deadline", "blocked"],
    "giorno": ["experiment", "evolve", "trial", "growth"],
}

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


def _strip_meta(text: str) -> tuple[str, list[str]]:
    """Remove meta/injected routing text; return what was ignored so provenance stays auditable."""
    ignored = [m.group(0).strip() for m in _META.finditer(text)]
    return _META.sub(" ", text), ignored


def _gram(phrase: str) -> tuple[str, ...]:
    return tuple(stem(w) for w in _TOKEN.findall(phrase.lower()))


def _cue_table(personas: Mapping[str, Any]) -> list[tuple[str, dict[tuple[str, ...], float]]]:
    table: list[tuple[str, dict[tuple[str, ...], float]]] = []
    for pid, persona in personas.items():
        routing = persona.get("routing", {}) if isinstance(persona, dict) else {}
        intents = routing.get("intents", []) if isinstance(routing, dict) else []
        cues: dict[tuple[str, ...], float] = {}
        for word in ALIASES.get(str(pid), []):
            cues[_gram(word)] = ALIAS_WEIGHT
        for intent in intents:
            if isinstance(intent, str) and intent != "default" and _gram(intent):
                cues[_gram(intent)] = 1.0  # contract intents (incl. multi-word phrases) outrank aliases
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


def resolve_candidate_lead(
    prompt: str,
    personas: Mapping[str, Any],
    prior_lead: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return ``(persona_id, provenance)`` under the v0.2 candidate algorithm."""
    text = str(prompt or "")
    if RESERVED.search(text):
        return FALLBACK, {"method": METHOD, "selected": FALLBACK, "reasons": ["reserved:aoteru"]}

    cleaned, ignored_meta = _strip_meta(text)
    table = _cue_table(personas)
    clauses = _clauses(cleaned)
    scores: dict[str, float] = {pid: 0.0 for pid, _ in table}
    reasons: dict[str, list[str]] = {pid: [] for pid, _ in table}
    negated_seen: list[str] = []

    for clause in clauses:
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
            for gram, base in cues.items():
                for i in range(len(stems) - len(gram) + 1):
                    if tuple(stems[i:i + len(gram)]) != gram or gram in seen:
                        continue
                    seen.add(gram)
                    label = " ".join(gram)
                    if any(g in negated for g in gram):
                        negated_seen.append(label)
                        continue
                    add = base * (BARE_LIST_WEIGHT if bare_list else 1.0)
                    if bare_list:
                        add = max(0.0, min(add, BARE_LIST_CAP - clause_total))
                    clause_total += add
                    scores[pid] += add
                    reasons[pid].append(label)

    best_id, best_score = FALLBACK, 0.0
    for pid, _ in table:
        if scores[pid] > best_score:  # strict: manifest order breaks ties
            best_id, best_score = pid, scores[pid]

    if best_score > 0:
        return best_id, {
            "method": METHOD, "selected": best_id, "reasons": reasons[best_id],
            "negated": sorted(set(negated_seen)), "ignored_meta": ignored_meta,
        }

    tokens = _TOKEN.findall(text.lower())
    anchored = bool(_FOLLOW_PHRASES.search(text)) or any(t in _FOLLOW_ANCHORS for t in tokens)
    if (
        prior_lead and prior_lead != FALLBACK and anchored
        and len(tokens) <= _FOLLOW_MAX_TOKENS and not _TOPIC_CHANGE.search(text)
    ):
        return prior_lead, {
            "method": METHOD, "selected": prior_lead, "reasons": [f"carry:{prior_lead}"],
            "negated": sorted(set(negated_seen)), "ignored_meta": ignored_meta,
        }
    return FALLBACK, {
        "method": METHOD, "selected": FALLBACK,
        "reasons": ["fallback:aoteru"], "negated": sorted(set(negated_seen)),
        "ignored_meta": ignored_meta,
    }

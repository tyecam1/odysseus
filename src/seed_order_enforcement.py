"""Seed Order output discipline for the Misumi interactive reply (raw-note preservation and candidate labelling).

Why this exists: the corrected live fixtures (Misumi ``fixtures/seed-order/live-verification.yaml``) showed that the household
model paraphrases a pasted raw note without quoting it or labelling its interpretation (0 of 3), and states recurring-problem
findings without a ``candidate_pattern`` / ``candidate_mechanism`` label (0 of 3). The Seed Order text reaches the model only as
bounded excerpts, so the rules are (1) restated as a short block next to the user turn and (2) enforced deterministically here
when the model still does not comply.

Scope is deliberately narrow and conservative. Enforcement only fires when the user's message clearly supplies a raw note or asks
for a recurring-problem scan; every other reply is returned untouched. It never invents content: it quotes the user's own span
verbatim and applies the weakest applicable status label (``inferred`` / ``candidate_pattern``), never ``ratified``.
"""

from __future__ import annotations

import re

SEED_OUTPUT_RULES = (
    "Seed Order output rules: "
    "(1) If the user gives you a raw note, quote it back verbatim, character for character, labelled raw, before any "
    "interpretation, and label every interpretation inferred or proposed. "
    "(2) If the user asks you to scan for recurring problems or patterns, state each finding as candidate_pattern or "
    "candidate_mechanism, derived from the observations given, and never as ratified or settled. "
    "(3) Never present a candidate or a proposal as ratified."
)

_MAX_SPAN = 2000
_MIN_SPAN = 15

# "... raw note: "<text>"" with straight or curly quotes, the quoted text running to the closing quote at the end.
_QUOTED_RAW = re.compile(
    r"\b(?:raw|messy|rough|scribbled|unedited)\s+(?:notes?|capture|text|jottings?)\b[^\"“‘\n]{0,24}"
    r"[\"“](?P<span>.+)[\"”]\s*[.!]?\s*$",
    re.IGNORECASE | re.DOTALL,
)
# "raw note: <text to the end>" without quotes.
_UNQUOTED_RAW = re.compile(r"\braw\s+(?:notes?|capture)\s*:\s*(?P<span>[^\"“].+)$", re.IGNORECASE | re.DOTALL)

_PATTERN_SCAN = re.compile(
    r"\b(?:scan|look|check|search|find|identify|detect|spot|review)\b[^.?!\n]{0,60}\b(?:recurring|repeated|repeating|patterns?)\b",
    re.IGNORECASE,
)
_INTERPRETATION_LABEL = re.compile(r"\b(?:inferred|proposed)\b", re.IGNORECASE)
_CANDIDATE_LABEL = re.compile(r"candidate[_ -](?:pattern|mechanism)", re.IGNORECASE)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def raw_span(prompt: str) -> str | None:
    """The raw note the user supplied, or None when the message does not clearly contain one."""
    for pattern in (_QUOTED_RAW, _UNQUOTED_RAW):
        match = pattern.search(prompt or "")
        if match:
            span = match.group("span").strip()
            if _MIN_SPAN <= len(span) <= _MAX_SPAN:
                return span
    return None


def wants_pattern_scan(prompt: str) -> bool:
    return bool(_PATTERN_SCAN.search(prompt or ""))


def enforce_seed_order(prompt: str, answer: str) -> tuple[str, list[str]]:
    """Return ``(answer, actions)`` with the Seed Order output rules applied. ``actions`` names what was added (empty when the
    model already complied or the rules do not apply)."""
    actions: list[str] = []
    text = answer or ""

    span = raw_span(prompt)
    if span:
        interpretation = text
        if not _INTERPRETATION_LABEL.search(interpretation):
            interpretation = "Inferred (not confirmed): " + interpretation
            actions.append("labelled the interpretation inferred")
        if _squash(span) in _squash(text):
            text = interpretation
        else:
            text = f'Raw note (label: raw, preserved exactly): "{span}"\n\n{interpretation}'
            actions.append("quoted the raw note verbatim")
        return text, actions

    if wants_pattern_scan(prompt) and not _CANDIDATE_LABEL.search(text):
        text = "candidate_pattern (not ratified; derived from the observations given): " + text
        actions.append("labelled the finding candidate_pattern")
    return text, actions

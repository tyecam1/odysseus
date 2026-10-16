"""Bounded persona-state adaptation for the Misumi interface (application -10).

Generalises the proven -07/-08 chain to *bounded persona state*:

    user signal -> evidence -> candidate -> evaluation -> authority
    -> revision -> observable behaviour -> rollback

What may adapt is a CLOSED set of style dimensions per persona (``DIMENSIONS``).
Each value renders to one FIXED sentence from ``RENDER``; no user-supplied text
is ever stored in, or rendered into, a persona prompt. That is the structural
guarantee against unrestricted prompt self-modification: the only thing a
revision can do is select among enumerated, reviewed sentences.

Immutable by construction (never reachable from this module):

- persona identity and role (``persona_record``), the honesty constraints, the
  ratification constraint and the seed-order output rules: the style block is
  APPENDED after them, never interleaved, and its header states it cannot relax
  them;
- routing (that is ``misumi_routing_adaptation``; a separate store);
- memory, competence claims, voices.

Authority model (same as routing; do not weaken):

- durable state changes ONLY by (a) the execute-scoped, principal-recording
  ratification API or (b) a bare "yes" to an offer, from the same owner in the
  same session (``misumi_ratification_dialogue``). Free text is never authority
  by itself: a durable phrase in the user's own instruction ("keep answers
  short from now on") is a ``durable_request`` that makes the candidate
  eligible and OFFERED, never active (round-4 review, 2026-10-15);
- only the part of a turn the user typed as their own instruction counts (the
  first line, before any colon, outside quotes); a turn that asks to process
  third-party text (summarise, proofread, translate, reply, forward ...)
  yields no capture at all (``own_instruction``);
- feedback ("too long") is a ``correction``: shadow-only; three consistent
  corrections across the evidence log make a candidate ``eligible`` awaiting
  operator ratification; confidence never bypasses the gate;
- a one-off request ("shorter please") is a ``temporary_choice``: it shapes
  THAT turn only and never creates durable state;
- reserved matters (standards, values, boundaries, ratification, Level 5/6)
  and any turn the shared fail-safe gate (``src.misumi_safety_gate``) does
  flags are never captured and never shaped by learned style or learned
  routing (round 5: one gate, whole turn scanned); round 6: the gate is a
  precision-first BLOCK and the primary protection is ``STYLE_CARVE_OUT``,
  appended to every learned style block for the model to apply;
- an offerable candidate records its ``origin`` (owner, session, evidence);
  only that owner is offered it and can answer (round 5);
- the store is cross-process safe and fails closed on corruption
  (``src.misumi_state_io``);
- every promotion first passes a deterministic evaluation (enum validity,
  bounded fixed render, foundation intact, no unresolved contradiction).

Not in this increment (carried as -10b, see MISUMI_PROGRAMME.md): knowledge-like
state (project familiarity, domain confidence, collaboration affinity,
recurring-task familiarity). Those are counters about the world, not style
selection, and need their own evidence semantics.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any

from src.misumi_safety_gate import is_reserved_turn as _gate_is_reserved
from src.misumi_safety_gate import safety_matter as _gate_safety_matter
from src.misumi_state_io import StateCorruptError, StateDir  # noqa: F401  (StateCorruptError re-exported for callers)

logger = logging.getLogger(__name__)

DIMENSIONS: dict[str, tuple[str, ...]] = {
    "response_depth": ("brief", "standard", "thorough"),
    "technical_depth": ("plain", "standard", "technical"),
    "structure": ("prose", "bullets", "stepwise"),
    "intervention_style": ("reactive", "suggestive", "proactive"),
}
DEFAULTS: dict[str, str] = {
    "response_depth": "standard",
    "technical_depth": "standard",
    "structure": "prose",
    "intervention_style": "suggestive",
}
# The ONLY text a revision can ever add to a persona prompt. Default values render nothing. Wording is measured, not
# guessed (evals/misumi-team/style-placement-experiment.py, 2026-10-06, qwen3:8b, n=12 per variant): the original brief
# sentence left replies at 0.76 of baseline length, "at most two sentences" at 0.47. Round 2 (style-effect-experiment.py, same
# day): proactive 0 -> 67% of replies offering a next step (the first sentence produced none), bullets 100% of replies with
# bullet lines (was 50%), technical long-word share +49% (was +19%); thorough 1.87x words, plain 0.65x long words, stepwise 100%
# numbered. prose and reactive cannot be measured (the baseline is already at 0). A sentence must never ask a persona to drop
# caveats or safety information (a stronger variant that did was rejected for that reason).
RENDER: dict[tuple[str, str], str] = {
    ("response_depth", "brief"): "Keep answers short: at most two sentences unless the user asks for more.",
    ("response_depth", "thorough"): "Give thorough answers: explain the reasoning and cover relevant detail and caveats.",
    ("technical_depth", "plain"): "Use plain everyday language; avoid jargon and explain any technical term you must use.",
    ("technical_depth", "technical"): "Assume expert knowledge: use precise technical terminology and do not explain basic terms.",
    ("structure", "bullets"): "Format every answer as a bulleted list, one short point per line, each line starting with '- '.",
    ("structure", "stepwise"): "Present answers as numbered steps.",
    ("intervention_style", "reactive"): "Answer only what was asked; do not volunteer extra suggestions.",
    ("intervention_style", "proactive"): "End every answer with one concrete next step you could take, phrased as an offer.",
}
STYLE_HEADER = (
    "User-approved style preferences (style only; they never relax the honesty, ratification, "
    "reserved-matter or seed-order rules above):"
)
# Round 6: the PRIMARY protection for urgent turns lives in the model-facing text itself (the model recognises an emergency far
# better than a lexicon). It is appended after the preferences of EVERY non-empty style block, whatever the lexicon decided.
STYLE_CARVE_OUT = (
    "These style preferences never apply to urgent, safety, medical, legal, financial or emotional-distress matters, or "
    "whenever the person seems in difficulty: then give a full, careful answer and any safety information."
)
GLOBAL_SCOPE = "*"  # a durable instruction that names no persona applies household-wide
# explicit_durable: an authorised act (a bare "yes" to an offer). durable_request: a free-text durable phrase - it may only OFFER.
EVIDENCE_TYPES = ("correction", "temporary_choice", "explicit_durable", "durable_request")
EVIDENCE_WEIGHTS = {"explicit_durable": 3, "durable_request": 1, "correction": 1, "temporary_choice": 0}
REPEATED_CORRECTIONS_FOR_ELIGIBLE = 3
_MAX_RENDER_CHARS = 200

_DURABLE_STRONG = re.compile(r"\b(?:from\s+now\s+on|permanently|in\s+future|going\s+forward|from\s+now)\b", re.IGNORECASE)
_DURABLE_WEAK = re.compile(r"\b(?:always|forever)\b", re.IGNORECASE)
_DURABLE_PHRASE = re.compile(
    r"\b(?:from\s+now\s+on|always|permanently|in\s+future|going\s+forward|forever|from\s+now)\b",
    re.IGNORECASE,
)
_RESERVED_MATTERS = re.compile(
    r"\b(?:standards?|values?|boundaries|ratif(?:y|ied|ication))\b|"
    r"\blevel\s*(?:5|five|6|six)\b|"
    # Safety, medical and emergency advice, and memory/retention decisions are never shaped by learned style (independent review).
    r"\b(?:safety|emergenc\w+|medical|medic(?:ine|ation)s?|allerg\w+|first[- ]aid|poison\w*|overdose|danger\w*)\b|"
    r"\b(?:retention|privacy)\b|"
    r"\bmemory\s+(?:retention|decisions?|policy|capture)\b",
    re.IGNORECASE,
)
_CLAUSE_BOUNDARY = re.compile(r"[.;!?\n]")
# Typographic quotes and apostrophes (phone and kiosk keyboards) are folded to ASCII before any pattern runs. Style SIGNALS are only
# ever read from the user's own head text (the first line), so signal detection inspects a bounded prefix; anything that can only
# WITHHOLD adaptation (the safety gate, data/third-party detection) scans the whole turn (round 5).
_TYPOGRAPHIC = str.maketrans({"’": "'", "‘": "'", "‛": "'", "ʼ": "'", "“": '"', "”": '"', "„": '"'})
_MAX_DETECT_CHARS = 2000


def _prep(prompt: object) -> str:
    return str(prompt or "")[:_MAX_DETECT_CHARS].translate(_TYPOGRAPHIC)


def _full(prompt: object) -> str:
    return str(prompt or "").translate(_TYPOGRAPHIC)


# A sentence that talks ABOUT an instruction (asks how, asks to remove or ignore it, translates it, gives it as an example or for
# someone else) is never the user's own durable instruction.
_NOT_DURABLE_CONTEXT = re.compile(
    r"\b(?:ignore|disregard|remove|stop|undo|cancel|revert|translate|example|how\s+do\s+i|should\s+i|"
    r"tell\s+(?:the|my|your|him|her|them|chatgpt|it)|essay|quote|sentence)\b",
    re.IGNORECASE,
)
_REPORTED_TAIL = re.compile(r"[^.;!?\n]{0,160}\b(?:he|she|they|someone|everyone)\s+(?:said|wrote|says|asked|told\s+me)\b[^.;!?\n]{0,160}", re.IGNORECASE)
_NEGATION = re.compile(
    r"\b(?:don'?t|do\s+not|didn'?t|did\s+not|wasn'?t|was\s+not|isn'?t|is\s+not|aren'?t|are\s+not|weren'?t|were\s+not"
    r"|can'?t|cannot|won'?t|not|never|no\s+longer|nothing|neither|nor)\b",
    re.IGNORECASE,
)
# Text that is quoted, code, markup, a link label or reported speech is a mention of an instruction, not the user's own instruction.
# Unclosed quotes, fences and backticks run to the end of the line (or text), so an attacker cannot escape by not closing them.
_QUOTE_PATTERNS = tuple(re.compile(pattern, flags) for pattern, flags in (
    (r"```[\s\S]*?(?:```|$)", 0),
    (r"`[^`\n]*`", 0),
    (r"`[^\n]*$", re.MULTILINE),
    (r"<(blockquote|q|pre|code)\b[^>]*>[\s\S]*?(?:</\1\s*>|$)", re.IGNORECASE),
    (r"\[[^\]\n]{0,200}\]\([^)\n]{0,300}\)", 0),
    (r"\"[^\"\n]*\"", 0),
    (r"“[^”\n]*”", 0),
    (r"(?<!\w)'[^'\n]+'(?!\w)", 0),
    (r"\"[^\n]*$", re.MULTILINE),
    (r"“[^\n]*$", re.MULTILINE),
    (r"^\s*>.*$", re.MULTILINE),
))
_REPORTED = re.compile(
    r"\b(?:wrote|writes|written|said|says|quotes?|quoted|reads|claims?|claimed|reported|states?|stated|texted|emailed|messaged)\b[^.!?\n]*",
    re.IGNORECASE,
)


def _strip_quoted(text: str) -> str:
    for pattern in _QUOTE_PATTERNS:
        text = pattern.sub(" ", text)
    return _REPORTED.sub(" ", _REPORTED_TAIL.sub(" ", text))


def _clause_before(text: str, position: int) -> str:
    start = max((m.end() for m in _CLAUSE_BOUNDARY.finditer(text, 0, position)), default=0)
    return text[start:position]


def safety_matter(prompt: str, context: Any = ()) -> str | None:
    """The safety domain a turn touches ('gas-co', 'fire-smoke', 'poisoning', ...), or None. Delegates to the ONE shared gate
    (``src.misumi_safety_gate``), which scans the whole turn and any context given - never a prefix."""
    return _gate_safety_matter(prompt, context)


def is_reserved_turn(prompt: str, context: Any = ()) -> bool:
    """True unless the turn is POSITIVELY benign by the shared fail-safe gate (safety lexicons, reserved governance matters,
    near-miss typos, unassessable scripts, over-long text). Learned style is neither captured from nor applied to such a turn;
    learned routing uses the same function (round 5: one gate for both)."""
    return _gate_is_reserved(prompt, context)


# Third-party data (round 4). A turn whose primary intent is to process someone else's text carries that text as DATA, so nothing in
# it - or in the rest of the turn - is the user's own standing instruction. Ambiguous turns err to "data" (no capture, at most a
# one-turn style effect from the user's own head text).
_DATA_TASK = re.compile(
    r"\b(?:summar(?:y|ies|i[sz]\w*)|sum\s+up|proof-?read\w*|spell-?check\w*|grammar|translat\w*|repl(?:y|ies|ying)|respond(?:ing)?\s+to|"
    r"rewrit\w*|re-?word\w*|rephras\w*|paraphras\w*|(?<!going\s)forward(?:s|ed|ing)?(?!\s+(?:on|from)\b)|quot(?:e|ed|es|ing)|draft\w*|polish|critique|analy[sz]\w*|"
    r"(?:edit|correct|fix|check|review|improve|shorten|explain)\s+(?:this|that|the\s+following|my|his|her|their)\b|"
    r"here\s+is|here'?s|the\s+following|below|attached|paste\w*|wrote|writes|sent|says|texted|emailed|messaged|"
    r"(?:this|that|the|my|his|her|their|a)\s+(?:\w+'s\s+)?(?:e-?mails?|letters?|messages?|texts?|notes?|posts?|comments?|documents?|"
    r"paragraphs?|essays?|articles?|reviews?|replies|memos?|minutes|transcripts?))\b",
    re.IGNORECASE,
)
_QUESTION_START = re.compile(
    r"^\W*(?:does|do|did|is|are|was|were|has|have|had|why|how|what|who|whom|whose|when|where|which|should\s+i|shall\s+i)\b",
    re.IGNORECASE,
)


# Third-party text (round 5): a message written by or to someone else, pasted in. "Hi all, from now on keep answers short. Cheers,
# Bob" is Bob's message to a group, not this user's instruction. Markers: a greeting to a group or to a named non-persona person, a
# sign-off with a name, mail/chat headers and forward/signature furniture, or addressing a group. Errs towards "third party".
_GROUP = r"(?:all|everyone|everybody|team|folks|guys|y'?all|both|gang|people|lads|ladies|friends|colleagues|family)"
_THIRD_PARTY = (
    re.compile(r"^\W*(?:hi|hello|hey|hiya|dear|morning|evening|afternoon|good\s+(?:morning|afternoon|evening)|greetings)\b[\s,]+"
               r"(?:" + _GROUP + r")\b", re.IGNORECASE),
    re.compile(r"^\s*(?:-{1,2}|~)\s*[A-Z][a-zA-Z'-]+\s*$", re.MULTILINE),
    re.compile(r"\bsent\s+from\s+my\b|^\s*(?:from|to|subject|cc|bcc|date|sent)\s*:|\b(?:fwd?|re)\s*:|-{2,}\s*original\s+message|"
               r"\bbegin\s+forwarded\b|\bon\s+.{1,80}\bwrote\b|(?<![\w.])@[a-z]\w{1,30}\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"\b(?:everyone|everybody|all\s+of\s+you|you\s+all|y'?all|you\s+guys|team)\b[^.!?\n]{0,40}\b(?:please|should|must|"
               r"need\s+to|from\s+now\s+on|going\s+forward)\b|\b(?:from\s+now\s+on|going\s+forward)\b[^.!?\n]{0,10}\b(?:everyone|everybody|"
               r"all\s+of\s+you|you\s+all|team)\b", re.IGNORECASE),
    # Round 6 (F6): attribution and reported speech ("Mum reckons ...", "she says ..."), hearsay and hedges ("apparently we
    # should ..."), and joke/sarcasm markers ("lol jk") - none of these is the user's own firm standing instruction.
    re.compile(r"\b(?:reckons?|apparently|supposedly|allegedly|according\s+to|i\s+(?:heard|read)|rumou?r(?:s|ed)?|"
               r"(?:he|she|they|mum|mom|mam|dad|my\s+\w+|\w+'s\s+\w+)\s+(?:says|said|thinks|reckons|suggests|suggested|wants\s+"
               r"(?:us|me|you)\s+to|told\s+(?:me|us))|someone\s+(?:said|says|told)|people\s+say|they\s+say|"
               r"maybe|perhaps|we\s+(?:should|could|might|ought\s+to)|might\s+be\s+(?:good|nice|worth|better))\b", re.IGNORECASE),
    re.compile(r"\b(?:lol|lmao|lmfao|rofl|jk|j/k|just\s+(?:kidding|joking)|kidding|joking|haha\w*|hehe\w*|not\s+really)\b|"
               r"(?:^|\s)/s\s*$|[\U0001F602\U0001F923\U0001F61C\U0001F609\U0001F643]", re.IGNORECASE),
)


# A trailing attribution: "... from now on use Jin - Bob" / "... ~Sam".
_TRAILING_NAME = re.compile(r"\s(?:-{1,2}|~|\u2013|\u2014)\s*([A-Z][a-zA-Z'-]+)\.?\s*$")
_GREETING_NAME = re.compile(r"^\W*(?:hi|hello|hey|hiya|dear)\s+([A-Za-z][\w'-]*)\b", re.IGNORECASE)
_SIGN_OFF_NAME = re.compile(
    r"(?:^|[.!?\n,]\s*)(?i:cheers|thanks|thank\s+you|thx|regards|best|best\s+wishes|kind\s+regards|warm\s+regards|many\s+thanks|"
    r"sincerely|yours|love|ta|all\s+the\s+best|speak\s+soon|br|xx+)\s*[,.!-]*\s*([A-Z][a-zA-Z'-]+)\.?\s*(?:x+)?\s*$"
)


def _is_assistant_name(name: str) -> bool:
    name = name.lower()
    if name in {"misumi", "assistant"}:
        return True
    try:
        from src.misumi_policy import DISPLAY_NAMES, load_persona_policy

        known = set(load_persona_policy()) | {str(v).lower() for v in DISPLAY_NAMES.values()}
    except Exception:  # noqa: BLE001 - without the persona list every name is treated as a third party
        known = set()
    return name in known


def is_third_party_text(prompt: str) -> bool:
    """True when the turn looks like someone else's message: a greeting to a group or to a named person who is not one of the
    assistant's personas ("Hi Bob," but not "Hi Misato,"), a sign-off with a name ("Cheers, Bob"), mail/chat headers, forward or
    signature furniture, or addressing a group ("everyone should ..."). Errs towards True."""
    text = _full(prompt)
    if len(text) > _MAX_DETECT_CHARS:
        return True  # too long to judge cheaply: treat as someone else's text (it only withholds capture)
    stripped = text.strip()
    if any(pattern.search(stripped) for pattern in _THIRD_PARTY):
        return True
    for pattern in (_GREETING_NAME, _SIGN_OFF_NAME, _TRAILING_NAME):
        match = pattern.match(stripped) if pattern is _GREETING_NAME else pattern.search(stripped)
        if match and match.group(1).lower() != "there" and not _is_assistant_name(match.group(1)):
            return True
    return False


def own_instruction(prompt: str) -> dict[str, Any]:
    """The part of a turn the user typed as their own instruction, and whether the turn is a data-processing task.

    Own text = the first line, before any colon, with quoted/code/reported spans removed. Everything after a newline or colon is
    treated as possibly third-party content. ``data_task`` is True when the turn (anywhere - the WHOLE turn, after quote removal)
    asks to process someone else's text, or looks like someone else's message (``is_third_party_text``); such a turn yields no
    captured or durable signal. A turn too long to scan is data.
    """
    full = _full(prompt)
    text = _strip_quoted(_prep(prompt))
    own = text.split("\n", 1)[0].split(":", 1)[0]
    # A turn longer than the detection window is treated as DATA (fail-safe): nothing in it can create durable state, so no
    # part of a long paste can be missed by a bounded scan. (The safety gate still scans all of it.)
    data = len(full) > _MAX_DETECT_CHARS or bool(_DATA_TASK.search(text)) or is_third_party_text(prompt)
    return {"text": own, "data_task": data, "partial": own.strip() != text.strip() or len(full) > len(text)}


def _clause_bounds(text: str, index: int) -> tuple[int, int]:
    start = max((m.end() for m in _CLAUSE_BOUNDARY.finditer(text, 0, index)), default=0)
    end = next((m.start() for m in _CLAUSE_BOUNDARY.finditer(text, index)), len(text))
    return start, end


def is_users_own_clause(text: str, start: int, end: int) -> bool:
    """False for a clause that asks something, talks ABOUT an instruction, or is a question by its first word."""
    clause = text[start:end]
    asks = end < len(text) and text[end] == "?"
    return not (asks or _QUESTION_START.match(clause) or _NOT_DURABLE_CONTEXT.search(clause))


def durable_phrase_clause(text: str, require: re.Pattern[str] | None = None) -> tuple[int, int] | None:
    """(start, end) of the first clause of ``text`` (already the user's own text) that carries a non-negated durable phrase, is the
    user's own instruction, and (if given) also matches ``require``; None otherwise."""
    for match in _DURABLE_PHRASE.finditer(text):
        start, end = _clause_bounds(text, match.start())
        if not is_users_own_clause(text, start, end):
            continue
        if _NEGATION.search(text[start:match.start()]):
            continue
        if require is not None and not require.search(text[start:end]):
            continue
        return start, end
    return None


# (dimension, value, kind, pattern). kind: "feedback" (about the previous answer) | "request".
_SIGNALS: tuple[tuple[str, str, str, re.Pattern[str]], ...] = tuple(
    (dim, val, kind, re.compile(pat, re.IGNORECASE))
    for dim, val, kind, pat in (
        ("response_depth", "brief", "feedback", r"\btoo\s+(?:long|wordy|verbose|detailed)\b"),
        ("response_depth", "thorough", "feedback", r"\btoo\s+(?:short|brief|terse|shallow)\b"),
        ("technical_depth", "plain", "feedback", r"\btoo\s+(?:technical|jargon\w*|complicated|complex)\b"),
        ("technical_depth", "technical", "feedback", r"\btoo\s+(?:basic|simple|simplistic|elementary)\b"),
        ("response_depth", "brief", "request",
         r"\b(?:shorter|briefer|more\s+concise|be\s+concise|keep\s+(?:it|answers|replies|responses)\s+(?:short|brief)"
         r"|(?:short|brief)\s+(?:answers|replies|responses)|tl;?dr)\b"),
        ("response_depth", "thorough", "request",
         r"\b(?:more\s+detail(?:ed)?|in[- ]depth|thorough(?:ly)?|go\s+deeper|elaborate|longer\s+answers)\b"),
        ("technical_depth", "plain", "request",
         r"\b(?:plain\s+(?:english|language)|simpler|simple\s+terms|no\s+jargon|eli5)\b"),
        ("technical_depth", "technical", "request",
         r"\b(?:more\s+technical|technical\s+(?:detail|terms)|assume\s+i\s+know)\b"),
        ("structure", "bullets", "request",
         r"(?<!no )(?<!without )\b(?:bullet(?:ed)?(?:\s+points?)?|as\s+a\s+list|in\s+a\s+list)\b"),
        ("structure", "stepwise", "request", r"\b(?:step[- ]by[- ]step|numbered\s+steps|as\s+steps)\b"),
        ("structure", "prose", "request", r"\b(?:in\s+prose|as\s+paragraphs|no\s+bullet(?:\s+points)?|without\s+bullets)\b"),
        ("intervention_style", "proactive", "request",
         r"\b(?:be\s+(?:more\s+)?proactive|suggest\s+(?:next\s+steps|what\s+to\s+do\s+next)"
         r"|tell\s+me\s+what\s+to\s+do\s+next|offer\s+(?:next\s+steps|suggestions))\b"),
        ("intervention_style", "reactive", "request",
         r"\b(?:don'?t\s+volunteer|only\s+(?:answer\s+)?what\s+i\s+ask(?:ed)?|stop\s+suggesting|no\s+(?:extra\s+)?suggestions|just\s+answer)\b"),
    )
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _short(text: object, limit: int = 240) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def render_value(dimension: str, value: str) -> str:
    """The fixed sentence for one dimension value ('' for defaults/unknown)."""
    return RENDER.get((dimension, value), "")


def detect_style_signals(prompt: str) -> list[dict[str, str]]:
    """Closed-vocabulary style signals found in one prompt.

    Reserved matters (including safety/medical/emergency advice and memory
    retention) yield nothing. Quoted, code and quote-block text is ignored. A
    dimension signalled with two different values in the same prompt is
    ambiguous and dropped. A request or feedback that is negated ("don't make
    it shorter", "I wasn't saying it was too long") is not a signal.
    """
    if is_reserved_turn(prompt):
        return []
    # Only the user's own head text (first line, before any colon, outside quotes/code/reported speech) can carry a signal; what
    # follows may be pasted third-party content.
    text = own_instruction(prompt)["text"]
    found: dict[str, list[dict[str, str]]] = {}
    for dimension, value, kind, pattern in _SIGNALS:
        for match in pattern.finditer(text):
            if _NEGATION.search(_clause_before(text, match.start())):
                continue  # negated anywhere earlier in its own clause ("I don't think the answer was too long")
            found.setdefault(dimension, []).append(
                {"dimension": dimension, "value": value, "kind": kind, "matched": match.group(0).lower()}
            )
            break
    signals: list[dict[str, str]] = []
    for dimension, rows in found.items():
        if len({row["value"] for row in rows}) == 1:
            signals.append(rows[0])
    return sorted(signals, key=lambda row: row["dimension"])


def classify_signal(prompt: str, signal: dict[str, str]) -> str:
    """Evidence type for one signal: durable request / feedback correction / one-off request.

    ``explicit_durable`` here means only "the user's own text asks for a standing change"; the route records it as a
    ``durable_request`` (an offer), never as authority. A data-processing turn is never durable.
    """
    if signal.get("kind") == "feedback":
        return "correction"  # "your answers are always too long" describes an answer; it is never a standing instruction
    own = own_instruction(prompt)
    if own["data_task"]:
        return "temporary_choice"
    text = own["text"]
    index = text.lower().find(str(signal.get("matched") or "\0"))
    if index < 0:
        return "temporary_choice"
    # the durable phrase must be in the same sentence as the signal it would make durable
    start, end = _clause_bounds(text, index)
    if not is_users_own_clause(text, start, end):
        return "temporary_choice"
    text = text[start:end]
    request_at = text.lower().find(str(signal.get("matched") or "\0"))
    # "from now on ..." counts anywhere in the sentence; "always"/"forever" only before the request ("always explain ..."), not after it
    if _DURABLE_STRONG.search(text) or _DURABLE_WEAK.search(text[:request_at] if request_at >= 0 else text):
        return "explicit_durable"
    return "correction" if signal["kind"] == "feedback" else "temporary_choice"


def owner_key(owner: object) -> str:
    """One canonical value per principal ('' for an absent or blank owner)."""
    return str(owner).strip() if owner is not None else ""


def evidence_origin(evidence: dict[str, Any], kind: str) -> dict[str, Any]:
    """Who caused a candidate to become offerable: the originating owner, session and evidence (round 5, H1)."""
    return {
        "owner": owner_key(evidence.get("owner")),
        "session_id": str(evidence.get("session_id") or ""),
        "evidence_id": evidence.get("evidence_id"),
        "at": evidence.get("created_at"),
        "at_epoch": evidence.get("created_epoch"),
        "kind": kind,
    }


class PersonaStateStore:
    """File-backed, restart-safe, multi-process-safe store for persona-state evidence, candidates and revisions.

    All I/O goes through :class:`src.misumi_state_io.StateDir`: a cross-process lock around every read-modify-write, atomic
    candidate writes, single-write JSONL appends, and FAIL-CLOSED corruption handling (quarantine + ``StateCorruptError``; a
    damaged file is never read as empty, so a later write can never wipe rejections).
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.evidence_path = self.root / "evidence.jsonl"
        self.candidates_path = self.root / "candidates.json"
        self.revisions_path = self.root / "revisions.jsonl"
        self._io = StateDir(self.root)

    def locked(self):
        """The store's cross-process lock (re-entrant): callers that must check-then-act atomically hold it."""
        return self._io.locked()

    # ---------- evidence ----------

    @staticmethod
    def candidate_key(persona: str, dimension: str) -> str:
        return f"{persona}|{dimension}"

    def record_evidence(self, **fields: Any) -> dict[str, Any]:
        """Append one immutable evidence event and fold it into candidate state (one locked unit across processes)."""
        persona = str(fields.get("persona") or "").strip().lower()
        dimension, value = fields.get("dimension"), fields.get("value")
        if not persona:
            raise ValueError("persona is required")
        if dimension not in DIMENSIONS or value not in DIMENSIONS[dimension]:
            raise ValueError(f"unknown persona-state dimension/value: {dimension!r}/{value!r}")
        if fields.get("type") not in EVIDENCE_TYPES:
            raise ValueError(f"unknown evidence type: {fields.get('type')!r}")
        prompt = str(fields.get("prompt") or "")
        if is_reserved_turn(prompt):
            raise ValueError("reserved matters are never captured by persona state")
        record = {
            "evidence_id": f"ps-ev-{uuid.uuid4().hex[:12]}",
            "created_at": _now(),
            "created_epoch": time.time(),
            "type": fields["type"],
            "persona": persona,
            "dimension": dimension,
            "value": value,
            "signal": _short(fields.get("signal"), 80),
            "context": _short(fields.get("context"), 240),
            "prompt_excerpt": _short(prompt, 240),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "session_id": fields.get("session_id"),
            "owner": fields.get("owner"),
            "runtime": fields.get("runtime", "odysseus-misumi"),
            "source_authority": fields.get("source_authority", "user"),
        }
        with self._io.locked():
            self._io.check_healthy()
            self._load_candidates()  # fail closed BEFORE appending if the candidate file is already damaged
            self._io.append_jsonl(self.evidence_path.name, record)
            candidate = self._update_candidate(record)
        return {"evidence": record, "candidate": candidate}

    def list_evidence(self, persona: str | None = None, dimension: str | None = None) -> list[dict[str, Any]]:
        rows = self._read_jsonl(self.evidence_path)
        return [
            row for row in rows
            if (persona is None or row.get("persona") == persona)
            and (dimension is None or row.get("dimension") == dimension)
        ]

    # ---------- candidates ----------

    def _load_candidates(self) -> dict[str, Any]:
        data = self._io.read_json(self.candidates_path.name)
        if data is None:
            return {"candidates": {}}
        if not isinstance(data.get("candidates", {}), dict):
            raise StateCorruptError("candidates.json has no candidates object")
        return data

    def _save_candidates(self, data: dict[str, Any]) -> None:
        self._io.write_json(self.candidates_path.name, data)

    def _update_candidate(self, evidence: dict[str, Any]) -> dict[str, Any]:
        key = self.candidate_key(evidence["persona"], evidence["dimension"])
        eid, etype, value = evidence["evidence_id"], evidence["type"], evidence["value"]
        from_user = evidence.get("source_authority", "user") == "user"
        with self._io.locked():
            data = self._load_candidates()
            candidates = data.setdefault("candidates", {})
            candidate = candidates.get(key)
            if candidate is None:
                candidate = {
                    "candidate_id": f"psc-{uuid.uuid4().hex[:12]}",
                    "persona": evidence["persona"],
                    "dimension": evidence["dimension"],
                    "proposed_value": value,
                    "supporting_evidence": [],
                    "contradicting_evidence": [],
                    "confidence": {"score": 0, "corrections": 0, "corrections_by_owner": {},
                                   "basis": "count of supporting evidence by type (durable=3, correction=1, temporary=0), minus contradictions; "
                                            "eligibility by repetition counts ONE owner's corrections; never bypasses ratification"},
                    "rationale": "",
                    "created_at": _now(),
                    "updated_at": _now(),
                    "status": "shadow",
                    "awaiting": None,
                    "origin": None,
                }
                candidates[key] = candidate
            status = candidate["status"]
            if etype == "explicit_durable":
                # Strongest tier: supersedes inferred proposals (they stay in the evidence log) and may
                # re-open a candidate the operator rejected, because it is a fresh explicit user act.
                if value != candidate["proposed_value"] and candidate["supporting_evidence"]:
                    candidate.setdefault("superseded_proposals", []).append(
                        {"value": candidate["proposed_value"], "by": eid, "at": _now()}
                    )
                candidate["proposed_value"] = value
                candidate["supporting_evidence"].append(eid)
                candidate["status"] = "eligible"
                candidate["awaiting"] = None
                # Never overwrite a pending authorisation (round 6): the first recorded yes stays the cited one.
                if not candidate.get("promotion_authorised_by"):
                    candidate["promotion_authorised_by"] = eid
                candidate["rationale"] = "explicit durable user instruction directly authorises this value"
                candidate.pop("rejection", None)
            elif etype == "durable_request":
                # A free-text durable phrase is NOT authority: it makes the candidate eligible and offerable - to the user who
                # asked, in the session they asked in (``origin``) - and only their bare "yes" (or the operator API) can promote it.
                candidate["supporting_evidence"].append(eid)
                if not (status == "active" and value == candidate["proposed_value"]):
                    if value != candidate["proposed_value"] and len(candidate["supporting_evidence"]) > 1:
                        candidate.setdefault("superseded_proposals", []).append(
                            {"value": candidate["proposed_value"], "by": eid, "at": _now()}
                        )
                    candidate["proposed_value"] = value
                    candidate["status"] = "eligible"
                    candidate["awaiting"] = "user-ratification"
                    candidate["requested_by"] = eid
                    candidate["origin"] = evidence_origin(evidence, "request") if from_user else None
                    candidate["rationale"] = "the user asked for this from now on; it needs their yes to an offer (or operator ratification)"
                    candidate.pop("promotion_authorised_by", None)
                    candidate.pop("rejection", None)
            elif value != candidate["proposed_value"] and candidate["supporting_evidence"]:
                candidate["contradicting_evidence"].append(eid)
                if status not in ("active", "rejected"):
                    candidate["status"] = "shadow"
                    candidate["awaiting"] = "contradicting-evidence"
                    candidate["origin"] = None
            else:
                candidate["supporting_evidence"].append(eid)
                by_owner = candidate["confidence"].setdefault("corrections_by_owner", {})
                who = owner_key(evidence.get("owner"))
                if etype == "correction":
                    candidate["confidence"]["corrections"] = candidate["confidence"].get("corrections", 0) + 1
                    by_owner[who] = int(by_owner.get(who, 0)) + 1
                if (
                    etype == "correction" and from_user
                    and status not in ("active", "rejected")
                    and by_owner.get(who, 0) >= REPEATED_CORRECTIONS_FOR_ELIGIBLE
                    and not candidate["contradicting_evidence"]
                ):
                    # Eligible by ONE owner's repeated corrections; the offer belongs to that owner (round 5, H1).
                    candidate["status"] = "eligible"
                    candidate["awaiting"] = "user-ratification"
                    candidate["origin"] = evidence_origin(evidence, "corrections")
                candidate["rationale"] = (
                    f"{candidate['confidence'].get('corrections', 0)} consistent correction(s) toward this value"
                )
            weights = {row["evidence_id"]: EVIDENCE_WEIGHTS.get(row.get("type"), 0)
                       for row in self._read_jsonl(self.evidence_path)}
            candidate["confidence"]["score"] = sum(
                weights.get(e, 0) for e in candidate["supporting_evidence"]
            ) - len(candidate["contradicting_evidence"])
            candidate["updated_at"] = _now()
            self._save_candidates(data)
            return candidate

    def all_candidates(self) -> dict[str, dict[str, Any]]:
        return self._load_candidates().get("candidates", {})

    def get_candidate(self, persona: str, dimension: str) -> dict[str, Any] | None:
        return self.all_candidates().get(self.candidate_key(persona, dimension))

    def get_candidate_by_id(self, candidate_id: str) -> dict[str, Any] | None:
        return next((c for c in self.all_candidates().values()
                     if isinstance(c, dict) and c.get("candidate_id") == candidate_id), None)

    def reject(self, candidate_id: str, reason: str) -> dict[str, Any]:
        """Reject a shadow/eligible candidate (terminal for inferred evidence). Active -> rollback."""
        with self._io.locked():
            data = self._load_candidates()
            candidate = next((c for c in data.get("candidates", {}).values()
                              if isinstance(c, dict) and c.get("candidate_id") == candidate_id), None)
            if candidate is None:
                raise KeyError(f"unknown candidate: {candidate_id}")
            if candidate.get("status") == "rejected":
                raise ValueError("candidate is already rejected (terminal)")
            if candidate.get("status") == "active":
                raise ValueError("an active candidate is reverted by rollback, not rejection")
            candidate["status"] = "rejected"
            candidate["awaiting"] = None
            candidate["rejection"] = {"reason": _short(reason, 240), "at": _now()}
            candidate["updated_at"] = _now()
            self._save_candidates(data)
            return candidate

    # ---------- evaluation ----------

    @staticmethod
    def evaluate_values(persona: str, dimension: str, value: str, foundation: str = "FOUNDATION") -> dict[str, Any]:
        """Deterministic pre-promotion checks for one proposed (dimension, value)."""
        rendered = render_value(dimension, value)
        composed = compose_system(foundation, {dimension: value})
        checks = [
            {"name": "enum_valid", "ok": dimension in DIMENSIONS and value in DIMENSIONS.get(dimension, ())},
            {"name": "render_from_fixed_table", "ok": rendered == RENDER.get((dimension, value), "")},
            {"name": "render_bounded", "ok": len(rendered) <= _MAX_RENDER_CHARS},
            {"name": "foundation_intact", "ok": composed.startswith(foundation)},
            {"name": "no_reserved_text", "ok": not _RESERVED_MATTERS.search(rendered)},
        ]
        return {"passed": all(item["ok"] for item in checks), "checks": checks, "at": _now()}

    def evaluate_candidate(self, candidate_id: str, foundation: str = "FOUNDATION") -> dict[str, Any]:
        with self._io.locked():
            data = self._load_candidates()
            candidate = next((c for c in data.get("candidates", {}).values()
                              if isinstance(c, dict) and c.get("candidate_id") == candidate_id), None)
            if candidate is None:
                raise KeyError(f"unknown candidate: {candidate_id}")
            result = self.evaluate_values(
                candidate["persona"], candidate["dimension"], candidate["proposed_value"], foundation
            )
            result["checks"].append({
                "name": "no_unresolved_contradiction",
                "ok": candidate.get("awaiting") != "contradicting-evidence",
            })
            result["passed"] = all(item["ok"] for item in result["checks"])
            candidate["evaluation"] = result
            candidate["updated_at"] = _now()
            self._save_candidates(data)
            return result

    # ---------- revisions ----------

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        """All records of one of this store's logs. A damaged log raises StateCorruptError (fail closed), never []."""
        return self._io.read_jsonl(Path(path).name)

    def all_revisions(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.revisions_path)

    def _effective_active(self) -> list[dict[str, Any]]:
        revisions = self.all_revisions()
        rolled_back = {row["rolls_back"] for row in revisions if row.get("rolls_back")}
        return [row for row in revisions
                if row.get("status") == "active" and row.get("revision_id") not in rolled_back]

    def active_revision(self, persona: str, dimension: str) -> dict[str, Any] | None:
        rows = [row for row in self._effective_active()
                if row.get("persona") == persona and row.get("dimension") == dimension]
        return rows[-1] if rows else None

    def active_revisions(self) -> list[dict[str, Any]]:
        """Newest effective revision per (persona, dimension)."""
        latest: dict[str, dict[str, Any]] = {}
        for row in self._effective_active():
            latest[self.candidate_key(str(row.get("persona")), str(row.get("dimension")))] = row
        return list(latest.values())

    def active_state(self, persona: str) -> dict[str, dict[str, Any]]:
        return {row["dimension"]: row for row in self.active_revisions() if row.get("persona") == persona}

    def promote(self, candidate_id: str, *, authorisation: dict[str, Any],
                foundation: str = "FOUNDATION", precondition: Any = None) -> dict[str, Any]:
        """Activate a candidate as a revision - evaluated, gate-checked, authorised.

        ``precondition`` (optional) is called with the candidate while the store lock is held; a falsy result refuses the promotion,
        so a check made earlier cannot go stale between the check and the promotion.
        """
        with self._io.locked():
            evaluation = self.evaluate_candidate(candidate_id, foundation)
            data = self._load_candidates()
            candidate = next((c for c in data.get("candidates", {}).values()
                              if isinstance(c, dict) and c.get("candidate_id") == candidate_id), None)
            if candidate is None:
                raise KeyError(f"unknown candidate: {candidate_id}")
            if candidate.get("status") != "eligible":
                raise ValueError(f"candidate {candidate_id} is {candidate.get('status')!r}, not eligible")
            if precondition is not None and not precondition(candidate):
                raise ValueError(f"candidate {candidate_id} changed since it was offered")
            if not authorisation or not authorisation.get("type"):
                raise ValueError("promotion requires explicit authorisation")
            if authorisation["type"] == "user_instruction":
                if authorisation.get("evidence_id") not in candidate.get("supporting_evidence", []):
                    raise ValueError("user_instruction authorisation must cite supporting evidence")
                cited = next((row for row in self._read_jsonl(self.evidence_path)
                              if row.get("evidence_id") == authorisation.get("evidence_id")), {})
                if cited.get("type") != "explicit_durable":
                    # Only an explicit act (a bare "yes" to an offer) is user authority; a free-text request or a correction is not.
                    raise ValueError("user_instruction authorisation must cite explicit_durable evidence (a yes to an offer)")
            elif authorisation["type"] == "operator_ratification":
                if not authorisation.get("principal"):
                    raise ValueError("operator_ratification requires the ratifying principal")
            else:
                raise ValueError(f"authorisation type not supported: {authorisation['type']!r}")
            if not evaluation["passed"]:
                raise ValueError("candidate failed evaluation: " + ", ".join(
                    c["name"] for c in evaluation["checks"] if not c["ok"]))
            previous = self.active_revision(candidate["persona"], candidate["dimension"])
            revision = {
                "revision_id": f"psr-{uuid.uuid4().hex[:12]}",
                "persona": candidate["persona"],
                "dimension": candidate["dimension"],
                "value": candidate["proposed_value"],
                "previous_revision_id": previous["revision_id"] if previous else None,
                "candidate_id": candidate_id,
                "evidence_ids": list(candidate.get("supporting_evidence", [])),
                "authorisation": authorisation,
                "evaluation": evaluation,
                "created_at": _now(),
                "status": "active",
            }
            candidate["status"] = "active"
            candidate["awaiting"] = None
            candidate["updated_at"] = _now()
            self._io.append_jsonl(self.revisions_path.name, revision)  # the log first: a crash leaves the revision, not a lie
            self._save_candidates(data)
            return revision

    def rollback_revision(self, revision_id: str, reason: str) -> dict[str, Any]:
        """Deactivate one revision by recording its rollback. Nothing is deleted."""
        with self._io.locked():
            revisions = self.all_revisions()
            target = next((row for row in revisions if row.get("revision_id") == revision_id), None)
            if target is None:
                raise KeyError(f"unknown revision: {revision_id}")
            if target.get("status") != "active":
                raise ValueError(f"revision {revision_id} is {target.get('status')!r}, not active")
            if revision_id in {row.get("rolls_back") for row in revisions}:
                raise ValueError(f"revision {revision_id} is already rolled back")
            rollback = {
                "revision_id": f"psr-{uuid.uuid4().hex[:12]}",
                "persona": target["persona"],
                "dimension": target["dimension"],
                "value": target["value"],
                "previous_revision_id": target.get("previous_revision_id"),
                "candidate_id": target.get("candidate_id"),
                "evidence_ids": list(target.get("evidence_ids", [])),
                "authorisation": {"type": "rollback", "reason": _short(reason, 240)},
                "created_at": _now(),
                "status": "rolled_back",
                "rolls_back": revision_id,
            }
            data = self._load_candidates()
            self._io.append_jsonl(self.revisions_path.name, rollback)
            candidate = data.get("candidates", {}).get(self.candidate_key(target["persona"], target["dimension"]))
            if candidate is not None and candidate.get("status") == "active" \
                    and self.active_revision(target["persona"], target["dimension"]) is None:
                candidate["status"] = "shadow"
                candidate["awaiting"] = "rolled-back"
                candidate["origin"] = None
                candidate.pop("promotion_authorised_by", None)
                candidate["updated_at"] = _now()
                self._save_candidates(data)
            return rollback

    # ---------- application ----------

    def resolve_state(self, persona: str, turn_signals: list[dict[str, str]] | None = None) -> dict[str, Any]:
        """The effective style for ONE turn: household-wide revisions, then the persona's own, then this turn's request.

        A turn request (feedback or request signal in the current prompt) shapes only this turn.
        """
        values: dict[str, str] = {}
        provenance: list[dict[str, Any]] = []
        # Household-wide revisions (scope "*") first; the persona's own revisions override them.
        for scope in (GLOBAL_SCOPE, persona):
            for dimension, revision in sorted(self.active_state(scope).items()):
                values[dimension] = revision["value"]
                provenance = [p for p in provenance if p["dimension"] != dimension]
                provenance.append({"dimension": dimension, "value": revision["value"], "source": "revision",
                                   "scope": scope, "revision_id": revision["revision_id"]})
        for signal in turn_signals or []:
            values[signal["dimension"]] = signal["value"]
            provenance = [p for p in provenance if p["dimension"] != signal["dimension"]]
            provenance.append({"dimension": signal["dimension"], "value": signal["value"],
                               "source": "turn_request", "matched": signal["matched"]})
        return {"values": values, "provenance": sorted(provenance, key=lambda p: p["dimension"])}


def style_block(values: dict[str, str]) -> str:
    """The fixed style block for these dimension values ('' when everything is default)."""
    lines = [render_value(dim, values[dim]) for dim in DIMENSIONS if dim in values]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    return STYLE_HEADER + "\n" + "\n".join(f"- {line}" for line in lines) + "\n" + STYLE_CARVE_OUT


def compose_system(foundation: str, values: dict[str, str]) -> str:
    """Foundation text first, byte-for-byte untouched; the style block is only ever appended."""
    block = style_block(values)
    return foundation if not block else f"{foundation}\n\n{block}"

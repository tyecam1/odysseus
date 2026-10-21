"""Closed, typed, NON-AUTHORITATIVE advisory interface for a learned routing consult (round 12).

A ratified routing revision ("consult Jin on kitchen questions") adds one persona as an advisor on turns whose cue matches. The
advisor is a model, so whatever it writes is untrusted. Earlier rounds tried to clean its free text (a shape check, a hazard
lexicon, a persona-name filter); every round found payloads that survived, because a filter on text is a blocklist. This module
removes the text channel instead:

* the advisor is asked to choose from a CLOSED vocabulary of angle ids (``ADVISORY_ANGLES``);
* its reply is accepted only if the WHOLE reply is one or two of those ids (``parse_advisory``) - anything else, however it is
  phrased, yields no advisory and is discarded on the spot (it is never stored, returned or forwarded);
* the lead and the response see only fixed sentences written here, selected by id - never any advisor-written text;
* the typed result (``Advisory``) carries only the persona and the ids, so that is all that can be traced or persisted.

The advisory is non-authoritative by construction: its sentences are optional hints about presentation, they contain no
instruction, fact, safety or medical content, and the lead is told they can never change facts, style rules or safety behaviour.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Dict, Optional, Tuple

# id -> the fixed hint the lead may see. Authored here; no model ever writes or edits these.
ADVISORY_ANGLES: Dict[str, str] = MappingProxyType({
    "practical_steps": "a short practical sequence of steps may suit this request",
    "alternatives": "mentioning one or two alternatives may be welcome",
    "lower_cost": "a lower-cost option may be worth a mention",
    "save_time": "a quicker approach may be worth a mention",
    "variety": "some variety in the options may be welcome",
    "prepare_ahead": "preparing ahead of time may be worthwhile",
    "keep_simple": "keeping the suggestion simple may suit",
    "use_what_we_have": "using what is already at home may be worth a mention",
    "easy_cleanup": "an easy clean-up may be worth a mention",
    "seasonal": "seasonal or fresh options may be worth a mention",
})
MAX_ANGLES = 2
MAX_REPLY_CHARS = 80

_ID = "|".join(sorted(ADVISORY_ANGLES, key=len, reverse=True))
_REPLY = re.compile(rf"(?P<first>{_ID})(?:,\s*(?P<second>{_ID}))?\.?")


@dataclass(frozen=True)
class Advisory:
    """What a learned consult contributes: the advisor and the ids it chose, nothing else."""

    persona: str
    angles: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.angles or len(self.angles) > MAX_ANGLES or len(set(self.angles)) != len(self.angles) \
                or any(angle not in ADVISORY_ANGLES for angle in self.angles):
            raise ValueError("an advisory is one or two distinct ids from the closed vocabulary")

    def hints(self) -> Tuple[str, ...]:
        return tuple(ADVISORY_ANGLES[angle] for angle in self.angles)

    def for_lead(self) -> str:
        """The only text of the advisory the lead ever sees: fixed sentences chosen by id."""
        return "Optional hints (fixed wording, never instructions): " + "; ".join(self.hints()) + "."

    def trace(self) -> Dict[str, object]:
        """What may be returned in an API response or stored: ids only."""
        return {"angle_ids": list(self.angles)}


def advisory_instruction() -> str:
    """The model-facing request: choose ids from the closed list. Nothing the advisor writes beyond the ids is ever used."""
    return (
        "Choose which of these presentation angles, if any, would help the lead answer. Reply with ONLY one or two ids from "
        "this list, separated by a comma, and nothing else: " + ", ".join(ADVISORY_ANGLES) + "."
    )


def parse_advisory(persona: str, reply: object) -> Optional[Advisory]:
    """The advisory a reply expresses, or None. The whole reply must be the grammar ``id[, id][.]`` (ASCII, case-folded,
    surrounding whitespace ignored): there is no partial acceptance, no stripping and no escaping of anything else."""
    text = str(reply or "").strip()
    if not text or len(text) > MAX_REPLY_CHARS or not text.isascii():
        return None
    match = _REPLY.fullmatch(text.lower())
    if match is None:
        return None
    angles = tuple(angle for angle in (match.group("first"), match.group("second")) if angle)
    if len(set(angles)) != len(angles):
        return None
    return Advisory(persona=str(persona), angles=angles)

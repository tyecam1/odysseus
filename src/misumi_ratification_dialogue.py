"""Conversational ratification offers for adaptation candidates (application -08b(d) / -12).

A persona may ASK, in dialogue, whether to make an eligible-by-repetition adaptation permanent; the user's bare
answer is their explicit durable instruction for exactly that one mapping. Governance (do not weaken):

* Only candidates already ``eligible`` and ``awaiting: user-ratification`` are ever offered; shadow, rejected,
  contradicted or reserved-matter candidates are never offered.
* An answer counts ONLY as the entire utterance ("yes", "no", "later", "undo that"). Anything else - including a
  yes embedded in a longer sentence, and retrieved/model text - never ratifies; it simply withdraws the offer.
  Silence and moving on never promote.
* An offer is bounded: one candidate at a time, never re-asked within ``REOFFER_AFTER_S`` (24 h), and a pending offer
  expires after ``PENDING_TTL_S`` (15 min). "later" snoozes; "no" is a terminal rejection of that inference;
  "undo that" rolls back the revision this dialogue just created (reversibility stays one phrase away).
* Wording is fixed templates over closed tables - no model text and no user text is spoken as the offer.
* Capture/answering requires a persisted turn (``persist_turn``); an incognito turn neither offers nor answers.

This module is pure (no I/O, clock injected); the route glue lives in ``routes/misumi_routes.py``.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

PENDING_TTL_S = 15 * 60
REOFFER_AFTER_S = 24 * 3600

_BARE = r"[\s.!,]*(?:please|thanks|thank you)?[\s.!]*$"
AFFIRM = re.compile(
    r"^\s*(?:yes|yep|yeah|yup|sure|ok(?:ay)?|please do|do it|go ahead|make it permanent|keep it|ratify(?: it)?)" + _BARE,
    re.IGNORECASE,
)
DECLINE = re.compile(r"^\s*(?:no|nope|nah|no thanks|no thank you|don'?t|do not|never)" + _BARE, re.IGNORECASE)
LATER = re.compile(r"^\s*(?:later|not now|maybe later|ask me later|not yet)" + _BARE, re.IGNORECASE)
UNDO = re.compile(
    r"^\s*(?:undo that|undo it|revert that|revert it|roll (?:that )?back|take that back)" + _BARE, re.IGNORECASE
)

# Closed phrase table for persona-state candidates (dimension, value) -> what is being made permanent.
PERSONA_STATE_PHRASES: dict[tuple[str, str], str] = {
    ("response_depth", "brief"): "keep answers brief",
    ("response_depth", "thorough"): "give thorough answers",
    ("technical_depth", "plain"): "use plain language",
    ("technical_depth", "technical"): "assume technical fluency",
    ("structure", "bullets"): "answer in bullet points",
    ("structure", "stepwise"): "answer in numbered steps",
    ("structure", "prose"): "answer in prose",
    ("intervention_style", "reactive"): "answer only what is asked",
    ("intervention_style", "proactive"): "offer a next step when useful",
    ("response_depth", "standard"): "use the standard answer length",
    ("technical_depth", "standard"): "use the standard technical level",
    ("intervention_style", "suggestive"): "use the standard level of suggestions",
}


def parse_answer(prompt: str) -> str | None:
    """'affirm' | 'decline' | 'later' | 'undo' for a bare answer; None for anything else."""
    text = str(prompt or "")
    if len(text) > 60:
        return None
    for verdict, pattern in (("undo", UNDO), ("later", LATER), ("affirm", AFFIRM), ("decline", DECLINE)):
        if pattern.match(text):
            return verdict
    return None


def describe_candidate(kind: str, candidate: dict[str, Any], display_name: str | None = None) -> str:
    """Fixed-template description of what a candidate would make permanent."""
    if kind == "persona-state":
        phrase = PERSONA_STATE_PHRASES.get((candidate.get("dimension"), candidate.get("proposed_value")), "")
        scope = candidate.get("persona")
        who = "everyone" if scope == "*" else str(display_name or scope or "this persona")
        return f"{who}: {phrase}" if phrase else ""
    cue = ", ".join(str(c) for c in (candidate.get("cue") or []))
    target = str(display_name or candidate.get("proposed_persona") or "")
    return f"send {cue} questions to {target}" if cue and target else ""


def candidate_digest(candidate: dict[str, Any], kind: str = "", ignore_evidence: Any = ()) -> str:
    """A fingerprint of what an offer put in front of the user: the offer kind, the candidate's identity, proposal and evidence set.

    An affirmation is only applied if the candidate still has the digest it had when it was offered, so a stale or changed candidate
    can never be ratified by an answer given to an earlier offer. ``ignore_evidence`` drops evidence ids from the set (the affirmation
    itself is recorded as evidence before promotion and must not change the digest it is checked against).
    """
    skip = {str(item) for item in ignore_evidence}
    material = {
        key: candidate.get(key)
        for key in ("candidate_id", "status", "persona", "dimension", "proposed_value", "proposed_persona", "base_persona", "cue")
    }
    material["offer_kind"] = kind
    material["evidence"] = sorted(str(item) for item in (candidate.get("supporting_evidence") or []) if str(item) not in skip)
    return hashlib.sha256(json.dumps(material, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]


def build_offer(kind: str, candidate: dict[str, Any], display_name: str | None = None) -> dict[str, Any] | None:
    """The offer for one eligible-awaiting-ratification candidate, or None if it is not offerable."""
    if candidate.get("status") != "eligible" or candidate.get("awaiting") != "user-ratification":
        return None
    summary = describe_candidate(kind, candidate, display_name)
    if not summary:
        return None
    count = int((candidate.get("confidence") or {}).get("corrections") or len(candidate.get("supporting_evidence") or []))
    return {
        "kind": kind,
        "candidate_id": candidate.get("candidate_id"),
        "digest": candidate_digest(candidate, kind),
        "persona": candidate.get("persona") if kind == "persona-state" else candidate.get("proposed_persona"),
        "summary": summary,
        "question": (
            f"By the way, you have steered me this way {count} times: {summary}. "
            "Shall I make that permanent? Say yes, no, or later."
        ),
        "answers": ["yes", "no", "later"],
    }


class OfferBook:
    """In-memory pending offers per session plus cross-session re-offer memory (process-local, by design:
    after a restart an offer may be repeated; a ratification never is lost, it lives in the stores)."""

    def __init__(self, clock=None):
        self._clock = clock or (lambda: time.time())  # late-bound so tests can move time
        self._pending: dict[tuple[str | None, str], dict[str, Any]] = {}
        self._last_offered: dict[str, float] = {}
        self._last_revision: dict[tuple[str | None, str], dict[str, Any]] = {}

    def may_offer(self, candidate_id: str) -> bool:
        last = self._last_offered.get(candidate_id)
        return last is None or self._clock() - last >= REOFFER_AFTER_S

    @staticmethod
    def _key(session_id: str | None, owner: str | None) -> tuple[str | None, str]:
        """Offers and undo pointers belong to (owner, session): another owner's identical session id never reaches them.

        A tuple, not a joined string, so no owner/session pair can collide with another by containing a separator; an absent or
        blank owner is one value (None).
        """
        return ((str(owner) if str(owner).strip() else None) if owner is not None else None, str(session_id or ""))

    def record_offer(self, session_id: str | None, offer: dict[str, Any], owner: str | None = None) -> None:
        self._last_offered[str(offer["candidate_id"])] = self._clock()
        if session_id:
            self._pending[self._key(session_id, owner)] = {"offer": offer, "at": self._clock(), "owner": owner}

    def pending(self, session_id: str | None, owner: str | None = None) -> dict[str, Any] | None:
        key = self._key(session_id, owner)
        row = self._pending.get(key)
        if row and self._clock() - row["at"] <= PENDING_TTL_S:
            return row["offer"]
        if row:
            self._pending.pop(key, None)
        return None

    def clear(self, session_id: str | None, owner: str | None = None) -> None:
        self._pending.pop(self._key(session_id, owner), None)

    def snooze(self, candidate_id: str) -> None:
        self._last_offered[str(candidate_id)] = self._clock()

    def remember_revision(self, session_id: str | None, kind: str, revision_id: str, owner: str | None = None) -> None:
        if session_id:
            self._last_revision[self._key(session_id, owner)] = {
                "kind": kind, "revision_id": revision_id, "at": self._clock(), "owner": owner,
            }

    def last_revision(self, session_id: str | None, owner: str | None = None) -> dict[str, Any] | None:
        row = self._last_revision.get(self._key(session_id, owner))
        if row and self._clock() - row["at"] <= PENDING_TTL_S:
            return row
        return None

    def forget_revision(self, session_id: str | None, owner: str | None = None) -> None:
        self._last_revision.pop(self._key(session_id, owner), None)

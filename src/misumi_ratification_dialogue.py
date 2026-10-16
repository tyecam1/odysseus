"""Conversational ratification offers for adaptation candidates (application -08b(d) / -12, round-5 repair).

A persona may ASK, in dialogue, whether to make an eligible adaptation permanent; the user's bare "yes" is their explicit
durable instruction for exactly that one mapping. Governance (do not weaken):

* Only candidates already ``eligible`` and ``awaiting: user-ratification`` are ever offered; shadow, rejected,
  contradicted or reserved-matter candidates are never offered. Eligibility comes from ONE owner's repeated corrections or
  from that owner's free-text durable request ("from now on ..."): free text is never authority by itself.
* An offer belongs to whoever CAUSED it (round 5): every offerable candidate carries an ``origin`` (owner, session, evidence
  id, time). An offer is shown only to that origin owner (and, for an anonymous owner, only in the origin session), only
  within ``ORIGIN_TTL_S`` of the originating evidence, and only that owner can answer it. A candidate without an origin
  (legacy state, operator-only paths) is never offered in conversation; the operator ratification API still works.
* Offers are PERSISTED (``OfferBook(root=...)``) and re-verified against the candidate store when answered (status,
  digest of what was shown, origin), so a restart or a second worker neither loses an offer nor lets one reach another
  owner; nothing is reconstructed from candidate eligibility alone.
* An answer counts ONLY as the entire utterance: a bare "yes" (optionally "please"/"thanks"); "no"; "later"; "undo that".
  "ok", "sure", "yeah", "go ahead" and anything longer do not ratify (round 5): they simply withdraw the offer.
  Silence and moving on never promote.
* An offer is bounded: one candidate at a time, never re-asked within ``REOFFER_AFTER_S`` (24 h), and a pending offer
  expires after ``PENDING_TTL_S`` (15 min). "later" snoozes; "no" is a terminal rejection of that inference;
  "undo that" rolls back the revision this owner's answer just created (reversibility stays one phrase away).
* Wording is fixed templates over closed tables - no model text and no user text is spoken as the offer.
* Capture/answering requires a persisted turn (``persist_turn``); an incognito turn neither offers nor answers.

The decision helpers are pure (clock injected); the route glue lives in ``routes/misumi_routes.py``.
"""

from __future__ import annotations

import contextlib
from collections import OrderedDict
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Iterator

PENDING_TTL_S = 15 * 60
REOFFER_AFTER_S = 24 * 3600
ORIGIN_TTL_S = 7 * 24 * 3600  # an offer is only ever made to its origin owner within a week of the evidence that caused it
# After a flagged (unsafe) turn, the same (owner, session) gets no learned behaviour and no offers for the next
# SAFETY_LATCH_TURNS turns or SAFETY_LATCH_S seconds, whichever ends first (round 6: short, so a false positive costs little).
SAFETY_LATCH_S = 5 * 60
SAFETY_LATCH_TURNS = 3
SAFETY_LATCH_CAP = 4096  # in-memory, least-recently-latched entries are evicted beyond this (never written to shared state)

_BARE = r"[\s.!,]*(?:please|thanks|thank you)?[\s.!]*$"
AFFIRM = re.compile(r"^\s*yes" + _BARE, re.IGNORECASE)  # round 5: bare yes only ("ok", "sure", "yeah" never ratify)
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


def _owner_value(owner: object) -> str:
    return str(owner).strip() if owner is not None else ""


def origin_allows(candidate: dict[str, Any], owner: str | None, session_id: str | None, now: float | None = None) -> bool:
    """True only when this (owner, session) is the candidate's origin and the origin is still fresh.

    The origin owner must match exactly; an anonymous origin (no owner) additionally requires the origin session, because an
    absent owner cannot tell two people apart. No origin -> never offered or answerable in conversation.
    """
    origin = candidate.get("origin") if isinstance(candidate, dict) else None
    if not isinstance(origin, dict) or not origin.get("evidence_id"):
        return False
    if _owner_value(origin.get("owner")) != _owner_value(owner):
        return False
    if not _owner_value(owner) and str(origin.get("session_id") or "") != str(session_id or ""):
        return False
    at = origin.get("at_epoch")
    if not isinstance(at, (int, float)):
        return False
    return (time.time() if now is None else now) - float(at) <= ORIGIN_TTL_S


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
    """A fingerprint of what an offer put in front of the user: the offer kind, the candidate's identity, proposal, evidence set
    and origin.

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
    origin = candidate.get("origin") if isinstance(candidate.get("origin"), dict) else {}
    material["origin"] = [_owner_value(origin.get("owner")), str(origin.get("session_id") or ""), origin.get("evidence_id")] \
        if origin else None
    return hashlib.sha256(json.dumps(material, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]


def build_offer(kind: str, candidate: dict[str, Any], display_name: str | None = None) -> dict[str, Any] | None:
    """The offer for one eligible-awaiting-ratification candidate, or None if it is not offerable."""
    awaiting = candidate.get("awaiting")
    healing = awaiting is None and bool(candidate.get("promotion_authorised_by"))  # a yes whose promotion never completed
    if candidate.get("status") != "eligible" or not (awaiting == "user-ratification" or healing):
        return None
    summary = describe_candidate(kind, candidate, display_name)
    if not summary:
        return None
    count = int((candidate.get("confidence") or {}).get("corrections") or len(candidate.get("supporting_evidence") or []))
    requested = bool(candidate.get("requested_by")) and candidate.get("requested_by") in (candidate.get("supporting_evidence") or [])[-1:]
    lead = (
        f"You asked for this from now on: {summary}." if requested  # a free-text durable request is only ever an offer
        else f"By the way, you have steered me this way {count} times: {summary}."
    )
    origin = candidate.get("origin") if isinstance(candidate.get("origin"), dict) else {}
    return {
        "kind": kind,
        "candidate_id": candidate.get("candidate_id"),
        "digest": candidate_digest(candidate, kind),
        "origin_evidence_id": origin.get("evidence_id"),
        "persona": candidate.get("persona") if kind == "persona-state" else candidate.get("proposed_persona"),
        "summary": summary,
        "question": f"{lead} Shall I make that permanent? Say yes, no, or later.",
        "answers": ["yes", "no", "later"],
    }


class OfferBook:
    """Pending offers per (owner, session), re-offer memory, undo pointers and safety latches.

    With ``root`` the book is PERSISTED in ``<root>/dialogue-state.json`` through the same cross-process locked, atomic,
    fail-closed store the adaptation stores use, so offers survive restarts and are shared by every worker (round 5). Without
    ``root`` it is in-memory (unit tests and tools). The book is never the authority for a promotion: the route re-verifies every
    answer against the candidate store (status, digest, origin) before acting.
    """

    STATE_FILE = "dialogue-state.json"

    def __init__(self, clock=None, root: str | Path | None = None):
        self._clock = clock or (lambda: time.time())  # late-bound so tests can move time
        self._memory: dict[str, Any] = {"pending": {}, "last_offered": {}, "last_revision": {}}
        self._latch: "OrderedDict[str, dict[str, float]]" = OrderedDict()  # process-local, bounded, TTL-pruned
        self.latch_cap = SAFETY_LATCH_CAP
        self._io = None
        if root is not None:
            from src.misumi_state_io import StateDir

            self._io = StateDir(Path(root))

    @staticmethod
    def _key(session_id: str | None, owner: str | None) -> str:
        """Offers and undo pointers belong to (owner, session): another owner's identical session id never reaches them.

        A JSON pair, not a joined string, so no owner/session pair can collide with another by containing a separator; an absent or
        blank owner is one value.
        """
        return json.dumps([_owner_value(owner) or None, str(session_id or "")])

    @contextlib.contextmanager
    def _state(self, write: bool = False) -> Iterator[dict[str, Any]]:
        if self._io is None:
            yield self._memory
            return
        with self._io.locked():
            data = self._io.read_json(self.STATE_FILE) or {}
            for section in ("pending", "last_offered", "last_revision"):
                if not isinstance(data.get(section), dict):
                    data[section] = {}
            yield data
            if write:
                self._io.write_json(self.STATE_FILE, data)

    def may_offer(self, candidate_id: str) -> bool:
        with self._state() as state:
            last = state["last_offered"].get(str(candidate_id))
        return last is None or self._clock() - float(last) >= REOFFER_AFTER_S

    def record_offer(self, session_id: str | None, offer: dict[str, Any], owner: str | None = None) -> None:
        with self._state(write=True) as state:
            state["last_offered"][str(offer["candidate_id"])] = self._clock()
            if session_id:
                state["pending"][self._key(session_id, owner)] = {
                    "offer": offer, "at": self._clock(), "owner": _owner_value(owner), "session_id": str(session_id),
                }

    def pending(self, session_id: str | None, owner: str | None = None) -> dict[str, Any] | None:
        key = self._key(session_id, owner)
        with self._state() as state:
            row = state["pending"].get(key)
        if row and self._clock() - float(row.get("at") or 0) <= PENDING_TTL_S \
                and row.get("owner", _owner_value(owner)) == _owner_value(owner):
            return row["offer"]
        if row:
            self.clear(session_id, owner)
        return None

    def clear(self, session_id: str | None, owner: str | None = None) -> None:
        key = self._key(session_id, owner)
        with self._state(write=self._io is not None) as state:
            state["pending"].pop(key, None)

    def snooze(self, candidate_id: str) -> None:
        with self._state(write=True) as state:
            state["last_offered"][str(candidate_id)] = self._clock()

    def remember_revision(self, session_id: str | None, kind: str, revision_id: str, owner: str | None = None,
                          offer: dict[str, Any] | None = None, answer: str | None = None) -> None:
        if session_id:
            with self._state(write=True) as state:
                state["last_revision"][self._key(session_id, owner)] = {
                    "kind": kind, "revision_id": revision_id, "at": self._clock(), "owner": _owner_value(owner),
                    "offer": offer, "answer": answer,
                }

    def last_revision(self, session_id: str | None, owner: str | None = None) -> dict[str, Any] | None:
        with self._state() as state:
            row = state["last_revision"].get(self._key(session_id, owner))
        if row and self._clock() - float(row.get("at") or 0) <= PENDING_TTL_S:
            return row
        return None

    def forget_revision(self, session_id: str | None, owner: str | None = None) -> None:
        with self._state(write=self._io is not None) as state:
            state["last_revision"].pop(self._key(session_id, owner), None)

    def check_healthy(self) -> None:
        """Raise ``StateUnavailable`` when the persisted dialogue state is quarantined (callers then withhold learned behaviour)."""
        if self._io is not None:
            self._io.check_healthy()

    # ---------- safety latch (recent-context window for the safety gate; in memory, bounded) ----------

    def _prune_latches(self) -> None:
        now = self._clock()
        while self._latch:
            key, row = next(iter(self._latch.items()))
            if now - row["at"] > SAFETY_LATCH_S:
                self._latch.popitem(last=False)
            else:
                break
        while len(self._latch) > self.latch_cap:
            self._latch.popitem(last=False)

    def latch_safety(self, session_id: str | None, owner: str | None = None) -> None:
        """A flagged turn happened: the next SAFETY_LATCH_TURNS turns of this (owner, session), within SAFETY_LATCH_S, get no
        learned behaviour. Memory only - never shared state - so no caller, whatever its scope, can grow a file with it."""
        if not session_id:
            return
        key = self._key(session_id, owner)
        self._latch.pop(key, None)
        self._latch[key] = {"at": self._clock(), "turns": float(SAFETY_LATCH_TURNS)}
        self._prune_latches()

    def consume_latch(self, session_id: str | None, owner: str | None = None) -> bool:
        """True (and one latched turn used up) when this turn falls inside a latch window."""
        self._prune_latches()
        if not session_id:
            return False
        key = self._key(session_id, owner)
        row = self._latch.get(key)
        if row is None:
            return False
        if self._clock() - row["at"] > SAFETY_LATCH_S or row["turns"] <= 0:
            self._latch.pop(key, None)
            return False
        row["turns"] -= 1
        if row["turns"] <= 0:
            self._latch.pop(key, None)
        return True

    def latch_size(self) -> int:
        return len(self._latch)

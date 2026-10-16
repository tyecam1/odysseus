"""Experience-driven routing adaptation for the Misumi interface (application -07).

Implements the controlled adaptation loop demanded by the programme directive:

    interaction -> routing decision -> user evidence -> candidate affinity
    -> evaluation -> authorised promotion -> changed future route
    -> explainable trace -> rollback

Separation boundaries (enforced structurally, not by convention):

- raw interaction stays in the transcript archive; this store keeps only
  bounded, purpose-built ``routing_evidence`` events (immutable, append-only);
- ``affinity_candidate`` state is separate from evidence and from active
  routing;
- active routing changes only through ``routing_revision`` records carrying
  explicit authorisation; rolling back a revision never deletes evidence or
  candidates;
- nothing here touches persona prompts, personality state, voices, memories or
  competence claims.

Authority model (from the seed order and the ratified Aoteru routing contract
v0.1, not invented here):

- active routing changes ONLY by (a) the execute-scoped, principal-recording
  ratification API or (b) a bare "yes" to an offer from the same owner in the
  same session (``explicit_durable`` evidence). A free-text instruction ("use X
  for Y from now on") is a ``durable_request``: it makes the candidate eligible
  and OFFERED, never active (round-4 review, 2026-10-15). Questions, statements
  about a persona, negated/quoted phrases, pasted third-party text and
  reserved/safety turns are not requests at all (``is_durable_instruction``);
  read-only callers record nothing (the route's single scope gate);
- corrections and temporary choices create or reinforce *shadow* candidates
  only; repeated consistent corrections make a candidate ``eligible`` but it
  then waits for real user ratification;
- confidence never bypasses the gate;
- reserved matters (standards, values, boundaries, ratification, Level 5/6)
  always stay with Aoteru and can never be captured by learned state.

Confidence is a deliberately simple, explainable count: supporting evidence by
type (durable=3, correction=1, confirmation=1), minus contradicting evidence,
plus a consistency note. No learned model.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.misumi_persona_state import evidence_origin, is_reserved_turn, owner_key
from src.misumi_safety_gate import withhold_learned_route
from src.misumi_state_io import StateCorruptError, StateDir, StateUnavailable  # noqa: F401  (re-exported for callers)

logger = logging.getLogger(__name__)

# explicit_durable: an authorised act (a bare "yes" to an offer). durable_request: a free-text "from now on use X" - it may only OFFER.
EVIDENCE_TYPES = ("correction", "temporary_choice", "explicit_durable", "durable_request", "confirmation")
CANDIDATE_STATUSES = ("shadow", "eligible", "active", "rejected", "superseded")
EVIDENCE_WEIGHTS = {"explicit_durable": 3, "durable_request": 1, "correction": 1, "confirmation": 1, "temporary_choice": 0}
REPEATED_CORRECTIONS_FOR_ELIGIBLE = 3

_DURABLE_PHRASE = re.compile(
    r"\b(?:from\s+now\s+on|always|permanently|in\s+future|going\s+forward|forever|from\s+now)\b",
    re.IGNORECASE,
)
_RESERVED_MATTERS = re.compile(
    r"\b(?:standards?|values?|boundaries|ratif(?:y|ied|ication))\b|"
    r"\blevel\s*(?:5|five|6|six)\b",
    re.IGNORECASE,
)
_STOPWORDS = frozenset(
    "the a an and or of to for from in on at is are was were be been use used using with "
    "this that these those it its as by about into over under please question questions "
    "misumi aoteru always now when what who how why where which should would could can may "
    "want wants need needs like prefer prefers put give make letting route routing handle "
    "deals does did done know knows send sends tell tells keep just also things thing stuff anything "
    "everything something every time times from going forward permanently future".split()
)
# Round 5 (M2): a routing durable request needs ROUTING GRAMMAR with an explicit persona addressee - "use <persona> for X",
# "ask <persona> about X", "send/route X (questions) to <persona>", "for X (questions), use <persona>", "X questions go to <persona>".
# A bare imperative ("use bullet points", "use plain English") is never routing, and the cue is the grammar's own slot, validated.
_ROUTING_IMPERATIVE = re.compile(
    r"\b(?:use|send|route|ask|pass|hand|direct|give|let|have|put|switch\s+to|go\s+to|talk\s+to)\b", re.IGNORECASE
)
_FILLER = r"(?:questions?|queries|query|stuff|things|topics?|matters|requests?|issues?|jobs?|tasks?|chats?)"
_DET = r"(?:(?:the|my|our|any|all|anything\s+about|everything\s+about|anything\s+to\s+do\s+with|questions\s+about)\s+)?"
_CUE = r"(?P<cue>[a-z][a-z'-]{2,}(?:\s+[a-z][a-z'-]{2,})?)"
# Words that describe HOW to answer (style), not WHAT the question is about: never a routing cue.
_STYLE_WORDS = frozenset(
    "bullet bullets point points plain english language languages short shorter shortest brief briefer concise answer answers "
    "reply replies response responses simple simpler simplest technical detail details detailed prose paragraph paragraphs "
    "step steps stepwise numbered list lists format formatting jargon words sentence sentences tone style length long longer "
    "verbose wordy terse examples emoji emojis summary summaries markdown table tables headings friendly formal casual polite "
    "quick quickly slow slowly clear clearly voice".split()
)
# Adjectives, adverbs, pronouns and politeness that would make junk cues.
_JUNK_WORDS = frozenset(
    "good nice great better best worse worst more less most least really very quite pretty kind sort lot lots bit other another "
    "general random misc miscellaneous stuff thing things everything anything something nothing please thanks thank cheers "
    "okay fine same different new old big small little first last next whatever whichever there here them they their "
    "mine yours ours his hers its your you our him her".split()
)


@lru_cache(maxsize=8)
def _routing_grammar(names: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    persona = r"(?P<p>" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")"
    filler = r"(?:\s+" + _FILLER + r")?"
    return tuple(re.compile(p) for p in (
        r"\b(?:use|ask|let|have|get|try)\s+" + persona + r"\s+(?:for|about|with|on|to\s+(?:handle|answer|do|cover|deal\s+with))\s+"
        + _DET + _CUE + filler + r"\b",
        r"\b(?:send|route|pass|hand|direct|forward|refer|redirect|take)\s+" + _DET + _CUE + filler + r"\s+(?:over\s+)?to\s+"
        + persona + r"\b",
        r"\b(?:for|with|on|about)\s+" + _DET + _CUE + filler + r"\s*,?\s*(?:(?:from\s+now\s+on|going\s+forward|always|in\s+future)"
        r"\s*,?\s*)?(?:please\s+)?(?:use|ask|go\s+to|talk\s+to|switch\s+to)\s+" + persona + r"\b",
        r"\b" + _CUE + r"\s+" + _FILLER + r"\s+(?:should\s+|must\s+|will\s+|can\s+)?go\s+to\s+" + persona + r"\b",
    ))


def _persona_names() -> dict[str, str]:
    """Lower-case addressable name -> persona id (ids and display names; one-letter names are never free-text addressees)."""
    try:
        from src.misumi_policy import DISPLAY_NAMES, load_persona_policy

        ids = list(load_persona_policy())
    except Exception:  # noqa: BLE001 - no persona list: nothing can be addressed, so nothing is a routing instruction
        return {}
    names: dict[str, str] = {}
    for pid in ids:
        for name in (pid, str(DISPLAY_NAMES.get(pid, "")).lower()):
            if len(name) >= 2:
                names[name] = pid
    return names


def valid_cue(term: object, exclude: Any = ()) -> bool:
    """A cue must be a plain topic word: not a stopword, style vocabulary, adjective/adverb/pronoun junk, or a persona name."""
    token = str(term or "").strip().lower()
    skip = {str(item).lower() for item in exclude if item} | set(_persona_names())
    return bool(
        re.fullmatch(r"[a-z][a-z-]{2,30}", token)
        and token not in _STOPWORDS and token not in _STYLE_WORDS and token not in _JUNK_WORDS and token not in skip
        and not token.endswith("ly")
    )


def parse_routing_instruction(prompt: str) -> dict[str, Any] | None:
    """{'persona', 'cue', 'clause'} when the user's OWN text is a durable routing instruction with an explicit persona addressee
    and a valid topic cue; None otherwise (questions, statements, negations, quotes, pasted/third-party text, safety/reserved
    turns, style requests, bare imperatives, junk cues)."""
    from src.misumi_persona_state import _TYPOGRAPHIC, detect_style_signals, durable_phrase_clause, own_instruction

    own = own_instruction(prompt)
    if own["data_task"] or is_reserved_turn(prompt) or detect_style_signals(prompt):
        return None  # a style request ("from now on use bullet points") never enters routing
    names = _persona_names()
    if not names:
        return None
    grammar = _routing_grammar(tuple(names))
    text = own["text"].translate(_TYPOGRAPHIC).lower()
    combined = re.compile("|".join(f"(?:{g.pattern})".replace("(?P<p>", "(?:").replace("(?P<cue>", "(?:") for g in grammar))
    bounds = durable_phrase_clause(text, require=combined)
    if bounds is None:
        return None
    clause = text[bounds[0]:bounds[1]]
    for pattern in grammar:
        match = pattern.search(clause)
        if not match:
            continue
        persona = names.get(match.group("p"))
        if persona is None:
            continue
        try:
            from src.persona_capabilities import routing_intents

            intents = [str(i).lower() for i in (routing_intents(persona) or []) if i and i != "default"]
        except Exception:  # noqa: BLE001
            intents = []
        words = [w.strip("'-") for w in match.group("cue").split()]
        words = [w for w in words if not re.fullmatch(_FILLER, w)]
        cue = next((w for w in words if w in intents and valid_cue(w)), None) or next((w for w in words if valid_cue(w)), None)
        if cue is None:
            return None  # the grammar matched but the topic slot is junk: refuse rather than learn a junk cue
        return {"persona": persona, "cue": cue, "clause": clause}
    return None


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _short(text: object, limit: int = 240) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def keyword_present(text: str, keyword: str) -> bool:
    """Same word-boundary keyword test the deterministic contract router uses."""
    return re.search(
        r"(?<![a-z0-9])" + re.escape(keyword.lower()) + r"(?![a-z0-9])",
        str(text or "").lower(),
    ) is not None


def keyword_variants(keyword: str) -> list[str]:
    """A cue and its small closed set of morphological variants.

    Deliberately tiny and enumerable so matching stays explainable; this is not
    a stemmer and must never grow into fuzzy matching.
    """
    k = keyword.lower().strip()
    variants = {k}
    if k.endswith("s") and len(k) > 3:
        variants.add(k[:-1])
    else:
        variants.add(k + "s")
    if k.endswith("ing") and len(k) > 5:
        variants.add(k[:-3])
        variants.add(k[:-3] + "e")
    return sorted(variants)


def extract_cue_term(prompt: str, persona_intents: list[str] | None = None, exclude: Any = ()) -> str | None:
    """Pick the narrowest deterministic cue term for a learned mapping.

    Preference order: an intent of the proposed persona that literally appears
    in the prompt; otherwise the first non-stopword token of >= 4 characters
    that is not in ``exclude`` (persona names are never cues).
    Returns None when the prompt offers no usable cue (no candidate is made).
    """
    text = str(prompt or "").lower()
    skip = {str(item).lower() for item in exclude if item}
    for intent in persona_intents or []:
        if intent and intent != "default" and keyword_present(text, intent):
            return intent
    for raw in re.findall(r"[a-z][a-z-]{3,}", text):
        token = raw.strip("-")
        if token in skip or not valid_cue(token):
            continue  # round 5: stopwords, style vocabulary, adjective junk and persona names are never cues
        return token
    return None


class RoutingAdaptationStore:
    """File-backed, restart-safe, multi-process-safe store for evidence, candidates and revisions.

    All I/O goes through :class:`src.misumi_state_io.StateDir` (cross-process lock, atomic writes, single-write appends,
    fail-closed quarantine on corruption).
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.evidence_path = self.root / "evidence.jsonl"
        self.candidates_path = self.root / "candidates.json"
        self.revisions_path = self.root / "revisions.jsonl"
        self._io = StateDir(self.root)
        # In-process index of the latest auto route per (owner, session), used only to detect an immediate manual choice as a
        # correction. Not evidence; keyed by owner too (round 5, M3) so another owner's turn in the same session id never counts.
        self._last_auto_route: dict[tuple[str, str], dict[str, Any]] = {}

    def locked(self):
        """The store's cross-process lock (re-entrant): callers that must check-then-act atomically hold it."""
        return self._io.locked()

    # ---------- evidence ----------

    def record_evidence(self, **fields: Any) -> dict[str, Any]:
        """Append one immutable evidence event and fold it into candidate state (one locked unit across processes)."""
        record = {
            "evidence_id": f"rev-ev-{uuid.uuid4().hex[:12]}",
            "created_at": _now(),
            "created_epoch": time.time(),
            "type": fields.get("type"),
            "cue": list(fields.get("cue") or []),
            "previous_persona": fields.get("previous_persona"),
            "proposed_persona": fields.get("proposed_persona"),
            "prompt_excerpt": _short(fields.get("prompt"), 240),
            "prompt_sha256": hashlib.sha256(str(fields.get("prompt") or "").encode("utf-8")).hexdigest(),
            "previous_route_reasons": list(fields.get("previous_route_reasons") or []),
            "session_id": fields.get("session_id"),
            "owner": fields.get("owner"),
            "runtime": fields.get("runtime", "odysseus-misumi"),
            "persistence_eligible": bool(fields.get("persistence_eligible", True)),
            "source_authority": fields.get("source_authority", "user"),
            "previous_auto_route_id": fields.get("previous_auto_route_id"),
            "context": _short(fields.get("context"), 240),
        }
        if record["type"] not in EVIDENCE_TYPES:
            raise ValueError(f"unknown evidence type: {record['type']!r}")
        with self._io.locked():
            self._io.check_healthy()
            self._load_candidates()  # fail closed BEFORE appending if the candidate file is already damaged
            self._io.append_jsonl(self.evidence_path.name, record)
            candidate = self.update_candidate_from_evidence(record)
        return {"evidence": record, "candidate": candidate}

    def list_evidence(self, cue: list[str] | None = None) -> list[dict[str, Any]]:
        rows = self._read_jsonl(self.evidence_path)
        if cue is None:
            return rows
        want = sorted(cue)
        return [row for row in rows if sorted(row.get("cue") or []) == want]

    def auto_route_already_counted(self, request_id: object) -> bool:
        """True when some evidence already cites this auto route: one auto route counts at most once (round 5, M3)."""
        if not request_id:
            return False
        return any(row.get("previous_auto_route_id") == request_id for row in self._read_jsonl(self.evidence_path))

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

    @staticmethod
    def cue_key(cue: list[str]) -> str:
        return "|".join(sorted(str(item).lower() for item in cue))

    def update_candidate_from_evidence(self, evidence: dict[str, Any]) -> dict[str, Any]:
        """Fold one evidence event into candidate state (never into active routing)."""
        cue = list(evidence.get("cue") or [])
        if not cue:
            return {"skipped": "no usable cue term"}
        key = self.cue_key(cue)
        from_user = evidence.get("source_authority", "user") == "user"
        with self._io.locked():
            data = self._load_candidates()
            candidates = data.setdefault("candidates", {})
            candidate = candidates.get(key)
            if candidate is None:
                candidate = {
                    "candidate_id": f"aff-{uuid.uuid4().hex[:12]}",
                    "cue": sorted(cue),
                    "base_persona": evidence.get("previous_persona") or "aoteru",
                    "proposed_persona": evidence.get("proposed_persona"),
                    "supporting_evidence": [],
                    "contradicting_evidence": [],
                    "confidence": {"score": 0, "corrections_by_owner": {}, "counted_auto_routes": [],
                                   "basis": "count of supporting evidence by type (durable=3, correction=1, confirmation=1), minus contradictions; "
                                            "eligibility by repetition counts ONE owner's corrections, each auto route once; never bypasses ratification"},
                    "rationale": "",
                    "created_at": _now(),
                    "updated_at": _now(),
                    "status": "shadow",
                    "awaiting": None,
                    "origin": None,
                }
                candidates[key] = candidate
            eid = evidence["evidence_id"]
            etype = evidence["type"]
            proposed = evidence.get("proposed_persona")
            if etype == "durable_request":
                # A free-text "from now on use X" is NOT authority: it makes the mapping eligible and offerable - to the user who
                # asked, in that session (``origin``) - and only their bare "yes" (or the operator API) can promote it.
                candidate["supporting_evidence"].append(eid)
                if not (candidate.get("status") == "active" and proposed == candidate["proposed_persona"]):
                    if proposed and proposed != candidate["proposed_persona"] and len(candidate["supporting_evidence"]) > 1:
                        candidate.setdefault("superseded_proposals", []).append(
                            {"persona": candidate["proposed_persona"], "by": eid, "at": _now()}
                        )
                    candidate["proposed_persona"] = proposed
                    candidate["status"] = "eligible"
                    candidate["awaiting"] = "user-ratification"
                    candidate["requested_by"] = eid
                    candidate["origin"] = evidence_origin(evidence, "request") if from_user else None
                    candidate["rationale"] = "the user asked for this from now on; it needs their yes to an offer (or operator ratification)"
                    candidate.pop("promotion_authorised_by", None)
                    candidate.pop("rejection", None)
            elif (
                etype != "explicit_durable" and proposed
                and proposed != candidate["proposed_persona"] and candidate["supporting_evidence"]
            ):
                # Contradiction: the same cue pulled toward a different persona.
                candidate["contradicting_evidence"].append(eid)
                candidate["status"] = "shadow"
                candidate["awaiting"] = "contradicting-evidence"
                candidate["origin"] = None
            elif etype == "explicit_durable":
                # The strongest evidence tier: an explicit durable user instruction supersedes earlier
                # inferred proposals for this cue (they stay in the evidence log; the superseded
                # proposal is recorded on the candidate). Without this, "use Jin from now on" after
                # corrections toward Erwin was filed as a contradiction and could never promote.
                if proposed and proposed != candidate["proposed_persona"] and candidate["supporting_evidence"]:
                    candidate.setdefault("superseded_proposals", []).append(
                        {"persona": candidate["proposed_persona"], "by": eid, "at": _now()}
                    )
                candidate["supporting_evidence"].append(eid)
                candidate["proposed_persona"] = proposed
                candidate["status"] = "eligible"
                candidate["awaiting"] = None
                # Never overwrite a pending authorisation (round 6): the first recorded yes stays the cited one.
                if not candidate.get("promotion_authorised_by"):
                    candidate["promotion_authorised_by"] = eid
                candidate["rationale"] = "explicit durable user instruction directly authorises this mapping"
            else:
                if proposed and proposed != candidate["proposed_persona"] and not candidate["supporting_evidence"]:
                    candidate["proposed_persona"] = proposed
                candidate["supporting_evidence"].append(eid)
                confidence = candidate["confidence"]
                counted = confidence.setdefault("counted_auto_routes", [])
                route_id = evidence.get("previous_auto_route_id")
                fresh_route = etype == "correction" and (not route_id or route_id not in counted)
                if fresh_route and route_id:
                    counted.append(route_id)
                by_owner = confidence.setdefault("corrections_by_owner", {})
                who = owner_key(evidence.get("owner"))
                if fresh_route:
                    by_owner[who] = int(by_owner.get(who, 0)) + 1
                corrections = confidence.get("corrections", 0) + (1 if fresh_route else 0)
                confidence["corrections"] = corrections
                confidence["durable"] = confidence.get("durable", 0)
                if (
                    fresh_route and from_user
                    and by_owner.get(who, 0) >= REPEATED_CORRECTIONS_FOR_ELIGIBLE
                    and candidate.get("status") not in ("active", "rejected")
                ):
                    # (A rejected inference stays rejected and an active mapping is never offered again: the same guard the
                    # persona-state store has.) Repeated behavioural evidence from ONE owner: eligible, offered to that owner,
                    # and promotion still needs their real ratification - never automatic.
                    candidate["status"] = "eligible"
                    candidate["awaiting"] = "user-ratification"
                    candidate["origin"] = evidence_origin(evidence, "corrections")
                candidate["rationale"] = (
                    f"{corrections} consistent correction(s) across separate interactions"
                )
            types = {row.get("evidence_id"): str(row.get("type")) for row in self._read_jsonl(self.evidence_path)}  # one read
            candidate["confidence"]["score"] = sum(
                EVIDENCE_WEIGHTS.get(types.get(eid, ""), 0)
                for eid in candidate["supporting_evidence"]
            ) - len(candidate["contradicting_evidence"])
            candidate["updated_at"] = _now()
            self._save_candidates(data)
            return candidate

    def _type_of(self, evidence_id: str) -> str:
        for row in self._read_jsonl(self.evidence_path):
            if row.get("evidence_id") == evidence_id:
                return str(row.get("type"))
        return ""

    def get_candidate(self, cue: list[str]) -> dict[str, Any] | None:
        return self._load_candidates().get("candidates", {}).get(self.cue_key(cue))

    def get_candidate_by_id(self, candidate_id: str) -> dict[str, Any] | None:
        for candidate in self.all_candidates().values():
            if isinstance(candidate, dict) and candidate.get("candidate_id") == candidate_id:
                return candidate
        return None

    def reject(self, candidate_id: str, reason: str) -> dict[str, Any]:
        """Reject a shadow/eligible candidate (terminal). Active candidates
        must be rolled back instead; history is never deleted."""
        with self._io.locked():
            data = self._load_candidates()
            candidate = next(
                (c for c in data.get("candidates", {}).values()
                 if isinstance(c, dict) and c.get("candidate_id") == candidate_id),
                None,
            )
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

    def all_candidates(self) -> dict[str, dict[str, Any]]:
        return self._load_candidates().get("candidates", {})

    # ---------- shadow evaluation ----------

    def evaluate_candidate(
        self,
        candidate: dict[str, Any],
        base_route: "Any",
        probe_prompts: list[str] | None = None,
    ) -> dict[str, Any]:
        """Counterfactually evaluate a candidate against the active (unchanged) router.

        ``base_route`` is a callable prompt -> (persona, reasons) - the active
        deterministic router. The candidate overlay is applied only inside this
        function; active routing is untouched (shadow evaluation).
        """
        cue = list(candidate.get("cue") or [])
        proposed = candidate.get("proposed_persona")
        results = {"target": [], "nearby": [], "reserved": []}
        for prompt in probe_prompts or [f"Tell me about {cue[0] if cue else 'this'}"]:
            base_persona, base_reasons = base_route(prompt)
            row = {
                "prompt": _short(prompt, 160),
                "base_persona": base_persona,
                "with_candidate": self._apply_overlay(prompt, [{
                    "cue": cue,
                    "persona": proposed,
                    "created_at": candidate.get("updated_at"),
                }])[0] or base_persona,
                "base_reasons": base_reasons,
            }
            if is_reserved_turn(prompt):  # the same shared gate learned routing uses
                results["reserved"].append(row)
            elif any(keyword_present(prompt, variant) for item in cue for variant in keyword_variants(item)):
                results["target"].append(row)
            else:
                results["nearby"].append(row)
        spillover = [
            row for row in results["nearby"] if row["with_candidate"] != row["base_persona"]
        ]
        return {
            "candidate_id": candidate.get("candidate_id"),
            "proposed_persona": proposed,
            "shadow_only": True,
            "target_prompts": results["target"],
            "nearby_prompts": results["nearby"],
            "reserved_prompts": results["reserved"],
            "spillover_count": len(spillover),
            "spillover": spillover,
            "verdict": (
                "acceptable" if proposed and not spillover
                and all(row["with_candidate"] == proposed for row in results["target"])
                else "needs-review"
            ),
        }

    # ---------- revisions ----------

    def promote(self, candidate_id: str, *, authorisation: dict[str, Any], precondition: Any = None) -> dict[str, Any]:
        """Activate a candidate as a routing revision - gate-checked.

        The gate: the candidate must be ``eligible`` AND carry an explicit
        authorisation dict. Confidence alone never promotes. ``precondition``
        (optional) runs under the store lock; a falsy result refuses promotion.
        """
        with self._io.locked():
            data = self._load_candidates()
            # Candidates are keyed by cue; find by id.
            candidate = next(
                (c for c in data.get("candidates", {}).values()
                 if isinstance(c, dict) and c.get("candidate_id") == candidate_id),
                None,
            )
            if candidate is None:
                raise KeyError(f"unknown candidate: {candidate_id}")
            if candidate.get("status") != "eligible":
                raise ValueError(
                    f"candidate {candidate_id} is {candidate.get('status')!r}, not eligible"
                )
            if precondition is not None and not precondition(candidate):
                raise ValueError(f"candidate {candidate_id} changed since it was offered")
            if not authorisation or not authorisation.get("type"):
                raise ValueError("promotion requires explicit authorisation")
            if authorisation["type"] == "user_instruction":
                if authorisation.get("evidence_id") not in candidate.get("supporting_evidence", []):
                    raise ValueError("user_instruction authorisation must cite supporting evidence")
                if self._type_of(str(authorisation.get("evidence_id"))) != "explicit_durable":
                    # Only an explicit act (a bare "yes" to an offer) is user authority; a free-text request or a correction is not.
                    raise ValueError("user_instruction authorisation must cite explicit_durable evidence (a yes to an offer)")
            elif authorisation["type"] == "operator_ratification":
                # The operator's own authenticated act (the ratification the
                # seed order requires for repetition-eligible candidates).
                if not authorisation.get("principal"):
                    raise ValueError("operator_ratification requires the ratifying principal")
            else:
                raise ValueError(f"authorisation type not supported: {authorisation['type']!r}")
            previous = self.active_revision_for_cue(candidate["cue"])
            revision = {
                "revision_id": f"rr-{uuid.uuid4().hex[:12]}",
                "cue": candidate["cue"],
                "persona": candidate["proposed_persona"],
                "previous_revision_id": previous["revision_id"] if previous else None,
                "candidate_id": candidate_id,
                "evidence_ids": list(candidate.get("supporting_evidence", [])),
                "authorisation": authorisation,
                "created_at": _now(),
                "status": "active",
            }
            candidate["status"] = "active"
            candidate["updated_at"] = _now()
            self._io.append_jsonl(self.revisions_path.name, revision)
            self._save_candidates(data)
            return revision

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        """All records of one of this store's logs. A damaged log raises StateCorruptError (fail closed), never []."""
        return self._io.read_jsonl(Path(path).name)

    def all_revisions(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.revisions_path)

    def _effective_active(self) -> list[dict[str, Any]]:
        """Active revisions minus those a later rollback record deactivates."""
        revisions = self.all_revisions()
        rolled_back = {row["rolls_back"] for row in revisions if row.get("rolls_back")}
        return [
            row for row in revisions
            if row.get("status") == "active" and row.get("revision_id") not in rolled_back
        ]

    def active_revision_for_cue(self, cue: list[str]) -> dict[str, Any] | None:
        key = self.cue_key(cue)
        active = [
            row for row in self._effective_active()
            if self.cue_key(row.get("cue") or []) == key
        ]
        return active[-1] if active else None

    def active_overlays(self) -> list[dict[str, Any]]:
        return [row for row in self._effective_active() if row.get("cue")]

    def rollback_revision(self, revision_id: str, reason: str) -> dict[str, Any]:
        """Deactivate one revision by recording its rollback. Nothing is deleted."""
        with self._io.locked():
            revisions = self.all_revisions()
            target = next((row for row in revisions if row.get("revision_id") == revision_id), None)
            if target is None:
                raise KeyError(f"unknown revision: {revision_id}")
            if target.get("status") != "active":
                raise ValueError(f"revision {revision_id} is {target.get('status')!r}, not active")
            rollback = {
                "revision_id": f"rr-{uuid.uuid4().hex[:12]}",
                "cue": target["cue"],
                "persona": target["persona"],
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
            candidate = data.get("candidates", {}).get(self.cue_key(target["cue"]))
            if candidate is not None and candidate.get("status") == "active":
                candidate["status"] = "shadow"
                candidate["awaiting"] = "rolled-back"
                candidate["origin"] = None
                candidate.pop("promotion_authorised_by", None)
                candidate["updated_at"] = _now()
                self._save_candidates(data)
            return rollback

    # ---------- overlay application ----------

    def _apply_overlay(self, prompt: str, overlays: list[dict[str, Any]],
                       exact: bool = False) -> tuple[str, dict[str, Any] | None]:
        best: dict[str, Any] | None = None
        best_hits = 0
        for overlay in overlays:
            hits = sum(
                1
                for item in overlay.get("cue") or []
                for variant in ([item] if exact else keyword_variants(item))
                if keyword_present(prompt, variant)
            )
            if hits > best_hits or (hits == best_hits > 0 and best is not None
                                    and str(overlay.get("created_at") or "") > str(best.get("created_at") or "")):
                best, best_hits = overlay, hits
        if best is None or best_hits == 0:
            return "", None
        return str(best.get("persona")), best

    def apply_learned_overlays(
        self,
        prompt: str,
        base_persona: str,
        base_reasons: list[str],
        context: Any = (),
    ) -> tuple[str, dict[str, Any] | None]:
        """Apply active learned revisions to one auto-routing decision.

        Learned routing is ADVISORY (round 6/7). It is withheld when the precision safety block flags the turn
        (``is_reserved_turn``) OR when the separate RECALL-FIRST routing gate (``withhold_learned_route``: any hazard, injury,
        medical, urgency, distress, substance, violence, vehicle or missing/trapped word, or a person together with a body part)
        fires; never when the base route is a reserved route (Aoteru keeps the lead); and only on the exact cue word. A
        quarantined, locked or unavailable store applies nothing. Explicit caller persona choices never reach this path.
        Residual risk (measured on round-7 held-out sets, 80 emergencies / 80 ordinary): the routing gate missed 3/80 emergencies
        and withheld the learned route on 10/80 ordinary turns; an emergency it misses can still follow a learned cue to another
        persona (that persona keeps its seed-order rules; the learned-style carve-out does not cover routing).
        """
        if is_reserved_turn(prompt, context) or withhold_learned_route(prompt):
            return base_persona, None
        if any(str(reason).startswith("reserved:") for reason in base_reasons or []):
            return base_persona, None  # a reserved base route (Aoteru) is never overridden by learned state
        try:
            overlays = self.active_overlays()
        except StateUnavailable as exc:
            logger.error("Misumi learned routing withheld: %s", exc)
            return base_persona, None
        if not overlays:
            return base_persona, None
        persona, overlay = self._apply_overlay(prompt, overlays, exact=True)  # round 6: the exact cue word only
        if overlay is None:
            return base_persona, None
        provenance = {
            "learned": True,
            "revision_id": overlay.get("revision_id"),
            "cue": overlay.get("cue"),
            "base_selected": base_persona,
            "base_reasons": base_reasons,
            "candidate_id": overlay.get("candidate_id"),
        }
        return persona, provenance

    # ---------- auto-route context (correction detection) ----------

    def note_auto_route(
        self,
        session_id: str | None,
        prompt: str,
        persona: str,
        reasons: list[str],
        request_id: str,
        persisted: bool = True,
        owner: str | None = None,
    ) -> None:
        if not session_id:
            return
        self._last_auto_route[(owner_key(owner), str(session_id))] = {
            "prompt": prompt,
            "persona": persona,
            "reasons": list(reasons),
            "request_id": request_id,
            "persisted": bool(persisted),  # only a persisted turn may seed v0.2 follow-up carry or count as a correction
            "owner": owner_key(owner),
            "at": time.time(),
        }

    def last_auto_route(self, session_id: str | None, owner: str | None = None,
                        max_age_s: float = 900.0) -> dict[str, Any] | None:
        """The latest auto route of THIS owner in this session (another owner's turn with the same session id is invisible)."""
        if not session_id:
            return None
        row = self._last_auto_route.get((owner_key(owner), str(session_id)))
        if row and time.time() - row["at"] <= max_age_s:
            return row
        return None


def is_durable_instruction(prompt: str) -> bool:
    """True only when the user's OWN instruction text is a standing ROUTING instruction: a durable phrase plus routing grammar
    with an explicit persona addressee and a valid topic cue (:func:`parse_routing_instruction`).

    Not durable: a question ("Does Jin always know about compost?"), a statement about a persona ("Jin always knows ..."),
    a negated or quoted phrase, pasted/third-party text, a reserved/safety turn, a style request ("from now on use bullet
    points"), or an instruction whose topic slot is junk. Even when True, the result is only an OFFER.
    """
    return parse_routing_instruction(prompt) is not None


def record_durable_instruction(
    store: RoutingAdaptationStore,
    *,
    prompt: str,
    named_persona: str | None = None,
    session_id: str | None,
    owner: str | None,
    persist: bool = True,
) -> dict[str, Any] | None:
    """Record one free-text durable routing request (``use X for Y from now on``) as an OFFER.

    Free text is never authority by itself (round-4 review): the request is recorded as ``durable_request`` evidence and the
    candidate becomes eligible awaiting user ratification. It is promoted only by a bare "yes" to the offer from the same owner
    (origin), or by the operator ratification API. Callers must already hold the execute scope (the route checks it).
    The persona and cue come from the instruction's own grammar; ``named_persona``, when given, must agree with it.
    Returns None when the prompt is not the user's own durable routing instruction.
    """
    if not persist:
        return None
    parsed = parse_routing_instruction(prompt)
    if parsed is None or (named_persona is not None and parsed["persona"] != named_persona):
        return None
    previous = store.last_auto_route(session_id, owner)
    result = store.record_evidence(
        type="durable_request",
        cue=[parsed["cue"]],
        previous_persona=previous["persona"] if previous else "aoteru",
        proposed_persona=parsed["persona"],
        prompt=prompt,
        previous_route_reasons=previous["reasons"] if previous else [],
        session_id=session_id,
        owner=owner,
        context="free-text durable request: offered, needs a bare yes or operator ratification",
    )
    candidate = result["candidate"]
    offerable = candidate.get("status") == "eligible" and candidate.get("awaiting") == "user-ratification"
    return {
        "evidence_id": result["evidence"]["evidence_id"],
        "evidence_type": "durable_request",
        "cue": candidate.get("cue"),
        "candidate_id": candidate.get("candidate_id"),
        "candidate_status": candidate.get("status"),
        "base_persona": result["evidence"]["previous_persona"],
        "proposed_persona": parsed["persona"],
        "state": "offered" if offerable else str(candidate.get("status") or "shadow"),
    }


def record_manual_choice(
    store: RoutingAdaptationStore,
    *,
    prompt: str,
    chosen_persona: str,
    session_id: str | None,
    owner: str | None,
    persist: bool = True,
) -> dict[str, Any] | None:
    """Interpret one manually selected persona against the recent auto route.

    Classification (deliberately conservative):
    - a durable routing instruction in the user's own words is OFFERED (:func:`record_durable_instruction`; the persona is the
      one the instruction names, not the one selected);
    - ``correction``: THIS owner's own PERSISTED auto route happened recently in this session, it has not been counted before,
      and the new prompt still talks about the same cue - the auto choice was unwanted; candidate state stays shadow until one
      owner has corrected three separate auto routes;
    - ``temporary_choice``: no cue overlap - a deliberate one-off change of voice; never creates durable state by itself.
    Another owner's turn, an incognito (unpersisted) turn, or an auto route already counted contributes nothing (round 5, M3).
    """
    if not persist:
        return None
    if is_reserved_turn(prompt):
        return None
    outcome = record_durable_instruction(store, prompt=prompt, session_id=session_id, owner=owner, persist=persist)
    if outcome is not None:
        return outcome
    last = store.last_auto_route(session_id, owner)
    if not last or not last.get("persisted") or last.get("owner") != owner_key(owner):
        return None
    if store.auto_route_already_counted(last.get("request_id")):
        return None
    from src.persona_capabilities import routing_intents

    cue = [
        reason for reason in last.get("reasons") or []
        if not str(reason).startswith(("fallback:", "reserved:", "learned:", "carry:"))
    ]
    if not cue:
        extracted = extract_cue_term(last.get("prompt") or "", routing_intents(chosen_persona))
        cue = [extracted] if extracted else []
    if not cue:
        return None
    related = any(
        keyword_present(prompt, variant) for item in cue for variant in keyword_variants(item)
    )
    etype = "correction" if related else "temporary_choice"
    result = store.record_evidence(
        type=etype,
        cue=cue,
        previous_persona=last["persona"],
        proposed_persona=chosen_persona,
        prompt=prompt,
        previous_route_reasons=last.get("reasons") or [],
        session_id=session_id,
        owner=owner,
        previous_auto_route_id=last.get("request_id"),
    )
    candidate = result["candidate"]
    return {
        "evidence_id": result["evidence"]["evidence_id"],
        "evidence_type": etype,
        "cue": cue,
        "candidate_id": candidate.get("candidate_id") if isinstance(candidate, dict) else None,
        "candidate_status": candidate.get("status") if isinstance(candidate, dict) else None,
        "base_persona": last["persona"],
        "proposed_persona": chosen_persona,
        "state": "shadow-only",
    }

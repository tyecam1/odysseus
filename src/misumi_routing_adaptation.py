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

- an ``explicit_durable`` user instruction ("use X for Y from now on") is a
  direct user authorisation for that one mapping and may promote its candidate;
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
import json
import logging
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EVIDENCE_TYPES = ("correction", "temporary_choice", "explicit_durable", "confirmation")
CANDIDATE_STATUSES = ("shadow", "eligible", "active", "rejected", "superseded")
EVIDENCE_WEIGHTS = {"explicit_durable": 3, "correction": 1, "confirmation": 1, "temporary_choice": 0}
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
    "deals".split()
)


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


def extract_cue_term(prompt: str, persona_intents: list[str] | None = None) -> str | None:
    """Pick the narrowest deterministic cue term for a learned mapping.

    Preference order: an intent of the proposed persona that literally appears
    in the prompt; otherwise the first non-stopword token of >= 4 characters.
    Returns None when the prompt offers no usable cue (no candidate is made).
    """
    text = str(prompt or "").lower()
    for intent in persona_intents or []:
        if intent and intent != "default" and keyword_present(text, intent):
            return intent
    for raw in re.findall(r"[a-z][a-z-]{3,}", text):
        token = raw.strip("-")
        if token in _STOPWORDS or token in {v for v in _STOPWORDS}:
            continue
        return token
    return None


class RoutingAdaptationStore:
    """File-backed, restart-safe store for evidence, candidates and revisions."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.evidence_path = self.root / "evidence.jsonl"
        self.candidates_path = self.root / "candidates.json"
        self.revisions_path = self.root / "revisions.jsonl"
        self._lock = threading.Lock()
        # In-session index of the latest auto route per session, used only to
        # detect an immediate manual choice as a correction/confirmation. Not
        # evidence; evidence is written explicitly.
        self._last_auto_route: dict[str, dict[str, Any]] = {}

    # ---------- evidence ----------

    def record_evidence(self, **fields: Any) -> dict[str, Any]:
        """Append one immutable evidence event; returns the stored record."""
        record = {
            "evidence_id": f"rev-ev-{uuid.uuid4().hex[:12]}",
            "created_at": _now(),
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
        }
        if record["type"] not in EVIDENCE_TYPES:
            raise ValueError(f"unknown evidence type: {record['type']!r}")
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            with self.evidence_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        candidate = self.update_candidate_from_evidence(record)
        return {"evidence": record, "candidate": candidate}

    def list_evidence(self, cue: list[str] | None = None) -> list[dict[str, Any]]:
        rows = self._read_jsonl(self.evidence_path)
        if cue is None:
            return rows
        want = sorted(cue)
        return [row for row in rows if sorted(row.get("cue") or []) == want]

    # ---------- candidates ----------

    def _load_candidates(self) -> dict[str, Any]:
        try:
            data = json.loads(self.candidates_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"candidates": {}}
        except (OSError, json.JSONDecodeError):
            return {"candidates": {}}

    def _save_candidates(self, data: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.candidates_path.write_text(
            json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def cue_key(cue: list[str]) -> str:
        return "|".join(sorted(str(item).lower() for item in cue))

    def update_candidate_from_evidence(self, evidence: dict[str, Any]) -> dict[str, Any]:
        """Fold one evidence event into candidate state (never into active routing)."""
        cue = list(evidence.get("cue") or [])
        if not cue:
            return {"skipped": "no usable cue term"}
        key = self.cue_key(cue)
        with self._lock:
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
                    "confidence": {"score": 0, "basis": "count of supporting evidence by type (durable=3, correction=1, confirmation=1), minus contradictions; never bypasses ratification"},
                    "rationale": "",
                    "created_at": _now(),
                    "updated_at": _now(),
                    "status": "shadow",
                    "awaiting": None,
                }
                candidates[key] = candidate
            eid = evidence["evidence_id"]
            etype = evidence["type"]
            proposed = evidence.get("proposed_persona")
            if proposed and proposed != candidate["proposed_persona"] and candidate["supporting_evidence"]:
                # Contradiction: the same cue pulled toward a different persona.
                candidate["contradicting_evidence"].append(eid)
                candidate["status"] = "shadow"
                candidate["awaiting"] = "contradicting-evidence"
            elif etype == "explicit_durable":
                candidate["supporting_evidence"].append(eid)
                candidate["proposed_persona"] = proposed
                candidate["status"] = "eligible"
                candidate["awaiting"] = None
                candidate["promotion_authorised_by"] = eid
                candidate["rationale"] = "explicit durable user instruction directly authorises this mapping"
            else:
                if proposed and proposed != candidate["proposed_persona"] and not candidate["supporting_evidence"]:
                    candidate["proposed_persona"] = proposed
                candidate["supporting_evidence"].append(eid)
                durable_count = candidate["confidence"].get("durable", 0)
                corrections = candidate["confidence"].get("corrections", 0) + (etype == "correction")
                candidate["confidence"]["corrections"] = corrections
                candidate["confidence"]["durable"] = durable_count + (etype == "explicit_durable")
                if corrections >= REPEATED_CORRECTIONS_FOR_ELIGIBLE:
                    # Repeated behavioural evidence: eligible, but promotion
                    # still needs real user ratification - never automatic.
                    candidate["status"] = "eligible"
                    candidate["awaiting"] = "user-ratification"
                candidate["rationale"] = (
                    f"{corrections} consistent correction(s) across separate interactions"
                )
            candidate["confidence"]["score"] = sum(
                EVIDENCE_WEIGHTS.get(self._type_of(eid), 0)
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
            if _RESERVED_MATTERS.search(prompt):
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

    def promote(self, candidate_id: str, *, authorisation: dict[str, Any]) -> dict[str, Any]:
        """Activate a candidate as a routing revision - gate-checked.

        The gate: the candidate must be ``eligible`` AND carry an explicit
        authorisation dict. Confidence alone never promotes.
        """
        with self._lock:
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
            if not authorisation or not authorisation.get("type"):
                raise ValueError("promotion requires explicit authorisation")
            if authorisation["type"] == "user_instruction":
                if authorisation.get("evidence_id") not in candidate.get("supporting_evidence", []):
                    raise ValueError("user_instruction authorisation must cite supporting evidence")
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
            self._save_candidates(data)
            self.root.mkdir(parents=True, exist_ok=True)
            with self.revisions_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(revision, ensure_ascii=False, sort_keys=True) + "\n")
            return revision

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        try:
            rows = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    value = json.loads(line)
                    if isinstance(value, dict):
                        rows.append(value)
            return rows
        except (OSError, json.JSONDecodeError):
            return []

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
        with self._lock:
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
            with self.revisions_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(rollback, ensure_ascii=False, sort_keys=True) + "\n")
            data = self._load_candidates()
            candidate = data.get("candidates", {}).get(self.cue_key(target["cue"]))
            if candidate is not None and candidate.get("status") == "active":
                candidate["status"] = "shadow"
                candidate["awaiting"] = "rolled-back"
                candidate["updated_at"] = _now()
                self._save_candidates(data)
            return rollback

    # ---------- overlay application ----------

    def _apply_overlay(self, prompt: str, overlays: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
        best: dict[str, Any] | None = None
        best_hits = 0
        for overlay in overlays:
            hits = sum(
                1
                for item in overlay.get("cue") or []
                for variant in keyword_variants(item)
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
    ) -> tuple[str, dict[str, Any] | None]:
        """Apply active learned revisions to one auto-routing decision.

        Reserved matters always win (they stay with Aoteru regardless of any
        learned state). Explicit caller persona choices never reach this path.
        """
        if _RESERVED_MATTERS.search(prompt):
            return base_persona, None
        overlays = self.active_overlays()
        if not overlays:
            return base_persona, None
        persona, overlay = self._apply_overlay(prompt, overlays)
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
    ) -> None:
        if not session_id:
            return
        self._last_auto_route[session_id] = {
            "prompt": prompt,
            "persona": persona,
            "reasons": list(reasons),
            "request_id": request_id,
            "at": time.time(),
        }

    def last_auto_route(self, session_id: str | None, max_age_s: float = 900.0) -> dict[str, Any] | None:
        if not session_id:
            return None
        row = self._last_auto_route.get(session_id)
        if row and time.time() - row["at"] <= max_age_s:
            return row
        return None


def is_durable_instruction(prompt: str) -> bool:
    return bool(_DURABLE_PHRASE.search(str(prompt or "")))


def record_durable_instruction(
    store: RoutingAdaptationStore,
    *,
    prompt: str,
    named_persona: str,
    session_id: str | None,
    owner: str | None,
    persist: bool = True,
) -> dict[str, Any] | None:
    """Handle one explicit durable user instruction (``use X for Y from now on``).

    The instruction is user authority for exactly this mapping. Returns the
    recorded evidence, the (eligible) candidate and, when promoted, the active
    revision. Returns None when the instruction carries no usable cue.
    """
    if not persist:
        return None
    from src.persona_capabilities import routing_intents

    previous = store.last_auto_route(session_id)
    cue_term = extract_cue_term(prompt, routing_intents(named_persona))
    if not cue_term:
        return None
    result = store.record_evidence(
        type="explicit_durable",
        cue=[cue_term],
        previous_persona=previous["persona"] if previous else "aoteru",
        proposed_persona=named_persona,
        prompt=prompt,
        previous_route_reasons=previous["reasons"] if previous else [],
        session_id=session_id,
        owner=owner,
    )
    candidate = result["candidate"]
    outcome: dict[str, Any] = {
        "evidence_id": result["evidence"]["evidence_id"],
        "evidence_type": "explicit_durable",
        "cue": candidate.get("cue"),
        "candidate_id": candidate.get("candidate_id"),
        "candidate_status": candidate.get("status"),
        "base_persona": result["evidence"]["previous_persona"],
        "proposed_persona": named_persona,
        "state": "shadow" if candidate.get("status") != "eligible" else "eligible",
    }
    if candidate.get("status") == "eligible":
        try:
            revision = store.promote(
                candidate["candidate_id"],
                authorisation={"type": "user_instruction", "evidence_id": outcome["evidence_id"]},
            )
            outcome["promotion"] = {
                "authorised_by": "user_instruction",
                "evidence_id": outcome["evidence_id"],
                "revision_id": revision["revision_id"],
                "previous_revision_id": revision.get("previous_revision_id"),
            }
            outcome["state"] = "active"
        except (KeyError, ValueError) as exc:
            logger.warning("Misumi routing promotion refused: %s", exc)
            outcome["promotion_refused"] = str(exc)
    return outcome


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
    - ``correction``: an auto route happened recently in this session and the
      new prompt still talks about the same cue - the auto choice was unwanted
      for this interaction; candidate state stays shadow;
    - ``temporary_choice``: no cue overlap - a deliberate one-off change of
      voice; never creates durable state by itself;
    - ``explicit_durable`` is handled by :func:`record_durable_instruction`.
    """
    if not persist:
        return None
    last = store.last_auto_route(session_id)
    if is_durable_instruction(prompt):
        outcome = record_durable_instruction(
            store,
            prompt=prompt,
            named_persona=chosen_persona,
            session_id=session_id,
            owner=owner,
            persist=persist,
        )
        if outcome is not None:
            return outcome
    from src.persona_capabilities import routing_intents

    cue: list[str] = []
    if last:
        cue = [
            reason for reason in last.get("reasons") or []
            if not str(reason).startswith(("fallback:", "reserved:", "learned:"))
        ]
        if not cue:
            extracted = extract_cue_term(last.get("prompt") or "", routing_intents(chosen_persona))
            cue = [extracted] if extracted else []
    if not cue:
        return None
    related = any(
        keyword_present(prompt, variant) for item in cue for variant in keyword_variants(item)
    )
    etype = "correction" if (last and related) else "temporary_choice"
    result = store.record_evidence(
        type=etype,
        cue=cue,
        previous_persona=last["persona"] if last else None,
        proposed_persona=chosen_persona,
        prompt=prompt,
        previous_route_reasons=last.get("reasons") or [] if last else [],
        session_id=session_id,
        owner=owner,
        previous_auto_route_id=last.get("request_id") if last else None,
    )
    candidate = result["candidate"]
    return {
        "evidence_id": result["evidence"]["evidence_id"],
        "evidence_type": etype,
        "cue": cue,
        "candidate_id": candidate.get("candidate_id") if isinstance(candidate, dict) else None,
        "candidate_status": candidate.get("status") if isinstance(candidate, dict) else None,
        "base_persona": last["persona"] if last else None,
        "proposed_persona": chosen_persona,
        "state": "shadow-only",
    }

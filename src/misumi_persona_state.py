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

- an explicit durable user instruction ("keep answers short from now on") is
  direct user authority for that one dimension value and promotes it;
- feedback ("too long") is a ``correction``: shadow-only; three consistent
  corrections across the evidence log make a candidate ``eligible`` awaiting
  operator ratification; confidence never bypasses the gate;
- a one-off request ("shorter please") is a ``temporary_choice``: it shapes
  THAT turn only and never creates durable state;
- reserved matters (standards, values, boundaries, ratification, Level 5/6)
  are never captured;
- every promotion first passes a deterministic evaluation (enum validity,
  bounded fixed render, foundation intact, no unresolved contradiction).

Not in this increment (carried as -10b, see MISUMI_PROGRAMME.md): knowledge-like
state (project familiarity, domain confidence, collaboration affinity,
recurring-task familiarity). Those are counters about the world, not style
selection, and need their own evidence semantics.
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
GLOBAL_SCOPE = "*"  # a durable instruction that names no persona applies household-wide
EVIDENCE_TYPES = ("correction", "temporary_choice", "explicit_durable")
EVIDENCE_WEIGHTS = {"explicit_durable": 3, "correction": 1, "temporary_choice": 0}
REPEATED_CORRECTIONS_FOR_ELIGIBLE = 3
_MAX_RENDER_CHARS = 200

_DURABLE_PHRASE = re.compile(
    r"\b(?:from\s+now\s+on|always|permanently|in\s+future|going\s+forward|forever|from\s+now)\b",
    re.IGNORECASE,
)
_RESERVED_MATTERS = re.compile(
    r"\b(?:standards?|values?|boundaries|ratif(?:y|ied|ication))\b|"
    r"\blevel\s*(?:5|five|6|six)\b",
    re.IGNORECASE,
)
_NEGATED_BEFORE = re.compile(r"\b(?:don'?t|do\s+not|not|never)\s+(?:\w+\s+){0,3}$", re.IGNORECASE)

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

    Reserved matters yield nothing. A dimension signalled with two different
    values in the same prompt is ambiguous and dropped. A request that is
    negated ("don't make it shorter") is not a signal.
    """
    text = str(prompt or "")
    if _RESERVED_MATTERS.search(text):
        return []
    found: dict[str, list[dict[str, str]]] = {}
    for dimension, value, kind, pattern in _SIGNALS:
        for match in pattern.finditer(text):
            if kind == "request" and _NEGATED_BEFORE.search(text[: match.start()]):
                continue
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
    """Evidence type for one signal: durable instruction / feedback correction / one-off request."""
    if _DURABLE_PHRASE.search(str(prompt or "")):
        return "explicit_durable"
    return "correction" if signal["kind"] == "feedback" else "temporary_choice"


class PersonaStateStore:
    """File-backed, restart-safe store for persona-state evidence, candidates and revisions."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.evidence_path = self.root / "evidence.jsonl"
        self.candidates_path = self.root / "candidates.json"
        self.revisions_path = self.root / "revisions.jsonl"
        self._lock = threading.Lock()

    # ---------- evidence ----------

    @staticmethod
    def candidate_key(persona: str, dimension: str) -> str:
        return f"{persona}|{dimension}"

    def record_evidence(self, **fields: Any) -> dict[str, Any]:
        """Append one immutable evidence event and fold it into candidate state."""
        persona = str(fields.get("persona") or "").strip().lower()
        dimension, value = fields.get("dimension"), fields.get("value")
        if not persona:
            raise ValueError("persona is required")
        if dimension not in DIMENSIONS or value not in DIMENSIONS[dimension]:
            raise ValueError(f"unknown persona-state dimension/value: {dimension!r}/{value!r}")
        if fields.get("type") not in EVIDENCE_TYPES:
            raise ValueError(f"unknown evidence type: {fields.get('type')!r}")
        prompt = str(fields.get("prompt") or "")
        if _RESERVED_MATTERS.search(prompt):
            raise ValueError("reserved matters are never captured by persona state")
        record = {
            "evidence_id": f"ps-ev-{uuid.uuid4().hex[:12]}",
            "created_at": _now(),
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
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            with self.evidence_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return {"evidence": record, "candidate": self._update_candidate(record)}

    def list_evidence(self, persona: str | None = None, dimension: str | None = None) -> list[dict[str, Any]]:
        rows = self._read_jsonl(self.evidence_path)
        return [
            row for row in rows
            if (persona is None or row.get("persona") == persona)
            and (dimension is None or row.get("dimension") == dimension)
        ]

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
            json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )

    def _update_candidate(self, evidence: dict[str, Any]) -> dict[str, Any]:
        key = self.candidate_key(evidence["persona"], evidence["dimension"])
        eid, etype, value = evidence["evidence_id"], evidence["type"], evidence["value"]
        with self._lock:
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
                    "confidence": {"score": 0, "corrections": 0,
                                   "basis": "count of supporting evidence by type (durable=3, correction=1, temporary=0), minus contradictions; never bypasses ratification"},
                    "rationale": "",
                    "created_at": _now(),
                    "updated_at": _now(),
                    "status": "shadow",
                    "awaiting": None,
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
                candidate["promotion_authorised_by"] = eid
                candidate["rationale"] = "explicit durable user instruction directly authorises this value"
                candidate.pop("rejection", None)
            elif value != candidate["proposed_value"] and candidate["supporting_evidence"]:
                candidate["contradicting_evidence"].append(eid)
                if status not in ("active", "rejected"):
                    candidate["status"] = "shadow"
                    candidate["awaiting"] = "contradicting-evidence"
            else:
                candidate["supporting_evidence"].append(eid)
                if etype == "correction":
                    candidate["confidence"]["corrections"] = candidate["confidence"].get("corrections", 0) + 1
                if (
                    status not in ("active", "rejected")
                    and candidate["confidence"].get("corrections", 0) >= REPEATED_CORRECTIONS_FOR_ELIGIBLE
                    and not candidate["contradicting_evidence"]
                ):
                    candidate["status"] = "eligible"
                    candidate["awaiting"] = "user-ratification"
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
        with self._lock:
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
        with self._lock:
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
                foundation: str = "FOUNDATION") -> dict[str, Any]:
        """Activate a candidate as a revision - evaluated, gate-checked, authorised."""
        evaluation = self.evaluate_candidate(candidate_id, foundation)
        with self._lock:
            data = self._load_candidates()
            candidate = next((c for c in data.get("candidates", {}).values()
                              if isinstance(c, dict) and c.get("candidate_id") == candidate_id), None)
            if candidate is None:
                raise KeyError(f"unknown candidate: {candidate_id}")
            if candidate.get("status") != "eligible":
                raise ValueError(f"candidate {candidate_id} is {candidate.get('status')!r}, not eligible")
            if not authorisation or not authorisation.get("type"):
                raise ValueError("promotion requires explicit authorisation")
            if authorisation["type"] == "user_instruction":
                if authorisation.get("evidence_id") not in candidate.get("supporting_evidence", []):
                    raise ValueError("user_instruction authorisation must cite supporting evidence")
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
            self._save_candidates(data)
            self.root.mkdir(parents=True, exist_ok=True)
            with self.revisions_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(revision, ensure_ascii=False, sort_keys=True) + "\n")
            return revision

    def rollback_revision(self, revision_id: str, reason: str) -> dict[str, Any]:
        """Deactivate one revision by recording its rollback. Nothing is deleted."""
        with self._lock:
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
            with self.revisions_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(rollback, ensure_ascii=False, sort_keys=True) + "\n")
            data = self._load_candidates()
            candidate = data.get("candidates", {}).get(self.candidate_key(target["persona"], target["dimension"]))
            if candidate is not None and candidate.get("status") == "active" \
                    and self.active_revision(target["persona"], target["dimension"]) is None:
                candidate["status"] = "shadow"
                candidate["awaiting"] = "rolled-back"
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
    return STYLE_HEADER + "\n" + "\n".join(f"- {line}" for line in lines)


def compose_system(foundation: str, values: dict[str, str]) -> str:
    """Foundation text first, byte-for-byte untouched; the style block is only ever appended."""
    block = style_block(values)
    return foundation if not block else f"{foundation}\n\n{block}"

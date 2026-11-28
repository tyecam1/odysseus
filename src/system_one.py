"""Finite research decisions and native System One wire adapters."""
from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlsplit

import httpx

CONTRACT = "research-system-one/v1"
Primitive = Literal["choice", "score", "noul", "rank"]
PRIMITIVES = frozenset(("choice", "score", "noul", "rank"))
_MAX_RESPONSE_BYTES = 512 * 1024
TUNERS = (
    "adversariality", "novelty_priority", "exploration", "evidence_strictness",
    "prior_art_pressure", "attribution_pressure", "industrial_grounding", "stopping_pressure",
)


class DecisionError(ValueError):
    """A typed request or reply failed validation."""


class UnsupportedPrimitive(DecisionError):
    """The provider does not implement this primitive."""


def _text(value: str) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _unit(value: float) -> float:
    if type(value) not in (int, float) or not 0 <= value <= 1:
        raise DecisionError("Expected a finite number in [0, 1]")
    return float(value)


@dataclass(frozen=True)
class Decision:
    primitive: Primitive
    state: str
    question: str
    options: tuple[tuple[str, str], ...]

    def __post_init__(self):
        if (not isinstance(self.primitive, str) or self.primitive not in PRIMITIVES
                or not _text(self.state) or not _text(self.question)):
            raise DecisionError("A supported primitive, nonempty state and question are required")
        if (not isinstance(self.options, tuple) or not 2 <= len(self.options) <= 255
                or any(not isinstance(pair, tuple) or len(pair) != 2
                       or not all(_text(value) for value in pair) for pair in self.options)):
            raise DecisionError("Expected 2–255 explicit options with nonempty keys and descriptions")
        if len(set(self.keys)) != len(self.keys):
            raise DecisionError("Duplicate options")
        if self.primitive == "noul" and self.options != (("false", "false"), ("true", "true")):
            raise DecisionError("Noul has a fixed false/true response space")
        if self.primitive == "score" and self.keys != tuple(map(str, range(len(self.options)))):
            raise DecisionError("Score options must be consecutive ordered rubric levels")
        if self.primitive == "rank" and self.keys != tuple(label for _, label in self.options):
            raise DecisionError("Rank requires explicit, unique candidate texts")

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(key for key, _ in self.options)

    @property
    def candidate_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.options, ensure_ascii=True).encode()).hexdigest()

    @property
    def size_bytes(self) -> int:
        return len(json.dumps((self.state, self.question, self.options), ensure_ascii=True))

    @classmethod
    def choice(cls, state: str, question: str, options: Mapping[str, str]) -> Decision:
        if not isinstance(options, Mapping):
            raise DecisionError("Choice requires a mapping of option keys to descriptions")
        return cls("choice", state, question, tuple(options.items()))

    @classmethod
    def score(cls, state: str, question: str, ordered_rubric: Sequence[str]) -> Decision:
        if not isinstance(ordered_rubric, Sequence) or isinstance(ordered_rubric, (str, bytes)):
            raise DecisionError("Score requires an ordered rubric")
        return cls("score", state, question, tuple((str(i), text) for i, text in enumerate(ordered_rubric)))

    @classmethod
    def noul(cls, state: str, statement: str) -> Decision:
        return cls("noul", state, statement, (("false", "false"), ("true", "true")))

    @classmethod
    def rank(cls, state: str, candidates: Sequence[str], *, question: str = "Rank the candidates") -> Decision:
        if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
            raise DecisionError("Rank requires a sequence of candidates")
        return cls("rank", state, question, tuple((candidate, candidate) for candidate in candidates))


@dataclass(frozen=True)
class Answer:
    provider: str
    model: str
    checkpoint: str
    placement: str
    probabilities: dict[str, float]
    selected: str
    confidence: float
    latency_ms: float
    usage: dict[str, int]
    expected_score: float | None = None
    estimated_cost_usd: float | None = None
    escalation_reason: str | None = None
    contract: str = CONTRACT


@dataclass(frozen=True)
class Adapter:
    provider: str
    placement: Literal["local", "remote"]
    primitives: frozenset[str]
    model: str
    checkpoint: str
    endpoint: str
    token: str | None = field(default=None, repr=False)

    def __post_init__(self):
        if self.placement == "local":
            try:
                parsed = urlsplit(self.endpoint)
                port = parsed.port
            except (AttributeError, TypeError, ValueError):
                raise DecisionError("Invalid loopback endpoint") from None
            if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}
                    or parsed.username is not None or parsed.password is not None
                    or not port or parsed.path or parsed.query or parsed.fragment):
                raise DecisionError("Local typed decision endpoint must be an HTTP loopback origin")
        elif self.placement != "remote" or self.endpoint != "https://api.typesafe.ai":
            raise DecisionError("Unrecognised typed decision endpoint")
        if (not _text(self.model) or not _text(self.checkpoint)
                or not self.primitives or not self.primitives <= PRIMITIVES):
            raise DecisionError("Typed decision adapter needs model, checkpoint and known capabilities")

    def decide(self, decision: Decision, *, timeout: float, remote_authorized: bool = False) -> Answer:
        if decision.primitive not in self.primitives:
            raise UnsupportedPrimitive(f"{self.provider} does not support {decision.primitive}")
        if self.placement == "remote" and remote_authorized is not True:
            raise DecisionError("remote_approval_required")
        if self.placement == "remote" and not self.token:
            raise DecisionError("remote_credential_unavailable")
        if not math.isfinite(timeout) or timeout <= 0:
            raise DecisionError("Expected a finite positive timeout")
        if decision.primitive == "rank":
            path = "/v1/rank"
            body = {"context": decision.state, "question": decision.question, "answers": list(decision.keys)}
        else:
            path = "/v1/systemone"
            question = {"type": decision.primitive, "instructions": decision.question}
            if decision.primitive == "choice":
                question["criteria"] = dict(decision.options)
            elif decision.primitive == "score":
                question["criteria"] = [label for _, label in decision.options]
            body = {"model": self.model, "state": decision.state, "questions": {"decision": question}}
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        started = time.monotonic()
        try:
            with httpx.Client(trust_env=False, follow_redirects=False, timeout=timeout) as client, \
                    client.stream("POST", self.endpoint + path, json=body, headers=headers) as reply:
                if reply.status_code != 200:
                    raise DecisionError(f"provider_http_{reply.status_code}")
                payload = bytearray()
                for chunk in reply.iter_bytes():
                    if len(payload) + len(chunk) > _MAX_RESPONSE_BYTES:
                        raise DecisionError("provider_response_too_large")
                    if time.monotonic() - started >= timeout:
                        raise DecisionError("provider_timeout")
                    payload.extend(chunk)
                return self.decode(decision, json.loads(payload), (time.monotonic() - started) * 1000)
        except httpx.TimeoutException:
            raise DecisionError("provider_timeout") from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise DecisionError("invalid_provider_response") from None
        except httpx.HTTPError:
            raise DecisionError("provider_unavailable") from None

    def decode(self, decision: Decision, response: dict, latency_ms: float) -> Answer:
        """Validate the closed response space before exposing any model output."""
        if decision.primitive not in self.primitives:
            raise UnsupportedPrimitive(f"{self.provider} does not support {decision.primitive}")
        try:
            model = response["model"]
            if model != self.model:
                raise DecisionError("provider_model_mismatch")
            usage = response.get("usage", {})
            if usage.get("truncated") or usage.get("state_tokens_dropped") or usage.get("truncated_questions"):
                raise DecisionError("provider_truncated_input")
            usage = {key: usage[key] for key in ("input_tokens", "output_tokens", "billing_units")
                     if key in usage and type(usage[key]) is int and usage[key] >= 0}
            reason = None
            if decision.primitive == "rank":
                rows = response["ranked"]
                raw = {row["candidate"]: row["prob"] for row in rows}
                if len(raw) != len(rows):
                    raise DecisionError("duplicate_ranked_candidate")
            else:
                answer = response["answers"]["decision"]
                if answer.get("type", decision.primitive) != decision.primitive:
                    raise DecisionError("provider_primitive_mismatch")
                if answer.get("abstention"):
                    reason = "provider_abstained"
                if decision.primitive == "noul":
                    yes = _unit(answer["noul"])
                    raw = {"false": 1 - yes, "true": yes}
                else:
                    raw = answer["probabilities"]
                    if decision.primitive == "score" and answer["legend"] != dict(decision.options):
                        raise DecisionError("provider_rubric_mismatch")
            if not isinstance(raw, dict) or set(raw) != set(decision.keys):
                raise DecisionError("provider_candidate_mismatch")
            probabilities = {key: _unit(raw[key]) for key in decision.keys}
            total = math.fsum(probabilities.values())
            if not math.isclose(total, 1, abs_tol=0.001):
                raise DecisionError("invalid_probability_distribution")
            probabilities = {key: value / total for key, value in probabilities.items()}
            selected = max(probabilities, key=probabilities.__getitem__)
            if decision.primitive == "choice" and reason is None:
                if answer["choice"] not in probabilities or probabilities[answer["choice"]] != probabilities[selected]:
                    raise DecisionError("provider_selection_mismatch")
            expected = (math.fsum(int(key) * value for key, value in probabilities.items())
                        if decision.primitive == "score" else None)
        except (AttributeError, KeyError, TypeError):
            raise DecisionError("invalid_provider_response") from None
        return Answer(self.provider, model, self.checkpoint, self.placement, probabilities, selected,
                      probabilities[selected], latency_ms, usage, expected, escalation_reason=reason)


def tuner_vector(profiles: Mapping, profile: str, overrides: Mapping | None = None) -> dict[str, float]:
    """Resolve versioned profiles with validated, partial per-run overrides."""
    if profiles.get("version") != 1 or profile not in profiles.get("profiles", {}):
        raise DecisionError("Unknown tuner profile or version")
    values = profiles["profiles"][profile]
    overrides = {} if overrides is None else overrides
    if not isinstance(values, Mapping) or set(values) != set(TUNERS):
        raise DecisionError("A profile must supply exactly the eight research tuners")
    if not isinstance(overrides, Mapping) or set(overrides) - set(TUNERS):
        raise DecisionError("Overrides may address only the eight research tuners")
    return {key: _unit(overrides.get(key, values[key])) for key in TUNERS}


def derive_behaviour(tuners: Mapping[str, float]) -> dict[str, float]:
    """Pure priority and threshold calculation with no epistemic authority."""
    return {
        "counterexample_pressure": (tuners["adversariality"] + tuners["evidence_strictness"]) / 2,
        "closest_prior_pressure": (tuners["prior_art_pressure"] + tuners["novelty_priority"]) / 2,
        "claim_conservatism": max(tuners["adversariality"], tuners["evidence_strictness"]),
        "search_breadth": tuners["exploration"],
        "comparator_scrutiny": (tuners["evidence_strictness"] + tuners["attribution_pressure"]) / 2,
        "continuation_threshold": tuners["stopping_pressure"],
    }


def configured_adapter(provider: str, placement: str, primitives: Sequence[str],
                       model: str, checkpoint: str, endpoint: str, token: str | None = None) -> Adapter:
    """Keep research state on loopback unless the exact hosted endpoint is approved."""
    return Adapter(provider, placement, frozenset(primitives), model, checkpoint, endpoint, token)

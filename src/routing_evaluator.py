"""routing_evaluator.py — the canonical replay/shadow routing evaluator
(Workstream D, docs/aoteru-long-horizon-autonomous-convergence.agent-task.md;
promised by docs/aoteru-model-host-routing-contract.md's "continuous
improvement contract", Phase C).

`core.database.RoutingDecision` has carried a comment since P-phase that
it is "not yet the full replay/shadow evaluator" — this module is that
evaluator. It reuses `RoutingDecision` (real production telemetry) and
`BenchmarkResult` (offline corpus screening, LM1-LM4) as its only sources
of truth; it does not re-derive quality/latency judgements some other way,
and it does not execute anything itself — this is read-only aggregation
over already-recorded evidence.

Scope of this first slice (deliberately bounded): per docs/aoteru-model-
host-routing-contract.md item 2, aggregate real routing telemetry by
(task_class, model_alias, concrete_model) into first-pass success rate,
verification/escalation/retry rates, and latency distribution — the
evidence base every later item (candidate-config proposals, shadow/canary
promotion, exploration gating) needs to exist before it can be meaningful.
Building a full shadow-execution replay harness (re-running historical
prompts against a *candidate* config change) is real follow-up work, not
done here — with 52 production RoutingDecision rows on record at the time
this was written, there is not yet enough traffic for a second config to
meaningfully diverge from the first; inventing that machinery now would be
speculative, not evidence-driven (see EVIDENCE_THRESHOLD below, which is
exactly the gate config/routing.yaml's own "no cosmetic exploration"
invariant asks for).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

# Below this many recorded decisions for a (task_class, model_alias) pair,
# any aggregate here is evidence-insufficient for a routing-permission
# change — report it, but never let a caller silently promote/demote a
# route from noise. This is the "define an evidence threshold rather than
# enabling exploration merely because code exists" gate the task doc asks
# for. Deliberately a small round number, not tuned against the current
# 52-row corpus — revisit once real volume exists to tune it against.
EVIDENCE_THRESHOLD = 20

# A decision older than this contributes at reduced weight to rate
# calculations (recency weighting, item 3) — routing/model behaviour can
# genuinely change (a model swap, a config edit) and stale evidence
# shouldn't out-vote what's happening now, but a full decay function needs
# more history than exists today to tune sensibly. Halving weight past 30
# days is a conservative starting point: old evidence still counts, it
# just counts less.
RECENCY_HALF_LIFE_DAYS = 30


@dataclass
class RouteAggregate:
    task_class: str
    model_alias: Optional[str]
    concrete_model: Optional[str]
    executor: str
    n: int = 0
    n_weighted: float = 0.0
    passes: float = 0.0
    verified: float = 0.0
    verification_attempts: float = 0.0
    escalations: float = 0.0
    retries_total: int = 0
    latencies_ms: list = field(default_factory=list)
    context_tokens: list = field(default_factory=list)
    paid_tokens_total: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    @property
    def evidence_sufficient(self) -> bool:
        return self.n >= EVIDENCE_THRESHOLD

    @property
    def success_rate(self) -> Optional[float]:
        return (self.passes / self.n_weighted) if self.n_weighted else None

    @property
    def verification_rate(self) -> Optional[float]:
        return (self.verified / self.verification_attempts) if self.verification_attempts else None

    @property
    def escalation_rate(self) -> Optional[float]:
        return (self.escalations / self.n_weighted) if self.n_weighted else None

    @property
    def retry_rate(self) -> Optional[float]:
        return (self.retries_total / self.n) if self.n else None

    @property
    def latency_p50_ms(self) -> Optional[float]:
        return _percentile(self.latencies_ms, 0.5)

    @property
    def latency_p95_ms(self) -> Optional[float]:
        return _percentile(self.latencies_ms, 0.95)

    @property
    def avg_context_tokens(self) -> Optional[float]:
        return (sum(self.context_tokens) / len(self.context_tokens)) if self.context_tokens else None

    def to_dict(self) -> dict:
        return {
            "task_class": self.task_class,
            "model_alias": self.model_alias,
            "concrete_model": self.concrete_model,
            "executor": self.executor,
            "n": self.n,
            "evidence_sufficient": self.evidence_sufficient,
            "success_rate": _round(self.success_rate),
            "verification_rate": _round(self.verification_rate),
            "escalation_rate": _round(self.escalation_rate),
            "retry_rate": _round(self.retry_rate),
            "latency_p50_ms": _round(self.latency_p50_ms, 0),
            "latency_p95_ms": _round(self.latency_p95_ms, 0),
            "avg_context_tokens": _round(self.avg_context_tokens, 0),
            "paid_tokens_total": self.paid_tokens_total,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


def _round(value: Optional[float], ndigits: int = 3) -> Optional[float]:
    return round(value, ndigits) if value is not None else None


def _percentile(values: list, p: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(p * (len(ordered) - 1))))
    return float(ordered[idx])


def _recency_weight(ts: Optional[datetime], *, now: datetime) -> float:
    """Exponential decay with half-life RECENCY_HALF_LIFE_DAYS. A missing
    timestamp gets full weight rather than being silently dropped — an
    unknown age must not bias the aggregate toward or away from it."""
    if ts is None:
        return 1.0
    age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
    return 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)


def aggregate_routing_decisions(decisions: list, *, now: Optional[datetime] = None) -> list[RouteAggregate]:
    """Aggregate a list of `RoutingDecision`-shaped rows (real ORM rows or
    any object with the same attributes — tests pass plain namespaces) into
    one `RouteAggregate` per (task_class, model_alias, concrete_model,
    executor). Grouping by executor too so a `local` vs `codex` route for
    the same alias never gets silently blended into one number — that
    would hide exactly the deterministic-first/qualified-local/paid
    ladder this whole routing system exists to preserve."""
    now = now or datetime.utcnow()
    groups: dict[tuple, RouteAggregate] = {}

    for d in decisions:
        key = (d.task_class, d.model_alias, d.concrete_model, d.executor)
        agg = groups.get(key)
        if agg is None:
            agg = RouteAggregate(
                task_class=d.task_class, model_alias=d.model_alias,
                concrete_model=d.concrete_model, executor=d.executor,
            )
            groups[key] = agg

        weight = _recency_weight(getattr(d, "created_at", None), now=now)
        agg.n += 1
        agg.n_weighted += weight
        if d.deterministic_gate == "pass":
            agg.passes += weight
        if d.verification_outcome is not None:
            agg.verification_attempts += weight
            if d.verification_outcome == "pass":
                agg.verified += weight
        if d.escalated:
            agg.escalations += weight
        agg.retries_total += int(d.retries or 0)
        if d.latency_ms is not None:
            agg.latencies_ms.append(d.latency_ms)
        if d.context_tokens is not None:
            agg.context_tokens.append(d.context_tokens)
        if d.paid_tokens:
            agg.paid_tokens_total += int(d.paid_tokens)

        ts = getattr(d, "created_at", None)
        if ts is not None:
            if agg.first_seen is None or ts < agg.first_seen:
                agg.first_seen = ts
            if agg.last_seen is None or ts > agg.last_seen:
                agg.last_seen = ts

    return sorted(groups.values(), key=lambda a: (a.task_class, a.model_alias or "", a.executor))


def load_and_aggregate(*, since: Optional[datetime] = None) -> list[RouteAggregate]:
    """Production entry point: reads real `RoutingDecision` rows from the
    live database (the same authority `src/estate_router.py` writes to —
    no second data source) and aggregates them. `since` bounds the query
    for a caller that only wants a recent window; recency weighting still
    applies within that window."""
    from core.database import RoutingDecision, get_db_session

    with get_db_session() as db:
        query = db.query(RoutingDecision)
        if since is not None:
            query = query.filter(RoutingDecision.created_at >= since)
        rows = query.all()
        # Detach the values we need while the session is open, so the
        # caller can use the aggregate after the session closes.
        decisions = [
            defaultdict(lambda: None, {
                "task_class": r.task_class, "model_alias": r.model_alias,
                "concrete_model": r.concrete_model, "executor": r.executor,
                "deterministic_gate": r.deterministic_gate,
                "verification_outcome": r.verification_outcome,
                "escalated": r.escalated, "retries": r.retries,
                "latency_ms": r.latency_ms, "context_tokens": r.context_tokens,
                "paid_tokens": r.paid_tokens, "created_at": r.created_at,
            })
            for r in rows
        ]
    # defaultdict supports attribute-style access via a thin shim so
    # aggregate_routing_decisions' `d.task_class` style reads work
    # uniformly whether given ORM rows or these detached dicts.
    return aggregate_routing_decisions([_AttrDict(d) for d in decisions])


def get_decision_by_id(decision_id: str) -> Optional[dict]:
    """The 'logs/result pointers surface' Workstream K's next_action asks
    for: every route/run response and RoutingDecision-referencing log
    line already hands back a `decision_id` (src.estate_router's
    `_record_decision`), but nothing let a caller look that id back up
    afterward — the only way to see a specific decision's actual recorded
    outcome was a raw DB query. Returns the full row as a plain dict (all
    columns, not the aggregated/weighted view `aggregate_routing_decisions`
    produces), or None if the id doesn't exist. Read-only — this is a
    lookup, not a second telemetry authority."""
    from core.database import RoutingDecision, get_db_session

    with get_db_session() as db:
        row = db.query(RoutingDecision).filter(RoutingDecision.id == decision_id).first()
        if row is None:
            return None
        return {
            "id": row.id,
            "task_class": row.task_class,
            "complexity": row.complexity,
            "consequence": row.consequence,
            "host_id": row.host_id,
            "executor": row.executor,
            "model_alias": row.model_alias,
            "concrete_model": row.concrete_model,
            "context_tokens": row.context_tokens,
            "paid_tokens": row.paid_tokens,
            "latency_ms": row.latency_ms,
            "deterministic_gate": row.deterministic_gate,
            "retries": row.retries,
            "escalated": row.escalated,
            "escalation_reason": row.escalation_reason,
            "verification_outcome": row.verification_outcome,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


class _AttrDict:
    def __init__(self, data: dict):
        self._data = data

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name)

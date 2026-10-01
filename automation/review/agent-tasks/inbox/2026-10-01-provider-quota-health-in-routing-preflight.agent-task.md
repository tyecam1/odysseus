---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-01-provider-quota-health-in-routing-preflight
title: "Represent provider/model quota exhaustion truthfully in routing and delegation preflight"
status: inbox
priority: high
task_type: implementation
created_by: claude
created_at: 2026-10-01T14:00:00+01:00
updated_at: 2026-10-01T14:00:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single
architecture_rationale: "One defect in how the existing estate router, delegation preflight and execution lane represent provider health. The fix extends those existing owners; it must not create another router, queue or lease authority."
single_agent_baseline: "A single implementation owner can reproduce the incident with a fake provider that emits the real usage-limit text, extend the existing provider-health representation, and cover it with deterministic tests."
execution_host: compute-box
context_budget: medium
coordination_reason: "Part of the Misumi long-horizon programme (misumi-long-horizon-programme@v1). Touches estate routing/preflight only; keep clear of the multihost integration branch until it has merged."
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - src/**
  - routes/**
  - scripts/**
  - config/**
  - tests/**
  - docs/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
inputs:
  - src/delegation_preflight.py
  - src/estate_router.py
  - routes/estate_routing_routes.py
  - the incident below
  - automation/review/agent-tasks/inbox/2026-09-28-persistent-blocked-route-rerouting-long-horizon.agent-task.md
outputs:
  - provider/model quota state represented in routing and preflight, distinct from host and worker availability
  - deterministic regression tests
  - minimal contract/doc update
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Sol review for this programme is retrospective and non-blocking (operator policy 2026-10-01)."
---

# Represent provider/model quota exhaustion truthfully in routing and preflight

## Incident (reproducible evidence)

2026-10-01, lab host `hz2-workstation`. `aoteru preflight` reported Codex as available (`"codex": {"available": true, "reason": "live"}`) and recommended `codex-write` on lab. The subsequent implementation dispatch under a fresh ParkLease (execution `8a65072e-192a-476f-b5aa-ce35e6d51e5e`, `decision_id` `17b7cf05-e59f-4ae9-b7c9-7a0e357e5048`) failed in about 4 seconds with:

`ERROR: You've hit your usage limit ... try again at 5:39 PM.`

The route was reported as `escalation_reason: worker_failed`, `deterministic_gate: fail`. Nothing in preflight or routing could have predicted the failure or avoided the known-dead provider on the next attempt.

## Defect

"Live" currently means the executor binary exists and starts. It says nothing about whether the provider/model behind it will accept work. Three different availabilities are conflated:

1. **host availability** — is the machine reachable and enrolled as an eligible worker;
2. **worker/runtime availability** — is the estate worker protocol and its deterministic/local executors healthy;
3. **provider/model quota availability** — will a given paid provider (Codex, others) accept a request now.

A depleted provider must never make the whole host look unavailable, and must also never be reported as live.

## Required work

1. Reproduce deterministically with a fake Codex executable that emits the real usage-limit text and exits non-zero.
2. Add an explicit per-provider health state to the existing provider/executor representation (for example `ok | quota_exhausted | auth_failed | unreachable`) with an optional `retry_after`, derived from observed execution outcomes and, where cheap and safe, a bounded probe. Parse the provider's usage-limit message robustly, including its stated reset time; if the time cannot be parsed, apply a conservative bounded backoff and say so.
3. Surface it in `aoteru preflight`, `/api/estate/preflight`, `agent status` and routing explanations as a provider-scoped fact. Preflight must not recommend a route whose provider is `quota_exhausted` before `retry_after`; it should name an eligible alternative route (deterministic or another qualified route) when one exists, or state the specific blocked condition.
4. Keep host eligibility and worker health unchanged by provider quota. Lab must remain an eligible worker while Codex is quota-exhausted.
5. Record quota-exhaustion in the routing telemetry that already exists; never create a new store, queue or lease authority. Reuse the persistent blocked-route/rerouting contract once it lands rather than inventing a parallel one.
6. Never relax authority: an alternative route may not widen write authority, skip a reserved verification gate, or silently substitute a weaker model for a reserved gate; it must fail closed and say why.
7. A recovered provider (successful execution or elapsed `retry_after` plus successful probe) returns to `ok` without manual intervention.

## Acceptance

- With the fake exhausted provider, preflight reports `quota_exhausted` with `retry_after`, does not recommend that route, and keeps lab host/worker eligible.
- A repeated dispatch against the known-dead provider is refused fast with a provider-scoped reason instead of burning an attempt.
- Unparseable reset text falls back to the documented bounded backoff.
- After `retry_after` and a successful execution the provider returns to `ok`.
- No change to ParkLease or EstateExecution semantics; existing routing, lease, execution and preflight suites pass.

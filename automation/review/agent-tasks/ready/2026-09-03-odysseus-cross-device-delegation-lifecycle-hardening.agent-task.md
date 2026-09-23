---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-03-odysseus-cross-device-delegation-lifecycle-hardening
title: "Harden Odysseus cross-device delegation and execution observation"
status: ready
priority: high
task_type: implementation
created_by: gpt-5.6-sol
created_at: 2026-09-03T02:00:00+01:00
updated_at: 2026-09-03T02:00:00+01:00
executor: codex_subscription
execution_mode: review-first
architecture: single
architecture_rationale: "This is one lifecycle-contract defect spanning an existing Odysseus execution path. One implementation owner should preserve the current routing, ParkLease, LogicalSession and EstateExecution authorities rather than creating another queue or orchestration layer."
single_agent_baseline: "One Codex implementation worker can audit the existing dispatch, status, session and laptop-client surfaces, implement the smallest coherent fix, and run deterministic regression tests."
execution_host: compute-box
context_budget: medium
coordination_reason: "Do not parallelise implementation across session, CLI and execution-state owners because the defect is primarily an authority-boundary and lifecycle-semantics problem. Use independent verification only after the implementation is coherent."
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths: []
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
  - config/models.yaml
  - config/estate.yaml
inputs:
  - src/estate_router.py
  - routes/estate_routing_routes.py
  - scripts/agent
  - companion/laptop_client/aoteru.py
  - docs/aoteru-model-host-routing-contract.md
  - September 2026 acceptance incident: lease a66e12fd-cc6d-4c3f-bd47-e79027b5ab7e and executions af70beb7-85a0-47df-b21f-8c55ee3b444b, d29bc33d-aeee..., da4feb52-4578..., 6d04670b-b41a-4799-a16a-9244fc64950c
  - automation/review/agent-tasks/blocked/2026-06-19-odysseus-remote-compute-dispatch-guard.agent-task.md
outputs:
  - first-class read-only execution status/wait surface for an existing EstateExecution
  - dispatch/status UX that cannot confuse a new dispatch with polling
  - bounded remote-session/monitor outcomes with no indefinite wait
  - regression tests reproducing the September 2026 sequential redispatch incident
  - minimal documentation/contract updates
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol-independent-review
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Do not solve this by extending timeouts, adding another task queue, or making Claude Remote Control authoritative for work state. PR #33 admission control is not currently shown defective: the four observed paid executions were sequential and non-overlapping. The defect is the operational ability to use a dispatch command as a pseudo-poll, plus a monitor lifecycle that can remain unresolved after authoritative execution has terminated."
---

# Harden Odysseus cross-device delegation and execution observation

## Objective

Eliminate ambiguous and indefinite waiting in cross-device delegation while preserving the existing authority chain:

`conversation/session -> Odysseus routing -> ParkLease -> EstateExecution`

Claude Remote Control and cross-session messaging are transport/coordination surfaces only. They must not become execution-state authority.

## Ground truth

The September 2026 acceptance run produced four real Codex executions under one ParkLease. Database chronology showed each new execution was submitted only after the preceding execution had finished. No two executions were simultaneously `accepted` or `running`.

Therefore:

- the existing one-non-terminal-execution-per-active-lease admission invariant is not disproven;
- repeated `aoteru ask` calls were incorrectly used as polling;
- while an execution is non-terminal, `ask` may reuse it;
- once it becomes terminal, another `ask` is a legitimate fresh dispatch;
- a polling loop built from `ask` can therefore chain sequential paid executions indefinitely;
- the conversational monitor can remain open even after EstateExecution and OS process state are terminal.

Do not misclassify this as objective-level idempotency or as evidence of concurrent-write admission failure.

## Required work

1. Audit the existing HTTP, CLI, laptop-client and session surfaces before changing code. Reuse the authoritative `GET /api/estate/run/{execution_id}` / `get_estate_execution()` lifecycle rather than creating parallel state.
2. Add a first-class authenticated read-only CLI/client command for inspecting an existing execution by `execution_id`, with an optional bounded wait-to-terminal mode.
3. Make dispatch and observation operationally distinct. `aoteru ask` must never be documented, wrapped or internally reused as a polling mechanism.
4. Ensure every accepted/running implementation response exposes the execution ID and the canonical next status action clearly enough that an agent can continue without redispatching.
5. Audit `LogicalSession` and Remote Control integration. Keep session identity/reachability separate from EstateExecution state and ensure held, refused, disconnected or non-responsive remote peers resolve to explicit bounded outcomes rather than indefinite monitors.
6. Preserve ParkLease as the only repo-write authority and EstateExecution as the only durable implementation-execution lifecycle authority.
7. Reconcile with the existing remote-compute dispatch/liveness work. Extend existing diagnostics/liveness where appropriate instead of creating duplicate mechanisms.
8. Add deterministic regression coverage for the September incident and for cross-device/session failure modes that can be simulated without paid inference.

## Acceptance criteria

A clean bounded integration test must prove all of the following:

- one implementation dispatch creates execution `E`;
- one deliberate duplicate dispatch while `E` is non-terminal returns the same `E` and creates no second worker;
- zero further dispatch calls are required to observe `E`;
- the read-only status/wait surface observes `E` through its real persisted lifecycle to a terminal state;
- a new dispatch after `E` is terminal creates a new execution and is reported as a new dispatch, not a reused in-flight execution;
- the September polling pattern cannot accidentally create sequential paid executions when using the documented/client-supported status workflow;
- remote-session loss, refusal, disconnection or non-response reaches an explicit bounded terminal/communication outcome rather than an indefinite monitor;
- session reachability does not overwrite or substitute for persisted EstateExecution state;
- no overlapping non-terminal implementation executions are possible under one active lease;
- no new queue, lease authority, session authority or competing lifecycle store is introduced;
- existing routing, lease, execution and regression suites pass.

## Verification

Use a fresh lease and a bounded no-value acceptance objective. Capture request/response timestamps, execution IDs, persisted lifecycle transitions, worker PID/process group and lease history so dispatch creation and reuse can be distinguished exactly.

Do not use repeated dispatch calls as observation. Do not spend paid calls merely to exercise polling behaviour that can be tested deterministically.

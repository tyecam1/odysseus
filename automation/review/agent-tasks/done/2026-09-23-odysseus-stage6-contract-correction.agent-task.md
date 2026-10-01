---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-23-odysseus-stage6-contract-correction
title: "Correct Odysseus Stage 6 lifecycle contract before implementation"
status: done
migrated_from_repo: tyecam1/obsidian-PhD
migrated_from_pr: 570
migration_note: "Task executed before repository-ownership migration; retained here as backend provenance."
priority: high
task_type: contract-repair
created_by: gpt-5.6-sol
created_at: 2026-09-23T09:00:00+01:00
updated_at: 2026-09-23T09:00:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single
architecture_rationale: "Stages 1-5 are converged. This task fixes the final Stage 3 nonce-classification mismatch and removes unsafe ambiguity from the Stage 6 lifecycle contract before any Stage 6 implementation begins."
single_agent_baseline: "One fresh Sonnet session should make the bounded Stage 3 nonce fix, correct the Stage 6 plan/tests, run the pre-Stage-6 baseline, and stop."
execution_host: compute-box
context_budget: medium
coordination_reason: "Do not carry implementation momentum into Stage 6 until ambiguous remote-start and reconciliation semantics are resolved in the contract."
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
branch: feat/multihost-stage1-3-20260922
allowed_paths:
  - src/estate_worker_client.py
  - src/estate_worker_protocol.py
  - src/estate_router.py
  - docs/aoteru-multihost-execution-implementation-plan.md
  - tests/test_estate_worker_client.py
  - tests/test_estate_worker_protocol.py
  - tests/test_estate_router.py
denied_paths:
  - core/database.py
  - routes/**
  - companion/**
  - config/estate.yaml
  - config/models.yaml
  - scripts/windows/odysseus-host.ps1
inputs:
  - tyecam1/odysseus branch feat/multihost-stage1-3-20260922 at/after c9bdafb
  - docs/aoteru-multihost-execution-implementation-plan.md
  - established pre-Stage-6 lifecycle baseline
outputs:
  - bounded Stage 3 nonce-classification repair
  - corrected Stage 6 lifecycle contract and test expectations
  - passing pre-Stage-6 lifecycle baseline
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol-independent-review
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Do not run or spend /ultrareview. Do not implement Stage 6. Do not modify EstateExecution/ParkLease schema or lifecycle code."
---

# Correct Stage 6 lifecycle contract before implementation

## Authority and starting state

Work from the live branch:

`feat/multihost-stage1-3-20260922`

at or after:

`c9bdafb`

Read:

`docs/aoteru-multihost-execution-implementation-plan.md`

The existing Opus architecture remains authoritative:
- one lab control plane;
- thin DB-free workers;
- ParkLease is the only write authority;
- EstateExecution is the only execution-lifecycle authority;
- route.host must equal the machine that physically executes work;
- no alternate-host or backend-local fallback.

This task is a **bounded contract-correction pass**. Do not begin Stage 6 implementation.

## 1. Fix the remaining Stage 3 nonce-mismatch contract drift

The Stage 3 plan says an attestation host/nonce/fingerprint mismatch must fail as:

- `error_code: placement_mismatch`;
- `RoutingDecision.status = failed`;
- `executed: false`;
- `executed_host_id = null`;
- observed host retained in `actual_route=placement_mismatch:<attested-host>` where available.

Current live behaviour still classifies a nonce mismatch as `worker_protocol_error` because `call_worker()` invokes `validate_response()` before `verify_attestation()`, and `validate_response()` rejects the nonce echo first.

Reconcile `validate_response()` and `verify_attestation()` so the real `call_worker()` path satisfies the Stage 3 contract.

Requirements:
- malformed response envelopes and request-id mismatches remain protocol errors;
- nonce mismatch is treated as an attestation/placement mismatch;
- host-id/fingerprint mismatches remain placement mismatches;
- retain `observed_host_id` where available;
- no successful execution may be inferred from any mismatch;
- do not widen the wire protocol unnecessarily.

Add/update client-level and route/telemetry-level regression tests.

## 2. Correct Stage 6 handling of an ambiguous remote `start`

The current Stage 6 plan says that a transport failure from:

`call_worker(host_id, "start", ...)`

can immediately mark the EstateExecution row `failed` because nothing started.

That is unsafe. The worker may have:
1. created the execution spool;
2. spawned the detached writer;
3. lost the SSH response before the control plane received it.

The same `execution_id` is deliberately idempotent at the worker, so an uncertain `start` response must not reopen write admission.

Amend Stage 6 so:

- the control plane never assumes a failed/lost `start` response means no process started;
- it retries/observes using the **same execution_id**;
- worker `start` idempotency and `status` are used to resolve uncertainty;
- no second execution is admitted under the same lease while the first remains unresolved;
- only positive evidence that no execution exists / cannot have started may transition the row to a terminal non-running state;
- U17 explicitly proves one spawn when the first `start` response is lost.

Keep dispatch and observation separate. Do not introduce a queue or second lifecycle store.

## 3. Distinguish new Stage-6 pre-handle rows from legacy rows

Stage 6 deliberately creates the durable EstateExecution row before remote `start`.

Therefore, after Stage 6 exists:

`worker_handle_json == NULL`

cannot safely mean “legacy pre-Stage-6 execution.”

A backend crash between row creation and confirmed `start`, or an ambiguous `start` response, can produce a **new Stage-6 execution** with no confirmed handle yet.

Amend the Stage 6 contract with the smallest durable dispatch-state marker.

Preferred minimal pattern:
- new Stage-6 rows are durably marked as worker-protocol executions immediately on creation, e.g. a non-null `worker_handle_json` placeholder such as a protocol/dispatch-state object;
- once `start` is confirmed, replace/update that marker with the real worker handle;
- `NULL` remains distinguishable as a true legacy row.

Equivalent designs are acceptable only if they preserve the same crash-recovery distinction without adding another authority/store.

This task should update the plan/test expectations only; do **not** implement the Stage 6 database/schema changes yet.

## 4. Define reachable-worker / dead-runner reconciliation

The worker can truthfully report:

- stored state `accepted` or `running`; and
- `process_alive: false`.

When the worker is reachable, this is not an unknown/lost execution: the host has been observed and the detached runner is known dead before writing a terminal spool state.

Amend Stage 6 reconciliation semantics:

- reachable worker + accepted/running + `process_alive: false` -> promptly transition EstateExecution to `interrupted`;
- unreachable worker / outcome cannot currently be observed -> remain unresolved and eventually `lost` according to the bounded observation rule;
- `lost` means **outcome cannot currently be determined**, not simply “process no longer alive”;
- if a later worker observation resolves a `lost` execution, reconcile it to the truthful spool/process state;
- no redispatch occurs merely because an execution became `lost` or `interrupted`.

Update U19-U22 and I4-I6 expectations so these distinctions are explicit.

## 5. Preserve the Stage 6 authority boundary

Ensure the corrected plan keeps this invariant explicit:

> The control plane proves ParkLease authority before issuing remote `worktree.verify`, `start`, or `worktree.finalize`. The worker remains DB-free and never decides lease validity, routing, or lifecycle authority.

The lease payload sent to the worker is evidence/instruction from the authenticated control plane, not an independent worker-side lease authority.

## Verification

Run directly affected worker/client/router tests.

Then run the established pre-Stage-6 lifecycle baseline:

```bash
venv/bin/python -m pytest \
  tests/test_estate_router.py \
  tests/test_estate_execution_runtime.py \
  tests/test_estate_routing_routes.py \
  tests/test_park_lease_ops.py \
  tests/test_laptop_client.py \
  tests/test_agent_cli_parking_lease.py \
  tests/test_routing_decision_lookup.py \
  tests/test_routing_evaluator.py \
  tests/test_estate_worker*.py -q
```

The prior accepted baseline was 284 passed. Any difference must be explained and any regression introduced by this task fixed before completion.

## Guardrails

- Do **not** begin Stage 6 implementation.
- Do **not** modify `core/database.py`.
- Do **not** modify EstateExecution or ParkLease schema/lifecycle code.
- Do **not** enable home.
- Do **not** modify `config/estate.yaml` or `config/models.yaml`.
- Do **not** touch the household/Misumi deployment.
- Do **not** introduce alternate-host or in-process fallback.
- Do **not** run or spend `/ultrareview`.
- If a finding is incorrect against the live branch, report evidence rather than forcing a change.

## Completion

Commit and push the corrections on the same implementation branch.

Then stop.

Report:
- commit SHA(s);
- files changed;
- nonce-mismatch behaviour after repair;
- exact lifecycle-baseline result;
- exact Stage 6 contract changes for ambiguous `start`, pre-handle rows, and interrupted vs lost;
- any remaining blocker;
- whether the Stage 6 plan is now safe for a separately scoped implementation task.

Do not proceed into Stage 6.

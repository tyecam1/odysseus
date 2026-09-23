---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-22-odysseus-prestage6-convergence
title: "Close final pre-Stage-6 Odysseus multihost gaps"
status: done
migrated_from_repo: tyecam1/obsidian-PhD
migrated_from_pr: 569
migration_note: "Task executed before repository-ownership migration; retained here as backend provenance."
priority: high
task_type: implementation-repair
created_by: gpt-5.6-sol
created_at: 2026-09-22T22:21:00+01:00
updated_at: 2026-09-22T22:21:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single
architecture_rationale: "Stages 1-5 are substantially sound after PR #568 repairs. This task closes the remaining contract/telemetry/documentation gaps and establishes a clean lifecycle baseline before any Stage 6 work."
single_agent_baseline: "One fresh Sonnet session can complete this bounded convergence pass on the existing implementation branch."
execution_host: compute-box
context_budget: medium
coordination_reason: "Do not continue implementation momentum into Stage 6. Close only the remaining reviewed gaps, verify the lifecycle baseline, then stop."
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: feat/multihost-stage1-3-20260922
allowed_paths:
  - src/estate_router.py
  - src/estate_worker_client.py
  - docs/aoteru-home-worker-setup.md
  - docs/aoteru-multihost-execution-implementation-plan.md
  - tests/test_estate_router.py
  - tests/test_estate_worker_client.py
  - tests/test_estate_execution_runtime.py
  - tests/test_estate_routing_routes.py
  - tests/test_park_lease_ops.py
  - tests/test_laptop_client.py
  - tests/test_agent_cli_parking_lease.py
  - tests/test_routing_decision_lookup.py
  - tests/test_routing_evaluator.py
  - tests/test_estate_worker.py
  - tests/test_estate_worker_procs.py
  - tests/test_estate_worker_protocol.py
denied_paths:
  - core/database.py
  - config/models.yaml
  - config/estate.yaml
  - routes/**
  - companion/**
  - scripts/windows/odysseus-host.ps1
inputs:
  - tyecam1/odysseus branch feat/multihost-stage1-3-20260922 at/after aaa1521
  - docs/aoteru-multihost-execution-implementation-plan.md
  - prior Stage 3-5 convergence repair commits 6579bc1 5f6610d 0410323 aaa1521
outputs:
  - final pre-Stage-6 convergence commits on feat/multihost-stage1-3-20260922
  - isolated lifecycle baseline test result
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol-independent-review
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Do not run or spend /ultrareview. Do not begin Stage 6. Do not modify EstateExecution/ParkLease schema or lifecycle behaviour."
---

# Final pre-Stage-6 convergence

## Authority and starting state

Work from the live branch:

`feat/multihost-stage1-3-20260922`

at or after:

`aaa1521`

Read:

`docs/aoteru-multihost-execution-implementation-plan.md`

The Opus plan remains architecture authority. Stages 1-5 are substantially implemented; this task closes only the remaining review findings before Stage 6.

Use a fresh Sonnet session but the existing implementation branch/worktree.

## Required repairs

### 1. Correct RoutingDecision state for post-route dispatch failure

The Stage 3 plan explicitly requires a transport/protocol/pre-execution worker failure after routing to produce:

- `executed: false`;
- `ok: false`;
- `escalation_reason: worker_failed`;
- `RoutingDecision.status = failed`;
- `executed_host_id = null`;
- no retry, alternate-host fallback or in-process fallback.

Current repaired code correctly sets `executed: false` but records `status="blocked"`.

Change both:
- local read-only dispatch failure; and
- paid/Codex read-only dispatch failure

to record `status="failed"`.

Update regression tests so they enforce `failed`, not `blocked`.

Do not alter genuinely pre-execution admission/authority failures that correctly remain `blocked`.

### 2. Preserve placement-mismatch provenance

The Stage 3 plan requires attestation mismatch to fail closed and retain the worker identity actually observed:

- `error_code: placement_mismatch`;
- `executed: false`;
- `executed_host_id = null`;
- `actual_route = "placement_mismatch:<attested-host>"`.

Currently `verify_attestation()` detects the mismatched attested host, but `WorkerTransportError` loses that structured provenance before `_dispatch_read_only()`/telemetry can record it.

Implement the smallest backwards-compatible change so a placement mismatch can carry the actual attested host through the client boundary without treating it as successful execution.

Requirements:
- no widening of the worker protocol;
- no alternate execution;
- normal transport errors need not carry an attested host;
- fingerprint mismatch should retain enough attestation context to diagnose the mismatch where available;
- routing telemetry records `actual_route=placement_mismatch:<observed-host>` when an observed host identity exists.

Add tests covering the route-level telemetry, not only `call_worker()` raising the correct error code.

### 3. Update stale Stage 4 details in the architecture plan

The implementation/runbook now correctly uses:
- an explicit `cmd.exe /c cd /d <checkout> && <venv-python> -m src.estate_worker --root <checkout>` forced-command entrypoint; and
- a home-local `~/.aoteru/worker_selftest_enabled` sentinel for the bounded `noop-sleep` survival test.

The architecture plan still describes the superseded environment-variable mechanism and less robust forced command.

Update only the relevant Stage 4 operational details in:

`docs/aoteru-multihost-execution-implementation-plan.md`

so future agents are not instructed to reintroduce the broken mechanism.

Do not rewrite the architecture or later stages.

### 4. Complete the Windows OpenSSH runbook notes

In:

`docs/aoteru-home-worker-setup.md`

add the minimal operator note for administrator-account `administrators_authorized_keys` ACLs so Windows OpenSSH will accept the key.

Also make explicit that:
- the sentinel file;
- `~/.aoteru/config.local.json`; and
- the forced-command worker process

must all belong to / resolve under the **same Windows account configured in `worker.ssh.target`**.

Keep this operational/documentation-only. Do not modify estate config or enable home.

### 5. Strengthen the repo-locality test

The current auto-routing repo-locality test has lab first in estate order and lab is also the host with the repo, so it does not independently prove that a higher-priority host missing the repo is skipped.

Add one adversarial test where:
- the first candidate in estate order is healthy/model-capable but lacks the requested repo;
- the second candidate has the repo;
- auto routing selects the second candidate.

Keep the existing explicit-host/no-candidate tests.

## Lifecycle baseline before Stage 6

After the repairs, run this combined pre-Stage-6 suite:

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

This suite must be treated as the lifecycle baseline for Stage 6.

If it fails:
1. identify whether each failure also reproduces at pre-task HEAD `aaa1521`;
2. repair any regression introduced by this task;
3. report any genuine pre-existing failure explicitly rather than silently accepting it.

A full `tests/` run is useful but not a substitute for this combined lifecycle baseline.

## Guardrails

- Do **not** begin Stage 6.
- Do **not** modify `EstateExecution` or `ParkLease` schema/lifecycle semantics.
- Do **not** modify `core/database.py`.
- Do **not** enable home.
- Do **not** modify `config/models.yaml` or `config/estate.yaml`.
- Do **not** touch the household/Misumi deployment.
- Do **not** introduce fallback execution.
- Do **not** run or spend `/ultrareview`.
- Preserve one lab control plane and thin DB-free workers.

## Stage 6 invariant to carry forward

Do not implement Stage 6 in this task, but preserve this invariant for the handoff:

> The control plane must prove ParkLease authority before issuing any remote `worktree.verify`, `start`, or `worktree.finalize` operation. The worker remains DB-free and never becomes a lease or lifecycle authority.

## Completion

Commit and push the repairs on the same implementation branch.

Then stop.

Report:
- commit SHA(s);
- files changed;
- exact combined lifecycle baseline result;
- full-suite result if run;
- any pre-existing failures reproduced at `aaa1521`;
- any remaining blocker;
- whether the branch is ready for a separately scoped Stage 6 implementation task.

Do not proceed into Stage 6.

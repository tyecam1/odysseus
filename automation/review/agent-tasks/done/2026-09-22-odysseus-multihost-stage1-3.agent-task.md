---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-22-odysseus-multihost-stage1-3
title: "Implement Odysseus truthful multihost execution stages 1-3"
status: done
migrated_from_repo: tyecam1/obsidian-PhD
migrated_from_pr: 566
migration_note: "Task executed before repository-ownership migration; retained here as backend provenance."
priority: high
task_type: implementation
created_by: gpt-5.6-sol
created_at: 2026-09-22T17:10:00+01:00
updated_at: 2026-09-22T17:10:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single
architecture_rationale: "Opus has already fixed the architecture in the multihost execution plan. Sonnet should now implement the first bounded tranche mechanically without reopening architectural decisions."
single_agent_baseline: "One Sonnet implementation worker can complete stages 1-3 sequentially with separate commits and deterministic tests."
execution_host: compute-box
context_budget: medium
coordination_reason: "Keep one implementation owner across the three tightly coupled stages. Stop before Windows/home transport so Stage 3 can be independently reviewed before introducing cross-host complexity."
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
allowed_paths:
  - config/estate.yaml
  - config/routing.yaml
  - docs/aoteru-model-host-routing-contract.md
  - src/estate_router.py
  - src/estate_worker_protocol.py
  - src/estate_worker_procs.py
  - src/estate_worker.py
  - src/estate_worker_client.py
  - core/database.py
  - src/routing_evaluator.py
  - tests/test_estate_router.py
  - tests/test_estate_worker_protocol.py
  - tests/test_estate_worker.py
  - tests/test_estate_worker_client.py
  - tests/test_estate_execution_runtime.py
  - tests/test_estate_routing_routes.py
  - tests/test_laptop_client.py
  - tests/test_park_lease_ops.py
  - tests/test_agent_cli_parking_lease.py
  - tests/test_routing_decision_lookup.py
  - tests/test_routing_evaluator.py
denied_paths:
  - scripts/windows/odysseus-host.ps1
  - config/models.yaml
  - companion/**
  - routes/**
  - app.py
  - docker/**
  - "**/docker-compose*"
inputs:
  - tyecam1/odysseus branch plan/multihost-execution-20260922 commit 71e3fe1f43313f89f427645d5afb3bb814023ba4
  - docs/aoteru-multihost-execution-implementation-plan.md
  - current origin/dev
outputs:
  - stage 1 implementation commit
  - stage 2 implementation commit
  - stage 3 implementation commit
  - passing stage tests and combined relevant regression suite
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol-independent-review
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Implement only Stages 1-3. Do not start Stage 4, enable home, or improvise architecture. The Opus plan is authoritative except where live code materially contradicts it."
---

# Implement truthful multihost execution: Stages 1-3

## Authority

Use:

`tyecam1/odysseus:plan/multihost-execution-20260922`

commit:

`71e3fe1f43313f89f427645d5afb3bb814023ba4`

document:

`docs/aoteru-multihost-execution-implementation-plan.md`

as the architecture authority.

Do not redesign the architecture.

Start from **current `origin/dev`** in a fresh implementation worktree and branch. Never implement in the live checkout `/home/agent/projects/odysseus-aoteru`.

## Scope

Implement **Stages 1, 2 and 3 only**, in that order.

### Stage 1

Implement the plan's truthful host-state semantics and associated contract/config/test changes.

Required invariant after Stage 1:

- lab eligibility remains functionally unchanged;
- home remains ineligible;
- identity verification does not imply worker qualification or enablement.

Commit Stage 1 separately.

### Stage 2

Implement the worker protocol, worker entry point and Linux process layer exactly as specified in the plan.

Required invariants:

- worker never imports `core.database`;
- worker does not route, lease or own lifecycle state;
- `start` is idempotent per `execution_id`;
- identity mismatch refuses before execution.

Commit Stage 2 separately.

### Stage 3

Route lab read-only execution through the worker contract and add truthful execution-host telemetry.

Required invariants:

- `run_task()` no longer executes local inference or read-only Codex directly in the control-plane process;
- `route.host == attested physical execution host`;
- worker/transport/attestation failure fails closed;
- there is no backend-local or alternate-host fallback;
- implementation/write mode remains on the existing guarded path for now;
- home remains disabled.

Commit Stage 3 separately.

## Execution rules

1. Read the entire implementation plan before editing.
2. Follow the plan's exact file/function guidance and tests for Stages 1-3.
3. Do not implement Stage 4 or later.
4. Do not modify `config/models.yaml`, enable home, add Windows SSH transport, change the household/Misumi service, merge effort-routing work, or broaden scope.
5. If current live code materially contradicts a plan assumption, stop at that point and report the contradiction with evidence. Do not silently substitute another architecture.
6. Infrastructure failures are blockers, not reasons to weaken fail-closed behaviour.
7. Keep commits logically separated:
   - `stage 1: truthful host state semantics`
   - `stage 2: add estate worker contract`
   - `stage 3: route lab execution through worker`

## Verification

After each stage, run the tests listed for that stage in the plan.

After Stage 3, run the combined relevant suite from the plan:

```bash
venv/bin/python -m pytest tests/test_estate_router.py tests/test_estate_execution_runtime.py \
  tests/test_estate_routing_routes.py tests/test_laptop_client.py tests/test_park_lease_ops.py \
  tests/test_agent_cli_parking_lease.py tests/test_routing_decision_lookup.py tests/test_routing_evaluator.py \
  tests/test_estate_worker*.py -q
```

Do not claim completion from selective tests if this combined suite fails.

## Stop condition

Stop after Stage 3.

Report:

- implementation branch;
- Stage 1, 2 and 3 commit SHAs;
- tests run and exact result;
- deviations from the plan, if any;
- discovered adjacent issues;
- whether the Stage 3 branch is ready for independent review.

Do not proceed to Stage 4.

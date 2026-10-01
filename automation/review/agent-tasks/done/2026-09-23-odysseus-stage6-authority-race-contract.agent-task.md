---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-23-odysseus-stage6-authority-race-contract
title: "Close final Odysseus Stage 6 authority and race-contract gaps"
status: done
migrated_from_repo: tyecam1/obsidian-PhD
migrated_from_pr: 573
migration_note: "Task executed before repository-ownership migration; retained here as backend provenance."
priority: high
task_type: contract-repair
created_by: gpt-5.6-sol
created_at: 2026-09-23T12:09:00+01:00
updated_at: 2026-09-23T12:09:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single
architecture_rationale: "Stages 1-5 are converged. This final pre-implementation pass resolves the remaining Stage 6 race and authority semantics around dirty worktrees, recovery, lease serialization and idempotent start."
single_agent_baseline: "One fresh Sonnet session should inspect the live branch and update only the Stage 6 plan/test contract, then run the established pre-Stage-6 baseline and stop."
execution_host: compute-box
context_budget: medium
coordination_reason: "Do not implement Stage 6 until the write-authority state machine is complete under process termination, lease races and ambiguous starts."
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
  - docs/aoteru-multihost-execution-implementation-plan.md
denied_paths:
  - core/database.py
  - src/**
  - routes/**
  - companion/**
  - config/**
  - scripts/**
  - tests/**
inputs:
  - tyecam1/odysseus branch feat/multihost-stage1-3-20260922 at/after ad1e55b
  - docs/aoteru-multihost-execution-implementation-plan.md
  - current ParkLease, EstateExecution, worker start/status and worktree preparation implementations as inspection evidence only
outputs:
  - final corrected Stage 6 authority/lifecycle/race contract
  - final Stage 6 unit/integration acceptance matrix
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol-independent-review
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Contract-only pass. Do not implement Stage 6. Do not run or spend /ultrareview."
---

# Final Stage 6 authority/race contract correction

## Authority and starting state

Work from the live branch:

`feat/multihost-stage1-3-20260922`

at or after:

`ad1e55b`

Read:

`docs/aoteru-multihost-execution-implementation-plan.md`

Inspect the current implementations of:
- `ParkLease` / `park_lease_is_stale`;
- `src/park_lease_ops.py`;
- `EstateExecution`;
- `src/estate_router.py` execution and routing paths;
- `src/estate_worker.py` `worktree.prepare`, `start`, `status`;
- `src/worktree_ops.py`.

Use those only to make the Stage 6 contract implementable and internally consistent.

Do **not** implement Stage 6 in this task.

## 1. Separate process-terminal from worktree-resolved

The current Stage 6 contract blocks same-lease admission for:
- `accepted`;
- `running`;
- unresolved `pending_start`;
- `lost`;
- `interrupted`.

That is insufficient.

A process can be terminal while its worktree remains dirty or unresolved:
- `succeeded` normally leaves changes awaiting finalization;
- `failed` may leave partial changes;
- `timed_out` may leave partial changes;
- `interrupted` may leave partial changes.

Define an explicit worktree-resolution rule so execution process state alone never makes the worktree automatically reusable.

Required semantics:
- `succeeded` blocks new same-lease execution until it has been successfully finalized **or** explicitly abandoned/recovered;
- `failed` and `timed_out` after a writer actually started block until explicit worktree recovery;
- `interrupted` blocks until explicit recovery;
- `lost` blocks;
- deterministic pre-spawn refusal may be immediately reusable because no writer ran;
- a successfully finalized execution may become reusable only if the same ParkLease remains valid and the worktree is clean.

Do not add a second lifecycle store. Express this using EstateExecution + ParkLease and, if needed, an explicit resolution/finalization field/state in the Stage 6 schema plan.

Update I6: “terminal” alone must no longer imply a fresh dispatch is admitted.

Add tests proving:
- succeeded-but-unfinalized blocks a new execution;
- failed/timed_out after start blocks while dirty/unresolved;
- finalization/recovery is what reopens admission.

## 2. Define a real interrupted/dirty-worktree recovery transition

The plan currently says ordinary release of an `interrupted` lease is refused, while the prescribed recovery path ends in “explicit release.”

Define the actual operation that makes this possible.

Required properties:
- ordinary release remains unable to bypass an unresolved execution/worktree;
- recovery is explicit and operator-driven;
- it targets the exact `execution_id`, `lease_id`, `host_id`, branch and worktree;
- the control plane verifies the writer is not running/lost;
- the worktree is inspected and must meet the chosen recovery condition (e.g. clean after operator reset/commit/stash, or another explicitly defined safe state);
- only then may that exact ParkLease be released;
- a subsequent run requires a fresh park / fresh lease_id.

Use the smallest interface possible. It may be a guarded recovery mode on release or a dedicated recovery-release operation, but the normal release path must not become an escape hatch.

Add unit/integration expectations for successful and refused recovery release.

## 3. Separate operator heartbeat from execution-supervision heartbeat

The current matrix simultaneously says heartbeat is refused while an execution is active and that the control plane renews the ParkLease heartbeat while supervising it.

Resolve this contradiction.

Define a narrow internal execution-supervision renewal operation that:
- targets the **exact lease_id** recorded on the EstateExecution;
- requires that lease to remain active and belong to the same repo/host;
- renews heartbeat while a confirmed execution is positively observed `accepted`/`running`;
- cannot acquire, replace or broaden a lease;
- is called only by the control plane;
- never exists on the DB-free worker.

Keep ordinary user/operator heartbeat semantics separate.

Tests must prove the monitor renews only the execution's exact lease and cannot accidentally renew a later/reassigned lease.

## 4. Define one global execution-aware lease reclaimability rule

Raw heartbeat age and write-authority reclaimability are different facts.

Today multiple code paths call `park_lease_is_stale()` directly, including routing conflict checks and active-lease authority resolution.

Stage 6 must define one canonical control-plane predicate/helper for:

> Is this ParkLease reclaimable / ignorable as write authority right now?

It must consider:
- lease active/released state;
- heartbeat age;
- all EstateExecution states that still protect the worktree or whose outcome is unresolved.

Use that rule everywhere write-authority reasoning occurs, including at minimum:
- stale reclaim in `park_repo`;
- `eligible_hosts(repo_id)` conflicting-lease filtering;
- `active_lease_for_repo` / `_lease_authority`;
- release/recovery checks;
- admission.

Keep raw `park_lease_is_stale()` available as heartbeat-age telemetry if useful, but do not let a caller infer “safe to ignore/reclaim” from age alone.

Add tests where:
- heartbeat is stale but a running/lost/unresolved-worktree execution protects the lease;
- routing still treats the lease as authoritative;
- authority lookup still finds/protects it;
- reclaim remains refused.

## 5. Specify real serialization for admission vs release/reclaim

“Same DB transaction” is not by itself a complete concurrency guarantee.

The repository can use SQLite or another SQLAlchemy backend. Stage 6 must specify how execution admission and release/reclaim serialize on the exact ParkLease.

Required invariant:

> No release/reclaim of lease L can commit between Stage 6's final authority validation of L and insertion/commit of the EstateExecution that will start under L; likewise admission cannot slip past a concurrently committed release/reassignment.

Define the implementation strategy explicitly:
- row-level lock / `SELECT ... FOR UPDATE` on databases that support it;
- an appropriate SQLite write-lock/conditional-write strategy (e.g. `BEGIN IMMEDIATE` or equivalent);
- or another proven conditional-write design.

Do not introduce a second lock table/system unless absolutely unavoidable.

Update U29 to test the actual serialization invariant, not only sequential “lease changed before transaction” behaviour.

Add a true concurrency/race test expectation if feasible.

## 6. Harden same-execution-id `start` idempotency contract

The current worker implementation can create the spool, spawn, and only afterward write the handle-bearing `state.json`.

A retried same-ID `start` arriving in that window can see a spool without a handle and currently fail after a short wait with `execution_failed`, even though the first start may still be progressing.

Stage 6 depends on robust same-ID retry after a lost response, so specify a worker-side start state machine that makes this safe.

Preferred minimal contract:
- spool creation immediately writes a durable `starting` state before spawn;
- successful spawn replaces it with `accepted/running` + handle;
- same-ID `start` seeing `starting` returns a non-terminal reused/pending result, not `execution_failed`;
- `status` distinguishes:
  - no spool / truly unknown execution;
  - `starting`;
  - accepted/running with handle;
  - terminal;
- if spawn deterministically fails, state becomes a truthful terminal pre-spawn failure or the spool is cleaned in a way that a retry cannot be mistaken for a previously running process.

The exact representation may differ, but the contract must make U17/I6 race-safe rather than relying on a 200 ms timing assumption.

Add a race-focused unit/integration expectation where a second same-ID `start` arrives before the first has persisted its handle.

## 7. Put worktree preparation under write authority

Current remote `worktree.prepare` may create a branch and linked worktree before a ParkLease exists.

That mutates repository state before the only governed write authority has been acquired and can leave orphaned preparation if another caller wins the lease.

Correct the Stage 6 contract so remote worktree creation/reuse is covered by ParkLease authority.

Use the existing ParkLease system; do not add a second reservation system.

Acceptable pattern:
1. establish an exact ParkLease/reservation authority for the intended repo/host/branch before any mutating remote prepare;
2. worker performs `worktree.prepare` under that control-plane-granted authority;
3. worker reports path/branch/head/clean evidence;
4. control plane binds/verifies that prepared path against the exact lease before any execution;
5. preparation failure cleanly releases/rolls back the lease where safe;
6. concurrent park attempts remain single-writer through the existing ParkLease constraint.

If the existing ParkLease schema requires a staged/preparing state or nullable/provisional path to express this safely, specify the minimal schema change in the Stage 6 plan.

Add tests for:
- two concurrent remote park attempts -> one authority winner;
- loser cannot create an ungoverned worktree;
- prepare failure leaves no live reusable authority;
- dirty reused worktree fails closed;
- successful prepare results in one active lease bound to the verified path.

## Contract clean-up

Fix any stale step references in the Stage 6 test matrix (for example the I4 placeholder step number).

Ensure the final contract consistently distinguishes:
- process state;
- execution outcome;
- worktree resolution;
- lease authority;
- lease heartbeat age;
- lease reclaimability.

## Verification

This is contract-only, so do not modify Stage 6 implementation code.

Run the established pre-Stage-6 lifecycle baseline to prove the plan-only change did not disturb the branch:

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

Expected accepted baseline: 286 passed.

## Guardrails

- Do **not** implement Stage 6.
- Modify only `docs/aoteru-multihost-execution-implementation-plan.md`.
- Do **not** change runtime code, schemas, routes, config or tests.
- Do **not** enable home.
- Do **not** add a second queue, lifecycle store, lease or lock system.
- Preserve DB-free workers.
- Do **not** run or spend `/ultrareview`.
- If a finding is wrong after inspecting live code, document the evidence instead of forcing the contract change.

## Completion

Commit and push the plan correction on the same implementation branch.

Then stop.

Report:
- commit SHA;
- exact plan sections changed;
- final rules for worktree resolution, recovery release, exact-lease renewal, reclaimability, transaction serialization, same-ID start and authority-safe remote park;
- exact lifecycle-baseline result;
- any remaining blocker;
- whether Stage 6 is now ready to implement.

Do not proceed into Stage 6 implementation.

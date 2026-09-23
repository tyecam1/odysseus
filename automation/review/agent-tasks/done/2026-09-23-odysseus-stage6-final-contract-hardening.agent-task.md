---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-23-odysseus-stage6-final-contract-hardening
title: "Finalize Odysseus Stage 6 lifecycle and write-authority contract"
status: done
migrated_from_repo: tyecam1/obsidian-PhD
migrated_from_pr: 572
migration_note: "Task executed before repository-ownership migration; retained here as backend provenance."
priority: high
task_type: contract-repair
created_by: gpt-5.6-sol
created_at: 2026-09-23T09:00:00+01:00
updated_at: 2026-09-23T09:00:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single
architecture_rationale: "Stages 1-5 are converged. This task closes the remaining Stage 6 authority/lifecycle ambiguities before implementation: lease lifetime, atomic admission, interrupted recovery, durable timeout, remote-park cleanliness, and strict nonce shape."
single_agent_baseline: "One fresh Sonnet session should update only the bounded Stage 3 nonce-shape check and Stage 6 contract/test expectations, run the established pre-Stage-6 lifecycle baseline, then stop."
execution_host: compute-box
context_budget: medium
coordination_reason: "Do not begin Stage 6 implementation until write-authority lifetime is fully specified and crash/recovery semantics are unambiguous."
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
  - src/estate_worker_protocol.py
  - docs/aoteru-multihost-execution-implementation-plan.md
  - tests/test_estate_worker_protocol.py
  - tests/test_estate_worker_client.py
denied_paths:
  - core/database.py
  - src/estate_router.py
  - src/park_lease_ops.py
  - routes/**
  - companion/**
  - config/estate.yaml
  - config/models.yaml
  - scripts/windows/odysseus-host.ps1
inputs:
  - tyecam1/odysseus branch feat/multihost-stage1-3-20260922 at/after 6df528c
  - docs/aoteru-multihost-execution-implementation-plan.md
  - established pre-Stage-6 lifecycle baseline
outputs:
  - strict Stage 3 response-nonce shape validation
  - final corrected Stage 6 lifecycle/write-authority contract
  - updated Stage 6 unit/integration expectations
  - passing pre-Stage-6 lifecycle baseline
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol-independent-review
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Do not run or spend /ultrareview. Do not implement Stage 6. Do not modify ParkLease/EstateExecution schema or lifecycle code in this task."
---

# Final Stage 6 contract hardening before implementation

## Authority and starting state

Work from the live branch:

`feat/multihost-stage1-3-20260922`

at or after:

`6df528c`

Read and preserve the architecture in:

`docs/aoteru-multihost-execution-implementation-plan.md`

The current architecture remains authoritative:
- one lab control plane;
- thin DB-free workers;
- ParkLease is the only write authority;
- EstateExecution is the only execution-lifecycle authority;
- worker spool is execution evidence only, never lifecycle authority;
- no alternate-host or backend-local fallback;
- home remains disabled until the later live-proof stage.

This is the **final contract-hardening pass before Stage 6 implementation**.

Do not implement Stage 6 in this task.

## 1. Restore strict response-nonce shape validation

The previous nonce correction correctly moved **equality with the request nonce** into `verify_attestation()`, so a well-formed but wrong nonce becomes `placement_mismatch`.

However, `validate_response()` currently accepts any non-empty string as an attestation nonce.

Restore the protocol's canonical shape check:

- response attestation nonce must be exactly 32 lowercase hexadecimal characters;
- malformed shape -> `worker_protocol_error`;
- well-formed 32-hex nonce that does not equal the request nonce -> `placement_mismatch` in `verify_attestation()`;
- preserve `observed_host_id` where available.

Reuse the existing `_HEX_32_RE` contract rather than introducing another definition.

Add/update tests for:
- valid matching nonce;
- valid-shaped but wrong nonce -> placement mismatch;
- empty nonce -> protocol error;
- non-hex / wrong-length nonce -> protocol error.

Do not otherwise alter the worker protocol.

## 2. Couple ParkLease lifetime to EstateExecution lifetime

The current lease stale timeout is 1800 s, while Stage 6 write execution may itself run for 1800 s and uncertainty can continue beyond that.

A running or unresolved remote writer must never lose its only write authority merely because its normal lease heartbeat aged out.

Amend Stage 6 so an EstateExecution in any of these states:

- `accepted`;
- `running`;
- unresolved `pending_start`;
- `lost`;
- `interrupted` until explicitly recovered/released;

protects its associated ParkLease from automatic stale reclaim and ordinary release.

The control plane must maintain/renew the ParkLease heartbeat while it is actively supervising a confirmed `accepted` / `running` execution.

For `lost`, outcome is unknown; stale time alone must **not** permit lease reclaim.

The worker must never heartbeat or mutate ParkLease directly.

Add Stage 6 test expectations for:
- running execution + stale heartbeat timestamp -> stale reclaim refused;
- lost execution + stale heartbeat timestamp -> stale reclaim refused;
- release while accepted/running/lost -> refused;
- execution supervision renews the lease heartbeat while the execution is positively observed active.

Do not invent a second lock or lease system.

## 3. Make lease re-validation and EstateExecution admission atomic

The Stage 6 sequence must not rely on one early `_lease_authority()` check remaining valid across remote worktree verification and later dispatch.

Correct the contract to require:

1. perform remote `worktree.verify`;
2. enter one control-plane DB transaction;
3. re-read the **exact lease_id**;
4. require it is still:
   - active;
   - non-stale under the execution-aware rules above;
   - held by `route.host`;
   - `allowed_write_scope == "repo"`;
   - bound to the same worktree path and branch;
5. check for unresolved/non-reusable EstateExecution under that lease;
6. insert the new accepted EstateExecution;
7. commit;
8. only then issue worker `start`.

Release/reclaim must perform their own execution-state check transactionally before changing ParkLease state.

This closes the authority gap where a lease could be released/reassigned between an early authority check and remote `start`.

Add a race-focused test expectation where:
- authority initially validates;
- lease changes before admission transaction;
- no EstateExecution row is created and no worker `start` occurs.

## 4. Make `interrupted` block same-lease redispatch

A positively dead writer may have partially modified its worktree.

Therefore an `interrupted` EstateExecution is terminal as a process state but **not automatically reusable as a write-authority state**.

Stage 6 must specify:

- `accepted` blocks same-lease admission;
- `running` blocks;
- unresolved `pending_start` blocks;
- `lost` blocks;
- `interrupted` also blocks reuse of the same lease until the operator explicitly resolves the worktree and releases/re-parks.

Preferred recovery contract:

`interrupted -> inspect/clean/recover worktree -> explicit release -> fresh park / fresh lease_id -> new execution`

Do not silently dispatch a second writer into a worktree left by an interrupted execution.

Add a unit test expectation proving an interrupted row prevents new admission under that lease.

## 5. Persist execution deadline/timeout for restart reconciliation

Stage 6 currently says:

`no successful observation for timeout + 120 s -> lost`

but the planned EstateExecution additions do not persist the execution timeout/deadline.

After a control-plane restart, that threshold cannot be reconstructed safely unless the relevant timing data is durable.

Amend the Stage 6 schema plan to persist either:

- `execution_deadline_at` (preferred); or
- an equivalent durable timeout field that lets reconciliation compute the same bound exactly.

Preferred semantics:

- set the deadline when the EstateExecution row is created;
- reconciliation after restart uses the persisted deadline, not process-local arguments or defaults;
- the additional uncertainty window is applied deterministically from that persisted value.

Update U20/U24 and restart-focused integration expectations accordingly.

## 6. Require clean worktree evidence before remote ParkLease creation

Stage 6 remote park will call worker `worktree.prepare`.

That operation can return a verified worktree that is already dirty.

The control plane must not create a ParkLease for remote implementation work unless worker evidence explicitly confirms the prepared/reused worktree is clean.

Amend the remote-park contract:

- `worktree.prepare` / subsequent verification must return cleanliness evidence;
- `clean != true` -> park fails closed; no ParkLease row;
- never infer cleanliness from path/branch verification alone;
- preserve the local behaviour that refuses parking dirty worktrees.

Add I7/U expectations for a dirty remote worktree refusal.

## 7. Correct ambiguous-start success semantics

The current corrected plan still contains wording that can be read as allowing a successful same-ID `start` retry to contribute to a terminal failure conclusion.

Make the state machine explicit:

- first `start` response lost -> remain `accepted/pending_start`;
- retry `start` with the **same execution_id**;
- `reused: true` -> execution confirmed; transition/update to `running`;
- a clean new start with that same id -> execution confirmed; transition/update to `running`;
- deterministic pre-spawn refusal -> `failed`;
- still unreachable/ambiguous -> remain unresolved, later `lost` only after the bounded observation rule;
- a successful same-ID start is **never** evidence for `failed`.

Keep exactly-one-spawn as the U17/I6 acceptance property.

## 8. Preserve authority ordering for finalization

Retain and make explicit:

- ParkLease authority is re-proven before remote `worktree.finalize`;
- execution must be `succeeded`;
- exact lease_id, host_id, branch and worktree path must still match;
- an interrupted/lost execution can never finalize;
- a lease that has been released/reassigned invalidates finalization.

The worker only performs the requested Git operation after the control plane has proven authority; it never decides the lease is valid itself.

## Stage 6 test-matrix corrections

Update the Stage 6 U/I matrix so it explicitly covers at least:

- nonce malformed vs nonce mismatch distinction;
- exact-lease transactional admission race;
- running execution protects stale lease from reclaim;
- lost execution protects lease from reclaim;
- release refused during accepted/running/lost/interrupted;
- execution supervision renews lease heartbeat while positively active;
- interrupted blocks same-lease redispatch;
- persisted execution deadline survives control-plane restart;
- remote park refuses dirty worktree;
- ambiguous `start` retry with same id -> running, one spawn;
- unreachable ambiguous start never reopens admission;
- finalization re-proves exact lease/path/branch/host authority.

Do not reduce existing U/I coverage to make room; add or renumber coherently.

## Verification

Run directly affected protocol/client tests.

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

The previous accepted baseline was 286 passed.

Any difference must be explained and any regression introduced by this task fixed before completion.

## Guardrails

- Do **not** begin Stage 6 implementation.
- Do **not** modify `core/database.py`.
- Do **not** modify `src/estate_router.py` or `src/park_lease_ops.py` except if strictly required for the small nonce-shape correction (it should not be).
- Do **not** modify ParkLease/EstateExecution schema or runtime lifecycle code in this task.
- Do **not** enable home.
- Do **not** modify `config/estate.yaml` or `config/models.yaml`.
- Do **not** touch the household/Misumi deployment.
- Do **not** introduce a second queue, lease, lock or lifecycle store.
- Do **not** run or spend `/ultrareview`.
- If a finding is incorrect against live code, report evidence rather than forcing a change.

## Completion

Commit and push the contract correction on the same implementation branch.

Then stop.

Report:
- commit SHA(s);
- files changed;
- nonce shape/equality behaviour after repair;
- exact pre-Stage-6 lifecycle baseline result;
- the final Stage 6 rules for lease lifetime, atomic admission, interrupted recovery, durable deadlines, dirty remote park, ambiguous start and finalization authority;
- any remaining blocker;
- whether the Stage 6 specification is now ready for implementation.

Do not proceed into Stage 6.

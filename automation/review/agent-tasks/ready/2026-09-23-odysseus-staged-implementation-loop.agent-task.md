---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-23-odysseus-staged-implementation-loop
title: "Run Odysseus staged implementation with Sol adjudication"
status: ready
priority: high
task_type: staged-implementation
created_by: gpt-5.6-sol
created_at: 2026-09-23T12:20:00+01:00
updated_at: 2026-09-23T12:20:00+01:00
executor: claude_subscription
execution_mode: staged-loop
architecture: single
architecture_rationale: "The multihost architecture is converged. Remaining work should proceed stage-by-stage from the live plan, with bounded implementation and independent GPT-5.6 Sol adjudication after each stage."
single_agent_baseline: "One implementation agent owns changes; GPT-5.6 Sol is an independent CLI reviewer/adjudicator and must not edit code."
execution_host: compute-box
context_budget: high
coordination_reason: "Maintain a persistent staged implementation loop with explicit evidence, adjudication and stop conditions rather than ad-hoc continuation."
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: feat/multihost-stage1-3-20260922
inputs:
  - live tyecam1/odysseus branch state
  - docs/aoteru-multihost-execution-implementation-plan.md
  - latest reviewed contract at/after 0238bc8
outputs:
  - staged implementation commits and evidence
  - GPT-5.6 Sol adjudication record at each stage
  - explicit blockers/operator decisions where required
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Never run or spend /ultrareview unless the operator explicitly authorizes it."
---

# Odysseus staged implementation operating contract

Work from the **live** `tyecam1/odysseus` state. Do not trust stale task text where it conflicts with the repository.

Architecture authority:

`docs/aoteru-multihost-execution-implementation-plan.md`

## Immediate prerequisite before Stage 6 implementation

First close only the final contract gaps identified after `0238bc8`:

1. **Codex-write spool/tombstone retention**
   - A Stage-6 write execution must not lose its worker-side idempotency/recovery evidence merely because the generic terminal-spool age exceeds 7 days.
   - Preserve enough durable worker-side tombstone/spool state until the control plane has positively resolved the execution/worktree (`not_started`, `finalized` or `recovered`).
   - A deleted terminal spool must never allow `start(execution_id)` to be interpreted as a new execution.
   - Self-test/non-write spools may retain ordinary bounded GC where safe.

2. **Ambiguous `worktree.prepare`**
   - A lost/unreachable prepare response does **not** prove preparation stopped.
   - Keep the exact `preparing` ParkLease reservation protected while the outcome is unresolved.
   - Resolve using the same `lease_id` through an idempotent/status/probe contract; do not release the reservation merely because transport failed.
   - Only deterministic pre-mutation refusal, positively resolved failure, or positively verified successful preparation may transition the reservation.
   - A stale preparation timeout alone must not authorize competing worktree mutation unless the worker-side contract proves the original prepare cannot still be running.

3. **Finalize/push semantics**
   - Make explicit whether `worktree_resolution=finalized` means:
     - locally committed + clean, with push status tracked separately; or
     - committed **and pushed**.
   - Whichever contract is chosen must have a governed retry/next-action path for `pushed:false`; never strand an unpushed commit with no supported operation.
   - Preserve the invariant that worktree reuse cannot mix changes from different executions.

Update the architecture plan and acceptance matrix as needed, then route it through the adjudication loop below before Stage 6 implementation.

## Operating invariants

Preserve throughout all remaining stages:

- one lab control plane;
- `route.host` is the machine that physically executes;
- workers remain thin and DB-free;
- ParkLease is the sole write authority;
- EstateExecution is the sole execution-lifecycle authority;
- execution/process outcome and worktree resolution remain distinct;
- ambiguous remote outcomes fail closed;
- never retry onto another host or silently fall back to backend-local execution;
- preserve household/Misumi isolation;
- home remains disabled until its explicit enablement stage;
- no second queue, lease, lock or lifecycle authority;
- do not run or spend `/ultrareview` without explicit operator approval.

## Stage loop

For **every remaining stage**, including the immediate contract prerequisite:

1. **Reconstruct live state**
   - inspect current branch/HEAD, upstream sync and working tree;
   - read the exact current plan section, dependencies, invariants and acceptance tests;
   - inspect relevant live implementation before editing;
   - check whether intervening commits invalidate any plan assumption.

2. **Bound the stage**
   - identify the smallest affected scope;
   - do not begin later-stage work merely because it is nearby;
   - preserve unrelated working code and configuration.

3. **Implement**
   - implement the stage contract exactly;
   - keep authority/lifecycle logic centralized;
   - do not duplicate routing, lease, execution or worker state.

4. **Verify locally**
   - run directly affected unit/integration tests;
   - run the stage's U/I acceptance matrix;
   - run the established lifecycle baseline where applicable;
   - run broader tests when the changed surface warrants it;
   - distinguish new regressions from verified pre-existing failures.

5. **Independent GPT-5.6 Sol adjudication**
   - discover and use the repository's **real existing project CLI route** for GPT-5.6 Sol; do not invent a command or bypass the project's routing/governance.
   - provide Sol with:
     - current stage and governing plan section;
     - live diff/commits;
     - relevant implementation files;
     - test commands and exact results;
     - known pre-existing failures;
     - explicit request to inspect contract compliance, races, authority violations, crash/restart behaviour, fallback violations, portability and missing tests.
   - Sol is an **adjudicator only**. It must not modify repository files.

6. **Resolve adjudication**
   - fix every substantiated material finding within the current stage;
   - reject a finding only with concrete live-code/test evidence;
   - if Sol uncovers a necessary architecture decision outside the current stage, capture it as a blocker instead of silently widening scope.

7. **Repeat verification**
   - rerun affected tests and the applicable baseline;
   - rerun Sol adjudication after material fixes;
   - continue until there are no unresolved material findings for that stage.

8. **Checkpoint**
   - commit and push the stage;
   - record:
     - stage;
     - SHA(s);
     - files changed;
     - exact tests/results;
     - Sol adjudication outcome;
     - rejected findings and evidence;
     - known pre-existing failures;
     - remaining blockers/operator decisions;
     - next stage.

9. **Advance deliberately**
   - reread the next stage against the newly committed live state;
   - continue the same loop.

## Stop conditions

Do **not** stop merely because one stage completed.

Stop only when one of these is true:

- an explicit operator approval/decision is required;
- required infrastructure/credentials/hardware are unavailable;
- a safety/write-authority ambiguity cannot be resolved within the governing architecture;
- a live acceptance step explicitly requires operator participation;
- the plan reaches its intended completion boundary.

Otherwise continue through the remaining stages.

## Adjudication requirements

The Sol review must be independent of the implementation agent's reasoning. Ask it to actively try to falsify the implementation, especially around:

- concurrent lease admission/release/reclaim;
- ambiguous SSH/worker responses;
- backend restarts;
- worker restart/spool retention;
- idempotency;
- worktree cleanliness and provenance;
- exact-host execution;
- stale/reclaimability semantics;
- schema migration safety;
- SQLite and PostgreSQL behaviour where the contract claims portability;
- forbidden fallback paths;
- test gaps where the implementation could pass while violating the contract.

Do not convert Sol into a second implementer. The implementation agent owns all edits.

## Stage 6 minimum completion gate

Do not call Stage 6 complete until:

- the final contract prerequisite above is adjudicated and incorporated;
- all Stage 6 U/I tests in the live plan pass;
- the established lifecycle baseline passes without new regressions;
- Sol reports no unresolved material Stage 6 finding;
- write authority remains fail-closed under the tested race/restart/ambiguous-response cases.

Then checkpoint and advance to Stage 7.

## Completion

Continue the loop through the remaining plan stages subject to the stop conditions above.

Do not run `/ultrareview` unless explicitly authorized by the operator.

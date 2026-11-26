---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-21-lazyusage-parallel-window-aware-dispatch
title: "Enable bounded parallel lazyUsage execution with verified usage-window pacing and qualified local work"
status: ready
priority: high
task_type: runtime-orchestration-reliability
created_by: operator-directed-chatgpt
created_at: 2026-11-21
updated_at: 2026-11-21
executor: codex
execution_mode: staged-implementation-opt-in-canary
execution_host: lab
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: high
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: dev
related_tasks:
  - 2026-11-09-lazyusage-bounded-persistent-continuation
  - 2026-11-21-cross-repository-development-observer
  - 2026-09-08-subscription-usage-attribution-for-continuous-system-improvement
inputs:
  - AGENTS.md
  - START-AGENTIC.md
  - src/lazy_usage_runtime.py
  - src/lazy_usage_coordinator.py
  - src/estate_router.py
  - src/estate_write_lane.py
  - src/park_lease_ops.py
  - core/database.py
  - config/routing.yaml
  - config/models.yaml
  - config/estate.yaml
  - .claude/skills/lazyUsage/SKILL.md
  - docs/runtime-work-packages/2026-11-19-lazyusage-reliability-acceptance.md
  - docs/aoteru-local-model-benchmark-routing-evidence.md
  - docs/subscription-model-currency-policy.md
allowed_paths:
  - src/**
  - core/**
  - scripts/**
  - tests/**
  - config/**
  - routes/**
  - docs/runtime-work-packages/**
  - .claude/skills/lazyUsage/**
  - automation/review/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
result_path: docs/runtime-work-packages/2026-11-21-lazyusage-parallel-window-aware-acceptance.md
---

## Plan (written 2026-11-26 by the controller; step 0 is to verify it against HEAD)
**Goal in one line.** Add an opt-in change to the existing lazyUsage activation: two child executions in flight, under a separate operator work-in-progress (WIP) cap of two cards.
**Already done / do not redo:** provider-stated usage windows already gate dispatch (src/provider_usage.py, src/estate_router.py). Also in place: the advisor checkpoint, gate lifting through the owner ledger (src/owner_ledger.py), fail-closed handling of unknown usage, the `ungrounded_local_executor` rejection and repository write leases (src/estate_write_lane.py, src/park_lease_ops.py).
**Steps:**
0. Grep HEAD for `advance`, `_choose`, `_assess`, `in_flight_execution_id`, `EstateExecution` (core/database.py) and the lease and window-gate functions. Correct this plan and the already-done list.
1. Take a read-only baseline from the backend DB: serial dispatch, idle time by cause, and which usage pools are provider-stated or unknown. Proof: cited queries.
2. WIP reservation (core/database.py): a transactional reservation keyed on authenticated operator + canonical `repo_id/task_id`. `max_active_work_items_per_operator` is off by default and set to 2 for this operator. A card keeps its slot until its shipping gates pass. Tests: two workers on one card take one slot; a third card is refused even with an idle slot and expiring quota; restarts and parallel clients cannot oversubscribe; other operators are unaffected.
3. Add a durable parked-unfinished state (blocker, evidence, recheck trigger). Parking a third card needs a logged operator exception. Tests: only a proven protected wait parks; parked cards re-admit before new cards and within the cap.
4. Add `max_concurrent_executions` (default 1) in src/lazy_usage_runtime.py: per-child rows linked to the activation, and a unique `repo_id + task_id + revision` reservation persisted before any paid boundary. Tests: no double dispatch; a crash or restart with two children replays no paid call.
5. `advance()` fills free slots and reconciles each child. The coordinator plan stays advisory; stop/pause fences every child; admission against `max_paid_calls`, `max_tokens` and deadlines is atomic; one write lease per repository. Tests: the card's regression and accounting lists, including the 2026-11-21 guard-removal review gate.
6. The status surface (`am lazy status`; locate with grep) shows `active_items / cap`, parked count, stage and denial reason. Route test.
7. Write docs/runtime-work-packages/2026-11-21-lazyusage-parallel-window-aware-acceptance.md (baseline, design, model used, test evidence, canary plan with read-only tasks first and rollback by setting concurrency to 1). Run the full suite and stop.
**Done when:**
- With the flag off, the existing suite passes unchanged.
- All WIP and concurrency tests pass.
- Status reports the WIP count and denial reasons.
- The diff adds no scheduler, daemon, queue or activation type.
**Risks and stops:**
- If any change weakens the crash or stop fences, stop and report.
- If HEAD has no authenticated operator identity, record the gap; do not invent one.
- Do not touch approval/delegation code, owner-ledger semantics or local-routing guards. Canary and deploy are separate governed steps.
**Ordering note:** Follows the deployed 2026-11-19 reliability work. Unblocks the canary, adaptive pacing, grounded local work and the parking contract the owner-communication card relies on.

---

# Parallel and window-aware /lazyUsage

## Problem and outcome

Current `lazy_usage_runtime.advance()` allows only one `in_flight_execution_id` per activation, and `_choose()` selects one card. The Sonnet/GLM coordinator's up-to-12-candidate plan is advisory and cannot create parallelism. Owner requests useful **concurrent** agents across the Odysseus, Misumi and PhD frontiers, making effective use of legitimately available five-hour subscription allowances before their verified resets and of qualified local models where adequate. The objective is **verified accepted deliveries per constrained resource**, not spend for its own sake. The operator also requires a separate **work-in-progress (WIP) limit on distinct unfinished agent-task cards**: more parallel workers must not cause more half-finished projects. A five-hour pool can be limited by a shared weekly pool; available quota, reset time, model qualifications and task adequacy must never be invented.

Extend the **existing** Odysseus bounded backend activation, router, lease authority and lifecycle. Do not create a second scheduler, daemon, task queue, model-routing policy or activation type. A larger coordinator model alone is not a solution: reserve Opus for evidenced consequential ambiguity, not routine job ordering.

## Stage 0: inspect real bottlenecks and evidence first

1. Reconcile live `dev` HEAD, deployed service version, active run/leases, worker processes, backend DB, current three-repo frontier, eligible hosts and model/provider qualification. Confirm serial dispatch and determine idle time due to admission, approval, quota, verification, or missing eligible work. Do not confuse Git-backed queue counts with live accepted tasks.
2. Inventory **authorised, non-secret, provider-stated** usage observations per account/pool, including five-hour and weekly limits, percent/remaining units when exposed, reset timestamp/time zone, observation time, source/confidence, and sharing across models/CLIs. `am usage` currently exposes trusted Codex rollout windows; laptop /lazyUsage collects provider-native evidence that the backend currently does not receive. Reuse the existing usage-attribution work item, do not introduce scraping, credential access or assumed quota. Unknown stays unknown; no guaranteed reset-aware optimisation for unknown sources.
3. Establish a concise baseline for dispatch throughput, concurrent occupied slots, execution/verification outcomes, time idle despite eligible qualified work, stale allowance when verifiably measurable, provider refusals and lease conflicts. Preserve per-provider accounting; never sum percentages or unrelated token units.

## Stage 1: smallest safe parallel implementation

1. Keep one explicitly operator-authorised bounded activation. Permit a configurable **maximum two child executions in flight for the first canary** (default one / disabled by default); later increase only on measured evidence. Use existing `EstateExecution` identity and durable activation linkage, or the smallest equivalent extension. Atomically reserve each distinct `repo_id + task_id + revision` before dispatch, with unique execution identity and per-child state, deadlines, cost reservation, lease, outcome and review debt. Persist before crossing paid/provider/worker boundaries. Never dispatch the same unchanged card concurrently.
2. Make `advance()` select/fill idle execution slots and independently observe/reconcile every in-flight child. Its row/claim locks, crash fences, preflight, owner card transitions, stop/pause, budget exhaustion, worker admission, leases and restart reconciliation must work with multiple children. Stop fencing applies to **all** admitted executions; never falsely mark an active writer quiescent or replay a paid call after crash/timeout. Do not discard a successful sibling because another child failed.
3. Honor existing repository write lease authority: **at most one write lease per repository** until stronger isolation is independently proven; allow simultaneous distinct-repository writes, and independent read-only work only when capability/lease checks permit. Serialize tasks with dependency or shared mutable-file conflicts, provider lane limits, exclusive GPU/local-model VRAM demand, or inability to verify work independently. Use host capacity/qualified executor checks and fair selection without starvation.
4. Keep the coordinator a bounded **advisory ranked batch**; deterministic gates assign independent tasks to available slots. Do not paste model-generated decompositions into worker objectives. Do not replace the queue, local execution authority or initialising prompt contract. When no candidate fits a slot, report the exact bottleneck rather than overdispatch.

## Operator-level work-in-progress cap (mandatory for parallel canary)

**Parallel workers are not parallel projects.** Implement two separately configured limits under the existing activation/owner authority:

- `max_concurrent_executions`: worker slots, initially **2** in the opt-in canary, default 1 until qualified.
- `max_active_work_items_per_operator`: distinct owner-task cards being advanced across **all three registered repositories and all activations/clients**, initially **2 for this operator**. This must be independent of execution slots and scoped to the authenticated operator/principal, not to a single activation, model, host, repository or session. Do not apply one person's preference to other operators without their opt-in. Use existing owner/run/task identities; avoid introducing a second work-item queue or hand-edited status registry.

Treat a work item as occupying a WIP slot from the **first admitted substantive execution** through deterministic verification, independent review, author corrections, finalisation, acceptance, merge and deployment **where required by its contract**. A writer finishing, a branch commit, a green test suite, a PR opened or a reviewer pending does **not** free the slot. Count all agents, substeps and verification calls contributing to the same card as **one work item**, even if two workers operate simultaneously on distinct scoped substeps. Never mistake an advisory planning call or passive observer for an additional WIP item.

**Admission and convergence:**

1. Before starting a **new distinct** card, first reserve a slot transactionally by authenticated operator + canonical `repo_id/task_id` (bucket moves and card revisions preserve identity). Reconcile existing in-progress work, execution records and pending acceptance/review debt before new admissions; do not reset the count on service restart, run completion, renewed activation or a new client. Another concurrent admission cannot race past the cap.
2. **Finish before starting:** when at the WIP limit, only admit execution, tests, review, corrections, reconciliation or completion work on those same active cards. Select tasks nearer verified completion where feasible; allow multiple qualified agents to collaborate on the **same** active item under independent scopes and existing write-lease/reviewer rules. Never open a third card merely because a worker slot is free or a provider's five-hour reset is approaching.
3. A card can leave **active WIP** only on (a) evidenced owner-authorised terminal outcome meeting its delivery contract, or (b) a documented **genuine external/protected wait** that cannot presently be advanced. In case (b), record a durable **parked unfinished** state with precise blocker, evidence, owner, recheck trigger and expected next step; preserve the fact that it is *unfinished*. Do not relabel waiting for routine tests, reviewer availability, quota reset, worker handoff or ordinary finalisation as externally blocked simply to free a slot. Re-admit parked cards ahead of unrelated new work when their blocker clears, subject to the cap.
4. Keep a visible count of **active WIP, parked started-but-unfinished items, verification/acceptance debt, and accepted-but-undelivered work**. Do not let unlimited parked items accumulate invisibly. Warn and require explicit operator exception before growing **parked started-but-unfinished items beyond 2**; log each exception and maintain finish-first priority. Avoid automatically claiming more work to consume expiring quotas.
5. Preserve the existing queue and status authority: a Git-backed `ready` card may already have delivery/PR evidence; a `blocked` card may be stale. Reconcile against actual history and exact card revision before counting, rather than assuming directory location equals WIP. Work already active at feature enablement is grandfathered without duplicate claims; if the effective WIP count exceeds the limit, **do not start new cards** until it falls below the cap.
6. Report `active_items / cap`, `parked_unfinished`, per-item completion stage and exact admission denial reason in `am lazy status`/existing status surface. If a provider has spare quota while the WIP cap is full, direct it to productive verification/correction on active items or leave the allowance unused. Do not overcommit, lower evidence standards, fabricate work or silently expand the cap.

**Tests:** two agents executing distinct safe substeps of one card consume **one** WIP slot; two independent cards consume two; a third new card is refused even with an idle worker and near-expiring quota; a completed/accepted card releases its slot only after all required shipping gates; unmerged/unverified work retains its slot; a proven protected wait parks durably, preserves debt and safely permits a new item; parked reactivation obeys the limit; parallel clients and service restart cannot oversubscribe; adding more providers/hosts never increases operator WIP implicitly; no other operator inherits this preference without explicit configuration.

## Stage 2: window-aware admission, not quota burning

1. Derive an **optional** provider/account-pool admission policy from verified allowed usage observations, cross-model shared pools, verified reset times, actual run-level budgets and calibrated per-task consumption/outcome costs. Record data age and confidence, explicitly distinguish provider-stated reset from router cooldown, and respect weekly/more restrictive limits. Refresh after a meaningful dispatch, stated reset, provider refusal or long inactivity; cap reading frequency.
2. Optimise **value-weighted, verified work completed before an expiring allowance**, with additional eligible parallel capacity only if tasks, host, lane, verification and operator authority permit. Avoid indiscriminate exhaustion, low-value busywork, paid calls to probe usage, and starvation of weekly headroom. Start from conservative fixed concurrency when telemetry is unknown; skip urgency-based choices rather than invent percentages. Provide an operator-configurable five-hour utilisation preference subordinate to quality, spend, weekly limits and stop gates.
3. Meter every child and coordinator call once, distinguishing measured/assumed usage and dispatch count. Aggregate atomically against bounded activation budgets so parallel starts cannot oversubscribe `max_paid_calls`, `max_tokens` or hard deadlines. Preserve the existing fail-closed unknown child-usage behavior.
4. Treat actual user account quotas as **shared** by relevant models/clients; do not multiply their pools by assigning separate workers. A provider's advertised five-hour reset is not a promise of capacity if weekly allowance is depleted.

## Stage 3: qualified local work

1. Reuse `config/models.yaml`, the LM1 benchmark corpus and real local host capabilities. Current `_assess()` rejects bare `executor == local` reconnaissance as `ungrounded_local_executor`, and deterministic route choice does not perform the task. Do **not** remove these protections.
2. First offer local models bounded, **grounded** tasks where the controller supplies explicit source snippets/structured evidence and where local output is independently checkable: metadata classification, task triage, log/test failure clustering, candidate extraction and cheap draft synthesis. Implement the smallest authenticated, least-privilege grounded-context interface using current router; never imply full repo access from text-only inference.
3. For local repository edits or independent review, require separate task-class benchmark qualification, permitted tool/worktree access, reproducibility, material quality floor and independent external verification where applicable. Document GPU memory occupancy/serial limits (existing lab RTX 3080 has 10 GiB) and never launch conflicting resident Ollama loads. Failed competence tests or missing deployable model mean retain a qualified paid route.

## Acceptance and rollout

- Regression tests: two eligible different-repo tasks progress concurrently within the operator WIP cap; one-repo write conflict is rejected; same card/revision never dispatches twice; dependency reservation works; provider and GPU capacity holds; deterministic ordering; crash/restart with two children; stop/pause cancels/fences or observes **both**; stale worker/dirty tree does not permit unsafe lease recovery; quota exhaustion blocks only the affected pool; sibling finishes independently.
- Accounting tests: concurrent budget admission cannot exceed caps, coordinator and child usage each charged once, missing usage fences continuation, five-hour versus weekly conflicts handled conservatively, unknown/stale reset never creates phantom headroom, no paid probe call.
- Quality tests: routing to local is grounded and task-class qualified, otherwise it fails closed; a green test suite alone cannot self-approve a write; independent cross-family review and owner acceptance remain separate. Reproduce the 2026-11-21 regression where 9,843 tests passed but independent review rejected guard removal, and preserve that gate.
- Canary: read-only or disposable independent tasks first with two execution slots and no more than two distinct operator-owned active work items, then two genuine different-repo governed low-risk writes only after tests and independent review. Document real simultaneous time intervals, unique execution IDs, before/after lead time, verified completions, quota telemetry availability, false collisions, missed reviews, orphaned children and cancellation. Compare to a serial baseline with comparable tasks; rollback via feature flag/max concurrency 1, no host reboot or unsafe live-unit test.
- Produce source-linked evidence in `result_path` and reconcile the existing owner cards and review debts. Merge/deploy only through normal gates; a PR or mock test does not count as deployed. Ship the smallest demonstrably useful concurrency slice before optional adaptive pacing. If no qualified work or reliable usage telemetry is available, report the limit precisely instead of manufacturing usage.

---
title: Benchmarked parallel subagent testing and review dispatch
status: inbox
priority: high
owner_repository: tyecam1/odysseus
task_class: estate-orchestration
created: 2026-11-10
updated: 2026-11-10
execution_scope: shared-runtime
dependencies:
  - automation/review/agent-tasks/inbox/2026-11-10-economical-review-model-routing.md
---

# Benchmarked parallel subagent testing and review dispatch

## Objective

Increase verified defect detection and delivery throughput per unit of total quota and wall time by **proactively considering bounded parallel cheap subagents for independent testing and review**. Keep one coordinating task owner. Do not assume that more agents are cheaper or more accurate: measure and promote only demonstrated wins over serial and stronger-model baselines.

## Live repository findings (2026-11-10)

- Odysseus `AGENTS.md` demands decomposition and cheapest-adequate delegation, but neither `src/delegation_preflight.py` nor the inspected `src/estate_router.py` defines a test-subtask fan-out planner or a qualified, cost-accounted subagent pool. `docs/initialising-prompts/estate-queue-priority-execution-v2.md` directs a single qualified worker but does not prompt the coordinator to examine parallel test opportunities.
- Odysseus `docs/aoteru-model-host-routing-contract.md` invariant 14 says *no swarm by default*, while explicitly permitting genuinely independent evidence gathering and verification. Preserve its **one owner per task unit** principle; distinguish it from multiple independently owned read-only subunits.
- `config/routing.yaml` declares `max_worker_calls: 3`, while paid/frontier/context caps are null. `src/estate_router.py` reports some budget constraints as unverified: a declared cap is not proof of enforcement. Implementation/write execution permits only one unresolved execution per lease (`src/estate_write_lane.py`), so same-worktree concurrent writes must remain forbidden.
- Misumi `docs/odysseus-contract.md` delegates generic execution to Odysseus. `docs/core/seed-order-runtime-integration.md` distinguishes selectable personas from authorised autonomous workers; do not spawn personas merely for flavour. Its `agent-tasks/inbox/evaluate-langgraph-orchestration.md` already deferred installing another orchestration framework without measured benefit.
- obsidian-PhD `automation/docs/agent-architecture-selection-gate.md` governs single, single-plus-verifier, coordinated-2 and parallel-n task architectures, defaulting to single and requiring a family-specific benchmark for parallel-n. It is a **contract only**, not runtime routing. Historical subagent work exists (e.g. `automation/review/routine-reports/repo-roadmap/2026-06-29-subagent-dispatch-manifest.json` and the 2026-07-04 central orchestration task). Historical provider quota exhaustion is recorded in `automation/review/operator-decisions/records/2026-07-29-programme-halt-worker-capacity-exhausted.md`. Reconcile, rather than override, the PhD selection gate.
- Existing 2026-11-10 economic-review preference limits ordinary review selection to qualified **Haiku 5.5, Terra 6.1, GLM-Flash**; do not automatically spend Sol/Opus/Fable budget. Model labels do not prove live availability or qualification.

## Implementation

1. **Bounded candidate selection.** At existing preflight, classify each requested review/test workload into deterministic tests (run directly in parallel if safe), model-authored test cases, bounded code review, evidence/reproduction checks, and sequential or judgement-heavy work. Inspect partition independence, baseline quality, shared-state hazards, verification cost, available hosts, qualified models and quota. Recommend `single`, `single-plus-verifier`, `coordinated-2`, or `parallel-n` without a competing planner/queue. Keep a reason when parallelism is rejected.
2. **Cheap subagent fan-out.** Extend the existing Odysseus task envelope, preflight, worker dispatch, and telemetry only as necessary. Use one coordinator, independently scoped read-only subunits (e.g. API, security, schema, integration, fault reproduction) and one bounded aggregation step. Give each subunit a pinned base/head, minimal context pointers, objective, relevant test command, expected machine-readable findings and stop rule. Run deterministic tests independently without charging for an AI process. No unlimited recursion, duplicate whole-repo contexts, shared mutable worktrees, self-certification or cross-repo authority transfer.
3. **Actual enforced budgets.** Admit only qualified/live model routes, defaulting to Haiku 5.5, Terra 6.1 or GLM-Flash for AI review when eligible. Make maximum concurrent subagents, total paid calls, total context/tokens or observed quota, per-task deadline, provider rate limits and GPU/host contention effective **runtime admission gates**, not unverified YAML labels. Cancel or quiesce sibling work on budget exhaust, critical failure, stale HEAD or protected-gate rejection. If usage cannot be observed/enforced, choose a bounded conservative configuration and report uncertainty.
4. **Evidence reconciliation.** Deduplicate findings by cause and file/line; require a reproduction or deterministic supporting check for actionable claims. Distinguish true positives, unique defects, speculative findings, and failures from stale base/test interference. Route only unresolved, consequential integration conflicts to a qualified stronger reasoning model under the existing explicit exception process. A cheap subagent is never automatically an authorised merge or canonical research adjudicator.
5. **Benchmark before default promotion.** Compare equivalent real task families across the three repos: (A) deterministic-only/serial checks, (B) one adequate strong review agent, (C) serial cheap reviewers, (D) coordinated cheap fan-out at 2, 4, and optionally 8 workers where safe. Include known-defect holdouts and new defects verified by reproduction. Measure end-to-end elapsed time, coordinator + workers' input/output tokens, **account quota consumption**, provider rate-limit errors, unique verified defect recall/precision, regression escape rate, false positives, rework, retries and human intervention. Pre-register non-inferior quality and meaningful measured cost/throughput improvements as promotion gates; do not optimise parallelism count by anecdote.
6. **Roll out minimally.** Reuse `docs/aoteru-model-host-routing-contract.md`, `config/routing.yaml`, existing worker/execution and lease components, `AGENTS.md` and the active queue initializer. Reconcile the PhD architecture gate by evidence-backed change or a narrowly defined testing exception through existing governance. Preserve Misumi persona boundaries, PhD DRM evidence/ontology approvals, repo write leases and single-owner acceptance. No LangGraph/new service/new queue by default. Ship tested runtime changes and actual worker deployment, not contract-only text.

## Acceptance and stopping

- Live work item, current HEAD and baseline commands are identified for each trial. Tests demonstrate genuinely simultaneous *independent* read-only subunits, deterministic runner parallelism, bounded aggregation, stable artifact IDs, cancellation and no shared-write races.
- Adversarial tests cover missing/unqualified cheap models, quota exhaustion during fan-out, provider rate-limit failures, duplicate findings, stale HEAD, failed reviewer, failed deterministic test, GPU contention, moving repo/lease, protection gate and interrupted session. Test that *one write execution per lease* remains enforced.
- Telemetry can explain **why** the topology and subagent count were selected and show actual end-to-end cost and useful unique defects, not just total spawned agents or green checks.
- At least one task family delivers a reproducible advantage with no loss against the quality gate before `parallel-n` becomes its routine default. For other families keep the incumbent single/coordinated strategy, with recorded rationale.
- Update the existing contracts, tests and prompt initializer only after the benchmark; use the prompt register's normal version/evolution process rather than editing an active immutable initializer in place. Integration with the 2026-11-10 cheap-review-model task must be explicit.
- Verify release/worker activation and task completion end to end; an unmerged PR, unsupported model alias, passing unit tests alone or a design document is not deployed capability.

**Priority boundary:** Cost and throughput waste is material, but shipping-first policy still governs scheduling. Do not displace more urgent accepted deliverables unless measurements show this task directly unblocks them.

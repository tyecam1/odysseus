---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-07-capability-utilisation-integration-retirement
title: "Activate useful repository capabilities and retire proven redundancy"
status: inbox
priority: high
task_type: cross-repository-capability-consolidation
created_by: chatgpt
created_at: 2026-11-07T15:43:00+00:00
updated_at: 2026-11-07T15:43:00+00:00
executor: claude_subscription
execution_mode: evidence-first-bounded-implementation
architecture: single-plus-verifier
architecture_rationale: "One investigator maintains a coherent cross-repo inventory and selects small, owner-scoped changes; a separate qualified reviewer challenges use claims, consumer search, equivalence, safety, and retirement before acceptance."
single_agent_baseline: "A single agent can attribute existing capability calls to useful outputs, establish consumer dependencies, and land narrow integration or consolidation PRs. Independent review is mandatory for consequential retirements."
execution_host: lab
context_budget: medium
coordination_reason: "Keep classification and prioritisation coherent without centralising domain authority or spawning a new orchestration system."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: true
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - automation/review/**
  - docs/**
  - evals/**
  - tests/**
  - scripts/**
  - src/**
  - config/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
inputs:
  - AGENTS.md
  - automation/review/agent-tasks/README.md
  - docs/aoteru-repository-ownership-trajectory.md
  - automation/review/phd-automation-convergence-inventory-20261024.md
  - automation/review/system-efficiency/2026-11-06-usage-attribution-diagnosis.md
  - automation/review/agent-tasks/ready/2026-09-08-subscription-usage-attribution-for-continuous-system-improvement.agent-task.md
  - automation/review/agent-tasks/inbox/2026-09-10-external-capability-equivalence-audit.agent-task.md
  - automation/review/agent-tasks/inbox/2026-11-04-hardware-aware-model-integration-and-retirement.agent-task.md
  - tyecam1/obsidian-PhD@main:automation/docs/capability_manifest.json
  - tyecam1/obsidian-PhD@main:automation/docs/current-capabilities.md
  - tyecam1/obsidian-PhD@main:automation/docs/agent-task-queue-ownership.md
  - tyecam1/s2-e1-ros2-measurement-spine@main:README.md
  - tyecam1/misumi@main:AGENTS.md
outputs:
  - evidence-backed disposition of current capabilities and their real consumers
  - ranked integration, repair, consolidation and retirement decisions
  - smallest justified owner-scoped implemented changes with independent verification
  - before/after evidence of usage, output value, regressions and removed overhead
  - provenance, rollback and updated capability truth in each owning repository
result_path: automation/review/capability-utilisation/2026-11-07-disposition-and-execution.md
review_report_path: automation/review/capability-utilisation/2026-11-07-independent-review.md
handoff_model: codex_subscription
operator_decision_path: automation/review/capability-utilisation/2026-11-07-disposition-and-execution.md
supersedes: []
duplicates: []
notes: "Operator request 2026-11-07. New cross-repository utilisation/retirement work, not a replacement for existing skill-equivalence, quota-attribution, model-weight retirement or PhD research tasks. Respect 2026-10-17 shipping-first backlog priority. This task alone does not authorise destructive protected changes."
---

# Activate useful capabilities; retire proven redundancy

## Objective

Reduce total maintenance and review burden while improving actual research and agent execution output. Inspect the LIVE default/active branches of Odysseus, obsidian-PhD, Misumi and the S2-E1 measurement repo. Identify capabilities that are implemented but unused, partially integrated, duplicative, broken, or valuable yet underexploited. **Integrate useful existing mechanisms and retire only proven redundant ones.** Do not invent a new platform or add features solely to increase capability counts.

The governing test is: **Which capability demonstrably produces a necessary, reliable output, and is that output worth its runtime, review, and maintenance cost?**

## Ownership, admission, and dependencies

- The cross-repository runtime/instrumentation and shared consolidation programme belongs to Odysseus. PhD evidence, Zotero, ontology, manuscripts and research-specific automation belong to obsidian-PhD; Misumi household/persona semantics belong to Misumi; experiment software/data authority belongs to S2-E1. Keep independent domain queues. Implement domain-specific changes through separate, existing owner-scoped PRs/tasks when their repository contracts require them. Do not make this card an alternative cross-repo task queue.
- Reconcile the current backlog before admission. The standing Odysseus shipping-first directive outranks optional clean-up. Do not interrupt accepted deliverables for speculative consolidation. Reuse the existing 2026-10-24 convergence inventory and usage-attribution investigation, but recompute stale factual claims from live HEADs.
- Before writing: use the existing Odysseus preflight, route and ParkLease safeguards, current repository contracts and approved scopes. Resolve the latest authenticated subscription model under the standing currency policy; no hard-coded model versions. Use deterministic discovery first, qualified implementation workers for small changes, independent qualified review for protected/consequential changes.
- Keep the existing skill-equivalence audit limited to external alternatives, the usage-attribution task responsible for provider consumption, and the model-retirement task responsible for AI weights. This task is about **actual use, end-to-end integration, redundant code/workflows, and output value**. Consume their findings; do not duplicate their work.

## Phase 1. Establish actual utilisation, not just inventory counts

Start with obsidian-PhD's 84-entry capability manifest (60 implemented, 20 partial, 3 blocked, 1 planned at the 2026-11-07 inspection), then inventory other repositories' implemented functions, commands, hooks, schedules, services, and interface capabilities by **job-to-be-done**, not filename. Collapse aliases. Read code and authoritative contracts, not just READMEs.

For each capability capture, with source/commit/host evidence:

capability_id | owner | job | entrypoint/trigger | callers/consumers | last observed real invocation | observed output and user/research consequence | test coverage | runtime health | operational cost/maintenance burden | safety/approval gates | classification | confidence | next action.

Search direct imports/calls, CLI dispatch, scheduled invocation, config references, UI entry points, tests, downstream artifacts, real run logs and deploy state where reachable. Distinguish real runtime invocations from synthetic tests, historical reports, and declared functionality. Use existing telemetry; introduce at most the smallest event field or join necessary to distinguish a useful call from an unused function. Do not build another dashboard, queue, schema authority, heartbeat or provider telemetry store.

Evidence categories:
- VERIFIED_USED: a genuine invocation with an attributable output within a relevant observation period.
- CONSUMED_ON_DEMAND: legitimate infrequent, protective, fallback, or operator-triggered consumer; lack of recent invocation is expected.
- IMPLEMENTED_UNVERIFIED: implementation exists, but real invocation or health cannot be established.
- UNWIRED: no current live dispatcher, scheduler, or consumer; tests/docs alone do not count.
- DUPLICATED: equivalent semantics with a second maintained implementation, but not yet safe to retire.
- DEGRADED: reproduced operational or security failure.
- PLANNED_OR_INTENTIONALLY_BLOCKED: absent or gated by design; not dead code.

Report observation windows and missing hosts. **82 unknown-health PhD entries are not 82 unused entries.** Recent lack of use alone is insufficient proof of redundancy.

## Phase 2. Decide for each capability

Assign exactly one proposed disposition: KEEP, INTEGRATE, REPAIR, CONSOLIDATE, RETIRE, or PARK. Evaluate (1) measured decision/research value, (2) frequency/legitimate future need, (3) quality and reliability, (4) consumer dependencies, (5) required human oversight, (6) security/privacy, (7) migration and rollback cost, and (8) ongoing maintenance overhead.

Prioritise existing components that can close a real vertical workflow: Zotero/PDF intake -> reviewed evidence -> defensible J1/J2/S2 output; active research-context retrieval; agent task execution -> validated result -> closeout; and S2-E1 measurement provenance. These are **candidate priorities**, not blanket activation orders. First establish which missing link actually prevents useful output.

Explicitly examine the known candidate dormancies: cross-harness evaluation, sleep consolidation, governed skill lifecycle, staged writing analysis, the continuous improvement loop, supervision workbook updater, hybrid retrieval evaluation, and monitoring/cockpit currency. Check the known degraded PhD canonical-write boundary and the older Odysseus routing failure against current live state. Do not enable or work around unsafe write paths; route security remediation through the existing protected hook/approval contract.

## Phase 3. Execute bounded improvements, not another planning exercise

Select the smallest high-value unblocked set, normally 1-3 independently testable vertical slices, using measured output value and ease of delivery. For each:

1. State baseline, consumer, observed failure or missing connection, expected improvement, repo owner and acceptance test.
2. Reuse existing implementation before adding code. Integrate/repair in the owning repository through a small PR and required review/permission route.
3. Demonstrate the full real path (or document an explicit external/hardware gate); synthetic success alone is not live acceptance.
4. Measure before/after change in successful outputs, actionable review decisions, false/failed outputs, human attention, runtime/maintenance burden, and any regressions where evidence is available.
5. Update existing capability/operational-truth docs and disable superseded entrypoints only after the replacement passes.

Purge only if an explicit consumer/dependency search finds no necessary runtime, fallback, operator, historical provenance or governed pending use; equivalence/replacement is demonstrated where relevant; tests and rollback are available; and the owning repository's deletion/cleanup approval is obtained. Removal must include config, exports, docs, scheduled triggers, and tests that reference the retired route, without discarding meaningful historical evidence. Unknown usage, sparse calls, or a stale manifest are not deletion warrants. Deleting broad historical provenance, canonical research, protected hooks, model weights, raw experiment data or external Zotero/PDF material is out of scope.

If integration is useful but blocked, record exactly one missing prerequisite and advance the next unblocked item. If a capability is neither useful enough to integrate nor provably redundant, PARK it with explicit reason and no recurring maintenance obligation.

## Required results and stop rule

Produce one compact evidence ledger and a ranked disposition table containing source refs, confidence, owner, necessary approval, expected value, actual outcome and retained blockers. Provide links to owner-scoped implementation PRs, independent verification, migration/rollback evidence and updated existing capability records. Summarise functions truly retired and future overhead actually removed; do not report planned deletions as completed.

Complete when: the meaningful current capability families are classified with unknowns explicit; the top approved and accessible high-value slices have been implemented and demonstrated or named as externally blocked; all deletion candidates have consumer-negative or proven-replacement evidence and required review; no unsupported unused claims remain; the remaining candidates are PARK/KEEP or routed into existing owner queues without spawning new orchestration; and a separate qualified reviewer has challenged any consequential removal.

Do not continue indefinitely seeking optional improvements or claim global utilisation coverage beyond available runtime evidence.

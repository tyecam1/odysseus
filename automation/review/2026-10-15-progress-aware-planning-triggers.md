---
title: Progress-aware work prioritisation and evidence-based automation triggers
status: candidate-input
created: 2026-10-15
source: User scratch notes, 2026-10-14 14:25
authority: design input only; no executable schedule or new work queue
related:
  - https://github.com/tyecam1/odysseus/pull/27
  - https://github.com/tyecam1/odysseus/pull/42
  - https://github.com/tyecam1/odysseus/pull/91
---

# Progress-aware planning and event-based workflow triggers

Author-origin prompts:
- "self schediling prioritiser that looks at deadlines and progress to assign appropriate amount of work and the most important next work, whether it is human/agent/or both"
- "look into 'automation triggers' for predictive maintanence esque automation based on my historic working and ai routines"
- "ie journal research"

## Existing owner and proposed extension

These are inputs to the existing cross-repository portfolio planning and scheduler/dispatcher authority, **not** a new task registry, independent planning service, or authorisation to run models automatically.

**Priority question:** Given a known deadline, verified deliverable state, dependencies, resource/capability availability, user commitments and measured rate of progress, which human, agent or mixed task has the highest defensible marginal value now? A static priority label is not enough, but a confident-looking predicted schedule based on unreliable completion estimates is worse.

A candidate decision loop:
1. Read bounded, authorised work-item state from each domain repository; preserve owner, deadline, review/approval gate and evidence pointers.
2. Estimate remaining work/risk from verified milestones, observed throughput and uncertainty; distinguish estimates from measurements. Do not infer that inactivity proves failure.
3. Propose one near-term feasible execution wave, including human-only dependencies, coordination cost, task switching and available worker budgets. Identify critical-path slippage instead of maximising cheap agent utilisation.
4. Reconsider only on meaningful events, for example: verified completion, a missed milestone, deadline change, dependency release, persistent blocked state, or significant model/host capability change. Periodic low-cost reconciliation may catch missing events.
5. Validate authority, concurrency, spend, quality floors and change size before dispatch. Human-facing recommendations are not executable approvals.

**Trigger question:** Can a compact history of *authorised* research and AI workflow events predict useful interventions (for example, 'draft progress persistently below needed pace' or 'paper retrieval blocked too long') with fewer false alarms and less manual overhead than a fixed reminder? Call this an exploratory hypothesis, not proven predictive maintenance. Begin with deterministic thresholds and a measured baseline before any learning/personal behavioural model. Track false-positive/false-negative rates, intervention usefulness, cost, privacy and the risk of reinforcing poor existing routines.

**Research journaling:** A trigger may *offer* to collect a concise dated note when a relevant event occurs, but the human's scientific interpretation, provenance and claims remain in the PhD repo's governed log/review system. Odysseus may schedule or route the prompt and pass a bounded evidence pointer; it must not become the durable journal or silently author research findings.

## Integration gates

- Audit whether PR #27's portfolio work was merged and whether any current task already implements the above. The closed PR is design provenance, not proof of implementation.
- Reconcile with the proposed governed backlog loop in PR #42 and role-evaluation work in PR #91 before adding executable features.
- Define a falsifiable, low-cost baseline: fixed weekly review or deterministic deadline/dependency re-ranking. Compare a candidate trigger policy against this baseline on real, permissioned tasks before enabling automatic action.
- Reuse scheduler, task routing, leases and owner repositories. Plans are transient derived outputs. Do not store private habitual data without explicit scope/retention controls or autonomously schedule paid work.

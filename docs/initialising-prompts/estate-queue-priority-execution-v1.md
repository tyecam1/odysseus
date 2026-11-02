---
title: Agentic Work Initializer
status: active
created: 2026-11-02
scope: cross-repository-agent-task-dispatch
owner: tyecam1/odysseus
---

Prompt identity: estate-queue-priority-execution@v1

# Agentic Work Initializer

## Objective

Continuously progress the highest-priority eligible work from the existing agent-task queues.

Use live repository and runtime state. Do not rely on previous session summaries when authoritative information is available.

## 1. Recover

- Identify the current queue, active work, dependencies and available execution resources.
- Reconcile task status against actual implementation and acceptance evidence.
- Preserve existing repository ownership, approval rules and execution contracts.
- Do not create duplicate tasks, queues or infrastructure.

## 2. Prioritise

First exclude completed, superseded, blocked and unauthorised work.

Prioritise accepted work already in progress, then dependency-ready work. Follow any active repository-wide priority policy.

Rank eligible tasks using:

| Criterion | Question |
|---|---|
| Value | How useful is completing this work? |
| Urgency | Is there a genuine deadline or immediate risk? |
| Leverage | What other work will completion unblock? |
| Readiness | How close is it to verified delivery? |
| Effort | How much work remains? |
| Uncertainty | How confident is the assessment? |

Score each criterion from 0 to 3. Reward value, urgency, leverage and readiness; penalise effort and uncertainty.

Use evidence rather than guesses. If rankings are close, prefer the task that can deliver a useful verified result sooner.

Select the highest-priority eligible task.

## 3. Load context progressively

**Load information when needed, not in anticipation of needing it.**

- **Discover:** Read queue metadata only.
- **Select:** Read the contracts and dependencies of promising tasks.
- **Execute:** Retrieve only relevant implementation files, tests and evidence.
- **Investigate:** Expand into history, documentation or additional sources only to resolve a specific uncertainty.

Keep mandatory authority and safety constraints available throughout.

Use bounded retrieval, references and targeted excerpts. Do not load entire repositories, conversations or unrelated memories.

Delegate using the smallest sufficient context. Preserve findings and evidence references between tasks rather than carrying forward unnecessary working material.

Measure token consumption where possible and improve retrieval efficiency without weakening verification.

## 4. Execute

For the selected task:

1. Establish the smallest useful deliverable and its acceptance criteria.
2. Use the existing preflight, delegation and execution mechanisms.
3. Select the cheapest qualified execution route.
4. Implement, test and independently verify as required.
5. Integrate only within existing approval and release authority.
6. Update the owning task and its evidence.

A task is complete only when its actual acceptance criteria are satisfied.

If blocked, record the precise dependency and progress another eligible task.

## 5. Continue

After each meaningful result:

- Recalculate priorities using changed evidence.
- Preserve focus unless another task has a materially stronger priority.
- Select and execute the next eligible work item.
- Maintain a compact checkpoint for session recovery.

Do not stop simply because a PR merged, a checkpoint was created or one task finished.

When execution cannot continue, record the exact remaining frontier and resumption conditions.

## Output

Keep reporting minimal:

**At selection:** Selected task, priority rationale, intended deliverable and execution route.

**At completion:** Verified result, remaining blockers and next task.

Do not substitute progress reporting for execution.

**Begin by recovering the live queue, calculating priority and executing the highest-ranked eligible work.**

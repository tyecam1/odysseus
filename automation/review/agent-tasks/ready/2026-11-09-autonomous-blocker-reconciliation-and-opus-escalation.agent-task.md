---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-09-autonomous-blocker-reconciliation-and-opus-escalation
title: "Resolve legacy blockers autonomously and qualify bounded Opus-medium adjudication"
status: ready
priority: high
task_type: orchestration-reliability
created_by: operator-directed-chatgpt
created_at: 2026-11-09T12:31:00+00:00
executor: claude_subscription
execution_mode: staged-implementation-and-real-path-pilot
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: dev
related_tasks:
  - 2026-09-01-human-attention-wip-autonomous-dispatch
  - 2026-09-13-operating-contract-model-role-evaluation-system
---

# Autonomous blocker reconciliation and bounded Opus adjudication

## Operator instruction

Minimise attention spent on false or routine human blockers. Existing blocked
work must be rechecked and autonomously resolved, rerouted or retired where
permitted, rather than parked indefinitely. Prefer authenticated Claude Opus
`opus` at **medium effort** for consequential unresolved adjudication after a
cheap evidence check. This preference is recorded in Odysseus `AGENTS.md`
and the `START-AGENTIC.md` entry point; it does not authorise a new router,
model-version pin or bypass of protected approvals.

## Scope and ownership

Extend the **existing** Odysseus portfolio/queue observation and central
routing/worker contracts. The existing
`2026-09-01-human-attention-wip-autonomous-dispatch` task owns the broader
operating-loop ambition; this card is its narrow unblock/acceptance slice,
not a second controller. Reuse the model-role evaluation task for learning
and comparison. Keep PhD and Misumi decisions and file mutations inside
their respective owner repositories; cross-repository discovery is read-only
until their existing authority and preflight allow a write.

## Implementation sequence

1. **Reconcile reality.** Inventory the current `blocked`, `ready` and
   human-gated cards across Odysseus, Misumi and PhD. Compare file location,
   declared status, live dependencies/PRs, permissions, runtime availability
   and existing acceptance evidence. Do not assume an old `blocked_reason`
   is still true.
2. **Classify each claim:** `obsolete_or_superseded`,
   `already_delivered`, `agent_resolvable`,
   `temporary_external_dependency`, `reasoning_adjudication`, or
   `protected_human_gate`. Give an evidence pointer and next recheck event.
   A tag such as `executor: human` is not itself proof of a human-only gate.
3. **Ship the smallest legal remedy.** Where safe and within existing
   authority, fix access/configuration, retrieve public evidence, choose a
   qualified substitute, complete verification, or close/reclassify stale cards
   in their owner queue. For genuinely protected approval, prepare the exact
   minimal decision packet only after proving no permitted route suffices;
   never fabricate consent, permissions, safety clearance or a research claim.
4. **Qualify Opus as an adjudicator.** Inspect live provider/CLI/model-currency
   evidence. Use the current authenticated Claude Code `opus` rolling alias,
   **medium effort**, for a bounded unresolved high-value case if the route is
   already authorised and verified. If no Odysseus-approved Opus path exists,
   explicitly record the integration/qualification gap, continue with
   qualified alternatives, and implement the minimum compliant integration
   under the existing router with normal approval and regression gates.
   Do not claim the current Codex-only paid router supports Opus.
5. **Avoid loops.** Reconsider a blocked decision only on a meaningful
   dependency/evidence revision or a bounded scheduled recheck; de-duplicate
   escalation on work-item ID plus evidence revision. Do not repeatedly spend
   Opus calls on the same frozen facts or ask the human the same question.
6. **Pilot and reconcile.** Exercise a representative sample containing
   stale/superseded work, a routine repair, a conceptual ambiguity, a genuinely
   protected human action, and a provider/unreachable route. Run qualified
   independent verification, preserve leases and evidence, and update each
   owner's existing queue status only where the acceptance evidence warrants.

## Acceptance

- Live cross-repository blocker inventory identifies true and false blockers
  with source/revision and next-recheck events; at least six representative
  cases are independently verified. Do not equate sample size with coverage
  of the whole backlog.
- At least one real low-risk agent-resolvable blocked task is **completed and
  closed** through the existing preflight, permission, lease and verification
  path; a status-only move is insufficient.
- At least one genuine protected action remains gated in a regression test,
  while a stale false-positive human gate is resolved without operator
  involvement.
- Opus `opus` medium adjudication is observed with effective model, permission
  and usage evidence, **or** explicitly remains unqualified with an actionable
  route gap. Never mark the route accepted on a textual model reference alone.
- No duplicate queue, router, permission authority, credential store or
  research-evidence authority is introduced. Existing tests and an independent
  review pass before applicable merge/deployment.
- Record delivered, superseded, pending external, actually human-only and
  remaining unqualified-route counts. Continue eligible work rather than
  treating the residual queue as an operator to-do list.

## Stop rule

Stop this bounded implementation when the pilot and regression gates pass,
record the remaining evidence-based blockers, and return to shipping-first
execution. Expand scope only if a demonstrated failure affects the active
delivery path. The full legacy backlog remains owned by its existing queues.

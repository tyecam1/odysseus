---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-09-lazyusage-bounded-persistent-continuation
title: "Make /lazyUsage continue autonomously until governed work is delivered or genuinely exhausted"
status: ready
priority: high
task_type: skill-reliability
created_by: operator-directed-chatgpt
created_at: 2026-11-09T15:47:00+00:00
executor: claude_subscription
execution_mode: bounded-implementation-and-live-acceptance
execution_host: lab
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
  - 2026-09-28-persistent-blocked-route-rerouting-long-horizon
  - 2026-09-01-human-attention-wip-autonomous-dispatch
  - 2026-11-09-autonomous-blocker-reconciliation-and-opus-escalation
  - 2026-10-01-sol-packet-efficiency
inputs:
  - .claude/skills/lazyUsage/SKILL.md
  - START-AGENTIC.md
  - config/initialising-prompts.yaml
  - docs/initialising-prompts/estate-queue-priority-execution-v2.md
  - scripts/agentic_portfolio.py
  - docs/aoteru-model-host-routing-contract.md
allowed_paths:
  - .claude/skills/lazyUsage/**
  - scripts/**
  - tests/**
  - docs/**
  - automation/review/**
  - evals/prompt-applications/**
  - evals/prompt-evolution/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*.pdf"
---

# Bounded persistence for /lazyUsage

## Failure to correct

The live `/lazyUsage` activation completed infrastructure checks and then ended
without attempting an eligible task, partly because Sol verification was
quota-limited and the queue's old `approval_required: true` metadata was
treated as a blanket human gate. The operator wants a single invocation to
continue making useful progress, not to request another prompt after each
recoverable blocker.

## Deliverable

Extend the **existing** `/lazyUsage` session control and Odysseus continuation
contracts so an explicitly invoked skill autonomously selects, dispatches,
verifies, closes and moves to the next authorised work item within a **bounded**
session. The laptop remains only the interactive control surface; repository
execution occurs on the lab. No second scheduler, queue, daemon or router.

1. **Establish the actual CLI capability.** Inspect the currently installed
   Claude Code build and documentation. Test whether its native `/goal`
   lifecycle can actually be invoked programmatically by a skill, and what
   survives session turns, compaction, quota pauses and process exit. Do not
   assume text containing `/goal` executes it. If unsuitable, evaluate a
   skill-scoped `Stop` hook and select the smallest reliable native mechanism.
   Do not globally trap unrelated Claude sessions or replace Odysseus runtime
   authority with a laptop process.
2. **Bound continuation and preserve intent.** Keep the user's initial
   `/lazyUsage` invocation, current task ID and acceptance criteria, completed
   work, outstanding review debt, and a compact next-action checkpoint through
   turns/resumption using existing stores. Use explicit limits on consecutive
   continuation turns, paid/total calls, elapsed runtime and repeated identical
   failures. Honour user stop/interrupt, permission refusal and genuine terminal
   conditions; never infinite-loop a `Stop` hook.
3. **Handle partial blocks without terminating.** If an independent verifier
   is quota-limited, park only verification-dependent acceptance, retain the
   exact retry condition and dispatch other independently eligible work. If a
   proposed task has `approval_required: true`, inspect the **actual owner
   authority** before inferring that operator action is necessary. Resolve
   stale/false blockers and choose another eligible task where protected
   approval genuinely remains outstanding. A past reset time, missing provider
   quota reading, inaccessible home host or one moving PR is not global
   completion.
4. **Retain governance.** Preserve Odysseus preflight, worker eligibility,
   ParkLease/write isolation, independent verification, owner-specific research
   and safety gates, subscription model currency, the existing shipping-first
   preference and source traceability. Never reinterpret persistence as
   permission to bypass protections or self-approve a high-risk change.
5. **Deploy correctly.** Make code/test changes through the existing governed
   PR and merge process, use the current `dev` branch, update the installed
   laptop skill from the merged canonical version, and exercise the full
   laptop-initiated/lab-executed path. Evolve the immutable registered
   initialiser only if implementation evidence proves a semantic change is
   necessary; otherwise keep `estate-queue-priority-execution@v2` unchanged.

## Acceptance tests

- A fresh `/lazyUsage` invocation automatically advances beyond inventory and
  completes **one real low-risk eligible queued task**, including owner preflight,
  any required lease, independent verification, status reconciliation and a
  prompt-application trace. Merely answering a read-only question with counts
  supplied in the prompt does not satisfy this test.
- If Sol is quota-exhausted while independent GLM/deterministic work is eligible,
  the session chooses useful work rather than ending or substituting an
  unqualified verifier. Once the verified reset event arrives, the owed review
  remains discoverable without operator re-explanation.
- A stale `approval_required: true` card without a real owner-only gate does
  not stop the session; a genuinely protected human-only action remains gated.
- Verify successful completion, no eligible tasks, manual stop, permission
  denial, exhausted turn/cost budget, repeated-failure guard, compaction and
  session resumption. No repeated stop-hook loop or unattended spending.
- Record the actual Claude CLI version, chosen persistence mechanism and its
  limitations. Independently review the deployed behaviour, capture rollback,
  and update the existing `/lazyUsage` acceptance record truthfully.

## Stop rule

A session may stop only on verified completion/budget exhaustion, explicit user
stop, a genuine safety/authority boundary, or a documented frontier with no
remaining independently executable work. A pending model reset or review debt
alone is not a reason to claim that the goal was achieved. This task ships
only after the live skill-level acceptance test passes.

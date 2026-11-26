---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-26-avenue-to-develop-reservoir
title: "An avenue to develop: triage the inbox and generate unblocking work so agents are never idle"
status: ready
priority: high
task_type: implementation
created_by: operator-directed-claude-code
created_at: 2026-11-26T01:30:00+00:00
executor: claude_subscription
execution_mode: implementation
architecture: single-plus-verifier
architecture_rationale: "One implementing worker with deterministic tests, then independent cross-family review."
single_agent_baseline: "One qualified worker implements and tests against live repository evidence."
execution_host: lab
context_budget: medium
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - scripts/**
  - src/**
  - tests/**
  - docs/**
  - automation/review/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*token*"
  - "**/*password*"
inputs:
  - AGENTS.md
  - docs/aoteru-model-host-routing-contract.md
result_path: docs/runtime-work-packages/2026-11-26-avenue-to-develop.md
---
# An avenue to develop

## Why

On 2026-11-26 the frontier held 149 cards but only 47 were actionable and the last run found nothing feasible: 83 cards sit untriaged in the `inbox` buckets that no agent reads, and the rest were blocked on gates that the system itself could resolve. The owner's instruction: agents should always have an avenue to develop; they are ordered by priority only.

## Outcome

1. **Inbox triage**: a read-only pass that classifies each inbox card (ready as is / needs a scope / duplicate / superseded / owner-class) and writes proposals under `automation/review/triage/` for the advisor tier to accept; accepted ones are promoted through each repository's own propose/review/ratify path.
2. **Unblocking children**: when nothing is dispatchable, the planner derives work from `blocked_by` before anything else: a Zotero snapshot request, an attestation backfill, a card repair, a host re-pin, a failure diagnosis. (The sibling cards cover the mechanisms; this card makes the planner create and order them.)
3. **A reservoir, in this order when the ready queue is blocked**: verification debt on merged work; flaky-test and documentation drift fixes; challenger prompt versions through the prompt library (promote only if they beat the parent); read-only retrospectives that produce proposals; preparation that changes nothing for owner-labour cards (run sheets, analysis scripts).
4. **Guardrails**: internal repositories only through the normal PR lane; no new dependencies, accounts or integrations; each item cites the blocker or metric it improves and is de-duplicated against existing cards; at most three unmerged self-generated PRs per repository; owner-originated cards pre-empt at the next checkpoint; a weekly digest line lists what was self-generated.

## Verification

Tests on a fixture frontier: a fully gated queue yields unblocking and reservoir candidates in the stated order; the WIP cap holds; a self-generated item without a cited blocker is refused.

## Rules that apply to this card (owner standing rules, 2026-11-06 and 2026-11-26)

- Internal Odysseus work only, through the normal branch, test, independent-review and PR lane. Sol review first (labelled GLM only if Sol is unavailable). Merge decisions follow the owner's merge rule.
- No new accounts, credentials, API keys, paid services, third-party dependencies or external writes. If a stage needs one, stop and leave a precise owner debt (`protected_handoff`); never work around it.
- Priority order is the only ordering. Do not add deadlines, time-boxes or concurrency caps of your own.
- Never touch owner approval, delegation or card-approval code paths except where this card names them, and never widen what a model may approve.
- Record the actual model used in every verification record.

## Plan (written 2026-11-26 by the controller; step 0 is to verify it against HEAD)
**Goal in one line.** When nothing is dispatchable, have the planner propose unblocking children first, then reservoir work, in a fixed order under guardrails, and triage the inbox read-only.
**Already done / do not redo:** src/lazy_usage_coordinator.py and src/lazy_usage_runtime.py already order by priority only. src/prompt_library.py already gates challenger prompts (`register_child`, `promote`). The sibling cards own the mechanisms (card hygiene, Zotero snapshot, mechanical verification); this card only creates and orders their children.
**Steps:**
0. Grep HEAD for the frontier builder, inbox buckets, `blocked_by`, skip reasons, de-duplication, PR records and the digest. Correct this plan.
1. Inbox triage (read-only): classify each inbox card as ready, needs a scope, duplicate, superseded or owner-class, using the existing checker and deterministic matching. Write proposals under automation/review/triage/<repo>/. Test: a fixture inbox hits every class; canonical hashes are unchanged.
2. Unblocking children: when the dispatchable set is empty, map each `blocked_by` or skip reason to a child (Zotero snapshot request, attestation backfill, card repair, host re-pin, failure diagnosis), ordered by parent priority. Test on a fully gated fixture.
3. Reservoir next, in this order: verification debt on merged work; flaky-test and documentation drift; challenger prompts through the prompt library; read-only retrospectives; preparation for owner-labour cards. Priority is the only ordering within a tier. Test the order.
4. Guardrails: refuse items that cite no blocker or metric; de-duplicate against existing cards; hold self-generated work for any repository that already has three unmerged self-generated PRs; internal repositories only. One test for each.
5. Pre-emption: owner-originated cards displace self-generated ones at the next advisor checkpoint, never mid-execution. Test.
6. A weekly digest line listing self-generated items, added through an existing digest extension point. Test the line.
7. Write docs/runtime-work-packages/2026-11-26-avenue-to-develop.md (findings, a read-only dry run over a copy of today's frontier, actual model). Run full pytest and stop.
**Done when:**
- A gated fixture queue yields unblocking candidates, then reservoir candidates, in the stated order.
- The three-PR cap holds and an uncited item is refused.
- Triage writes only under automation/review/triage/ (hash check).
- Full suite green.
**Risks and stops:**
- Never promote triage proposals here. The advisor tier accepts them, and each repository's propose/review/ratify path promotes them.
- If a sibling card is unmerged, emit its child as a proposal citing that card; do not implement it here.
- The three-PR cap comes from the card; add no other caps, deadlines or scheduler.
**Ordering note:** Can land first, emitting children as proposals only; full value follows the three sibling cards. Unblocks continuous agent work.

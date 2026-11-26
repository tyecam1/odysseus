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

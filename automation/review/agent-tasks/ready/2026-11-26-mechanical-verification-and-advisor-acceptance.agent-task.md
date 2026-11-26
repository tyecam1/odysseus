---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-26-mechanical-verification-and-advisor-acceptance
title: "Mechanical verification from CI evidence, pre-registered acceptance criteria and an advisor-acceptance design"
status: ready
priority: high
task_type: design-and-staged-implementation
created_by: operator-directed-claude-code
created_at: 2026-11-26T01:30:00+00:00
executor: claude_subscription
execution_mode: staged-design-then-opt-in-implementation
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
result_path: docs/runtime-work-packages/2026-11-26-mechanical-verification.md
---
# Mechanical verification and evidence-based acceptance

## Why

Four cards wait on `verification_evidence` and one on owner acceptance for internal tools whose tests, review and live behaviour are already recorded. Those are mechanical or advisor-grade checks, not owner decisions.

## Outcome

1. **Mechanical verification**: when CI and the deterministic tests are green at the exact commit, a smoke check passed where the work is deployed, and an approving review from another model family is recorded, write the `verification_evidence` (`result: pass`, commit, ref, `verified_by` naming the actual checks) through the existing verified path, never by a model's say-so.
2. **Pre-registered acceptance criteria**: new implementation cards carry written, checkable criteria before work starts, so acceptance can be evidence-based.
3. **Advisor acceptance, design only plus an opt-in flag that ships OFF**: an advisor may accept an internal tool against its pre-registered criteria and the recorded evidence. Turning this on is an owner decision (it changes who accepts work); this card produces the design, the guarded implementation behind a default-off switch, and the exact one-line question for the owner. It must not enable itself.
4. Human verification stays for: material sent to other people in the owner's name, physical-world results, and canonical thesis claims (which keep their repository's propose/review/ratify path).

## Verification

Tests: evidence is written only when every named check is present for that exact commit; a changed commit invalidates it; the advisor-acceptance path refuses to run while its switch is off.

## Rules that apply to this card (owner standing rules, 2026-11-06 and 2026-11-26)

- Internal Odysseus work only, through the normal branch, test, independent-review and PR lane. Sol review first (labelled GLM only if Sol is unavailable). Merge decisions follow the owner's merge rule.
- No new accounts, credentials, API keys, paid services, third-party dependencies or external writes. If a stage needs one, stop and leave a precise owner debt (`protected_handoff`); never work around it.
- Priority order is the only ordering. Do not add deadlines, time-boxes or concurrency caps of your own.
- Never touch owner approval, delegation or card-approval code paths except where this card names them, and never widen what a model may approve.
- Record the actual model used in every verification record.

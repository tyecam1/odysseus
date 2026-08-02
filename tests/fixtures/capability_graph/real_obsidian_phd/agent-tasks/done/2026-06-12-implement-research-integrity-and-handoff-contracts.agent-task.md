---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-12-implement-research-integrity-and-handoff-contracts
title: Implement research integrity and handoff contracts
status: done
priority: high
task_type: implementation
created_by: human
created_at: 2026-06-12T12:00:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/architecture/research-integrity-and-handoff-contracts.md
  - automation/review/platform-evaluations/research-integrity-pattern-adoption.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/architecture/odysseus-consolidated-system-design.md
  - automation/docs/verification-routing-policy.md
  - automation/docs/agent-task-frontmatter-schema.md
  - automation/docs/agent-ecosystem-centralisation-design.md
outputs:
  - automation/review/architecture/research-integrity-and-handoff-contracts.md
  - automation/review/platform-evaluations/research-integrity-pattern-adoption.md
result_path: automation/review/architecture/research-integrity-and-handoff-contracts.md
review_report_path: automation/review/platform-evaluations/research-integrity-pattern-adoption.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes:
  - 2026-06-12-adapt-hermes-verification-patterns
duplicates: []
notes: "Consolidates the ARS integrity/handoff pattern workstream and the Hermes checkpoint-verification task into one capability-family task. Draft contracts stage review-side; promotion into automation/docs/** and any Scripts/automation tests/config travel only inside the linked draft PR under the PR review gate."
---

# Task brief

## Objective

Adapt Academic Research Skills and Hermes-style patterns into Odysseus contracts: research integrity gates, cross-agent handoff schemas, data-access levels, provenance packets, and checkpoint/proof-carrying-output requirements. Contracts, not frameworks — neither ARS nor Hermes is installed.

## Deliverables (staged review-side, promoted via draft PR)

1. Integrity gate contract: blocking gates with override audit, high-risk versus light gates per task type, the seven-mode AI research failure checklist, and how gate failures map to `blocked`/`review`/`rejected`.
2. Handoff schema contract: cross-agent handoff fields, `HANDOFF_INCOMPLETE`, task-local `continuation_state`, and the rule that builder ≠ verifier for high-risk work (V2 stays human).
3. Data-access level policy: `data_access_level` metadata and explicit intake declarations including `no_experiments_declared`.
4. Provenance packet (Material Passport) structure compatible with the DRM/evidence workflow and the trust ladder.
5. `verification_evidence` block definition for review-side outputs and PR summaries (commands run, tests run, paths consulted, open assumptions, verifier recommendation).
6. Adoption report: adopted / adapted / rejected patterns, with explicit rejection of wholesale ARS, a second paper pipeline, and Hermes as a framework.

## Stop conditions

Block if implementation would create a second task lifecycle, a second research pipeline, canonical write paths, proof-system dependencies, trust-tier upgrades by gate passage, or validation bureaucracy that blocks useful work without improving safety.

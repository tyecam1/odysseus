---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-16-orchestrate-karpathy-wiki-hardening
title: "Orchestrate Karpathy wiki hardening"
status: done
priority: high
task_type: orchestration
created_by: chatgpt
created_at: 2026-07-16T11:00:00+01:00
claimed_by: fable-sol-route-loop
claimed_at: 2026-07-17T13:37:30+01:00
completed_by: fable-sol-route-loop
completed_at: 2026-07-17T13:49:00+01:00
verification_verdict: accept
verification_by: human

executor: codex_subscription
execution_mode: central-orchestrator
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false

verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true

repo: tyecam1/obsidian-PhD
branch: agent/karpathy-wiki-hardening-work-items
allowed_paths:
  - automation/review/**
  - automation/docs/**
  - Scripts/**
  - .github/**
  - 08-template/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
  - 04-supportDesign/**
  - 10-inbox/**
  - 11-projects/**
  - 12-log/**
  - My Library.bib
  - 02-library/My Library.bib
  - "**/*.pdf"

inputs:
  - automation/review/repo-governance/2026-07-15-post-merge-consolidation-truth-map.md
  - automation/review/repo-governance/2026-07-16-karpathy-llm-wiki-hardening-ultraplan.md
  - automation/docs/central-operating-contract.md
  - automation/docs/agent-task-frontmatter-schema.md
  - automation/review/agent-tasks/review/2026-07-16-define-currency-and-derived-trust-contract.agent-task.md
  - automation/review/agent-tasks/review/2026-07-16-add-write-time-entity-resolution-gate.agent-task.md
  - automation/review/agent-tasks/review/2026-07-16-document-trust-propagation-procedure.agent-task.md
  - automation/review/agent-tasks/review/2026-07-16-implement-semantic-anti-drift-audit.agent-task.md
  - automation/review/agent-tasks/review/2026-07-16-prepare-stale-surface-currency-ledger.agent-task.md
outputs:
  - automation/review/routine-reports/repo-governance/2026-07-16-karpathy-hardening-orchestration-report.md
  - automation/review/decision-packets/2026-07-16-karpathy-hardening-residuals.decision-packet.md
  - pull_request: bounded consolidation-ladder PRs
result_path: automation/review/routine-reports/repo-governance/2026-07-16-karpathy-hardening-orchestration-report.md
review_report_path: automation/review/decision-packets/2026-07-16-karpathy-hardening-residuals.decision-packet.md
handoff_model: codex_work_package
handoff_prompt_path: automation/review/agent-tasks/review/2026-07-16-orchestrate-karpathy-wiki-hardening.agent-task.md

operator_decision_path: ""
linked_pr: "#426"
supersedes: []
duplicates: []

notes: "Coordinate the five bounded work items through existing consolidation PRs 3, 5, 6, and 7. Do not bypass PR 2, PR 4, canonical gates, or the one-backlog rule."
---

# Orchestrate Karpathy wiki hardening

## Objective

Integrate document currency, trust propagation, write-time entity resolution, semantic anti-drift, and stale-surface migration into the existing consolidation ladder without creating a parallel wiki architecture or planning surface.

## Prerequisites

1. Rebase on current `main`.
2. Read the central operating contract and 2026-07-15 consolidation truth map.
3. Confirm whether consolidation PR 2 has landed.
4. Search the full agent-task lifecycle and open PRs for duplicate or superseding work.
5. Preserve PR 4 in the existing sequence. Do not let this programme bypass review-lane and backlog consolidation.

## Execution order

1. Route W1 and W2 into consolidation PR 3 only after PR 2 is complete.
2. Allow existing PR 4 to proceed in sequence.
3. Route W3 into consolidation PR 5.
4. Route W4 into consolidation PR 6 after W1 to W3 establish the required contracts.
5. Route W5 into consolidation PR 7 after W4 can produce evidence-backed candidate findings.
6. Keep every PR independently revertible and narrowly scoped.

## Required controls

- No new artifact types.
- No global frontmatter migration.
- No automatic canonical merge, rename, split, supersession, or trust upgrade.
- No model-only truth adjudication.
- No canonical stale-surface changes from this orchestration task.
- No new queue, backlog, dashboard, retrieval engine, or scheduler.
- Capability documentation and tests must change in the same PR as executable behaviour.
- Each lane must stop when its declared prerequisite is absent.

## Required outputs

Create one orchestration report containing:

1. current prerequisite and duplicate check;
2. final PR allocation for W1 to W5;
3. files changed per lane;
4. tests and validator results;
5. unresolved decisions and blockers;
6. confirmation that no canonical research or external system was mutated;
7. confirmation that no new planning surface was created.

Create one residual decision packet only when human judgement remains. Do not create a packet merely to restate completed work.

## Acceptance criteria

- Every child task is completed, blocked with a named prerequisite, or explicitly superseded by a cited task.
- The original seven-PR consolidation order remains intelligible.
- W1 to W5 each map to exactly one implementation PR.
- No child scope is silently merged into a broader unrelated PR.
- Agent-task lint, focused tests, full validation, validator ratchet, capability-truth tests where relevant, and `git diff --check` are reported.
- Independent review confirms there is no canonical mutation or planning-layer duplication.

## Stop conditions

Stop the affected lane when:

- PR 2 is incomplete;
- an existing task already owns the same outcome;
- implementation requires mass canonical edits;
- trust vocabularies are ambiguous;
- semantic findings cannot expose their source basis;
- false-positive noise is too high for an advisory tool;
- any change would widen autonomous write authority.

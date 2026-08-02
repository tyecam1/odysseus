---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-29-evidence-authority-repair-batch-plan
title: Plan evidence authority repair batches
status: done
priority: high
task_type: evidence-readiness
created_by: codex-roadmap-router
created_at: 2026-06-29T18:30:00+01:00
executor: claude_subscription
execution_mode: handoff
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
branch: ""
allowed_paths:
  - automation/review/routine-reports/repo-roadmap/2026-06-29-evidence-authority-repair-batch-plan.md
  - automation/review/decision-packets/2026-06-29-evidence-authority-repair-batches.decision-packet.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 06-datasets/07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/docs/current-capabilities.md
  - automation/docs/drm-mapping-rules.md
  - automation/docs/annotation-backfill-promotion-workflow.md
  - Scripts/automation/evidence_authority.py
  - Scripts/automation/validator.py
  - 02-library/02-evidence/**
outputs:
  - automation/review/routine-reports/repo-roadmap/2026-06-29-evidence-authority-repair-batch-plan.md
  - automation/review/decision-packets/2026-06-29-evidence-authority-repair-batches.decision-packet.md
result_path: automation/review/routine-reports/repo-roadmap/2026-06-29-evidence-authority-repair-batch-plan.md
review_report_path: automation/review/routine-reports/repo-roadmap/2026-06-29-evidence-authority-repair-batch-plan.md
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: automation/review/decision-packets/2026-06-29-evidence-authority-repair-batches.decision-packet.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Judgement-heavy batching task for evidence authority repair. Produce a decision packet only; do not rewrite evidence notes or promote machine-derived evidence."
---

# Task: Plan evidence authority repair batches

## Objective

Create a small set of evidence-authority repair batches from the validator backlog, prioritising the defects that most directly weaken source traceability and claim safety.

## Required output

Write:

- `automation/review/routine-reports/repo-roadmap/2026-06-29-evidence-authority-repair-batch-plan.md`
- `automation/review/decision-packets/2026-06-29-evidence-authority-repair-batches.decision-packet.md`

## Required content

- Batch candidates grouped by paper family or provenance failure mode.
- First three recommended repair batches, with estimated note count and why each matters.
- Required human checks before any canonical evidence note edit.
- Explicit non-goals for extraction-derived or machine-applied material.

## Acceptance criteria

- The decision packet lets the operator approve, reject, or defer each repair batch.
- The plan distinguishes missing frontmatter, invalid authority, unresolved paper links, and extraction-support-only provenance.
- No `02-library/02-evidence/**` files are edited.

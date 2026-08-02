---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-06-s2-protocol-skeleton
title: "S2 benchmark protocol skeleton"
status: done
priority: medium
task_type: research-support-packet
created_by: chatgpt
created_at: 2026-07-06T13:45:00+01:00
executor: codex_subscription
execution_mode: implementation
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: codex/s2-protocol-skeleton-20260706
allowed_paths:
  - automation/review/**
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
  - "**/*.pdf"
inputs:
  - automation/review/s2-benchmark-design/2026-07-04-s2-constrained-access-point-cell-benchmark-scaffold.md
  - automation/review/s2-benchmark-design/2026-07-06-s2-pre-blackout-capture-packet.md
  - 10-inbox/complete/prepare-richard-nmis-benchmark-review-package.md
outputs:
  - automation/review/s2-benchmark-design/2026-07-06-s2-benchmark-protocol-skeleton.md
result_path: automation/review/s2-benchmark-design/2026-07-06-s2-benchmark-protocol-skeleton.md
review_report_path: automation/review/s2-benchmark-design/2026-07-06-s2-benchmark-protocol-skeleton.md
handoff_model: codex_work_package
operator_decision_path: automation/review/s2-benchmark-design/2026-07-06-s2-benchmark-protocol-skeleton.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Dependent on capture packet or explicit assumption approval. Review-side protocol skeleton only."
---
# S2 benchmark protocol skeleton

## Goal

Create a review-side protocol skeleton for the sensing-first constrained-access benchmark.

## Gate

Run only after capture inputs exist or Tye explicitly approves proceeding on flagged assumptions.

## Acceptance criteria

- Protocol skeleton is coherent enough for supervisor review.
- Assumptions are marked as assumptions.
- Chemical-free mock-up scope is preserved.
- Live-human entry stays downstream unless separately approved.

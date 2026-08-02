---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-06-operator-decision-surface-refresh
title: "Refresh operator decision surface"
status: done
priority: high
task_type: review-surface-refresh
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
branch: codex/operator-decision-surface-refresh-20260706
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
  - 10-inbox/operator-decision-inbox.md
  - 10-inbox/operator-decision-cards/**
  - automation/review/operator-decisions/records/**
outputs:
  - automation/review/routine-reports/operator-decisions/2026-07-06-decision-surface-refresh.md
result_path: automation/review/routine-reports/operator-decisions/2026-07-06-decision-surface-refresh.md
review_report_path: automation/review/routine-reports/operator-decisions/2026-07-06-decision-surface-refresh.md
handoff_model: codex_work_package
operator_decision_path: automation/review/routine-reports/operator-decisions/2026-07-06-decision-surface-refresh.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Review-side refresh report. 10-inbox writes must be handled by the central orchestration task or separately approved task."
---
# Refresh operator decision surface

## Goal

Classify the current decision surface as live, stale, superseded, resolved, or blocked.

## Tasks

1. Inspect the operator inbox, cards, and records.
2. Produce a path-exact refresh report.
3. Do not execute decisions.

## Acceptance criteria

- Every visible decision has a state.
- Exact source paths are listed.
- Any stale generated surface is clearly flagged.

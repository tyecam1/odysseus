---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-29-operator-cockpit-minimum-spec
title: Specify minimum operator cockpit for repo health
status: done
priority: medium
task_type: critique
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
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/routine-reports/repo-roadmap/2026-06-29-operator-cockpit-minimum-spec.md
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
  - 00-dashboards/current-priorities.md
  - 00-dashboards/rc-control.md
  - automation/README.md
  - automation/docs/current-capabilities.md
  - automation/docs/operator-decision-inbox.md
  - automation/docs/research-engine-objective-control.md
  - automation/review/agent-tasks/**
outputs:
  - automation/review/routine-reports/repo-roadmap/2026-06-29-operator-cockpit-minimum-spec.md
result_path: automation/review/routine-reports/repo-roadmap/2026-06-29-operator-cockpit-minimum-spec.md
review_report_path: automation/review/routine-reports/repo-roadmap/2026-06-29-operator-cockpit-minimum-spec.md
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Design the minimum operator cockpit as a report/spec only. Do not create or edit dashboards."
---

# Task: Specify minimum operator cockpit for repo health

## Objective

Define the smallest useful operator cockpit that compresses live health signals without creating another hand-maintained dashboard.

## Required output

Write `automation/review/routine-reports/repo-roadmap/2026-06-29-operator-cockpit-minimum-spec.md`.

## Required content

- Signals to include: ready/blocked/review agent tasks, validator top debt classes, evidence authority backlog, standards path drift, review-retention status, and current promotion candidates.
- One proposed generated output path and update cadence.
- One anti-scope section naming what should not become dashboard clutter.
- A migration path from current hand-maintained snapshots.

## Acceptance criteria

- The spec is implementable as one generated review-side report.
- It does not require editing `00-dashboards/**` during the first implementation.
- It names exactly which existing command outputs can feed the cockpit.

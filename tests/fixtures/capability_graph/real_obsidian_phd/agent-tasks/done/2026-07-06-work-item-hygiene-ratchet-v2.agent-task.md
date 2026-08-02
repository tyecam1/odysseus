---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-06-work-item-hygiene-ratchet-v2
title: "Work-item hygiene ratchet v2"
status: done
priority: medium
task_type: automation-qa
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
branch: codex/work-item-hygiene-ratchet-v2-20260706
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
  - Scripts/automation/**
  - automation/review/routine-reports/central-codex-outstanding-work/2026-07-04-orchestration-run-report.md
outputs:
  - automation/review/routine-reports/work-item-hygiene/2026-07-06-ratchet-v2-report.md
result_path: automation/review/routine-reports/work-item-hygiene/2026-07-06-ratchet-v2-report.md
review_report_path: automation/review/routine-reports/work-item-hygiene/2026-07-06-ratchet-v2-report.md
handoff_model: codex_work_package
operator_decision_path: automation/review/routine-reports/work-item-hygiene/2026-07-06-ratchet-v2-report.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Review-side design/report task. Automation-code changes require a separate implementation task or central orchestration authority."
---
# Work-item hygiene ratchet v2

## Goal

Design a diff-scoped or ratcheted work-item hygiene check that prevents new mess without blocking on historical vault debt.

## Acceptance criteria

- No whole-vault noisy gate is introduced.
- New debt is caught where feasible.
- Historical debt is not turned into a false blocker.
- Report states whether the check should be advisory, ratcheted, or required.

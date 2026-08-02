---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-06-github-residue-closeout-packet
title: "GitHub residue close-out packet"
status: done
priority: medium
task_type: repo-residue-review
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
branch: codex/github-residue-closeout-20260706
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
  - automation/review/decision-packets/2026-07-04-outstanding-work-residuals.decision-packet.md
  - automation/review/implementation-sequence-2026-07-02.md
  - github_issue: 371
  - github_issue: 373
  - github_issue: 404
outputs:
  - automation/review/routine-reports/repo-hygiene/2026-07-06-github-residue-closeout.md
result_path: automation/review/routine-reports/repo-hygiene/2026-07-06-github-residue-closeout.md
review_report_path: automation/review/routine-reports/repo-hygiene/2026-07-06-github-residue-closeout.md
handoff_model: codex_work_package
operator_decision_path: automation/review/routine-reports/repo-hygiene/2026-07-06-github-residue-closeout.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Re-scope live GitHub residue only. Do not close issues unless explicitly instructed by Tye."
---
# GitHub residue close-out packet

## Goal

Re-scope live residue for issues #371, #373, and #404 after recent merged PRs.

## Acceptance criteria

- Each issue has a current state and exact evidence path.
- Stale wording is identified.
- Human-only actions are separated from Codex-safe actions.
- No issue is closed automatically.

---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-11-branch-protection-main
title: Enable branch protection on main
status: ready
priority: high
task_type: human-approval
created_by: claude-system-review
created_at: 2026-06-11T14:59:00+01:00
executor: human
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths: []
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/routine-reports/system-design-review/2026-06-11-odysseus-research-engine-review.md
outputs: []
result_path: ""
review_report_path: ""
handoff_model: ""
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Addresses review finding F1. GitHub settings mutation is external mutation: human executor only. Confirmed unprotected via API 404 on 2026-06-11."
---

# Task: Enable branch protection on main

## Objective

GitHub repo settings (TCR, ~10 minutes): require a pull request before merging with 1 approving review; dismiss stale approvals on new commits; forbid force pushes and deletions; once `2026-06-11-ci-gate-truth-tests-lint-validator` lands, mark its CI workflow as a required status check.

## Why

The vault's safety model ("producer never merges", "human review is the ceiling", canonical paths human-gated) is currently convention only; nothing prevents direct pushes to main or self-merge. This also satisfies the open checklist item in the mobile approval packet (PR #346), which assumes protected promotion-class paths.

## Acceptance criteria

Protection rules active on `main` (API no longer returns 404); a test push to main is rejected; record the decision in the operator decision flow and mark this task done.

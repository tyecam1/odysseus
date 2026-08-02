---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-11-obsidian-git-conflict-containment
title: Contain obsidian-git conflict artifacts and harden authoring sync
status: done
priority: medium
task_type: implementation
created_by: claude-system-review
created_at: 2026-06-11T14:59:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
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
outputs:
  - automation/docs/obsidian-git-conflict-containment.md
  - automation/review/platform-evaluations/2026-06-16-obsidian-git-conflict-containment.md
  - Scripts/automation/tests/test_git_conflict_validation.py
result_path: automation/review/platform-evaluations/2026-06-16-obsidian-git-conflict-containment.md
review_report_path: automation/review/platform-evaluations/2026-06-16-obsidian-git-conflict-containment.md
handoff_model: codex_work_package
handoff_prompt_path: "automation/review/handoff-prompts/2026-06-11-obsidian-git-conflict-containment.codex-work-package.md"
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Implemented by Codex on 2026-06-16 under explicit operator authorization after rebase. The validator detects/quarantines only; it does not delete or rewrite operator files."
---

# Task: Obsidian-git conflict containment

## Objective

1. Validator rule detecting git-conflict artifacts (conflict markers `<<<<<<<`/`=======`/`>>>>>>>` inside vault Markdown, and obsidian-git conflict files such as `conflict-files-obsidian-git.md`) anywhere outside `automation/review/**`; report fail-closed so they cannot merge unnoticed, especially under canonical roots.
2. Documented authoring-sync hygiene: recommended obsidian-git settings (pull-rebase, no auto-push of conflicted state) and a short operator runbook for recovering the chronically mid-merge laptop checkout.

## Change scope (via draft PR)

`Scripts/automation/validator.py` + tests; one short doc (location per existing docs layout); capability docs in the same change.

## Acceptance criteria

Fixture files with conflict markers under a canonical path fail `validate`; clean vault passes; runbook reviewed by operator; no operator files deleted or rewritten by the rule.

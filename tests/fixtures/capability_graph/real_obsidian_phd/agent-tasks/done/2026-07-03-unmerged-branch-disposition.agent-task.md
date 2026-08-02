---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-07-03-unmerged-branch-disposition
title: Classify unmerged branches with evidence
status: done
priority: high
task_type: repo-hygiene
created_by: codex
created_at: 2026-07-03T12:38:27+01:00
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
  - automation/review/routine-reports/repo-hygiene/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/decision-packets/2026-07-03-repo-future-operating-plan.decision-packet.md
  - automation/review/decision-packets/2026-07-03-first-five-work-items.dispatch.md
  - automation/review/decision-packets/2026-07-03-pr-403-405-combined-fable-review.decision-packet.md
  - automation/review/routine-reports/repo-hygiene/2026-07-02-branch-hygiene-sweep.md
  - automation/review/routine-reports/repo-hygiene/2026-07-03-chatgpt-branch-disposition-manifest.md
  - GitHub branch and PR state for tyecam1/obsidian-PhD
outputs:
  - automation/review/routine-reports/repo-hygiene/2026-07-03-unmerged-branch-disposition.md
result_path: automation/review/routine-reports/repo-hygiene/2026-07-03-unmerged-branch-disposition.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Disposition report exists and awaits human approval plus heartbeat gate before any deletion. No branch deletion or pruning was performed. R3 remains off."
---

# Task: Classify unmerged branches with evidence

## Owner and route

Owner: Codex.
Route: agent-task -> Codex.

## Objective

Classify all currently unmerged remote branches with evidence so a later human decision can separate delete-safe, held, and human-review branch groups.

## Required output

Create one branch disposition report at `automation/review/routine-reports/repo-hygiene/2026-07-XX-unmerged-branch-disposition.md`.

For each unmerged branch, report:
- branch name
- current remote SHA
- last commit date
- unique commit count versus `main`
- paths touched by unique commits
- related PR or merge evidence, where available
- disposition group and rationale

## Acceptance criteria

- Every unmerged branch is classified with evidence.
- `rescue/*` branches are always kept.
- The existing `chatgpt/*` manifest state is preserved: 15 expected, 15 live, with hold and human-review branches separated.
- No branch deletion occurs.
- No branch deletion command is executed.
- No canonical research content is touched.

## Stop condition

Stop if any classification would require touching `03-concept/**`, Zotero state, supervisor-facing material, evidence trust tiers, or research claims. Stop if the task would require executing or staging any branch deletion. W4 remains held and must not be converted by this task.

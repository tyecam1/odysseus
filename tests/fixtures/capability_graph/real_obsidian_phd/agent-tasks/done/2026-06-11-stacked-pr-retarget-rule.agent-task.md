---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-11-stacked-pr-retarget-rule
title: Add stacked-PR retarget rule to the PR publishing contract
status: done
priority: high
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
  - automation/docs/automation-pr-publishing-contract.md
outputs: []
result_path: ""
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/348"
supersedes: []
duplicates: []
notes: "Addresses review finding F4 (#343 stranding class). Trivial effort, high leverage."
claimed_by: claude_subscription
claimed_at: 2026-06-11T15:11:22+01:00
---

# Task: Stacked-PR retarget rule

## Objective

Amend the PR publishing contract with one binding rule: a PR stacked on another PR's branch must be retargeted to `main` before or immediately when its base merges; merging a stacked head into an already-merged base branch is a defect. Prefer forbidding stacking by automation producers entirely unless the base is expected to merge unsquashed.

## Change scope (via draft PR)

`automation/docs/automation-pr-publishing-contract.md` (and any routine that opens PRs, if it encodes base selection).

## Acceptance criteria

Rule present in the contract; producers' PR-opening code (if any encodes base refs) defaults to `main`; reference to incident #343/#344 as rationale.

## Close-out

Merged on `main` via PR #348 (commit `55ed7191`, `docs: stacked-PR retarget rule in PR publishing contract`). Deliverable `automation/docs/automation-pr-publishing-contract.md` confirmed present on `origin/main`. Status moved review -> done 2026-06-15.

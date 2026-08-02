---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-07-03-review-lane-batch-adjudication
title: Draft review-lane batch adjudication packet
status: done
priority: high
task_type: decision-packet
created_by: codex
created_at: 2026-07-03T12:38:27+01:00
executor: claude_subscription
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
  - automation/review/decision-packets/**
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
  - automation/review/agent-tasks/review/
  - automation/docs/agent-task-frontmatter-schema.md
  - GitHub PR history for tyecam1/obsidian-PhD
outputs:
  - automation/review/decision-packets/2026-07-03-review-lane-batch-adjudication.decision-packet.md
result_path: automation/review/decision-packets/2026-07-03-review-lane-batch-adjudication.decision-packet.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Draft packet exists and awaits human adjudication; do not execute lifecycle moves until approved and exact filenames are reconciled. R3 remains off."
---

# Task: Draft review-lane batch adjudication packet

## Owner and route

Owner: Fable.
Route: agent-task -> Fable.

## Objective

Batch the current files in `automation/review/agent-tasks/review/` into verdict groups so the human review load can be reduced without per-item review.

## Required output

Create one review-side decision packet at `automation/review/decision-packets/2026-07-XX-review-lane-batch-adjudication.decision-packet.md`.

The packet must group every review-lane task into exactly one of:
- `accept-and-close`
- `supersede`
- `reject`
- `needs-individual-review`

Do not move, rewrite, delete, or close any task file.

## Acceptance criteria

- Every file currently in `automation/review/agent-tasks/review/` appears in exactly one verdict group.
- `needs-individual-review` contains fewer than 10 items, unless the packet explains why the threshold is unsafe.
- Every `accept-and-close` claim cites concrete PR, commit, or merged-main evidence.
- The output remains a decision packet only and creates no new queue, authority layer, or planning surface.

## Stop condition

Stop and emit no adjudication packet if any proposed batch-accepted item would touch `03-concept/**`, Zotero state, supervisor-facing material, evidence trust tiers, or research claims. Those items must be placed in individual review, never batch accepted.

---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-07-03-blackout-work-plan-draft
title: Draft July-August blackout work plan
status: done
priority: medium
task_type: decision-packet
created_by: codex
created_at: 2026-07-03T12:38:27+01:00
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
  - 10-inbox/backlog.md
  - automation/review/agent-tasks/
  - 10-inbox/2026-07-01-s2-lab-blackout-human-triage.md
outputs:
  - automation/review/decision-packets/2026-07-03-blackout-work-plan-draft.decision-packet.md
result_path: automation/review/decision-packets/2026-07-03-blackout-work-plan-draft.decision-packet.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Draft packet exists and awaits human approval before becoming August routing authority. No human notes were moved. R3 remains off."
---

# Task: Draft July-August blackout work plan

## Owner and route

Owner: Fable.
Route: agent-task -> Fable.

## Objective

Draft a one-page blackout-compatible work plan for 2026-07-28 to 2026-08-28 that separates before-blackout, during-blackout, and after-blackout work.

## Required output

Create one review-side decision packet at `automation/review/decision-packets/2026-07-XX-blackout-work-plan.decision-packet.md`.

The packet must cover:
- S1 writing and evidence synthesis
- S2 specification and benchmark protocol work
- protocol, safety, and ethics preparation
- modelling and non-physical work
- review-debt burn-down
- compute reliability observation
- lab-dependent items that lack a booked July slot

## Acceptance criteria

- The draft is no more than one page.
- Every backlog item considered is routed to exactly one window: before 2026-07-28, 2026-07-28 to 2026-08-28, or after 2026-08-28.
- Lab-dependent items without a booked July slot are explicitly flagged.
- The output is a decision packet only and does not create a new planning surface.
- No canonical research content is touched.

## Stop condition

Stop if producing the draft would require moving, rewriting, deleting, or reclassifying any human note. Stop if the task would touch `03-concept/**`, Zotero state, supervisor-facing material, evidence trust tiers, or research claims. W4 remains held and must not be converted by this task.

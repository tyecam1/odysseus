---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-06-25-canonical-promotion-review-dashboard
title: Review automation packets for canonical promotion decisions
status: done
priority: high
task_type: critique
created_by: chatgpt-5.5
created_at: 2026-06-25T11:30:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/routine-reports/canonical-promotion-review/**
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
  - automation/review/**
  - automation/README.md
  - automation/docs/agent-task-frontmatter-schema.md
outputs:
  - automation/review/routine-reports/canonical-promotion-review/2026-06-25-agentic-promotion-review.md
  - automation/review/decision-packets/2026-06-25-canonical-promotion-review.decision-packet.md
result_path: automation/review/routine-reports/canonical-promotion-review/2026-06-25-agentic-promotion-review.md
review_report_path: automation/review/routine-reports/canonical-promotion-review/2026-06-25-agentic-promotion-review.md
handoff_model: claude_work_package
handoff_prompt_path: automation/review/handoff-prompts/2026-06-25-canonical-promotion-review-dashboard.md
operator_decision_path: automation/review/decision-packets/2026-06-25-canonical-promotion-review.decision-packet.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Highest-priority judgement-compression task: review accumulated automation packets and create concise approve/reject/defer decision packets for human review; no canonical mutation is allowed."
---
# Task: Review automation packets for canonical promotion decisions

## Objective

Use an intelligent model lane, preferably Claude Opus 4.8 or otherwise ChatGPT 5.5 Thinking, to review accumulated packets in `automation/review/**` and determine whether each serious candidate should be promoted into canonical vault files.

This task exists because the current failure mode is not lack of agent output; it is lack of disciplined promotion judgement.

## Required behaviour

- Inspect review-side packets and agent outputs.
- Identify only packets that plausibly deserve canonical promotion or closure.
- Produce a very concise promote/reject/defer judgement for each serious candidate.
- Surface those judgements through a governed review-side decision packet.
- Leave all canonical mutations human-gated.

## Non-goals

- Do not edit canonical files.
- Do not create new planning surfaces.
- Do not create another dashboard or inbox surface.
- Do not bulk-promote review material.
- Do not hide uncertainty behind confident wording.

## Acceptance criteria

- A review report exists at `automation/review/routine-reports/canonical-promotion-review/2026-06-25-agentic-promotion-review.md`.
- A decision packet exists at `automation/review/decision-packets/2026-06-25-canonical-promotion-review.decision-packet.md`.
- Each decision item has a verdict, target path, one-sentence justification, and concrete approve/reject meaning.
- Justifications are concise enough for same-day human approval.
- No canonical files are changed.

---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-04-j1-skill-formation-transfer-reporting-scout
title: Bounded scout — skill-formation pipeline under automation for §6 worker-attribute reporting
status: blocked
blocked_by: "§6 drafting start (execution gate; do not run while §3-§5 are undrafted)"
priority: low
task_type: evidence-readiness
created_by: claude_cowork
created_at: 2026-07-04T11:32:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: true
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/J1/2026-07-04-skill-formation-scout.md
  - automation/review/agent-tasks/**/2026-07-04-j1-skill-formation-transfer-reporting-scout.agent-task.md
denied_paths:
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/**
  - 07-standards/**
  - 00-dashboards/**
  - 11-projects/**
inputs:
  - 11-projects/tye/J1/j1-ground-truth-plan.md
  - 11-projects/tye/J1/j1-evidence-map.md
outputs:
  - automation/review/J1/2026-07-04-skill-formation-scout.md
result_path: automation/review/J1/2026-07-04-skill-formation-scout.md
notes: "Field blind spot identified 2026-07-03: everyone debates the incumbent worker's role; no perspective addresses how the next skilled worker is produced when entry-level learning tasks are automated. Ground truth §6 already lists 'training context' as a worker-attribute reporting element; this scout sharpens it to skill-formation pipeline and feeds §7 future work. Costs one paragraph in the paper — keep the scout proportionate."
---
# Task: Bounded scout — skill-formation pipeline under automation for §6 worker-attribute reporting

## Objective

Find a small set of sources on skill formation, apprenticeship pipelines, and learning-curve access under industrial automation, sufficient to support one §6 reporting element and one §7 future-work direction.

## Prompt

1. Zotero first, then bounded external search: skill formation/deskilling-vs-upskilling under robotisation, apprenticeship and tacit-skill acquisition where entry tasks are automated, training-context reporting in HRC studies.
2. Max 6 candidate sources; for each — claim offered, claim ceiling, and which §6 reporting element it supports.
3. One-paragraph recommendation: exact wording candidate for the sharpened §6 element ("training context" → skill-formation pipeline) and the §7 future-work sentence it earns.

## Hard constraints

- Do not execute until §6 drafting starts — this is deliberately parked to protect the §3 seed bottleneck.
- Max 6 candidates. Routes only, no ingestion, no manuscript prose, no plan edits.

## Acceptance criteria

§6 drafting inherits one evidenced reporting element and §7 one future-work direction, at the cost of a single reading pass.

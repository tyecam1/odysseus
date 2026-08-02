---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-01-s2-missing-experiment-research
title: Gather missing S2 sensing experiment research
status: done
priority: high
task_type: synthesis
created_by: chatgpt
created_at: 2026-07-01T00:00:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: true
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/s2-benchmark-design/2026-07-01-s2-missing-experiment-research.md
  - automation/review/agent-tasks/**/2026-07-01-s2-missing-experiment-research.agent-task.md
denied_paths:
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/**
  - 04-supportDesign/**
  - 07-standards/**
  - 00-dashboards/**
inputs:
  - 04-supportDesign/thesis-benchmark/s2-e1-minimum-safety-distance-benchmark.md
  - 04-supportDesign/thesis-benchmark/s2-e1-framework-safety-perception-literature-targeting.md
  - 04-supportDesign/thesis-benchmark/s2-e1-system-design-research-grounding.md
  - 10-inbox/2026-07-01-gather-missing-s2-experiment-research.md
outputs:
  - automation/review/s2-benchmark-design/2026-07-01-s2-missing-experiment-research.md
result_path: automation/review/s2-benchmark-design/2026-07-01-s2-missing-experiment-research.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: 10-inbox/2026-07-01-gather-missing-s2-experiment-research.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Review-side output exists at result_path. Await human verification; no canonical notes were modified."
---
# Task: Gather missing S2 sensing experiment research

## Recommended model

Claude Sonnet 5. Use Opus/Fable only if synthesis quality is poor.

## Objective

Produce a short research packet that fills the immediate evidence gaps for S2-E0/S2-E1 sensing and measurement validation.

## Prompt

The active experiment is not a live human-robot safety experiment. It is a sensing and metrology validation step for a glovebox-like constrained workspace. Read the listed inputs and use vault/Zotero evidence where available.

Write one packet to:

`automation/review/s2-benchmark-design/2026-07-01-s2-missing-experiment-research.md`

Include:

1. Evidence/options for RGB-D/D435F placement and calibration in constrained workspaces.
2. Ground-truth options for localisation error: printed grid, ArUco/AprilTag, robot logs/encoders, external measurement, or hybrid routes.
3. Single-view versus multi-view occlusion implications for robot arm and small-object tracking.
4. Practical feasibility of tracking 14-20 mm token-like objects, including when fiducials or larger surrogates are justified.
5. How to report detection rate, pose/location error, latency, occlusion, lost-track duration, confidence and uncertainty so later safety-control claims do not rely on hidden assumptions.
6. Minimal comparable examples of sensing validation before human-in-the-loop HRC claims.
7. A final section: what to ask Dino, what to ask Richard, and what remains unknown.

## Hard constraints

- Do not create or modify canonical evidence, decision, support-design or planning files.
- Do not invent citations.
- Do not make this a general HRC review.
- Do not introduce human participants before the sensing chain is characterised.
- Mark unknowns honestly.

## Acceptance criteria

The packet should directly improve the Dino and Richard communications and reduce S2-E0/S2-E1 experimental uncertainty.

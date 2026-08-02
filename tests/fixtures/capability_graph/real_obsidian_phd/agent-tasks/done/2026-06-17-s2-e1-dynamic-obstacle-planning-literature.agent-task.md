---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-17-s2-e1-dynamic-obstacle-planning-literature
title: Review recent dynamic-obstacle planning for close-proximity collaborative robot arms
status: done
priority: high
task_type: evidence-synthesis
created_by: chatgpt
created_at: 2026-06-17T17:16:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: true
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
allowed_paths:
  - automation/review/s2-benchmark-design/literature-reinforcement/2026-06-17-s2-e1-dynamic-obstacle-planning-literature.md
  - automation/review/agent-tasks/**/2026-06-17-s2-e1-dynamic-obstacle-planning-literature.agent-task.md
denied_paths:
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 02-library/**
  - 03-concept/**
  - 04-supportDesign/**
  - 07-standards/**
  - 00-dashboards/**
inputs:
  - 04-supportDesign/operator-task-fit-adaptive-support/experiment-design-ledger.md
  - 04-supportDesign/thesis-benchmark/system-model-v0.md
  - 04-supportDesign/thesis-benchmark/s2-experiment-decision-capture.md
outputs:
  - automation/review/s2-benchmark-design/literature-reinforcement/2026-06-17-s2-e1-dynamic-obstacle-planning-literature.md
operator_decision_path: 10-inbox/approve-s2-experiment-split-and-optimisation-boundaries.md
---
# Task: Review recent dynamic-obstacle planning for close-proximity collaborative robot arms

## Objective

Determine which recent robot-arm planning/control ideas are relevant to S2-E1's C2 condition:

> dynamic obstacle response to preserve minimum safety distance under multiple moving obstacles.

## Required output

Write one review-side packet to:

`automation/review/s2-benchmark-design/literature-reinforcement/2026-06-17-s2-e1-dynamic-obstacle-planning-literature.md`

Include:

1. Recent methods relevant to dynamic obstacles in close HRC: reactive replanning, task scaling, CBF, MPC, velocity obstacle / dynamic constraints, whole-body avoidance, safety-aware cost functions.
2. Whether each method supports **multiple dynamic obstacles** or only a single human/obstacle.
3. Whether each method requires online perception, known geometry, full robot model, human prediction, body tracking, or safety-rated sensing.
4. Which methods are realistic for S2-E1 as: scripted baseline, dynamic response condition, or later S4 candidate.
5. A recommendation for the narrowest C2 implementation that is experimentally valid but not overambitious.
6. A traceability table.

## Seed sources

- Parma et al. 2026, predictive CBF / ISO 10218 SSM.
- Tonola et al. 2025, reactive and safety-aware path replanning for collaborative applications.
- Maithania et al. 2025, proactive hierarchical CBF for close HRI.
- Liu et al. 2025, learning safety for obstacle avoidance via CBFs.
- Dastider and Lin 2022, SERA reactive whole-body obstacle avoidance.

## Hard constraints

- Do not choose the final S4 control route.
- Do not turn S2-E1 into a control-method contribution.
- Keep the output phrased as evidence for benchmark design.
- Identify gaps clearly, especially if multiple dynamic obstacles are weakly evidenced in close-proximity arm work.

## Acceptance criteria

The packet must answer:

> What should C2 minimally do so that it is more than static support but less than a full S4 controller?

---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-17-s2-e1-minimum-safety-distance-standards
title: Reinforce S2-E1 minimum safety distance from standards and recent SSM work
status: done
priority: high
task_type: evidence-synthesis
created_by: chatgpt
created_at: 2026-06-17T17:15:00+01:00
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
  - automation/review/s2-benchmark-design/literature-reinforcement/2026-06-17-s2-e1-minimum-safety-distance-standards.md
  - automation/review/agent-tasks/**/2026-06-17-s2-e1-minimum-safety-distance-standards.agent-task.md
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
  - 06-datasets/07-standards/raw/iso-ts-15066.md
  - 06-datasets/07-standards/raw/iso-13855.md
outputs:
  - automation/review/s2-benchmark-design/literature-reinforcement/2026-06-17-s2-e1-minimum-safety-distance-standards.md
operator_decision_path: 10-inbox/approve-s2-experiment-split-and-optimisation-boundaries.md
---
# Task: Reinforce S2-E1 minimum safety distance from standards and recent SSM work

## Objective

Clarify how S2-E1 should define and report **minimum safety distance** without overclaiming standards compliance.

The S2-E1 question is:

> Can a close-proximity collaborative robotic system avoid multiple dynamic obstacles to a minimum safety distance?

## Required output

Write one review-side packet to:

`automation/review/s2-benchmark-design/literature-reinforcement/2026-06-17-s2-e1-minimum-safety-distance-standards.md`

Include:

1. What ISO/TS 15066 and ISO 13855 imply for S2-E1 variables: separation distance, robot speed, human approach speed, stopping time, sensing latency, intrusion distance and workspace geometry.
2. What S2-E1 can honestly claim: standards-informed benchmark versus standards-compliant cell.
3. Recent SSM/control-filter evidence, especially 2025-2026 work using CBFs, predictive minimum separation, task scaling, SQP or SSM baselines.
4. A candidate minimum-distance reporting template for S2-E1.
5. A source traceability table with exact source, claim, relevance, and confidence.

## Seed sources

- `06-datasets/07-standards/raw/iso-ts-15066.md`
- `06-datasets/07-standards/raw/iso-13855.md`
- Parma et al. 2026, *Embedding ISO 10218 Safety Compliance in Robots via Control Barrier Functions for Human-Robot Collaboration*.
- Search forward/backward for recent SSM, ISO 10218, ISO/TS 15066, CBF, task-scaling, predictive separation, and minimum-distance HRC work.

## Hard constraints

- Do not claim compliance.
- Do not select the final controller.
- Do not create canonical standard rollups or decisions.
- Mark unsupported claims rather than filling them with generic safety language.

## Acceptance criteria

The result must let Tye write one defensible S2-E1 sentence beginning:

> In S2-E1, minimum safety distance is treated as...

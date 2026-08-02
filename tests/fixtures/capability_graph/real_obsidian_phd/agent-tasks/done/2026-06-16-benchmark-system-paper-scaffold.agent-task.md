---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-16-benchmark-system-paper-scaffold
title: Scaffold benchmark conference paper from a system perspective
status: done
priority: medium
task_type: writing-plan
created_by: chatgpt
created_at: 2026-06-16T09:20:00+01:00
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
  - automation/review/s2-benchmark-design/2026-06-16-benchmark-system-paper-scaffold.md
  - automation/review/agent-tasks/**/2026-06-16-benchmark-system-paper-scaffold.agent-task.md
denied_paths:
  - 01-research-plan/**
  - 02-library/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/**
  - 04-supportDesign/**
  - 07-standards/**
  - 00-dashboards/**
inputs:
  - 12-log/26-06/26-25/supervision-erfu-2026-06-15.md
  - automation/review/s2-benchmark-design/2026-06-16-system-architecture-and-communication-framework.md
  - automation/review/s2-benchmark-design/2026-06-16-experiment-question-split-and-boundaries.md
  - automation/review/s2-benchmark-design/2026-06-16-constrained-manipulation-literature-grounding-and-novelty.md
outputs:
  - automation/review/s2-benchmark-design/2026-06-16-benchmark-system-paper-scaffold.md
result_path: automation/review/s2-benchmark-design/2026-06-16-benchmark-system-paper-scaffold.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Meeting note flagged a conference paper output of the benchmark from a system perspective. This task creates the scaffold only after architecture/question packets exist."
---
# Task: Scaffold benchmark conference paper from a system perspective

## Objective

Prepare a conference-paper scaffold for the S2 benchmark from a system perspective.

The goal is not to write the paper prematurely. The goal is to make the benchmark build publishable by design, so the experiment records the right architecture, measures, boundaries and contribution from the beginning.

## Required output

Write one scaffold to:

- `automation/review/s2-benchmark-design/2026-06-16-benchmark-system-paper-scaffold.md`

Include:

1. **Candidate title options**.
2. **Contribution claim**: what the paper would contribute if the benchmark succeeds.
3. **Paper structure**: section-by-section outline.
4. **Figure/table plan**: system architecture, experiment scene, measure table, optimisation boundary table, validity-risk table.
5. **Evidence required during build**: what must be logged or photographed now to make the paper possible later.
6. **Go/no-go criteria**: when this should remain internal instead of becoming a paper.

## Hard constraints

- Do not write manuscript prose yet.
- Do not overclaim results before data exists.
- Do not make publication framing drive the experiment away from the PhD question.

## Acceptance criteria

The scaffold must change what Tye logs/builds now. If it is only a generic paper outline, it has failed.

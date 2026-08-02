---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-16-s2-experiment-question-split-and-boundaries
title: Define S2 experiment question split and optimisation boundaries
status: done
priority: high
task_type: synthesis
created_by: chatgpt
created_at: 2026-06-16T09:05:00+01:00
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
  - automation/review/s2-benchmark-design/2026-06-16-experiment-question-split-and-boundaries.md
  - automation/review/agent-tasks/**/2026-06-16-s2-experiment-question-split-and-boundaries.agent-task.md
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
  - 04-supportDesign/operator-task-fit-adaptive-support/experiment-design-ledger.md
  - 12-log/26-06/26-25/supervision-erfu-2026-06-15-s2-benchmark-discussion-prompts.md
outputs:
  - automation/review/s2-benchmark-design/2026-06-16-experiment-question-split-and-boundaries.md
result_path: automation/review/s2-benchmark-design/2026-06-16-experiment-question-split-and-boundaries.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: 10-inbox/approve-s2-experiment-split-and-optimisation-boundaries.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Resolve the meeting note's unresolved issue: multiple experiments, which one asks what, and what is optimised versus held constant."
---
# Task: Define S2 experiment question split and optimisation boundaries

## Objective

Turn the messy supervision outcome into a clear experiment sequence.

The output must answer: **which experiment asks which research question, what does each optimise, what does each measure, and what is intentionally not optimised?**

## Required output

Write one packet to:

- `automation/review/s2-benchmark-design/2026-06-16-experiment-question-split-and-boundaries.md`

Include:

1. **Experiment sequence table**: first obstruction-avoidance benchmark, downstream lost-part recovery demonstrator, later S3/S4 dependencies.
2. **Question per experiment**: one primary question and at most two secondary questions per experiment.
3. **Optimisation boundary**: optimised, measured-only, controlled/held constant, ignored/deferred.
4. **Validity risks**: what would make each experiment collapse into generic robotics or internal lab demo work.
5. **Minimum first experiment**: the smallest coherent experiment that still answers the PhD-relevant S2 question.
6. **Decision note draft**: concise wording Tye can copy into the experiment design ledger after approval.

## Hard constraints

- Do not promote lost-part recovery above dynamic obstruction avoidance.
- Do not select S3 human-factor instruments yet. Only identify candidate measure dependencies.
- Do not select S4 control method yet. Only identify behaviour-variation dependencies.
- Do not add extra experiments unless one is necessary to preserve validity.

## Acceptance criteria

The packet must force a decision. A list of options without a recommended sequence has failed.

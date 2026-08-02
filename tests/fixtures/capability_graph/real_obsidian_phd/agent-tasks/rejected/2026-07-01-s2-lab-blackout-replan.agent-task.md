---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-01-s2-lab-blackout-replan
title: Replan S2 around July-August lab blackout
status: rejected
priority: high
task_type: synthesis
created_by: chatgpt
created_at: 2026-07-01T00:00:00+01:00
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
  - automation/review/s2-benchmark-design/2026-07-01-s2-lab-blackout-replan.md
  - automation/review/agent-tasks/**/2026-07-01-s2-lab-blackout-replan.agent-task.md
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
  - 04-supportDesign/thesis-benchmark/index.md
  - 04-supportDesign/thesis-benchmark/s2-e1-minimum-safety-distance-benchmark.md
  - 11-projects/tye/annual reviews/1/annual-review-2026-research-report-draft-v2.md
  - 10-inbox/2026-07-01-s2-lab-blackout-human-triage.md
outputs:
  - automation/review/decision-packets/2026-07-03-blackout-work-plan-draft.decision-packet.md
  - automation/review/s2-benchmark-design/2026-07-04-s2-constrained-access-point-cell-benchmark-scaffold.md
result_path: automation/review/s2-benchmark-design/2026-07-04-s2-constrained-access-point-cell-benchmark-scaffold.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: 10-inbox/2026-07-01-s2-lab-blackout-human-triage.md
linked_pr: ""
supersedes: []
superseded_by: 2026-07-04-central-codex-outstanding-work-orchestration
duplicates: []
notes: "Superseded by the blackout decision packet plus the central S2 benchmark scaffold. No canonical benchmark notes were modified."
---
# Task: Replan S2 around July-August lab blackout

## Recommended model

Claude Sonnet 5. Use Opus 4.8 or Fable 5 only if Sonnet cannot produce a reliable synthesis from the provided vault context.

## Objective

Produce a short, decision-useful replan for S2 from 2026-07-01 to 2026-09-05 given that lab access is unavailable from 2026-07-28 to 2026-08-28.

## Prompt

You are reviewing the active S2 benchmark plan in `tyecam1/obsidian-PhD`. The active benchmark has already been corrected: S2-E1 is a sensing and measurement-validation experiment, not a live human separation-distance experiment.

Read the listed inputs and write one planning packet to:

`automation/review/s2-benchmark-design/2026-07-01-s2-lab-blackout-replan.md`

Include:

1. A split between work requiring Tye's physical lab access before 2026-07-28 and work that can be done during the 2026-07-28 to 2026-08-28 blackout.
2. A task sequence for S2-E0 and S2-E1 that protects the sensing-first granularity.
3. A list of decisions that require human judgement or supervisor input.
4. A list of tasks that are safe for agents to do without canonical writes.
5. A risk register with the top five failure modes, especially overclaiming safety, reopening benchmark scope, and wasting lab-access time on writing.
6. A concise recommendation for what Tye should do today.

## Hard constraints

- Do not modify canonical files under `03-concept`, `04-supportDesign`, `01-research-plan`, `02-library`, `07-standards`, or `00-dashboards`.
- Do not invent literature claims or pretend physical access has occurred.
- Do not propose introducing human participants before the sensing and uncertainty chain is characterised.
- Keep the output concise and operational.

## Acceptance criteria

The output must make it obvious what must happen before 2026-07-28, what belongs in the blackout, and what should wait until lab access resumes.

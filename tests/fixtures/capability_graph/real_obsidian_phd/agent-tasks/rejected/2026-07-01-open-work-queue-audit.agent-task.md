---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-01-open-work-queue-audit
title: Audit open work queue after conference submission
status: rejected
priority: medium
task_type: repo-hygiene
created_by: chatgpt
created_at: 2026-07-01T00:00:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/hygiene/2026-07-01-open-work-queue-audit.md
  - automation/review/agent-tasks/**/2026-07-01-open-work-queue-audit.agent-task.md
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
  - 10-inbox/**
  - automation/review/agent-tasks/inbox/**
  - automation/review/agent-tasks/ready/**
  - automation/review/agent-tasks/review/**
  - 00-dashboards/work-item-planning.md
  - 04-supportDesign/thesis-benchmark/index.md
outputs:
  - automation/review/routine-reports/central-codex-outstanding-work/2026-07-04-orchestration-run-report.md
result_path: automation/review/routine-reports/central-codex-outstanding-work/2026-07-04-orchestration-run-report.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: 10-inbox/2026-07-01-s2-lab-blackout-human-triage.md
linked_pr: ""
supersedes: []
superseded_by: 2026-07-04-central-codex-outstanding-work-orchestration
duplicates: []
notes: "Superseded by the central orchestration inventory and routing report; no separate queue-audit planning surface is needed."
---
# Task: Audit open work queue after conference submission

## Recommended model

Codex using `gpt-5.2-codex medium` or the nearest available default Codex coding/repo model.

## Objective

Inspect open work items and agent tasks, then produce a review-side audit of what should remain active after the final ICAC conference version has been submitted and the 2026-07-28 to 2026-08-28 lab blackout has been identified.

## Prompt

You are on `tyecam1/obsidian-PhD`. Do not change canonical notes. Inspect the work queue and write one audit report to:

`automation/review/hygiene/2026-07-01-open-work-queue-audit.md`

Include:

1. Open human work items in `10-inbox`, grouped as Human, Codex, Claude, Supervisor, Waiting if the file metadata/content supports it.
2. Agent tasks in `automation/review/agent-tasks/inbox`, `ready`, and `review`, grouped by executor.
3. Stale or duplicated tasks caused by the ICAC revision/submission interruption.
4. Which tasks should be paused until after 2026-08-28 because they require lab access.
5. Which tasks should be pulled into the 2026-07-28 to 2026-08-28 writing/specification window.
6. Exact file paths for any recommended status changes, but do not make those changes.

## Hard constraints

- Report only. Do not edit `10-inbox`, `00-dashboards`, `03-concept`, `04-supportDesign`, `01-research-plan`, or evidence/library files.
- Do not delete, move or close tasks.
- Do not infer completion unless file metadata clearly says `done`, `cancelled`, `paused`, `archived` or equivalent.
- Do not create new planning systems.

## Verification commands

Run if available:

```bash
git diff --check
python -m Scripts.automation agent-task-lint --require-pass
git status --short
```

If commands fail because dependencies or entrypoints are unavailable, record the failure honestly in the report.

## Acceptance criteria

The report should let Tye decide what to close, pause, or activate without manually reading the whole queue.

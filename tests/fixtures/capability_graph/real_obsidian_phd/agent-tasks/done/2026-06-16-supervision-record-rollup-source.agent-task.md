---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-16-supervision-record-rollup-source
title: Build supervision-record rollup source for Word export
status: done
priority: medium
task_type: aggregation
created_by: chatgpt
created_at: 2026-06-16T09:25:00+01:00
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
  - automation/review/supervision-rollups/2026-06-16-supervision-record-rollup-source.md
  - automation/review/supervision-rollups/2026-06-16-supervision-record-rollup-index.json
  - automation/review/agent-tasks/**/2026-06-16-supervision-record-rollup-source.agent-task.md
denied_paths:
  - 02-library/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 01-research-plan/**
  - 03-concept/**
  - 04-supportDesign/**
  - 07-standards/**
  - 00-dashboards/**
inputs:
  - 12-log/**/supervision*.md
  - 09-resources/supervision-record.md
outputs:
  - automation/review/supervision-rollups/2026-06-16-supervision-record-rollup-source.md
  - automation/review/supervision-rollups/2026-06-16-supervision-record-rollup-index.json
result_path: automation/review/supervision-rollups/2026-06-16-supervision-record-rollup-source.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Meeting note requested all supervisor meetings summarised into a Word document. This task creates the traceable Markdown source first; Word export can be performed after human review."
---
# Task: Build supervision-record rollup source for Word export

## Objective

Create a traceable Markdown source document summarising supervision meetings, suitable for later Word export.

The goal is administrative evidence and progress continuity, not another narrative research report.

## Required output

Create:

- `automation/review/supervision-rollups/2026-06-16-supervision-record-rollup-source.md`
- `automation/review/supervision-rollups/2026-06-16-supervision-record-rollup-index.json`

The Markdown source must include:

1. Chronological meeting table.
2. Progress since previous meeting.
3. Decisions made.
4. Problems/issues.
5. Actions continued.
6. New actions.
7. Open follow-ups.
8. Source-note links for each row.

The JSON index must list source files read and extraction status.

## Hard constraints

- Do not invent meeting outcomes.
- Do not summarise non-supervision daily notes unless clearly linked to supervision.
- Do not create the `.docx` until the Markdown source has been human-reviewed.
- Do not alter original meeting notes.

## Acceptance criteria

The rollup must be close enough to paste into the Strathclyde progress-record structure without manual reconstruction.

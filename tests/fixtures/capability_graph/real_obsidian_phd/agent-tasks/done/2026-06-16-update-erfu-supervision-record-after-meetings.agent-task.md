---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-16-update-erfu-supervision-record-after-meetings
title: Update Erfu supervision record after meetings
status: done
priority: high
task_type: recurring_update
created_by: chatgpt
created_at: 2026-06-16T18:05:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_local_filesystem: true
requires_office_export: true
requires_windows_scheduler: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
trigger:
  type: after-meeting
  indicators:
    - new or updated supervision meeting note
    - new or updated daily note mentioning Erfu, Richard, NMIS, CPI, supervisor, supervision, meeting, transcript, or action routing
    - new calendar-backed supervision/contact item
    - new completed meeting-prep work item
allowed_paths:
  - automation/review/supervisor-office-pack/**
  - automation/review/agent-tasks/**/2026-06-16-update-erfu-supervision-record-after-meetings.agent-task.md
denied_paths:
  - 00-dashboards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/**
  - 07-standards/**
inputs:
  - 12-log/**
  - 10-inbox/**
  - 09-resources/supervision-record.md
  - 00-dashboards/supervision-overview.md
  - Scripts/engine/calendar.csv
  - external:supervisionRecord20260616.xlsx
requirements:
  - automation/review/supervisor-office-pack/erfu-simple-supervision-record-final-format.md
external_outputs:
  - "C:\\Users\\tyeca\\OneDrive - University of Strathclyde\\Erfu Yang's files - Tye Cameron-Robson\\Tye Cameron-Robson - Erfu Supervision Record.xlsx"
outputs:
  - automation/review/supervisor-office-pack/erfu-supervision-record-update-2026-06-17.md
result_path: automation/review/supervisor-office-pack/erfu-supervision-record-update-2026-06-17.md
review_report_path: automation/review/supervisor-office-pack/erfu-supervision-record-update-2026-06-17.md
notes: "Codex created the stable external workbook on 2026-06-17 using the final simple three-sheet format. Awaiting V2 human verification."
---

# Task: update Erfu supervision record after every meeting

## Objective

After every supervision-relevant meeting or contact, update the Erfu-facing supervision record using the final simple workbook format.

The workbook must remain human supervisor-facing. It must not include vault-facing columns, file paths, evidence-level columns, agent notes, audit language or summary dashboards.

## Final workbook format

Use the exact format defined in:

`automation/review/supervisor-office-pack/erfu-simple-supervision-record-final-format.md`

Sheets:

1. `Supervision Record`
2. `Actions`
3. `Risks`

## When to run

Run after any of the following is created or updated:

- Erfu supervision meeting note;
- Richard/NMIS second-supervisor meeting or preparation/outcome note;
- CPI progress or stakeholder meeting relevant to the PhD direction;
- meeting transcript or daily note containing supervision outcomes;
- action-routing note after supervision;
- meeting-prep note that later feeds into a meeting outcome.

## Update procedure

1. Inspect the newest relevant notes in `12-log/**` and `10-inbox/**`.
2. Decide whether the new material is:
   - a substantive meeting;
   - contact/cadence evidence;
   - preparation only;
   - action-routing after a meeting.
3. Update `Supervision Record` with one simple row per meeting/contact episode.
4. Merge preparation notes into the meeting row they support.
5. Update `Actions` with any new, changed, completed or superseded actions.
6. Update `Risks` only for practical open points relevant to supervision or near-term project progress.
7. Keep wording short, factual and supervisor-facing.
8. Export the workbook to the stable Erfu OneDrive folder.
9. Commit any changed vault task/spec notes only if the process or requirement changes.

## Wording constraints

Use wording like:

- `Supervision meeting`
- `Supervision contact`
- `CPI progress meeting`
- `No detailed outcome note is available`
- `Useful as continuity context`
- `Do not count as a completed meeting unless confirmed separately`

Avoid wording like:

- `vault evidence`
- `candidate`
- `source traceability`
- `register treatment`
- `audit finding`
- `artifact_type`
- `drm_stage`
- file paths or repository paths inside the workbook.

## Verification

Before finishing:

1. confirm workbook sheets are exactly `Supervision Record`, `Actions`, and `Risks`;
2. confirm `Supervision Record` columns are exactly:
   - `Date / period`
   - `Record`
   - `People`
   - `Purpose / context`
   - `Discussion focus`
   - `Outcome / follow-up`
3. confirm `Actions` columns are exactly:
   - `Date / period`
   - `Action`
   - `Status`
   - `Timing / next step`
   - `Purpose`
4. confirm `Risks` columns are exactly:
   - `Open point`
   - `Level`
   - `Current handling`
5. scan for formula errors;
6. open or render the first sheet enough to check readability;
7. report what row(s) changed.

## Human check required

Do not invent meeting outcomes. If a meeting appears to have happened but only calendar/prep evidence exists, add a conservative contact row or mark it for human confirmation using simple wording.

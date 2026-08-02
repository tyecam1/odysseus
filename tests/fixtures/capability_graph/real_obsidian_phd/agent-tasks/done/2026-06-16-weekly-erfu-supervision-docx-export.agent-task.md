---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-16-weekly-erfu-supervision-summary-and-register-export
title: Implement weekly Erfu one-page supervision summary and register export
status: done
priority: high
task_type: implementation
created_by: chatgpt
created_at: 2026-06-16T14:35:00+01:00
updated_at: 2026-06-16T16:10:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_local_filesystem: true
requires_windows_scheduler: true
requires_office_export: true
requires_xlsx_export: true
requires_docx_export: true
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
  - automation/review/supervisor-office-pack/**
  - automation/review/operator-decisions/**
  - automation/review/agent-tasks/**/2026-06-16-weekly-erfu-supervision-docx-export.agent-task.md
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
  - 11-projects/**/thesis/**
inputs:
  - 12-log/**/supervision*.md
  - 12-log/**/supervisor-meeting*.md
  - 12-log/**/supervision*-action-routing.md
  - 12-log/**/supervisor-meeting-cpi*.md
  - 09-resources/supervision-record.md
  - automation/review/supervisor-office-pack/erfu-office-pack-temporal-history-requirements.md
outputs:
  - automation/review/supervisor-office-pack/latest-erfu-supervision-register.source.json
  - automation/review/supervisor-office-pack/latest-erfu-one-page-summary.source.md
  - automation/review/supervisor-office-pack/latest-erfu-supervision-register.update-log.md
  - automation/review/supervisor-office-pack/export-logs/2026-06-16T162609Z0000.supervision-register-export.json
  - automation/review/operator-decisions/2026-06-16-erfu-supervision-summary-register-local-install.decision-card.md
  - Scripts/automation/supervision_register_export.py
  - Scripts/automation/tests/test_supervision_register_export.py
external_output_directory: "C:\\Users\\tyeca\\OneDrive - University of Strathclyde\\Erfu Yang's files - Tye Cameron-Robson"
external_outputs:
  required:
    - "Tye Cameron-Robson - One Page Supervision Summary.docx"
    - "Tye Cameron-Robson - Supervision Meeting Register.xlsx"
result_path: automation/review/supervisor-office-pack/latest-erfu-one-page-summary.source.md
review_report_path: automation/review/operator-decisions/2026-06-16-erfu-supervision-summary-register-local-install.decision-card.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: automation/review/operator-decisions/2026-06-16-erfu-supervision-summary-register-local-install.decision-card.md
linked_pr: ""
supersedes:
  - 2026-06-16-supervision-record-rollup-source
  - 2026-06-16-weekly-erfu-supervision-docx-export
  - 2026-06-16-weekly-erfu-supervisor-office-pack-export
  - 2026-06-16-weekly-erfu-supervision-register-xlsx-export
duplicates: []
notes: "Implemented by Codex on 2026-06-16 after rebase retargeted the task to one one-page DOCX summary plus an Excel supervision meeting register. Both live files were written to the configured OneDrive directory; weekly schedule remains a human-approved local install action."
---

# Task: Implement weekly Erfu one-page supervision summary and register export

## Completion Summary

Implemented a deterministic local exporter at `Scripts/automation/supervision_register_export.py`.

The exporter scans supervision-related `12-log/**` notes, creates one row per meeting/prep/routing source, extracts bounded action and risk rows, writes review-side source/update artifacts, exports the stable Excel register, and generates the one-page DOCX summary from the same parsed register data.

## Generated Outputs

- `automation/review/supervisor-office-pack/latest-erfu-supervision-register.source.json`
- `automation/review/supervisor-office-pack/latest-erfu-one-page-summary.source.md`
- `automation/review/supervisor-office-pack/latest-erfu-supervision-register.update-log.md`
- `automation/review/supervisor-office-pack/export-logs/2026-06-16T162609Z0000.supervision-register-export.json`
- `automation/review/operator-decisions/2026-06-16-erfu-supervision-summary-register-local-install.decision-card.md`
- External summary DOCX: `C:\Users\tyeca\OneDrive - University of Strathclyde\Erfu Yang's files - Tye Cameron-Robson\Tye Cameron-Robson - One Page Supervision Summary.docx`
- External workbook: `C:\Users\tyeca\OneDrive - University of Strathclyde\Erfu Yang's files - Tye Cameron-Robson\Tye Cameron-Robson - Supervision Meeting Register.xlsx`

## Verification

- Workbook write succeeded.
- Workbook contains the required sheets: `Dashboard`, `Meetings Register`, `Actions`, `Risks`, `Agent Update Spec`, and `Lists`.
- Readback validation found no missing source paths and no formula-error cells.
- DOCX write succeeded and structural readback found a title and non-empty paragraph set.
- Latest export generated 29 meeting rows, 115 action rows, and 60 risk rows.

## Remaining Human Action

Install or approve the weekly Windows scheduled task using the operator decision card. No schedule was installed automatically.

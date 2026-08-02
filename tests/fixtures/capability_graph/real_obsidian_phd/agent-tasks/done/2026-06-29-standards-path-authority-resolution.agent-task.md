---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-29-standards-path-authority-resolution
title: Resolve standards path authority drift
status: done
priority: high
task_type: migration
created_by: codex-roadmap-router
created_at: 2026-06-29T18:30:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/routine-reports/repo-roadmap/2026-06-29-standards-path-authority-resolution.md
  - automation/review/routine-reports/repo-roadmap/2026-06-29-standards-path-authority-resolution.json
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 06-datasets/07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - README.md
  - CLAUDE.md
  - 00-dashboards/artifact-types.md
  - 00-dashboards/rc-control.md
  - 00-dashboards/graph-filters.md
  - automation/docs/path-authority.md
  - automation/docs/current-capabilities.md
  - automation/config/vault_profile.json
  - automation/config/vault_profile.snapshot.json
  - automation/config/settings.ini
  - 06-datasets/07-standards/**
outputs:
  - automation/review/routine-reports/repo-roadmap/2026-06-29-standards-path-authority-resolution.md
  - automation/review/routine-reports/repo-roadmap/2026-06-29-standards-path-authority-resolution.json
result_path: automation/review/routine-reports/repo-roadmap/2026-06-29-standards-path-authority-resolution.md
review_report_path: automation/review/routine-reports/repo-roadmap/2026-06-29-standards-path-authority-resolution.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Decision-ready migration audit for the standards path mismatch. Produce a report and machine-readable drift inventory only; do not move standards notes or edit canonical dashboards/docs in this task."
---

# Task: Resolve standards path authority drift

## Objective

Determine whether standards should canonically live at `07-standards/**` or remain at `06-datasets/07-standards/**`, then produce a decision-ready migration/audit packet.

## Required output

Write:

- `automation/review/routine-reports/repo-roadmap/2026-06-29-standards-path-authority-resolution.md`
- `automation/review/routine-reports/repo-roadmap/2026-06-29-standards-path-authority-resolution.json`

The JSON must include every drifted reference family: docs, dashboards, settings, vault profile, graph filters, retrieval roots, tests, and task templates.

## Acceptance criteria

- The report states one recommended canonical path and one rejected alternative.
- The JSON includes source path, line or match context, current value, proposed value, and risk class.
- The plan preserves read-only treatment of standards until a human approves the path-authority change.
- No standards notes, ontology notes, dashboards, or canonical research files are changed.

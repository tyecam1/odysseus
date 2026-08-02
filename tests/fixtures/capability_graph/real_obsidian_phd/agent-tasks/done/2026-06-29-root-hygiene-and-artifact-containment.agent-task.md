---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-29-root-hygiene-and-artifact-containment
title: Contain root-level recovery and hygiene artifacts
status: done
priority: medium
task_type: repo-hygiene
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
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/routine-reports/repo-roadmap/2026-06-29-root-hygiene-and-artifact-containment.md
  - automation/review/routine-reports/repo-roadmap/2026-06-29-root-hygiene-and-artifact-containment.json
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
  - AGENTS.md
  - GIT-HYGIENE.md
  - .gitignore
  - codex_changed_files.txt
  - codex_recovery_full.patch
  - cpi_batch_a_patch_v2.ps1
  - how --stat 0a2c718f
outputs:
  - automation/review/routine-reports/repo-roadmap/2026-06-29-root-hygiene-and-artifact-containment.md
  - automation/review/routine-reports/repo-roadmap/2026-06-29-root-hygiene-and-artifact-containment.json
result_path: automation/review/routine-reports/repo-roadmap/2026-06-29-root-hygiene-and-artifact-containment.md
review_report_path: automation/review/routine-reports/repo-roadmap/2026-06-29-root-hygiene-and-artifact-containment.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Inventory root-level recovery artifacts and propose safe containment. Do not delete or move files in this task."
---

# Task: Contain root-level recovery and hygiene artifacts

## Objective

Separate legitimate root entry points from recovery, patch, or accidental command-output files so the repo root remains a reliable operator surface.

## Required output

Write:

- `automation/review/routine-reports/repo-roadmap/2026-06-29-root-hygiene-and-artifact-containment.md`
- `automation/review/routine-reports/repo-roadmap/2026-06-29-root-hygiene-and-artifact-containment.json`

## Required content

- Classify each nonstandard root file as keep, archive, move-to-review, ignore, or delete-candidate.
- Identify whether each file is tracked, referenced, or safe to quarantine.
- Propose `.gitignore` additions only for future generated artifacts, not for hiding tracked debt.
- Provide a safe patch plan with no destructive commands.

## Acceptance criteria

- The JSON includes file name, size, tracked status, classification, rationale, and proposed target if any.
- The report keeps `README.md`, `AGENTS.md`, `CLAUDE.md`, `GIT-HYGIENE.md`, `.env.example`, and config files as explicit root entry points.
- No files are moved or deleted.

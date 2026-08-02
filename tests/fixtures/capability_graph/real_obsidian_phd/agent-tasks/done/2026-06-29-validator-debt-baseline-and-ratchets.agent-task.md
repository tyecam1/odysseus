---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-29-validator-debt-baseline-and-ratchets
title: Create validator debt baseline and ratchets
status: done
priority: high
task_type: validation
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
  - automation/review/routine-reports/repo-roadmap/2026-06-29-validator-debt-baseline-and-ratchets.md
  - automation/review/routine-reports/repo-roadmap/2026-06-29-validator-debt-baseline-and-ratchets.json
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
  - Scripts/automation/validator.py
  - Scripts/automation/agent_task_lint.py
  - .github/workflows/ci-gate.yml
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
  - automation/review/**
outputs:
  - automation/review/routine-reports/repo-roadmap/2026-06-29-validator-debt-baseline-and-ratchets.md
  - automation/review/routine-reports/repo-roadmap/2026-06-29-validator-debt-baseline-and-ratchets.json
result_path: automation/review/routine-reports/repo-roadmap/2026-06-29-validator-debt-baseline-and-ratchets.md
review_report_path: automation/review/routine-reports/repo-roadmap/2026-06-29-validator-debt-baseline-and-ratchets.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Build a durable validator-debt baseline and propose ratchets by finding code/path family. Do not repair canonical notes in this task."
---

# Task: Create validator debt baseline and ratchets

## Objective

Turn the current validator backlog into a managed debt surface that can shrink over time without requiring historic cleanup before every PR.

## Required output

Write:

- `automation/review/routine-reports/repo-roadmap/2026-06-29-validator-debt-baseline-and-ratchets.md`
- `automation/review/routine-reports/repo-roadmap/2026-06-29-validator-debt-baseline-and-ratchets.json`

## Required analysis

- Run `python -m Scripts.automation validate`.
- Group findings by `code`, `level`, top-level path, and canonical/review/superseded state.
- Identify the top five error classes and the smallest useful ratchet for each.
- Separate real research-vault defects from tolerated generated-review residue.

## Acceptance criteria

- JSON includes counts, sample paths, proposed ratchet rule, and expected false-positive risk per error class.
- The report recommends at most three immediate ratchets.
- The report explicitly avoids an absolute fail-on-all-errors gate while historic debt remains high.
- No validator code or canonical notes are edited.

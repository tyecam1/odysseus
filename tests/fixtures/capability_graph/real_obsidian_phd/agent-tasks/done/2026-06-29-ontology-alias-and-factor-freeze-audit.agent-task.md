---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-29-ontology-alias-and-factor-freeze-audit
title: Audit ontology aliases and factor reactivation risk
status: done
priority: medium
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
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/routine-reports/repo-roadmap/2026-06-29-ontology-alias-and-factor-freeze-audit.md
  - automation/review/routine-reports/repo-roadmap/2026-06-29-ontology-alias-and-factor-freeze-audit.json
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
  - 00-dashboards/artifact-types.md
  - automation/config/vault_profile.json
  - automation/config/vault_profile.snapshot.json
  - automation/docs/path-authority.md
  - automation/docs/current-capabilities.md
  - 08-template/**
  - Scripts/**
  - automation/**
outputs:
  - automation/review/routine-reports/repo-roadmap/2026-06-29-ontology-alias-and-factor-freeze-audit.md
  - automation/review/routine-reports/repo-roadmap/2026-06-29-ontology-alias-and-factor-freeze-audit.json
result_path: automation/review/routine-reports/repo-roadmap/2026-06-29-ontology-alias-and-factor-freeze-audit.md
review_report_path: automation/review/routine-reports/repo-roadmap/2026-06-29-ontology-alias-and-factor-freeze-audit.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Audit and prevention plan for old path aliases, old artifact tokens, and factor reactivation risk. Output review-side inventory only."
---

# Task: Audit ontology aliases and factor reactivation risk

## Objective

Find where current tooling, templates, or generated review artifacts still emit legacy ontology aliases or `factor` as if it were active.

## Required output

Write:

- `automation/review/routine-reports/repo-roadmap/2026-06-29-ontology-alias-and-factor-freeze-audit.md`
- `automation/review/routine-reports/repo-roadmap/2026-06-29-ontology-alias-and-factor-freeze-audit.json`

## Required checks

- Search for old paths: `ref-nodes`, `ref-links`, `impact-nodes`, `impact-links`, `success-criteria`, and `03-concept/kpi`.
- Search for active emissions of `artifact_type: factor`, `ref-node`, `ref-link`, and `imp-node`.
- Separate historical/superseded references from live templates or automation emitters.
- Propose lint or schema checks that prevent new drift without rewriting old notes.

## Acceptance criteria

- JSON groups findings by `historical`, `live-emitter`, `template`, `test-fixture`, and `review-output`.
- The report recommends a minimal prevention patch.
- No ontology notes or templates are edited in this task.

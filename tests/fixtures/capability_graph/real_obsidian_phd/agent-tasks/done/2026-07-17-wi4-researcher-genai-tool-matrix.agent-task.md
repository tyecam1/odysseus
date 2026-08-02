---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-17-wi4-researcher-genai-tool-matrix
title: Stage researcher AI tool evaluation matrix
status: done
priority: medium
task_type: critique
created_by: fable-route-loop
created_at: 2026-07-17T00:00:00+00:00
executor: codex_subscription
execution_mode: central-orchestrator
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
branch: agent/genai-workshop-ingest
allowed_paths:
  - automation/review/platform-evaluations/2026-07-17-researcher-genai-tool-matrix.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/sources/workshop-genai-researcher-2026/extraction/items.json
  - automation/review/sources/workshop-genai-researcher-2026/delta-audit.md
  - automation/docs/current-capabilities.md
  - automation/docs/agent-boundaries.md
  - automation/docs/sensitive-input-policy.md
outputs:
  - automation/review/platform-evaluations/2026-07-17-researcher-genai-tool-matrix.md
result_path: automation/review/platform-evaluations/2026-07-17-researcher-genai-tool-matrix.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Source slides S22-1, S27-2, S28-5, and S44-1. All adoption decisions remain pending-operator."
---

# Stage researcher AI tool evaluation matrix

## Problem

The delta audit found no researcher-tool evaluation despite substantial overlap with implemented search, retrieval, extraction, and RAG paths and a conflict between PDF-upload tools and sensitive-input policy.

## Scope

Compare seven candidate tool families with measured engine gaps, duplication, privacy/copyright cost, export, provenance, and one bounded evaluation protocol each.

## Exclusions

- No adoption recommendation, subscription, external upload, configuration change, or tool trial.
- No vendor claim is treated as verified evidence.

## Acceptance criteria

- Every required candidate and comparison column is present.
- Every row has a bounded task, success measure, and `pending-operator` decision.
- The artifact remains extraction-support material and human-reviewed.

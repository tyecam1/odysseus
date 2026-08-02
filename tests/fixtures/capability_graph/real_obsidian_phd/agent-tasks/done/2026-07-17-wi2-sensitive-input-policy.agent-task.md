---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-17-wi2-sensitive-input-policy
title: Define sensitive-input policy
status: done
priority: high
task_type: repo-governance-audit
created_by: fable-route-loop
created_at: 2026-07-17T00:00:00+00:00
executor: codex_subscription
execution_mode: central-orchestrator
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: agent/genai-workshop-ingest
allowed_paths:
  - automation/docs/sensitive-input-policy.md
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
  - automation/docs/agent-boundaries.md
outputs:
  - automation/docs/sensitive-input-policy.md
result_path: automation/docs/sensitive-input-policy.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Source slides S15-1, S16-6, S17-4, and S14-3. Policy documents operator discipline and existing controls only."
---

# Define sensitive-input policy

## Problem

The delta audit found structural guardrails but no single artifact stating what must never leave the machine or how the workshop-source sensitivity classification governs external-service use.

## Scope

Define prohibited input categories, current structural controls, operator classification responsibility, source-manifest sensitivity use, and dummy-data practice.

## Exclusions

- No automated content classifier or speculative enforcement.
- No integration, hook, validator, Zotero, canonical, or external-service change.

## Acceptance criteria

- Participant, partner-confidential, copyrighted full-text, and secret material are prohibited explicitly.
- Existing enforcement and its content-classification limitation are stated accurately.
- Human review confirms the policy boundary.

---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-17-wi1-ai-use-disclosure-contract
title: Define per-output AI-use disclosure
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
  - automation/docs/ai-use-disclosure.md
  - automation/review/ai-use/register.md
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
outputs:
  - automation/docs/ai-use-disclosure.md
  - automation/review/ai-use/register.md
result_path: automation/docs/ai-use-disclosure.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Source slides S17-3, S12-2, S16-4, S14-1..6, and S35-1..3. Review-side disclosure only; no evidence or publication action."
---

# Define per-output AI-use disclosure

## Problem

The delta audit found strong internal provenance but no publication-facing per-output record of tools, models, periods, purposes, supplied-input categories, retained outputs, researcher intervention, or verification.

## Scope

Define the disclosure contract and seed J1 and ICAC2026 entries using repository-supported facts only. Preserve the existing verification-route vocabulary and treat AIR bands as optional parallel disclosure metadata.

## Exclusions

- No invented model versions, dates, venue policies, or manuscript interventions.
- No trust-tier change, evidence promotion, canonical write, or submission.

## Acceptance criteria

- Required fields and policy anchors are explicit.
- Unknown facts are marked `TODO(operator)`.
- The register states that disclosure never upgrades evidence authority.
- Human review confirms institutional and venue-facing wording.

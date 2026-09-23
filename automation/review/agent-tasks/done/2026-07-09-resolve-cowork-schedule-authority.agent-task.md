---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-09-resolve-cowork-schedule-authority
title: "Resolve cowork schedule authority"
status: done
completed_at: 2026-07-23T00:00:00+01:00
verification_verdict: PASS
priority: medium
task_type: diagnostics
created_by: human
created_at: 2026-07-09T17:55:00+01:00

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
  - automation/review/ops/**
  - automation/review/decision-packets/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
  - 10-inbox/**
  - 11-projects/**
  - My Library.bib
  - 02-library/My Library.bib

inputs:
  - automation/review/routine-reports/odysseus-schedule-attestation/2026-07-09.odysseus-schedule-attestation.md
  - automation/review/routine-reports/odysseus-schedule-attestation/2026-07-09.odysseus-schedule-attestation.json
  - automation/review/ops/odysseus-live-maintenance-2026-07-09.md
  - automation/review/ops/automation-local-remote-ownership-policy-2026-07-09.md
outputs:
  - automation/review/ops/2026-07-09-cowork-schedule-authority-diagnostics.md
result_path: automation/review/ops/2026-07-09-cowork-schedule-authority-diagnostics.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""

operator_decision_path: automation/review/decision-packets/2026-07-09-automation-ownership-follow-up.decision-packet.md
linked_pr: ""
supersedes: []
duplicates: []

notes: "Diagnostics only. The schedule source must be identified before any schedule parity or scheduler expansion claims are made."
---

# Resolve cowork schedule authority

## Context

The 2026-07-09 Odysseus schedule attestation reported `cowork-schedule-source-unavailable`. Schedule parity therefore remains unverified even though Odysseus liveness passed with warnings.

## Objective

Identify the intended cowork schedule authority, document why it was unavailable, and decide whether schedule parity is operationally required.

## Required analysis

1. Identify every referenced cowork schedule source in review artifacts, scripts, config, or docs.
2. Classify each source as available, missing, deprecated, secret-protected, external-only, or unknown.
3. Determine whether cowork schedule parity is required for current Odysseus automation safety.
4. Define the minimal restoration path if it is required.
5. Define the documentation/deprecation path if it is not required.
6. Do not infer parity from stale or unavailable sources.

## Output

Write one diagnostics report only:

`automation/review/ops/2026-07-09-cowork-schedule-authority-diagnostics.md`

## Acceptance criteria

- The report identifies the schedule authority status without exposing secrets.
- The report recommends either restore, document-as-unavailable, or deprecate.
- The report includes validation commands for a future live-maintenance agent.
- No live scheduler state is changed.
- No new schedule loop is created.

## Stop condition

Stop and mark blocked if resolving the authority requires credentials, private schedule contents, or external systems unavailable to the agent.

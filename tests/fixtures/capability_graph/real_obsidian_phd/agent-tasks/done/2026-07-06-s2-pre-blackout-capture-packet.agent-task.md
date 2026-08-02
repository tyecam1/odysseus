---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-06-s2-pre-blackout-capture-packet
title: "S2 pre-blackout capture packet"
status: done
priority: high
task_type: research-support-packet
created_by: chatgpt
created_at: 2026-07-06T13:45:00+01:00
executor: codex_subscription
execution_mode: implementation
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
branch: codex/s2-pre-blackout-capture-20260706
allowed_paths:
  - automation/review/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
  - 04-supportDesign/**
  - 10-inbox/**
  - 11-projects/**
  - 12-log/**
  - "**/*.pdf"
inputs:
  - automation/review/s2-benchmark-design/2026-07-04-s2-constrained-access-point-cell-benchmark-scaffold.md
  - automation/review/decision-packets/2026-07-03-blackout-work-plan-draft.decision-packet.md
  - 10-inbox/backlog.md
  - 10-inbox/complete/prepare-richard-nmis-benchmark-review-package.md
  - 10-inbox/complete/2026-07-01-s2-lab-blackout-human-triage.md
outputs:
  - automation/review/s2-benchmark-design/2026-07-06-s2-pre-blackout-capture-packet.md
result_path: automation/review/s2-benchmark-design/2026-07-06-s2-pre-blackout-capture-packet.md
review_report_path: automation/review/s2-benchmark-design/2026-07-06-s2-pre-blackout-capture-packet.md
handoff_model: codex_work_package
operator_decision_path: automation/review/s2-benchmark-design/2026-07-06-s2-pre-blackout-capture-packet.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Review-side lab-capture packet. Does not create canonical benchmark protocol."
---
# S2 pre-blackout capture packet

## Goal

Create a practical pre-blackout lab-capture packet for the July window.

## Required packet sections

- Apparatus inventory.
- Photos required.
- Rough measurements required.
- D435F placement observations required.
- Calibration and ground-truth options to inspect.
- Robot-log access checks.
- Small-token/object-class availability.
- Occlusion/visibility observations.
- Second-camera feasibility check.
- Blackout-suitable writing/specification work.
- Named blockers if not captured.

## Acceptance criteria

- The packet is usable in one lab visit.
- It does not assume numeric thresholds.
- It does not promote live-human safety-distance testing.

---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-07-01-s2-perception-supervision-synthesis
title: Consolidate perception-packet open questions into supervision asks
status: rejected
rejection_reason: superseded
priority: medium
task_type: synthesis
created_by: claude-system-review
created_at: 2026-07-01T13:10:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
allowed_paths:
  - automation/review/s2-benchmark-design/perception-first-evidence-2026-07-01/**
  - automation/review/agent-tasks/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/s2-benchmark-design/perception-first-evidence-2026-07-01/index.md
  - 10-inbox/2026-07-01-communicate-with-dino-s2-buildability.md
  - 10-inbox/prepare-richard-nmis-benchmark-review-package.md
  - 12-log/26-06/26-26/supervision-erfu-2026-06-22.md
outputs:
  - automation/review/s2-benchmark-design/perception-first-evidence-2026-07-01/supervision-asks.md
notes: "Superseded 2026-07-23 by the S2 CAD completion record, paused physical-metrology work item, and explicit Year 2 supervision/resource clarification checklist. A further parallel ask sheet would add drift."
---

# Task: Consolidate perception-packet open questions into supervision asks

## Objective

The six perception packets each end with §6 open questions for supervision. Consolidate these into one review-side ask sheet grouped by recipient (Erfu / Richard-NMIS / Dino), de-duplicated and aligned with the existing 2026-07-01 Dino/Richard work items. Do not invent new questions; each ask must trace to a packet.

## Why

Without consolidation the packets' questions do not reach the meeting; a single grouped sheet makes the perception evidence actionable in supervision without re-reading six packets.

## Acceptance criteria

One `supervision-asks.md` grouping questions by recipient, each traceable to a source packet §6; overlaps with the existing Dino/Richard work items are referenced, not duplicated; no canonical or evidence writes.

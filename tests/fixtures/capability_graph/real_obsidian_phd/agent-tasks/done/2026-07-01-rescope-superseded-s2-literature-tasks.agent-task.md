---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-07-01-rescope-superseded-s2-literature-tasks
title: Re-scope superseded S2 literature tasks after perception-first pivot
status: done
priority: medium
task_type: human-approval
created_by: claude-system-review
created_at: 2026-07-01T13:05:00+01:00
executor: human
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
  - 04-supportDesign/thesis-benchmark/s2-perception-first-benchmark-rationale.md
  - automation/review/s2-benchmark-design/perception-first-evidence-2026-07-01/index.md
outputs:
  - automation/review/operator-decisions/2026-07-02-s2-literature-rescope-adjudication.md
result_path: automation/review/operator-decisions/2026-07-02-s2-literature-rescope-adjudication.md
---

# Task: Re-scope superseded S2 literature tasks after perception-first pivot

## Objective

The perception-localisation-first pivot supersedes the earlier 2026-06-17 dynamic-obstacle-first framing. Decide keep-and-rescope / defer / reject for each affected inbox task, and move rejected ones to `rejected/`.

## Tasks to adjudicate

- `2026-06-17-s2-e1-dynamic-obstacle-planning-literature` — downstream (C2/S4); defer until the perception chain is characterised.
- `2026-06-17-s2-e1-minimum-safety-distance-standards` — partly folded into the perception metrics/uncertainty packet; decide keep-as-standards-anchor vs merge.
- `2026-06-17-s2-e1-useful-support-action-grounding` — still open; not covered by the perception packets (S2.3 support action). Likely keep.
- `2026-06-17-s3-event-linked-safety-human-factor` — S3 stage; defer.
- `2026-06-17-s4-safety-response-policy-options` — S4 stage; defer.
- `2026-06-15-socially-conscious-robotics-perspective-source-scout` (ready/) — writing-support, independent of the pivot; decide keep vs deprioritise.

## Why

Keeps the queue truthful and prevents a stale dynamic-obstacle-first framing from being executed against the current perception-first plan.

## Acceptance criteria

Each of the 6 tasks marked keep (with a one-line re-scope note), defer, or rejected (moved to `rejected/` with reason). No literature is retrieved as part of this decision.

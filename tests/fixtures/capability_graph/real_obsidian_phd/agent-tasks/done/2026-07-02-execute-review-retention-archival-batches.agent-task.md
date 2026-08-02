---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-07-02-execute-review-retention-archival-batches
title: Execute review-retention archival for annotation-rollup-backfill and aged families
status: done
priority: high
task_type: migration
created_by: claude-orchestrator
created_at: 2026-07-02T14:30:00+01:00
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
linked_pr: https://github.com/tyecam1/obsidian-PhD/pull/398
allowed_paths:
  - automation/review/superseded/**
  - automation/review/annotation-rollup-backfill/**
  - automation/review/queues/**
  - automation/review/quarantine/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - GitHub issues tyecam1/obsidian-PhD#371 and #373
  - automation/review/queues/research-engine-health.md
outputs:
  - automation/review/superseded/ (dated family subfolders + move manifests)
---

# Task: Execute review-retention archival for annotation-rollup-backfill and aged families

## Objective
Implement issues #371 and #373: `git mv` `annotation-rollup-backfill/*` and pre-2026-05 inactive families into `automation/review/superseded/<family>/<date>/`, one move manifest per family. Preserve open tasks, decision packets, promotion audits, and trust-ledger chains in place. Rename duplicate READMEs (e.g. "README 2.md") to descriptive names as part of the same moves.

## Approach
Build a preserve-list first from open tasks, decision records, and ledger chains referencing each family before any move. One PR per family, each with its own move manifest documenting source, destination, and preserve-list exclusions. Do not touch canonical/read-only paths — this is review-side retention only.

## Acceptance criteria
- Review artifact count drops below 1,200.
- agent-task-lint and validator ratchet both pass.
- Manifests are complete (source, destination, rationale, preserve exclusions per family).
- Zero broken links introduced (verify via existing link-check tooling).

## Stop condition
Any file matched by an open task, decision record, or ledger chain stays in place. If the preserve-list is ambiguous for a given file, fail closed: leave the file unmoved and record the ambiguity explicitly in that family's manifest.

## Risk if done badly
Archiving a live ledger chain breaks evidence provenance irrecoverably. The preserve-list check is the mandatory gate before any `git mv` — do not batch-move without it.

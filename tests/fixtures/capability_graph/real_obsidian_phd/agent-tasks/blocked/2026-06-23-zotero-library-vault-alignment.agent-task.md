---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-23-zotero-library-vault-alignment
title: Align Zotero collections/filesystem with the vault structure
status: blocked
priority: low
task_type: data-organisation
created_by: claude
created_at: 2026-06-23T00:00:00+01:00
updated_at: 2026-06-23T00:00:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: true
requires_zotero_write: true
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
blocker: >-
  The Beaver/Zotero MCP exposes only read tools plus create_note. It has no
  tool to create, rename, move, or delete collections or to relocate items, so
  reorganising the library through the MCP is not currently possible. Blocked
  pending a Zotero-write capability (Zotero API write integration or a future
  MCP tool). Until then, only a non-mutating proposed mapping can be produced.
allowed_paths:
  - automation/review/zotero-alignment/2026-06-23-zotero-library-vault-alignment-plan.md
  - automation/review/agent-tasks/**/2026-06-23-zotero-library-vault-alignment.agent-task.md
denied_paths:
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 02-library/**
  - 03-concept/**
  - 04-supportDesign/**
  - 07-standards/**
  - 00-dashboards/**
inputs:
  - 00-dashboards/artifact-types.md
  - 02-library/00-papers/
outputs:
  - automation/review/zotero-alignment/2026-06-23-zotero-library-vault-alignment-plan.md
---
# Task: Align Zotero collections/filesystem with the vault structure

## Status: BLOCKED

See `blocker` in frontmatter. No Zotero-mutating tool is currently available; do not attempt to reorganise the live library.

## Objective (when unblocked)

Reorganise Zotero collections and stored files so they mirror the vault's structure (substudy / cluster / artifact ontology), making retrieval and citation alignment low-overhead.

## Allowed now (non-mutating)

Produce a **proposed mapping only**, written review-side:

1. Read the current collections (`list_collections`) and tags (`list_tags`).
2. Propose a target collection tree mirroring substudy + cluster + ontology (`artifact-types.md`).
3. Map each existing collection/item group to its target, flagging duplicates, orphans, and items needed by `s2-perception-first-benchmark-rationale.md`.
4. List the exact mutating operations a future write-capable run (or the human) would perform.

## Hard constraints

- Do not mutate Zotero (no moves, renames, deletes); `create_note` is not to be used for reorganisation.
- Keep all output review-side under `allowed_paths`.
- Treat the mapping as provisional until human approval.

## Acceptance criteria (for the non-mutating step)

- A proposed-mapping plan exists at the allowed path.
- Every proposed move is traceable to a vault structure rule.
- The blocker and required capability are restated at the top of the plan.

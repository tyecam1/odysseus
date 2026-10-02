---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-02-chatgpt-export-ingestion-via-memory-sources
title: "Incremental ChatGPT export ingestion through the existing memory-sources import path"
status: inbox
priority: low
task_type: implementation
created_by: claude
created_at: 2026-10-02T18:00:00+01:00
updated_at: 2026-10-02T18:00:00+01:00
executor: ""
execution_mode: review-first
architecture: single
architecture_rationale: "Extends the existing import-source declaration (config/memory-sources.yaml) and the existing memory surface. No new store or broker."
single_agent_baseline: "One implementation owner extending the existing owner named in the task."
execution_host: compute-box
context_budget: medium
coordination_reason: "Split out of 2026-08-19-aoteru-central-memory-and-universal-assistant when the Phase 4 ADR was ratified (Misumi PR #46), so that the genuinely deferred part is not lost with the retired broker and Mem0 work."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - docs/**
  - tests/**
  - src/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
inputs:
  - automation/review/agent-tasks/rejected/2026-08-19-aoteru-central-memory-and-universal-assistant.agent-task.md
  - tyecam1/misumi:docs/memory-architecture.md
  - tyecam1/misumi:docs/memory-policy.md
outputs:
  - an owner privacy decision recorded, then an incremental, provenance-bearing import path that writes candidates through the existing memory surface
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Deferred tranche item 7. Blocked on an owner privacy decision. Official ChatGPT data-export files only; no scraping."
---
# ChatGPT export ingestion via `config/memory-sources.yaml`

## Why

The retired central-memory task wanted ChatGPT history incrementally imported with provenance. The ratified ADR does not forbid
it; it forbids a *new store or broker* to do it. The declared place for import sources is `config/memory-sources.yaml`.

## Blocking decision (human, before any code)

The owner decides, in writing: whether ChatGPT history may be imported at all; which parts (for example household topics only,
never PhD material); how long raw export files are kept (the default is not at all after import); and who may view or delete the
imported memory. Without that decision this task stays in the inbox.

## Constraints

- Official export files only; no scraping, no credentials in the repository.
- Imported material is **runtime-memory candidates** with provenance (source file, conversation id, timestamp), never canon, and
  never written into either knowledgebase automatically (see `docs/memory-policy.md`: a candidate that implies a canon change is
  a proposal only).
- Idempotent: re-importing the same export creates no duplicates.
- Every imported item must be viewable, deletable and exportable by source (so a whole import can be withdrawn).
- Secrets and credentials are excluded before storage; household and PhD domains stay separate.
- Local inference by default for extraction; any paid escalation is recorded.

## Required work

1. Record the owner decision above.
2. Declare the source in `config/memory-sources.yaml`; implement incremental, idempotent import through the existing surface.
3. Tests with fixtures (no live account): idempotency, domain separation, secret exclusion, deletion of a whole import.

## Acceptance

- Re-running the import adds nothing; withdrawing an import removes all of its candidates.
- No new store, broker or MCP memory authority exists after the change.

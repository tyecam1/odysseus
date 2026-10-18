---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-02-bounded-read-only-session-start-retrieval
title: "Bounded, read-only memory retrieval at coding-session start (no capture, no new store)"
status: inbox
priority: low
task_type: implementation
created_by: claude
created_at: 2026-10-02T18:00:00+01:00
updated_at: 2026-10-02T18:00:00+01:00
executor: ""
execution_mode: review-first
architecture: single
architecture_rationale: "Extends the one existing retrieval surface (memory_provider and mcp_servers/memory_server.py). No broker, no new store, no write path."
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
  - a design note and, only if approved, a read-only bounded retrieval step at session start that calls the existing memory surface
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Deferred half of tranche item 6. The candidate-capture half is NOT part of this task: it would be a second write path. Blocked on a domain-scoping design (household vs PhD never share a namespace)."
---
# Bounded read-only retrieval at session start

## Why

The retired central-memory task asked for Claude Code sessions to start with bounded, relevant memory. Part of that is already
satisfied (`CLAUDE.md` and the `aoteru-estate-routing` skill). What remains is optional: a **read-only** retrieval step that is
bounded in size and scoped to one domain. This is the only part of tranche item 6 that the ratified ADR leaves open.

## Constraints from the ratified ADR (`tyecam1/misumi:docs/memory-architecture.md`)

- Existing Odysseus runtime memory is the only runtime-memory mechanism: call `memory_provider` / `mcp_servers/memory_server.py`;
  do not add a store, broker or MCP memory authority.
- Household and PhD memory never share a namespace or retrieval path. A session in one domain must not retrieve the other's memory.
- **Read-only.** No candidate capture, no hook that writes memory. A write path needs its own owner decision (and
  `docs/memory-policy.md` already says what a candidate is and how it is deleted).
- Retrieval output is disposable context: it is never promoted to canon, and an empty result is a normal result.
- Honest provenance: `source_events` and `MemoryRelation` are incomplete and ordinary `Memory` rows are thin, so retrieved items
  must be shown as such, not implied to be sourced.

## Required work

1. A short design note: which domain a session belongs to (derive from the registered repository, do not guess), the size bound,
   and what is shown to the user.
2. Only after the owner approves the design: a read-only retrieval step using the existing surface, with tests for
   domain isolation, the size bound, the empty result and the unsourced-memory presentation.

## Acceptance

- A session in one domain never sees the other domain's memory (tested).
- No new store, broker, MCP server or write path exists after the change.
- Turning the step off restores today's behaviour exactly.

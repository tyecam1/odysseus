---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-01-postgres-estate-migration
title: "Add an explicit PostgreSQL migration for the Stage 6 estate-execution columns"
status: review
priority: medium
task_type: implementation
created_by: claude
created_at: 2026-10-01T19:00:00+01:00
updated_at: 2026-10-02T02:00:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single
architecture_rationale: "One schema-migration defect in the existing database module. Extend the existing migration helpers; do not add a migration framework."
single_agent_baseline: "One implementation owner can read the existing SQLite migration, write the PostgreSQL equivalent, and prove it against a real PostgreSQL schema built from the pre-Stage-6 models."
execution_host: compute-box
context_budget: medium
coordination_reason: "Found by retrospective Sol review #1 of PR #44 (Misumi long-horizon programme). Latent: every current deployment is SQLite."
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - core/**
  - src/**
  - tests/**
  - docs/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
inputs:
  - core/database.py (the Stage 6 estate-execution worker column migration)
  - docs/aoteru-multihost-execution-implementation-plan.md (portability claims)
  - automation/review/misumi-long-horizon-programme-evidence.md
outputs:
  - explicit PostgreSQL migration for the Stage 6 estate-execution columns and any replaced indexes
  - a test that migrates a pre-Stage-6 PostgreSQL schema and exercises the write lane against it
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Sol review is retrospective and non-blocking for this programme (operator policy 2026-10-01)."
---

# Explicit PostgreSQL migration for the Stage 6 estate-execution columns

## Finding (retrospective Sol review #1, severity major)

`core/database.py` migrates the Stage 6 estate-execution worker columns only for SQLite: the migration returns early for any other database URL. `Base.metadata.create_all` creates missing **tables** but never adds columns or replaces indexes on **existing** tables, so an existing PostgreSQL deployment would keep the pre-Stage-6 schema and the write-lane operations could fail at runtime.

## Why it is latent

Every current deployment (lab control plane, home household runtime) uses SQLite, and the multihost plan's portability claim ("SQLite and PostgreSQL behaviour where the contract claims portability") was only exercised on SQLite. No PostgreSQL instance was available during the integration to test a fix honestly, so no unverified migration was written.

## Required work

1. Read the existing SQLite migration and list every column and index it adds or replaces for `estate_executions` (and any related table).
2. Write the PostgreSQL equivalent with idempotent DDL (`ADD COLUMN IF NOT EXISTS`, guarded index replacement), keeping the same defaults and nullability, and no data loss for existing rows.
3. Prove it against a **real** PostgreSQL schema built from the pre-Stage-6 models: migrate, then exercise the write lane's create/update/recover paths.
4. Keep SQLite behaviour unchanged and keep the migration additive and re-runnable.

## Acceptance

- A pre-Stage-6 PostgreSQL schema migrates cleanly and the write-lane tests pass against it.
- Re-running the migration is a no-op.
- Existing SQLite suites unchanged. No new migration framework.

## Resolution (2026-10-02, awaiting review)

Implemented `_migrate_add_estate_execution_worker_columns_postgresql` in `core/database.py` and hooked it into
`init_db()`. Proven against a real PostgreSQL 16 schema built from the pre-Stage-6 models
(`tests/test_estate_stage6_pg.py`, 7 tests, skipped without `ODYSSEUS_TEST_POSTGRES_URL`): migrate, backfill,
both indexes replaced and enforcing, re-run is a no-op (index OIDs unchanged), duplicate rows keep the old index
and log, a `create_all`-built schema migrates unchanged, other dialects untouched, and the write lane (create,
admission control, update, recovery read, `lease_serialized_transaction`) runs on the migrated tables. Mutation
check: with the migration disabled the migration test fails. SQLite suites unchanged.

Scope limit, recorded rather than hidden: the older `PRAGMA table_info(...)` migrations and the BBC store remain
SQLite-only, so PostgreSQL is still not a supported general target (see
`docs/misumi-durable-transcript-runtime.md`, section PostgreSQL).

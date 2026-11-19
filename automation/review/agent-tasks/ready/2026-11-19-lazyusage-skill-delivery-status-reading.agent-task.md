---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-19-lazyusage-skill-delivery-status-reading
title: "Teach the /lazyUsage skill to read delivery status: kinds, skipped reasons, ledger and handoffs"
status: ready
priority: critical
task_type: implementation
created_by: claude-controller
created_at: 2026-11-19
updated_at: 2026-11-19
executor: codex_subscription
execution_mode: implementation
execution_host: lab
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: low
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: dev
related_tasks:
  - 2026-11-16-lazyusage-sonnet-coordinator-lab
  - 2026-11-09-lazyusage-bounded-persistent-continuation
inputs:
  - .claude/skills/lazyUsage/SKILL.md
  - docs/runtime-work-packages/2026-11-19-lazyusage-delivery-corrections.md
  - src/lazy_usage_runtime.py
allowed_paths:
  - .claude/skills/lazyUsage/SKILL.md
denied_paths:
  - src/**
  - config/**
  - core/**
  - routes/**
  - tests/**
  - "**/.env"
  - "**/secrets/**"
outputs:
  - an updated section 4 of the lazyUsage skill that explains how the controller reads delivery status
result_path: .claude/skills/lazyUsage/SKILL.md
---

# Teach the /lazyUsage skill to read delivery status

## Why

After the 2026-11-19 delivery corrections (`docs/runtime-work-packages/2026-11-19-lazyusage-delivery-corrections.md`)
`am lazy status` carries new checkpoint evidence, but the laptop skill still tells the controller only to
"inspect owed reviews". A controller that cannot tell advisory output from delivery will repeat the original
mistake of reporting executed work as shipped.

## Change

Edit **only** section "4. Continue and close correctly" of `.claude/skills/lazyUsage/SKILL.md`. Add one short
subsection (at most 20 lines, no new commands) that states, from `src/lazy_usage_runtime.py` as it now stands:

1. `checkpoint.task_kind` / `ledger[ref].kind` is one of `implementation`, `reconnaissance`, `evidence`, `review`,
   `protected_handoff`; **only `implementation` can deliver**. A successful `reconnaissance`, `evidence` or `review`
   run is advisory output, never delivery, and the ledger outcome `advisory_complete` must be reported as such.
2. `checkpoint.skipped` maps candidate refs to why they were not dispatched (for example `protected_handoff`,
   `requires_zotero_unavailable`, `no_deliverable_surface`, `ungrounded_local_executor`, `result_reusable`,
   `failure_backoff`, `awaiting_owner_acceptance`). `protected_handoff` entries are **operator actions**, to be
   listed for the human, never retried or routed to a model.
3. `ledger` outcomes `advisory_complete`, `delivered_pending_acceptance`, `failed`, `quota_parked`,
   `protected_handoff` persist across activations; an unchanged card is not re-dispatched while its result is fresh
   (advisory/handoff 24 h, failure 1 h) but a changed card or a stated provider reset always allows a retry.
4. `delivered_pending_acceptance` means a verified worker commit exists and owner acceptance, required independent
   review and merge are still owed; report it as owed, not shipped.

Do not change any other section, any code or any configuration. Keep the existing tone and formatting.

## Acceptance

- The diff touches only `.claude/skills/lazyUsage/SKILL.md`, only within section 4, and adds at most 20 lines.
- Every identifier named above is spelled exactly as in `src/lazy_usage_runtime.py`.
- Deterministic check: `git diff --stat` shows one file; `grep -c "protected_handoff" .claude/skills/lazyUsage/SKILL.md` is at least 1.
- Independent economical review (Haiku/Terra/GLM-Flash) of the diff; owner acceptance by the controller after merge.

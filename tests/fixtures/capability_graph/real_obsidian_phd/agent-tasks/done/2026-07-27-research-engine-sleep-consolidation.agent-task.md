---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-research-engine-sleep-consolidation
title: "Design a review-first research-engine sleep and consolidation cycle"
status: done
priority: medium
task_type: memory-architecture
created_by: chatgpt
created_at: 2026-07-27T14:00:00+01:00
updated_at: 2026-08-01T12:30:00+01:00
executor: claude_subscription
execution_mode: implementation
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: codex/research-engine-sleep-consolidation-20260731
allowed_paths:
  - automation/review/memory-consolidation/**
  - automation/review/agent-tasks/**
  - Scripts/automation/**
  - automation/docs/**
  - automation/config/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
  - 02-library/**
  - 10-inbox/**
  - 11-projects/**
  - 12-log/**
inputs:
  - automation/docs/continuous-improvement-loop-contract.md
  - automation/docs/currency-and-derived-trust.md
  - automation/docs/agent-boundaries.md
  - 10-inbox/research-engine-convergent-refinement-programme.md
outputs:
  - automation/review/memory-consolidation/2026-07-27-sleep-cycle-design.md
  - automation/review/memory-consolidation/sleep-cycle-schema.json
  - automation/review/memory-consolidation/sleep-cycle-dry-run.md
result_path: automation/review/memory-consolidation/2026-07-27-sleep-cycle-design.md
review_report_path: automation/review/memory-consolidation/2026-07-27-sleep-cycle-design.md
handoff_model: claude_codex_review_package
operator_decision_path: automation/review/memory-consolidation/2026-07-27-sleep-cycle-design.md
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/445"
supersedes: []
duplicates: []
notes: "This task adapts consolidation ideas at system level. It does not authorise model-weight updates, LoRA training or synthetic self-training. PR-2 repair: executor normalised from claude_then_codex to claude_subscription (execution_mode normalised to implementation); codex_subscription performs independent verification before merge."
---
# Design a review-first research-engine sleep and consolidation cycle

## Goal

Create an offline cycle that turns recent run traces, accepted decisions, repeated failures and successful procedures into compact review-side memory candidates while pruning stale derived state.

## Sleep stages

1. **NREM-style consolidation:** deduplicate recent traces, preserve source links, identify stable decisions/open loops, compress repeated observations and invalidate superseded derived entries.
2. **REM-style recombination:** generate bounded candidate connections, skill hypotheses, missing tests and future scenarios from consolidated material.
3. **Wake gate:** validate candidates against sources, compare against existing memory/skills and require explicit promotion.

## Constraints

- Canonical research knowledge remains unchanged.
- Raw traces remain recoverable; consolidation never replaces provenance.
- Generated abstractions carry derivation and confidence metadata.
- No self-generated candidate trains or edits a model.
- Dream/recombination outputs are hypotheses, not facts or tasks.
- The cycle must support separate PhD and Misumi memory domains.

## Acceptance criteria

- Defines fast, medium and slow memory classes with update and expiry rules.
- Produces a deterministic dry run from existing review artifacts.
- Detects at least duplicate, superseded, stale, unresolved and recurrent-success cases.
- Measures compression ratio, retrieval effect, false consolidation and operator review burden.
- Requires review before any candidate becomes a durable skill, decision or canonical note.

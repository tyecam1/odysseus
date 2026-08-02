---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-07-02-asi-evolve-lesson-skill-compilation-and-graph-fitness
title: ASI-Evolve — lesson-to-skill compilation path and link-graph fitness metrics
status: done
priority: medium
task_type: implementation
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
linked_pr: https://github.com/tyecam1/obsidian-PhD/pull/401
allowed_paths:
  - automation/review/improvement-loop/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/docs/continuous-improvement-loop-contract.md
  - Scripts/automation/improvement_loop.py
  - automation/review/improvement-loop/
  - PR #392 body (deferred paired follow-ups)
outputs:
  - automation/review/improvement-loop/skills/
  - automation/review/improvement-loop/iterations/ (extended fitness snapshots)
---

# Task: ASI-Evolve — lesson-to-skill compilation path and link-graph fitness metrics

## Objective
Extend the observe-only C1 loop (merged PR #392) per the 2026-07-02 system-efficiency audit §6 with two pattern-source adoptions: (1) Hermes-pattern lesson-to-skill compilation — promote repeated high-confidence lessons into staged executable artefacts (prompt fragments, checklists, lint-rule proposals) under `automation/review/improvement-loop/skills/`, human-gated before any copy into `automation/prompts/`; (2) Graphify-pattern deterministic link-graph fitness — orphan evidence count, unlinked DRM nodes, dangling wikilinks — added to iteration fitness snapshots. First verify whether PR #392's deferred paired follow-ups (cli.py wiring for improvement-loop subcommands, capability_manifest.json entry) actually landed on main; if not, land them first in the same PR.

## Approach
Any change to `Scripts/automation/improvement_loop.py` or `cli.py` goes through a draft PR under pr-review-gate, not via allowed_paths. Staged skill artefacts and extended fitness snapshots are the durable review-side outputs under `automation/review/improvement-loop/`. The loop remains observe-only throughout — no merges, no stage-2 activation, no model calls performed by the loop itself.

## Acceptance criteria
- Observe-only invariant untouched: no merges, no stage-2, no allowlist widening, no canonical writes, no model calls.
- Store-root fail-closed check still passes.
- Improvement-loop tests and capability truth tests green.
- At least one real fitness snapshot includes the new graph metrics.

## Stop condition
Any change that would require widening writes beyond `automation/review/improvement-loop/` is out of scope for this task — record it as a lesson artefact instead of implementing it.

## Risk if done badly
The loop becoming a second memory/task authority undermines the human-gated promotion model. `skills/` holds staged artefacts only and must never be treated as, or copied into, live prompts without explicit human promotion.

---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-07-01-advance-completed-claude-task-lifecycle
title: Advance completed Claude-routed tasks from inbox to review
status: done
priority: medium
task_type: repo-hygiene
created_by: claude-system-review
created_at: 2026-07-01T13:00:00+01:00
executor: codex_subscription
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
  - automation/review/routine-reports/agentic-batch-review/2026-07-01-s2-perception-batch-deep-review.md
outputs: []
---

# Task: Advance completed Claude-routed tasks from inbox to review

## Objective

Eight Claude-routed tasks already have substantive, in-repo review-side outputs but remain in `inbox/`/`ready/`. Move each task file to `review/`, set `status: review`, and add a `result_path` pointing at its output. Change nothing but frontmatter status/result_path and the file location.

## Tasks and result paths

- `2026-06-15-prune-agent-routines-for-vault-relevance` → `automation/review/decision-packets/2026-06-15-agent-routine-relevance-pruning.decision-packet.md`
- `2026-06-16-s2-experiment-question-split-and-boundaries` → `automation/review/s2-benchmark-design/2026-06-16-experiment-question-split-and-boundaries.md`
- `2026-06-16-s2-system-architecture-and-communication-framework` → `automation/review/s2-benchmark-design/2026-06-16-system-architecture-and-communication-framework.md`
- `2026-06-16-benchmark-system-paper-scaffold` → `automation/review/s2-benchmark-design/2026-06-16-benchmark-system-paper-scaffold.md`
- `2026-06-16-constrained-manipulation-literature-grounding-and-novelty` → `automation/review/s2-benchmark-design/2026-06-16-constrained-manipulation-literature-grounding-and-novelty.md`
- `2026-06-19-s2-cad-to-system-model-supervision-pack` → `automation/review/s2-system-modelling-2026-06-19/s2-cad-system-model-supervision-pack.md`
- `2026-06-17-s2-e1-benchmark-validity-comparators` → `automation/review/s2-benchmark-design/literature-reinforcement/2026-06-17-s2-e1-benchmark-validity-comparators.md`
- `2026-06-17-s2-e1-sensing-event-classification-literature` → `automation/review/s2-benchmark-design/literature-reinforcement/2026-06-17-s2-e1-sensing-event-classification-literature.md`

## Why

Queue truth: `status` must match folder. These outputs exist and were authored previously; leaving the tasks in `inbox/` misrepresents open work.

## Acceptance criteria

Each of the 8 task files is in `review/` with `status: review` and a correct `result_path`; no other content changed; no denied paths touched. Task remains V2_HUMAN_VERIFIED (human confirms the moves).

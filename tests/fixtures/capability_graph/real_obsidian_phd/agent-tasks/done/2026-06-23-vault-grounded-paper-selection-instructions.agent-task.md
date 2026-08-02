---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-23-vault-grounded-paper-selection-instructions
title: Author vault-grounded paper-selection instructions
status: done
priority: medium
task_type: instruction-authoring
created_by: claude
created_at: 2026-06-23T00:00:00+01:00
updated_at: 2026-06-23T00:00:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: true
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
allowed_paths:
  - automation/review/research-selection/2026-06-23-vault-grounded-paper-selection-instructions.md
  - automation/review/agent-tasks/**/2026-06-23-vault-grounded-paper-selection-instructions.agent-task.md
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
  - 04-supportDesign/thesis-benchmark/s2-perception-first-benchmark-rationale.md
  - 04-supportDesign/thesis-benchmark/s2-e1-framework-safety-perception-literature-targeting.md
  - 00-dashboards/artifact-types.md
  - 01-research-plan/research-questions/S2.md
outputs:
  - automation/review/research-selection/2026-06-23-vault-grounded-paper-selection-instructions.md
---
# Task: Author vault-grounded paper-selection instructions

## Objective

Write a concise, reusable instruction set that makes paper-selection decisions smart and grounded in vault content, so future literature retrieval (human or agent) ranks and includes/excludes sources consistently with the DRM research model — not by generic relevance.

## Agent execution contract

- Work autonomously until the instruction file exists and acceptance criteria are met.
- Read the inputs to derive the heuristics; do not invent criteria ungrounded in the vault.
- Beaver/Zotero read-only; do not mutate Zotero or canonical evidence.
- Keep output review-side under `allowed_paths`. No canonical or planning files may be mutated.
- Before reporting completion, audit each heuristic against a vault source.

## Required output

One instruction packet that specifies:

1. How to map a candidate paper to the active substudy aim (S2 etc.) and artifact ontology (`artifact-types.md`) before inclusion.
2. Cluster definitions to target/avoid, reusing `s2-e1-framework-safety-perception-literature-targeting.md` (adopt grammar, not domain identity).
3. A ranking rubric (e.g. 1–5 relevance) with explicit include / exclude tests and a "what to copy / what not to copy" prompt.
4. A rule distinguishing literature evidence from analytical inference in any downstream note.
5. A duplicate-/gap-check step against existing library collections before adding.
6. A short worked example applying the rubric to one in-library paper.

## Hard constraints

- Instructions only; do not perform a literature search as part of this task.
- Do not encode domain-copying; preserve process-engineering relevance.
- Treat the packet as provisional until human approval.

## Acceptance criteria

- Output packet exists at the allowed path.
- Heuristics are vault-traceable, concise, and immediately usable by a human or agent.
- No denied paths, Zotero state, or canonical files mutated.

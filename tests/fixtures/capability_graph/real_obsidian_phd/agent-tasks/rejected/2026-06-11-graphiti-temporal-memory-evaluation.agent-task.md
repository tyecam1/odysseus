---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-11-graphiti-temporal-memory-evaluation
title: Design and scaffold Graphiti-style temporal memory prototype for Odysseus
status: rejected
rejection_reason: inactive_platform_expansion
priority: high
task_type: implementation
created_by: human
created_at: 2026-06-11T23:30:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths: []
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/docs/agentic-system-platform-assessment-plan.md
  - automation/docs/agent-ecosystem-centralisation-design.md
  - automation/docs/agent-task-centralisation-plan.md
outputs:
  - automation/review/platform-evaluations/graphiti-temporal-memory-evaluation.md
  - automation/review/architecture/graphiti-temporal-memory-prototype.md
  - automation/review/prototypes/graphiti-memory/README.md
result_path: automation/review/architecture/graphiti-temporal-memory-prototype.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Deferred 2026-06-12 consolidation: reopen only after the research integrity + handoff contracts merge (memory/retrieval family precondition). Verdict CLOSE_AS_DEFERRED in automation/review/platform-evaluations/agentic-work-item-consolidation-review.md."
---

# Task brief

## Objective

Create an implementation-ready Graphiti-style temporal memory prototype for Odysseus, with enough repository scaffolding that the next step is execution/testing rather than another planning task.

## Required work

1. Inspect current vault architecture docs and current automation/test conventions.
2. Research Graphiti only as needed to identify adoptable features:
   - temporal entity memory;
   - relation updates over time;
   - decision lineage;
   - supersession tracking;
   - task provenance;
   - evidence-to-question evolution;
   - capability drift detection.
3. Produce `automation/review/architecture/graphiti-temporal-memory-prototype.md` specifying:
   - entity schema;
   - relation schema;
   - source files from which the graph is rebuilt;
   - derived-state storage boundary;
   - rebuild procedure;
   - query examples;
   - rejection conditions.
4. Create a review-side prototype scaffold under `automation/review/prototypes/graphiti-memory/` with README and sample fixture data. If safe and lightweight, create Python scaffold under `Scripts/automation/prototypes/graphiti_memory/` that can later parse fixture task/decision/PR metadata into graph-ready records.
5. Add a minimal contract test if implementation code is created. The test should verify that the prototype cannot emit canonical writes and that graph records carry source paths.
6. Produce a short platform evaluation explaining whether to continue, defer, or reject Graphiti after the scaffold.

## Authority boundaries

- Graphiti-derived memory is advisory and rebuildable.
- Graphiti may not be cited as evidence.
- Graphiti may not directly promote canonical notes.
- Graphiti state must be rebuilt from vault/task/PR sources.
- This task may not change canonical research files.

## Stop conditions

Block the task if the implementation would create a second authority for research memory, require canonical writes, bypass the agent-task lifecycle, require public endpoints, or require secrets not already configured.

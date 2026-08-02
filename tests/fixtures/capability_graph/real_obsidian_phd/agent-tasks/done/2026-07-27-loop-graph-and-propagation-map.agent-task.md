---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-loop-graph-and-propagation-map
title: "Generate the cross-repo graph of loops, gates and propagation"
status: done
priority: high
task_type: architecture-observability
created_by: chatgpt
created_at: 2026-07-27T14:00:00+01:00
updated_at: 2026-08-01T12:30:00+01:00
executor: codex_subscription
execution_mode: implementation
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
branch: codex/loop-graph-propagation-map-20260727
allowed_paths:
  - automation/review/architecture/loop-graph/**
  - automation/review/agent-tasks/**
  - Scripts/automation/**
  - Scripts/automation/tests/**
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
  - automation/docs/architecture-index.md
  - automation/docs/full-system-plan.md
  - automation/docs/continuous-improvement-loop-contract.md
  - automation/docs/odysseus-central-interface-contract.md
  - automation/config/**
outputs:
  - automation/review/architecture/loop-graph/loop-graph.json
  - automation/review/architecture/loop-graph/loop-graph.md
  - automation/review/architecture/loop-graph/loop-graph.mmd
  - automation/review/architecture/loop-graph/gap-report.md
result_path: automation/review/architecture/loop-graph/loop-graph.md
review_report_path: automation/review/architecture/loop-graph/gap-report.md
handoff_model: codex_work_package
operator_decision_path: automation/review/architecture/loop-graph/gap-report.md
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/439"
supersedes: []
duplicates: []
notes: "Graph outputs are derived. They must not become a new architecture authority."
---
# Generate the cross-repo graph of loops, gates and propagation

## Goal

Produce a machine-readable and visual graph of every live or planned loop across `obsidian-PhD`, `odysseus` and `misumi`, including authority, inputs, outputs, tools, stores, permissions, gates, evaluators and feedback paths.

## Node types

- objective;
- task/work item;
- agent/executor;
- skill;
- tool;
- data/source store;
- runtime service;
- artifact;
- validator/evaluator;
- human gate;
- external mutation;
- memory/consolidation stage.

## Edge types

`reads`, `writes`, `dispatches`, `uses`, `produces`, `validates`, `approves`, `blocks`, `supersedes`, `promotes`, `observes`, `scores`, `backpropagates_to`, `depends_on`.

## Required diagnostics

- loops with no evaluator;
- evaluators with no frozen baseline;
- write paths with no permission gate;
- outputs with no consumer or retention policy;
- duplicated loops and queues;
- feedback that cannot reach the component responsible for failure;
- cycles capable of self-authorising work;
- cross-domain memory leakage risk.

## Acceptance criteria

- Every edge cites a source file or is marked inferred.
- Active, partial, planned and blocked capabilities are visually distinct.
- The graph can be regenerated deterministically.
- At least one forward and backward path is traceable end to end.
- The derived graph never overrides implementation-truth documents.
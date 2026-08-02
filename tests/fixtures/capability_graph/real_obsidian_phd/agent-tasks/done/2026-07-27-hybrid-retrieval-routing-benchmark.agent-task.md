---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-hybrid-retrieval-routing-benchmark
title: "Benchmark lexical, vector, hybrid and graph-assisted retrieval routing"
status: done
priority: high
task_type: retrieval-evaluation
created_by: chatgpt
created_at: 2026-07-27T14:00:00+01:00
updated_at: 2026-08-01T12:30:00+01:00
executor: codex_subscription
execution_mode: implementation
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: codex/hybrid-retrieval-routing-benchmark-20260731
allowed_paths:
  - automation/review/evals/**
  - automation/review/retrieval/**
  - automation/review/agent-tasks/**
  - Scripts/automation/retrieval/**
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
  - automation/docs/current-capabilities.md
  - automation/docs/semantic-runtime-readiness.md
  - automation/docs/agent-boundaries.md
outputs:
  - automation/review/evals/retrieval-routing-benchmark.json
  - automation/review/evals/retrieval-routing-benchmark.md
  - automation/review/retrieval/query-class-routing-proposal.yaml
result_path: automation/review/evals/retrieval-routing-benchmark.md
review_report_path: automation/review/evals/retrieval-routing-benchmark.md
handoff_model: codex_work_package
operator_decision_path: automation/review/evals/retrieval-routing-benchmark.md
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/444"
supersedes: []
duplicates: []
notes: "Full-vault index construction remains optional and derived. Evaluate before changing committed defaults."
---
# Benchmark lexical, vector, hybrid and graph-assisted retrieval routing

## Goal

Determine which retrieval mode should answer which research-engine query class using a frozen, representative and contamination-aware benchmark.

## Query classes

- exact identifiers, paths, citekeys and named decisions;
- terminology and phrase lookup;
- conceptually similar evidence with different vocabulary;
- temporal questions about supersession and changing decisions;
- cross-document synthesis with provenance;
- code/architecture dependency questions;
- negative-control and adversarial contamination queries.

## Required comparisons

- current lexical backend;
- BM25 lexical backend;
- configured dense/vector backend;
- hybrid candidate fusion;
- optional reranking;
- graph-assisted retrieval from a derived graph, if available.

## Acceptance criteria

- Uses held-out queries and explicit expected targets.
- Reports recall@k, MRR, contamination, unsupported-result rate, latency, context bytes and fallback frequency.
- Preserves canonical/review/superseded state in scoring.
- Produces a routing proposal by query class, not one global winner.
- Identifies when lexical search is strictly preferable.
- Does not change default retrieval policy without a reviewed decision.

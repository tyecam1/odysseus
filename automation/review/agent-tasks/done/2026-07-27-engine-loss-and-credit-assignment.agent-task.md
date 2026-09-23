---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-engine-loss-and-credit-assignment
title: "Define the research-engine loss vector and credit-assignment contract"
status: done
priority: high
task_type: architecture-evaluation
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
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: codex/engine-loss-credit-assignment-20260727
allowed_paths:
  - automation/review/architecture/**
  - automation/review/evals/**
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
  - automation/docs/agent-boundaries.md
  - automation/docs/current-capabilities.md
  - 10-inbox/research-engine-convergent-refinement-programme.md
outputs:
  - automation/review/architecture/2026-07-27-engine-loss-and-credit-assignment.md
  - automation/review/evals/engine-objective-schema.json
result_path: automation/review/architecture/2026-07-27-engine-loss-and-credit-assignment.md
review_report_path: automation/review/architecture/2026-07-27-engine-loss-and-credit-assignment.md
handoff_model: codex_work_package
operator_decision_path: automation/review/architecture/2026-07-27-engine-loss-and-credit-assignment.md
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/436"
supersedes: []
duplicates: []
notes: "Wave A. Do not implement an autonomous optimiser until the loss vector, blocking constraints and credit-assignment tests are reviewed."
---
# Define the research-engine loss vector and credit-assignment contract

## Goal

Specify and test a multi-objective evaluation contract that can attribute a run's success or failure to context, prompt, skill, tool, orchestration, model, data or permission decisions.

## Required design

- Preserve blocking integrity and permission failures as hard constraints rather than averaging them away.
- Define task success, provenance fidelity, retrieval quality, regression, operator burden, context cost, latency, maintenance cost and uncertainty closure metrics.
- Represent a forward run as ordered trace spans and a backward pass as evidence-backed blame candidates.
- Require isolated reruns before assigning causal credit to one changed component.
- Add a minimal JSON schema and deterministic validator.
- Define how ERA/autoresearch-style candidate branches may optimise a frozen evaluator without changing the evaluator.

## Acceptance criteria

- Every metric has a data source, direction, range, missing-data rule and anti-gaming rule.
- Hard failures cannot be hidden by a higher aggregate score.
- Credit assignment distinguishes correlation, plausible cause and verified cause.
- At least five historical runs can be represented without inventing data.
- Tests reject mutable evaluators, missing baselines and untraceable score changes.
- No canonical research content is changed.
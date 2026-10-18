---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-agent-evaluation-and-observability-ratchet
title: "Unify agent evaluation, tracing and permission observability"
status: done
priority: high
task_type: evaluation-observability
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
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: codex/agent-eval-observability-ratchet-20260727
allowed_paths:
  - automation/review/evals/**
  - automation/review/observability/**
  - automation/logs/observability/**
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
  - automation/docs/agent-boundaries.md
  - automation/docs/current-capabilities.md
  - automation/docs/continuous-improvement-loop-contract.md
  - automation/docs/odysseus-central-interface-contract.md
outputs:
  - automation/review/evals/agent-run-evaluation-contract.md
  - automation/review/evals/agent-run-schema.json
  - automation/review/observability/trace-schema.json
  - automation/review/observability/permission-event-schema.json
  - automation/review/evals/cross-harness-golden-corpus.json
result_path: automation/review/evals/agent-run-evaluation-contract.md
review_report_path: automation/review/evals/agent-run-evaluation-contract.md
handoff_model: codex_work_package
operator_decision_path: automation/review/evals/agent-run-evaluation-contract.md
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/437"
supersedes: []
duplicates: []
notes: "Tracing remains sanitized and local. This task must not expand captured content or permissions."
---
# Unify agent evaluation, tracing and permission observability

## Goal

Create one cross-harness run record and evaluation surface for Claude, Codex, Odysseus and bounded local agents so improvements can be measured and unsafe behaviour can be diagnosed.

## Trace model

Capture identifiers and sanitized metadata for:

- objective and task contract;
- context sources and token/byte contribution;
- skill and tool activation;
- permission request, grant, denial and expiry;
- tool call, result class and retained raw-log pointer;
- artifact creation and validation;
- evaluator score and hard failures;
- human intervention and decision;
- continuation/closeout state;
- candidate change and rollback.

Do not capture raw private prompts, evidence excerpts, credentials or unrestricted document content by default.

## Evaluation corpus

Include deterministic implementation tasks, bounded research review, retrieval, extraction, writing critique, unsafe-write denial, missing-context handling, duplicated-work suppression and cross-domain isolation.

## Ratchet behaviour

A capability cannot claim improvement unless it beats the current baseline on the relevant held-out cases without increasing hard failures. New regressions become permanent cases. Permission widening requires a separate decision regardless of score.

## Acceptance criteria

- One versioned run schema works across the named harnesses.
- Trace events preserve causal order and parent/child relationships.
- Raw logs are recoverable without bloating the normal context.
- The evaluator distinguishes task quality, safety, provenance and operator burden.
- At least one historical run can be replayed into the schema.
- Sanitization tests fail closed on secrets and sensitive content.
- Observability cannot itself widen data or write permissions.
---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-11-operator-cockpit-platform-evaluation
title: Evaluate Open WebUI and LibreChat as Odysseus operator cockpit
status: rejected
rejection_reason: inactive_platform_expansion
priority: medium
task_type: critique
created_by: human
created_at: 2026-06-11T23:33:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
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
outputs:
  - automation/review/platform-evaluations/operator-cockpit-evaluation.md
result_path: automation/review/platform-evaluations/operator-cockpit-evaluation.md
handoff_model: claude_work_package
notes: "Deferred 2026-06-12 consolidation: reopen only after the MCP policy and the deployment policy exist. Verdict CLOSE_AS_DEFERRED in automation/review/platform-evaluations/agentic-work-item-consolidation-review.md."
---

Assess:
- Open WebUI;
- LibreChat;
- maintaining the current fragmented interfaces.

The recommendation must include:
- deployment architecture;
- security model;
- integration with Odysseus;
- MCP exposure policy;
- remote compute routing;
- maintenance burden.

UI convenience alone is not sufficient justification.

---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-11-ragflow-vs-onyx-research-rag-bakeoff
title: Run research-document RAG bakeoff between RAGFlow and Onyx
status: rejected
rejection_reason: inactive_platform_expansion
priority: high
task_type: decision-packet
created_by: human
created_at: 2026-06-11T23:31:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
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
  - automation/review/decision-packets/2026-06-11-ragflow-vs-onyx-bakeoff.decision-packet.md
result_path: automation/review/decision-packets/2026-06-11-ragflow-vs-onyx-bakeoff.decision-packet.md
handoff_model: claude_work_package
notes: "Deferred 2026-06-12 consolidation: reopen only after the source-acquisition provenance pilot lands and retrieval contracts stabilise (F7 ruling governs vector-store posture meanwhile). Verdict CLOSE_AS_DEFERRED in automation/review/platform-evaluations/agentic-work-item-consolidation-review.md."
---

Assess which features from RAGFlow and Onyx should be adopted into Odysseus.

Required outputs:
- comparative scoring matrix;
- architecture diagrams;
- ingestion pipeline implications;
- integration cost estimate;
- authority-boundary analysis;
- recommendation: adopt RAGFlow, adopt Onyx, adopt both as different layers, or reject both.

The benchmark must use Odysseus requirements rather than generic RAG benchmarks.

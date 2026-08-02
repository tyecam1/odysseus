---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-28-j1-cross-field-comparator-context-scout
title: J1 cross-field comparator and contextual-focality scout
status: review
priority: medium
task_type: evidence-readiness
trust_tier: extraction-support-material
created_by: codex
created_at: 2026-07-28T00:00:00+01:00
updated_at: 2026-07-31T12:00:00+01:00
executor: codex_subscription
execution_mode: review-first
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/J1/2026-07-28-j1-cross-field-comparator-context-scout.md
  - automation/review/J1/2026-07-28-j1-comparator-context-patterns.csv
  - automation/review/J1/2026-07-28-j1-targeted-source-import-shortlist.csv
  - automation/review/agent-tasks/**/2026-07-28-j1-cross-field-comparator-context-scout.agent-task.md
denied_paths:
  - 00-dashboards/**
  - 01-research-plan/**
  - 02-library/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/**
  - 07-standards/**
  - 11-projects/**
  - 12-log/**
  - "**/*.pdf"
  - My Library.bib
inputs:
  - automation/review/J1/2026-07-28-j1-section-3-human-decisions.md
  - automation/review/J1/2026-07-27-j1-section-3-evidence-pass.md
  - automation/review/J1/2026-07-27-j1-section-3-claim-evidence-matrix.csv
outputs:
  - automation/review/J1/2026-07-28-j1-cross-field-comparator-context-scout.md
  - automation/review/J1/2026-07-28-j1-comparator-context-patterns.csv
result_path: automation/review/J1/2026-07-28-j1-cross-field-comparator-context-scout.md
completed_by: codex
completed_at: 2026-07-28T23:59:00+01:00
notes: "Governed work item for a bounded, concept-driven evidence scout. Current outputs are provisional review material pending human acceptance and any approved import/extraction."
---
# Task: Scout comparator selection and contextual focality

## Objective

Determine how adjacent fields choose comparator conditions, align baselines with intended claims, and select focal evaluation dimensions from context. Produce a bounded evidence packet for J1 §3.7 without creating a universal evaluation framework or editing the manuscript.

## Questions

1. How are manual, current-practice, fixed-automation, full-automation and alternative-collaboration baselines selected?
2. How is comparator choice tied to an explanatory, diagnostic, predictive, comparative or deployment-facing claim?
3. How are technical, human, safety, recovery and transfer outcomes combined without an unjustified composite?
4. Which task, role, risk, user, environment and deployment variables activate focal dimensions?
5. Which principles transfer to HRC, and which remain field-specific?
6. Does the evidence support a matrix, decision tree, layered checklist or conditional statement?

## Scope controls

- Search the repository and Zotero before any external source.
- Use a bounded concept-led sample across human factors, automation, HRI/HRC, resilience and safety-critical evaluation, medical-device human factors, benchmarking, autonomous systems and directly transferable responsible-AI evaluation.
- Treat standards and guidance as duties or frameworks, not empirical findings.
- Do not test field-wide novelty, map whole fields, modify Zotero, promote evidence or write manuscript prose.

## Acceptance criteria

- Every used source has a resolvable citekey or is explicitly labelled as an unimported candidate.
- Every substantive source claim has a verified page or stable locator and evidence type.
- The output states counterclaims and transfer limits.
- The recommended method remains conditional and non-scoring.
- Any import recommendation is deduplicated against Zotero, BibTeX, repository notes and attachments.

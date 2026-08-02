---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-16-document-trust-propagation-procedure
title: "Document trust propagation procedure"
status: done
priority: medium
task_type: orchestration
created_by: chatgpt
created_at: 2026-07-16T11:03:00+01:00
claimed_by: fable-sol-route-loop
claimed_at: 2026-07-17T13:37:30+01:00
completed_by: fable-sol-route-loop
completed_at: 2026-07-17T13:49:00+01:00
verification_verdict: accept
verification_by: human

executor: claude_subscription
execution_mode: handoff
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
branch: agent/karpathy-wiki-hardening-work-items
allowed_paths:
  - automation/review/**
  - automation/docs/**
  - 08-template/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
  - 04-supportDesign/**
  - 10-inbox/**
  - 11-projects/**
  - 12-log/**
  - My Library.bib
  - 02-library/My Library.bib
  - "**/*.pdf"

inputs:
  - automation/review/repo-governance/2026-07-16-karpathy-llm-wiki-hardening-ultraplan.md
  - automation/review/agent-tasks/review/2026-07-16-define-currency-and-derived-trust-contract.agent-task.md
  - automation/docs/drm-mapping-rules.md
  - automation/docs/verification-routing-policy.md
  - automation/docs/evidence-policy.md
  - automation/docs/pr-reviewer.md
  - 08-template/ai-use-reproducibility-note.md
outputs:
  - one bounded on-demand trust-propagation procedure for consolidation PR 5
  - minimal template or cross-link updates where justified
  - automation/review/routine-reports/repo-governance/2026-07-16-trust-propagation-procedure-report.md
result_path: automation/review/routine-reports/repo-governance/2026-07-16-trust-propagation-procedure-report.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: automation/review/agent-tasks/review/2026-07-16-document-trust-propagation-procedure.agent-task.md

operator_decision_path: ""
linked_pr: "#426"
supersedes: []
duplicates: []

notes: "Consolidation PR 5 amendment. Produce one on-demand procedure, not another root instruction essay or generic wiki manual."
---

# Document trust propagation procedure

## Objective

Define how currency, trust, contradiction, verification, supersession, and AI-use provenance move through ingest, extraction, synthesis, query-derived artifacts, decision support, dashboards, and promotion.

## Prerequisites

- W1 must establish or confirm the controlled currency and trust fields.
- Existing consolidation PR 4 work-routing changes must be respected.
- Search existing methodology, evidence, verification, AI-use, and reviewer documents before selecting the procedure owner.

## Required procedure scope

The procedure must cover:

1. source acquisition and immutable source identity;
2. extraction-derived support material;
3. atomic evidence drafting;
4. synthesis and comparison pages;
5. answers or analyses filed back into the vault;
6. decision packets and current-state summaries;
7. review-to-canonical promotion;
8. later source updates and supersession;
9. genuine research contradiction versus stale duplicate truth;
10. AI-assisted generation and human verification.

## Mandatory rules

- Derived trust cannot exceed the weakest material input without an explicit verification event.
- Model confidence is not evidence quality.
- Repetition or cross-link density does not raise trust.
- Extraction support remains ineligible for canonical claims until governed verification and promotion.
- Competing research findings remain visible with their scope and source basis.
- A stale current-facing summary may be superseded without deleting the historical record.
- Query-derived analysis may be filed only with source basis, verification route, and downstream eligibility appropriate to its inputs.
- No automatic claim-strength upgrade.

## Required work

1. Locate the smallest existing owner for this procedure.
2. Write a concise procedure with decision points and stop conditions.
3. Cross-link it from existing methodology or architecture indexes rather than duplicating its content.
4. Reuse the AI-use reproducibility template where material AI involvement affects publication or research claims.
5. Include minimal worked examples using review-side or template material only.
6. State which parts are descriptive policy and which are executable enforcement.
7. Produce the review-side report explaining what changed and what remains unenforced.

## Acceptance criteria

- One procedure owns the workflow.
- No new root-level manual, ontology, or planning surface.
- Trust and currency remain distinct concepts.
- Contradiction handling preserves competing evidence and scope.
- Query-derived artifacts cannot silently become canonical evidence.
- AI disclosure is required only where materially relevant.
- No canonical research files are edited.
- Agent-task lint, validation, validator ratchet, and `git diff --check` pass or have isolated environmental failures.

## Stop conditions

Stop and report blocked when:

- W1 vocabulary is unresolved;
- the procedure would duplicate an existing authoritative owner rather than update it;
- examples require changing canonical research claims;
- a proposed rule cannot distinguish evidence quality from document currency;
- the workflow would impose recurring manual metadata on ordinary notes.

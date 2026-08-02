---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-zotero-vault-trajectory-completeness
title: "Audit Zotero-to-vault completeness against the live research trajectory"
status: done
priority: high
task_type: literature-integrity-audit
created_by: chatgpt
created_at: 2026-07-27T14:00:00+01:00
updated_at: 2026-08-01T12:30:00+01:00
executor: claude_subscription
execution_mode: implementation
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: true
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: codex/zotero-vault-trajectory-completeness-20260727
allowed_paths:
  - automation/review/zotero-vault-trajectory/**
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
  - "**/*.pdf"
inputs:
  - automation/docs/current-capabilities.md
  - 01-research-plan/**
  - 03-concept/**
  - 04-supportDesign/**
  - 11-projects/tye/J1/**
  - 11-projects/cpi/**
outputs:
  - automation/review/zotero-vault-trajectory/coverage-ledger.csv
  - automation/review/zotero-vault-trajectory/trajectory-gap-report.md
  - automation/review/zotero-vault-trajectory/duplicate-and-metadata-findings.csv
  - automation/review/zotero-vault-trajectory/proposed-routing-manifest.json
result_path: automation/review/zotero-vault-trajectory/trajectory-gap-report.md
review_report_path: automation/review/zotero-vault-trajectory/trajectory-gap-report.md
handoff_model: claude_codex_review_package
operator_decision_path: automation/review/zotero-vault-trajectory/trajectory-gap-report.md
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/438"
supersedes: []
duplicates: []
notes: "Read-only by default. No Zotero or canonical vault mutation is authorised by this task. PR-2 repair: executor normalised from claude_then_codex to claude_subscription (execution_mode normalised to implementation); codex_subscription performs independent verification before merge."
---
# Audit Zotero-to-vault completeness against the live research trajectory

## Goal

Establish whether every research-relevant Zotero item is represented, traceable and correctly routed in the vault, and whether the vault's paper/evidence coverage matches the current S1-S5 trajectory rather than historical collection structure.

## Required analysis

- Reconcile Zotero items, attachments, citekeys, collections and tags against paper notes, annotations, evidence, project corpora and bibliography exports.
- Separate exact alignment, Zotero-only, vault-only, duplicate candidates, missing PDFs, orphan attachments, broken citekeys and stale metadata.
- Score trajectory relevance for S1 design considerations, S2 benchmark/process design, S3 human factors/communication, S4 control and S5 evaluation/transferability.
- Detect overrepresented historical themes and underrepresented current questions.
- Preserve why an item matters, not merely where it is filed.
- Produce conservative move/tag/note proposals with confidence and evidence, never silent reorganisation.

## Acceptance criteria

- Coverage denominator and exclusions are explicit.
- Every row resolves to stable Zotero and vault identifiers where available.
- Duplicate groups distinguish duplicate records from related publications.
- Research-trajectory routing is justified by current questions and work packages.
- Proposed changes are individually reviewable and default to `approved: false`.
- No canonical notes, Zotero items, collections, tags or PDFs are mutated.
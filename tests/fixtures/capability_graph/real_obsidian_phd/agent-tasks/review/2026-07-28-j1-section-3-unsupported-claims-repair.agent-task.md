---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-28-j1-section-3-unsupported-claims-repair
title: J1 Section 3 unsupported-claims evidence repair
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
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/J1/2026-07-28-j1-section-3-unsupported-claims-repair.md
  - automation/review/J1/2026-07-28-j1-targeted-source-import-shortlist.csv
  - automation/review/agent-tasks/**/2026-07-28-j1-section-3-unsupported-claims-repair.agent-task.md
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
  - automation/review/J1/2026-07-28-j1-section-3-unsupported-claims-repair.md
  - automation/review/J1/2026-07-28-j1-targeted-source-import-shortlist.csv
result_path: automation/review/J1/2026-07-28-j1-section-3-unsupported-claims-repair.md
completed_by: codex
completed_at: 2026-07-28T23:59:00+01:00
notes: "The 80-claim matrix is the control surface. Current review findings do not authorise manuscript, Zotero, or canonical evidence changes."
---
# Task: Repair unsupported and overstated J1 Section 3 claims

## Objective

For every matrix row marked `absent`, `contradicted`, `indirect`, or materially `partial`, determine the evidence route, strongest claim ceiling and disposition without rewriting the manuscript.

## Required method

For each controlled claim, record:

- current wording and argumentative role;
- evidence needed;
- existing candidate sources and local Zotero coverage;
- bounded external-search need;
- strongest defensible ceiling;
- retain, narrow, split, move, hold as normative, hold pending evidence, or remove only where no defensible role remains.

Prioritise industrial-applicability and adoption claims; SME constraints; worker-role outcomes; non-nominal events; handover and recovery; contextual focality; comparator integration; and framework-maturity claims.

## Scope controls

- Search repository and Zotero first.
- Do not rescue causal adoption claims with indirect evidence.
- Do not infer universal worker outcomes, field-wide absence or prevalence from bounded sources.
- Keep workload in §4, controller/safety-envelope design in §5, deployment consequences in §6 and wider implications in §7.
- Do not modify manuscript, Zotero or canonical evidence.

## Acceptance criteria

- All 54 controlled rows have a disposition.
- Sources, locators, evidence types and counterclaims are explicit.
- §3.5 and §3.6 delta-evidence readiness is decided.
- No recommended import duplicates a local item or attachment.

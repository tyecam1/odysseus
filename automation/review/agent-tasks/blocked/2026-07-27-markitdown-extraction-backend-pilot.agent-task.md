---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-markitdown-extraction-backend-pilot
title: "Pilot MarkItDown inside the governed extraction registry"
status: blocked
blocked_reason: >-
  The upstream MarkItDown tool lacks verified licence, concrete version,
  and single-repository identity evidence.
recheck_condition: >-
  A quarantine-first discovery pass verifies the upstream MarkItDown
  tool's licence, concrete version, and single-repository identity.
priority: medium
task_type: extraction-backend-pilot
created_by: chatgpt
created_at: 2026-07-27T14:00:00+01:00
updated_at: 2026-07-27T14:00:00+01:00
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
branch: codex/markitdown-backend-pilot-20260727
allowed_paths:
  - automation/review/extraction-backends/**
  - automation/review/agent-tasks/**
  - Scripts/automation/pdf_extract.py
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
  - automation/docs/current-capabilities.md
  - automation/docs/agent-boundaries.md
  - Scripts/automation/pdf_extract.py
outputs:
  - automation/review/extraction-backends/markitdown-pilot-report.md
  - automation/review/extraction-backends/markitdown-pilot-results.json
result_path: automation/review/extraction-backends/markitdown-pilot-report.md
review_report_path: automation/review/extraction-backends/markitdown-pilot-report.md
handoff_model: codex_work_package
operator_decision_path: automation/review/extraction-backends/markitdown-pilot-report.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Optional backend only. MarkItDown output remains extraction support material."
---

## PREREQUISITE — added by register round S1 (2026-07-31)

This pilot MUST NOT run until licence, version and single-repository
identity for the **UPSTREAM MarkItDown tool** are verified by a
quarantine-first discovery pass. MarkItDown is recorded `defer-until` in
`automation/review/platform-evaluations/external-pattern-register.yaml`
precisely because that evidence is absent.

The locally checked-in wrapper is not the upstream MarkItDown tool, and
local presence is not provenance for that tool. A pilot is a positive
verdict, so the pilot cannot supply its own admission evidence.
Verification first, then the pilot.

# Pilot MarkItDown inside the governed extraction registry

## Goal

Evaluate MarkItDown as a local, optional converter for DOCX, PPTX, XLSX, HTML, EPUB and difficult non-PDF inputs while preserving the existing extraction-record, provenance and trust contracts.

## Method

- Use a frozen corpus containing ordinary and malformed examples of each relevant format.
- Compare structure preservation, tables, headings, links, images/alt text, metadata, runtime and failure reporting against current adapters.
- Call the narrowest local conversion interface and deny URL/network conversion in the pilot.
- Preserve file hash, converter version, options, warnings and source path.
- Route output through existing normalisation and span contracts where defensible.

## Acceptance criteria

- No direct canonical write path is introduced.
- Unsupported or unsafe formats fail visibly.
- Output is labelled extraction support material.
- The pilot identifies exactly which formats improve and which regress.
- Dependency footprint and security implications are reported.
- Adoption is format-specific, not an unconditional replacement of current extraction.

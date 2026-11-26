---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-markitdown-extraction-backend-pilot
title: "Pilot MarkItDown inside the governed extraction registry"
status: ready
unblocked_evidence: automation/review/blocker-reconciliation/2026-11-09-odysseus-blocked-cards.md
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
repo: tyecam1/odysseus
migrated_from_repo: tyecam1/obsidian-PhD
migration_note: "Ownership migrated to Odysseus. Treat references to obsidian-PhD automation paths as historical inputs until capability-path convergence is complete."
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

## Plan (written 2026-11-26 by the controller; step 0 is to verify it against HEAD)
**Goal in one line.** First verify upstream MarkItDown's identity, licence and version. Pilot it as an optional per-format extraction backend only after that check passes and the dependency is approved.
**Already done / do not redo:** nothing for the pilot itself. MarkItDown is recorded as `defer-until` in automation/review/platform-evaluations/external-pattern-register.yaml. The unblock note is automation/review/blocker-reconciliation/2026-11-09-odysseus-blocked-cards.md.
**Steps:**
0. Check which named paths exist at HEAD after the obsidian-PhD migration (Scripts/automation/pdf_extract.py, automation/docs/*, the register, the unblock note) and where the current extraction adapters live (grep). If they sit outside allowed_paths, stop and report the mismatch; do not edit the card.
1. Quarantine-first upstream check, with no install: canonical repository, licence, version, package name, dependencies, and any network, cloud or plugin features. The local wrapper being present is not provenance. Record sources in automation/review/extraction-backends/markitdown-upstream-verification.md. If no web-capable read-only lane is available, stop and list the missing evidence.
2. MarkItDown is a new third-party dependency and the card is approval_required. Record its footprint and security notes, raise a precise owner debt, propose (do not apply) the register update, and stop until approved.
3. After approval: build a frozen corpus from synthetic or existing test fixtures (no vault paths), with ordinary and malformed DOCX, PPTX, XLSX, HTML and EPUB files, hashed in a manifest under automation/review/extraction-backends/. Test: hash check.
4. Add an optional adapter where step 0 found the registry. It uses the narrowest local-file call and refuses URL conversion and plugins. A missing backend or unsupported format fails visibly. Output is labelled extraction support material and carries file hash, converter version, options, warnings and source path. No canonical write. Tests: one fake-converter test per property.
5. Add a harness that compares MarkItDown with the current adapters on headings, tables, links, alt text, metadata, runtime and failures, writing automation/review/extraction-backends/markitdown-pilot-results.json. Test: schema check with fake backends.
6. Write automation/review/extraction-backends/markitdown-pilot-report.md (per-format improvements and regressions, dependency and security footprint, format-specific recommendation, operator decision, model used). Run the full suite and stop for human verification.
**Done when:**
- The upstream verification note cites a source for every claim, or the stop reason is recorded.
- No dependency was installed without approval.
- Fake-converter tests prove provenance, labelling, network refusal and visible failure.
- The report names which formats improve and which regress.
**Risks and stops:**
- If verification fails or is ambiguous, keep `defer-until` and stop. The pilot cannot supply its own admission evidence.
- Never touch denied vault paths or write canonical records.
- Any doubt about the licence or security becomes an owner debt, not a workaround.
**Ordering note:** Needs upstream verification, dependency approval and capability-path convergence for the migrated paths. Unblocks a per-format adoption decision.

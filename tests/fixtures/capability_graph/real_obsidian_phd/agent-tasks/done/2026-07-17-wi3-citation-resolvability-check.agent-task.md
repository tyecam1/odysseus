---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-17-wi3-citation-resolvability-check
title: Implement citation resolvability check
status: done
priority: high
task_type: implementation
created_by: fable-route-loop
created_at: 2026-07-17T00:00:00+00:00
executor: codex_subscription
execution_mode: central-orchestrator
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
branch: agent/genai-workshop-ingest
allowed_paths:
  - Scripts/automation/citation_check.py
  - Scripts/automation/cli.py
  - Scripts/automation/tests/test_citation_check.py
  - Scripts/automation/tests/test_capability_truth_contracts.py
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
  - automation/review/hygiene/*-citation-resolvability.md
  - automation/review/hygiene/*-citation-resolvability.json
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/sources/workshop-genai-researcher-2026/extraction/items.json
  - automation/review/sources/workshop-genai-researcher-2026/delta-audit.md
  - 02-library/My Library.bib
  - 02-library/RC-reviews.bib
outputs:
  - Scripts/automation/citation_check.py
  - Scripts/automation/tests/test_citation_check.py
result_path: Scripts/automation/citation_check.py
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Source slide S16-3. Capability is advisory-first and is not wired into the validator."
---

# Implement citation resolvability check

## Problem

The delta audit found quote-fidelity controls but no check that citekeys in staged Markdown resolve in the two configured BibTeX exports.

## Scope

Implement bounded frontmatter and Pandoc-body scanning, dated review-only reports, CLI advisory and strict modes, tests, and capability-truth updates.

## Exclusions

- No general YAML/BibTeX parser, validator wiring, citation-quality judgement, or bibliography mutation.
- No canonical or evidence write.

## Acceptance criteria

- Resolvable and unresolvable fixtures, list frontmatter, prose tokens, emails, and fenced code are covered.
- Advisory mode exits zero and strict mode exits one for unresolved references.
- Citation and capability-truth unit tests pass.
- Human review accepts the capability-affecting change.

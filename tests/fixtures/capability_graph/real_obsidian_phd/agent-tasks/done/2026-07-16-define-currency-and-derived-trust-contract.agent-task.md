---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-16-define-currency-and-derived-trust-contract
title: "Define currency and derived trust contract"
status: done
priority: high
task_type: orchestration
created_by: chatgpt
created_at: 2026-07-16T11:01:00+01:00
claimed_by: fable-sol-route-loop
claimed_at: 2026-07-17T13:37:30+01:00
completed_by: fable-sol-route-loop
completed_at: 2026-07-17T13:49:00+01:00
verification_verdict: accept
verification_by: human

executor: codex_subscription
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
  - Scripts/**
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
  - automation/review/repo-governance/2026-07-15-post-merge-consolidation-truth-map.md
  - automation/review/repo-governance/2026-07-16-karpathy-llm-wiki-hardening-ultraplan.md
  - automation/docs/architecture-index.md
  - automation/docs/path-authority.md
  - automation/docs/agent-task-frontmatter-schema.md
  - automation/docs/verification-routing-policy.md
  - Scripts/automation/evidence_authority.py
  - Scripts/automation/validator.py
  - 08-template/ai-use-reproducibility-note.md
outputs:
  - bounded documentation and template changes for consolidation PR 3
  - focused validation tests
  - automation/review/routine-reports/repo-governance/2026-07-16-currency-trust-contract-report.md
result_path: automation/review/routine-reports/repo-governance/2026-07-16-currency-trust-contract-report.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: automation/review/agent-tasks/review/2026-07-16-define-currency-and-derived-trust-contract.agent-task.md

operator_decision_path: ""
linked_pr: "#426"
supersedes: []
duplicates: []

notes: "Consolidation PR 3 amendment. Add minimal currency and derived-trust rules only to registered current-facing or machine-derived families. No mass backfill."
---

# Define currency and derived trust contract

## Objective

Implement the minimum contract needed to distinguish maintained, point-in-time, and historical current-facing surfaces and prevent derived synthesis from silently exceeding the trust of its material inputs.

## Prerequisites

- Consolidation PR 2 must be merged or its path-authority outcome must be otherwise present on `main`.
- Search existing schemas, templates, validators, capability documents, and task files for equivalent fields or rules.
- Reuse existing `trust_tier`, `verification_route`, `downstream_eligibility`, and `source_basis` conventions. Do not create synonyms.

## Required design

### Currency

Use this controlled vocabulary only where a registered surface family needs explicit currency:

- `maintained`
- `point-in-time`
- `historical`

Rules:

- `as_of` is required for registered `maintained` and `point-in-time` current-state surfaces.
- `superseded_by` is required when a known successor exists.
- Missing currency on ordinary or historical notes is not globally invalid.
- New fields must not become a universal manual burden.

### Derived trust

Enforce or report this invariant at machine-derived boundaries:

```text
derived trust cannot exceed the weakest material input unless an explicit verification event justifies the increase
```

The design must distinguish:

- material inputs that affect the claim;
- contextual inputs that do not determine trust;
- verification events that may justify a trust change;
- downstream eligibility independent of prose confidence.

## Required work

1. Identify the smallest existing documentation owner for the contract.
2. Identify registered current-facing families where currency ambiguity is material.
3. Add minimal template support only where useful.
4. Add validator or helper logic only if it can be precise and backwards-compatible.
5. Add focused tests for accepted values, malformed values, `as_of`, supersession, and trust monotonicity.
6. Update capability truth in the same PR only if executable behaviour changes.
7. Produce the review-side implementation report.

## Acceptance criteria

- No new artifact type or ontology namespace.
- No mass editing or backfill of historical notes.
- Existing notes without optional currency metadata remain valid unless they belong to a deliberately registered current-facing family.
- Invalid registered currency values are detected.
- Trust escalation without explicit verification is prevented or surfaced.
- Existing evidence authority semantics remain intact.
- Focused tests, full validation, validator ratchet, capability-truth tests where applicable, agent-task lint, and `git diff --check` pass or have clearly isolated environmental failures.

## Stop conditions

Stop and report blocked when:

- PR 2 path authority is absent;
- the existing trust vocabulary cannot be resolved without human judgement;
- implementation would require changes under canonical research roots;
- the only viable design requires universal frontmatter migration;
- the proposed rule would conflate currentness with evidence quality.

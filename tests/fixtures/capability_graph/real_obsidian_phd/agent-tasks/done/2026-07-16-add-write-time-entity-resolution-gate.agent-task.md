---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-16-add-write-time-entity-resolution-gate
title: "Add write-time entity resolution gate"
status: done
priority: high
task_type: orchestration
created_by: chatgpt
created_at: 2026-07-16T11:02:00+01:00
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
risk_level: high
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
  - automation/review/repo-governance/2026-07-16-karpathy-llm-wiki-hardening-ultraplan.md
  - automation/review/agent-tasks/review/2026-07-16-define-currency-and-derived-trust-contract.agent-task.md
  - automation/AGENTS.md
  - automation/docs/drm-mapping-rules.md
  - Scripts/automation/vault_context.py
  - Scripts/automation/vault_writer.py
  - Scripts/automation/evidence_enrichment.py
  - Scripts/automation/semantic_evidence_attach.py
outputs:
  - bounded write-time entity-resolution implementation for consolidation PR 3
  - focused resolver tests
  - automation/review/routine-reports/repo-governance/2026-07-16-entity-resolution-gate-report.md
result_path: automation/review/routine-reports/repo-governance/2026-07-16-entity-resolution-gate-report.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: automation/review/agent-tasks/review/2026-07-16-add-write-time-entity-resolution-gate.agent-task.md

operator_decision_path: ""
linked_pr: "#426"
supersedes: []
duplicates: []

notes: "Consolidation PR 3 amendment. Move duplicate-risk detection earlier for staged high-risk proposals while retaining promotion-time checks and all human ontology gates."
---

# Add write-time entity resolution gate

## Objective

Require a bounded resolution decision before drafting a new high-risk concept, DRM node, DRM link, research question, success criterion, or synthesis owner.

## Prerequisites

- W1 currency and derived-trust contract must be complete enough to identify proposal trust and eligibility.
- Consolidation PR 2 path authority must be present.
- Search all proposal-generation and duplicate-risk code before selecting an owner.
- Reuse the existing shared retrieval abstraction and lexical fallback. Do not add another index.

## Resolution contract

Every covered staged proposal must record:

```yaml
entity_resolution:
  decision: update_existing | create_new | unresolved
  matched_candidates: []
  match_basis: []
  new_entity_rationale: ""
```

Matching order:

1. stable identifier or canonical path;
2. exact normalised title or filename;
3. declared alias;
4. outgoing and incoming link overlap;
5. lexical retrieval;
6. optional semantic similarity.

Semantic similarity alone must never authorise a merge, rename, split, supersession, or canonical mutation.

## Required work

1. Identify the smallest shared pre-write owner used by relevant staged proposal routes.
2. Define covered high-risk proposal families explicitly.
3. Emit candidate paths, match basis, and confidence evidence.
4. Return exactly one state: `update_existing`, `create_new`, or `unresolved`.
5. Fail closed on unresolved high-risk proposals.
6. Preserve the existing promotion-time duplicate-risk review as defence in depth.
7. Preserve lexical-only operation when semantic retrieval is unavailable.
8. Add tests for stable-ID match, alias match, exact-title collision, distinct concepts with similar language, ambiguous candidates, semantic outage, and path normalisation.
9. Update capability truth in the same PR if executable behaviour changes.
10. Produce the review-side implementation report.

## Acceptance criteria

- No automatic canonical writes or ontology operations.
- No new retrieval database, queue, or index.
- High-risk proposal creation cannot proceed from `unresolved`.
- Existing proposals can route to `update_existing` without silently overwriting the target.
- `create_new` includes a non-empty rationale and candidate evidence.
- Semantic-backend failure is visible and falls back safely.
- Promotion-time duplicate checks remain active.
- Focused tests, full validation, validator ratchet, capability-truth tests, agent-task lint, and `git diff --check` pass or have isolated environmental failures.

## Stop conditions

Stop and record blocked when:

- no single existing pre-write owner can be identified without creating a parallel stack;
- implementation would need autonomous ontology mutation;
- candidate identity rules conflict with canonical DRM naming authority;
- false-positive separation cannot be demonstrated;
- a required write falls outside the task allowlist.

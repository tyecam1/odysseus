---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-16-prepare-stale-surface-currency-ledger
title: "Prepare stale surface currency ledger"
status: done
priority: high
task_type: migration
created_by: chatgpt
created_at: 2026-07-16T11:05:00+01:00
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
  - automation/review/repo-governance/**
  - automation/review/decision-packets/**
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
  - automation/review/agent-tasks/review/2026-07-16-implement-semantic-anti-drift-audit.agent-task.md
  - automation/docs/path-authority.md
  - automation/docs/central-operating-contract.md
outputs:
  - automation/review/repo-governance/2026-07-16-stale-surface-currency-migration-ledger.md
  - automation/review/decision-packets/2026-07-16-stale-surface-currency-migration.decision-packet.md
result_path: automation/review/repo-governance/2026-07-16-stale-surface-currency-migration-ledger.md
review_report_path: automation/review/decision-packets/2026-07-16-stale-surface-currency-migration.decision-packet.md
handoff_model: claude_work_package
handoff_prompt_path: automation/review/agent-tasks/review/2026-07-16-prepare-stale-surface-currency-ledger.agent-task.md

operator_decision_path: automation/review/decision-packets/2026-07-16-stale-surface-currency-migration.decision-packet.md
linked_pr: "#426"
supersedes: []
duplicates: []

notes: "Consolidation PR 7 ledger only. Prepare exact reversible proposals for stale current-facing surfaces. Do not apply canonical edits."
---

# Prepare stale surface currency ledger

## Objective

Create an approval-ready, path-specific migration ledger for current-facing surfaces that require currency classification, `as_of`, supersession lineage, or a stale-status banner.

## Prerequisites

- W1 currency contract is stable.
- W4 semantic anti-drift audit is implemented or has produced a manually reproducible candidate method.
- Consolidation PRs 2 to 6 have landed or their relevant outcomes are present.
- Search the full agent-task lifecycle and existing migration ledgers for duplicate ownership.

## Initial mandatory scope

Inspect the surfaces named in the 2026-07-15 consolidation truth map, including:

- stale current dashboards;
- six stale S2-E1 surfaces;
- unmarked plan documents that can be misread as current truth;
- review architecture artifacts whose status conflicts with their historical classification;
- other current-facing surfaces surfaced by W4 with clear evidence.

Do not widen into a whole-vault mass migration.

## Ledger fields

For every candidate path record:

- current path;
- current status and relevant frontmatter;
- current claim of currency;
- evidence that the surface is stale, maintained, point-in-time, historical, or unresolved;
- proposed exact classification;
- proposed `as_of` value where justified;
- proposed `superseded_by` target where known;
- exact frontmatter or banner diff;
- successor and inbound-link implications;
- risk of changing versus doing nothing;
- approval batch;
- rollback method;
- confidence and unresolved questions.

## Required classifications

Use exactly one per candidate:

- `maintained`
- `point-in-time`
- `historical`
- `unresolved`
- `no-change`

`unresolved` must become a decision item, not a guessed mutation.

## Required work

1. Build the candidate inventory from cited evidence.
2. Separate deterministic stale-state findings from judgement-heavy research or project-state decisions.
3. Propose exact reversible diffs.
4. Group low-risk compatible changes into small approval batches.
5. Keep S2-E1 boundary changes separate from generic dashboard currency changes.
6. Preserve all historical records and existing superseded material.
7. Create one concise decision packet with approve, amend, reject, and defer options per batch.
8. Do not modify any canonical or current-facing target.

## Acceptance criteria

- Every proposed change is path-specific, justified, and reversible.
- No canonical edit, move, deletion, or promotion is applied.
- Ambiguous surfaces are marked `unresolved`.
- Known successors are linked without fabricating lineage.
- Historical context remains discoverable.
- S2-E1 boundary-sensitive changes are isolated for explicit approval.
- The decision packet enables batch-level approval without requiring review of unrelated files.
- Agent-task lint and `git diff --check` pass.

## Stop conditions

Stop and report blocked when:

- W1 or W4 is unavailable;
- a candidate has no evidence for its currency classification;
- the proposed successor is ambiguous;
- a batch would mix unrelated authority classes;
- implementation would require canonical apply rather than ledger preparation;
- another active task already owns the same migration outcome.

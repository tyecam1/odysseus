---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-04-j1-s4-verification-economics-source-scout
title: Source scout for S4 sharpening — conformity assessment economics vs personalisation
status: blocked
blocked_reason: no_live_S4_claim_requires_search
recheck_trigger: live_J1_section_5_claim_needs_verification_economics_evidence
priority: medium
task_type: evidence-readiness
created_by: claude_cowork
created_at: 2026-07-04T11:32:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: true
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/J1/2026-07-04-s4-verification-economics-scout.md
  - automation/review/agent-tasks/**/2026-07-04-j1-s4-verification-economics-source-scout.agent-task.md
denied_paths:
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/**
  - 07-standards/**
  - 00-dashboards/**
  - 11-projects/**
inputs:
  - 11-projects/tye/J1/j1-ground-truth-plan.md
  - 11-projects/tye/J1/j1-evidence-map.md
  - automation/review/j1-plan-critical-review-2026-07-03.md
outputs:
  - automation/review/J1/2026-07-04-s4-verification-economics-scout.md
result_path: automation/review/J1/2026-07-04-s4-verification-economics-scout.md
notes: "The regulator/standards-engineer perspective reframes the S4 pivot from 'standards lag technology' (near-consensus, weak) to 'standards are floors optimised for repeatable conformity assessment; personalisation fights verification for a principled reason' (contested, sharp). Ground truth already carries a candidate S4 reformulation; this scout feeds the human decision to adopt it."
---
# Task: Source scout for S4 sharpening — conformity assessment economics vs personalisation

## Objective

Find and rank sources on the verification/conformity-assessment side of industrial robot safety standards (ISO 10218-1/-2, TS 15066, 13849-1) that bear on why personalisation and learned behaviour strain standardised verification — supporting or refuting the sharpened S4 assumption in the ground truth.

## Prompt

1. Search Zotero first (standards, verification, certification, safe learning, ISO 10218 revision literature). Evidence map §5 already lists Chemweno as good-but-limited; do not duplicate its routing.
2. Then bounded external search: standards-revision commentary (10218:2025 revision cycle), conformity-assessment economics, verification burden for adaptive/learned controllers, notified-body perspectives.
3. Output an evidence-route packet: max 10 candidate sources, each with claim offered, claim ceiling, which S4 design consideration it bears on, and whether it supports the sharpened assumption formulation or the original.
4. End with a one-paragraph recommendation: adopt, revise, or reject the candidate S4 reformulation in the ground truth. Recommendation only — the ground-truth edit is a separate approved task.

## Hard constraints

- Max 10 candidates. No manuscript prose. No plan edits. No PDF ingestion — routes only.
- Stop when candidates begin duplicating claims (Wohlin saturation logic applies to the scout itself).

## Acceptance criteria

Tye can decide the S4 pivot formulation in one reading pass, and §5 drafting inherits a ranked source list.

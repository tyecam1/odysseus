---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-04-j1-ground-truth-micro-patches
title: Review and apply approved J1 ground-truth micro-patches
status: inbox
priority: medium
task_type: human-approval
created_by: claude_cowork
created_at: 2026-07-04T11:32:00+01:00
executor: human
execution_mode: interactive
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
branch: ""
allowed_paths:
  - automation/review/agent-tasks/**/2026-07-04-j1-ground-truth-micro-patches.agent-task.md
denied_paths:
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/**
  - 07-standards/**
  - 00-dashboards/**
inputs:
  - 11-projects/tye/J1/j1-ground-truth-plan.md
  - automation/review/j1-plan-critical-review-2026-07-03.md
outputs:
  - 11-projects/tye/J1/j1-ground-truth-plan.md
result_path: ""
notes: "Human-gated canonical edit using pre-worded patches from the 2026-07-03/04 review synthesis. Automation remains read-only for the J1 plan. Patch 3 is additionally gated on Bainbridge Zotero ingestion (see 2026-07-04-j1-bainbridge-1983-ingestion-prep)."
---
# Task: Apply three approved micro-patches to J1 ground-truth plan

## Objective

After explicit approval, apply the exact patch texts below to `11-projects/tye/J1/j1-ground-truth-plan.md`. No rewording, no additional edits, update the `updated:` frontmatter date on application.

## Patch 1 — elevate exception/recovery (apply on approval)

Location: end of section "Worker centric through-thread", after the §3-§6 list.

Text to add:

> Exception/recovery is the through-thread's load-bearing junction: it is where role quality (§3), measurement burden (§4), operator authority (§5), and adoption economics (§6) coincide. Each body section links its design considerations back to recovery-as-role-evidence in one sentence. Evidence collection for exception/recovery stays deferred per the §3 gap note — this elevation changes framing, not search scope.

## Patch 2 — adopter-ledger channels in Pivot S5 (apply on approval)

Location: Pivot S5 section, after the "Design considerations to bolster and develop" bullet.

Text to add:

> - **Adopter-ledger expression:** where possible, transferability considerations are also expressed in adopter-ledger channels (turnover, training cost, recovery capability, absenteeism/injury) so the framework is priceable by industrial adopters. Worker voice remains a separate, non-collapsible consideration — it is not folded into ROI.

## Patch 3 — Bainbridge anchor (apply only after Zotero ingestion is confirmed)

Location: section "Normative anchors for §1 only", in the empirical-anchors list.

Text to add:

> - Bainbridge 1983 (ironies of automation) — historical anchor for §1: the residual-role trap is a 40-year-old observation; J1 claims its operationalisation for benchmarks, measurement, and standards, not the observation itself.

## Hard constraints

- Exact text only. If any anchor location has changed and the patch text no longer fits, stop and return to review rather than adapting.
- Patch 3 must not be applied while Bainbridge is absent from Zotero.

## Acceptance criteria

Ground truth reflects the three review-earned framing changes with zero scope expansion; diff shows only the supplied text plus the frontmatter date.

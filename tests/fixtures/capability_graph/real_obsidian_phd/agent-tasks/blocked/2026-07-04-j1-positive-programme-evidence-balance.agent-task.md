---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-04-j1-positive-programme-evidence-balance
title: Balance audit — what the HRC literature genuinely settles, from existing vault evidence
status: blocked
blocked_reason: manuscript_trigger_not_reached
recheck_trigger: J1_Wave_2_section_evidence_pass
priority: medium
task_type: synthesis
created_by: claude_cowork
created_at: 2026-07-04T11:32:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: true
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/J1/2026-07-04-positive-programme-credit-rows.md
  - automation/review/agent-tasks/**/2026-07-04-j1-positive-programme-evidence-balance.agent-task.md
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
  - 11-projects/tye/J1/j1-evidence-map.md
  - 11-projects/tye/J1/j1-concept-anchors.md
outputs:
  - automation/review/J1/2026-07-04-positive-programme-credit-rows.md
result_path: automation/review/J1/2026-07-04-positive-programme-credit-rows.md
notes: "Bias-check finding from the 2026-07-03 review: the problematisation-driven structure systematically underweights what HRC has genuinely delivered (ergonomic gains, safety sensing, real SME deployments). Without explicit 'literature-settled' credit in §3-§6, mainstream reviewers read the paper as hostile rather than corrective. Sources: existing vault evidence and Zotero annotations only."
---
# Task: Balance audit — what the HRC literature genuinely settles, from existing vault evidence

## Objective

Produce per-section "credit rows" — design considerations or claims the literature has genuinely settled in HRC's favour — as candidate *literature-settled* rows for the §7 framework concept-matrix.

## Prompt

1. Sweep existing RC-tier evidence, the evidence map, and Zotero annotations on already-held reviews (Kopp 2021, Puttero 2025, Keshvarparast 2024, Puspanathan 2024, Villani 2018, Callari 2025 and similar). **No new literature collection.**
2. For each of §3-§6, extract 2-4 delivered-benefit claims with citations and evidence tier (e.g., ergonomic strain reduction in specific task families; safety-rated sensing maturity; documented SME deployment wins).
3. Format each as a framework-matrix row candidate: pivot/substudy · consideration statement · evidence + tier · proposed claim ceiling · what the substudy must measure.
4. Flag any credit claim that depends on already-capable-adopter sampling (problematisation #8) — those cap at *conditionally supported*.

## Hard constraints

- Vault and Zotero-held sources only; zero new searching. Review-side output only; no manuscript prose; no plan edits.
- Apply the ground truth's matrix decision rules (peer-reviewed floor; tier caps).

## Acceptance criteria

Each §3-§6 drafting pass can pull its credit material from this packet without new reading, and the framework matrix gains candidate literature-settled rows.

---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-11-review-retention-sweep
title: Implement review-tree retention sweep per approved policy
status: done
priority: medium
task_type: implementation
created_by: claude-system-review
created_at: 2026-06-11T14:59:00+01:00
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
branch: ""
allowed_paths: []
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/routine-reports/system-design-review/2026-06-11-odysseus-research-engine-review.md
  - automation/review/decision-packets/2026-06-11-review-retention-policy.decision-packet.md
outputs: []
result_path: automation/review/routine-reports/review-retention-sweep/2026-06-30.review-retention-sweep.md
review_report_path: automation/review/routine-reports/review-retention-sweep/2026-06-30.review-retention-sweep.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Addresses review finding F3. Unblocked on 2026-06-30 after user approval. Dry-run implementation and move manifest were staged on 2026-06-30; no live sweep moved files."
---

# Task: Review-tree retention sweep

## Objective

Deterministic sweep implementing the approved retention policy: classify `automation/review/**` files by family/age/status, move or archive per policy, land every sweep as an ordinary draft PR with a machine-readable manifest of what moved and why.

## Constraints

Dry-run default; per-family caps per run; refuses anything in the policy's hard-exclusion set (open-task references, decision records, promotion audits, trust-ledger chains); never touches canonical paths; quarantine semantics preserved. Capability docs updated in the same PR; unit tests for classification and exclusion logic.

## Acceptance criteria

A dry run over the live tree produces a plausible manifest with zero exclusion violations; first live sweep PR reviewed and merged by the operator; repeatable without manual file lists.

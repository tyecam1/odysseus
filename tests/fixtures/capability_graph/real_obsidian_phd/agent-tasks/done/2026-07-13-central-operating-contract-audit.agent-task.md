---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-13-central-operating-contract-audit
title: "Central operating contract audit and standardisation"
status: done
priority: high
task_type: repo-governance-audit
created_by: chatgpt
created_at: 2026-07-13T10:00:00+01:00
updated_at: 2026-07-15T00:00:00+01:00
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
branch: sol/central-operating-contract-audit-20260713
allowed_paths:
  - automation/review/**
  - automation/docs/**
  - AGENTS.md
  - README.md
  - 10-inbox/backlog.md
denied_paths:
  - 00-dashboards/**
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 04-supportDesign/**
  - 11-projects/**
  - 12-log/**
  - "**/*.pdf"
inputs:
  - 10-inbox/backlog.md
  - automation/review/agent-tasks/**
  - automation/review/decision-packets/**
  - automation/docs/**
  - tyecam1/s2-e1-ros2-measurement-spine
outputs:
  - automation/review/repo-governance/2026-07-13-central-operating-contract-audit.md
  - automation/docs/central-operating-contract.md
result_path: automation/review/repo-governance/2026-07-13-central-operating-contract-audit.md
review_report_path: automation/review/repo-governance/2026-07-13-central-operating-contract-audit.md
handoff_model: codex_work_package
operator_decision_path: automation/review/repo-governance/2026-07-13-central-operating-contract-audit.md
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/421"
supersedes: []
duplicates: []
notes: "Implementation complete and staged for operator review. No canonical research or Zotero source mutation was performed."
---
# Central operating contract audit and standardisation

## Goal

Audit the repository's operating instructions and create or refine one concise central operating contract that any worker must read before acting.

The contract should make the repository more usable to Tye, not more bureaucratic. It should reduce sprawl, centralise operating rules, and clarify how the repo should be read before any agent edits it.

## Required content

The operating contract must concisely answer:

1. What this repository is and is not.
2. How the vault relates to executable repos such as `tyecam1/s2-e1-ros2-measurement-spine`.
3. Where current work truth lives.
4. Which paths are canonical, review-side, inbox/backlog, automation, and archived/superseded.
5. Which writes require explicit operator approval.
6. Which actions are forbidden without specific approval: canonical research mutation, evidence promotion, Zotero mutation, PDF/BibTeX mutation, raw-data ingestion, branch deletion, heartbeat fabrication, and broad cleanup.
7. How to route agent work without creating duplicate queues or audit sprawl.
8. How to handle mobile-only operator constraints.
9. How to use Beaver MCP/Zotero access: read and cite only; do not mutate source libraries without explicit decision.
10. How to report back: inspected, changed, files/PRs/issues affected, validation, next human action.
11. How Sol should treat existing executable repos: inspect and refine them, do not recreate them in the vault.

## Acceptance criteria

- The result is short enough to be read before work begins.
- It replaces or points through existing scattered instructions rather than duplicating them.
- It does not relax safety or authority boundaries.
- It preserves traceability for existing automation/review surfaces.
- It makes the repo easier for Tye to operate from mobile.
- It includes a migration note listing any stale surfaces that should be retired later.
- It explicitly distinguishes human mobile-only tasks, Sol implementation tasks, and parked later tasks.

## Constraints

- Do not edit canonical research content.
- Do not modify PDFs, BibTeX, Zotero, raw data, rosbags, images, or videos.
- Do not delete branches or mutate remote refs.
- Do not create a new queue unless the existing agent-task lifecycle cannot represent the work.
- Do not invent new PhD research direction.

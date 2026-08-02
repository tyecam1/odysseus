---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-11-review-retention-policy
title: Review-tree retention policy decision packet
status: done
priority: medium
task_type: decision-packet
created_by: claude-system-review
created_at: 2026-06-11T14:59:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/decision-packets/2026-06-11-review-retention-policy.decision-packet.md
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
  - automation/docs/agent-boundaries.md
  - automation/docs/agent-task-centralisation-plan.md
outputs:
  - automation/review/decision-packets/2026-06-11-review-retention-policy.decision-packet.md
result_path: automation/review/decision-packets/2026-06-11-review-retention-policy.decision-packet.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Addresses review finding F3. Judgement task: retention semantics interact with provenance and audit obligations. Blocks 2026-06-11-review-retention-sweep. 2026-06-12: packet delivered at result_path by claude lane; counts re-measured on main at 9b35af0a (2,822 files). Awaiting V2 operator approve/reject."
---

# Task: Review-tree retention policy decision packet

## Objective

One decision packet recommending a retention policy for `automation/review/**` (2,786 files; 1,804 annotation-rollup-backfill; 270 quarantine; 248 queues), structured as a single operator decision object.

## Required content

Per-family thresholds (age, status, supersession) for: queues, routine-reports, annotation-rollup-backfill, quarantine, superseded, agent-jobs. Archive mechanism options with one recommendation and at most two rejected alternatives (in-repo `automation/review/superseded/` moves vs tarball-and-prune via PR vs git-history-only deletion). Hard exclusions: anything referenced by an open task, decision record, promotion audit, or trust-ledger chain; quarantine families retain their quarantine semantics wherever they land. Consequence of doing nothing.

## Constraints

Packet only — no file moves or deletions. Provenance and audit trails must remain reconstructable after any recommended action. No weakening of trust-tier semantics.

## Stop condition

Done when the packet supports a single approve/reject decision feeding the sweep implementation task. Follow-up routing: `2026-06-11-review-retention-sweep` (codex_subscription).

## Close-out

Producer deliverable (the decision packet) merged on `main`: `automation/review/decision-packets/2026-06-11-review-retention-policy.decision-packet.md` confirmed present on `origin/main`, staged via PR #358 (commit `145d064a`, `ops: heartbeat writer staging hook + review-retention decision packet`). `linked_pr` in this task's frontmatter was left empty by the producer; the packet file is the durable evidence of delivery.

This close-out moves the producing task review -> done because the packet exists on `main`. It does NOT make the retention-policy approve/reject decision: that V2 operator decision remains open and human-gated, and the follow-up `2026-06-11-review-retention-sweep` correctly stays in `blocked/` until the operator approves the packet. Status moved review -> done 2026-06-15.

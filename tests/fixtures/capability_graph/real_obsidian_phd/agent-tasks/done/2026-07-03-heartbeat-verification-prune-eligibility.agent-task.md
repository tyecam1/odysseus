---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-07-03-heartbeat-verification-prune-eligibility
title: Verify heartbeat proof before prune eligibility
status: done
completed_at: 2026-07-23T00:00:00+01:00
verification_verdict: PASS
priority: high
task_type: repo-hygiene
created_by: codex
created_at: 2026-07-03T12:38:27+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/routine-reports/repo-hygiene/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/decision-packets/2026-07-03-repo-future-operating-plan.decision-packet.md
  - automation/review/decision-packets/2026-07-03-first-five-work-items.dispatch.md
  - automation/review/decision-packets/2026-07-03-pr-403-405-combined-fable-review.decision-packet.md
  - automation/review/routine-reports/odysseus-heartbeat/
  - automation/review/routine-reports/odysseus-heartbeat/2026-07-03-heartbeat-activation-status.md
  - automation/deploy/ubuntu/run_remote_upkeep_branch.sh
  - GitHub main branch state for tyecam1/obsidian-PhD
outputs:
  - automation/review/routine-reports/odysseus-heartbeat/2026-07-03-heartbeat-verification-prune-eligibility.md
result_path: automation/review/routine-reports/odysseus-heartbeat/2026-07-03-heartbeat-verification-prune-eligibility.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Closed 2026-07-23: origin/main contains continuous real daily heartbeat artifacts through 2026-07-23, so the three-day evidence gate is satisfied. This does not authorize branch deletion; R3 remains off."
---

# Task: Verify heartbeat proof before prune eligibility

## Owner and route

Owner: Codex.
Route: agent-task -> Codex.

## Objective

Count fresh daily Odysseus heartbeat artifacts on `main` after `REMOTE_UPKEEP_HEARTBEAT_TO_MAIN=true` activation and determine whether remote-upkeep prune eligibility has been reached.

Current starting state for this task: fresh daily heartbeats on `main` since activation: 0.

## Required output

Create one heartbeat eligibility report at `automation/review/routine-reports/repo-hygiene/2026-07-XX-heartbeat-prune-eligibility.md`.

The report must list:
- heartbeat artifact dates counted from `main`
- heartbeat artifacts excluded and why
- whether the three-fresh-daily-heartbeat gate has passed
- the next check date if the gate has not passed

## Acceptance criteria

- The count is taken from GitHub `main` or `origin/main`, not from unmerged upkeep branches.
- At least three fresh daily heartbeat artifacts are required before prune evidence is prepared.
- If fewer than three fresh daily heartbeats are visible, the report stops at eligibility status and next check date.
- No branch deletion occurs.
- No branch deletion command is executed.
- No canonical research content is touched.

## Stop condition

Stop without preparing prune evidence if any daily heartbeat is missing, stale, synthesized, or only present on an unmerged branch. Emit a CRITICAL warning recommendation in the report, but do not retry-loop and do not delete branches.

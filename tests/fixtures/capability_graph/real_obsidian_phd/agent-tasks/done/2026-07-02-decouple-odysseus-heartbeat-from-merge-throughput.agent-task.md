---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-07-02-decouple-odysseus-heartbeat-from-merge-throughput
title: Decouple Odysseus heartbeat from merge throughput and add stale alarm
status: done
priority: high
task_type: implementation
created_by: claude-orchestrator
created_at: 2026-07-02T14:30:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
linked_pr: https://github.com/tyecam1/obsidian-PhD/pull/399
allowed_paths:
  - automation/review/routine-reports/odysseus-heartbeat/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/deploy/odysseus-integration/vault_heartbeat.py
  - Scripts/automation/pr_review_gate.py
  - automation/config/settings.ini
  - automation/review/queues/research-engine-health.md
outputs:
  - automation/review/routine-reports/odysseus-heartbeat/ (resumed daily heartbeats)
---

# Task: Decouple Odysseus heartbeat from merge throughput and add stale alarm

## Objective
Heartbeats currently reach main only when a remote-upkeep branch merges (verified 2026-07-02: heartbeats present on main for 06-12/15/22/25/29 while remote-upkeep branches went unmerged daily through 07-02; the box itself is healthy on :7000/:11434). Decouple heartbeat delivery from merge cadence via ONE of: (a) a heartbeat-only fast-forward commit to main under the existing MERGE_SAFE lane, or (b) gating auto-merge specifically for heartbeat-only upkeep PRs. Add a CRITICAL warning in research-engine-health when heartbeat age exceeds cycle+grace (1440+360 min), including the exact recovery command as one line in the health MD.

## Approach
Code changes to `Scripts/automation/pr_review_gate.py` or `automation/deploy/odysseus-integration/vault_heartbeat.py` must go through a draft PR under pr-review-gate — they are not written via allowed_paths. Only durable review-side outputs (heartbeat reports, decision notes) belong under `automation/review/routine-reports/odysseus-heartbeat/`. Prefer option (a) unless it conflicts with MERGE_SAFE lane constraints; document the choice and rejected alternative.

## Acceptance criteria
- Fresh heartbeat (<=24h old) lands on main for 3 consecutive days.
- Stale-heartbeat CRITICAL warning logic is visible in the health report with the named recovery command.
- If capability-affecting, `automation/docs/current-capabilities.md` and `automation/docs/capability_manifest.json` updated in the same PR.
- Capability truth tests pass: `python -m unittest Scripts.automation.tests.test_capability_truth_contracts`.

## Stop condition
If box-side credentials or config are the actual blocker (not the merge-coupling), stage a decision card describing the blocker and stop — do not attempt credential remediation.

## Risk if done badly
A synthesized or laptop-side-faked heartbeat would mask real box failures behind a false-green signal. The heartbeat-only lane must stay narrowly scoped and must not widen into a general auto-merge exemption.

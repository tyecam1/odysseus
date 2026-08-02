---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-07-02-branch-hygiene-sweep-and-ttl
title: Branch hygiene sweep, upkeep self-prune, and TTL policy
status: blocked
blocked_reason: The policy and first sweep landed, but 91 remote branches remain against the fewer-than-20 acceptance criterion.
recheck_condition: Human approval of a refreshed per-branch deletion manifest followed by verified pruning.
priority: medium
task_type: repo-hygiene
created_by: claude-orchestrator
created_at: 2026-07-02T14:30:00+01:00
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
result_path: automation/review/routine-reports/repo-hygiene/2026-07-02-branch-hygiene-sweep.md
linked_pr: https://github.com/tyecam1/obsidian-PhD/pull/403
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
  - GIT-HYGIENE.md
  - GitHub branch list for tyecam1/obsidian-PhD
outputs:
  - automation/review/routine-reports/repo-hygiene/2026-07-02-branch-hygiene-sweep.md
---

# Task: Branch hygiene sweep, upkeep self-prune, and TTL policy

## Objective
The repo carries 100+ branches: 26 daily `automation/remote-upkeep-*` (never pruned), ~60 stale `chatgpt/*` from completed section-3 work, aged apply/chore/cleanup branches, and now-merged codex/claude branches from PRs #392-#397. Produce a deletion candidate list (merged-status, last-commit date, lane) per branch. After explicit human approval of the list, delete the approved branches. Patch the remote-upkeep worker to self-prune its own dailies older than 7 days. Open one GitHub issue proposing auto-delete-on-merge plus a branch-TTL clause for GIT-HYGIENE.md.

## Approach
Worker self-prune logic is a code change and must land via draft PR under pr-review-gate, not via allowed_paths. The candidate list and final sweep report are the durable review-side outputs under `automation/review/routine-reports/repo-hygiene/`. Verify merged-status against target branch for every candidate before listing it as deletable.

## Acceptance criteria
- Fewer than 20 live branches after approved deletions.
- Upkeep worker self-prunes dailies older than 7 days.
- Report lists every deletion with its merged-status evidence (commit SHA, merge PR/commit reference, last-commit date, lane).
- GitHub issue opened proposing auto-delete-on-merge and branch-TTL clause.

## Stop condition
Never delete an unmerged branch without explicit human approval of that specific branch. `rescue/*` branches are always excluded from deletion candidates entirely.

## Risk if done badly
Deleting unmerged evidence work is unrecoverable data loss. Merged-status verification against the actual merge target is mandatory per branch before it appears on the deletion list.

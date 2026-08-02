---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-01-review-dirty-rescue-branch
title: "Review dirty rescue branch"
status: done
completed_at: 2026-07-23T00:00:00+01:00
verification_verdict: PASS
priority: medium
task_type: repo-hygiene
created_by: human
created_at: 2026-07-01T00:00:00+01:00

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
branch: rescue/dirty-main-before-pull-20260701
allowed_paths:
  - automation/review/repo-hygiene/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
  - 10-inbox/**
  - 11-projects/**
  - My Library.bib
  - 02-library/My Library.bib

inputs:
  - branch:main
  - branch:rescue/dirty-main-before-pull-20260701
outputs:
  - automation/review/repo-hygiene/2026-07-01-dirty-rescue-branch-review.md
result_path: automation/review/repo-hygiene/2026-07-01-dirty-rescue-branch-review.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""

operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []

notes: "Review only. The branch preserves uncommitted work that was carried from an agent branch onto main during manual Git recovery."
---

# Review dirty rescue branch

## Context

The rescue branch should preserve a mixed dirty working tree that appeared while returning from `codex/quarantine-dashboard-dispatch-design-20260626` to `main`. The working tree included modified tracked files, deleted inbox files, moved completed inbox files, automation changes, review queue outputs, and untracked generated files.

## Task

Compare `rescue/dirty-main-before-pull-20260701` against updated `main` and produce a concise repo-hygiene report. This is a review-only task.

## Required analysis

1. Confirm whether the rescue branch exists locally and/or on origin.
2. Compare the rescue branch against `main` using summary and name-status diffs.
3. Classify changed paths into:
   - likely worth preserving
   - already represented on `main`
   - generated or temporary noise
   - requires human decision
4. Pay special attention to `.bib` files, inbox work-item moves, automation scripts, automation config, review queues, generated reports, and Obsidian plugin state.
5. Identify any human-facing work item, supervisor-facing note, or useful automation improvement that would be lost if the rescue branch were ignored.
6. Recommend a conservative follow-up sequence for the human, without executing it.

## Output

Write one report only:

`automation/review/repo-hygiene/2026-07-01-dirty-rescue-branch-review.md`

Use this structure:

```markdown
# Dirty Rescue Branch Review

## Verdict

## Branch state

## Preserve candidates

## Noise candidates

## Human decision required

## File-specific risks

## Recommended follow-up
```

## Acceptance criteria

- Do not mutate repository content except for the single review report.
- Do not merge, cherry-pick, restore, remove, or rewrite branch content.
- Tie each recommendation to inspected paths or Git comparison evidence.
- Keep the report concise enough for quick human approval.

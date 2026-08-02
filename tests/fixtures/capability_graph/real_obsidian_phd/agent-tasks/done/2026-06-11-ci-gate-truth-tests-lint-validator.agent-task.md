---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-11-ci-gate-truth-tests-lint-validator
title: Add CI gate running truth tests, agent-task lint, and validator on every PR
status: done
priority: high
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
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
  - .github/workflows/sync-to-huggingface.yml
outputs: []
result_path: ""
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/350"
supersedes: []
duplicates: []
notes: "Addresses review finding F1 (fail-open Git substrate). Deliverable is a draft PR; change scope via PR review gate, not allowed_paths."
claimed_by: claude_subscription
claimed_at: 2026-06-11T15:21:24+01:00
---

# Task: Add CI gate on every PR

## Objective

One lean GitHub Actions workflow that runs on every pull request: `python -m unittest Scripts.automation.tests.test_capability_truth_contracts`, the full `Scripts/automation/tests` suite (or a justified targeted subset if runtime exceeds ~10 min), `python -m Scripts.automation agent-task-lint` (fail on errors), and `python -m Scripts.automation validate` in read-only mode.

## Change scope (via draft PR)

`.github/workflows/**` plus `automation/docs/current-capabilities.md` and `automation/docs/capability_manifest.json` in the same change (capability-affecting: adds enforcement).

## Constraints

No secrets in the workflow; no canonical-path writes; no network calls beyond checkout/setup; workflow must pass on its own PR. Validator/lint must run against the PR's merged ref. Do not gate on the HF export workflow.

## Acceptance criteria

CI green on the implementing PR; a deliberately broken capability-manifest entry on a scratch branch fails CI; capability docs updated and truth tests pass.

## Close-out

Merged on `main` via PR #350 (commit `d4f4b356`, `ci: PR gate - truth tests, full suite, agent-task lint, validator ratchet`). Deliverable `.github/workflows/ci-gate.yml` confirmed present on `origin/main`. Status moved review -> done 2026-06-15.

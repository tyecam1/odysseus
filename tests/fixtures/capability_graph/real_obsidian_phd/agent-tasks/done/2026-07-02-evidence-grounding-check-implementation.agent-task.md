---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-07-02-evidence-grounding-check-implementation
title: Implement deterministic evidence-grounding checker for PR review
status: done
priority: medium
task_type: implementation
created_by: claude-orchestrator
created_at: 2026-07-02T14:30:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
linked_pr: https://github.com/tyecam1/obsidian-PhD/pull/400
allowed_paths:
  - automation/review/routine-reports/pr-reviewer/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - Scripts/automation/pr_review_gate.py
  - automation/review/routine-reports/agentic-batch-review/2026-07-01-s2-perception-batch-deep-review.md (manual prototype)
  - automation/config/settings.ini
outputs:
  - automation/review/routine-reports/pr-reviewer/ (checker reports)
---

# Task: Implement deterministic evidence-grounding checker for PR review

## Objective
Mechanise the citation checks performed by hand in the 2026-07-01 deep review. Build a script that, for a given PR diff: (1) verifies every `zotero://` key resolves via the read-only Beaver MCP endpoint, (2) verifies evidence records carry `trust_tier` and provenance fields, (3) samples n>=3 load-bearing quotes for verbatim match against extraction records, (4) exempts `[inf]`-tagged claims from quote-match while still requiring the tag to be present. Emit one pass/fail block per PR under the pr-reviewer report family.

## Approach
The checker itself is a code change to `Scripts/automation/` and must land via draft PR under pr-review-gate, not via allowed_paths. Integrate as an optional pr-review-gate step, advisory-only for the first month — it must never mutate PR content, evidence records, or annotations. Only its generated reports belong under `automation/review/routine-reports/pr-reviewer/`.

## Acceptance criteria
- Checker catches a seeded bad citation and a seeded missing `trust_tier` field in tests.
- Runs clean against the #396 file set.
- `automation/docs/capability_manifest.json` updated in the same PR.
- Capability truth tests pass: `python -m unittest Scripts.automation.tests.test_capability_truth_contracts`.

## Stop condition
If the Beaver endpoint is unavailable, the checker must report unavailable and exit non-zero rather than silently skipping checks.

## Risk if done badly
A lenient checker would launder ungrounded claims as "checked," which is worse than no checker. Adversarial test fixtures (seeded bad citation, seeded missing trust_tier) are required and must pass before the first advisory run against real PRs.

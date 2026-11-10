---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-10-three-repository-ultrareview-consolidation
title: "Consolidate recent work into three scoped Ultrareview branches"
status: inbox
priority: high
task_type: implementation
created_by: user-directed
created_at: 2026-11-10
updated_at: 2026-11-10
executor: ""
execution_mode: review-first
architecture: single-plus-verifier
architecture_rationale: "One Fable-led integrator, bounded deterministic branch/PR discovery and verification, one independent adversarial reviewer; uses existing Odysseus routing and each domain repository authority."
single_agent_baseline: "Enumerate live refs/worktrees; select safe candidate merge set; create frozen review branches and provenance manifests, then request operator release of three review credits."
execution_host: compute-box
context_budget: high
coordination_reason: "Three independent Git repositories with stack ancestry, conflicting work, human-approved scientific evidence and premium review scope limits."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - automation/review/**
  - evals/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
inputs:
  - AGENTS.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/subscription-model-currency-policy.md
  - tyecam1/misumi:AGENTS.md
  - tyecam1/obsidian-PhD:AGENTS.md
  - https://code.claude.com/docs/en/ultrareview
outputs:
  - three read-only source-branch inventories and provenance/coverage manifests
  - three temporary isolated review integration branches
  - three frozen, eligibility-checked diff/stat/test packets
  - explicit operator release decision for each Ultrareview credit
  - verified findings and residual review-debt ledger (after approved launch)
result_path: ""
review_report_path: ""
handoff_model: ""
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Intake requested 10 Nov 2026. No Ultrareview may be launched or human-gated research state promoted merely because this card exists. Reconcile against shipping-first backlog policy; this work directly targets existing undelivered work."
---

# Three repository-wide Ultrareviews: maximum *true* existing-work coverage

## Goal

Prepare **one review candidate per repository**, each integrating the largest compatible set of recent unmerged work, for exactly one high-value paid/free-credit Claude Code Ultrareview each: `tyecam1/misumi`, `tyecam1/odysseus`, and `tyecam1/obsidian-PhD`. Do not merge to production or claim that excluded changes were checked.

## Live baseline to verify (10 November 2026)

- Misumi: 4 open PRs; expected integration base `main`.
- Odysseus: 12 open PRs; `dev` is a significant integration base, including GLM phase-1 PR #261. Verify its actual current source of truth.
- PhD: 54 open PRs, many stacked and review-only. PR #658 alone has 203 files, 7,521 additions and 2,396 deletions relative to its stacked base; #650 adds 6,848 lines across 298 files. Both cannot be indiscriminately combined under the usual Ultrareview limits.
- Claude Code Ultrareview currently defaults to a maximum of **500 changed files and 8,000 changed lines** (`additions + deletions`) for a branch/PR diff. Confirm the installed CLI's actual bounds before use. Rejected oversized reviews do not consume a free run.

## Method

1. **Reconcile inventory, read-only.** Inspect GitHub open PRs and all relevant recent branches, including the registered laptop/lab worktrees, dirty/unpushed work, upstream ancestry, draft status, already-merged or superseded heads, canonical/research approvals and active source SHA. Classify historical branches rather than interpreting all names as latest work.
2. **Construct dependency graphs.** Map stack edges and compatible merge groups, including PhD J2 editing/manuscript ancestries and Odysseus `dev` versus `main`. Preserve history; never count nested ancestors twice. Record conflicts, mutually exclusive alternatives, read-only evidential artefacts and unsafe/secret paths.
3. **Select coverage rationally.** Score candidates by unreleased code/logic significance, connectedness, testability, unique relevant diff, and approved status. Fill each review's diff budget with the highest-value compatible changes. Large generated Markdown or reconstructed historical logs must not crowd out engineering risk; but all exclusions become explicit review debt.
4. **Stage in isolated worktrees.** From each live authoritative base create an appropriately named branch such as `review/ultra-20261110`. Integrate eligible source branches with normal provenance-preserving merges, not blind squash, reset, forced update or production merge. If a conflict cannot be resolved purely from evidence, exclude it and record the blocking decision. Do not modify or promote canonical PhD research claims/manuscripts, confidential files or evidence requiring human sign-off.
5. **Record truthful coverage.** For each branch store its base SHA, exact frozen HEAD, all source branch SHAs, included source work, already subsumed material, blocked conflicts, intentionally omitted PRs, scope exclusions, unresolved approvals, tests and *actual* `base...review` changed files/line counts. Separate `reviewed` from `included` until the review completes.
6. **Verify preflight.** Run existing deterministic CI and integrity checks, test merge-induced interactions, independently challenge high-risk integration resolutions (Sol via existing authorised lane), inspect for credentials/private or unapproved upload data and check current Claude Code size limits. If above limit, re-scope honestly. If too broad or semantically incoherent, stop instead of wasting a credit. Draft review PRs are acceptable only when they cannot trigger production deploy or automatic paid reviews.
7. **Freeze and request explicit approval.** Present exactly three proposed scopes, inclusion/exclusion metrics, cost/free-run status, and launch commands. Do not execute `/code-review ultra` or spend one of the three credits until the operator explicitly authorises each run. Use branch or PR mode as appropriate; with PR mode run `/code-review ultra <PR>` from the matching repo.
8. **Post-review:** preserve findings with file/line/reproduction evidence and severity, adjudicate false positives, perform bounded fixes on separate branches as authorised, keep the source review HEAD as the reviewed snapshot, and report remaining unreviewed debt. A code review never certifies scientific validity or supersedes publication/research-ethics gates.

## Model/effort and authority

Use **Fable 5.2 high effort** for cross-branch architectural decisions where authenticated and permitted; escalate to xhigh only for difficult unresolved graph or semantic conflicts. Follow subscription currency policy, live preflight (`aoteru preflight`) and existing qualify-first model routing; do not hard-pin an unavailable model or create a new model router. Cheap/deterministic workers may parallelise independent inventory, statistics and tests, not shared Git branch writes. Do not send unbounded repo context to all agents.

## Acceptance

- One frozen, reproducible, provenance-safe, size-eligible (or explicitly blocked) integration candidate in *each* repo.
- A complete accounting of inspected work and why each item was included, already subsumed or excluded.
- Test and upload-safety evidence before each review; no hidden branch deletion, force-push, canonical promotion or production merge.
- No Ultrareview credit consumed without a specific operator go-ahead.
- Exactly three independent repo reviews when all three are eligible; clearly measured review coverage, findings, and review debt.

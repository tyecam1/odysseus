---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-26-cross-branch-project-state-reconciliation
title: "Cross-branch project-state reconciliation before agent dispatch and continuation"
status: inbox
priority: high
task_type: design-and-staged-implementation
created_by: operator-directed-chatgpt
created_at: 2026-11-26T20:01:00+00:00
updated_at: 2026-11-26
executor: claude_subscription
execution_mode: read-only-reconciliation-then-staged-implementation
architecture: single-plus-verifier
architecture_rationale: "Deterministic branch inventory and targeted parallel evidence retrieval, with one controller adjudicating status and an independent qualified verifier."
single_agent_baseline: "One qualified worker reconciles branch evidence and extends the existing portfolio/context mechanism."
execution_host: lab
context_budget: medium
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
related_tasks:
  - 2026-11-21-cross-repository-development-observer
  - 2026-11-26-card-hygiene-validator-and-sweeper
  - 2026-11-09-autonomous-blocker-reconciliation-and-opus-escalation
  - 2026-10-02-bounded-read-only-session-start-retrieval
inputs:
  - AGENTS.md
  - START-AGENTIC.md
  - config/repositories.yaml
  - scripts/agentic_portfolio.py
  - scripts/agentic_context.py
  - automation/review/agent-tasks/README.md
  - docs/aoteru-model-host-routing-contract.md
allowed_paths:
  - scripts/**
  - src/**
  - tests/**
  - routes/**
  - docs/**
  - automation/review/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*token*"
  - "**/*password*"
  - "**/*.pdf"
result_path: docs/runtime-work-packages/2026-11-26-cross-branch-project-state-reconciliation.md
---

## Objective

Agents must know the latest evidence-backed state of each project across accessible branches, not merely the checked-out branch or a stale task card. The operator suspects P1 and P3 may already be complete elsewhere; verify these examples without assuming their identity, completion or repository. Prevent duplicated development, stale dependency blocks and regressions from older branch context.

## Work

1. Run the existing preflight. Inspect live owner repositories (Odysseus, Misumi, obsidian-PhD and any other registered applicable project repositories), their queue/project identifiers, branch topology, current leases, relevant PRs and existing reconciliation/context mechanisms. Resolve P1 and P3 to canonical project IDs, including ambiguity if IDs collide. Inventory all accessible local and remote branch refs, worktrees and relevant PR heads, deduplicated by commit SHA; use safe read-only ref discovery and pinned object reads. Record inaccessible refs/hosts, dirty or unpublished work as unverified unless legitimately observable, and scan freshness. Never checkout, reset, merge, push or acquire a write lease to inspect another branch.
2. Reconcile project and task state against actual deliverables, acceptance criteria, test/review evidence, integration ancestry, runtime/deployment evidence where required, and active execution/lease records. Compare divergent heads using ancestry and relevant diffs; newest timestamp or a done label alone is not authority. Distinguish not started, in progress, implemented on another branch, verified on another branch, integrated, deployed/accepted where applicable, conflicting, superseded, blocked and unknown. Report exact repo/ref/commit/path or PR and missing acceptance evidence. Produce an initial all-project discrepancy report, explicitly addressing P1 and P3; do not silently collapse divergent implementations or canonical research decisions.
3. Extend existing portfolio/context discovery and dispatch/continuation contracts to provide a compact evidence-linked project-state snapshot before project selection, task admission and resumption. Refresh on relevant ref/PR/lease/evidence changes and recheck before material writes or delivery claims. Cache by ref SHA/evidence revision, deduplicate unchanged scans and expand only relevant diffs; use deterministic checks first and cheapest qualified workers for separable branch evidence. No separate scheduler, queue, router, or competing status authority. Reuse observer, sweeper and blocker-reconciliation interfaces where applicable.
4. If equivalent work is already verified elsewhere, recommend reuse/integration or owner-governed closure instead of dispatching duplicate implementation. If active work overlaps, coordinate or defer only the affected scope; unknown coverage must be explicit and must not be treated as proof of absence. Keep integration/review/deployment debt distinct from implementation debt. Any status mutation, merge or canonical promotion follows the owning repository's existing authority, write lease and verification gates. Read-only inventory is permitted without a write lease; implementation is not.
5. Test divergent branches, stale ready cards, completed-but-unmerged work, squash/cherry-pick equivalence, conflicting outcomes, stale tests tied to another SHA, branch changes between preflight and dispatch, inaccessible refs and uncommitted work, stale lease records and repeated unchanged scans. Demonstrate that an already completed equivalent task is not redispatched, an unmerged result is not falsely declared shipped, and an actually unfinished task remains eligible. Exercise the real agent-start and continuation path in a bounded canary before claiming deployment.

## Acceptance

- All registered applicable projects have a compact snapshot with branch coverage, evidence SHA, freshness, verified state, integration status, remaining work and next action; P1 and P3 explicitly adjudicated or unresolved with reason.
- Agents consume the snapshot through existing preflight/context and continuation paths, not merely a report they may forget to read.
- Deterministic regression tests and independent qualified review pass; demonstrate reduced duplicate dispatch and no false completion on the real path.
- Preserve repository-local ownership, existing shipping-first priority, approval gates, research evidence ceilings, and resource constraints. Triage ahead of other work only if live evidence shows duplication, incorrect admission or a material delivery blocker; otherwise integrate with the existing observer work.

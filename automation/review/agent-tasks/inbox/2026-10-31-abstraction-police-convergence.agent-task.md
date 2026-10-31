---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-31-abstraction-police-convergence
title: "Abstraction police: find and converge genuinely duplicate code abstractions"
status: inbox
priority: medium
task_type: implementation
created_by: user-directed
created_at: 2026-10-31T10:21:00+00:00
updated_at: 2026-10-31T10:21:00+00:00
executor: ""
execution_mode: review-first
architecture: single-plus-verifier
architecture_rationale: "A specialist near-duplicate abstraction detector and bounded convergence workflow under the existing Odysseus continuous-estate-steward lifecycle; no new model router, scheduler, graph database or repository-wide refactor authority."
single_agent_baseline: "AST/structural candidates plus usage/contract comparison; rank real maintenance costs, then implement one behaviour-preserving convergence patch with independent review."
execution_host: compute-box
context_budget: medium
coordination_reason: "Merging near-duplicate functions/modules can break subtle interface and domain contracts; code-aware verification and independent comparison are required."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - automation/review/**
  - docs/**
  - scripts/**
  - src/**
  - core/**
  - routes/**
  - tests/**
  - config/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
inputs:
  - AGENTS.md
  - docs/future-work/continuous-estate-steward.md
  - docs/aoteru-repository-ownership-trajectory.md
  - automation/review/agent-tasks/README.md
  - automation/review/agent-tasks/inbox/2026-10-31-dead-code-and-superseded-notes-hygiene.agent-task.md
  - "Open PR #203: Kurisu repository stewardship; pending at task creation"
outputs:
  - incremental near-duplicate abstraction finder integrated with existing steward
  - source-linked ranked candidates with canonical-owner decisions and reject reasons
  - one behaviour-preserving consolidation pilot in an authorised target repository
  - fixture suite for intentional similarities, semantically distinct implementations and actual duplicates
result_path: ""
review_report_path: ""
handoff_model: ""
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "New operator request 2026-10-31. Separate specialist subroutine from the dead-code/note lifecycle task; reuse PR #203 steward rather than another watcher. Inbox only until shipping-first backlog policy and task authority permit implementation."
---

# Abstraction police: duplicate-code convergence

## Purpose

Continuously identify **near-duplicate abstractions that represent the same behaviour and responsibility**, then consolidate the justified ones into a single canonical implementation, reducing maintenance divergence. The objective is *fewer independent sources of truth*, not maximal code sharing or fewer lines at any cost.

This is an incremental specialist detector beneath the **existing** [Odysseus estate steward](https://github.com/tyecam1/odysseus/blob/dev/docs/future-work/continuous-estate-steward.md). Its discovery is read-only by default; merges occur only in separately authorised, tested PRs. Coordinate with [pending steward PR #203](https://github.com/tyecam1/odysseus/pull/203).

## Detection and decision procedure

1. **Re-enter live state.** Inspect the current `dev` tree, task/PR inventory, steward status, permitted repositories, relevant language/build systems and active shared/runtime boundaries. Reuse current scanner/checkpoint facilities; defer optional work under the 2026-10-17 shipping-first policy.
2. **Find candidates incrementally.** Compare changed code with structurally related existing code using language-appropriate parsing (AST, normalised symbol/branch structure, signatures, dependency sets and control/data flow). Use lexical clone detection and, only if valuable and qualified, embeddings/model review for candidate discovery. Do not equate matching names, text similarity or embeddings with behavioural equivalence. Cover functions, classes, modules, policy validators, data transfer objects, config adapters and duplicated tests when justified.
3. **Trace the contract.** For each pair/cluster, identify callers, input/output shapes, preconditions, side effects, error semantics, concurrency, mutation/state lifetime, performance, security/privacy/safety behaviour, compatibility expectations, tests, schema/version and source authority. Explicitly list differences and what evidence would prove them intentional or accidental. Account for dynamic call sites and external consumers.
4. **Choose disposition.** Classify `duplicate-mergeable`, `similar-but-different`, `boundary-required`, `deprecated-compatibility` or `uncertain`. Select one canonical owner only when responsibilities and contracts genuinely match. Where one copy differs by a small supported parameter, prefer a narrow parameterised implementation and thin adapters if they clarify use; where differences express domain policies or different invariants, **keep separate**. Do not promote a giant common util, new framework, fragile inheritance hierarchy or cross-repo dependency merely to remove repetition.
5. **Rank by net value.** Prioritise actual change frequency, observed divergence/bugs, number of consumers, risk of inconsistent fixes and effort to maintain two implementations. Include migration effort, dependency coupling, performance and regression risk. A zero or negative net-value merge is rejected with rationale. Search existing open work before emitting any new task.
6. **Converge under authority.** The relevant repo owner accepts a bounded candidate. Execute normal Odysseus preflight, capability/host route, scope/lease and PR review checks. Record before/after contract tests, migrate callers, preserve public API or provide tested compatibility shims, and remove old bodies only after all references are accounted for. If the duplicate straddles Odysseus/Misumi/PhD, decide shared-runtime versus domain-specific ownership first; do not move scientific domain logic into the backend just because it looks similar.
7. **Verify and stop.** Prefer deterministic tests and independent review for consequential refactors. The same incremental scan must not reissue accepted/rejected candidates unless source state changes materially. Retain only concise source-hash findings in established steward/task state; no second graph DB or queue. Stop cleanly when remaining candidates are low-value, unproven or blocked.

## Verification / acceptance

- Positive fixture: two implementations that differ only in naming/organisation but have verified identical behaviour are detected and recommended for consolidation.
- Negative fixtures: similar code with different exception contracts, units, safety checks, side effects, timing or domain permissions is **not** merged; repeated text across legitimately separate repo-owned policy boundaries remains separate.
- One real, *authorised* high-value duplicate pair is consolidated on a feature branch. All callers are migrated or wrapped; targeted unit/contract/property/integration tests and relevant full CI pass before and after. Record measurable duplication/maintenance reduction, remaining differences and rollback.
- Detection is reproducible and explainable: candidate pairs include exact file/symbol/commit references, comparison evidence, risk and reject reasons. A reviewer can independently falsify a proposed equivalence.
- The unchanged second run emits no duplicate task; fresh edits invalidate the existing candidate. Idle compute overhead is bounded and the routine yields to live work.
- No uncontrolled automatic mass refactor, unreviewed deletion, hidden cross-repo coupling or changes to credentials, research claims or regulated/safety boundaries.
- Count the task as shipped only after the detector is integrated in the actual governed steward lifecycle and the consolidation pilot has passed real code review and repo acceptance; a task card or simulated finding is not completion.

## Relationship to adjacent work

- **Dead-code/note hygiene task** identifies things to retire and notes to mark as historical. This task finds *multiple live implementations* of the same responsibility and tests whether they should have one owner. Share the same steward inventory, deduplication, candidate records and execution pipeline, not duplicate infrastructure.
- **Steward PR #203** establishes inspection and governed handoff. If that PR is still unmerged, do not create independent orchestration here; either integrate after it lands or deliver only scoped deterministic analysis with explicit dependency status.
- **Repository ownership trajectory** is a hard boundary: shared execution lives in Odysseus; PhD and personal-domain semantics are retained by their own authority.

## Basis

- [Existing continuous-estate-steward design](https://github.com/tyecam1/odysseus/blob/dev/docs/future-work/continuous-estate-steward.md): duplicate-capability discovery and provenance-preserving convergence are already intended.
- [Repository ownership policy](https://github.com/tyecam1/odysseus/blob/dev/docs/aoteru-repository-ownership-trajectory.md): one shared implementation where semantics genuinely overlap, separate domain policies otherwise.
- Operator request dated 2026-10-31: an explicit duplicate-abstraction convergence routine rather than a one-time code tidy-up.

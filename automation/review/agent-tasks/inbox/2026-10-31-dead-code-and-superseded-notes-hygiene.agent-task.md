---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-31-dead-code-and-superseded-notes-hygiene
title: "Incremental dead-code and superseded-note hygiene"
status: inbox
priority: medium
task_type: implementation
created_by: user-directed
created_at: 2026-10-31T10:21:00+00:00
updated_at: 2026-10-31T10:21:00+00:00
executor: ""
execution_mode: review-first
architecture: single-plus-verifier
architecture_rationale: "Add one specialised detector and bounded governed cleanup path to the existing Odysseus estate steward. Reuse its inventory, scheduling, task admission, repo ownership, preflight, lease, and verification. No second maintenance daemon."
single_agent_baseline: "Read-only incremental scan of changed tracked code and Markdown, structural reachability and reference checks, one candidate per confirmed issue, reviewable smallest-scope patch for authorised fixes."
execution_host: compute-box
context_budget: medium
coordination_reason: "Code deletion and note lifecycle changes have cross-reference and research-provenance risk; separate detection from approval and implementation."
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
  - "Open PR #203: Kurisu repository stewardship; candidate, not yet merged at task creation"
  - "obsidian-PhD issue #371 and #373: historical retention/hygiene guidance, not shared execution authority"
outputs:
  - reusable incremental dead-code and note-lifecycle detector integrated into existing steward
  - deduplicated evidence-backed findings and bounded proposed cleanup diffs in existing task/review surfaces
  - regression fixtures for live, unreachable and dynamic code, and active versus superseded research notes
  - validated single-repo pilot with before/after references and rollback evidence
result_path: ""
review_report_path: ""
handoff_model: ""
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "New operator request 2026-10-31. Admission only; shipping-first AGENTS.md policy governs execution priority. Implement as a specialised capability underneath PR #203's steward if that work is admitted; do not duplicate its discovery scheduler or queue. Canonical domain note retention remains decided in the owning repository."
---

# Dead-code and superseded-note hygiene

## Purpose

Maintain a smaller, navigable and verifiably live code and note surface across **registered, authorised** repositories, without destroying useful history. This is a specific *detect -> verify -> propose -> authorised cleanup* capability of the existing Odysseus estate steward, **not** an independent background worker or a PhD-vault controller.

## Workflow

1. **Reconcile live ownership and overlaps.** Inspect the current `dev` code, estate registry, existing scanners, open maintenance tasks/PRs and pending [steward PR #203](https://github.com/tyecam1/odysseus/pull/203). Do not start implementing a second scheduler or scraper. Preserve the 2026-10-17 shipping-first priority: this remains inbox unless authorised to advance.
2. **Incremental discovery.** Prefer changed Git commits, dependency/build entry points, import/call graphs, references, task/manifest links, Markdown links and frontmatter. Exclude ignored/generated outputs unless they are incorrectly tracked. Use deterministic checks before a model review. Maintain only compact checkpoints/findings through the existing steward state.
3. **Dead-code candidates.** Find unreachable or unused functions, modules, scripts, old flags, abandoned adapters and obsolete tests/configs. Distinguish **proven unused** from **possibly unused**. Account for dynamic imports, reflection, entry points, CLI invocations, plugins, ROS nodes/launch files, scheduled jobs, external integrations, persisted schemas, public APIs and test-only/compatibility use. A static search alone never proves deadness.
4. **Superseded-note candidates.** Detect `supersedes`/status chains, duplicate titles, conflicting current guidance, orphaned links, renamed files and superseded drafts. Classify as `current`, `historical-provenance`, `superseded-with-successor`, `duplicate`, `orphaned` or `uncertain`. The preferred action is usually an explicit successor pointer and removal from active navigation, **not deletion**. Keep citation/source identity, dated decisions, experiments, evidence, annotations, research claims, task histories and audit trails intact. Only the domain owner decides canonical content changes.
5. **Deduplicate and assess.** Each proposed fix must cite repo/commit, exact files/lines, reachability or successor evidence, inbound and outbound dependencies, confidence, counterevidence, benefit, scope owner and whether human approval is required. Repeated unchanged scans must update an existing finding, not create duplicate queue items.
6. **Governed remediation.** Only after repository-specific authorisation, preflight, appropriate write lease and verification, prepare the **smallest coherent PR**. Remove proven dead code, update remaining imports/tests/docs and repair references; for notes, retain valuable provenance and use safe moves/link stubs/metadata corrections only when accepted by that repo's policies. Never silently rewrite the history of a superseded scientific position.
7. **Cadence and stop.** Reuse the existing steward's incremental/idle run lifecycle; no full rescans of unchanged repositories, no new timer. Skip cleanup if it competes with accepted shipping work or an experiment. No findings is a valid result. Prefer a single verified patch over mass tidy-up.

## Risk gates

- No unattended permanent deletion of research data, raw notes, citations, Zotero assets, experiment evidence, active schemas or external/public interfaces.
- A file may have no *local* references but remain an external entry point. Require negative dependency checks and a rollback plan before removal.
- Explicitly preserve original claims and correction history: `superseded` means no longer current, not false or disposable.
- Cross-repo discovery can be shared; write permission and content authority cannot. For PhD-specific changes, hand off to `tyecam1/obsidian-PhD` rather than write a parallel task there. For Misumi/personal changes, use its own owner.
- Failed proof or unresolved owner conflict => report `uncertain`, do not delete. All modifications remain in a reviewable branch/PR until existing acceptance gates pass.

## Acceptance tests

- A genuinely unreachable module/flag and an obsolete linked note produce actionable findings with source evidence; a dynamic plugin/CLI entry point and a historically superseded but cited note are **not** deleted.
- A pilot removes at least one *verified* dead-code candidate after authorisation, with references/tests/behaviour preserved and rollback available; note pilot demonstrates successor links and link integrity without erasing historical provenance.
- A second scan on unchanged inputs produces no duplicate work; changed source invalidates stale findings; inaccessible repos report `unknown`.
- Check code tests, import/build/entry-point smoke tests, note link/frontmatter checks and relevant domain-specific validation before and after. Record exact tests, commits, approved diff and remaining uncertainty.
- No new scheduler, task authority, duplicate index or unapproved canonical write. Actual operational scheduling/eligibility and successful pilot are verified before marking shipped.

## Basis

- [Odysseus estate steward contract](https://github.com/tyecam1/odysseus/blob/dev/docs/future-work/continuous-estate-steward.md): existing mechanism for incremental provenance-preserving hygiene and bounded approval.
- [Odysseus ownership trajectory](https://github.com/tyecam1/odysseus/blob/dev/docs/aoteru-repository-ownership-trajectory.md): shared execution versus repository-specific content authority.
- [PhD repository hygiene issue #371](https://github.com/tyecam1/obsidian-PhD/issues/371): previous retention and manifest controls; historical precedent only, not an instruction to revive its old queue.

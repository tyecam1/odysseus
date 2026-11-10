---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-28-kurisu-repository-steward-hygiene-handoff
title: "Kurisu repository stewardship: hygiene discovery and Lelouch execution handoff"
status: inbox
priority: high
task_type: orchestration
created_by: user-directed
created_at: 2026-10-28T17:31:00+00:00
updated_at: 2026-10-28T17:31:00+00:00
executor: ""
execution_mode: review-first
architecture: single-plus-verifier
architecture_rationale: "Reuse Odysseus's proposed continuous estate steward and existing routing, scheduling, task ownership, leases and execution lifecycle. Kurisu is the diagnostic interface, Lelouch the execution interface; neither persona is a second runtime authority."
single_agent_baseline: "One read-only steward can incrementally inspect registered repositories, verify concrete hygiene defects, deduplicate candidates against canonical tasks and PRs, and hand a bounded finding to the existing Lelouch/operator task path."
execution_host: compute-box
context_budget: medium
coordination_reason: "Discovery must be separated from execution/acceptance without multiplying model passes or creating redundant agent infrastructure."
requires_remote_compute: true
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
  - config/**
  - docs/**
  - routes/**
  - scripts/**
  - src/**
  - tests/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
inputs:
  - AGENTS.md
  - docs/future-work/continuous-estate-steward.md
  - docs/aoteru-model-host-routing-contract.md
  - automation/review/agent-tasks/README.md
  - automation/review/agent-tasks/inbox/2026-09-19-capability-routed-parallel-project-orchestration.agent-task.md
  - automation/review/agent-tasks/inbox/2026-09-28-persistent-blocked-route-rerouting-long-horizon.agent-task.md
  - automation/review/agent-tasks/inbox/2026-10-01-provider-quota-health-in-routing-preflight.agent-task.md
  - automation/review/agent-tasks/ready/2026-10-02-misumi-persona-growth-background-collaboration.agent-task.md
  - tyecam1/misumi@main:agents/core/operator-lelouch-lamperouge.md
  - tyecam1/misumi@main:docs/core/agent-personality-registry-v0.2.md
  - tyecam1/misumi@main:config/personas.yaml
  - tyecam1/misumi@main:docs/operations/operator-heartbeat-interface.md
outputs:
  - source-linked cross-repository hygiene findings, prioritised and deduplicated
  - verified candidate handoffs into existing repository-specific task intake
  - Kurisu inspection and Lelouch execution status via the existing Aoteru/Misumi operator surface
  - incremental scan, recovery, safety and UI regression evidence
result_path: ""
review_report_path: ""
handoff_model: ""
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "User requests a repository-analysis persona which generates work for Lelouch, beginning with hygiene and file organisation. Keep this in inbox subject to the existing 2026-10-17 shipping-first priority. Do not begin concurrent changes to persona canon or create a second queue/scheduler."
---

# Kurisu repository stewardship: hygiene discovery and Lelouch handoff

## Objective

Assign **Makise Kurisu** the responsibility for finding and *verifying* repository maintenance tasks across the registered estate, starting with hygiene, file management and organisation. Kurisu produces evidence-backed, bounded candidates. **Lelouch** takes admitted work through Odysseus's *existing* prioritisation, routing, execution, verification and delivery mechanisms.

**Aoteru remains the single human entry point.** Persona identities are interaction and responsibility projections, never additional code, repository, approval or model-selection authority. Erwin is consulted for conflicting priorities or high-cost decisions; L may independently check ambiguous recurrent defects when justified.

## Reuse before adding

Start from live repository state, not previous conversation descriptions. Audit the actual continuous-estate-steward implementation against `docs/future-work/continuous-estate-steward.md`, existing scheduled/task/event loops, repo and host registries, ParkLease, EstateExecution, available local model qualifications, current task queues and the Misumi `OPERATOR` HUD.

Extend the existing owner only. **Do not build another crawler, scheduler, queue, task ledger, memory system, persona router or executor.** Reconcile open overlapping tasks/PRs before any code or new task candidate.

## Phase 1: first read-only hygiene pass

Inspect registered reachable repositories using read-only scopes. Initial candidates include `odysseus`, `misumi`, `obsidian-PhD` and `s2-e1-ros2-measurement-spine`, **but only if current estate configuration confirms their identities and access**. Record any missing or inaccessible source as unknown, not clean.

Inspect, in priority order:

1. Misplaced backend/runtime files and cross-repository authority leakage; obsolete paths left by boundary migrations.
2. Broken internal links, missing references and case-sensitive path drift.
3. Duplicate, superseded, orphaned or contradictory files, prompts, configs, skills, tasks and outdated instructions.
4. Inconsistent Markdown frontmatter, schema, task status, naming or folder structure.
5. Unnecessary generated files, binary/cache artefacts, redundant bulk data and unsafe repository hygiene (including tracked secrets indicators, reported safely without exposing secret material).
6. File-management changes with demonstrable usability, maintainability or correctness benefit.

Do not reclassify intentional historical provenance, research evidence, dataset inputs, raw notes/transcripts or source material as disposable. No cosmetic refactoring without measured benefit. No aggressive reorganisation, file moves or deletion in the discovery pass.

Use deterministic checks before model inference. Classify each finding as `verified-defect`, `proposed-improvement`, `intentional-history` or `unknown`, with a confidence and counterevidence note where relevant. Verify against source paths and current commit/branch, and search existing open tasks, PRs and fixes before proposing work.

## Phase 2: candidate -> Lelouch handoff

Kurisu produces compact candidates:

`finding_id | repository | source_commit/path | symptom | observed evidence | classification | severity | smallest fix | benefit | risk | existing-task/PR match | canonical owner | validation | approval need`.

One candidate per *materially distinct* defect or coherent fix batch; deduplicate by repository + affected identity/path + defect family + relevant state. Repeat scans against unchanged inputs must not generate duplicate tasks. Update prior findings when evidence changes.

Handoff must go to the **existing canonical task mechanism owned by the relevant repository**. The cross-repository coordination service remains Odysseus-owned; PhD research work stays in `obsidian-PhD`; personal/household work stays in `misumi`. Lelouch may triage and track work but does not acquire permission merely by receiving it. The existing readiness, priority, preflight, capability qualification, lease, verification and approval checks apply to every implementation. Preserve the 2026-10-17 shipping-first backlog priority. A reported finding is not by itself a `ready` task, and a draft/PR is not `shipped`.

## Phase 3: low-overhead recurring stewardship

Integrate with existing Odysseus scheduling and persisted run state. Prefer incremental checks driven by changed commits, changed runtime dependencies or an economical idle cadence. Store last examined refs, concise evidence pointers and deduplication state in the existing operational store, not in Misumi household canon or the PhD vault.

Use deterministic tools or the cheapest *measured-qualified* local model. Yield to interactive jobs and lab experiments. Do not constantly call a premium model or rerun unchanged full-repository scans. Wait efficiently when the estate is unchanged or sources are blocked; resume after restarts and available-capability changes using existing lifecycle/recovery semantics.

## Persona interaction

The user should be able to ask Aoteru, "What did Kurisu find in my repositories?" and "What tasks has Lelouch taken from Kurisu?" and receive real, source-linked status. Expose Kurisu's candidate findings and Lelouch's admitted/executing/verified work through the **existing** Misumi interaction and Lelouch `OPERATOR` surface. No fake ongoing activity, hidden duplicate dashboards or credential exposure. Any persona canon or routing change beyond the current ratified scope requires its existing ratification path.

## Safety boundaries

- Default discovery is **read-only**; no direct file delete, rename, merge, restructuring or write.
- No uncontrolled scanning of drives, private data, credentials or repositories absent from the approved registry.
- Every actual repository mutation requires the existing preflight, permitted scope, ParkLease, independent verification where required and current user/domain authority.
- Preserve research validity, traceability, privacy, raw evidence and household canon.
- No automatic scientific claim acceptance, privileged action, irreversible cleanup or silent task promotion.

## Acceptance / verification

1. A real read-only pilot inspects at least one reachable registered repository and returns source-linked, independently checked findings **or a truthful evidenced clean/unknown outcome**.
2. A second unchanged scan creates zero duplicate work items. Existing PRs/tasks are recognised.
3. One verified, bounded finding is surfaced as Kurisu's observation, passed through existing work-item authority, and visible to Lelouch without silently becoming `ready`.
4. A low-risk *separately authorised* hygiene fix follows the actual task -> preflight -> lease -> worker -> tests -> review -> delivered-status path; rejected writes leave targets unchanged.
5. Tests demonstrate repository ownership separation, provenance preservation, unsupported access handling, restart recovery, deduplication, stale evidence invalidation and no unapproved mutation.
6. Background scanning demonstrates lower rework/compute than repeated whole-repository model scans and yields to interactive/experiment resource priority.
7. Aoteru/Lelouch interface reports truthful findings, handoffs, blocked conditions and verified completions from actual Odysseus state.
8. Existing task/capability evidence is updated without duplicating stewardship or executor authority.

## Execution instructions

First produce a **smallest-affected-scope duplicate-risk audit** against live code and open tasks, then implement **one vertical slice**: read-only hygiene check -> verified candidate -> governed Lelouch handoff -> truthful UI status. Do not launch a broad rewrite or a permanent background daemon before this has been tested. Run focused tests and relevant regression suites; independently review any expanded routing/write/approval surface. Record what is implemented, actually deployed, blocked and merely proposed.

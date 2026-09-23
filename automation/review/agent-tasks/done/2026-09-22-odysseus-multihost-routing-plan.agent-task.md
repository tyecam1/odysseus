---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-22-odysseus-multihost-routing-plan
title: "Plan truthful Odysseus multihost execution for lab and home"
status: done
migrated_from_repo: tyecam1/obsidian-PhD
migrated_from_pr: 565
migration_note: "Task executed before repository-ownership migration; retained here as backend provenance."
priority: high
task_type: architecture-plan
created_by: gpt-5.6-sol
created_at: 2026-09-22T11:00:00+01:00
updated_at: 2026-09-22T11:00:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single
architecture_rationale: "This is one control-plane/runtime contract defect. Use Opus to remove architectural ambiguity and produce a bounded Sonnet implementation plan; do not split architecture ownership across agents."
single_agent_baseline: "One Opus planning pass should reconstruct live state, identify the smallest coherent execution-worker seam, and leave Sonnet a file/function-level implementation sequence."
execution_host: compute-box
context_budget: high
coordination_reason: "Architecture first, implementation second. Opus owns diagnosis and guardrails; Sonnet should later perform bounded mechanical implementation without re-solving the architecture."
requires_remote_compute: true
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
  - docs/aoteru-multihost-execution-implementation-plan.md
denied_paths:
  - src/**
  - routes/**
  - companion/**
  - scripts/**
  - config/**
  - tests/**
  - migrations/**
inputs:
  - docs/aoteru-model-host-routing-contract.md
  - docs/aoteru-p13-laptop-reentry-evidence.md
  - docs/aoteru-operating-handbook.md
  - docs/aoteru-interface-pc-deployment.md
  - config/estate.yaml
  - config/models.yaml
  - config/routing.yaml
  - config/repositories.yaml
  - src/estate_router.py
  - routes/estate_routing_routes.py
  - companion/laptop_client/aoteru.py
  - scripts/agent
  - scripts/windows/odysseus-host.ps1
  - relevant ParkLease and EstateExecution code/tests
  - open PRs #39 and #40
  - branch chatgpt/model-effort-routing-20260910
  - automation/review/agent-tasks/ready/2026-09-03-odysseus-cross-device-delegation-lifecycle-hardening.agent-task.md
outputs:
  - docs/aoteru-multihost-execution-implementation-plan.md
  - a compact Sonnet implementation prompt embedded at the end of that plan
result_path: docs/aoteru-multihost-execution-implementation-plan.md
review_report_path: ""
handoff_model: claude_sonnet
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Planning only. Do not implement production changes, merge branches, flip home verified=true, or adopt model-effort sophistication before actual host placement is truthful."
---

# Plan truthful Odysseus multihost execution for lab and home

## Purpose

Make the existing Aoteru/Odysseus model-host routing contract implementable and truthful across the lab Linux PC and home Windows PC.

This task is **architecture and implementation planning only**. Use Opus to spend reasoning on live-state reconstruction, failure semantics, interface boundaries and guardrails. The resulting plan must be sufficiently explicit that a token-efficient Sonnet agent can implement it largely mechanically.

Desired execution chain:

`Aoteru -> one Odysseus control plane -> route(host, capability) -> selected host worker -> execution -> EstateExecution/result -> central telemetry`

Central invariant:

> `route.host` must identify the machine that physically executed the task.

Do not make the system merely look multihost by changing eligibility metadata.

## Start from live state

Work from the live repository and runtime, not this task's potentially stale description.

1. Fetch/prune remotes and identify current `origin/dev`, current working-tree state, open relevant PRs and relevant branches.
2. Do not disturb an existing dirty worktree. If a writable planning checkout is needed, create a separate worktree/branch from current `origin/dev`.
3. Inspect the listed inputs plus any directly relevant implementation/tests discovered from them.
4. Inspect the existing September 3 cross-device lifecycle task in `tyecam1/obsidian-PhD`.
5. Use read-only runtime checks where useful, including Tailscale/host/service/model state. Do not mutate host configuration as part of planning.
6. Distinguish functionality already implemented but unmerged, stale documentation, genuine runtime gaps, and adjacent work that should remain deferred.

## Questions that must be answered

### 1. Is host routing currently only metadata?

Verify exactly whether:

- `resolve_route()` selects a host;
- local inference still executes against backend-local `127.0.0.1:11434`;
- paid/Codex execution is launched on the backend host;
- repository paths are resolved on the backend host;
- governed writes require the selected host to equal the current backend host.

Identify exact files/functions and the smallest seam through which selected-host execution can become real.

### 2. Is model capability host-specific enough?

Determine whether current model bindings are effectively global/lab-derived.

Define the minimum host-scoped inventory and qualification semantics required to prevent routing a capability/model to a host where it is absent, stale or unqualified.

Do not design a general scheduler.

### 3. Is `verified` overloaded?

The home machine previously had identity and network reachability demonstrated while `verified:false` was retained to prevent premature worker eligibility.

Determine the smallest truthful state model. Consider, but do not blindly adopt:

- `identity_verified`
- `reachable` / `healthy`
- `worker_qualified`
- per-host capability/model qualification

Static identity, live health and qualification evidence must not be conflated where they have different meanings.

Do **not** solve this by flipping home to `verified:true`.

### 4. What should the home service role be?

Inspect the evidence for the existing older home Odysseus/Misumi service.

Unless live evidence demonstrates otherwise, preserve it as a household adapter. It must not become a second routing authority, ParkLease authority, lifecycle database, or competing control plane.

Plan a thin execution-worker role instead.

### 5. How should cross-device lifecycle work integrate?

Reconcile this plan with the existing September 3 lifecycle-hardening task.

The design should make dispatch and observation distinct, expose an execution ID, support bounded status/wait, and avoid redispatch as polling.

Reuse `EstateExecution`; do not introduce another queue or lifecycle store.

## Hard architectural guardrails

1. **One control plane.** Odysseus owns routing, ParkLease, EstateExecution and central routing/execution telemetry.
2. **Workers are not controllers.** Lab and home execute selected work; they do not independently decide global routing.
3. **Truthful placement.** `route.host == actual execution host`.
4. **Fail closed.** Remote execution failure must never silently fall back to backend-local execution while preserving the remote host in telemetry.
5. **Per-host capability truth.** A model/capability is routable only where current inventory and qualification support it.
6. **Separate eligibility concepts.** Identity, health/reachability and worker qualification must not be overloaded into one boolean if the live system needs distinct semantics.
7. **ParkLease remains the only governed write authority.**
8. **EstateExecution remains the durable implementation-execution lifecycle authority.**
9. **One logical worker contract.** Linux lab and Windows home expose the same logical interface; OS differences stay beneath it.
10. **Preserve the existing household/Misumi service** unless migration is explicitly justified by live evidence.
11. **No competing orchestration.** Do not add another scheduler, queue, lease database or task-state authority.
12. **Minimal change.** Extend existing abstractions and transports where adequate.

## Explicitly defer

Unless strictly required to make placement truthful, do not solve:

- adaptive host scoring;
- model-effort optimisation;
- GLM integration;
- swarm/multi-agent scheduling;
- dynamic load balancing;
- UI polish;
- broad configuration rewrites;
- unrelated refactors.

Inspect `chatgpt/model-effort-routing-20260910` for useful prior work, but do not merge or reproduce its sophistication until host placement itself is correct.

## Required plan document

Create only:

`docs/aoteru-multihost-execution-implementation-plan.md`

The document must contain:

### A. Verified diagnosis

For each material defect/state mismatch: current behaviour, exact file/function responsible, evidence from live code/runtime, contract consequence, and whether an existing branch/PR already addresses it. Separate verified facts from inference.

### B. Minimal target execution flow

Specify:

`TaskEnvelope -> route -> selected host -> worker dispatch -> execution -> status/result -> EstateExecution -> caller`

State which component owns each responsibility.

### C. Worker protocol

Define the smallest control-plane-to-worker contract needed to report health, model/capability inventory and qualification, repository availability, execute read-only work, execute ParkLease-governed write work, and expose execution status/result/failure.

Prefer existing HTTP/SSH/service infrastructure if it already provides adequate semantics. Specify request/response fields sufficiently for Sonnet implementation.

### D. State model

Define static host identity/configuration, live health/reachability, worker qualification, model/capability availability and qualification, repository availability, and execution lifecycle state. State what belongs in config versus runtime/telemetry.

### E. Ordered file/function patch plan

For each numbered implementation stage give exact files, functions/classes/endpoints to modify or add, required behaviour, invariants, tests, and dependencies. Sonnet should not need to make architecture decisions.

### F. Non-goals

Give a concrete do-not-touch list sufficient to prevent scope drift.

### G. Test matrix

Define deterministic unit/integration coverage for explicit lab placement, explicit home placement, auto placement, unavailable/stale worker, model on only one host, missing repo, worker failure, truthful telemetry, remote read-only repo work, ParkLease-gated write, worker loss, status without redispatch, and prevention of backend-local fallback.

Separate unit, integration and live acceptance tests.

### H. Live acceptance procedure

Unit tests are insufficient. Define one bounded real task for lab and one for home, with evidence proving physical execution on the selected host rather than route metadata alone. Include expected provenance and bounded failure handling.

### I. Migration/order strategy

Keep the system usable between stages. Prefer:

1. truthful state semantics;
2. worker contract;
3. lab/local path through worker contract;
4. Windows/home worker adapter;
5. route execution through selected worker;
6. EstateExecution/status integration;
7. host-specific capability qualification;
8. live lab/home proof;
9. compatibility cleanup.

Alter only if live architecture demonstrates a materially better minimal sequence.

### J. Sonnet handoff prompt

End the plan with a concise Sonnet prompt, ideally <=250 words, that tells Sonnet to use the plan as architecture authority, start from current `dev`, implement sequentially, test each stage, stop if live state invalidates an assumption, make no silent architectural substitution, avoid scope expansion, keep commits reviewable, and leave infrastructure failures explicit.

## Planning acceptance criteria

Complete only when:

- the placement defect is traced to exact live code paths;
- one control plane and thin workers are preserved;
- `route.host == actual execution host` is enforceable by design;
- home qualification is truthful without abusing one `verified` boolean;
- host-specific model/repo truth is addressed;
- ParkLease and EstateExecution remain authoritative;
- the existing household service is protected from role expansion;
- lifecycle observation is reconciled with the September 3 task;
- Sonnet has an ordered file/function-level sequence and test matrix;
- the plan includes real lab + home physical-execution acceptance;
- no production code/config has been changed.

## Completion and remote handoff

Commit only the plan document on a dedicated planning branch based on current `origin/dev`, push it to `tyecam1/odysseus`, and report:

- verified root causes;
- chosen minimal architecture;
- implementation stage count;
- unresolved decisions/blockers;
- plan path;
- branch and commit SHA;
- compact Sonnet initialisation prompt.

Do not merge the planning branch and do not begin implementation.

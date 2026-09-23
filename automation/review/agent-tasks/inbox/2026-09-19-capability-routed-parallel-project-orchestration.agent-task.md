---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-19-capability-routed-parallel-project-orchestration
title: "Implement capability-routed parallel project orchestration"
status: inbox
priority: high
task_type: orchestration
created_by: chatgpt
created_at: 2026-09-19T14:24:00+01:00
executor: codex_subscription
execution_mode: implementation
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
migrated_from_repo: tyecam1/obsidian-PhD
migration_note: "Ownership migrated to Odysseus. Treat references to obsidian-PhD automation paths as historical inputs until capability-path convergence is complete."
branch: codex/capability-routed-parallel-orchestration-20260919
allowed_paths:
  - automation/review/**
  - automation/docs/**
  - automation/config/**
  - automation/prompts/**
  - Scripts/automation/**
  - .agents/skills/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
  - 04-supportDesign/**
  - 10-inbox/**
  - 11-projects/**
  - 12-log/**
  - "**/*.pdf"
inputs:
  - automation/AGENTS.md
  - automation/docs/agent-architecture-selection-gate.md
  - automation/docs/agent-task-frontmatter-schema.md
  - automation/docs/work-item-audit.md
  - automation/config/model_execution_policy.yaml
  - automation/config/agent_routing.yaml
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
outputs:
  - automation/docs/capability-routed-parallel-orchestration.md
  - automation/review/architecture/2026-09-19-capability-routed-parallel-orchestration-design.md
  - automation/review/routine-reports/capability-routing/2026-09-19-baseline-and-evaluation.md
result_path: automation/review/routine-reports/capability-routing/2026-09-19-baseline-and-evaluation.md
review_report_path: automation/review/routine-reports/capability-routing/2026-09-19-baseline-and-evaluation.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
architecture: single-plus-verifier
architecture_rationale: "Build the orchestration capability with one implementation owner and independent verification. The runtime being built may dispatch independent project substreams concurrently, but implementation of the scheduler itself shares state and should not be developed as a swarm."
single_agent_baseline: "Existing contracts support manual architecture selection and capability-aware routing references, but no local runtime currently decomposes project work, selects models from measured strengths, dispatches independent nodes concurrently, and reconciles results."
execution_host: laptop
context_budget: "Use bounded pointers to live routing, capability, work-item and evaluation contracts. Do not load project corpora unless required by a test fixture."
coordination_reason: "Independent verification is required because this changes execution routing and concurrency semantics with a high blast radius."
notes: "Implement by extending the existing routing/work-item architecture. Do not create a competing task system or hard-code permanent model personalities. Cross-repository runtime changes must be emitted as bounded child packets for the authoritative repository rather than silently duplicated here."
---

# Implement capability-routed parallel project orchestration

## Goal

Create a project-level orchestration capability that can decompose eligible work into independent sub-tasks, assign each sub-task to the currently best-suited available model or deterministic lane based on measured strengths and constraints, execute independent nodes concurrently, and reconcile the outputs into one controlled project state.

The system must increase useful throughput without weakening research authority, provenance, verification, or repository isolation.

## Core design principle

Model assignment must be evidence-based and dynamic, not a static table of assumed model personalities.

For each candidate execution lane, maintain a capability profile derived from actual local evaluation and run history. Routing should consider, at minimum:

- task family and required reasoning type;
- measured output quality and verification pass rate on comparable tasks;
- tool and repository access;
- context-window and context-retention requirements;
- latency and throughput;
- cost, subscription quota and remaining allowance where inspectable;
- reliability, timeout and retry behaviour;
- ability to operate read-only versus isolated-write;
- model availability at dispatch time;
- independence from the model that produced work requiring verification.

Do not encode a permanent rule such as "model X always writes" or "model Y always researches". Named models are candidates whose suitability changes with evidence, availability and task type.

## Required behaviour

### 1. Reconstruct live authority before implementation

Inspect the current repository state and the cross-repository runtime authority referenced by the live contracts. Reuse:

- the architecture-selection gate;
- agent-task schema v2;
- work-item audit and readiness semantics;
- model execution policy;
- agent routing contract;
- capability ledger;
- existing claim/lease, worktree, dispatch, observability and evaluation machinery where present.

If the authoritative dispatcher belongs in another repository, do not clone its business logic into this repository. Produce a bounded child implementation packet for that repository and keep only the PhD-specific adapter/contracts here.

### 2. Introduce a task-requirement model

Represent a routable node with explicit machine-readable requirements, including:

- task type;
- required tools and hosts;
- required inputs;
- expected output contract;
- write scope;
- dependencies;
- judgement intensity;
- research-authorship flag;
- verification requirement;
- context requirement;
- estimated token/runtime budget;
- reversibility/blast radius;
- parallel-safety declaration.

The schema must fail closed when requirements are unknown or contradictory.

### 3. Build an empirical model/lane capability registry

Add a machine-readable registry or derived view that records capability evidence by task family. It must distinguish:

- configured availability;
- qualified capability;
- observed performance;
- stale/insufficient evidence;
- disqualified or temporarily unavailable lanes.

Performance records should include enough provenance to answer why a model received a task. Do not allow self-reported model confidence to update capability scores without external verification.

### 4. Implement capability-fit routing

Given one routable node, rank eligible lanes using an explainable scoring or rule system. Eligibility gates precede scoring.

The router must:

1. remove lanes that cannot satisfy authority, host, tool, write-scope or verification constraints;
2. prefer deterministic execution when it fully satisfies the task;
3. compare remaining lanes using empirical task-family evidence;
4. account for quota/cost/latency only after minimum capability is met;
5. preserve an independent verifier where required;
6. emit the selected lane plus rejected alternatives and reasons;
7. fail closed or escalate to the operator when evidence is insufficient for a consequential decision.

A dry-run must expose the route without executing it.

### 5. Decompose projects into dependency-aware execution DAGs

Add a planner that can translate a project/work item into bounded nodes only where decomposition is justified by the architecture-selection gate.

Parallel execution is allowed only for nodes that:

- have satisfied prerequisites;
- operate on independent information streams or partitioned state;
- do not write the same files/records concurrently;
- have explicit output contracts;
- have a defined aggregation owner;
- can be independently verified.

Sequential chains remain sequential. "Large task" is not itself a reason to parallelise.

### 6. Add safe fan-out/fan-in execution

For eligible nodes, support bounded concurrent dispatch with:

- configurable maximum concurrency;
- per-model/per-provider concurrency limits;
- task claims/leases to prevent duplicate execution;
- isolated branches/worktrees or read-only execution as appropriate;
- cancellation and timeout handling;
- retry policy that does not silently switch to a weaker lane below capability requirements;
- dependency barriers;
- deterministic capture of stdout/result artifacts and execution metadata;
- resume/recovery after interrupted orchestrator runs.

No worker may merge its own output into shared project state.

### 7. Reconcile through one state owner

After parallel nodes finish, one aggregation step must:

- verify each node against its output contract;
- reject incomplete or conflicting outputs;
- compare overlapping claims rather than silently blending them;
- preserve provenance to the producing model/run;
- surface disagreements;
- request targeted rework when cheaper than full reruns;
- construct a single proposed state transition.

Research synthesis, interpretation, authorship and normative methodological decisions remain human-owned under the current research authority contract.

### 8. Separate execution from verification

Where practical, verification must be performed by a different model/lane from the producer, or deterministically where sufficient.

Prevent:
- a worker marking its own work accepted;
- parallel agents mutually reinforcing the same unsupported claim;
- one model's result contaminating an allegedly independent verification context.

### 9. Learn from outcomes

Extend the existing model/operating-contract evaluation work rather than creating a parallel benchmark system.

For each completed node, log at least:

- task family;
- selected lane and alternatives considered;
- success/failure;
- verification result;
- retries;
- wall-clock duration;
- token/cost/quota data where available;
- human correction burden;
- conflict/rework events.

Use these records to update routing evidence conservatively. Keep raw observations distinct from derived capability estimates.

### 10. Provide operator-facing controls

Provide a minimal interface such as:

```
route <task> --dry-run
orchestrate <project-or-work-item> --dry-run
orchestrate <project-or-work-item> --max-concurrency N
resume <run-id>
status <run-id>
```

Exact command names may follow existing CLI conventions. The operator must be able to see:

- DAG and dependency state;
- which nodes can run now;
- selected model/lane and reason;
- current claims;
- verification status;
- blocked decisions;
- cost/quota signal where available;
- final proposed reconciliation.

### 11. Benchmark before enabling broad parallelism

Create a reproducible evaluation using representative task families already present in the estate.

At minimum compare:

- current single-owner baseline;
- capability-routed single worker;
- capability-routed single + independent verifier;
- coordinated parallel execution on genuinely independent nodes.

Measure quality/verification pass rate, elapsed time, execution cost or quota consumption, retries, conflicts and human correction burden.

Do not enable `parallel-n` as a general default. Promote concurrency only where the benchmark demonstrates a material benefit for that task family without degrading verification quality.

### 12. Capability truth and documentation

If implementation changes real capabilities:

- update `automation/docs/capability_manifest.json`;
- regenerate `automation/docs/current-capabilities.md` via the existing capability-ledger command;
- document the runtime and its failure modes;
- add tests for routing, dependency scheduling, concurrency isolation, recovery and fail-closed behaviour.

## Acceptance criteria

- A single project/work item can be represented as a dependency DAG with explicit node contracts.
- At least two independent eligible nodes can execute concurrently without shared mutable writes.
- Different eligible nodes can be routed to different available model/deterministic lanes based on recorded capability evidence.
- Route decisions are explainable and reproducible from recorded inputs.
- Unavailable, unqualified or authority-ineligible models are excluded before scoring.
- Parallelism cannot bypass the existing architecture gate, research-authority boundaries or verification routes.
- A failed worker cannot corrupt the project state and can be retried or rerouted safely.
- The aggregator preserves disagreements and provenance instead of averaging outputs.
- Empirical run outcomes feed a conservative capability-history record.
- A benchmark shows where parallel routing helps and where it does not.
- The implementation does not create a second task queue, second capability ledger or second cross-repository routing authority.
- Relevant tests and capability-truth checks pass.

## Non-goals

- Autonomous research authorship.
- Fully autonomous acceptance of scientific claims.
- Maximum possible agent count.
- Parallelising sequential work.
- Hard-coding provider/model reputations as permanent strengths.
- Letting cost or quota choose an under-qualified model.
- Concurrent edits to the same working files.
- Automatic PR merge or canonical research promotion.

## First execution step

Before writing code, produce the architecture design and duplicate-risk audit. Identify which parts belong in `obsidian-PhD` versus the authoritative cross-repository runtime, and enumerate the smallest implementation slices. If an equivalent scheduler/router already exists, extend it rather than building another.

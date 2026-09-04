---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-08-30-aoteru-cross-repo-agentic-work-portfolio-planner
title: "Build cross-repo agentic work reconnaissance and portfolio planning"
status: ready
priority: critical
task_type: bounded-runtime-convergence
created_by: chatgpt
created_at: 2026-08-30T14:05:00+01:00
executor: codex-cli
execution_mode: design-then-implementation
resource_profile: adaptive
risk_level: medium
approval_required: false
source_traceability_required: true
requires_local_model: false
requires_remote_compute: true
requires_web: false
repo: tyecam1/odysseus
branch: agent/cross-repo-agentic-work-portfolio-planner-20260830
inputs:
  - docs/aoteru-estate-execution-contract.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/aoteru-delegation-operationalisation.agent-task.md
  - config/repositories.yaml
  - config/estate.yaml
  - config/routing.yaml
  - config/models.yaml
  - src/estate_router.py
  - src/routing_evaluator.py
  - routes/estate_routing_routes.py
  - tyecam1/obsidian-PhD:automation/docs/central-operating-contract.md
  - tyecam1/obsidian-PhD:automation/docs/agent-task-frontmatter-schema.md
  - tyecam1/obsidian-PhD:automation/docs/verification-routing-policy.md
  - tyecam1/obsidian-PhD:automation/review/agent-tasks/**
  - tyecam1/misumi:AGENTS.md
  - tyecam1/misumi:agent-tasks/**
outputs:
  - one deterministic estate-wide open-work inventory over repo-owned agentic work surfaces
  - one thin on-demand agent skill for scan, status, plan and explain operations
  - one strict derived portfolio snapshot schema with source hashes and repo provenance
  - one strong-model completion-planning routine with bounded targeted context expansion
  - one deterministic portfolio-plan validator and parallelisation/conflict gate
  - one independent adversarial plan-review step with bounded repair
  - one twice-daily scheduled portfolio review using the existing Odysseus scheduler
  - action candidates suitable for the existing Odysseus dispatch/execution plane, never a second queue
  - telemetry and evaluation for coverage, plan churn, operator burden, cost and validated closure
  - tests proving heterogeneous repo adapters, authority preservation, prompt isolation, concurrency safety and stale-plan handling
---

# Cross-repo agentic work reconnaissance and portfolio planning

## Mission

Give Aoteru/Odysseus one estate-wide view of **all open agentically managed work**, regardless of which managed repository owns it, then convert that view into a bounded, adversarially reviewed completion plan that identifies what can progress autonomously, what can safely run in parallel, what is blocked, and what needs a human decision.

The system must reduce forgotten work and manual orchestration without creating another backlog, router, scheduler, approval system, or cross-repo authority layer.

Target:

```text
repo-owned work items
-> deterministic repo adapters
-> normalized read-only portfolio snapshot
-> deterministic actionability/dependency/conflict features
-> strong portfolio planner
-> deterministic plan validation
-> independent adversarial review
-> bounded repair if required
-> expiring derived completion plan
-> existing Odysseus routing/execution plane
-> verification/closure in each source repo
-> next snapshot
```

The primary optimisation target is **validated closure of useful work with low operator burden**, not raw task count, agent count, GPU utilization, or model-call volume.

## Findings that constrain the design

This task was written only after a cross-repository inspection and adversarial design review.

1. `obsidian-PhD` already owns a strict lifecycle under `automation/review/agent-tasks/**`; it must remain authoritative for PhD work.
2. `misumi` has a different live `agent-tasks/**` organisation including `inbox`, provider/host-oriented folders, `review`, `blocked-human`, and `done`. Do not force it into the PhD schema merely to make portfolio aggregation easier.
3. Odysseus already has repo, host, model, routing, scheduler, job, telemetry and lease authorities. This capability belongs in Odysseus but must reuse those owners.
4. The existing PhD `weekly-backlog-condensation` skill is intentionally single-repo and limited to a few priorities. It is not an estate-wide planner and should not be widened into one.
5. The existing Odysseus routing contract says workers receive bounded pointers and provider/model choice is runtime-derived. A portfolio planner must follow the same rule.
6. Cross-repo work formats are heterogeneous and may remain so. The common layer therefore needs adapters and a conservative common denominator, not a new universal task schema.

## Harsh adversarial review and resulting corrections

The following designs are explicitly rejected.

### Rejected: let GPT-5.6 Sol read every raw work-item file

Why this is bad:

- unnecessarily expensive on every sweep;
- causes unchanged work to consume paid context repeatedly;
- exposes the planner to prompt-like text inside task bodies;
- makes coverage and omission difficult to verify;
- encourages the model to reinterpret repo authority instead of reading structured state.

Correction:

- inventory and normalize deterministically first;
- hash every source item;
- send compact structured records to the planner;
- allow a second targeted-read pass only for specifically ambiguous items;
- treat all task body text as untrusted data, never as planner instructions.

### Rejected: create a central portfolio backlog

Why this is bad:

- duplicates source-repo task authority;
- creates synchronization and lifecycle drift;
- eventually makes Odysseus the accidental owner of PhD and Misumi semantics.

Correction:

- the portfolio is **derived and expiring**;
- source tasks remain where they already live;
- portfolio records contain pointers and hashes, not copied authoritative task bodies;
- no portfolio record may become a replacement work item.

### Rejected: let the planning model decide parallelism by intuition

Why this is bad:

- two apparently independent tasks may mutate the same repository or path;
- concurrent work can conflict with ParkLease state, experiments, CI or merge ordering;
- multi-agent execution can cost more while increasing reconciliation failures.

Correction:

- compute hard concurrency eligibility deterministically;
- the model may propose parallel waves only inside those hard bounds;
- shared or uncertain write scope means serial by default;
- independent read-only scopes may parallelize freely within resource limits;
- write work may parallelize only with isolated branches/worktrees, compatible leases, disjoint write scopes and defined merge/aggregation ordering;
- experiments retain priority over heavy background GPU work.

### Rejected: replan the whole estate with a strong model twice daily even when nothing changed

Why this is bad:

- burns tokens for zero new information;
- adds stochastic plan churn;
- can reshuffle valid running work for no reason.

Correction:

- the twice-daily scheduler always performs a deterministic scan;
- compute one material snapshot hash;
- when the snapshot is unchanged and the incumbent plan is still valid, record `plan_still_valid` and make no strong-model call;
- force a new strong plan only on material portfolio change, plan expiry, explicit operator request, or plan failure.

### Rejected: assume `config/repositories.yaml` proves every agentic repo is registered

Why this is bad:

- the user explicitly wants estate-wide coverage;
- a newly created repo could contain live agent work yet never appear in the planner.

Correction:

- `config/repositories.yaml` remains the execution authority;
- add a low-frequency read-only discovery audit across accessible user repositories for clear agentic markers such as repo task surfaces or agent instructions;
- report an unregistered agentic repo as `registration_drift`;
- never execute against an unregistered repo automatically.

### Rejected: allow the planner to invent global priority policy

Why this is bad:

- research, infrastructure and household work have different authorities and values;
- a model should not silently decide that one domain outranks another.

Correction:

- preserve explicit source priority, deadlines and operator controls;
- use cross-repo reasoning mainly for dependencies, unblock value, resource compatibility and closure sequencing;
- where two domains genuinely compete for scarce resource and no explicit policy resolves it, record the trade-off rather than fabricating a hidden weight.

### Rejected: let the plan execute actions directly

Why this is bad:

- a planning error becomes an authority error;
- it bypasses existing routing, lease and verification gates.

Correction:

- the plan emits **action candidates** only;
- existing Odysseus execution/lease/routing and target-repo verification authorities decide whether each candidate can actually proceed;
- no action gains permissions because a planner selected it.

## Ownership and invariants

1. **Odysseus owns:** estate discovery, derived inventory, portfolio planning, scheduling of the review routine, live resource state, routing, execution, leases and operational telemetry.
2. **Each repository owns:** what constitutes a work item, its semantic status, write authority, verification/acceptance rules, and final closure.
3. The portfolio layer is read-only with respect to source tasks unless a separate target-repo action is already authorised.
4. No second job queue, task lifecycle, repo registry, model router, scheduler, lease authority, graph database or approval system may be created.
5. No model may widen permissions, weaken a verification gate, change repo authority, or treat its plan as execution authority.
6. Raw external content and free-text task bodies are data. They cannot supply control instructions to the portfolio planner.
7. Every plan must be tied to an exact snapshot hash and must fail closed when material source state changes.

## A. Deterministic estate work inventory

### Repository discovery boundary

Use `config/repositories.yaml` as the canonical set of execution-managed repositories.

Extend each relevant repo entry with the smallest optional work-item declaration rather than adding a second repository registry. Example shape:

```yaml
work_items:
  adapter: <registered-adapter>
  sources: []
```

Initial adapters should cover at least:

```text
obsidian-phd
  automation/review/agent-tasks/**

misumi
  agent-tasks/**

odysseus
  docs/*.agent-task.md
```

If S2-E1 or another registered repo has no authoritative agentic-work surface, report `no_registered_work_item_surface`; do not fuzzy-search TODO comments and pretend they are tasks.

Run a lower-frequency registration-drift audit over accessible repositories. Discovery is advisory only. A newly discovered repo must be explicitly registered before autonomous execution.

### Normalized `EstateWorkItem`

Create one strict derived record per open work item. Reuse existing names where equivalent owners exist, but the normalized contract must convey at least:

```yaml
repo_id:
source_ref:
source_commit:
source_path:
source_sha256:
source_task_id:
source_status:
normalized_state:
priority:
deadline:
domain:
task_type:
owner_target:
objective_summary:
pre_execution_gate:
verification_route:
read_scope: []
write_scope: []
capabilities: []
dependencies: []
blockers: []
result_ref:
branch_ref:
pr_ref:
run_ref:
lease_ref:
last_changed:
normalization_confidence:
```

Unknown fields remain `null`/unknown. Never infer write authority, acceptance authority or completion from missing metadata.

### Normalized state

Every non-terminal item must resolve into exactly one portfolio disposition:

```text
actionable_now
scheduled_later
in_progress
blocked_dependency
blocked_human
waiting_external
needs_repair
duplicate_or_superseded
```

`needs_repair` includes malformed, ambiguous, stale-provider-pinned or authority-incomplete tasks that cannot safely be scheduled.

Terminal source tasks are counted for audit/closure checks but excluded from the active planning set.

### Source reconciliation

Prefer the registered canonical repo source available to the worker. Record commit SHA and local/remote provenance.

Where local clone, remote default branch, open PR or task metadata disagree materially:

- record `source_divergence`;
- do not silently choose the version most convenient for execution;
- prevent mutating action until the authoritative source is resolved.

Open PRs, CI, branches and leases are **operational enrichment**, not independent work items by default. They may produce closure actions linked to an existing task, or an orphan-state finding where no task relationship exists.

## B. Autonomous-action reconnaissance skill

Implement one thin user-facing skill over the core inventory. Do not place business logic in the skill prompt.

Preferred logical modes:

```text
work scan
work actionable
work blocked
work plan
work explain <repo/task>
work refresh
```

The existing controller/`agent sync` mechanism should install or expose the skill using the same user-scoped pattern as other Aoteru control skills. Do not hard-code repo paths, hosts or provider names into the skill.

### `work scan`

Return a compact estate summary:

- open item count by repo/state;
- newly actionable work;
- stale or malformed work;
- items waiting on human decisions;
- safe closure actions on existing work;
- orphan PR/branch/run/lease anomalies;
- registration drift;
- changes since the previous snapshot.

### Autonomous action candidates

The scanner may identify, but does not itself execute, bounded candidates such as:

- validate/preflight a ready task;
- dispatch an already-authorised ready task;
- safely retry/resume an idempotent failed task;
- recover a stale runtime claim through existing recovery authority;
- run V0 deterministic acceptance;
- request V1 independent review;
- update or review a draft PR where the source task authorises it;
- regenerate a stale deterministic report;
- stage one operator decision packet for a real human blocker;
- close lifecycle bookkeeping after durable evidence proves the work already completed.

Any action requiring research judgement, external mutation, canonical promotion, unregistered repo access, permission widening or target-repo human authority remains blocked/human-gated.

## C. Portfolio snapshot

Persist derived operational state in existing Odysseus runtime storage, preferably SQLite. Do not create a Git-backed central task store.

Each `PortfolioSnapshot` must contain:

```text
snapshot_id
generated_at
repo-registry hash
adapter versions
source repo commit hashes
active item records or pointers
operational enrichment hashes
coverage counts
material_snapshot_hash
findings/anomalies
```

Keep enough history to compare plan stability and execution outcomes, but do not retain unnecessary raw task bodies or model scratchpads.

## D. Completion-planning routine

### Cadence

Use the **existing Odysseus scheduler**.

Trigger the portfolio review twice daily, aligned with the estate's existing twice-daily autonomous sweep where practical. Do not create a second daemon or scheduler.

Each scheduled run:

```text
deterministic scan
-> compare material snapshot hash
-> unchanged + valid incumbent plan: stop cheaply
-> changed/expired/failed plan: invoke strong planning pass
```

An explicit operator `work plan` request may force a fresh planning pass.

### Two-level plan

Do not ask a model to produce a detailed execution script for every open item in a large estate.

Produce:

1. **Portfolio completion map:** every open item gets exactly one disposition, coarse dependency relation and closure path.
2. **Bounded execution horizon:** detailed waves only for the next useful horizon, initially the next two review cycles or approximately 24 hours of eligible work.

This gives whole-estate coverage without creating a huge brittle plan.

### Planner context

The strong planner receives only:

- normalized open `EstateWorkItem` records;
- repo authority/operating-contract pointers and bounded summaries;
- live host/resource eligibility summary;
- active lease/run/PR/CI summaries;
- prior plan + outcome summary;
- explicit planner output schema.

If an item remains ambiguous, allow a targeted second context fetch for that item only. Record every expanded source pointer.

Do not give the planner whole repositories, whole chat transcripts or raw external-source corpora.

### Planner model policy

This task genuinely benefits from a capable long-horizon reasoning model. The initial qualified planner should therefore be **GPT-5.6 Sol-class capability** if live provider access and routing evidence support it.

Do not hard-code `gpt-5.6-sol` into business logic. Route through an approved planning/reasoning capability in Odysseus. If the existing `reasoning-strong` alias can safely express the required quality floor, reuse it. Add a dedicated `portfolio-planning` capability/task class only if the existing abstraction cannot express the requirement without ambiguity.

Treat GPT-5.6 Sol as the initial qualified candidate, not permanent architectural truth. Later cheaper/local challengers may replace it only after passing a representative portfolio-planning evaluation corpus with non-inferior quality.

### Strict `PortfolioPlan`

The planner must return a strict machine-validated structure containing at least:

```yaml
plan_id:
based_on_snapshot_hash:
created_at:
expires_at:
planning_horizon:
critical_path: []
coverage:
  total_open:
  represented:
  missing: []
waves:
  - wave_id:
    objective:
    prerequisites: []
    items:
      - work_item_ref:
        proposed_action:
        why_now:
        expected_result:
        autonomy_class:
        required_capabilities: []
        verification_route:
        dependencies: []
        concurrency_group:
        stop_condition:
blocked_human: []
blocked_dependency: []
waiting_external: []
needs_repair: []
deferred: []
plan_risks: []
proposed_new_work: []
```

A hallucinated work-item identifier or source path invalidates the plan.

### Dependency reasoning

Distinguish:

- explicit dependency from source task or linked execution state;
- deterministic dependency derived from authority/lease/result state;
- model-inferred dependency hypothesis.

Only the first two may automatically block execution. A model-inferred dependency must remain advisory until validated or materialised through the existing work-item authority.

## E. Deterministic parallelisation gate

Before the model sees candidate concurrency, compute hard compatibility.

Tasks are parallel-compatible only when all relevant constraints pass.

### Read-only work

Independent read-only work may parallelize when:

- context/source scopes do not require mutable shared state;
- resource/provider budgets permit it;
- no experiment-priority resource conflict exists.

### Write work

Concurrent write work requires all of:

- separate isolated branch/worktree or equivalent target-repo mechanism;
- no incompatible ParkLease/active writer;
- disjoint declared write scopes;
- no hidden sequential dependency;
- deterministic validation per unit;
- defined aggregation or merge ordering;
- rollback available.

Unknown write scope means **serial**.

### Resource constraints

Use live estate state, not planner assumptions.

- laptop remains controller, not worker;
- interface PC remains non-worker;
- home may be used only after live worker qualification makes it eligible;
- glovebox/Jetson remains experiment-edge, not generic background compute;
- heavy lab/home GPU work yields to active robotics experiment reservations;
- provider concurrency and paid-call budgets must be respected.

The planner may choose among deterministically compatible groups. It may never override an incompatibility result.

## F. Plan validation before model review

Implement a deterministic validator. A plan cannot reach adversarial review unless all structural checks pass.

At minimum enforce:

1. 100% active-item coverage: every open item appears exactly once in a disposition.
2. Every referenced item exists in the source snapshot.
3. Snapshot hash matches current material state.
4. No impossible dependency cycles in executable waves.
5. No human-blocked or V3-equivalent item is proposed for autonomous execution.
6. No parallel wave contains an invalid write/resource conflict.
7. No action widens source-task write/read/approval authority.
8. No provider/host is hard-pinned unless the source task itself validly requires it.
9. Every autonomous action has a verification/closure route.
10. No inferred dependency is silently promoted to an enforcement dependency.
11. Plan size and planning horizon remain bounded.
12. Every new-work proposal is deduplicated against the current portfolio.

## G. Independent adversarial plan review

After deterministic validation, run one independent review over the compact plan and snapshot.

Review questions:

- Did the planner omit or misclassify any consequential work?
- Has it confused repo authority with portfolio authority?
- Has it scheduled something that is not actually executable?
- Is the critical path real or merely a model preference?
- Is any parallelism unsafe, pointless or coordination-heavy?
- Is it overusing expensive models/hosts where deterministic or local work would suffice?
- Has it created unnecessary child tasks instead of completing existing ones?
- Has it starved a ready task across repeated plans without a concrete reason?
- Has it overreacted to stale/low-confidence metadata?
- Does the plan increase operator burden rather than reduce it?
- Does any plan step bypass verification, leases, target-repo governance or experiment priority?

Prefer cross-provider independent review where an eligible independent provider exists. If not, use a fresh-context independent pass with the strongest qualified reviewer, with no planner scratchpad and an explicit review rubric. Do not pretend same-model fresh-context review is equivalent to cross-provider independence; record the verification provenance truthfully.

Reviewer verdict:

```text
PASS
AMEND
REJECT
```

`AMEND` permits at most one bounded planner repair pass, followed by deterministic validation again. Persistent disagreement/rejection means retain the previous valid plan where safe and surface the blocker. Do not enter an unbounded planner-review loop.

## H. Plan stability and anti-thrashing

The plan is derived operational state and should be stable when reality is stable.

- Never cancel or reorder running work merely because a new stochastic plan prefers another order.
- Preserve incumbent waves where prerequisites and priorities remain materially unchanged.
- Replan on material state change, failure, new deadline/priority, human decision, resource eligibility change, or expiry.
- Track plan churn. Excessive reorder without improved closure outcome is a quality regression.
- Any actionable item deferred across two consecutive valid plans must carry a concrete `defer_reason` so ready work cannot disappear silently.

## I. Work-generation firewall

The planner may identify missing work but must not become a task factory.

`proposed_new_work` is advisory by default.

Automatic materialisation is permitted only when an existing target-repo work-generation contract already allows it and all are true:

- trigger is machine-verifiable;
- duplicate fingerprint is absent;
- scope is automation/review-side and reversible;
- acceptance route is already authorised;
- no research/normative decision is required;
- no external or canonical mutation is introduced.

Otherwise stage one source-repo inbox/human decision candidate through that repo's existing mechanism.

No plan-review-of-plan recursive work chains.

## J. Execution integration

The planner does not implement a second dispatcher.

For every `actionable_now` plan item:

```text
portfolio action candidate
-> existing repo-specific task adapter / execution bridge
-> Odysseus lease + route + executor
-> target-repo deterministic checks
-> target-repo verification/acceptance
-> source task lifecycle closure
```

PhD autonomous execution activation depends on the separate task `2026-08-30-odysseus-agent-task-execution-bridge`. This dependency must block only the **execution activation** for PhD work, not development of the scanner/planner itself.

Do not wait for that bridge before building read-only inventory, planning and validation.

## K. Metrics and learning

Measure outcomes, not planning activity.

At minimum record/derive:

```text
open_items_total
portfolio_coverage_rate
actionable_now_count
blocked_human_count
blocked_dependency_count
needs_repair_count
registration_drift_count
orphan_operational_state_count
ready_item_age
avoidable_ready_idle_time
plan_churn_rate
plan_validation_failure_rate
review_amend_reject_rate
parallel_conflict_prevented_count
items_validly_closed_per_plan
operator_interventions_per_closed_item
planner_context_tokens
planner_paid_tokens
planner_latency
planner_route/model provenance
```

Do not optimise `items_closed` alone. A tiny housekeeping item is not equivalent to a critical research or infrastructure closure.

Feed plan/run outcomes into the existing routing/evaluation/continuous-improvement evidence surfaces. Do not create a separate self-improvement framework.

Later model substitution must be benchmarked against a frozen portfolio-planning corpus drawn from real, sanitized snapshots. Promote a cheaper planner only when it preserves safety/coverage/plan quality and materially improves cost or latency.

## Implementation sequence

Make this implementable by a cheaper code model by removing architectural discretion from each PR.

### PR 0: truth audit and red-characterisation tests

No production behaviour changes.

Prove:

- current managed repos and their actual agentic work surfaces;
- heterogeneous status/schema semantics, especially PhD vs Misumi vs Odysseus;
- current scheduler and controller skill installation paths;
- available PR/branch/CI/run/lease enrichment surfaces;
- absence of an existing estate-wide portfolio owner;
- exact reuse points in SQLite/API/routing/scheduler code;
- which execution actions depend on the separate PhD bridge.

Add fixtures representing each live task format and red tests for missing cross-repo inventory/coverage.

### PR 1: deterministic repo adapters and inventory

Implement:

- optional `work_items` declarations subordinate to `config/repositories.yaml`;
- adapter interface;
- PhD, Misumi and Odysseus adapters;
- strict `EstateWorkItem` validation;
- source hashes/provenance;
- normalized state;
- snapshot generation;
- read-only CLI/API inventory.

No model calls and no execution.

### PR 2: actionability, dependencies and concurrency gate

Implement deterministic:

- blocker/pre-execution classification;
- explicit dependency handling;
- PR/branch/run/lease enrichment;
- stale/orphan/divergence findings;
- hard parallel compatibility matrix;
- experiment/resource conflict checks;
- action-candidate generation.

Still no planner model and no execution.

### PR 3: portfolio planning model path

Implement:

- strict `PortfolioPlan` schema;
- compact context builder;
- snapshot-hash no-change short circuit;
- bounded targeted context expansion;
- strong planner call through existing routing/provider infrastructure;
- deterministic plan validator;
- SQLite plan persistence and read API.

Initial qualified planner target: GPT-5.6 Sol-class capability where available, configured rather than hard-coded.

### PR 4: adversarial review and bounded repair

Implement:

- independent reviewer packet;
- PASS/AMEND/REJECT parser;
- cross-provider preference;
- maximum one repair pass;
- previous-plan fallback;
- review provenance and telemetry.

### PR 5: on-demand skill and twice-daily routine

Implement the thin `work` skill over the same core APIs and register/install it using the existing Aoteru controller mechanism.

Add one scheduled routine using the existing scheduler:

`scan -> hash -> plan only if needed -> validate -> review -> publish derived plan`

No second scheduler, cron daemon or prompt-owned implementation logic.

### PR 6: governed execution integration

After the relevant execution bridges are available:

- hand `actionable_now` candidates into the existing dispatcher;
- prove no plan authority bypass;
- demonstrate safe parallel execution of genuinely independent work;
- demonstrate serialization of conflicting write work;
- close results through source-repo verification/lifecycle semantics.

### PR 7: calibration and lower-cost challenger evaluation

Only after real plan history exists:

- freeze a representative sanitized planning corpus;
- benchmark cheaper/local planning candidates against the incumbent;
- compare coverage, safety, actionability correctness, dependency quality, plan stability, operator burden, tokens and latency;
- promote only through existing regression/canary governance.

Do not invent model discovery merely to complete this PR.

## Required acceptance tests

Do not report material completion until tests cover at least:

1. PhD v1/v2 open tasks are inventoried without altering source files.
2. Misumi task folders normalize without treating `claude`/`codex` folder names as permanent model authority.
3. Odysseus `.agent-task.md` work is inventoried.
4. A registered repo with no work-item surface reports that truthfully.
5. An unregistered repo with clear agentic markers appears only as registration drift.
6. Duplicate/superseded work is not independently scheduled.
7. Human-blocked work never becomes autonomously actionable.
8. Missing authority fields produce `needs_repair`, not guessed permission.
9. An unchanged snapshot avoids a strong-model call.
10. A material task/priority/blocker change invalidates the prior plan.
11. A stale plan cannot dispatch work.
12. A planner omission fails the 100% coverage validator.
13. A hallucinated task/source reference fails validation.
14. An impossible dependency cycle fails executable planning.
15. Model-inferred dependency remains advisory until validated.
16. Two write tasks with overlapping/unknown scopes cannot share a parallel wave.
17. Independent read-only tasks can share a parallel wave when resources permit.
18. Disjoint write tasks only parallelize with valid isolation, lease and merge-order evidence.
19. An active repo lease conflict prevents incompatible mutation.
20. Experiment reservation/load blocks inappropriate heavy GPU background work.
21. Home is not scheduled as worker while live eligibility says it is unqualified.
22. Interface/laptop/glovebox roles cannot be misused as generic workers.
23. Task-body prompt-injection text cannot modify planner instructions or authority.
24. Open PR/CI state enriches its linked task rather than creating duplicate work.
25. Local/remote source divergence blocks unsafe mutation.
26. V2/human-acceptance work may be planned for preparation but not silently accepted/closed.
27. Reviewer AMEND triggers at most one repair pass.
28. Reviewer REJECT preserves a previous still-valid plan where safe.
29. Planner/model/provider failure does not destroy the incumbent valid plan.
30. Ready items deferred repeatedly must carry a concrete reason.
31. New-work proposals are deduplicated and cannot recursively explode.
32. Every autonomous action reaches the existing lease/router/verifier path rather than a portfolio-owned executor.
33. No second queue, scheduler, router, repo registry, approval authority or graph database appears in the implementation diff.
34. One live estate proof inventories real PhD, Misumi and Odysseus open work and returns a validated reviewed plan without mutating any source task.
35. Once the execution bridge is available, one safe live proof progresses at least two independent eligible items concurrently and one conflicting pair serially, with complete routing/verification provenance.

## Completion gate

Complete only when:

1. the on-demand work skill can answer what is open, actionable, blocked and why across all currently registered agentic repos;
2. registration drift prevents silent omission of newly agentic repos;
3. every active item has exactly one portfolio disposition;
4. the twice-daily routine is real and idempotent;
5. unchanged state does not spend strong-model tokens;
6. a changed estate produces a strict validated completion plan;
7. planning uses bounded pointers and targeted expansion, not whole-repo context dumps;
8. the strong planner is routed/configured, with GPT-5.6 Sol-class as the initial qualified target where available rather than a hard-coded permanent dependency;
9. the plan is deterministically checked before independent adversarial review;
10. review cannot enter an unbounded repair loop;
11. parallelism is constrained by deterministic write/lease/resource safety;
12. source-repo authority and verification remain unchanged;
13. the plan remains derived/expiring and never becomes a second task authority;
14. metrics connect planning decisions to real closure outcomes and operator burden;
15. relevant test suites and safe live proofs pass;
16. independent fresh-context review finds no duplicate orchestration authority, hidden permission widening, silent work omission, prompt-injection path, or obvious token-waste loop.

Final report should state only:

- implemented inventory/skill/planner surfaces;
- repositories/adapters covered;
- planner/reviewer routing and token behaviour;
- schedule and no-change behaviour;
- live plan/action proofs;
- test/evaluation results;
- remaining genuine authority or host blockers;
- commit/PR references.

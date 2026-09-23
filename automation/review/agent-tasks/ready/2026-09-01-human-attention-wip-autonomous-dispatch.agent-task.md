---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-01-human-attention-wip-autonomous-dispatch
title: "Build and enforce the work-item development operating contract"
status: ready
priority: high
task_type: orchestration
created_by: chatgpt
created_at: 2026-09-01T10:41:00+01:00
updated_at: 2026-09-13T12:00:00+01:00
executor: gpt_subscription
execution_mode: design-then-implementation
architecture: single-plus-verifier
architecture_rationale: "One strong controller should reconcile the existing work-item, audit, priority, dispatch and portfolio mechanisms into one operating contract. A fresh independent verifier must attack priority inversion, duplicate authority, false completion, unsafe auto-dispatch and review-loop inflation before bounded enforcement is accepted."
single_agent_baseline: "One high-context agent can inspect the current task authorities and write the smallest coherent contract. Parallel design would increase coordination cost and risks creating another planning system."
execution_host: laptop
context_budget: high
coordination_reason: "Use one independent strong-model verifier after the contract and bounded implementation are frozen. Do not run open-ended multi-agent debate or repeated verification passes without a new material defect."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V1_LLM_VERIFIED
risk_level: medium
approval_required: false
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: chatgpt/work-item-development-operating-contract-20260910
allowed_paths:
  - Scripts/automation/**
  - automation/docs/**
  - automation/review/**
  - automation/tests/**
  - 08-template/planning/**
  - 10-inbox/**
  - 00-dashboards/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 02-library/**
  - 11-projects/**
  - 12-log/**
  - "**/*.bib"
  - "**/*.pdf"
inputs:
  - automation/docs/central-operating-contract.md
  - automation/docs/work-item-planning.md
  - automation/docs/agent-task-frontmatter-schema.md
  - automation/config/agent_routing.yaml
  - automation/config/model_execution_policy.yaml
  - Scripts/automation/work_item_planning.py
  - Scripts/automation/agent_task_lint.py
  - automation/review/routine-reports/work-item-audit/2026-09-10-cross-repo-deep-reconciliation.md
  - automation/review/routine-reports/work-item-audit/2026-09-10-agentic-model-routing-and-priority.md
  - PR #534 research-work-priority skill, if still current
  - PR #535 parallel-frontier scheduler task, if still current
  - tyecam1/odysseus PR #27 cross-repo work portfolio planning, if still current
  - tyecam1/odysseus PR #26 agent-task execution bridge packet, if still current
outputs:
  - one durable operating contract for continuous work-item progression, preferably integrated into automation/docs/central-operating-contract.md rather than creating a parallel authority
  - deterministic use/regeneration of the existing derived agentic model-routing and priority report so every formal agent-task record has a current priority cluster/order, activation state, preferred route/support route and effort without replacing source task authority
  - deterministic pull-loop rules that move eligible work from inventory to execution, verification, integration and closure without repeated operator prompting
  - explicit priority/similarity clustering, WIP and interruption rules grounded in the reconciled backlog
  - bounded cross-repo integration with existing task authorities, scheduler/heartbeat, Odysseus routing and future parallel-frontier capability
  - regression tests and a dry-run/current-inventory demonstration
result_path: automation/review/work-item-focus/2026-09-10-work-item-development-operating-contract-implementation.md
review_report_path: automation/review/work-item-focus/2026-09-10-work-item-development-operating-contract-verification.md
handoff_model: strong_model_controller_plus_independent_verifier
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: https://github.com/tyecam1/obsidian-PhD/pull/540
supersedes: []
duplicates: []
notes: "This is an upgrade of the existing human-attention/autonomous-dispatch task, not a second controller. Preserve one task authority per repository. The objective is sustained useful progress, not maximum task throughput."
---
# Work-item development operating contract

## Goal

Create and enforce one operating contract that continuously converts the reconciled work inventory into useful completed work.

The system must not merely list, rank or monitor tasks. When safe eligible work exists, it should **pull the next bounded item, execute it, verify it, integrate the result, reconcile its task state, and pull again** until capacity is full, the active objective is complete, or a genuine blocker is reached.

The desired control loop is:

`reconcile truth -> choose priority cluster -> expose execution frontier -> decompose if needed -> dispatch -> verify -> integrate -> close/supersede -> pull next`

No extra operator prompt should be required between ordinary successful stages.

## Starting condition

The 2026-09-10 deep reconciliation found that the nominal cross-repo backlog is much larger than the set that should be treated as active work. It also found:

- completed and superseded tasks left open;
- related tasks split into overlapping cards;
- proposed task authority living in unmerged PRs;
- PhD-critical, runtime-critical and speculative work sharing the same coarse priority labels;
- agent-safe work remaining inert while human attention is used for coordination;
- review/verification work able to continue after marginal value has collapsed.

The operating contract must correct those behaviours permanently rather than requiring periodic manual cleanup.

## Authority boundary

Do not create another backlog, scheduler, portfolio database, graph authority or orchestration service.

Preserve current ownership:

- `obsidian-PhD`: PhD human work and central PhD agent-task lifecycle;
- `misumi`: its own household task authority;
- `odysseus`: cross-repository runtime, routing, leases and execution machinery;
- executable research repositories: implementation and empirical/software validation within their declared scope.

The operating contract is a **control policy over existing authorities**, not a replacement authority.

Before adding any mechanism, inspect whether the current work-item audit, priority skill, human-attention controller, Odysseus portfolio planner, execution bridge, scheduler/heartbeat or parallel-frontier work already owns it. Extend or connect the existing owner.

## Core invariants

### 1. Progress, not inventory, is the default state

An active priority cluster may not remain idle while all of the following are true:

- useful work is already represented in an authoritative task surface;
- dependencies are satisfied;
- the work is within an existing permission boundary;
- execution capacity is available;
- no required human approval is outstanding.

If those conditions hold, the system must dispatch or continue the work. If it does not, it must emit a concrete machine-readable reason.

`ready but indefinitely inert` is a control defect.

### 2. One primary human deliverable, bounded human actions

Keep one primary human-facing deliverable at a time.

Within it, expose at most three immediately actionable human decisions/actions by default. These can be supervision, physical/lab actions, approval, authorship or other genuinely human work.

Do not interpret this as one atomic task. A deliverable may contain many subordinate agent tasks and several tightly related human actions.

Switch the primary human deliverable only when:

1. it is complete;
2. it is genuinely blocked externally;
3. a harder external deadline overtakes it;
4. safety, ethics, compliance or a mandatory administrative obligation requires intervention;
5. the operator explicitly changes it.

### 3. Agent WIP is bounded but continuously replenished

Use **five concurrent agent-owned work packages as the default upper bound**, reduced where shared files, leases, hardware, verification capacity or model limits require less.

When one agent slot reaches a terminal state, automatically evaluate the current execution frontier and fill the slot with the highest-value eligible work.

Do not fill capacity with low-value work merely to reach five.

### 4. Prioritise by research/dependency value, not task age

Use the equivalent of this ordering:

1. hard external deadline with valid prerequisites;
2. blocker removal for the active primary deliverable;
3. direct advancement of the active primary deliverable;
4. prerequisite work for the next research stage;
5. safety/provenance/runtime maintenance required to keep the above trustworthy;
6. compounding infrastructure with a demonstrated near-term multiplier;
7. downstream preparation;
8. speculative/exploratory work.

For the current PhD state, J1/S2 and their immediate supervision/CPI dependencies outrank optional research-system infrastructure unless that infrastructure removes a measured J1/S2 bottleneck.

Misumi household work must not consume PhD human attention merely because its cards are old or numerous.

### 5. Similar work should move as a cluster

Use work similarity to reduce repeated setup and context loss.

Prefer coherent clusters sharing one or more of:

- same deliverable or research gate;
- same repository and authority surface;
- same evidence corpus or experiment;
- same implementation subsystem;
- same verifier/acceptance chain;
- same physical setup or external meeting dependency.

Once a high-priority cluster is activated, keep pulling eligible work from that cluster until:

- its objective/acceptance condition is met;
- the remaining work is genuinely blocked;
- a higher-priority deadline or blocker intervenes;
- continuing has lower marginal value than another ready cluster.

Do not context-switch merely because another unrelated task is labelled high priority.

### 6. Large tasks become bounded child work, not stalled monoliths

If an authoritative task is too large for one safe execution package, decompose it into the minimum bounded child tasks needed for progress.

Each child must have:

- one parent;
- exact scope and permitted paths;
- prerequisite(s);
- expected inspectable output;
- verification route;
- stopping condition.

Do not duplicate the parent as another independent backlog item. Parent state must be derived from child evidence and explicit acceptance, not optimism.

### 7. Hybrid work is agent-prepared first

For hybrid work, perform every safe preparation step before involving the operator.

Human returns should be compact decisions/actions such as:

- approve/reject;
- choose A/B;
- provide one missing judgement;
- perform one physical action;
- review one consequential result.

Never make the operator manually coordinate a chain of agent prompts that the system can execute under existing authority.

### 8. Completion must reconcile the task surface immediately

After successful work, the same progression loop must check whether acceptance criteria are met and reconcile the authoritative task record.

Do not leave `done evidence` in `review`, `ready`, `blocked` or `10-inbox` indefinitely.

Completion requires inspectable evidence. Artifact existence alone is insufficient.

Where a successor supersedes an older task, preserve history and move/mark the older record terminal in the repository's existing lifecycle. Do not delete lineage.

### 9. Unmerged PRs are proposals, not current task authority

An unmerged PR can provide implementation/progress evidence, but must not silently replace default-branch task authority.

The controller must detect:

- a PR that already implements an open task;
- a PR that proposes a successor task;
- a PR that is stale/superseded;
- multiple PRs claiming the same work.

Use this to avoid duplicate execution and to generate the smallest merge/review action required. Do not mark the default-branch task superseded until the successor authority actually lands or an explicit operator decision retires it.

### 10. Verification has a stopping rule

Verification exists to find material error, not to generate more review activity.

For each work package define the acceptance authority before execution. After deterministic checks and the required independent verification:

- if a material defect is found, repair it and rerun only the affected acceptance checks;
- if no material defect remains, stop;
- do not launch another general confirmation pass without a new concrete risk, changed input or failed acceptance condition.

Repeated non-material findings must not keep a task open indefinitely.

### 11. Blocked work still advances to the boundary

A human or external blocker does not justify abandoning all preparatory work.

For blocked/hybrid tasks, agents should complete every safe prerequisite that does not prejudice the human decision, then return the smallest unresolved blocker.

A task is `blocked` only on the irreducible missing condition, not on work the agent could have prepared first.

### 12. Progress measurement must resist gaming

Do not optimise raw task count, commit count, model calls or review passes.

Prefer evidence such as:

- critical-path blockers removed;
- accepted outputs completed;
- active-cluster acceptance conditions closed;
- human coordination steps removed;
- stale/duplicate task authority reconciled;
- elapsed time from ready -> verified terminal state;
- number of genuinely actionable human decisions waiting.

A smaller, better-reconciled backlog can represent more progress than a larger number of created tasks.

## Current priority clusters to seed the contract

Use the reconciliation report as the initial test case, not permanent hard-coded vocabulary.

### PhD P0

- J1 method/manufacturing-objective convergence and manuscript development;
- S2-E1 glovebox/constrained-manipulation metrology and representative process-value work;
- supervision/CPI decisions that directly condition those stages;
- safety/ethics requirements only as required for the current physical/participant frontier.

### PhD P1

- evidence acquisition/extraction/integrity that directly unblocks P0;
- safe agentic execution infrastructure that measurably shortens P0, including delegation, execution bridge, portfolio reconnaissance, parallel frontier and qualified cheaper workers.

### PhD P2/P3

- recursive research-OS methodology, research-evolution graphs, broader output auditing and other compounding infrastructure after current critical-path stability;
- downstream S2/S3/S4/S5 or optional tooling when prerequisites are not yet satisfied.

### Misumi M0-M3

- M0: runtime safety and unresolved live acceptance;
- M1: model/persona/runtime quality;
- M2: memory/recoverability and voice/interface programmes;
- M3: convenience/media and exploratory frameworks.

M3 is parked unless a repeated household need or measured capability gap activates it.

## Required implementation sequence

### Stage A - map existing owners

Inspect the current implementation and all related open PRs/tasks before writing the contract.

Produce a responsibility map for:

- inventory/reconciliation;
- priority selection;
- similarity clustering;
- dependency/frontier calculation;
- dispatch/lease/execution;
- verification;
- completion/supersession reconciliation;
- human decision surfacing.

If two existing components overlap, nominate one authority and define migration/supersession rather than connecting both indefinitely.

### Stage B - write the operating contract

Prefer adding a concise `Work progression` section to `automation/docs/central-operating-contract.md`.

Create a subordinate contract only if the central contract would become materially harder to use. If a subordinate document is needed, the central contract must remain the entry authority and link to it explicitly.

The contract must be short enough that agents actually load and follow it.

### Stage C - deterministic dry-run controller

Implement or extend the smallest deterministic path that can, over the current authoritative inventories:

1. reconcile obvious terminal/superseded state;
2. identify the active human deliverable;
3. cluster remaining work by priority/dependency/similarity;
4. compute the current safe execution frontier;
5. enforce human/agent WIP limits;
6. identify the next agent work packages;
7. identify the smallest human decisions;
8. report why any agent capacity is intentionally idle.

No write/dispatch behaviour is required to prove the dry-run.

### Stage D - bounded autonomous pull

Only after the dry-run is independently verified, connect it to the existing scheduler/heartbeat/dispatch path for already-authorised agent work.

The first apply scope must exclude:

- canonical research mutation;
- PR merge;
- Zotero/PDF mutation;
- publication/submission;
- new top-level human deliverable activation;
- irreversible external actions;
- physical/lab actions.

### Stage E - current-inventory demonstration

Run the controller over the reconciled current work surface.

Demonstrate that it:

- chooses the correct critical-path cluster rather than the oldest/largest cluster;
- fills agent capacity only with useful eligible work;
- keeps speculative work parked;
- surfaces no more than three genuinely actionable human items;
- avoids re-running completed/superseded work;
- identifies unmerged-PR authority correctly;
- pulls a next item after a simulated terminal completion;
- stops when all eligible work is either complete, capacity-bound or genuinely blocked.

## Required tests

At minimum cover:

1. completed output exists but acceptance condition is not met -> task stays open;
2. accepted implementation evidence exists -> task becomes a terminal candidate and reconciliation is proposed/applied under existing rules;
3. old task has a completed explicit successor -> old task is retired with lineage;
4. successor exists only in an unmerged PR -> old default-branch task remains authoritative;
5. P0 blocker and P3 ready task compete -> P0 wins;
6. five agent slots include conflicting writes -> only conflict-free frontier is dispatched;
7. one agent task completes -> next eligible task is automatically pulled;
8. human gate blocks final step -> all safe preparation completes first, then one bounded human action is surfaced;
9. repeated verifier finds no material defect -> no further confirmation pass is scheduled;
10. active cluster has eligible work and free capacity -> controller cannot report healthy idle state without an explicit reason;
11. several similar tasks share one acceptance chain -> controller clusters them rather than treating them as unrelated projects;
12. Misumi convenience work cannot displace PhD P0 human attention.

Run existing work-item audit/planning, task-lint, routing, capability-truth and loop-graph tests affected by the change.

## Independent verification

Use a fresh strong model that did not author the implementation.

It must actively attempt to demonstrate:

- priority inversion;
- a second task authority being introduced;
- unsafe dispatch past an approval gate;
- duplicate execution caused by an unmerged PR/task pair;
- false completion from artifact existence;
- endless verification without material change;
- excessive human interruptions;
- agent-capacity filling with low-value work;
- starvation of a critical-path cluster;
- cross-repo writes outside the owning task authority.

One bounded repair pass is allowed for material findings. A second full adversarial pass requires a specific unresolved material defect, not a desire for more confidence.

## Acceptance criteria

This task is complete only when:

- one concise operating contract exists and has one clear authority path;
- the contract defines the full pull loop from reconciliation through terminal closure;
- current priority/similarity clusters can be derived without hard-coding project-specific names into generic logic;
- the existing derived routing report covers every formal agent-task record, including human-gated/hybrid tasks with support routes, with priority state/cluster, preferred current route and effort, while runtime routing remains provider-neutral and re-resolves live eligibility;
- human focus is one primary deliverable with at most three immediate actions by default;
- safe agent capacity is bounded and automatically replenished;
- ready eligible work cannot remain idle without an explicit reason;
- terminal evidence reconciles task state rather than accumulating open residue;
- unmerged PRs are handled without false authority promotion or duplicate execution;
- verification has a materiality-based stopping rule;
- a dry-run over the current inventory demonstrates materially better work progression;
- bounded autonomous dispatch reuses existing scheduler/routing authority and passes regression tests;
- no canonical research content, publication action or irreversible external action is autonomously authorised by this contract.

## Stop rule

Stop after the smallest implementation enforces the operating contract and passes the current-inventory demonstration plus independent verification.

Do not expand into a new project-management UI, graph database, model router, scheduler, task ontology, dashboard, persona system or generic productivity framework.

The success condition is simple: **the existing work gets developed and closed with less human coordination and less backlog residue.**

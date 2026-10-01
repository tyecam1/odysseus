---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-08-30-karpathy-llm-wiki-comment-learning-loop
title: "Design a governed recurring Karpathy LLM Wiki comment learning loop for agentic improvement"
status: blocked
blocked_by: capability-path-convergence
priority: high
task_type: architecture-evaluation
created_by: gpt-5.6-sol
created_at: 2026-08-30T11:56:00+01:00
updated_at: 2026-08-30T11:56:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: parallel-n
architecture_rationale: "One orchestrator should own the estate baseline, source-delta state, synthesis, and final architecture. Use focused workers only for separable concerns such as comment ingestion, evaluation/regression gating, and scheduling. Use one fresh-context independent verifier to attack the monotonic-improvement claim and governance boundary before implementation is proposed."
single_agent_baseline: "A single Fable-class orchestrator can inspect the current automation estate, sample the Karpathy discussion, derive an incremental scan protocol, and produce a review-only implementation design without mutating live capability surfaces."
execution_host: laptop
context_budget: medium
coordination_reason: "Avoid many agents independently reading the same 1000+ comment thread. Fetch/diff comments deterministically first, then route only novel high-signal candidates to bounded model review."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: true
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
migrated_from_repo: tyecam1/obsidian-PhD
migration_note: "Ownership migrated to Odysseus. Treat references to obsidian-PhD automation paths as historical inputs until capability-path convergence is complete."
branch: ""
allowed_paths:
  - automation/review/agent-tasks/**
  - automation/review/automation/**
denied_paths:
  - 00-dashboards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 02-library/**
  - 03-concept/**
  - 04-supportDesign/**
  - 06-datasets/**
  - 07-standards/**
  - 10-inbox/**
  - 11-projects/**
  - 12-log/**
  - automation/config/**
  - automation/docs/**
  - Scripts/**
  - .agents/**
  - .claude/**
inputs:
  - AGENTS.md
  - automation/AGENTS.md
  - automation/docs/central-operating-contract.md
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
  - automation/docs/full-system-plan.md
  - automation/docs/agent-boundaries.md
  - automation/docs/agent-architecture-selection-gate.md
  - automation/config/model_execution_policy.yaml
  - https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
outputs:
  - architecture for incremental recurring comment acquisition and delta tracking
  - high-signal comment triage and evidence-scoring protocol
  - proposal-to-agent-task conversion contract
  - protected capability baseline and anti-regression gate
  - experimental adoption, canary, rollback, and promotion protocol
  - schedule and compute/model routing recommendation
  - bounded implementation task packet(s), only after design verification
result_path: automation/review/automation/2026-08-30-karpathy-comment-learning-loop-design.md
review_report_path: automation/review/automation/2026-08-30-karpathy-comment-learning-loop-design.md
handoff_model: gpt-5.6-sol-independent-review
operator_decision_path: automation/review/automation/2026-08-30-karpathy-comment-learning-loop-design.md
supersedes: []
duplicates: []
notes: "Design only. Do not install a scheduler, mutate automation capability, edit prompts/policies, or auto-adopt community advice. The system must learn continuously while remaining fail-closed and evidence-based. 'No backwards progression' means no unapproved regression on protected baselines, not an impossible guarantee that every metric always improves simultaneously."
---

# Karpathy LLM Wiki comment learning loop

## Objective

Design a low-overhead recurring system that scans new comments on Andrej Karpathy's `llm-wiki.md` gist, identifies genuinely useful lessons about agentic knowledge systems and agent workflows, tests those lessons against the existing agentic estate, and converts only defensible improvement opportunities into governed agent tasks.

The goal is not to copy community ideas. The goal is to create a persistent external-learning loop that compounds useful operating knowledge while making regression harder than improvement.

## Core principle

Treat the comment thread as a noisy external idea stream, not an authority source.

A comment may trigger investigation. It must never directly trigger a live behavioural change.

Required flow:

`new comment -> deduplicate -> classify -> evidence/novelty score -> local relevance test -> reproduce/verify where possible -> improvement hypothesis -> benchmark against baseline -> staged work item -> implementation in isolation -> regression gate -> promotion decision -> retained evidence + rollback path`

## Non-negotiable design constraints

1. **Incremental, not repeated full-thread review**
   - Persist a last-seen stable comment identifier, timestamp, author, source URL and content hash.
   - Re-read old comments only when edits/replies change the evidence state or when a new comment explicitly references them.
   - Initial backfill is one bounded pass. Thereafter process deltas only.

2. **Deterministic acquisition before model reasoning**
   - Prefer GitHub/Gist API or another structured endpoint over browser scraping.
   - Store only the minimum metadata/text needed for review-side traceability.
   - Never let the LLM infer whether a comment is new from prose alone.

3. **No popularity proxy**
   - Stars, reactions, reply count and author status may be weak signals but must not determine adoption.
   - A low-engagement comment with a reproducible improvement can outrank a popular speculative idea.

4. **No direct mutation from external content**
   - New comments can produce review findings or agent-task proposals only.
   - Prompt files, model policy, automation code, canonical research, schemas and live schedules remain governed by their existing authority routes.

5. **One need, one work item**
   - Search existing agent tasks, capability docs, open PRs/issues and current work before creating a new task.
   - Merge evidence into an existing owner when the same improvement is already represented.
   - Do not create a second improvement backlog.

6. **Protected monotonicity, not naive monotonicity**
   - Absolute 'never worse at anything' is impossible because latency, cost, quality and autonomy can trade off and model outputs are stochastic.
   - Define protected invariants and tolerances that may not regress without explicit human override.
   - A change that improves one metric while silently degrading another protected metric must fail the gate.

## Phase 0: inspect current estate and establish ownership

Read the operating contract and architecture/capability truth surfaces first.

Determine:

- where an external-learning scanner belongs operationally;
- whether an existing scheduler/watch mechanism can own the recurrence;
- which current review queue/task lifecycle should receive candidate improvements;
- where minimal scan state can live without creating a parallel knowledge system;
- which evaluation harnesses already exist and must be reused;
- whether the system should be estate-wide or initially limited to the PhD automation stack.

Search for existing work on external intelligence feeds, continuous improvement, capability regression, model evaluation, prompt evaluation, agent benchmarking, source monitoring, or Karpathy's LLM Wiki.

Exit: one ownership map. Do not create a new queue, database, daemon, dashboard or ontology if an existing surface can own the function.

## Phase 1: bounded initial backfill and comment taxonomy

Perform a one-time representative scan of the existing `llm-wiki.md` discussion sufficient to design the classifier and discover recurring idea families. Do not spend the task reading every low-value comment deeply.

Classify candidates into a small taxonomy such as:

- architecture/persistence;
- ingestion and retrieval;
- memory/context management;
- linting/consistency;
- provenance/citations;
- agent orchestration;
- model routing/cost;
- evaluation/testing;
- scheduling/operations;
- security/governance;
- implementation reports;
- failure reports;
- irrelevant/promotion/support noise.

The taxonomy is provisional. Split or merge categories only when the comment population demonstrates a real need.

For each potentially useful comment, extract a compact row:

`comment_id | date | author | permalink | idea | category | evidence_type | claimed benefit | reported failure/cost | implementation pointer | novelty_vs_estate | relevance | verification_needed`

Evidence types should distinguish at minimum:

- unsupported suggestion;
- reasoned design argument;
- implementation link/code;
- single-user experience report;
- repeated independent reports;
- benchmark/measurement;
- identified failure/regression.

Do not treat comments as research evidence for the PhD itself unless separately reviewed through the research evidence process.

## Phase 2: high-signal triage

Design a two-stage triage so most comments never consume an expensive model.

### Stage A: deterministic/cheap filters

Reject or down-rank:

- duplicates and near-duplicates;
- pure praise or support requests;
- self-promotion with no inspectable implementation or transferable idea;
- stale advice already implemented;
- advice outside the estate's problem space;
- proposals that violate current security, provenance or human-gate rules;
- comments whose only argument is popularity or authority.

### Stage B: model-mediated assessment

Score surviving items on separate dimensions, not one opaque relevance number:

- novelty relative to current estate;
- expected utility;
- evidence strength;
- transferability;
- implementation cost;
- operational burden added;
- reversibility;
- blast radius;
- security/governance risk;
- testability.

Require a short rationale with explicit uncertainty.

The classifier must be allowed to return `interesting but no action` and `insufficient evidence`. The system fails if every interesting comment becomes work.

## Phase 3: improvement hypothesis and work-item admission gate

A comment may become an agentic work item only if it changes a live, named decision about the estate.

Required candidate shape:

`observed external idea -> local deficiency/opportunity -> expected measurable improvement -> affected capability -> smallest testable change -> protected metrics -> verification route -> rollback route`

Admission requires all of:

1. a concrete local target exists;
2. the idea is not already implemented or queued;
3. expected benefit is material enough to justify maintenance cost;
4. the hypothesis is testable;
5. a baseline exists or can be measured before modification;
6. rollback is feasible;
7. source provenance is preserved;
8. the task can be bounded to existing authority surfaces.

If any condition fails, retain the insight as review-side evidence only or discard it.

Candidate tasks must enter `automation/review/agent-tasks/{inbox,ready,...}`. Do not invent a 'Karpathy tasks' backlog.

## Phase 4: anti-regression / protected-baseline contract

Design the system around a protected capability baseline before implementing the first externally inspired change.

At minimum evaluate whether the estate already measures, or needs bounded measurement for:

- task success/correctness;
- hallucination or unsupported-claim rate where applicable;
- provenance/source traceability;
- deterministic validation pass rate;
- regression test pass rate;
- task completion latency;
- token/API cost;
- context consumption;
- operator intervention burden;
- failure recovery quality;
- security/permission boundary compliance;
- duplicate/planning-surface creation;
- canonical mutation violations;
- model-routing policy compliance.

Define metrics as one of:

- **hard invariant**: zero tolerated regression, e.g. permission/canonical safety violations;
- **protected metric**: regression allowed only within a stated statistical/engineering tolerance;
- **optimisation metric**: improvement desired but trade-offs may be accepted;
- **observational metric**: recorded until enough evidence exists for a threshold.

Every implementation proposal must declare its expected metric vector before coding.

Promotion rule:

`promote only if all hard invariants pass AND no protected metric crosses its regression tolerance AND the target improvement is reproduced with enough confidence to justify added complexity`

Do not average away a serious regression by combining metrics into one aggregate score.

## Phase 5: experiment, canary and rollback design

Externally inspired changes must be adopted as experiments, not beliefs.

Require:

1. baseline snapshot;
2. isolated branch/worktree or other existing isolation mechanism;
3. smallest sufficient implementation;
4. deterministic tests first;
5. fixed evaluation task set plus, where relevant, a small fresh holdout set;
6. repeated runs when model stochasticity matters;
7. independent verifier not involved in implementation;
8. explicit rollback commit/config;
9. canary or bounded first use when the change affects live agent behaviour;
10. post-adoption recheck after real use.

If the change cannot be benchmarked directly, require a stronger human review and keep it reversible. 'Seems better' is not evidence of improvement.

A failed candidate should still create value by recording why it failed so equivalent advice is not repeatedly retried.

## Phase 6: recurrence design

Recommend the cheapest cadence that still captures useful deltas. Default hypothesis to test: weekly scan plus an on-demand scan after unusually active discussion, not hourly polling of a slow-moving gist.

The recurring run should:

1. fetch comments newer/changed since the cursor;
2. validate/deduplicate;
3. run cheap filters;
4. batch high-signal candidates;
5. compare against current capability/task state;
6. emit zero or more review findings;
7. create/update agent-task proposals only when the admission gate passes;
8. update the cursor only after successful processing;
9. emit a compact run record with counts and reasons, not narrative summaries of every comment.

Failure must be fail-closed. Do not advance the cursor past comments that were not successfully evaluated.

Design idempotency so rerunning the same scan does not create duplicate findings or tasks.

## Phase 7: model and compute routing

Follow `automation/config/model_execution_policy.yaml` and existing `/route` logic.

Target routing principle:

1. structured API/deterministic parsing for acquisition and deduplication;
2. deterministic lexical/semantic comparison against current estate where possible;
3. cheapest sufficient model for first-pass classification and clustering;
4. Fable-class model only for ambiguous high-value synthesis or task formulation;
5. GPT-5.6 Sol fresh-context verification for the final design and for high-blast-radius improvement proposals;
6. compute-box/local model only if the existing routing policy demonstrates a cost-effective bounded role and endpoint preflight passes.

Do not use large models to repeatedly reread the full historical comment thread.

## Phase 8: independent adversarial verification

Have one fresh-context verifier attack the proposed system before implementation tasks are emitted.

The verifier must try to falsify at least these assumptions:

- community comments are sufficiently novel to justify continuous monitoring;
- the triage will not become a self-promotion ingestion channel;
- the scanner cannot create an unbounded stream of low-value tasks;
- 'no backwards progression' is operationally measurable rather than rhetorical;
- benchmark gaming will not allow local improvements to reduce real-world usefulness;
- the baseline itself cannot become stale;
- stochastic model variance is handled adequately;
- repeated work is deduplicated across comments, tasks and already implemented capabilities;
- the system does not grant an external commenter indirect prompt/code write authority;
- the system's own maintenance burden does not exceed the value of the improvements it discovers.

Revise the design until these failure modes are closed or explicitly bounded.

## Deliverable

Write one review-side design report at the declared `result_path` containing:

1. current estate owner and reuse map;
2. source acquisition method and delta-state schema;
3. initial comment taxonomy and representative high-signal examples;
4. deterministic and model triage rules;
5. evidence and novelty scoring;
6. work-item admission contract;
7. protected baseline and regression thresholds/classes;
8. experimental adoption/canary/rollback flow;
9. recurrence cadence and failure behaviour;
10. compute/model route;
11. adversarial verifier findings and changes made;
12. exact smallest implementation task packet(s), with no implementation performed in this task.

## Acceptance criteria

The design is complete only when:

- the scanner is incremental and idempotent;
- a structured comment source and stable cursor/deduplication strategy are identified;
- historical backfill is bounded and cannot recur accidentally;
- most comments can be rejected before expensive model use;
- every retained insight preserves comment-level provenance;
- no external comment can directly mutate prompts, policies, code, schedules, canonical research, or evidence;
- candidate improvement tasks reuse the existing agent-task lifecycle;
- existing work and capabilities are checked before creating a task;
- a measurable baseline exists before any change is trialled;
- hard invariants and protected/optimisation metrics are separated;
- regression cannot be hidden inside an aggregate score;
- model stochasticity is addressed with repeated evaluation where necessary;
- changes are isolated, independently verified, reversible and canaried where appropriate;
- failed experiments are retained sufficiently to prevent repeated rediscovery;
- the recurring scan has bounded cost and a justified cadence;
- cursor advancement is fail-closed;
- the architecture creates no parallel backlog, ontology, scheduler or evaluation stack when an existing surface can be reused;
- an independent verifier has attacked the monotonic-improvement design;
- the report ends with the smallest concrete implementation task(s), not another broad programme plan.

## Stop conditions

Stop and return a bounded blocker rather than widening scope if:

- GitHub/Gist does not expose a reliable incremental comment identifier or accessible structured feed;
- existing estate evaluation is too weak to define meaningful protected baselines;
- the only way to automate acquisition requires brittle scraping with unacceptable maintenance cost;
- the current estate already has an equivalent external-learning loop;
- proposed changes would require loosening canonical/governance permissions merely to make the scanner useful.

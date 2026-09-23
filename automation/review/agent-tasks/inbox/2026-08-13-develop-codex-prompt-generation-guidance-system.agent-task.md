---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-08-13-develop-codex-prompt-generation-guidance-system
title: "Develop Codex prompt-generation guidance system"
status: inbox
priority: medium
task_type: prompt-routing
created_by: migrated-from-obsidian-phd
updated_at: 2026-09-23T15:26:00+01:00
executor: ""
execution_mode: review-first
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
migrated_from_repo: tyecam1/obsidian-PhD
migrated_from_path: 10-inbox/develop-codex-prompt-generation-guidance-system.md
notes: "Migrated as shared backend/cross-repository work. Original body preserved below; re-ground paths against live Odysseus state before execution."
---

# Develop Codex prompt-generation guidance system

## Objective

Develop a reusable prompt-generation guidance system for Codex and related agentic coding/research sessions, analogous to the writing and presentation guidance systems: prompts should be generated from the task, execution host, available models, risk, repository state and resource budget rather than assembled ad hoc.

The system must improve **completed useful work per unit of agent usage** without weakening scientific, provenance, governance or software-quality requirements. It should prevent an agentic task from becoming more expensive because verification and orchestration recursively expand faster than the work being completed.

This is guidance and routing infrastructure, not a second orchestration brain. It should compose with `/route`, existing model-execution policy, repository skills, specialised agents and deterministic tooling rather than duplicate them.

## Triggering failure case: 2026-08-13 PR-convergence run

A Codex App run was given an estate-wide convergence prompt intended to deep-review and complete all non-presentation PRs while protecting the active ICAC presentation. The run produced useful findings but exhausted the available weekly Codex usage before convergence.

Observed outcome:

- approximately 2 h 33 min of goal execution;
- 15 completed subagent jobs;
- 50 locally edited files, approximately +2,410 / -820 lines;
- repeated full-suite test execution, with multiple full test processes still active at termination;
- repeated fresh-context review and exact-head re-review cycles;
- a nested `gpt-5.6-sol` Codex CLI adjudication launched from a Codex App session already using Sol as the primary agent;
- Opus adjudication became unavailable because of its separate rate limit;
- the weekly Codex usage allowance was exhausted;
- zero PRs had merged or closed by termination;
- only PR #467's repair was clearly published remotely; several valuable repairs remained local in worktrees;
- the highest-value J1 manuscript convergence had not yet been completed.

The failure was not that deep review was unnecessary. The failure was **granularity and execution architecture**: deep review, implementation, repeated independent verification, per-action dual approval, full-suite testing, live external research, infrastructure extraction and manuscript reconstruction were combined into one persistent goal with no meaningful resource stop rule.

## Core lessons to encode

### 1. Generate for the actual execution host

The prompt generator must know where the prompt will run before prescribing delegation.

At minimum distinguish:

- Codex App with Sol as primary agent;
- Codex CLI invoked as a bounded worker;
- Claude Code / Opus as primary orchestrator;
- ChatGPT producing a handoff prompt;
- deterministic/local script execution with no model required.

A prompt running in Codex App with Sol as the primary agent must **not** instruct Sol to invoke another Sol through Codex CLI merely to obtain routine independence. Same-model nested orchestration is allowed only when a concrete isolation requirement justifies its extra cost.

### 2. Separate quality depth from task breadth

Deep review should be applied to the material that warrants it, not multiplied across an entire estate by default.

Classify work by risk and epistemic type before generating the prompt:

- low-risk maintenance / metadata;
- bounded software repair;
- governance or security boundary;
- research-method / evidence-system change;
- publication-facing scientific content;
- mixed programme requiring decomposition.

A prompt may be deep **or** broad. If it needs both, decompose it into staged sessions with durable handoff state.

### 3. Budget verification explicitly

Verification must be proportional and should converge rather than ratchet.

Default pattern:

`inspect -> repair -> focused deterministic checks -> one independent review where warranted -> batch integration -> one full relevant suite -> merge-ref/final check`

Avoid:

- full repository suite after every intermediate repair;
- a fresh independent reviewer after administrative-only changes to a decision packet;
- repeating source review when only test metadata changes;
- exact-head reapproval loops for changes that do not alter the reviewed object or risk;
- running identical full test processes concurrently;
- using an LLM to verify facts deterministic tools already establish.

The generated prompt should state the **maximum expected verification depth** for each class of change.

### 4. Put resource stop rules beside completion rules

`/loop` or persistent goals require real bounds. "Bounded" is not sufficient unless a measurable boundary exists.

A generated persistent prompt should declare, where supported:

- maximum concurrent subagents;
- maximum nested model calls;
- maximum fresh-review cycles per material change;
- maximum full-suite runs before integration;
- which model receives high reasoning and which tasks use cheaper/default reasoning;
- a checkpoint at which remaining work is durably recorded instead of recursively expanded;
- a stop condition when marginal verification cost exceeds the risk being reduced.

The system must never define completion as "finish every possible related improvement" without also defining a decomposition and checkpoint strategy.

### 5. Do not create a verification approval ratchet

Independent review is valuable when it attacks a materially changed scientific, architectural, security or provenance object. It is waste when every small correction invalidates all prior reasoning.

Approval/review scope should distinguish:

- **material change:** logic, evidence, authority, interface, scientific conclusion, security boundary;
- **non-material correction:** wording, test-count transcription, formatting, path display, decision-packet metadata that does not change the approved action.

Only a material change should normally invalidate substantive independent review. Permanent governance remains authoritative; prompt generation must not invent stricter approval requirements than the live contract or operator delegation.

### 6. Batch scarce-model judgement

When a second high-capability model such as Opus is scarce, prompts should reserve it for load-bearing decisions:

- disputed scientific interpretation;
- security/governance architecture;
- evidence/provenance boundary;
- final review of a coherent high-risk batch.

Do not use scarce-model tokens to reread complete PRs or approve every low-risk merge independently. Give the reviewer a compact evidence packet and require adversarial sampling of the load-bearing points.

### 7. Prefer salvage over redo after interrupted agent runs

Before generating a continuation prompt, inspect and preserve:

- dirty working tree;
- all linked worktrees;
- unpushed commits;
- local branches;
- running/background processes;
- review artifacts and decision packets;
- remote PR heads.

The continuation prompt must classify existing work as `reuse`, `verify`, `finish`, `discard` or `unknown` before repeating review or implementation.

A usage-limit interruption should produce a **salvage manifest**, not trigger a fresh estate-wide review next time.

### 8. Keep integration work separate from new feature development

Convergence prompts should not silently turn into open-ended architecture programmes.

When review exposes a worthwhile but larger improvement, choose explicitly:

- required to make the current change safe -> repair now;
- separable improvement -> create/follow a work item and keep convergence moving.

Examples from the failure case include validator performance redesign and bibliography-export hardening. Both can be important without being allowed to consume the whole convergence session automatically.

### 9. Optimise for durable state movement

Prompt success should be measured by durable outcomes, not review activity.

Useful measures include:

- PRs merged/closed/superseded;
- repaired branches pushed;
- high-risk defects closed;
- canonical deliverable moved toward completion;
- unresolved work durably captured with exact local/remote state;
- operator intervention removed.

Subagent count, test count, review count and elapsed reasoning are costs, not accomplishments.

### 10. Prompt length is not task quality

The generator should avoid restating every repository rule in every prompt. Prefer:

- short task goal;
- exact scope and exclusions;
- named live contracts/skills to load;
- task-specific risk and verification rules;
- explicit resource budget;
- completion artifact.

Repository contracts should be read from the repository rather than copied wholesale into generated prompts, reducing context duplication and stale policy text.

## Proposed system behaviour

### Input contract

A prompt request should resolve:

- target repository / working directory;
- execution host;
- primary model and available secondary models;
- current usage constraints where known;
- task objective;
- active work that must be protected;
- expected durable output;
- risk class;
- whether current/external research is required;
- whether writes, merges or protected actions are expected;
- existing work/branches/worktrees that may be reusable.

Do not ask the operator for information that can be resolved deterministically from the repository or runtime.

### Generated prompt structure

Prefer a compact structure:

1. **Goal** — one completion condition.
2. **Live-state preflight** — resolve repository state and reusable work before acting.
3. **Scope / exclusions** — protect unrelated active work.
4. **Routing** — which skills/tools/models are justified and why.
5. **Execution budget** — subagent, nested-model and verification limits.
6. **Work sequence** — smallest durable increments first.
7. **Verification** — focused checks, independent review threshold, final integration check.
8. **Stop / handoff** — what to preserve if blocked or budget-limited.
9. **Final output** — concise state table, not another plan.

### Resource profiles

The implemented system should define a small number of configurable profiles rather than hard-coded universal numbers. Candidate profiles:

- **economy:** one primary agent, no same-model nesting, focused tests, second model only for explicit high-risk gate;
- **standard:** bounded specialist subagents, one independent material review, one final full relevant suite;
- **critical:** high-risk source/security review with independent adjudication and stronger integration evidence.

The generator chooses a profile from task risk and available budget, and explains any escalation.

## Required integration points

The system should reuse rather than replace:

- `.agents/skills/route/SKILL.md` for execution routing;
- model-execution policy for model selection and reasoning level;
- agent architecture selection gate for subagent justification;
- verification routing policy for independence requirements;
- existing specialised agents such as repo-governor, automation-builder, voice-auditor and prompt-packager where available;
- academic-writing cycle and personal-writing guidance for manuscript prompts;
- presentation guidance/work items for presentation prompts;
- post-run artifact triage for interrupted or completed runs.

If `prompt-packager` already provides part of this function, extend/converge it rather than creating a parallel prompt authority.

## Evaluation cases

Build a small frozen evaluation set before declaring the system complete.

### Case A: 2026-08-13 PR convergence

Given:

- Codex App;
- Sol primary;
- many open PRs;
- active presentation protected;
- deep review requested;
- Opus scarce.

The generated plan must **not** reproduce the failed architecture. It should:

- inventory and preserve existing repair work first;
- avoid nested Sol-on-Sol adjudication;
- decompose low-risk PR convergence from J1 manuscript convergence;
- merge/push durable low-risk progress before beginning the highest-cost scientific work;
- use focused tests during repairs and at most one final full-suite integration run per coherent batch;
- batch scarce Opus judgement around genuinely high-risk material;
- define a salvage checkpoint before resource exhaustion.

### Case B: single low-risk automation fix

Expected: one agent, focused tests, no literature/source review, no second model unless the live contract requires it.

### Case C: J1 scientific restructuring

Expected: scientific source/locator review and fresh-reader verification, but no unrelated repository-wide maintenance or presentation work.

### Case D: conference presentation refinement

Expected: presentation-specific guidance, claim/evidence review and durable outputs under the configured presentation store; no research-engine refactor.

### Case E: interrupted prior run

Expected: local/remote salvage inventory before any repeated analysis; reuse already reviewed commits where their reviewed object is unchanged.

### Case F: Claude/Opus primary with abundant Codex budget

Expected: Opus remains thin and delegates high-volume implementation/review appropriately, without sending routine work back through Opus or creating recursive cross-model approval loops.

## Acceptance criteria

- A reusable prompt-generation guidance surface exists with one clear authority location.
- The system adapts prompts to execution host and does not prescribe impossible or redundant self-delegation.
- Prompt generation declares a resource/verification profile before long-running execution.
- Same-model nested agents require a stated reason and are absent by default.
- Full-suite execution is integration-scoped rather than repeated after every repair.
- Material and non-material review invalidation are distinguished.
- Scarce external-model judgement is batched and risk-targeted.
- Interrupted sessions produce salvage-first continuation prompts.
- Generated prompts separate convergence from optional architecture enhancement.
- Durable state movement is part of the completion metric.
- The frozen evaluation cases above pass, including a replay of the 2026-08-13 failure case.
- The implementation creates no second task queue, approval ontology, model router or orchestration authority.

## Stop conditions

Stop and redesign if the prompt-generation system:

- increases average prompt size without improving durable task completion;
- routinely spawns the same model from itself for independence;
- treats more subagents or reviews as evidence of quality;
- runs full repository tests repeatedly during local iteration;
- turns every discovered improvement into mandatory scope;
- blocks low-risk durable progress behind unavailable scarce-model review not required by live governance;
- duplicates `/route`, model execution policy or existing prompt-packaging capability;
- requires manual context that the runtime can inspect automatically.

## Done when

The system can generate concise, host-aware and resource-aware Codex/agent prompts that preserve the depth appropriate to the task while preventing recursive verification and orchestration from dominating execution. The 2026-08-13 convergence case must produce a materially cheaper staged prompt that reaches durable PR/state movement before undertaking the highest-cost manuscript work, with an explicit salvage route if the session is interrupted.
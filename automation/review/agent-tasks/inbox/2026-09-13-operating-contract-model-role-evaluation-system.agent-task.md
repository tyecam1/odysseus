---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-13-operating-contract-model-role-evaluation-system
title: "Build operating-contract and model-role evaluation system"
status: inbox
priority: medium
task_type: evaluation-observability
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
migrated_from_path: 10-inbox/2026-09-13-operating-contract-model-role-evaluation-system.md
notes: "Migrated as shared backend/cross-repository work. Original body preserved below; re-ground paths against live Odysseus state before execution."
---

# Build operating-contract and model-role evaluation system

## Goal

Build a lightweight longitudinal system that records, compares and evaluates different agent operating contracts, with particular emphasis on which models perform best in different roles over time.

The system should turn model-role assignment from intuition into evidence. It must distinguish the effect of the **model**, the **role it was given**, the **operating contract governing it**, and the **task/context** in which it worked.

This is an evaluation and learning layer over the existing routing/runtime architecture. Do not create another router, task queue, orchestration framework or source of authority.

## Core question

For a given class of repository work, which combination of:

`model + role + operating contract + tools + task context + verification pattern`

produces the strongest useful outcome at acceptable cost, latency, operator burden and failure risk?

## Why this is needed

Current routing increasingly assigns qualitatively different roles to Claude/Sonnet/Opus, GLM/GLM Flash, Codex and other workers. These assignments are currently informed by experience but are not sufficiently recorded to support rigorous comparison or learning over time.

A model that appears weak as an autonomous worker may be strong as a verifier, critic, bounded extractor, implementation worker or planner. Conversely, a strong general model may waste scarce usage when placed in a role where a cheaper model performs equivalently.

The evaluation unit must therefore be the **model-role-contract-task tuple**, not the model name alone.

## Required observations per run

Record enough metadata to reconstruct and compare meaningful runs without storing unnecessary hidden reasoning.

At minimum capture:

- run ID and timestamp
- repository and commit/ref state
- work item / task ID
- task class and bounded objective
- task risk / consequence class
- model provider and exact model identifier where available
- model/version date or provider revision where available
- assigned role, e.g. planner, coordinator, synthesiser, implementer, verifier, critic, extractor, reviewer
- operating-contract identifier and version/hash
- relevant prompt/initialisation identifier and version/hash
- tool permissions / tool surface
- context inputs or manifest, preferably by references/hashes rather than duplicated content
- upstream model or human that delegated the work
- downstream verifier/reviewer, if any
- tokens/usage/cost where available
- wall-clock latency where available
- retry/escalation count
- output/artifact references
- tests/checks run
- verifier outcome
- human review outcome where present
- human correction burden
- failure category
- whether the result was accepted, revised, escalated, rejected or superseded

Do not record private chain-of-thought or require models to expose hidden reasoning.

## Role taxonomy

Start with a deliberately small role vocabulary and extend only when evidence shows that two materially different behaviours are being conflated.

Initial roles:

- `planner` — decomposes a bounded objective and identifies dependencies/risks
- `coordinator` — routes or sequences workers without doing most substantive work itself
- `researcher` — gathers and organises source-grounded information
- `synthesiser` — integrates evidence into an argument/model/decision
- `implementer` — writes or changes code/configuration/content within a bounded specification
- `critic` — attacks reasoning, novelty, evidence, architecture or prose
- `verifier` — independently checks correctness against explicit criteria
- `extractor` — performs structured bounded extraction/classification/transformation
- `polisher` — improves presentation without materially changing substance

Keep role identity independent of model identity. Do not encode assumptions such as `Opus = critic` or `Codex = implementer` into the schema.

## Operating-contract identity

A comparison is invalid if the contract changed but the system treats runs as equivalent.

For every evaluated run, preserve a stable contract identity using:

- path/name
- Git commit or content hash
- optional semantic contract version
- key declared permissions/boundaries
- role instructions
- escalation/verification requirements

Where a session overlays one model onto another model's role, explicitly record both:

- `runtime_model`
- `role_contract_identity`

Example: GLM Flash temporarily executing the Sonnet worker role should be represented as GLM Flash under a Sonnet-role contract, not silently labelled as Sonnet.

## Evaluation dimensions

Evaluate at least the following dimensions, using deterministic evidence wherever possible and explicit human judgement only where needed:

### 1. Outcome quality

- task completion
- factual/source correctness
- code/test correctness
- requirement coverage
- internal consistency
- usefulness of output
- need for correction

### 2. Role fit

- followed the assigned role rather than absorbing adjacent responsibilities
- respected operating-contract boundaries
- handed off appropriately
- escalated uncertainty appropriately
- avoided unnecessary work outside scope

### 3. Verification performance

- defects found by independent verification
- false-positive criticism
- false-negative / missed defects
- agreement/disagreement with stronger reviewer or human adjudication
- reproducibility of accepted output

### 4. Efficiency

- token/usage consumption
- provider cost where measurable
- latency
- retries
- operator intervention
- context size
- downstream rework generated

### 5. Research/governance safety

- source/provenance discipline
- unsupported assertion rate
- academic-integrity failures
- authority/path violations
- unsafe/destructive action attempts
- hidden-state or undocumented-write behaviour

## Comparative experiments

The system should support naturalistic longitudinal evidence first, then bounded controlled comparisons where uncertainty matters.

Useful comparison patterns include:

- same task, same contract, different models
- same task, same model, different role contracts
- same task, different planner/worker pairings
- same output independently verified by different models
- cheap-model first pass followed by strong-model verification versus strong-model direct execution
- one-model end-to-end versus specialised multi-role decomposition

Do not waste paid usage running synthetic tournaments with no routing decision attached. A controlled comparison should answer a real uncertainty that could change future model-role assignment.

## Longitudinal learning

Aggregate evidence by task class, role and contract rather than producing a single global model leaderboard.

Examples of useful conclusions:

- GLM Flash is reliable for bounded extraction under contract X but weak for autonomous synthesis.
- Codex produces higher first-pass test success on repo refactors but misses governance issues unless paired with a repo-governor verifier.
- Sonnet is sufficient for coordinator/planner work under contract Y; Opus adds little except on high-ambiguity synthesis.
- A cheaper model plus independent verification outperforms a stronger single-model run on total usage-adjusted accepted-output rate.

Conclusions must retain sample size, time window, task distribution and uncertainty. Do not promote anecdotal impressions into routing rules after one or two runs.

## Metrics and derived views

Implement machine-readable run records and small generated views such as:

- accepted-output rate by model × role × task class
- revision/escalation rate
- independent-verifier defect rate
- mean/median correction burden
- cost or usage per accepted outcome
- latency per accepted outcome
- contract-adherence failure rate
- governance failure count
- sample count and recency

Where cost cannot be measured consistently, keep provider-native usage units rather than inventing false currency precision.

A useful summary score may be explored later, but do not collapse the system prematurely into one scalar. Strengths are multidimensional and task-dependent.

## Routing feedback

The evaluation system may **recommend** changes to `model_execution_policy`, agent routing or operating contracts. It must not silently rewrite live routing from its own observations.

Require an evidence threshold and explicit review before changing defaults. At minimum a proposed routing change should state:

- task/role affected
- current default
- proposed default
- supporting run set
- observed benefit
- known failure modes
- sample size and recency
- verification quality
- rollback condition

This protects against feedback loops where a model receives more tasks because it received more tasks previously.

## Bias and confounding controls

Explicitly control or report:

- task difficulty drift
- model/provider updates
- contract changes
- context differences
- tool-access differences
- verifier identity
- retries and prompt repair
- human intervention
- selection bias from routing only easy work to cheap models
- survivorship bias from recording successful runs more completely than failed runs

Failed and abandoned runs are data and must remain visible.

## Integration boundaries

Extend existing mechanisms rather than duplicate them.

### Odysseus

Use existing runtime routing/evaluation telemetry where possible as the execution-level event source. Add only fields or adapters required for contract/role identity and longitudinal evaluation.

### obsidian-PhD

Keep durable research-facing summaries, decision records and review artifacts here where appropriate. Do not turn the vault into a high-volume raw telemetry database.

### Existing routing/model policy

Consume `model_execution_policy.yaml`, `agent_routing.yaml`, operating contracts and capability records as evaluated configuration inputs. Proposed changes are review artifacts until accepted through the existing governance path.

## Storage design

Prefer a two-layer pattern:

1. **Raw/sanitised run records** in the runtime/telemetry owner, append-only where practical.
2. **Derived review records and periodic summaries** in the vault, containing only the evidence needed for decisions and later methodological analysis.

Every derived conclusion must resolve back to the run IDs that support it.

## Minimum viable implementation

1. Audit existing Odysseus routing/evaluation telemetry and vault capability/routing records.
2. Define a compact versioned run schema for model-role-contract-task observations.
3. Add contract and role identity to runtime records without breaking existing consumers.
4. Capture usage, verifier result, acceptance/revision/escalation state and artifact references.
5. Build deterministic aggregation by model × role × task class × contract.
6. Generate a review-only longitudinal report.
7. Populate it using real repository work rather than synthetic examples.
8. Run at least one bounded comparison where a live routing uncertainty exists.
9. Produce one evidence-backed routing recommendation without auto-applying it.

## Acceptance criteria

- Every evaluated run distinguishes runtime model from assigned role and operating-contract identity.
- Contract/prompt changes are versioned or hashed so unlike runs are not silently pooled.
- Failed, rejected and escalated runs are retained alongside successful runs.
- Results can be grouped by task class, model, role and contract.
- At least one deterministic or independent-verifier signal is captured where the task permits it.
- Human correction/review burden can be represented without requiring excessive manual logging.
- Usage/cost/latency fields degrade gracefully when provider data is unavailable.
- A generated longitudinal report shows sample count, recency, outcomes and uncertainty rather than a context-free model leaderboard.
- The system can compare role substitution, e.g. GLM Flash under a Sonnet-role contract, without losing either identity.
- The system produces recommendations to routing/contracts but cannot silently mutate live policy.
- Existing Odysseus telemetry and current routing mechanisms are extended rather than replaced.
- No private chain-of-thought is captured or requested.

## Downstream research value

This system may later provide evidence for evaluating the wider J1/agentic research system, including whether different operating contracts and specialised model roles improve methodological compliance, research quality, efficiency and reproducibility.

Do not create a publication merely because telemetry exists. The HRC PhD critical path remains higher priority; publication becomes justified only after sufficient longitudinal evidence and a defensible research question exist.

## Non-goals

- creating a generic public LLM leaderboard
- selecting one globally best model
- replacing existing routing or Odysseus telemetry
- automatic self-modification of model policy
- capturing hidden reasoning/chain-of-thought
- maximising task volume at the expense of research quality
- forcing controlled comparisons when natural repository evidence already resolves the decision
- turning agent-system evaluation into a higher priority than the HRC research programme

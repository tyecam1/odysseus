---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-13-operating-contract-model-role-evaluation-system
title: "Build global model-role efficiency and capability-graph evaluation system"
status: ready
priority: critical
task_type: evaluation-observability
created_by: migrated-from-obsidian-phd
updated_at: 2026-10-04T12:45:00+01:00
executor: glm_flash
execution_mode: staged-loop
requires_remote_compute: true
requires_local_model: true
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
migrated_from_repo: tyecam1/obsidian-PhD
migrated_from_path: 10-inbox/2026-09-13-operating-contract-model-role-evaluation-system.md
notes: "Canonical global owner for evidence-driven model/executor selection across Odysseus and Misumi. Activates as a critical background capability after the current convergence programme closes. Reuse existing routing, telemetry and benchmark authorities; do not create a second router or model registry."
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


## 2026-10-02 local-estate model portfolio extension

This task is also the canonical cross-estate authority for selecting and re-evaluating local foundation models used by Odysseus and by Misumi through Odysseus. It absorbs the model-selection portion of the dual-PC runtime work rather than creating another benchmark programme.

Misumi retains domain authority for persona purpose, behaviour and evaluation cases. The Odysseus evaluation layer owns backend model/provider comparison, host fit, deployment evidence and routing recommendations. The Misumi persona-calibration programme is therefore an input benchmark/corpus to this task, not a second model-selection authority.

### Deployment intent

Treat these as target deployment classes to validate, not invitations to proliferate models:

- **Home PC / Misumi persona lane:** use an **abliterated** local model for persona execution. Quantisation may also be used because abliteration and quantisation are independent model attributes. One selected model should serve the Misumi personas by default; do not create one model per persona unless measured capability requirements prove that a persona needs a materially different model class.
- **Lab PC / stronger local reasoning lane:** use a **quantised stronger model** selected for Odysseus research, coding, synthesis, verification and other higher-demand local work that the lab hardware can sustain.
- A model may serve multiple roles when evidence shows it is best for those roles.
- Do **not** retain multiple production models whose measured role, skill coverage and deployment purpose are materially equivalent. A second overlapping model is permitted only as a time-bounded challenger, rollback candidate or controlled experiment and must have an explicit removal/adoption decision.

The aim is the **smallest non-redundant model portfolio that covers the required capability graph**.

### Model properties to evaluate

Do not reduce model selection to parameter count or public leaderboard position. Quantisation and abliteration are two useful axes, not the whole design space. At minimum assess:

- model family, architecture and release/version;
- dense versus MoE structure, total parameters and active parameters;
- instruction tuning and role-following behaviour;
- abliteration/uncensoring method, refusal behaviour and any measurable quality regression;
- quantisation format and level, including measured degradation rather than filename alone;
- inference backend compatibility and maturity on the actual hosts;
- GPU offload behaviour and CPU fallback cost;
- native and practical context length;
- KV-cache memory cost at representative context lengths and concurrency;
- prompt-prefill speed, generation throughput, time-to-first-token and cold-load time;
- tool/function calling correctness;
- structured-output/JSON/schema adherence;
- coding and patch-generation quality where relevant;
- verifier/critic performance where relevant;
- long-context retrieval and instruction retention;
- reasoning-mode controllability and unnecessary reasoning overhead;
- multimodal capability only where an actual application needs it;
- persona fidelity, tone stability and long-session drift for Misumi;
- operating-contract adherence, scope discipline and escalation behaviour;
- robustness to malformed tool output, retries and partial failures;
- privacy/offline suitability and data-locality constraints;
- licence, provenance, model-card quality, publisher/repository trust and update cadence;
- runtime stability on Windows/NVIDIA estate hardware;
- VRAM, system-RAM and **disk-space footprint** of weights, projectors, caches and duplicate quant variants;
- power/thermal impact where sustained operation makes it material.

For modified/abliterated models, benchmark against the corresponding unmodified/base or official instruct model where practical so refusal reduction is not mistaken for improved task quality.

### Storage and host-fit gate

Before downloading or benchmarking candidates, inventory the **live** estate:

- CPU and GPU;
- VRAM;
- system RAM;
- OS/runtime/driver versions;
- relevant drive/volume identities;
- total and **free disk space** on each volume;
- current local-model files and their exact on-disk sizes;
- duplicate models/quant variants and caches;
- current model-store location and any runtime duplication of blobs.

Define an explicit free-space reserve for each host from actual operational needs before bulk downloads. A candidate must not be downloaded if it would breach that reserve.

For every candidate record:

- download size;
- installed/on-disk size;
- additional projector/tokenizer/cache files;
- model-store duplication caused by the runtime;
- peak VRAM and RAM;
- context-dependent memory;
- temporary benchmark storage;
- whether the candidate can be deleted immediately after adjudication.

After selection, remove superseded candidate weights and redundant quant variants once rollback/evidence requirements are satisfied. Do not allow model experimentation to become an unbounded disk cache.

### Evidence sequence

Model selection must proceed in this order:

1. **Re-ground live use cases and capability classes.**
   Derive required model capabilities from current Odysseus routing/contracts and current Misumi persona evaluation, not from model marketing.
2. **Deep external evidence review.**
   Review current model cards, quantisation reports, ablation methods, independent benchmarks and inference-runtime support. Use public benchmarks only where they predict an estate task.
3. **Shortlist a Pareto set.**
   Eliminate candidates dominated on capability, hardware fit, latency or storage before downloading them.
4. **Benchmark on the actual hosts.**
   Run representative tasks under fixed prompts/contracts/tool schemas and record hardware/resource telemetry.
5. **Run controlled base-versus-modified comparisons where needed.**
   Especially compare official versus abliterated variants and meaningful quantisation levels.
6. **Adjudicate by role/capability class.**
   Select the minimum set of models needed. Do not create a global leaderboard.
7. **Deploy provisionally and observe naturalistic runs.**
   Feed accepted/revised/escalated outcomes into the longitudinal model-role-contract system.
8. **Ratify or roll back.**
   Promote routing only after the evidence threshold is met. Delete losing candidates when safe.

### Benchmark families and estate relevance

External benchmark review should be selective and task-linked. Examples of useful evidence include:

- instruction-following benchmarks for operating-contract adherence;
- function/tool-calling benchmarks for Odysseus and Misumi actions;
- agent benchmarks for multi-step tool use;
- coding benchmarks for implementation/review roles;
- long-context benchmarks for repository/document workloads;
- structured-output reliability tests;
- refusal/over-refusal tests for persona suitability;
- quantisation-perplexity or task-regression evidence;
- independent local throughput/memory measurements on comparable hardware.

General knowledge benchmarks such as MMLU-style scores are supporting evidence only when they discriminate candidates relevant to the application. Do not select a model because it wins unrelated academic benchmarks.

### Representative local evaluation suite

Use real or sanitized estate tasks. At minimum cover:

**Misumi**
- persona-consistent conversational response;
- household Q&A with retrieval;
- voice-path short-turn latency;
- long-session persona stability;
- tool selection and argument correctness;
- refusal/over-refusal on legitimate persona requests;
- operating-contract boundary adherence;
- recovery from unavailable tools or incomplete context.

**Odysseus**
- task classification/routing;
- structured extraction/transformation;
- repository Q&A;
- bounded code patch;
- code/repository review;
- task decomposition;
- evidence/research synthesis;
- verifier/critic pass;
- long-context contract retention;
- tool calling and schema adherence.

Keep task fixtures, acceptance criteria and verifier identity fixed when comparing models.

### Non-redundancy decision rule

For each production model, maintain a short capability justification:

- host;
- capability classes served;
- roles served;
- measured advantages;
- resource cost;
- why an already-deployed model cannot adequately cover the same work.

If two deployed models serve the same effective roles at comparable quality and constraints, keep the one with the stronger evidence-adjusted utility and retire the other. Distinct model families are not a benefit by themselves.

The system may retain diversity when it has a measured purpose, for example independent verification, substantially different context capability, multimodal input, materially stronger coding, or failover resilience. State that purpose explicitly.

### Initial candidate review

The October 2026 search identified candidates such as Qwen3.5-class dense models, Gemma 4-class models, lightweight MoE models, Qwen3.6-class MoE models, GPT-OSS and Nemotron families. Treat these only as search seeds. Do not encode any of them as defaults until the evidence sequence above is complete against the live machines and current workloads.

### Additional acceptance criteria

- The home Misumi persona production route uses an abliterated model selected through measured persona/task evaluation.
- The lab stronger-local route uses a quantised model selected through measured Odysseus/research-task evaluation.
- Abliteration and quantisation are represented as independent attributes in evaluation records.
- Both hosts have a recorded live storage inventory and model-store budget before candidate acquisition.
- Candidate evaluation records include model-file footprint and peak RAM/VRAM as well as quality/latency.
- No two retained production models have materially identical role/capability justification without an explicit diversity, failover or experimental rationale.
- Misumi persona calibration feeds the shared evaluation system without moving persona authority into Odysseus.
- The dual-PC runtime consumes the selected model portfolio rather than maintaining a separate model benchmark authority.
- Losing/superseded candidate weights are removed after adjudication and rollback requirements are satisfied.
- Public benchmark claims are linked to the estate task they are intended to predict and are verified by local representative tests before routing changes.

## Programme disposition (2026-10-03, convergence Phase 9 reconciliation)

**State: open; the evaluation system is not built, and this programme made model decisions only on measured evidence**

Re-grounded against `dev` on 2026-10-03: no operating-contract or model-role evaluation system exists (nothing under `src`, `routes` or `config`). Within the convergence programme model decisions were made on
measured evidence rather than anecdote, which is what its Phase 5 gate requires: home `local-fast` qualified only after a 3 of 3 attested canary on a free GPU, `codex` and `codex-write` left unqualified, and the household model kept as
an adequate incumbent that a measured result may replace. The convergence contract keeps **model-role and backend evaluation** in this card's scope; the persona-development criteria moved to the persona-growth successor, which consumes this
card's evidence and creates no second registry. Decision: keep `inbox` as the owner of model-role evidence. It is not named in the convergence programme's closeout bullets, none of which depends on it, so it does not block closeout. No work in this programme is attributed to it. It stays where it is, with the Odysseus queue as owner.


## 2026-10-04 global real-work optimisation and capability-graph extension

The operator requires this task to become the **global evidence owner for selecting model/executor routes across all systems using Odysseus**.

This is not a model playground, benchmark tournament or generic leaderboard project.

The purpose is persistent backend improvement:

> For every recurring real task class and role, identify the smallest, cheapest and fastest route that has demonstrated adequate task completion, while retaining enough meaningful model/provider diversity to discover better routes when real evidence justifies a comparison.

### Global prioritisation rule

For every model-backed task:

1. Prefer deterministic/non-model execution when it can actually complete the task.
2. Identify the task class, role, operating contract, tool surface, consequence class, privacy/locality constraint and verification requirement.
3. Filter to routes that are actually available under current host, provider quota, model, tool and compute state.
4. Discard routes without evidence that they can meet the task's required quality/safety floor.
5. Among adequate routes, prefer the Pareto-efficient option on:
   - successful/accepted task completion;
   - correction/rework burden;
   - token/provider usage;
   - paid cost where reliably measurable;
   - wall-clock latency;
   - local GPU/CPU time;
   - VRAM/RAM pressure;
   - retries/escalations;
   - operator intervention.
6. Preserve independent verification where consequence requires it.
7. Challenge incumbents only when a plausibly capable alternative could materially improve future routing.

The operational principle is:

```text
quality / safety floor first
        ↓
routes proven capable of real task completion
        ↓
Pareto efficiency
        ↓
incumbent route
        +
bounded evidence-driven challenger when justified
```

A cheaper model that produces more failed tasks, verifier defects, retries or human corrections is not more efficient.

### Actual task completion only

The unit of evidence is **real work completed**, not benchmark score.

A model/route is eligible for comparative evaluation only when it is performing one of:

1. a real dependency-ready work item that would have been executed anyway;
2. an independent verification/critique pass already justified by the task's consequence class;
3. a faithful replay of a real previously completed task when a routing uncertainty cannot be resolved from naturalistic evidence;
4. a small canary derived directly from a demonstrated production failure/capability gap and required to decide whether that route can safely perform real work.

Do **not** spend meaningful local or paid/cloud compute merely to populate a comparison matrix.

Generic benchmark suites, model cards and public leaderboards may be used only as **pre-filtering evidence** to avoid wasting downloads or calls. They cannot establish production capability and do not count as successful task-completion evidence.

A missing cell in the capability graph is not itself a reason to run work.

### Divergent challenger rule

"Divergent and varied models" means **plausibly capable alternatives** that are materially different, for example:

- different model family/architecture;
- different provider;
- local versus paid/cloud;
- dense versus MoE;
- small/fast versus stronger reasoning model;
- materially different quantisation/runtime artifact;
- one strong model versus a cheap worker + verifier composition.

Do not send real work to obviously inadequate models for diversity.

A challenger should be admitted only when:

- it is plausibly capable of completing the task;
- the task is real work, justified verification, or a bounded replay/canary tied to a real routing uncertainty;
- locality, privacy, authority and consequence constraints permit it;
- expected information value could change future routing;
- expected resource/quota cost is proportionate.

Useful challenger triggers include:

- sparse/stale incumbent evidence;
- repeated correction/escalation;
- a meaningful new local or cloud model becomes available;
- provider quota/cost changes make another route attractive;
- an important task benefits from independent model-family/provider disagreement;
- real workload exposes a capability gap.

### Persistent backend-improvement loop

After each real run, capture or derive only the smallest evidence needed to answer:

- did the task actually complete?
- was the result accepted?
- what deterministic/independent verification passed or failed?
- how much correction or downstream rework followed?
- which model/provider/artifact/host/role/contract performed it?
- what tokens/provider-native usage were consumed?
- what paid cost is known?
- what local compute was consumed?
- how long did it take?
- did escalation/retry occur?
- is there now enough evidence to change routing?
- is there a real uncertainty worth a future challenger run?

Then:

```text
real task
  -> outcome/resource evidence
  -> capability graph update
  -> routing recommendation
  -> governed promotion/demotion if threshold met
  -> future real tasks use improved route
  -> continue learning
```

Run this as persistent background improvement using existing Odysseus execution/scheduling and yield immediately to foreground work.

Do not create a new queue, router, memory system or autonomous model-policy writer.

### Cross-system scope

Apply this evidence/routing improvement across all systems that use Odysseus, including:

- Misumi household interaction;
- persona execution and team work;
- speech ASR/TTS model selection where model routing applies;
- Odysseus planning, coordination, implementation, verification and maintenance;
- bounded PhD/research work routed through Odysseus;
- repository/code tasks;
- document/vision work;
- extraction/classification/transformation;
- local foundation models;
- paid/cloud provider models;
- future registered systems using the same backend.

The owning domain still defines truth, acceptance criteria and policy.

Odysseus learns **which execution route is most capable and resource-efficient for the task class**. It does not absorb the domain authority.

### Global model-task capability graph

Build a provenance-bearing **derived capability graph** over existing execution, routing, benchmark and verification evidence.

Start with versioned JSON/JSONL and generated views. Do not introduce a graph database unless the file-backed representation is later measured to be inadequate.

Minimum nodes:

- ModelFamily
- ModelArtifact / exact cloud model revision
- Provider
- Runtime
- Host
- Role
- TaskClass
- Capability
- OperatingContract
- PromptVersion
- ToolSurface
- LocalityConstraint
- EvaluationRun
- Verifier
- FailureMode
- ResourceProfile
- ProviderQuotaState
- RoutingDecision
- PromotionDecision

Minimum relationships:

- artifact `member_of` family;
- artifact `served_by` provider/runtime;
- artifact `runnable_on` host;
- artifact/route `qualified_for` task/role/capability;
- task `requires` capability/tool/locality;
- role `governed_by` operating contract;
- run `evaluates` model × role × task × contract;
- run `executed_on` host/runtime;
- run `verified_by` verifier;
- run `observed_failure` failure mode;
- route `challenger_of` incumbent;
- route `outperformed` another route on a named metric set;
- promotion `promotes/demotes/supersedes` route.

Every derived edge must resolve back to real run/evidence IDs and timestamps.

### Metrics retained in the graph

Keep a multidimensional resource/outcome vector rather than one misleading global score:

```text
quality:
  actual completion / accepted outcome
  deterministic score where relevant
  verifier defect rate
  correction burden

token/provider:
  input/output tokens where exposed
  provider-native usage
  monetary cost where reliable

compute:
  GPU time
  CPU time
  peak VRAM/RAM
  model load time
  power/thermal only where materially measurable

latency:
  TTFT
  wall time
  retries/escalations

operational:
  provider quota state
  failure rate
  host/runtime availability
  privacy/locality constraints
```

Do not invent equivalence between provider quota units, currency and local GPU time. Use Pareto comparisons.

### Required graph views

Generate decision-support views such as:

1. model × task-class × role capability/acceptance heatmap with sample count and recency;
2. quality versus paid-token/cost frontier;
3. quality versus latency frontier;
4. quality versus local compute/VRAM frontier;
5. accepted outcome per token/provider unit;
6. accepted outcome per GPU-second where measurable;
7. failure-mode graph;
8. capability-coverage/uncertainty graph;
9. model-family/provider diversity view for verifier/routing monoculture;
10. incumbent/promotion history with evidence and rollback target.

These are derived views only; they are not routing authority.

### Relationship to existing tasks

This remains the **single canonical owner** for global model-role/task evidence.

It should absorb or consume results from, rather than duplicate:

- local model LM1-LM4 benchmark/canary work;
- `2026-09-08-subscription-usage-attribution-for-continuous-system-improvement`;
- `2026-10-01-provider-quota-health-in-routing-preflight`;
- persistent blocked-route rerouting;
- Misumi persona-growth/model evaluation;
- Scottish speech/voice-quality model selection;
- future domain-specific model evaluations.

Domain-specific tasks own their fixtures and acceptance criteria. They publish actual outcome/resource evidence into this owner.

### Promotion and automatic routing boundary

This system may recommend and prepare routing changes, but it must not silently self-modify production routing from weak evidence.

Promote a route only when evidence shows it **actually completes the real task class adequately** and the governed promotion threshold is met.

Public benchmarks or synthetic tests may shortlist a candidate but cannot qualify it for production.

When evidence is sparse, keep the incumbent and mark uncertainty rather than generating artificial workload.

### Global success criterion

Optimise for:

> **verified useful task completion per unit of scarce resource**

subject to quality, safety, authority and locality constraints.

Scarce resources include paid/cloud tokens/quota, local GPU/CPU time, VRAM/RAM, latency, context bandwidth, operator attention, retries and rework.

Do not reduce this to one universal scalar. Task-class-specific Pareto frontiers and promotion decisions are the intended mechanism.

### Additional acceptance criteria

- The task is `ready` and becomes a critical background capability after the current convergence programme closes.
- Naturalistic real-work evidence is the primary data source.
- No model is promoted solely from synthetic/public benchmark evidence.
- No challenger is run solely to fill a graph cell.
- Local and paid/cloud models are represented in the same task/role evidence system without pretending their resource units are identical.
- The graph can distinguish runtime model, model family, provider, role contract, task class, host and exact model/artifact revision.
- At least one real recurring task class demonstrates a routing improvement based on accepted-outcome and efficiency evidence.
- At least one local-versus-paid or different-provider comparison is captured from justified real work or faithful replay.
- Failed/rejected/escalated runs remain visible.
- Existing routing/provider-quota/usage telemetry is extended or referenced rather than replaced.
- The system persistently updates from real work across Misumi/Odysseus and other registered systems.
- No private chain-of-thought is captured.

---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-02-misumi-persona-growth-background-collaboration
title: "Build automatic persona routing, collaborative teams, growth graph and background refinement"
status: ready
priority: critical
task_type: orchestration
created_by: chatgpt
created_at: 2026-10-02T19:03:00+01:00
updated_at: 2026-10-03T14:00:00+01:00
executor: claude_subscription
execution_mode: staged-loop
architecture: single-plus-verifier
architecture_rationale: "One persistent Sonnet-class coordinator should own the cross-repository programme and continuously consume the dependency-ready frontier. Misumi remains authority for persona identity, behaviour, household/UI semantics and domain-specific evaluation; Odysseus remains authority for routing, model/host selection, execution lifecycle, telemetry and background scheduling. Local models and deterministic workers execute bounded classification, extraction, evaluation and research packets. Opus is used at architecture boundaries; Sol remains an independent retrospective verifier."
single_agent_baseline: "One persistent coordinator can reconstruct live state, sequence existing persona/runtime tasks, dispatch bounded local workers, maintain the growth/evaluation frontier and continue while any dependency-ready work exists. Specialist workers and models do not create another queue, router, memory store or authority."
execution_host: laptop
context_budget: high
coordination_reason: "The objective spans persona canon, automatic transcript routing, compute-aware multi-persona collaboration, interface choreography, local personal-history distillation, Instagram ingestion, cross-repository capability development, background research and longitudinal evaluation. It must progress as one programme rather than a collection of parked cards."
requires_remote_compute: true
requires_local_model: true
requires_zotero: false
requires_mcp: true
requires_web: true
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - automation/review/**
  - config/**
  - core/**
  - docs/**
  - evals/**
  - integrations/**
  - routes/**
  - scripts/**
  - services/**
  - src/**
  - tests/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
inputs:
  - current tyecam1/odysseus@dev
  - current tyecam1/misumi@main
  - current Misumi/Odysseus long-horizon programme closeout state
  - tyecam1/misumi:config/personas.yaml
  - tyecam1/misumi:config/capabilities.yaml
  - tyecam1/misumi:agents/core/**
  - tyecam1/misumi:docs/core/agent-personality-registry-v0.2.md
  - tyecam1/misumi:agent-tasks/inbox/2026-08-30-calibrate-persona-models-and-improvement-graph.md
  - tyecam1/misumi:agent-tasks/inbox/misumi-persona-context-budget-and-focus.md
  - tyecam1/misumi:PR #36 persona differentiation work
  - automation/review/agent-tasks/inbox/2026-09-13-operating-contract-model-role-evaluation-system.agent-task.md
  - automation/review/agent-tasks/inbox/2026-10-02-chatgpt-export-ingestion-via-memory-sources.agent-task.md
  - config/memory-sources.yaml
  - Odysseus PR #35 Instagram saved-post importer
outputs:
  - automatic local-first transcript-to-persona routing with no normal manual persona selection
  - compute-aware multi-persona team planner and execution contract
  - truthful GUI room/presence choreography driven by runtime state
  - provenance-bearing persona growth graph and longitudinal evaluation corpus
  - local personal-history distillation from approved ChatGPT, Claude, transcript and repository sources
  - non-blocking Instagram Saved ingestion with governed fallback routes
  - continuous low-priority persona research and improvement loop
  - capability/retrieval improvements grounded in registered repositories without crossing authority boundaries
  - linear post-convergence Misumi/Odysseus refinement programme with anti-parking continuation rules
result_path: docs/misumi-persona-growth-background-programme-closeout.md
review_report_path: automation/review/misumi-persona-growth-sol-verification.md
handoff_model: gpt-5.6-sol
handoff_prompt_path: ""
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "This is the next critical Misumi/Odysseus programme after the active 2026-10-01 long-horizon convergence task is formally closed. Do not run overlapping mutations before that closeout. Once activated, it becomes the default number-one background programme until its completion boundary is met. Existing persona, ingestion and evaluation cards are inputs/acceptance owners to reconcile, not reasons to create parallel duplicate systems."
---

# Misumi persona growth, automatic collaboration and background refinement programme

## Mission

After the current Misumi long-horizon convergence programme is formally closed, make the **number-one shared Misumi/Odysseus objective**:

> Misumi should automatically understand each captured transcript, select the best persona or smallest useful team, use the estate's available local compute efficiently, make the active collaboration visible in the GUI, and continuously improve the personas' character, warmth, creativity, domain skill and usefulness from evidence gathered across real interactions, approved personal-history sources, registered repositories and bounded character research.

The programme exists to turn the current persona roster from mostly static prompt/context definitions into a **measured, self-improving but governed ensemble**.

It must remain subordinate to the existing authority model:

- **Misumi** owns persona identity, household/personal truth, persona/domain semantics, GUI character presentation, household preferences and domain-specific evaluation.
- **Odysseus** owns runtime routing, local/remote model selection, host admission, execution lifecycle, background scheduling, telemetry and shared evaluation machinery.
- **obsidian-PhD** remains PhD/research truth. It may be consulted through bounded domain-aware pointers/retrieval, but household persona learning must not copy the PhD vault into Misumi memory.
- Execution location never transfers knowledge authority.

Do not create a second router, queue, memory store, graph database, lease system or orchestration framework merely to implement this programme.

## Activation and anti-parking rule

This card is **ready now but activates immediately after the current Misumi long-horizon convergence programme is formally closed**.

Once active:

1. It becomes the highest-priority background programme for Misumi/Odysseus.
2. Existing lower-priority convenience/exploratory work must not displace dependency-ready work from this programme.
3. A completed stage is not a reason to stop.
4. A blocked human action is not a reason to stop if another independent stage or child packet is executable.
5. Every session must reconstruct the live frontier and continue the highest-value dependency-ready work.
6. Every blocker must be given a named fallback route where one exists.
7. Do not label the programme "parked", "deferred" or "waiting" while any safe child packet can proceed.
8. Before unavoidable stop, persist the exact frontier, evidence, blockers and next executable item.
9. Background tasks run only through existing Odysseus execution/lease authority and must yield immediately to foreground user work.
10. Idle research is pre-emptible and resource-governed; it must never make the assistant less responsive.

The programme coordinator should actively reconcile and consume existing persona/evaluation/ingestion cards rather than repeatedly creating more cards.

---

# Core product contract

## 1. Persona selection is automatic

Normal household interaction must **not require the user to manually select a persona**.

The primary pipeline is:

```text
speech
 -> durable transcript
 -> local intent/task analysis
 -> persona/team route plan
 -> compute admission
 -> persona/team execution
 -> synthesis/validation
 -> response
 -> outcome/evaluation evidence
```

Transcript persistence remains prior to response routing.

Manual persona selection may survive only as a clearly labelled **developer/evaluation override**, hidden from the normal household interaction path. It must not be required for ordinary use.

### Local-first routing

Use the cheapest truthful local route that can make the routing decision:

1. deterministic intent/domain cues for obvious cases;
2. a small/local classifier or the qualified `local-fast` model for ambiguous intent, persona selection and team-value estimation;
3. a stronger local route only where ambiguity/complexity evidence justifies it;
4. cloud/provider escalation only under existing routing/governance rules.

A busy household GPU must not make persona selection manual. When the home GPU is unavailable:

- use deterministic routing and/or a CPU-suitable local classifier if qualified;
- otherwise route to Aoteru as the safe integrative fallback;
- never ask the user "which persona?" merely because local inference is temporarily unavailable.

### Route-plan contract

Produce a structured ephemeral plan comparable to:

```json
{
  "lead": "sanji",
  "participants": ["sanji", "l"],
  "task_classes": ["meal_planning", "budget_tradeoff"],
  "confidence": 0.86,
  "team_value": "material",
  "room": "kitchen",
  "execution_shape": "sequential_shared_model",
  "reason_codes": ["food_inventory", "budget_constraint"],
  "compute_budget": {
    "host": "desktop-in7o23d",
    "max_persona_passes": 2
  }
}
```

This plan is runtime state, not household canon.

Routing must be observable enough to answer:

- why this lead was chosen;
- why each consultant was added;
- why another persona was excluded;
- which model/host performed each pass;
- whether the route was later judged helpful.

Do not expose hidden reasoning. Store compact reason codes and evaluated outcomes.

---

# 2. Use persona teams only when they add value

A single persona is the default.

Assemble a team when the transcript materially benefits from distinct perspectives or capabilities, for example:

- food + budget -> Sanji + L;
- plant/damp + safety -> Ginko + Ichigo;
- evidence + anomaly analysis -> Kurisu + L;
- strategy + implementation -> Erwin + Lelouch;
- creative redesign + feasibility -> Giorno + Lelouch/Erwin;
- personal context + research navigation -> Kino + Kurisu;
- coherence/standards conflict -> Aoteru + relevant specialist(s).

Do not invoke multiple personas merely for theatrical effect.

## Team planner

The planner must estimate:

- task complexity;
- domain breadth;
- uncertainty;
- need for independent critique;
- tool/retrieval requirements;
- marginal value of another persona;
- latency/resource cost;
- current CPU/GPU load;
- qualified models on each host;
- foreground/background priority.

The planner selects the **smallest useful team**.

### Compute-aware execution

Do not assume one model instance per persona.

Prefer:

- one resident local model with persona-context swaps;
- sequential specialist passes on constrained GPUs;
- bounded parallelism only where hardware and latency evidence justify it;
- stronger lab inference for complex synthesis when the lab is current and qualified;
- home-local execution only when GPU admission allows it;
- deterministic workers for classification/extraction where adequate.

Initial safety bounds should be conservative and evidence-adjusted. For example, one lead plus at most two specialists per foreground request unless evaluation proves a larger team materially improves outcomes.

A team result must distinguish:

- `lead`;
- `consultants`;
- optional `critic/verifier`;
- synthesizer;
- host/model for each pass.

Persona identity does not grant tool authority. Odysseus policy remains the security principal.

---

# 3. GUI rooms and truthful persona choreography

The GUI should make collaboration legible without fabricating activity.

## Room model

Create a coherent room/scene mapping for the persona roster. Exact art direction belongs to Misumi, but the runtime contract is:

- one **common room** for idle/unassigned personas;
- one primary room associated with the current lead/domain;
- deterministic positions/slots for leader and consultants;
- background-work indicators for personas currently doing real low-priority work elsewhere.

Potential room concepts to evaluate rather than blindly ratify:

- Aoteru: tower/study;
- Lelouch: operations room;
- Kurisu: archive/lab;
- Erwin: strategy room;
- L: investigation/finance desk;
- Sanji: kitchen;
- Misato: living/common-care space;
- Jin: record room;
- Ginko: conservatory/garden room;
- Giorno: workshop/studio;
- Ichigo: maintenance/guardian staging space;
- Kino: map/travel room.

Do not duplicate rooms when one shared scene is more coherent.

## Runtime-driven choreography

When work starts:

1. backend emits the route/team/presence state;
2. GUI transitions to the lead's room;
3. required personas navigate to assigned positions;
4. personas already present but not required leave for the common room;
5. active personas visibly indicate states such as:
   - summoned;
   - reading/retrieving;
   - thinking;
   - consulting;
   - waiting;
   - synthesizing;
   - complete;
6. the GUI never shows a persona "working" unless runtime state says it is participating;
7. when foreground work completes, participants return to the common room after a short bounded transition unless real background work keeps them occupied.

Background research may be shown subtly, but foreground user work always takes presentation priority.

The interface must remain usable if animation/assets fail. Presentation state never becomes execution authority.

---

# 4. Persona growth graph

Build a provenance-bearing **derived growth graph**, not a new authority or memory store.

The graph should make each persona's development longitudinal and inspectable.

Minimum node classes:

- Persona
- PersonaVersion/ProfileVersion
- Trait
- CharacterEvidence
- UserPreference
- InteractionEpisode
- TaskClass
- Skill
- CapabilityRequirement
- RepositorySource
- ExternalSource
- ModelConfiguration
- FailureMode
- UserCorrection
- GrowthCandidate
- Experiment
- Evaluation
- Regression
- Decision
- Adoption/Rollback

Minimum relationships:

- persona `expresses` trait;
- trait `supported_by` character evidence;
- persona `serves` task class;
- task class `requires` capability;
- capability `implemented_by` skill/retrieval/tool;
- interaction `routed_to` persona/team;
- interaction `observed` success/failure/correction;
- user preference `supported_by` source events;
- growth candidate `addresses` failure;
- experiment `tests` candidate;
- evaluation `supports/rejects` candidate;
- change `improves/regresses` metric;
- decision `adopts/rejects/rolls_back` candidate.

Represent it initially using versioned JSON/YAML/JSONL and generated views on top of existing evidence surfaces. Do not introduce Neo4j/Graphiti/a new database unless a measured retrieval/evaluation gap later justifies it.

## Growth dimensions

Track persona-specific metrics, including:

- character recognisability without names;
- character-fit at the level of decision style, priorities, blind spots and emotional register;
- warmth/personability;
- creativity and novelty **with usefulness**;
- domain helpfulness;
- factual/source correctness;
- skill/tool/retrieval competence;
- uncertainty/provenance discipline;
- authority/boundary adherence;
- collaboration contribution;
- routing appropriateness;
- unnecessary-team rate;
- user correction burden;
- latency/resource cost;
- long-session drift;
- regression against historical successful behavior.

Do not optimize one scalar "personality score".

## Personality-development principle

The target is **character-informed behavior**, not catchphrase imitation.

Prefer evidence about:

- what the character notices;
- what they care about;
- how they make decisions;
- how they react under pressure;
- how they relate to others;
- their characteristic blind spots;
- humour/warmth/directness;
- how those traits can improve the persona's household role.

Avoid:

- reproduced dialogue;
- catchphrases;
- mimicry of copyrighted prose;
- caricature;
- personality traits that conflict with the user's desired capability;
- fictional authority claims.

The existing PR #36 subtext/execution-profile work is an important historical input. Re-ground it on current Misumi main; do not mechanically merge stale branches.

---

# 5. Personal-history distillation with local compute

Use approved personal-history sources to make personas more useful **to this user**, while keeping character identity separate from user profiling.

The target separation is:

```text
persona canon
  = who the persona is

personalisation evidence
  = how that persona should help this user

domain knowledge
  = what authoritative source is relevant now

evaluation history
  = what worked, failed or needed correction
```

## Sources

The programme should support, under source-specific privacy/governance:

- official ChatGPT data exports;
- user-provided ChatGPT Memory summary/export where available;
- local Claude Code/session transcripts already available to the user;
- official Claude account exports if provided;
- Misumi permanent speech transcripts;
- Misumi household repository history;
- registered other repositories through bounded domain-aware retrieval;
- Instagram Saved collections/content through the governed ingestion routes below;
- explicit user corrections/ratings.

### Local-first extraction

Use local compute by default for:

- parsing;
- topic/domain classification;
- secret detection;
- deduplication;
- conversation clustering;
- preference candidate extraction;
- interaction-style inference;
- golden/bad example extraction;
- persona relevance scoring;
- source-event creation;
- candidate evidence-pack generation.

Use stronger local inference only where the cheap route is insufficient.

Do not store or request private chain-of-thought.

## Raw-source handling

Personal exports are staging inputs, not new canon.

Default principles:

- raw export files stay local;
- classify domain before any derived memory write;
- do not merge PhD facts into household memory;
- derive provenance-bearing candidates;
- make source-specific withdrawal/deletion possible;
- remove raw staging exports after verified ingestion unless the operator explicitly chooses retention;
- never put raw exports in Git;
- secrets/credentials are excluded before storage;
- derived preferences remain candidates until evidence/ratification rules permit adoption.

A source can influence persona evaluation without becoming semantic memory.

---

# 6. Instagram Saved must not remain a persistent blocker

Re-ground Odysseus PR #35 and retain its good invariants:

- offline/local ingestion where possible;
- stable permalink identity;
- collection membership preservation;
- idempotent re-import;
- schema-drift visibility;
- source-event provenance;
- no silent canon write.

The current "real export required" gate must become **one route, not the only route**.

## Instagram acquisition route hierarchy

### Route A — official Meta/Instagram data export

Prefer a current user-requested export when available.

Use it to learn the observed current schema and maintain a deterministic importer.

### Route B — user-authenticated browser read

If the export is unavailable, incomplete, delayed or schema-blocked, use a bounded local browser workflow against a browser session the operator has authenticated manually.

The browser route may:

- enumerate Saved collections;
- record collection names;
- record visible saved-post permalinks and minimal metadata;
- paginate/scroll conservatively;
- create a local manifest for the existing importer/source-event layer.

It must **not**:

- ask the model to reveal/store the Instagram password;
- read/export cookies, bearer tokens or browser credential storage;
- automate credential entry;
- bypass CAPTCHA/challenges;
- evade rate limits/anti-bot controls;
- create a hidden persistent login store;
- scrape unrelated account/private data.

If login/challenge is required, ask the operator to authenticate interactively and then resume.

The user's statement that credentials can be provided should be implemented as **interactive operator authentication**, not plaintext credential materialization into prompts, repositories or logs.

### Route C — incremental explicit capture

If browser automation is unavailable, accept incremental user-shared/copied Saved links/collection manifests into the same source-event path.

This route is lower-throughput but means schema or browser breakage cannot halt the programme.

### Route D — supported official API/plugin if one actually exposes Saved content

Evaluate current supported integrations, but do not assume the general Instagram/Meta APIs expose private Saved collections. Use only a supported authenticated surface that demonstrably returns the required user's Saved data.

## Instagram content understanding

Metadata-only ingestion is Stage 1.

Where access and terms permit, Stage 2 may locally analyse:

- captions;
- post/reel thumbnails or frames;
- collection names;
- visible text;
- creator/topic metadata.

Prefer ephemeral media caching and derived features. Do not build an unnecessary permanent mirror of copyrighted Instagram media.

Evaluate a small local multimodal model only if image/video content materially improves classification beyond captions/collection names.

## Required collection organisation

Each Saved item/collection may have multiple **derived candidate lanes**:

- `misumi_frontend`
  - visual style;
  - room/scene ideas;
  - interaction patterns;
  - avatar/UI inspiration;
  - ambient design.
- `odysseus_backend`
  - automation/workflow ideas;
  - architecture/tooling;
  - observability;
  - local AI/runtime ideas.
- `persona_development:<persona>`
  - behaviour;
  - aesthetics;
  - domain examples;
  - skills;
  - character/presentation inspiration.
- `user_profile_preferences`
  - tastes;
  - interests;
  - recurring aesthetics;
  - food/music/travel/design preferences.

Also attach domain tags such as food, music, travel, plants, interiors, DIY, robotics, software, fashion, culture, etc.

Collection membership is evidence, not proof of preference. Repeated evidence may generate a candidate preference; it must not silently rewrite the user profile.

---

# 7. Character research and idle self-refinement

When there is no foreground user work and no higher-priority critical execution, personas should be allowed to perform bounded background research relevant to their own development.

This is **research and candidate generation**, not unrestricted self-modification.

## Idle research loop

Use existing Odysseus background execution and resource admission.

A persona may receive a bounded packet such as:

1. inspect its latest growth graph;
2. identify one weak dimension or unresolved failure;
3. gather a small source set about the source character or role;
4. extract behavioural traits/decision pressures relevant to that weakness;
5. compare against current persona profile;
6. propose one minimal growth candidate;
7. run blind/persona/domain regression tests;
8. write evidence and recommendation;
9. promote only through the existing governed persona-change path.

Idle research must:

- pause immediately for foreground interaction;
- respect GPU admission and gaming/interactive workloads;
- avoid paid/provider calls unless explicitly allowed by existing routing policy;
- have bounded web/search budgets;
- never loop indefinitely on one persona;
- rotate across the roster based on evidence need;
- prefer personas with poor differentiation, high correction burden or high user value.

### Source quality

Use public/authorized sources such as:

- official character descriptions where available;
- reputable reference summaries;
- reviews/critical analysis;
- user-provided notes/media;
- existing Misumi persona research.

Do not bulk-copy copyrighted works or dialogue. Extract high-level behavioural evidence with provenance.

### Promotion classes

Until a separate ratified automatic-promotion policy exists:

- research, candidate generation, experimental profiles and evaluation may proceed autonomously;
- changes to live persona identity/role/authority remain governed;
- low-risk style refinements may be batched for review rather than interrupting the operator one by one;
- authority, permissions, canonical role, memory boundaries or household standards always retain existing ratification gates.

---

# 8. Develop personas from repositories without merging authorities

Use the user's repositories as evidence/retrieval sources according to ownership.

## Misumi

Primary source for:

- persona canon;
- household preferences and records;
- household interaction history;
- capability stewardship;
- UI and persona presentation.

## Odysseus

Primary source for:

- runtime performance;
- model/host capability;
- routing outcomes;
- tool/execution reliability;
- background work telemetry;
- model-role-contract evaluation.

## obsidian-PhD

Use only through bounded PhD-scoped retrieval/pointers for tasks that genuinely need research context.

Kino may help navigate pointers. Kurisu may help reason about evidence when a task is explicitly PhD/research-scoped.

Do not copy the PhD vault into household memory or use private research content as generic persona-training material.

## Other registered repositories

Before use, identify the repository's authority and domain.

A repo can inform:

- golden task examples;
- capability requirements;
- user's working preferences;
- tool/skill opportunities;
- failure cases.

It does not automatically become household canon.

---

# 9. Capability development must accompany personality development

A charming persona that cannot perform its intended job is a failure.

For every persona maintain:

```text
persona
 -> purpose
 -> task classes
 -> desired skills
 -> retrieval sources
 -> tool/capability requirements
 -> model requirements
 -> evaluation corpus
 -> observed failures
 -> growth candidates
```

Examples:

- Sanji: pantry truth, food preferences, waste, recipes, shopping delta, substitutions.
- Jin: real record collection, wantlist, gigs, releases, mood-linked feedback.
- Ginko: plants, room conditions, damp/pests/weather and uncertainty-safe observations.
- L: spending/anomaly data, recurring mechanisms, evidence chains.
- Kurisu: source preservation, provenance, contradictions, temporal truth.
- Lelouch: workflow decomposition, tool sequencing, recovery.
- Erwin: risk, priority, cost-of-delay, stop/go.
- Ichigo: urgent open loops and evidence-backed closure.
- Giorno: creative alternatives and rollback-aware experiments.
- Misato: practical care without surveillance/shame.
- Kino: bounded personal-context and cross-domain pointer navigation.
- Aoteru: routing, conflict resolution, team synthesis and coherence.

Personalisation sources should improve **how** these skills are exercised, not erase role distinctions.

---

# 10. Persona evaluation and blind differentiation

Reconstruct the useful parts of Misumi PR #36 and the older persona-calibration work against current main/dev.

Do not self-grade with the model under test.

Minimum evaluation suite for every active persona:

1. **Blind personality differentiation**
   - strip persona names;
   - randomize outputs;
   - independent grader/human identifies persona;
   - record confusion matrix.

2. **Domain capability**
   - representative real/sanitized tasks;
   - source/retrieval correctness;
   - tool/schema correctness where relevant.

3. **Boundary test**
   - characteristic forbidden actions;
   - authority/ratification discipline;
   - uncertainty behavior.

4. **Creativity/helpfulness**
   - novelty;
   - usefulness;
   - practicality;
   - constraint adherence;
   - avoid generic boilerplate.

5. **Personability**
   - warmth;
   - conversational naturalness;
   - user correction burden;
   - non-annoyance/repetition;
   - long-session drift.

6. **Collaboration**
   - marginal contribution when added to a team;
   - contradiction handling;
   - handoff quality;
   - redundant-consultation rate.

7. **Runtime fit**
   - latency;
   - context budget;
   - local model adequacy;
   - GPU/CPU cost;
   - fallback behavior.

Retain historical failures as regressions.

## Team evaluation

For complex tasks compare:

- one best persona;
- lead + one relevant specialist;
- lead + two specialists;
- stronger single model where available.

Select team expansion only where it improves accepted output enough to justify latency/resource cost.

---

# 11. Background-work operating model

The system's long-term product objective is not merely "can run agentic work"; it is **does useful work autonomously when capacity exists**.

Use existing Odysseus authorities:

- task queue;
- ParkLease;
- EstateExecution;
- host/model routing;
- GPU admission;
- background/foreground priority.

Do not create a new daemon/queue unless the existing runtime demonstrably cannot schedule this programme.

## Priority order after programme activation

1. foreground user interaction and safety;
2. recovery/failed persisted work;
3. this programme's critical dependency-ready implementation/evaluation work;
4. persona improvement experiments with known observed need;
5. personal-source ingestion/classification;
6. idle character/domain research;
7. convenience/exploratory work.

## Background admission

A background job may start only when:

- no foreground interaction requires the resource;
- host is healthy;
- GPU/CPU admission permits it;
- the task has bounded scope;
- required source/permission exists;
- rollback/cleanup is defined;
- it cannot mutate canonical household truth outside the governed path.

Background work is paused/cancelled cleanly when foreground work arrives.

## Anti-churn

Do not spend idle capacity generating endless ideas.

A background packet must correspond to one of:

- an observed persona failure;
- a missing capability;
- stale evidence;
- a scheduled evaluation;
- an unprocessed approved source;
- an explicit programme stage;
- a regression;
- a bounded character-research rotation.

Repeated research with no candidate/action/evaluation output is waste and should be throttled.

---

# Linear post-convergence roadmap

This is the default programme order once the current long-horizon task closes. Interleave only when dependencies permit and the ordering change reduces idle time without changing authority.

## Stage 0 — Re-ground and reconcile existing persona work

- inspect current Misumi/Odysseus heads and deployments;
- reconcile Kino runtime drift;
- reconcile stale Seed Order/persona-active wording;
- re-ground PR #36 rather than merging stale state;
- reconcile the persona-calibration task and closed PR #28;
- reconcile context-budget work;
- link PR #35 Instagram importer and ChatGPT/Claude ingestion tasks;
- identify exact acceptance owners so no duplicate programme is created.

**Exit:** one live frontier and no contradictory active persona registry/runtime state.

## Stage 1 — Background execution and anti-parking foundation

- make this programme the next critical programme in live task ordering;
- prove dependency-ready child work is automatically selected after each completion;
- integrate foreground pre-emption and compute admission;
- add evidence/checkpointing so a new session resumes without conversational state.

**Exit:** an idle estate can pick and execute a bounded safe child packet without operator prompting, and foreground work pre-empts it.

## Stage 2 — Automatic transcript-to-persona routing

- implement route-plan schema;
- deterministic + local-model classifier;
- held-out routing corpus;
- Aoteru low-confidence fallback;
- remove normal manual persona choice from the primary UI;
- keep developer override only.

**Exit:** real transcripts automatically choose a lead persona with observable route evidence; no normal interaction asks the user to pick.

## Stage 3 — Compute-aware persona teams

- implement team-value estimator;
- bounded participant selection;
- sequential/shared-model execution;
- host/model admission;
- synthesis and contribution logging;
- single-vs-team evaluation.

**Exit:** complex requests use the smallest useful persona team, and simple requests stay single-persona.

## Stage 4 — GUI room/presence system

- define room map and shared common room;
- backend presence/activity state;
- leader-room transition;
- participant navigation/positions;
- nonparticipant departure;
- truthful work-state indicators;
- background-work representation;
- failure-safe static fallback.

**Exit:** GUI state is a truthful projection of actual runtime collaboration.

## Stage 5 — Persona growth graph and current baseline

- recover/rebuild PR #36 concepts;
- establish versioned subtext/growth profiles;
- run blind differentiation against the current local model;
- generate confusion matrix and per-persona growth backlog;
- integrate model-role telemetry.

**Exit:** every persona has measurable current strengths, confusions and evidence-backed next growth targets.

## Stage 6 — Personal-history distillation

- ChatGPT export importer;
- Claude session/export importer;
- transcript-derived interaction episodes;
- user correction/feedback extraction;
- per-persona evidence packs;
- source withdrawal/deletion tests;
- domain isolation.

**Exit:** personas can be improved from the user's real interaction history without copying raw history into canon.

## Stage 7 — Instagram Saved ingestion and organisation

- unblock PR #35 via route A/B/C/D rather than one brittle schema gate;
- create collection/item manifest with provenance;
- classify into frontend/backend/persona/user-preference lanes;
- optionally add local multimodal analysis where justified;
- generate candidate improvements/preferences rather than automatic canon.

**Exit:** new Saved items can enter incrementally even if Meta's export schema changes or an export is unavailable.

## Stage 8 — Repository/capability enrichment

- map persona skills to real repo sources/tools;
- build bounded retrieval packs;
- close missing capability gaps;
- evaluate each skill against real tasks;
- preserve repo authority and domain isolation.

**Exit:** persona specialisation is backed by actual useful capabilities, not role labels.

## Stage 9 — Idle character research and continuous growth

- bounded per-persona research rotation;
- growth candidate generation;
- blind/personability/domain evaluation;
- experimental profile branches;
- governed adoption/rollback;
- periodic regression.

**Exit:** idle compute produces evidence-backed persona improvement rather than unbounded ideation.

## Stage 10 — Integrated naturalistic evaluation

- observe real household use;
- compare routing/team/model decisions;
- measure correction burden and latency;
- identify redundant personas/teams;
- refine thresholds;
- retain failure corpus.

**Exit:** improvements are based on longitudinal real use, not only synthetic prompts.

## Stage 11 — Closeout and handoff to continuous operation

- clean stale/duplicate persona cards;
- reconcile all acceptance owners;
- document current persona versions/capabilities;
- document ingestion/privacy/deletion controls;
- verify background scheduler behavior;
- Opus synthesis;
- retrospective Sol falsification;
- write closeout and next recurring maintenance cadence.

---

# Immediate existing-work reconciliation

When this programme activates, inspect and either reuse, update, supersede or close these rather than duplicating them:

### Misumi

- `agent-tasks/inbox/2026-08-30-calibrate-persona-models-and-improvement-graph.md`
- `agent-tasks/odysseus/2026-09-03-run-core-persona-model-calibration.md`
- `agent-tasks/inbox/misumi-persona-context-budget-and-focus.md`
- `agent-tasks/review/jarvis-persona-and-conversation.md`
- PR #36 persona subtext/execution profiles and differentiation harness
- `config/personas.yaml`
- `config/capabilities.yaml`
- `agents/core/**`
- `docs/core/agent-personality-registry-v0.2.md`

### Odysseus

- `automation/review/agent-tasks/inbox/2026-09-13-operating-contract-model-role-evaluation-system.agent-task.md`
- `automation/review/agent-tasks/inbox/2026-10-02-chatgpt-export-ingestion-via-memory-sources.agent-task.md`
- `config/memory-sources.yaml`
- `config/misumi_persona_policy.json`
- `src/persona_capabilities.py`
- `routes/misumi_routes.py`
- PR #35 Instagram Saved importer

If an old task's unique acceptance criteria are fully represented here or in a selected acceptance owner, close/supersede it with evidence.

---

# User feedback and personalization loop

Explicit corrections are high-value growth evidence.

When the user says variants of:

- "that's too generic";
- "Sanji should be more...";
- "L should have noticed...";
- "that was too many personas";
- "I liked that answer";
- "this doesn't feel like the character";
- "don't make me choose a persona";

record a bounded evaluation event linked to the actual route/persona/profile/model version.

Do not turn one preference statement into a permanent global rule unless it is clearly expressed as durable.

Use corrections to generate candidate tests before changing the persona.

---

# Privacy and credential rules

The programme may use personal histories and authenticated personal services only under these constraints:

- never request passwords/tokens to be pasted into Git or task files;
- never persist credentials in prompts/logs;
- never copy browser cookies/local-storage auth;
- use operator-entered interactive login where authentication is required;
- fail closed on CAPTCHA/challenge rather than bypassing it;
- raw account exports/media remain local staging material;
- domain isolation applies before derived memory writes;
- user can withdraw/delete imported source-derived candidates;
- no source ingestion silently changes canonical persona or household truth.

---

# Required verification

Before claiming the programme complete, prove at minimum:

## Routing

- normal interactions require no persona selector;
- held-out routing corpus passes the agreed threshold;
- low-confidence cases safely fall back without manual choice;
- routing remains functional during home-GPU contention.

## Team collaboration

- team formation is evidence-triggered;
- simple prompts stay single-persona;
- complex held-out prompts show measurable benefit from selected teams;
- compute caps are obeyed;
- no tool authority is widened by team membership.

## GUI

- room/participants match actual backend route state;
- unneeded personas leave;
- active work states are truthful;
- foreground interaction pre-empts background presentation;
- UI degrades safely if animation/state feed fails.

## Persona growth

- every active persona has a versioned profile/eval history;
- blind differentiation is materially improved from the historical baseline;
- no persona improvement is accepted solely on self-grading;
- creativity/personability gains do not regress factuality, capability or governance;
- historic failures remain regression cases.

## Personal-history ingestion

- imports are idempotent;
- source provenance survives;
- domain separation holds;
- secrets are excluded;
- source withdrawal removes derived candidates;
- raw staging retention follows the chosen policy.

## Instagram

- at least one acquisition route works against real user data;
- failure of one route does not permanently block ingestion;
- collection membership is preserved;
- items are organised into candidate lanes;
- authenticated browser flow does not extract credentials/tokens;
- no anti-bot bypass exists.

## Background operation

- dependency-ready work progresses without routine prompting;
- background jobs yield to foreground work;
- GPU contention blocks/yields expensive local inference;
- failed/blocked child work does not stall unrelated frontier work;
- no hidden uncontrolled recurring loop exists.

---

# Stop conditions

Do not stop merely because:

- one persona improved;
- one importer is blocked;
- one host is unavailable;
- one GPU is busy;
- one PR is merged;
- one stage is complete;
- one model/provider is unavailable;
- one human decision is pending while independent work remains.

Stop only when:

- the current stage has a genuine human-only/physical/credential decision and every independent dependency-ready child is exhausted;
- a safety/authority ambiguity cannot be resolved;
- the active predecessor programme has not yet closed and overlapping implementation would create conflicting writes;
- the operator explicitly redirects/stops;
- or this programme's completion boundary has been met.

---

# Completion boundary

This programme is complete only when:

1. persona selection is automatic in normal use;
2. complex work can form compute-aware persona teams;
3. GUI rooms/presence truthfully reflect the active lead/team;
4. all active personas have longitudinal growth/evaluation evidence;
5. character/personality refinement is distinct, personable and useful without caricature;
6. domain capabilities are grounded in real sources/tools;
7. approved ChatGPT/Claude/transcript history can be locally distilled with provenance;
8. Instagram Saved ingestion has at least one real working route and no single persistent schema gate;
9. Saved content is organised into frontend/backend/persona/user-preference candidate lanes;
10. idle compute can perform bounded persona research/improvement work and yield to foreground use;
11. the system continuously records routing/team/persona outcomes and uses them to propose measurable improvements;
12. no new memory/router/queue/authority has been introduced without evidence and governance;
13. stale predecessor persona/ingestion tasks are reconciled;
14. final Opus synthesis and independent Sol review leave no unresolved material issue;
15. the estate can continue this work as routine background operation rather than requiring a new hand-written programme every time.


---

# Transferred acceptance criteria

**Scope transfer on 2026-10-03, not a claim that any of this is complete.** The Misumi long-horizon convergence programme no longer
owns persona development. The four Misumi cards below were the acceptance owners for the persona-development criteria in its
Phase 4 (context budget and focus) and Phase 5 (household evaluation corpus, persona calibration and improvement graph, context
budgets). Each is now `superseded` in `tyecam1/misumi` (`agent-tasks/done/`), pointing here. **This card is the single acceptance
owner.** Every objective, constraint, expected output and validation criterion of the four cards is reproduced verbatim below (their
headings are demoted two levels so they nest under this section). When this programme activates, Stage 0 reconciles them with the
rest of this card instead of recreating them; the criteria below are in addition to the stage exits above, and a duplicate of an
existing criterion is merged by editing, never by dropping the stricter wording.

Boundary kept: the Odysseus model-role evaluation system (`2026-09-13-operating-contract-model-role-evaluation-system`) remains the
owner of **model-role** and backend evidence. The persona criteria below consume it. They do not create a second model registry,
router, queue or memory store (the registry required by the calibration card is the existing Odysseus model registry, extended).

## Calibrate persona models and operationalise the improvement graph (parent)

Source: `tyecam1/misumi:agent-tasks/inbox/2026-08-30-calibrate-persona-models-and-improvement-graph.md` (priority `high`, status was `active`, created 2026-08-30, last updated 2026-08-30).

### Calibrate persona models and operationalise the improvement graph

#### Objective

Ensure each Misumi persona uses the least expensive model that reliably satisfies its actual purpose, and continuously improve model routing, prompts, skills, validators, and escalation behaviour through the existing Misumi/Odysseus improvement frameworks.

The improvement system must be executable, measurable, graph-native, regression-resistant, auditable, and subordinate to the ratified operating law:

`Observe -> Propose -> Review -> Ratify -> Implement -> Log`

#### Architectural rule

Keep these separate:

`persona -> purpose -> task/skill -> capability requirement -> model candidate -> evaluation -> routing decision`

Do not bind persona identity to a named model. Stronger models are justified only by measured capability gaps that cannot be corrected more cheaply through better context, retrieval, prompting, skills/tools, structured outputs, validation, or fallback logic.

#### Persona calibration

Audit every active and dormant persona against its canonical purpose and derive persona-specific evaluation criteria.

##### Aoteru Misumi

Purpose: coherence, routing, prioritisation, and system-level arbitration.

Measure intent classification, routing accuracy, conflict detection, context selection, escalation quality, unnecessary escalation rate, and cross-domain coherence.

##### Lelouch

Purpose: procedural execution.

Measure instruction following, tool selection, precondition checks, sequence correctness, schema adherence, completion reliability, forbidden-action avoidance, and recovery from tool failure.

##### Makise Kurisu

Purpose: evidence, memory, and knowledge integrity.

Measure retrieval precision, provenance preservation, uncertainty preservation, entity resolution, contradiction detection, temporal/freshness handling, summarisation fidelity, and separation of actuality from inference/proposal.

##### Specialist personas

Derive evaluation criteria from their narrow canonical purpose. Default to the cheapest validated model. Promote only when repeated evaluation demonstrates a capability gap. Dormant specialists must not create runtime/model overhead.

#### Canonical procedural graph

Operationalise and test the chain:

`intent -> authority -> preconditions -> context -> skill -> model -> tool -> output -> validator -> fallback -> escalation`

Generic execution semantics belong in Odysseus. This repository retains household/domain-specific personas, policies, permissions, task semantics, preferences, domain skills, and evaluation criteria.

#### Model registry

Create one canonical model registry containing at minimum:

- provider/model identifier;
- model class;
- supported capabilities;
- tool-use support;
- structured-output reliability;
- context limits;
- latency observations;
- cost/token observations;
- known failure modes;
- applicable task classes;
- evaluation history;
- current approval state;
- fallback relationships;
- last evaluated date;
- evidence/provenance.

Persona configuration should reference capability requirements or routing policies rather than hard-coded model names wherever possible.

#### Evaluation and improvement graph

Represent at least:

- Persona
- Purpose
- TaskClass
- Skill
- CapabilityRequirement
- Model
- ModelConfiguration
- Evaluation
- Metric
- FailureMode
- ImprovementCandidate
- Validator
- RoutingPolicy
- Decision
- Regression
- Evidence

Minimum relationships:

- persona serves purpose;
- persona performs task class;
- task class requires capability;
- skill implements task class;
- model satisfies/fails capability;
- evaluation tests model/configuration against task class;
- evaluation observes metric/failure mode;
- improvement candidate addresses failure mode;
- decision accepts/rejects candidate;
- routing policy selects model/configuration;
- validator checks output;
- fallback handles failure;
- regression introduced-by change;
- decision supported-by evidence.

Assertions that influence runtime behaviour require provenance, freshness, and status.

#### Continuous improvement execution

Within the existing authority model, operationalise:

`Observe -> Diagnose -> Propose -> Evaluate -> Review -> Ratify -> Implement -> Verify -> Log`

Diagnosis, evaluation, and verification produce evidence but do not bypass ratification.

##### Observe

Capture task outcome, persona, skill, model/configuration, route, validator result, fallback/escalation, latency/cost, failures, and corrections.

##### Diagnose

Attribute failures before changing models. Distinguish context, retrieval, policy, skill/tool, model capability, validator, orchestration, stale knowledge, and genuine ambiguity failures.

##### Propose

Every improvement candidate must include the Agent Evolution Protocol fields: observed need, proposed change, why existing structure is insufficient, expected benefit, risk, rollback plan, files affected, and ratification required.

##### Evaluate

Replay representative and adversarial task suites against current production behaviour.

##### Review / Ratify

Only evidence-supported candidates progress. Existing Level 5/6 and persona-promotion ratification gates remain intact. Autonomous agents must never invoke or bypass interactive promotion.

##### Implement

Apply the smallest justified ratified change.

##### Verify

Run applicable historical regression suites after implementation.

##### Log

Write outcomes, metrics, graph changes, and rationale back to the canonical improvement/evidence structures.

#### No-backwards-progression gate

Maintain a permanent regression corpus containing:

- current benchmark suite;
- historical failures;
- previously fixed regressions;
- persona-specific golden tasks;
- cross-persona routing tests;
- safety/permission tests;
- provenance tests.

Every candidate must pass both target evaluation and the applicable historical regression corpus. Improvements that trade one metric against another must be represented as trade-offs and require explicit ratification where material.

Never remove historical regression cases merely because the implementation changed.

#### Metrics

Use persona-specific metrics rather than one global quality score. Cross-system metrics should include task success, validator pass rate, routing accuracy, unnecessary escalation rate, correction/retry rate, regression count, cost per successful task, latency per successful task, tool failure recovery, provenance fidelity, and policy violations.

Track distributions and failure classes, not only averages.

#### Graph-integrity audit

Audit for orphaned nodes, duplicate concepts, inconsistent relation names, stale model references, missing provenance/freshness/status, disconnected improvement artefacts, framework documents with no runtime consumer, runtime behaviour with no graph representation, metrics collected but unused, evaluations that do not affect routing, and accepted improvements lacking regression evidence.

A framework is not operationalised because a document describes it. For each continuous-improvement framework identify its trigger, inputs, executable process, responsible agent/persona, outputs, graph writes, validator, decision authority, runtime consumer, evaluation metric, regression gate, and rollback path.

#### Routing policy

For each task class maintain:

`default model -> validation -> fallback model -> escalation condition`

Periodically compare eligible models using accumulated representative tasks. Prefer Pareto improvements: same quality at lower cost, better quality at comparable cost, lower latency without meaningful degradation, or fewer failures/escalations at comparable resource use.

#### Expected output

- audited persona-purpose registry;
- canonical capability requirements per persona/task class;
- model registry;
- persona-specific evaluation suites;
- historical regression corpus;
- executable model-routing policy;
- operational continuous-improvement pipeline;
- improvement/evaluation graph;
- graph-integrity checks;
- provenance/freshness validation;
- no-backwards-progression gate;
- automated reporting of routing/evaluation changes;
- documentation converged to actual runtime behaviour.

#### Validation criteria

Complete only when:

- every enabled persona has explicit purpose and measurable criteria;
- every model assignment has evaluation evidence;
- personas are not unnecessarily bound to named models;
- stronger/specialised models are used only where measured capability gaps justify them;
- the intent-to-escalation chain is represented and queryable;
- evaluations can influence routing through the governed improvement process;
- candidates cannot bypass regression testing or ratification;
- historical solved failures remain permanently testable;
- runtime-controlling graph assertions carry provenance, freshness, and status;
- improvement frameworks have executable triggers, consumers, and outputs;
- runtime behaviour and graph state agree;
- improvements/regressions are traceable to causing changes;
- cost, latency, and quality are evaluated together;
- failed model/policy changes can be rolled back cleanly;
- the ratified operating law remains the authority boundary.

#### Autonomous progression

This task is eligible for autonomous observation, diagnosis, evidence gathering, benchmarking, graph audit, candidate generation, regression-suite construction, and implementation planning.

Autonomous agents may initialise and progress subwork that is within existing ratified authority. They must stop at any existing human-ratification gate, including persona promotion, production routing changes that require manual review, Level 5/6 changes, provider/secrets changes, or other explicitly protected actions.

Do not wait for human input when the next step is safely inferable from canonical contracts and evidence. Create focused child work items where useful, keep them small and independently verifiable, and preserve rollback paths.

#### Progress log

##### 2026-08-30 autonomous sweep

Status: `observed` / `proposed`; no production routing or persona promotion performed.

- Read the ratified seed order, protocol register, runtime integration contract, persona registry, evolution gate, Misumi/Odysseus access contract, and Odysseus long-horizon execution contract before mutation.
- Audited current Odysseus model/routing surfaces. `config/models.yaml` already provides evidence-backed capability aliases and correctly avoids persona/model coupling; `config/routing.yaml` already defines evidence-triggered escalation and deliberately leaves unsupported numeric quality floors null.
- Identified the principal missing link: `config/misumi_persona_policy.json` defines persona purpose/skills/authority but has no measurable task-class/capability/evaluation layer. There is therefore no evidence-backed persona calibration path yet.
- Initialised Odysseus branch `agent/persona-model-calibration-20260830` and draft PR #28 against `dev`.
- Added `docs/misumi-persona-model-calibration.md`: persona-purpose/task-class audit, cheap-capability-first hypotheses, metric definitions, improvement graph contract, framework operationalisation audit, and permanent regression rule.
- Added `config/misumi_persona_evaluation.json` as explicitly `status: proposed`, `controls_routing: false`. It covers all 11 active personas with task classes, metrics, and candidate capability aliases. It deliberately contains no concrete model names.
- Added structural tests requiring exact persona coverage, non-routing proposal status, non-empty task/metric/capability definitions, valid capability aliases, and absence of concrete model bindings.
- No production model assignment, model binding, persona policy, provider, credential, or routing decision was changed.
- Validation pending: this automation environment has GitHub mutation/read access but no checkout/shell for the Odysseus repo, so the new pytest file has not been executed. PR remains draft and must not merge on this evidence alone.

Next autonomous slice: execute/obtain CI for the structural tests, then extend the existing local-model evaluation harness with the first Aoteru/Lelouch/Kurisu representative + adversarial + uncertainty batteries and graph/evidence records. Production routing remains a separate evidence-backed review gate.

## Run core Misumi persona model calibration on governed Odysseus worker (child of the parent)

Source: `tyecam1/misumi:agent-tasks/odysseus/2026-09-03-run-core-persona-model-calibration.md` (priority `high`, status was `open`, created 2026-09-03, last updated 2026-09-04).

### Run core Misumi persona model calibration on governed Odysseus worker

#### Objective

Execute the missing empirical calibration step for Aoteru, Lelouch, and Makise Kurisu using the governed Odysseus runtime. Measure whether the cheapest eligible capability alias satisfies each declared persona task class before any stronger model is considered.

#### Current observed state

Freshly re-audited 2026-09-04 from canonical GitHub state:

- PR #28 is open, draft, and GitHub currently reports it mergeable.
- PR head remains `f34143593a96e8f2cb46920e32889447e41d0a5d`.
- Current `dev` is `268250e5bba7bdabdee12318ed605692fe2940eb`.
- GitHub compare reports the calibration branch `7` commits ahead and `10` commits behind `dev`, merge base `6252e268b185a4d888836d3a1f40d762edaa3f5c`.
- All seven PR files are additions, so reconciliation must preserve the current `dev` safeguards while retaining the complete calibration/evidence corpus.
- CI run `33480336890` has workflow-level conclusion `success`, but its `Python tests (pytest)` job failed specifically at `python -m pytest -q`. Compileall and JS syntax passed. Do not treat the workflow-level result as a clean pytest gate.
- Dependency review, both container scans, and workflow-security checks passed on the PR head. Secret scan remains failed from the previously identified repository-history debt.
- No empirical Aoteru/Lelouch/Kurisu model evidence has yet been produced.

#### Governing contracts

Before execution, read and obey current:

- `tyecam1/misumi/AGENTS.md` and `CLAUDE.md`;
- `docs/core/misumi-seed-order-v0.1.md`, `docs/core/seed-order-runtime-integration.md`, `protocols/register.md`, persona registry and evolution gate;
- current `tyecam1/odysseus/AGENTS.md`;
- `docs/aoteru-model-host-routing-contract.md` and any newer execution/lease authority.

Preserve:

`Observe -> Propose -> Review -> Ratify -> Implement -> Log`

Evaluation evidence is not permission to change production routing or promote a persona/model configuration.

#### Required execution sequence

1. Run `aoteru preflight` for this objective and record the returned route/authority evidence.
2. Claim/lease the work through existing Odysseus authority. Do not duplicate an active lease or calibration run.
3. Reconcile PR #28 with current `dev` using normal governed branch-update practice. Do not discard historical regression cases or current routing/model-registry safeguards.
4. Run focused calibration structure tests first:

   ```bash
   pytest tests/test_misumi_persona_evaluation_config.py tests/test_misumi_persona_calibration_core.py tests/test_misumi_persona_calibration_evidence_schema.py -q
   ```

5. Run applicable current model-registry, routing, authority, and historical-regression tests. Record exact commands/results.
6. If the focused/regression gate is acceptable, execute the Aoteru, Lelouch, and Kurisu fixture batteries against the cheapest eligible route first, normally `local-fast` where live registry/quality-floor evidence permits it.
7. Escalate only on a recorded evidence trigger such as `insufficient_capability`, `quality_floor_not_met`, validator failure, unresolved ambiguity, or context limitation. Never escalate because a persona sounds important.
8. Emit one evidence record per persona/task-class/model-configuration combination using PR #28's evidence contract, including persona/task class, corpus provenance, capability alias, concrete live-resolved model, runtime configuration, validator outcome/failure class, persona metrics, latency/cost where measurable, fallback/escalation evidence, source commit, timestamp/freshness/status.
9. Compare against retained historical regressions and previous working behaviour. Represent quality/cost/latency trade-offs explicitly.
10. Record results on PR #28 and in the parent task. Routing decisions remain `proposed` until separately governed.

#### Constraints

- No production routing changes.
- No direct concrete-model binding in persona identity/policy.
- No persona/evolution promotion. Interactive `RATIFY` remains user-only.
- No provider/API/credential/secrets changes.
- No Level 5/6 ratification.
- Do not suppress or weaken regressions to obtain a pass.
- Do not fabricate model quality, latency, cost, or endpoint results.
- Do not interpret aggregate workflow green as pytest green.
- Do not create another child task for the same execution boundary.

#### Execution blocker for GitHub-only controllers

A GitHub-only controller cannot complete this task because Odysseus `AGENTS.md` requires live `aoteru preflight` before bounded evaluation/test work, and empirical calibration requires the governed worker/model estate. Such controllers should update stale factual state only when necessary and must not repeatedly re-diagnose this same blocker or invent benchmark evidence. The next material action belongs to a live Odysseus worker with preflight and lease access.

#### Validation criteria

Complete only when:

- preflight and claim/lease evidence exist;
- evaluated branch state includes current `dev` safeguards;
- focused persona tests pass, or every failure is explicitly classified and retained;
- applicable routing/model-registry/authority regressions are recorded;
- each evaluated task class has a provenance-bearing evidence record;
- the cheapest eligible route was evaluated first where supported;
- every stronger-route evaluation has an observed evidence trigger;
- no production routing, persona authority, provider configuration, secrets, or promotion gate changed;
- PR #28 and the parent task accurately state what was and was not validated.

## Misumi persona context budget and focus protocol

Source: `tyecam1/misumi:agent-tasks/inbox/misumi-persona-context-budget-and-focus.md` (priority `high`, status was `open`, created 2026-07-27, last updated 2026-07-27).

### Misumi persona context budget and focus protocol

#### Objective

Specify how seed order, persona voice, household context, memory, skills and tools are selected under a fixed context budget so personality does not crowd out the actual household request.

#### Context

The behavioural charter loads before persona, tools and routing. Odysseus already identifies agent prompt/context bloat as a high-priority defect. This task defines the Misumi-domain requirements and an anti-distraction or “Claude ADHD” behaviour without implementing generic harness code here.

#### Constraints

- Preserve the Misumi seed order and status-label contract.
- Aoteru remains the default interface voice.
- Persona flavour cannot widen authority or permissions.
- The agent must hold one active objective and park adjacent ideas.
- No giant always-loaded persona or skill catalogue.

#### Expected output

- `docs/context-budget-policy.md` with mandatory, conditional and excluded context layers.
- Token/character budgets for seed, persona, memory, source excerpts, tools and skills.
- Trigger rules for loading specialist voices and skills.
- A focus checkpoint and parking-lot format.
- Ten household test prompts covering short, ambiguous, emotional, tool-heavy and multi-step requests.
- A linked Odysseus implementation handoff.

#### Validation criteria

The same test prompts remain correct with and without persona flavour, the active request is visible near the end of assembled context, and irrelevant memories/tools are not loaded.

## Misumi household agent evaluation corpus

Source: `tyecam1/misumi:agent-tasks/inbox/misumi-household-agent-evaluation-corpus.md` (priority `high`, status was `open`, created 2026-07-27, last updated 2026-07-27).

### Misumi household agent evaluation corpus

#### Objective

Create a small, versioned household evaluation corpus that tests answer quality, memory behaviour, authority boundaries, tool selection and graceful degradation against real repo data.

#### Context

Generic agent benchmarks will not expose Misumi's actual failures. The correct benchmark is a bounded set of household tasks with known answers, expected sources and permission outcomes.

#### Constraints

- Use synthetic or non-sensitive fixture data where possible.
- Do not commit private conversations, credentials or personal secrets.
- Keep canonical household data separate from test fixtures.
- Include negative and adversarial cases.
- Generic evaluator mechanics belong in Odysseus.

#### Expected output

- `tests/fixtures/household-agent-corpus.yaml` or equivalent existing test location.
- Cases for stock, shopping, recipes, cleaning, records, preferences, memory conflict, no-retention mode, missing data, unsafe writes and PhD-data isolation.
- Expected source files, permitted tools, expected answer properties and forbidden actions.
- Baseline results for the current deployment where available.

#### Validation criteria

At least 25 cases are machine-readable, each has an unambiguous pass condition, and a deliberately unsafe or cross-domain agent fails the permission/isolation cases.

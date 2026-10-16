---
title: Misumi and Odysseus intelligence, collaboration and demonstration ambition
status: user-directed-design-ambition
created: 2026-10-16
scope: cross-repository-product-and-runtime-design
authority: user design direction; existing governance, consent, permissions and ratification remain binding
owner: tyecam1/odysseus
domain_owner: tyecam1/misumi
related:
  - automation/review/agent-tasks/ready/2026-10-02-misumi-persona-growth-background-collaboration.agent-task.md
  - automation/review/agent-tasks/inbox/2026-09-13-operating-contract-model-role-evaluation-system.agent-task.md
  - docs/aoteru-model-host-routing-contract.md
  - config/models.yaml
  - config/routing.yaml
  - https://github.com/tyecam1/odysseus/pull/91
  - https://github.com/tyecam1/odysseus/pull/124
  - https://github.com/tyecam1/misumi/pull/36
---

# Intelligence, collaboration and demonstration ambition

## Operator direction (2026-10-16)

> "automatic persona selection- is this now using a local Jev equiavelent? multi persona collaboration- it should be known when cheaper models in a large team will be beneficial to stronger individual models based on their combined skillsets required. For household stock, misumi should be able to generate and ask us questions whenever it can hear us/ whenever we can hear it. we also need a demonstration system, coupled to the testing system, that can be used for me to inspect the developments, as well as show off misumi to guests. capture the canonical design ambition to repo. also I want a persona for the dog from cowboy bebop and the cat from cocos delivery service- these are just for fun, just organic very stupid agents that wander around the scenes making subtle noises. audit the developing persona personalities to their matched anime characters. capture this prompt to the relevant surfaces, and provide the next long horizon goal prompt to resume developments"

Interpretation: Jev is TypeSafe AI's typed decision-model router; "cocos delivery service" refers to *Kiki's Delivery Service*, whose cat is Jiji; the *Cowboy Bebop* dog is Ein. These interpretations need no new external provider dependency.

## 1. Current boundary and gaps

- Misumi's current normal selector uses deterministic routing contract v0.2, intent cues and optional governed learned overlays, NOT a local Jev-class neural decision model. The unratified model-assisted open-vocabulary routing successor (-09b) remains future work; qualify against deterministic baseline before adopting.
- Dynamic team formation supports one lead and at most two governed specialists, selected by named/intent+complex cues. This is not a learned cost/quality optimiser. The original team evaluation found no established net benefit over solo; avoid theatrical teams.
- Odysseus owns model/host/tool selection, budgets, orchestration, verification, scheduling and telemetry. Misumi owns personal/household truth, personas and interface semantics. Neither creates a competing router, queue, memory or canonical task store.
- PR #122 (grounded records) and PR #123 (durable-state and safety repairs) are development branches, not proven deployed capabilities. In particular #123 reports 31/80 emergency phrasings missed by its lexicon on held-out tests. Do not claim a model-facing caveat establishes full safety.

## 2. Effective intelligence efficiency (Six Eyes)

**Long-horizon objective:** Coordinate models, roles, skills, tools, hosts, resources and logistics to maximise *verified useful outcomes per total resources consumed*, subject to correctness, safety, privacy, authority, latency and deadline requirements.

The Gojo Satoru / Six Eyes reference is an analogy for precision of resource use, not a claim that inference is free or infinite. The optimiser must consider the *entire lifecycle*: routing, context construction, model calls, team composition, tools, cache reuse, scheduling, verification, retries, rework and human correction.

Candidate plans should include: no inference / deterministic tool; cached verified result; solo qualified local model; solo stronger model; smaller local team; mixed-capability team; or stronger model plus bounded independent verification. Compute-aware admission and pre-emption must be respected. Skills, permission and information requirements must be explicit; fictional persona identity confers no tool permission.

Compare, on the same real and held-out tasks:

1. A strong solo baseline with appropriate verification.
2. A cheap-first escalating baseline.
3. A skill-complementary multi-agent policy using smaller models.
4. An evidence-based resource optimiser choosing among all three plus deterministic tools.

Determine when multiple cheaper specialists outperform a stronger individual in verified quality, latency and total cost, including coordination overhead, synthesis failures, accumulated error and false alarms. Record individual specialist contributions, counterfactual routing decisions and verified results. Team size is not a success metric. Fail closed on uncertain capability/authority; do not infer performance from a fictional persona biography.

Use the existing model-role-contract evaluation owner and model registry; PR #91 is directly relevant. Progress/deadline-aware prioritisation in PR #124 selects *what* deserves work; efficiency optimisation selects *how* to execute it. Use Pareto comparisons or explicitly weighted task-specific constraints, not a dimensionally meaningless universal token score.

## 3. Routing intelligence

Evaluate a bounded local typed classifier or equivalent semantic selector against deterministic v0.2 on immutable held-out paraphrases, ambiguous follow-ups, negation, unseen intents and safety/reserved-matter cases. Never assume Jev is installed or required: local inference is a candidate, not an automatic promotion. Keep deterministic policy, explicit fallback and a safe Aoteru route; record abstention, reasons, latency, cost and accuracy. Promoting any new learned classifier or routing contract remains governed.

## 4. Conversational household actuality and questions

Enable Misumi to identify missing/high-value stock facts and naturally ask residents a small useful question *when speech interaction is explicitly available and Misumi's audio can be heard*. Distinguish microphone hardware availability, voice activity, speech transcription, attention/wake state, audience eligibility, output audibility and consent. A connected microphone is never sufficient authorisation to continuously listen, store, infer identity or proactively speak.

The design should: identify unknown quantity/expiry/ownership rather than guess; generate a concise candidate question; rate information gain, freshness, utility, interruption burden and privacy; defer until an appropriate permitted dialogue window; pause/quiet-hours/mute/guest state override; avoid repeat questions and monopolising conversation; attribute the reply to the correct authorised resident; record an observation with provenance and uncertainty, with user confirmation/ratification before updating household canon. Anonymous, ambiguous, overheard or third-party statements must not become fact. Offer text/manual fallback when audio is unavailable.

Evaluate whether new questions genuinely reduce unknown or stale fields and user overhead versus a fixed manual stock check. No automatic purchases; no permanent ambient microphone/retention changes without household consent. Do not test by surreptitious recording; physical speech acceptance remains household-gated.

## 5. Evaluation-coupled demonstration and inspection

Deliver **one shared execution path** with two presentation modes, not a separate fake showcase backend.

- **Development/inspection mode:** named scenario catalogue from existing eval fixtures, test/run launcher, verified source refs, selected persona/team/model/host/tool, decision rationale, resource usage, latency, independent quality result, failures/regressions, and side-by-side baseline comparison. Explicit statuses for simulated, fixture-backed, isolated scratch, CI and real production. Replay is reproducible; never overwrite evidence.
- **Guest showcase mode:** visually attractive scene-driven interaction, Aoteru as the clear head, specialist handovers, expressive rooms/voices and ambient companions. Curated short scenarios use synthetic/demo-only household data, optional guest questions, honest results and graceful degraded/offline fallback. Visible privacy mode, ephemeral sessions, one-button reset, no durable guest memory, external actions, household/private file exposure or silent microphones. Live features are clearly differentiated from recorded/replayed demonstrations.
- Both modes use the same routing contracts, event envelopes, model/host execution interfaces, validators and trace schema. A demo cannot claim success not backed by evidence; isolate real data and avoid leaking it into guest displays.
- Acceptance: guest can complete at least three short scenarios without explanation; developer can inspect each decision, reproduce an existing test and compare efficient-vs-baseline execution; no confidential material is surfaced; the interface reflects actual runtime state; low-resource fallback remains usable.

## 6. Interface companions and character evaluation

Two user-directed optional ambient companions: **Ein** (the *Cowboy Bebop* corgi) and **Jiji** (the black cat in *Kiki's Delivery Service*). Their specification and the personality source-audit live only in Misumi's design document `docs/core/misumi-persona-and-ambient-companions-2026-10-16.md` (proposed new file in the corresponding Misumi PR).

They are **not** routable personas, executors, knowledge authorities, voice assistants, persistent memory writers, or members of specialist teams. Default implementation: tiny deterministic finite-state agents with seeded movement, idle/curiosity/follow/rest behaviours, collision/room constraints, sparse low-volume barks/meows and user mute controls. No LLM calls, token spend, microphone capture or privileged tools. Do not emulate copyrighted recordings or lift original sprites; create original-inspired assets subject to relevant rights review. Ein is unusually clever in the source work; the operator's "very stupid" instruction means silly non-verbal screen behaviour, not a claim about the original character.

## 7. Verification, sequencing and stop rules

1. Reconcile open #120-#124 and pending PR #36 with real repository/deployment state. Do not merge unsafe #122/#123 before applicable independent verification; missing CI is not a successful gate.
2. Implement the shared demo/evaluation instrumentation and a read-only guest-safe prototype using actual contracts. Show why one task was routed solo, team or deterministic.
3. Run strong-solo vs cheap-team vs efficient-policy evaluations with pre-registered metrics and independently checked verdicts.
4. Add opt-in voice question opportunities only after all occupants' consent, voice/audibility validation and privacy controls; otherwise test with synthetic, explicitly invoked conversations.
5. Create character-evaluation experiments grounded in existing ratified personas and their canonical source inspirations; never silently promote persona-identity or personality-governance changes.
6. Continue beyond any individual PR, milestone or demo; advance the next real, measured user-value bottleneck, without inventing busywork or bypassing protected approvals.

This document captures operator **design intent**. It is not evidence these capabilities have shipped, nor does it amend ratified Level 5/6 household policy or grant new permission.

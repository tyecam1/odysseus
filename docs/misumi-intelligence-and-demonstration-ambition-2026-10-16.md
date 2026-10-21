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

---

## 2026-10-16 supplementary operator direction: spacecraft HUD, dynamic roles and Spotify

Full Misumi-domain specification: `tyecam1/misumi:docs/design/ftl-hud-and-jin-music-ambition-2026-10-16.md` (proposed in Misumi PR #68). This is additive user design direction, not confirmation of deployment or ratification of new household access.

### HUD / original scene preservation

Refine the existing 2D spacecraft, work-node/room map and HUD visuals to more intentional FTL-inspired pixel-art: tactile 8/16-bit panels, stronger differentiated green/warm-hull/deep-space palettes, legible node states and typography, pixel icons, high-resolution starfields/planets/nebula backgrounds and proper hitbox/keyboard/touch operation. Fix the user's reported broken 2D interactions with reproduced tests, not only screenshots. Preserve the existing ratified low-poly PS2 3D room scenes **without restyling/removing/changing geometry or rigs**; only add complementary animations/characters or truthful events after visual review.

Reference asset update (2026-10-16): the earlier uploaded `Better_Planets_and_Backgrounds_v1.3.2.zip` held only a README, but the user has since shown four actual `.ftl` mod packages in the **confirmed local OneDrive folder** `C:\Users\tyeca\OneDrive\Pictures\Misumi\design-references`: `Better Planets and Backgrounds_v1.3.2.ftl`, `better_asteroids.ftl`, `nebula_2x_original_res.ftl`, and `nebula_original_res.ftl`. The `.ftl` format is a mod archive, not a directly renderable browser image; first verify OneDrive local hydration, list/archive-test with 7-Zip or compatible tools, then extract only candidate texture images into a separate non-Git scratch folder, leaving originals intact. User screenshot proves names/location, not internal assets. **Operator clarification, 2026-10-16:** the actual space images contained in those archives are intended for **direct use in the private, locally deployed Misumi 2D spacecraft HUD / visual demo**, not merely stylistic reference. Inspect/extract/convert locally as necessary, retain image provenance, and integrate into a locally controlled asset/deployment path with performance and offline fallbacks; do not alter the existing PS2 3D rooms. The user's local-use direction does not itself establish public redistribution rights, so check asset permissions separately before embedding those third-party files in Git or distributing them publicly. Frontend work is owned by Misumi; execution telemetry and model state by Odysseus. Note existing `bbc-route-b.css` and `bbc-pixel.js` refer to `docs/design/bbc-visual-system-v1.md`, absent on inspected Misumi main: reconcile the pointer before assuming its authority.

### Task-specific persona roles, skill requirements and tool/MCP assignment

Distinguish three independent axes:

1. **Persona identity** (Misumi canon, character decision style and domain competencies, stable under ratified rules).
2. **Ephemeral task assignment** (coordinator/researcher/critic/music-selector/synthesiser/etc., with explicit requested competence and an evidence-based persona/team choice).
3. **Execution binding** (qualified concrete model/host, tool/MCP endpoint, scoped operation, credential principal, verifier, resource budget), chosen by Odysseus *per task* from the existing capability registry.

No permanent `persona -> model` or `persona -> provider/MCP` bindings. A user-facing persona may request a task capability, but cannot gain credentials, permissions or authority by identity. Define semantic tool capability requirements at plan time and bind a live qualified executor under least privilege only at execution. Local Jev-like typed/classifier inference or a qualifying planner may propose work assignments; benchmark against current deterministic routing and strong solo with held-out tasks before promotion. Expertise must be evidenced by task success, not fictional source character assumptions. Six Eyes evaluates which specialist mix is cheaper/better than a stronger solo model, counting total tool+model+verification+coordination cost, quality, failure and latency. Respects existing host admission and scheduler.

### Jin/Spotify MCP

Jin is the conversational specialist for music taste, intent and recommendations; **Odysseus** owns the provider-agnostic `music.*` tool capability and authorised Spotify-MCP binding. Target spoken/typed commands: play/search/queue/pause/resume/next/volume/device/now-playing. Do not bind a Spotify token to Jin or create an additional tool router. Implement against an existing provider-agnostic tool capability interface with Spotify OAuth2 PKCE, minimal official playback scopes, secure token storage, principal/device-aware write authorisation, idempotency, revocation, no unprompted playback, guest isolation and mock/demo adapter. Only after the operator completes the required OAuth account connection and Spotify Premium/device eligibility. No hardcoding of open-source MCP implementation without security/release review. Spotify Web API development-mode access, quota/rate limits and policy restrictions must be validated before live deployment. No synchronised Spotify audio with visual media or copied music assets. Keep Spotify listening data separate from canonical record ownership.

Acceptance should include an actual authenticated playback/skip/pause/queue drill on the chosen Spotify Connect device, negative read-only and guest tests, clear error paths and source/trace/provenance. Never claim connected Spotify access until OAuth and production tests prove it. This provider integration is subordinate to the existing tool registry and work orchestration, not a new stand-alone service.

### Extension to demo/evaluation programme

Show the ship HUD and 3D room as distinct complementary views. A task inspection should expose persona identity, temporary work roles, selected models/hosts/MCP tools, user scopes, resource cost, verifiers and whether a real Spotify command ran or was only demo-simulated. Guest showcases may show a fake playlist interaction without exercising owner's Spotify account. Visual comparisons must preserve existing PS2 scene snapshots and test functional 2D HUD paths at native 1024x768.

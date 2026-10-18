---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-01-misumi-long-horizon-session-operating-contract
title: "Run the Misumi long-horizon convergence programme across Misumi and Odysseus"
status: inbox
priority: critical
task_type: orchestration
created_by: chatgpt
created_at: 2026-10-01T12:30:00+01:00
updated_at: 2026-10-03T14:00:00+01:00
executor: claude_subscription
execution_mode: staged-loop
architecture: single-plus-verifier
architecture_rationale: "One persistent Sonnet-class coordinator owns programme continuity and task routing. Opus is a bounded planner/synthesizer at macro-phase and architecture boundaries. Sol is the fresh-context independent verifier/adjudicator. Other deterministic/local/Codex/GLM workers may execute bounded packets but do not replace these three programme roles."
single_agent_baseline: "A single Sonnet laptop session can reconstruct live state, maintain the programme frontier and execute or dispatch bounded work. It must not self-plan every consequential architecture decision or self-certify stage completion."
execution_host: laptop
context_budget: high
coordination_reason: "The programme spans two repositories, three physical computers, persistent runtime state, privacy-sensitive microphone capture, multihost execution and a large stale backlog. Continuity must stay with one orchestrator while planning and verification remain independent."
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: true
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - automation/review/**
  - docs/**
  - config/**
  - routes/**
  - services/**
  - src/**
  - core/**
  - companion/**
  - scripts/**
  - tests/**
  - migrations/**
  - evals/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*.pdf"
inputs:
  - tyecam1/misumi live default branch and unresolved agent-task queue
  - tyecam1/odysseus live dev branch and shared agent-task queue
  - tyecam1/misumi:docs/audits/2026-10-01-misumi-odysseus-voice-gui-integration-audit.md
  - tyecam1/misumi:agent-tasks/inbox/2026-10-01-misumi-ambient-transcript-interface.md
  - automation/review/agent-tasks/inbox/2026-10-01-misumi-durable-transcript-runtime.agent-task.md
  - docs/aoteru-model-host-routing-contract.md
  - config/estate.yaml
  - config/routing.yaml
  - config/initialising-prompts.yaml
outputs:
  - completed or explicitly retired/superseded Misumi unresolved portfolio
  - qualified home and laboratory compute for truthful Misumi execution
  - reliable persistent transcript path and low-friction interface
  - converged memory/runtime/persona/evaluation surfaces
  - reviewed Phase-B or explicit decision to retain read-only operation
  - compact programme evidence and application traces
result_path: docs/misumi-long-horizon-programme-closeout.md
review_report_path: automation/review/misumi-long-horizon-sol-verification.md
handoff_model: gpt-5.6-sol
handoff_prompt_path: docs/initialising-prompts/misumi-long-horizon-programme-v1.md
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "The queue snapshots below are discovery baselines, not frozen truth. Every session starts by reconciling them against live repository and runtime state. This programme must not create a second queue, router, lease authority, memory authority or cross-repo knowledge store."
---

# Misumi long-horizon convergence programme

## Mission

Carry Misumi from its current partially converged state to a dependable, low-friction household assistant backed by Odysseus, with durable microphone transcripts, truthful home/laboratory compute routing, coherent memory, strong recovery, measured model use and a cleaned backlog.

The persistent user-facing priority is:

> Misumi should continuously and visibly capture speech into a durable text transcript, use Odysseus as its shared runtime, and be able to exploit both the home and laboratory PCs as governed compute workers without moving household knowledge authority out of the Misumi repository.

This is a **programme operating contract**, not one implementation card. It remains active across as many CLI sessions, branches, stage loops and worker packets as necessary until its completion boundary is met.

## Authority model

Preserve these boundaries throughout:

```text
tyecam1/misumi
  household/personal truth
  Misumi domain policy
  interface/capture UX
  persona/domain-specific capability
  domain task queue

tyecam1/odysseus
  shared backend/runtime
  sessions and runtime memory machinery
  model/provider routing
  home/lab host routing
  leases/execution lifecycle
  shared orchestration/telemetry
  transcript runtime storage
  global initialising-prompt register

tyecam1/obsidian-PhD
  PhD/research truth and PhD-domain queue
```

Execution location does not transfer knowledge authority.

Do not reintroduce shared/backend task authority into Misumi merely because the programme concerns Misumi. Do not move genuinely Misumi-specific UI/privacy/persona tasks into Odysseus merely because Odysseus executes them.

## Programme roles

### Sonnet: persistent orchestrator

The laptop Claude CLI Sonnet session is the foreman and continuity owner.

Sonnet must:

- start from live repository/runtime state every time;
- maintain the current programme frontier;
- classify and sequence the task portfolio;
- invoke Opus and Sol at the required gates;
- choose or dispatch bounded implementation workers through existing Odysseus mechanisms;
- protect repository/host authority and avoid overlapping writes;
- preserve evidence, commits, PRs, task status and continuation state;
- continue through eligible work instead of stopping after one child task;
- use deterministic/local workers where they are adequate rather than spending premium reasoning on mechanical work.

Sonnet may implement bounded changes itself when that is the clearest route. It must not convert convenience into architecture authority or certify its own consequential changes.

### Opus: planner and synthesizer

Use an Opus-class Claude route for **bounded high-value reasoning**, not as a second long-running coordinator.

Mandatory Opus gates:

1. initial programme triage and architecture synthesis after live-state reconstruction;
2. before a macro-phase whose architecture is still materially ambiguous;
3. when live state contradicts the current programme contract;
4. before introducing a new persistent store, replication/failover mechanism, daemon, authority boundary or major UX mode;
5. at the end of each macro-phase to synthesize outcomes, retire stale assumptions and frame the next phase.

Provide Opus with a compact evidence packet. Do not ask it to rediscover the whole estate from prose.

Opus plans/synthesizes. Sonnet remains the programme owner.

### Sol: independent verifier/adjudicator

Every consequential stage closes with a fresh-context Sol-class verification pass through the repository's real existing OpenAI/Codex/Sol route.

Sol must be given:

- the governing task/phase contract;
- the actual live diff/commits;
- relevant implementation files;
- exact test commands/results;
- runtime evidence;
- known pre-existing failures;
- explicit falsification questions.

Sol is independent and read-only. It does not edit the implementation it judges.

Sonnet must resolve every substantiated material finding before stage acceptance. If Sol and the implementation owner disagree, use evidence, tests and if needed an Opus architecture synthesis. Do not resolve disagreement by majority vote.

### Other worker lanes

The programme may use:

- deterministic scripts;
- local-fast and local-strong models;
- GLM/Z.AI;
- Codex implementation workers;
- other currently qualified Odysseus lanes.

These are execution resources under Sonnet/Odysseus routing. They do not replace the Sonnet/Opus/Sol role contract.

## Long-horizon continuation rule

Do not stop merely because:

- one task completed;
- one repository PR was opened;
- one model/provider is quota-limited;
- one host is unavailable;
- one source route is blocked;
- one macro-phase reached a checkpoint.

Use the existing persistent blocked-route and multihost machinery to continue the smallest unaffected scope.

A session stops only when:

- a real human-only approval/consent/credential/physical-presence gate is reached and no independent work remains;
- all currently executable frontier items are blocked by named conditions;
- the local environment lacks required access that cannot be replaced by an eligible route;
- the programme completion boundary is reached;
- the operator explicitly redirects or stops the programme.

Before any unavoidable session end, checkpoint state so the next registered initializer application resumes from live evidence rather than conversational memory.

## Session start protocol

Every substantive Sonnet session must:

1. Resolve `misumi-long-horizon-programme` from the Odysseus initialising-prompt register and record the version/application id.
2. Fetch/prune relevant remotes and inspect:
   - `tyecam1/odysseus@dev`;
   - `tyecam1/misumi@main`;
   - open relevant PRs and active branches;
   - dirty worktrees/leases/in-flight EstateExecutions.
3. Never overwrite an existing dirty operator/agent worktree. Use the existing parking/worktree authority or a fresh isolated worktree.
4. Read:
   - this contract;
   - the Misumi 2026-10-01 re-entry audit;
   - the durable transcript runtime card;
   - the ambient transcript/interface card;
   - current multihost routing/estate contracts;
   - task/status surfaces materially relevant to the current frontier.
5. Reconstruct the live task portfolio. The appendix below is only a baseline.
6. Re-check home/lab reachability, worker qualification and currently available model/provider routes before dispatch.
7. Ask Opus for the initial programme synthesis if no current same-programme synthesis exists against the present live state.
8. Select the smallest high-value executable frontier and begin. Do not return to the operator merely to describe a plan that can be executed.

## Task portfolio policy

Every unresolved task must be classified as one of:

- `critical_path`
- `enabling_dependency`
- `domain_convenience`
- `exploratory_evaluation`
- `human_gated`
- `duplicate_consolidated`
- `completed_stale_status`
- `superseded_obsolete`

Classification is evidence, not deletion.

When two or more old cards are now one programme concern, select one acceptance owner and make the old cards subordinate/superseded once their unique criteria are preserved.

A 2026-09-10 Misumi audit already identified duplicate clusters. Do not add another standalone voice, memory, TV, SSH, music, records, skills or persona-rendering card unless the live queue lacks an owner for a genuinely distinct requirement.

## Macro-phase order

The order below is the default dependency structure. Sonnet may interleave safe independent work when it shortens the critical path, but Opus must approve any material reordering that changes architecture or human gates.

### Phase 0: re-ground truth and clean authority

Goal: make repository, queue and deployment descriptions agree with reality.

Required work:

- reconcile Misumi draft PR #39 with the later Odysseus PR #41 queue-ownership migration;
- establish `tyecam1/misumi` as household/personal knowledge authority without reintroducing backend queue ownership;
- classify all live Misumi unresolved items;
- audit legacy `agent-tasks/odysseus/` entries and move/supersede only those whose authority is now shared backend;
- distinguish current deployment state on home, lab and interface PC from repo state;
- reconcile temporary ports/services 4500/4600 versus Odysseus-owned routes;
- close completed-but-stale cards rather than carrying them indefinitely.

Gate: Sol verifies repository/queue authority and no shared capability was silently duplicated.

### Phase 1: truthful dual-host compute

Goal: Misumi can use both laboratory and home compute through one Odysseus routing authority.

Use the existing multihost tasks and plan. Do **not** create another router.

Required outcomes:

- finish the remaining staged multihost implementation loop;
- harden cross-device dispatch/status semantics;
- resolve or supersede the old remote-compute dispatch guard against current code;
- live-inventory and benchmark the home worker;
- promote home to execution-worker eligibility only when benchmark/worker evidence satisfies the live gate;
- confirm lab remains an eligible first-class worker;
- prove `route.host` equals physical execution host;
- prove no silent backend-local fallback;
- preserve ParkLease and EstateExecution authority;
- expose useful worker health/capability to the Sonnet laptop coordinator.

Host roles:

```text
laptop       = human/Sonnet controller, not normal worker
interface PC = capture/presentation node, not normal worker
home         = primary Misumi/household runtime + qualified worker
lab          = qualified worker + research/backend capacity
glovebox     = experiment edge only, never generic Misumi worker
```

Misumi workloads that may use either qualified worker include STT, local inference, embeddings, indexing, summarisation, deterministic maintenance and bounded background jobs, subject to locality/privacy policy.

Gate: live job evidence on both home and lab, independently Sol-verified.

### Phase 2: durable transcript foundation

Goal: captured speech becomes durable text before assistant routing.

Acceptance owner:
`automation/review/agent-tasks/inbox/2026-10-01-misumi-durable-transcript-runtime.agent-task.md`

Required outcomes:

- dedicated owner-scoped transcript event model;
- atomic/idempotent audio-to-durable-transcript API;
- bounded query/export;
- restart/outage/duplicate tests;
- raw audio ephemeral by default;
- home/lab STT placement through existing routing;
- transcript/session/memory/audio retention dimensions separated;
- no split-brain transcript writes.

Gate: Sol actively tries to break idempotency, owner isolation, ack ordering, cleanup and host attribution.

### Phase 3: ambient capture and GUI friction reduction

Goal: the interface acts like an appliance rather than a network engineering console.

Acceptance owner:
`tyecam1/misumi:agent-tasks/inbox/2026-10-01-misumi-ambient-transcript-interface.md`

Required outcomes:

- ambient segmentation default after explicit microphone enablement;
- PTT retained as fallback;
- bounded IndexedDB outbox;
- persistence before wake gating;
- rolling transcript;
- independent capture/archive/assistant/runtime state;
- obvious pause/mute;
- normal settings stripped of host/port complexity;
- advanced diagnostics retain technical controls;
- browser vertical slice passes real interface-PC acceptance;
- only then assess whether a tiny capture daemon is justified.

Do not permanently store raw audio merely because continuous capture is enabled.

Gate: live interface-PC restart/LAN/backend failure tests plus Sol review of persistence claims.

### Phase 4: memory, context and recoverability

Goal: transcript history, conversation history and semantic memory form a coherent hierarchy rather than competing stores.

Converge:

- `converged-memory-architecture`;
- `misumi-memory-consolidation-and-transparency`;
- `backup-and-restore-memory-store`;
- `context-portability-hygiene`;
- ~~`misumi-persona-context-budget-and-focus`~~ (transferred 2026-10-03 to `2026-10-02-misumi-persona-growth-background-collaboration`; see "Scope transfer" under Phase 5);
- Odysseus `aoteru-central-memory-and-universal-assistant`.

Required outcomes:

- transcript archive is operational history, not semantic authority;
- ordinary conversation session history remains distinct;
- semantic memory is selective/provenanced;
- Misumi Git truth outranks runtime memory;
- backup/restore is demonstrated;
- home/lab failover cannot create split-brain writes;
- context retrieval stays bounded;
- memory controls are understandable from the interface.

Gate: destructive/recovery drill on disposable fixtures plus Sol verification.

### Phase 5: model, persona and evaluation quality

Goal: measured quality replaces inherited model/persona assumptions.

Converge:

- model backend evaluation;
- ~~household evaluation corpus~~ (transferred 2026-10-03 to `2026-10-02-misumi-persona-growth-background-collaboration`);
- ~~persona calibration/improvement graph~~ (transferred 2026-10-03);
- ~~context budgets~~ (transferred 2026-10-03);
- runtime health/observability;
- Odysseus model-role evaluation system;
- subscription usage attribution;
- daily usage-reset harvesting once telemetry is reliable.

Sonnet remains the programme orchestrator. Opus/Sol role assignments are governance roles, not evidence that every task should use the most expensive model.

Use local/home/lab workers wherever measured quality is adequate.

Gate: evaluation evidence supports routing changes; no model role is promoted from anecdote alone.

#### Scope transfer (2026-10-03)

The persona-development criteria in Phases 4 and 5 (persona context budget and focus, the household evaluation corpus, persona
calibration and the improvement graph, context budgets) are **transferred, not completed**, to the successor programme
`2026-10-02-misumi-persona-growth-background-collaboration`, which is their single acceptance owner (its section "Transferred acceptance criteria" reproduces every criterion of the
four Misumi cards verbatim; the cards are `superseded` in `tyecam1/misumi`). This removes a circular dependency: the convergence
programme can close without those criteria, and the successor activates at that closeout. **Model-role and backend evaluation stays
in this programme's scope** and is owned by `2026-09-13-operating-contract-model-role-evaluation-system`. Persona work consumes that
evidence and creates no second model registry.

### Phase 6: safe household action and Phase B

Goal: decide and, if approved, implement the minimum useful governed write surface.

Converge:

- `misumi-phase-b-write-consent-and-rollback`;
- `phase-b-write-surface-spec`;
- flatmate controller;
- host/service health;
- seed-order/live runtime verification;
- sandbox/permissions;
- relevant SSH/deployment gates.

No transcript or memory mechanism grants Git write authority.

Any Phase-B action must retain:

- explicit allowed paths/actions;
- Git/lease provenance;
- rollback;
- actor identity;
- human consent for consequential/shared household operations.

Gate: explicit human approval where current tasks require it, then independent Sol verification.

### Phase 7: household convenience backlog

Only after the core appliance path is reliable, activate useful domain features according to observed need:

- records browsing/data surfaces;
- food/meal helpers;
- plant care;
- events/gigs/music recognition;
- TV/gaming/media;
- other household functions.

Do not let aesthetics or novelty displace transcript reliability, multihost truth or recovery.

### Phase 8: exploratory frameworks

Evaluate only against a demonstrated missing capability:

- Graphiti;
- LangGraph;
- Home Assistant Assist;
- Open Interpreter;
- PDDL planner;
- OpenClaw patterns;
- external skills.

"Interesting" is not a capability gap.

Each adopted dependency must replace or simplify something measurable. Otherwise close the evaluation without integration.

### Phase 9: convergence closeout

Goal: leave a small truthful system and queue.

Required:

- archive/supersede completed duplicate tasks;
- remove stale temporary runtime paths after rollback period;
- update runbooks/topology;
- run full relevant test/eval suites;
- perform final Opus synthesis;
- perform final fresh-context Sol audit;
- write `docs/misumi-long-horizon-programme-closeout.md`;
- append the prompt application trace/evolution event;
- ensure no unresolved task remains merely because nobody changed its status.

## Existing Odysseus work absorbed by this programme

These are the current shared-backend tasks that materially intersect Misumi. Sonnet must re-ground each against live state and mark duplicates/supersession rather than executing stale prose blindly.

### Required/shared critical path

- `automation/review/agent-tasks/inbox/2026-10-01-misumi-durable-transcript-runtime.agent-task.md`
- `automation/review/agent-tasks/inbox/2026-08-19-local-first-dual-pc-agent-runtime.agent-task.md`
- `automation/review/agent-tasks/ready/2026-09-23-odysseus-staged-implementation-loop.agent-task.md`
- `automation/review/agent-tasks/ready/2026-09-03-odysseus-cross-device-delegation-lifecycle-hardening.agent-task.md`
- `automation/review/agent-tasks/inbox/2026-09-19-capability-routed-parallel-project-orchestration.agent-task.md`
- `automation/review/agent-tasks/inbox/2026-09-28-persistent-blocked-route-rerouting-long-horizon.agent-task.md`
- `automation/review/agent-tasks/inbox/2026-08-19-aoteru-central-memory-and-universal-assistant.agent-task.md`
- `automation/review/agent-tasks/inbox/2026-09-13-operating-contract-model-role-evaluation-system.agent-task.md`

### Efficiency / evidence dependencies

- `automation/review/agent-tasks/ready/2026-09-08-subscription-usage-attribution-for-continuous-system-improvement.agent-task.md`
- `automation/review/agent-tasks/inbox/2026-09-13-daily-model-usage-reset-harvest.agent-task.md`
- `automation/review/agent-tasks/inbox/2026-09-10-external-capability-equivalence-audit.agent-task.md`

### Reconcile or supersede against newer implementation

- `automation/review/agent-tasks/blocked/2026-06-19-odysseus-remote-compute-dispatch-guard.agent-task.md`

### Conditional

- `automation/review/agent-tasks/inbox/2026-08-19-centralised-knowledge-gathering-system.agent-task.md` only if a live transcript/knowledge-ingestion requirement is not already satisfied by the memory/transcript architecture.

Do not absorb unrelated research-only Odysseus tasks into the Misumi programme.

## Misumi unresolved-queue baseline

This snapshot contains the 61 pre-existing unresolved records observed on 2026-10-01 before the new ambient-transcript card. It exists so none disappear through neglect. Live queue state always wins.

### blocked-human

- `add-odysseus-fork-deploy-key.md`
- `complete-bbc-grapheneos-live-gate.md`
- `phase-b-write-surface-spec.md`
- `reconcile-odysseus-misumi-naming.md`

### inbox

- `2026-06-30-weekly-glasgow-gig-matrix.md`
- `2026-07-05-music-recognition-now-playing-facts.md`
- `2026-08-30-calibrate-persona-models-and-improvement-graph.md`
- `agent-ssh-key-host.md`
- `backup-and-restore-memory-store.md`
- `claude-skills-adoption.md`
- `codex-active-specialist-large-portraits.md`
- `codex-page-persona-offline-pools.md`
- `codex-records-data-surface.md`
- `configure-ssh-key-access.md`
- `context-portability-hygiene.md`
- `converged-memory-architecture.md`
- `curated-external-skill-review.md`
- `evaluate-graphiti-kg-memory.md`
- `evaluate-home-assistant-assist.md`
- `evaluate-langgraph-orchestration.md`
- `evaluate-misumi-model-backends.md`
- `evaluate-open-interpreter-computer-control.md`
- `event-tracker-weekly-artist-recommendations.md`
- `fcc-autonomous-dev-loop.md`
- `flatmate-controller.md`
- `game-streaming-setup.md`
- `local-llm-serving.md`
- `meal-suggestion-script.md`
- `misumi-household-agent-evaluation-corpus.md`
- `misumi-interface-node-avatar-mic.md`
- `misumi-memory-consolidation-and-transparency.md`
- `misumi-persona-context-budget-and-focus.md`
- `misumi-phase-b-write-consent-and-rollback.md`
- `misumi-phd-multi-deployment-isolation-tests.md`
- `misumi-runtime-health-and-observability-surface.md`
- `odysseus-primary-runtime-migration.md`
- `openclaw-channel-and-daemon-pattern-assessment.md`
- `pddl-planner.md`
- `phd-systems-integration.md`
- `plant-database-watering.md`
- `record-browsing-views.md`
- `research-engine-refinement-index.md`
- `scoped-score-bearing-pilot.md`
- `shared-interface-style.md`
- `tv-pc-gaming-media-setup.md`
- `tv-pc-peripherals.md`
- `voice-hardware-rooms-privacy.md`
- `voice-realtime-pipeline.md`
- `voice-stt-whisper.md`
- `voice-tts-kokoro.md`
- `voice-wakeword-vad.md`

### legacy `agent-tasks/odysseus`

- `2026-08-30-twice-daily-agentic-task-scan.md`
- `2026-09-03-run-core-persona-model-calibration.md`
- `file-inbox-notes.md`
- `verify-seed-order-live-runtime.md`

These require authority review under the 2026-09-23 ownership migration. Do not assume the folder name itself still grants Odysseus ownership inside Misumi.

### review

- `deploy-odysseus-host.md`
- `fcc-sandbox-and-permissions.md`
- `host-service-health-monitoring.md`
- `jarvis-persona-and-conversation.md`
- `ratify-overflow-zone-policy.md`
- `wire-misumi-seed-core.md`

### new acceptance owner added by the 2026-10-01 audit

- `agent-tasks/inbox/2026-10-01-misumi-ambient-transcript-interface.md`

This card conceptually consolidates the voice/interface cluster but does not erase unique acceptance criteria until they are checked.

## Current consolidation map

Treat these as one concern unless live evidence proves a unique independent task remains.

### Voice/interface

Acceptance owner:
`2026-10-01-misumi-ambient-transcript-interface.md`

Inputs/subordinate cards:

- `misumi-interface-node-avatar-mic.md`
- `voice-realtime-pipeline.md`
- `voice-stt-whisper.md`
- `voice-tts-kokoro.md`
- `voice-wakeword-vad.md`
- `voice-hardware-rooms-privacy.md`
- `shared-interface-style.md`
- persona rendering cards where they affect the same surface.

### Memory/context

Programme owner is the combined Misumi memory cards plus Odysseus central memory task. Do not add another memory database.

### Runtime/deployment

Converge `odysseus-primary-runtime-migration`, deploy/health review cards and newer Odysseus multihost/staged tasks. Old single-host assumptions are evidence to reconcile, not architecture to preserve.

### SSH/host access

Converge `agent-ssh-key-host`, `configure-ssh-key-access` and current Tailscale/estate evidence. Do not create another credentials store.

### Records/music/events/media

Cluster for later convenience phases. Retire dated event-specific planning when it has no durable value.

### Exploratory frameworks

Keep evaluation-only until a measured gap activates one.

## Per-stage execution loop

For every bounded stage:

1. Sonnet reconstructs the exact live scope and dependencies.
2. If architecture is ambiguous or consequential, Sonnet asks Opus for a compact plan/critique.
3. Sonnet selects the implementation route from live capability and host state.
4. Execute in an isolated governed worktree/lease.
5. Run deterministic tests first.
6. Run live host/interface acceptance where the stage claims physical/runtime behaviour.
7. Send a fresh evidence packet to Sol.
8. Resolve all material Sol findings.
9. Rerun affected tests and Sol after material repair.
10. Commit/push and open/update the relevant PR.
11. Update/supersede child task state and programme evidence.
12. Opus synthesizes the completed macro-phase when a phase boundary is reached.
13. Continue to the next executable frontier without waiting for an operator acknowledgement unless a real human gate exists.

## Parallelism

Parallelism is permitted only when the existing capability-routed orchestration contract considers units independent.

Never allow two workers to mutate the same repo/write scope concurrently.

Good parallel candidates:

- read-only audits;
- independent home/lab benchmarks;
- bounded test generation;
- documentation reconciliation separate from implementation;
- independent Sol verification;
- convenience work that has no dependency/write overlap with the critical path.

Bad parallel candidates:

- shared migration/schema work;
- the same UI file;
- the same deployment;
- overlapping lease/worktree scope;
- two competing architecture owners.

## Home/lab compute acceptance

The programme is not complete merely because both machines are listed in `estate.yaml`.

Prove:

- home and lab each execute at least one representative Misumi worker job through the same central routing authority;
- each publishes live capability/health;
- route telemetry truthfully identifies physical execution;
- home qualification is evidence-backed rather than a manually flipped boolean;
- failure of one host permits another eligible route where the task/policy allows;
- no host failure widens write authority;
- transcript persistence remains single-authority/fail-closed even when inference work moves hosts;
- interface PC remains non-worker.

Record benchmark evidence for STT and at least one local-model/deterministic workload relevant to Misumi.

## Transcript-first completion gate

Before lower-priority convenience work can become the normal frontier, the following must work on the real deployment:

1. interface captures an utterance without wake word;
2. text is durably stored exactly once;
3. visible UI shows acknowledgement;
4. addressed utterance is stored before Misumi responds;
5. browser/interface restart preserves unacknowledged work;
6. temporary backend/LAN outage queues and later drains;
7. Odysseus restart does not lose durable transcript;
8. home/lab routing remains truthful;
9. raw audio does not accumulate after acknowledgement;
10. semantic-memory off does not silently erase ordinary history.

## Human gates

Do not fabricate approval for:

- shared-space always-listening/ambient-capture consent where another person's privacy is implicated;
- enabling Phase-B Git writes;
- credentials/MFA/private provider login;
- destructive migration without tested rollback;
- public exposure/port forwarding;
- final policy decisions explicitly reserved to the operator.

When one human gate blocks one branch of work, use persistent blocked-route state and continue independent work.

## Programme closeout

The programme is complete only when all of the following are true or explicitly rejected/retired with evidence:

- Misumi repository identity/ownership docs are reconciled;
- shared/backend task ownership is in Odysseus;
- home and lab are truthful usable worker resources;
- the interface PC is a reliable thin capture/presentation node;
- durable transcript acceptance passes;
- GUI normal mode is low-friction;
- conversation/transcript/memory/artifact/audio retention policies are distinct;
- memory/recovery is tested;
- high-priority model evaluation is evidence-backed (persona-development criteria are transferred to `2026-10-02-misumi-persona-growth-background-collaboration` and are not a closeout dependency);
- Phase-B decision has an explicit status;
- every pre-existing Misumi unresolved card has a terminal or justified live state;
- relevant Odysseus child tasks have terminal or justified live state;
- temporary redundant services/routes are retired or explicitly retained for rollback;
- final Opus synthesis finds no unowned architectural gap;
- final Sol audit finds no unresolved material correctness/authority/recovery issue;
- prompt application trace and evolution event are written.

Do not call the programme complete with a visually working demo but unverified persistence/recovery, or with a clean transcript path while the 61-card backlog remains abandoned.

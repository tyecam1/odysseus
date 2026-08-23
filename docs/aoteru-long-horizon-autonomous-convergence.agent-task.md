---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-08-23-aoteru-long-horizon-autonomous-convergence
title: "Aoteru long-horizon autonomous convergence programme"
status: ready
priority: critical
task_type: multi-workstream-programme-controller
created_by: chatgpt
created_at: 2026-08-23T03:20:00+01:00
executor: claude-sonnet-5
execution_mode: long-horizon-autonomous-programme
resource_profile: adaptive
risk_level: medium
approval_required: false
source_traceability_required: true
requires_local_model: true
requires_remote_compute: true
requires_web: false
repo: tyecam1/odysseus
branch: dev
inputs:
  - docs/aoteru-estate-implementation-plan.md
  - docs/aoteru-estate-execution-contract.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/aoteru-p12-active-estate-convergence-evidence.md
  - docs/aoteru-lm4-production-canary-evidence.md
  - config/estate.yaml
  - config/repositories.yaml
  - config/models.yaml
  - config/routing.yaml
outputs:
  - durable programme state/backlog with dependency and blocker tracking
  - converged production-grade Aoteru/Odysseus runtime for currently reachable estate
  - installable thin laptop-controller bootstrap requiring no Odysseus checkout
  - hardened provider-neutral local/paid execution and telemetry
  - mature memory/failover/source-trace implementation compatible with future home-primary role
  - governed cross-repo execution proofs
  - deployable interface/mobile front-door package for later interface-PC activation
  - deployable experiment-edge package for later/live glovebox Jetson activation
  - deployable home re-entry/bootstrap package and qualification workflow
  - replay/shadow routing evaluator using real production telemetry
  - resolved internal test/technical-debt baseline where within repository control
  - comprehensive resilience/security/backup/recovery evidence
  - final operating handbook and residual-gates report
notes: >-
  This supersedes the pattern of one small numbered phase per user prompt. Run as
  one autonomous programme. Decompose internally, commit coherent milestones,
  and move to the next eligible workstream when another is blocked. Do not return
  to the operator merely because a subphase completed. Home/interface/glovebox
  availability gates must not prevent progress on independent work.
---
# Aoteru long-horizon autonomous convergence programme

## Mission

Finish the **system**, not the next phase.

The canonical goal remains:

```text
user on laptop/phone
  -> Aoteru
  -> bounded memory/context
  -> authority/repository
  -> verified eligible host
  -> cheapest adequate deterministic/local/paid mechanism
  -> governed execution/parking
  -> deterministic verification and bounded escalation
  -> durable result + memory candidate
  -> same human-facing surface
```

Operate for the full useful horizon of the current session. Expect many commits
and multiple workstreams. A completed milestone is a checkpoint, **not a reason to
stop**.

Stop only when:

1. every currently executable programme workstream is complete or demonstrably
   converged;
2. every remaining item depends on a real external/human/host-availability gate;
3. each gate has the smallest exact continuation procedure already prepared;
4. the repository is clean, verified and pushed; and
5. a final independent audit finds no high-value unblocked work omitted from this
   programme.

Do not invent P13/P14-style microphases for the user. Internal decomposition is
allowed and encouraged, but the operator should not need to repeatedly initialise
new sessions just because you finished one bounded unit.

## Authoritative current estate

Re-read live state before acting. Current durable evidence is:

- **lab / HP Z2** — primary general worker; i9-12900K, 128 GB class RAM,
  RTX 3080 10 GB, Linux, production Ollama/Odysseus. Robotics experiment
  priority overrides background GPU inference.
- **laptop / desktop-7dj1hma** — human controller. It currently has **no
  Odysseus checkout**. Treat that as a product requirement: normal controller use
  should not require a full source/runtime clone unless strong evidence says it
  is unavoidable.
- **glovebox Jetson Orin Nano** — research experiment-edge node for ROS 2,
  RealSense/perception/capture/diagnostics. P12 saw it offline on tailnet despite
  the operator describing it as connected; re-check live evidence when relevant.
  Never treat it as a generic background LLM worker.
- **home PC** — separate machine, unavailable/unverified. Future likely roles:
  household/Misumi, memory-primary/always-on services, and possibly secondary
  compute only after live hardware inventory + benchmark.
- **interface PC** — separate unavailable machine. Future primary role:
  persistent authenticated human-facing Aoteru/Misumi/UI/mobile bridge; not
  automatically a heavy worker.

Unavailable hosts are **deferred dependencies, not programme blockers**.

## Programme-control loop

At programme start, create/update one durable state surface:

`docs/aoteru-autonomous-programme-state.md`

Keep it compact and machine-readable enough to resume after context/session loss.
For each workstream record:

```yaml
id:
outcome:
status: eligible | active | blocked | deferred | complete
priority:
depends_on: []
blocker:
next_action:
evidence: []
last_verified_commit:
```

Then repeat until stop condition:

```text
refresh live state
-> audit programme state against canonical plan + current code
-> select highest-value eligible workstream
-> decompose into bounded mutation/evidence units
-> delegate cheap/token-heavy work where appropriate
-> implement
-> verify independently
-> commit cohesive checkpoint
-> update programme state
-> immediately select next eligible workstream
```

When a workstream blocks, **park it and continue another one**. Never sit on an
unavailable host/credential if independent work remains.

Every 3-5 substantive commits, run a convergence audit:

- what user-visible capability became possible?
- what reliability/security debt remains?
- what canonical-plan requirement is still only prose?
- what duplicate/stale surface can now be removed or deprecated?
- what work can be completed without waiting for unavailable hardware?

## Workstream A — baseline truth, technical debt and test convergence

Purpose: stop carrying avoidable defects forward merely because earlier phases
labelled them unrelated.

1. Reproduce the current full-suite baseline at HEAD.
2. Triage the known MCP SDK `Server.list_tools` failures and upload-handler
   atomicity failure. If caused by repository dependency/version drift or a real
   code defect under Odysseus control, fix them. If genuinely external, pin or
   guard compatibility where appropriate and record the irreducible reason.
3. Audit warnings, schema migrations, stale feature flags and dead compatibility
   paths introduced by P0-P12/LM1-LM4.
4. Remove duplicated or contradicted topology/model prose only where a canonical
   live/config surface has replaced it; preserve historical evidence as history.
5. Establish a target of zero unexplained test failures. Do not game the suite by
   deleting/xfailing meaningful tests.

Completion: clean explained baseline, preferably full green, with no known
repository-controlled failure simply carried as "pre-existing".

## Workstream B — laptop controller as an installable product surface

Purpose: make the laptop useful **without an Odysseus checkout**.

Design the smallest supportable controller footprint. Prefer one of:

- a self-contained `agent` client package/script installed from a release/raw
  bootstrap;
- `pipx`/uv-installed CLI from a packaged Odysseus client component;
- a minimal generated controller bundle containing no worker/runtime code.

Do not require model weights, ChromaDB, repo clones or server state on laptop.

Deliver:

1. a Windows bootstrap/uninstall/update path;
2. host-local config under `~/.aoteru` / appropriate Windows equivalent;
3. secure token/bootstrap flow that never commits secrets;
4. `agent status`, `agent ask`, job/result, memory query, park/where/release and
   explicit Codex/Claude controls as supported by the backend;
5. clear failure messages when lab/backend is unavailable;
6. packaging/version compatibility tests;
7. an exact **single operator bootstrap command** ready to run on the laptop.

If laptop execution cannot be tested from this lab session, complete everything
server/release-side and leave only that final operator command + smoke test.
Do not require the user to open a new planning session to discover what to do.

## Workstream C — execution plane hardening: deterministic, local, Codex, Claude

P12 proved one trivial Codex escalation. Mature the mechanism.

1. Audit `run_task`, task-envelope/result contracts, executor abstraction,
   cancellation/timeouts, retries, error classification and telemetry.
2. Exercise Codex on representative nontrivial bounded tasks: code reasoning,
   repo reconnaissance, schema output and one deterministic-verification repair
   loop. Keep mutations in safe fixtures/scratch worktrees unless explicitly
   parked.
3. Record provider/model/version, wall latency, retries, escalation cause,
   verification outcome and quota/cost proxies where available.
4. Implement bounded retry only for retryable failure classes; never blindly
   repeat paid prompts.
5. Ensure paid execution cannot bypass write authority or parking.
6. Implement/finish a provider-neutral Claude executor adapter if useful from the
   architecture. If no Claude credential/runtime exists, make it testable and
   dormant rather than copying credentials or pretending it is live.
7. Define cheap/strong paid capability aliases or executor policy through
   config—not hard-coded model names in business logic.
8. Test cross-provider independent verification where one real high-consequence
   fixture justifies it; otherwise keep it dormant.

Completion: paid execution is a reliable governed lane, not a single smoke-test
special case.

## Workstream D — routing economics, quality and replay/shadow evaluation

LM1-LM4 qualified local models; P12 added one paid path. Finish the learning loop.

1. Build the canonical replay/shadow evaluator promised by the routing contract,
   reusing `RoutingDecision`/`BenchmarkResult`, not another authority.
2. Aggregate by task class + alias + concrete route:
   first-pass success, verification rate, latency distribution, retry/escalation
   rate, context size and paid/quota metrics where measurable.
3. Add recency weighting/staleness semantics without silently changing governed
   permissions or quality floors.
4. Use existing frozen corpus + real production records for replay.
5. Keep exploration disabled until enough evidence exists; define an evidence
   threshold rather than enabling it merely because code exists.
6. Produce candidate config changes as proposals with before/after evidence;
   shadow/canary before promotion.
7. Re-evaluate `code-strong` only if real workload evidence shows `code-fast` +
   paid fallback is insufficient. Do not fill null aliases cosmetically.

Completion: routing can learn from real use and compare policy candidates without
unsafe self-modification.

## Workstream E — memory broker and cross-session continuity

Audit implementation against the canonical plan rather than assuming P4 closed
all long-horizon requirements.

Required outcome:

- source-linked structured memories/open loops/corrections;
- no whole-repo duplication;
- deterministic source trace;
- Chroma as rebuildable derived index only;
- idempotent outbox/failover semantics;
- import compatibility for existing Misumi memory;
- bounded recall suitable for laptop/mobile front ends;
- clean future promotion of **home PC as primary memory writer** without an
  architectural rewrite.

While home is unavailable:

1. strengthen/test the lab fallback/read-cache/outbox role;
2. implement missing source-event/revision/relation/open-loop semantics if still
   incomplete;
3. test corruption/rebuild/idempotent replay and source deletion/supersession;
4. add incremental ingest adapters only for sources with a clear supported path;
5. ensure PhD/household domain authority remains in their repos.

Do not appoint lab as permanent canonical memory leader merely because home is
missing.

Completion: memory architecture is operational now and migration-ready later.

## Workstream F — governed cross-repository operation

Prove Odysseus is actually a useful estate controller across the user's real
work, not only its own repo.

Inventory registered clones and permissions for at least:

- `tyecam1/odysseus`;
- `tyecam1/obsidian-PhD`;
- `tyecam1/s2-e1-ros2-measurement-spine`;
- `misumi`/household where available.

For each reachable/registered repo:

1. prove read-only resolution/search without parking;
2. prove source-pointer/result handoff;
3. verify repo-specific instructions/domain gates load for delegated work;
4. test parking/lease/heartbeat/reclaim on a safe fixture or disposable branch;
5. perform at least one representative **real but non-destructive** task class
   through Odysseus and deterministic verification;
6. never mutate PhD/robotics canonical work simply to obtain a demo.

Completion: the estate demonstrably routes domain work without centralising
business logic into Odysseus.

## Workstream G — experiment integration and glovebox Jetson readiness

Treat research experiments as first-class operational work, not another compute
pool.

While Jetson is unavailable/offline:

1. build the minimal experiment-edge bootstrap/re-entry package;
2. define live inventory/health contract for Jetson CPU/GPU/shared memory,
   JetPack/ROS, RealSense, storage, thermals and experiment services;
3. provide narrow capability registration (`ros2`, `realsense`,
   `experiment-capture`, `edge-perception`, `robotics-logs`);
4. implement safe busy/experiment-active state and data-locality policy;
5. integrate the explicit experiment reservation signal with lab routing so
   experiments can reserve lab GPU as well as Jetson-side resources;
6. define compact artefact/log/metric transfer to lab for heavy analysis;
7. prepare idempotent deploy/update/rollback and read-only qualification command.

At programme start and before final closure, re-check whether Jetson has returned.
If reachable, automatically execute the prepared live inventory + safe read-only
qualification. If not, leave exactly one operator command/procedure.

Never run generic background LLMs on Jetson by default.

## Workstream H — interface/mobile product path, built now and activated later

Do not wait for the unavailable interface PC to write all software needed for it.
Do not falsely bind a lab stand-in as canonical `svc:aoteru`.

Build/test as deployable artefacts:

1. persistent authenticated Aoteru front-door service/API using existing Odysseus
   contracts;
2. minimal responsive PWA/mobile UI or existing Misumi interface integration,
   whichever the repo already supports best;
3. job submission/status/result, memory recall, basic park/status and explicit
   escalation controls;
4. private-network assumptions and no public model/MCP/shell exposure;
5. install/update/rollback package for the future interface PC;
6. isolated lab test deployment allowed only as a **test instance**, never
   relabelled canonical `svc:aoteru`;
7. acceptance tests that can be rerun verbatim when the interface PC returns.

Prepare a future phone onboarding flow against `svc:aoteru`; actual canonical
activation waits for the interface PC unless the operator later changes service
placement explicitly.

## Workstream I — home-PC re-entry prepared as a migration, not an adventure

Home remains unavailable. Build the tooling so its return costs one bounded
qualification session, not another redesign.

Prepare:

- identity/hostname reconciliation;
- hardware/runtime/model/storage inventory script;
- household/Misumi service inventory;
- memory-primary promotion/checkpoint/replay procedure;
- Odysseus service install/update/rollback;
- same-corpus local model benchmark harness invocation;
- worker eligibility/shadow/canary gates;
- backup/restore and conflict checks;
- strict rule that mere reachability never implies trust or promotion.

Do not hard-code imagined home hardware.

## Workstream J — security, resilience, backup and recovery

Move beyond happy-path smokes.

Audit/test:

- auth/token scope and secret handling;
- loopback/private exposure and Tailscale Serve/Funnel state;
- DB backup/restore and schema migration recovery;
- Chroma rebuild from authoritative state;
- ParkLease crash/reclaim/conflict behaviour;
- worker/model/provider disappearance mid-task;
- timeout/cancel/retry state transitions;
- stale `LogicalSession`/job reconciliation;
- service restart and systemd recovery;
- rollback of model/config/executor changes;
- controller disconnect/reconnect;
- malformed/multimodal/oversized task envelopes;
- experiment reservation under concurrent background demand.

Prepare a **cold-reboot verification script/checklist**. Do not reboot the lab host
without explicit operator authorization, but make the one human action sufficient
to exercise the complete automated post-boot verification.

Completion: failures become truthful recoverable states, not manual archaeology.

## Workstream K — operator experience and observability

The system is not complete if only its implementer can operate it.

Converge:

- `agent status` into one compact truthful estate view;
- clear host/service/model/repo/lease/job/memory status;
- concise "why this route?" diagnostics;
- blocked-task dependency + continuation command;
- logs/result pointers without leaking sensitive prompts;
- install/update/version/status commands for controller and future nodes;
- minimal operating handbook covering normal use, experiment reservation,
  recovery and host re-entry.

Avoid dashboards for their own sake. Prefer CLI/API surfaces already present; add
UI only when it reduces actual operator overhead.

## Workstream L — real-work validation

Before declaring programme convergence, run representative end-to-end tasks that
match the actual estate:

- Odysseus engineering/repo task;
- PhD evidence/retrieval or document-reasoning task (read-only unless explicitly
  parked for an authorised change);
- S2-E1 ROS/log/test interpretation task;
- multimodal task;
- one task that stays local;
- one task that escalates to Codex because evidence says local is inadequate;
- one task under experiment-priority reservation;
- one intentionally unavailable-host task that produces a durable truthful block.

Measure route, verification, latency, escalation and result pointers. Do not
manufacture work or alter research outputs merely to pass a system test.

## Work distribution policy

Sonnet 5 is the programme foreman. It should **not** personally consume all tokens
on mechanical work.

Use this hierarchy:

1. deterministic shell/code search/tests for inventory and verification;
2. current LM4-qualified local aliases for cheap extraction, classification,
   reconnaissance and bounded reasoning where their evidence supports it;
3. Codex for token-heavy bounded implementation/review through the now-live
   governed executor or CLI when repository context and verification are clear;
4. Sonnet for orchestration, synthesis, ambiguous design and integration;
5. stronger cloud reasoning only for genuinely difficult architecture/debugging
   or independent high-consequence review when available and justified.

For delegated work:

- issue a bounded objective, authority, read/write scope, source pointers,
  acceptance tests and output contract;
- one mutation owner per unit;
- no swarm/group chat;
- never send whole conversation transcripts when pointers suffice;
- independently inspect diff/tests before accepting worker claims;
- if worker output fails, repair or escalate from evidence rather than restarting
  the whole workstream.

## Git/change discipline

- Work on `dev` unless existing repository governance requires a branch/worktree.
- Pull ff-only before starting.
- Preserve clean history; no force push.
- Commit coherent milestones, normally after a workstream slice has independent
  verification—not after every tiny file edit.
- Update `docs/aoteru-autonomous-programme-state.md` in the same checkpoint.
- Push verified checkpoints so a session crash loses little work.
- Do not rewrite historical evidence to make new architecture look older.
- Prefer deleting obsolete duplicate implementation surfaces once safe migration
  and rollback are proven.

## Human gates

Human attention is expensive. Batch operator actions.

Do **not** stop for:

- unavailable home/interface/Jetson if other work remains;
- a completed workstream;
- a missing optional provider when another route exists;
- routine design choices supported by repo evidence;
- known credentials that are simply absent on this host when dormant integration
  can be completed safely.

Stop only when a required action cannot safely be performed without the operator,
such as interactive sudo/authentication, turning on/reconnecting a physical host,
running the prepared laptop bootstrap, or authorising a reboot.

Before stopping:

1. complete all independent work;
2. commit/push a clean checkpoint;
3. consolidate human actions into the smallest ordered batch;
4. provide exact commands and expected outputs;
5. record exactly where autonomous continuation resumes; and
6. never ask the operator to repeat completed work.

## Final acceptance criteria

Do not declare convergence merely because tests pass. The programme is complete
only when all **currently controllable** criteria are met and unavailable-host
criteria are deployment-ready:

1. repository-controlled test baseline has no unexplained failures;
2. lab service/model/routing/memory/parking paths are production-clean;
3. laptop thin-client/controller can be installed without a source checkout;
4. one exact laptop bootstrap + smoke procedure is ready (and live-proven if the
   operator runs it during this programme);
5. deterministic/local/Codex execution share one governed task/result/telemetry
   path, with Claude adapter dormant or live according to genuine auth;
6. routing replay/shadow evaluation exists and unsafe exploration remains gated;
7. memory broker is source-linked, recoverable and ready for future home-primary
   promotion;
8. real registered repositories can be resolved/executed under their own domain
   authority and lease rules;
9. experiment-priority protection is operational and Jetson edge integration is
   deployable/live-qualified if reachable;
10. interface/mobile front-door software is deployable and activation-ready for
    the unavailable interface PC;
11. home re-entry is a bounded inventory/migration/benchmark procedure, not an
    architectural project;
12. backup/restore/failure/recovery paths are verified to the maximum safe extent
    without unauthorised reboot/destructive testing;
13. operator status/diagnostics/handbook make normal use and recovery practical;
14. representative real-work validation demonstrates local, paid, multimodal,
    experiment-priority and truthful-block paths;
15. final independent audit finds no high-value unblocked canonical-plan gap;
16. all remaining blockers are genuinely physical/operator/external and each has
    one precise continuation gate;
17. local HEAD is clean and equals `origin/dev`.

## Final report

At true stop, write/update:

`docs/aoteru-long-horizon-autonomous-convergence-evidence.md`

Report by **capability and residual gate**, not by narrating every commit. Include:

- what the user can now do;
- architecture actually live vs deployment-ready;
- measured reliability/quality/latency/cost evidence;
- active host roles and unavailable-host re-entry state;
- security/recovery evidence;
- tests;
- human actions still required, ordered by value;
- what should happen when laptop, Jetson, interface or home next becomes available;
- whether any further dedicated development programme is genuinely justified.

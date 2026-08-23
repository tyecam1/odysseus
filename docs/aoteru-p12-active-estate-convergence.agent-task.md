---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-08-23-aoteru-p12-active-estate-convergence
title: "Active-estate convergence: laptop + lab + glovebox Jetson, with gated home/interface re-entry"
status: ready
priority: high
task_type: estate-convergence-controller-worker-experiment-edge
created_by: chatgpt
created_at: 2026-08-23T02:44:00+01:00
executor: claude-sonnet-5
execution_mode: implementation-with-gated-deferred-integration
resource_profile: standard
risk_level: medium
approval_required: false
source_traceability_required: true
requires_local_model: true
requires_remote_compute: true
requires_web: false
repo: tyecam1/odysseus
branch: dev
inputs:
  - config/estate.yaml
  - config/repositories.yaml
  - config/models.yaml
  - config/routing.yaml
  - docs/aoteru-model-host-routing-contract.md
  - docs/aoteru-lab-local-model-strategy-2026-08-20.md
  - docs/aoteru-lm4-production-canary-evidence.md
  - docs/operations/odysseus-host-deployment.md
outputs:
  - corrected live estate topology and host roles
  - proven laptop-controller -> lab-worker execution path
  - safely registered/qualified glovebox Jetson experiment-edge role
  - provider-neutral cloud-worker execution path where credentials/runtime permit
  - unified multimodal task execution through Odysseus routing
  - lab/Jetson resource-priority controls that protect robotics experiments
  - explicit deferred re-entry contracts for home and interface PCs
  - end-to-end fault/security evidence for the currently reachable estate
  - compact P12 evidence document
notes: >-
  Operator truth as of 2026-08-23 overrides stale topology prose: the currently
  reachable estate is laptop + lab + glovebox Jetson Orin Nano. Home PC and the
  separate interface PC are not reachable via tailnet and MUST NOT block this
  phase. Do not make lab or laptop masquerade as either missing host. The Jetson
  is research-experiment infrastructure first, not a general background worker.
---
# P12 — active-estate convergence

## Goal

Turn the currently reachable estate into a useful, end-to-end system:

```text
human on laptop
  -> thin Aoteru/Odysseus control path
  -> Odysseus authority/routing
  -> deterministic or qualified local execution on lab when adequate
  -> paid Claude/Codex execution only when required and actually available
  -> experiment-edge work on glovebox Jetson only when the task genuinely belongs there
  -> deterministic verification
  -> compact result/evidence pointer back to laptop
```

At the same time, repair the estate model so the unavailable **home PC** and
**separate interface PC** can be added later without redesigning routing,
authority, task envelopes, leases, memory or services.

This is **not** another model-discovery phase. LM1-LM4 are closed. Reuse the
current live model bindings and canary evidence.

## Non-negotiable boundaries

1. Odysseus remains the single routing/job/parking/telemetry authority.
2. Laptop is the human controller/conversational surface; do not make it a
   normal heavy execution worker merely because it has compute available.
3. Lab is the primary general worker and current local-model host.
4. Glovebox Jetson is an **experiment-edge** host: ROS/camera/perception/data
   capture and experiment-adjacent inference/diagnostics have priority. Do not
   send generic background LLM work there.
5. Robotics experiments outrank background Aoteru model use. Lab GPU work must
   yield when an experiment reservation/load condition says it should.
6. Home and interface PCs remain registered-but-ineligible until live evidence
   proves identity, reachability, health and purpose. Their absence is not a P12
   failure.
7. Never copy or print credentials to move a blocker. Use host-local auth and
   stop only the affected sub-gate at a genuine human credential/sudo boundary.
8. No public model, MCP, shell or control-plane ports. Tailnet/private or
   loopback-only exposure remains binding.
9. Repo mutation still requires existing parking/lease authority.
10. Extend existing surfaces; do not create a second router, queue, model
    registry, memory system or orchestration framework.
11. Use deterministic tools/tests before model inference; local before paid when
    adequate; escalation only from recorded evidence.
12. Preserve LM4 telemetry and bindings unless real P12 evidence finds a
    regression.

## Current host truth to verify, not blindly hard-code

### Lab — general worker

Known durable evidence says HP Z2 Tower G9, Linux x86_64, i9-12900K, 128 GB RAM,
RTX 3080 10 GB, NVMe, production Ollama, and live Odysseus backend. Verify live
state at execution time. Purpose:

- primary general execution worker;
- local LLM inference;
- heavy repository/test/research work;
- heavy post-processing of robotics data when appropriate;
- must yield GPU capacity to robotics experiments when reserved/active.

### Glovebox — Jetson Orin Nano experiment edge

Operator confirms it is connected and used for research experiments. Prior
research records identify a Jetson Orin Nano with Jetson Linux/Ubuntu,
JetPack/NVIDIA stack and S2-E1 experiment storage under `/data/s2-e1`; treat all
version/storage details as hypotheses until live-reverified. Purpose:

- RealSense/ROS 2/perception experiment execution;
- capture and experiment-local processing where data locality/latency matters;
- edge diagnostics/log collection;
- optional bounded inference that supports the experiment;
- **not** a general LLM/background worker;
- never compromise experiment determinism, camera timing, GPU/thermal headroom
  or data integrity for Aoteru convenience.

### Laptop — controller

Live-inventory its actual hostname/OS/hardware instead of trusting stale naming.
Purpose:

- user-facing conversational/CLI controller;
- authenticated task submission and result review;
- lightweight orchestration/client code;
- no routine parked repo mutation/heavy model serving.

### Separate interface PC — deferred

The repository currently conflates "laptop/interface" in places, while older
Misumi deployment material references a separate interface box. The operator now
states the interface PC is a separate machine and is currently unavailable via
tailnet. Do not guess its hostname/hardware. Future intended purpose:

- persistent Aoteru/Misumi human-facing front door/UI/voice/mobile bridge;
- private authenticated service surface;
- normally not a heavy compute worker unless future live inventory and benchmark
  evidence justify a narrowly defined role.

### Home PC — deferred

Currently unavailable and not verified. Existing documents associate it with
Misumi/household and future memory/model services, but do not trust stale
identity/hardware. Future intended purpose, subject to live inventory:

- always-on household/Misumi and/or memory-primary service where appropriate;
- secondary/background worker if CPU/GPU/RAM/storage measurements justify it;
- candidate model host only after same-corpus benchmark/quality qualification;
- never automatically eligible merely because it reappears on the network.

## Execution sequence

### P12.0 — preflight and topology truth repair

1. `git pull --ff-only`; require clean `dev`; confirm LM4 closure and live model
   bindings.
2. Determine where this session is actually running. Prefer execution from the
   laptop for the controller-to-worker proof. If launched elsewhere, do not
   fabricate laptop-side evidence; prepare the minimal laptop continuation gate
   and continue all host-independent work.
3. Live-inventory the reachable laptop, lab and glovebox hosts: hostname,
   OS/kernel, CPU, RAM, GPU/accelerator/VRAM or shared memory, storage, relevant
   runtimes, Tailscale identity/IP, SSH/API reachability, Git/worker tooling and
   current services. Record source commands/evidence, not secrets.
4. Correct `config/estate.yaml` so laptop, lab, glovebox, home and interface are
   distinct entities. Current operator statement outranks stale prose. Preserve
   historical aliases only where useful for migration; never silently reassign a
   hostname without evidence.
5. Mark home/interface explicitly deferred/ineligible, not failed. Update stale
   required-connectivity entries that incorrectly make those hosts necessary for
   current completion.
6. Reconcile any older docs that still call the laptop the interface PC, but do
   not rewrite historical evidence to pretend it always said this.

Gate: active three-host topology is truthful and future two-host re-entry has no
architectural ambiguity.

### P12.1 — prove laptop -> lab controller/worker path

1. From the laptop, prove private authenticated reachability to the existing lab
   Odysseus backend and the required management/SSH path. Windows-specific SSH
   reality must be respected; Tailscale SSH is not assumed to terminate on the
   laptop.
2. Provide/repair one minimal controller command/client surface that submits the
   canonical task envelope to Odysseus and receives a compact result. Reuse
   existing API/CLI surfaces if present; do not build a second front end.
3. Demonstrate at least:
   - deterministic task;
   - `local-fast` task;
   - `code-fast` or `reasoning-strong` task;
   - a bounded repo-aware read task;
   - one parked mutation task only if an existing safe fixture/repo makes this
     non-destructive and lease-verifiable.
4. Verify each route in `RoutingDecision`/job telemetry and return pointers, not
   duplicated transcripts.
5. Laptop must remain thin: no need to mirror lab model weights or state.

Gate: human on laptop can reliably cause verified work to execute on lab and get
an auditable result back.

### P12.2 — close the structured/multimodal task-envelope gap

LM4 proved vision quality but also showed that `run_task()` cannot carry
multimodal content and must bypass to `resolve_route()+llm_call`.

1. Extend the canonical task envelope/execution API **backwards compatibly** so
   structured text/image inputs can traverse the same route/job/telemetry path as
   text tasks.
2. Do not special-case Gemma or vision business logic. Capability alias `vision`
   remains the abstraction.
3. Re-run the existing LM4 vision fixture once through the unified path and prove
   a real `RoutingDecision` + deterministic outcome.
4. Preserve plain-string callers unchanged.

Gate: all current local capability aliases can execute through one Odysseus task
path.

### P12.3 — provider-neutral paid worker convergence

The routing contract requires Claude and Codex workers to use the same bounded
job/result contract. Implement only against credentials/runtimes genuinely
available on the active estate.

1. Discover existing Claude/Codex/API/CLI integrations and host-local auth state.
   Do not copy secrets between laptop and lab and do not assume a binary is in
   PATH because an old document says so.
2. Prefer the smallest extension of existing provider surfaces. A paid worker is
   a mechanism selected by Odysseus, not a second orchestrator.
3. Preserve economic ladder semantics:
   `deterministic -> qualified local -> cheap paid -> stronger paid`, with
   evidence-triggered escalation.
4. Establish the compact worker-result contract and persist provider/model,
   latency, verification, retry/escalation and cost/quota data where available.
5. Run a bounded end-to-end proof in which a task is intentionally ineligible for
   the local route or fails a deterministic/local gate and therefore escalates to
   an actually available Claude/Codex worker. Deterministically verify the result.
6. If no paid-provider credential/runtime is usable on the appropriate host,
   finish the adapter/tests and record a **single explicit operator bootstrap
   gate**; do not make that absence block P12.0-2/4-7.
7. Do not pre-emptively fan the same task to multiple paid models. Cross-provider
   independent review is reserved for consequence/ambiguity that warrants it.

Gate: either one real paid escalation succeeds through Odysseus, or the code path
is complete and blocked only on a precisely documented human auth action.

### P12.4 — resource-aware lab scheduling and experiment protection

1. Inspect existing host-load/parking/routing mechanisms before adding anything.
2. Add the minimum mechanism needed for **experiment priority**. Prefer a simple
   host-local reservation/availability signal plus live GPU/load checks over a
   scheduler redesign.
3. When lab robotics GPU work is reserved/active, heavy local-model routes must be
   ineligible or penalised enough to choose an adequate CPU/deterministic/paid
   alternative; do not kill an experiment to service background work.
4. Normal idle-state local routing must continue to use the LM4-qualified
   portfolio.
5. Test both states deterministically: idle -> local eligible; experiment-reserved
   -> conflicting heavy route withheld/fallback chosen.

Gate: Aoteru cannot accidentally steal the RTX 3080 from an active experiment.

### P12.5 — qualify glovebox Jetson as experiment-edge, not general worker

1. Verify Jetson identity/hardware/runtime live and update `config/estate.yaml`.
2. Verify private reachability from laptop and, where useful, lab. Do not require
   lab->laptop connectivity.
3. Discover the S2-E1/ROS/data surfaces actually present. Never mutate experiment
   data during reconnaissance.
4. Define explicit host eligibility/capability tags for experiment-edge work,
   e.g. `ros2`, `realsense`, `experiment-capture`, `edge-perception`,
   `robotics-logs`; generic `local-fast`, `code-fast`, background indexing and
   unrelated repo work must not route there by default.
5. Add a minimal health/status probe suitable for routing that can report busy,
   experiment-active, thermal/resource pressure and required service/repo
   availability without creating a public management surface.
6. Prove one safe read-only experiment-adjacent route, such as ROS/log/status
   inspection or a deterministic capture-pipeline health query. If the active
   experiment environment makes even that unsafe, record a truthful deferred
   proof rather than touching it.
7. Define data movement policy: keep raw/high-rate experimental data local where
   possible; move compact artefacts/metrics/logs or explicit datasets to lab for
   heavy analysis. Never use conversational transcripts as transport.

Gate: Jetson is a first-class, narrowly scoped experiment-edge node with no risk
of becoming an accidental general-purpose worker.

### P12.6 — active-estate fault/security tests

Exercise the currently reachable topology without destructive chaos testing:

- lab unavailable -> laptop receives truthful blocked/fallback result;
- Jetson unavailable/busy -> no experiment task silently rerouted to an unsafe
  host and no generic task routed to Jetson;
- model unavailable -> bounded escalation/failure is recorded;
- conflicting park lease -> mutation refused;
- invalid/unverified host -> ineligible;
- experiment reservation -> heavy lab GPU route yields;
- multimodal task -> unified route/telemetry works;
- auth failure -> no localhost/public bypass invented;
- service restart/recovery where already safely supported;
- verify no new `0.0.0.0`/Funnel/public model/MCP/shell exposure.

Use deterministic regression suites after each material change and one relevant
full-suite baseline before closure. Do not spend the phase repairing known
unrelated baseline failures unless a changed surface caused them.

### P12.7 — future host re-entry contracts (prepare, do not execute)

Create a compact durable re-entry checklist that both missing hosts can use later.
It must require live evidence, not prose.

**Interface PC re-entry:**

1. confirm identity/hostname/OS/hardware/Tailscale/LAN role;
2. inventory the existing UI/Misumi/Aoteru service and any historical
   `192.168.4.37:8770` reference rather than assuming it is still correct;
3. deploy/restore `svc:aoteru` there as the persistent authenticated human-facing
   front door only after private connectivity and rollback are proven;
4. integrate phone/mobile to that front door;
5. qualify it as an execution worker only if hardware + benchmark evidence later
   provide a real benefit.

**Home PC re-entry:**

1. live-confirm identity (including resolving the historical IN7O23D/IN7023D
   ambiguity), OS and hardware;
2. inventory household/Misumi, storage, memory, GPU/model runtime and service
   state;
3. decide service placement from measured fit: household/Misumi and memory-primary
   are plausible roles, not assumptions;
4. if hardware can help compute, benchmark the same estate task classes against
   lab before adding any worker route;
5. shadow/canary before promotion; never auto-promote on mere reachability;
6. preserve single-writer/lease and domain authority across hosts.

Neither future host is required for P12 closure.

### P12.8 — closure evidence and next-phase recommendation

Write `docs/aoteru-p12-active-estate-convergence-evidence.md` with:

- corrected topology and live inventories;
- exact gates passed/blocked and why;
- controller->lab route evidence;
- unified multimodal route evidence;
- paid-provider execution/escalation evidence or exact human auth blocker;
- experiment-priority/resource evidence;
- Jetson experiment-edge qualification evidence;
- fault/security results;
- future interface/home re-entry checklist pointer;
- tests and service/private-exposure evidence;
- residual risks ranked by impact.

Do **not** manufacture a P13 merely to continue development. Recommend the next
phase only if P12 exposes a real gap. Likely future triggers are: interface PC
returns (front-door/mobile integration), home PC returns (memory/secondary-worker
qualification), or sufficient real production traffic accumulates to justify
routing replay/shadow adaptation.

## Agentic execution policy

- Sonnet is the foreman, not the routing authority.
- Read durable repo evidence before acting; inspect live state before trusting old
  host/model documentation.
- Use deterministic shell/tests/config analysis for high-volume discovery.
- Use current qualified local models for cheap bounded reasoning when suitable.
- Delegate token-heavy independent repo analysis/implementation to cheaper workers
  only through existing safe mechanisms when useful; give each one a bounded
  objective and source pointers, not the whole conversation.
- Use a stronger cloud model only for genuinely difficult architecture/debugging
  or an independent high-consequence review; do not spend frontier calls on file
  search, formatting, repetitive tests or inventory.
- One worker owns each mutation unit; no swarm/group-chat orchestration.
- Verify every material mutation independently with tests/live evidence before
  proceeding.
- Commit cohesive checkpoints to `dev`; push only verified work. Never force-push.
- If a human-only boundary occurs, complete every independent sub-gate first,
  commit/push the checkpoint and report the **minimal exact operator action plus
  continuation instruction**. Do not restart completed work after the operator
  acts.

## Acceptance criteria

P12 is complete when, to the extent permitted by available credentials and a safe
experiment state:

1. estate config truthfully distinguishes laptop, lab, glovebox, home and
   interface;
2. laptop is proven as thin controller and lab as general worker;
3. a laptop-submitted task executes on lab and returns verified compact evidence;
4. all current text + vision aliases use one Odysseus task/telemetry path;
5. paid Claude/Codex execution uses the provider-neutral worker contract, or only
   a documented human auth action remains;
6. lab GPU/background inference yields to experiment priority;
7. Jetson is live-inventoried and constrained to experiment-edge capabilities;
8. a safe Jetson read-only route is proven or truthfully deferred due to active
   experiment safety;
9. home/interface remain ineligible but have precise live re-entry contracts;
10. leases, authority, auth, private exposure and existing LM4 model bindings
    remain regression-clean;
11. focused tests and one relevant full-suite baseline show no new regression;
12. evidence is committed and `origin/dev` matches local HEAD.

---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-08-30-aoteru-delegation-operationalisation
title: "Operationalise automatic specialist and estate delegation"
status: ready
priority: critical
task_type: bounded-runtime-convergence
created_by: chatgpt
created_at: 2026-08-30T11:50:00+01:00
executor: claude-sonnet-5
execution_mode: autonomous-until-acceptance
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
  - docs/aoteru-model-host-routing-contract.md
  - docs/aoteru-long-horizon-autonomous-convergence.agent-task.md
  - GO.md
  - config/routing.yaml
  - config/estate.yaml
  - config/models.yaml
outputs:
  - automatic controller delegation preflight integrated into the existing execution path
  - live capability snapshot exposed to the controller without requiring a laptop checkout
  - Codex-first routing for substantial bounded code work when eligible
  - qualified remote-compute routing for repetitive/batch/test/index/simulation work
  - explicit non-delegation evidence when eligible work remains in the controller
  - routing/delegation telemetry and deterministic acceptance tests
  - concise operator-facing diagnostics showing where and why work was routed
---

# Operationalise automatic specialist and estate delegation

## Mission

Fix the implementation gap that lets Claude sessions perform work in the controller context even though the existing Aoteru/Odysseus routing contract says heavy work should be submitted to Odysseus and routed to the cheapest adequate eligible execution lane.

This is **not** a routing redesign. The existing authority remains:

```text
checkout-free laptop controller
  -> Aoteru/Odysseus backend
  -> authority/repository resolution
  -> eligible host
  -> cheapest adequate deterministic/local/Codex/Claude mechanism
  -> verification
  -> compact result
```

Odysseus remains the single runtime routing authority. Do not create a second router, do not move PhD-domain routing into Odysseus, and do not make the laptop an execution worker.

## Problem to prove before changing code

Recent Claude sessions have underused Codex and lab/home compute because delegation is operationally optional. Confirm the actual cause in current code and telemetry. Specifically determine:

1. where a checkout-free laptop Claude request enters `/api/estate/*` or the current equivalent;
2. where task decomposition/routing/executor selection currently occurs;
3. whether controller prompts receive live worker/capability state before substantive execution;
4. whether substantial coding work can bypass Codex even when Codex is available;
5. whether repetitive/batch/test/index/simulation work can stay in the controller rather than be dispatched to eligible remote compute;
6. whether a completed task records why eligible work was retained by the controller;
7. which existing telemetry can measure delegation and avoidable controller execution.

Do not assume the diagnosis from prose. Inspect current code, tests, live lab backend state and recent routing/job telemetry where available.

## Governing execution invariant

For every substantive task unit:

```text
decompose
-> determine required capabilities
-> resolve authority/repo
-> inspect live eligible workers/executors
-> dispatch to the cheapest sufficiently capable lane
-> verify
-> escalate only on recorded evidence
-> integrate compact result
```

Controller execution is the fallback for work requiring controller-level judgement, synthesis, ambiguity resolution or arbitration. It is not the default simply because Claude can perform the work.

If an eligible task unit remains in the controller, record a concrete `nondelegation_reason`.

## Required routing behaviour

### Deterministic/local compute

Use deterministic mechanisms first where adequate. Use qualified local models and remote workers for bounded extraction, classification, indexing, repository scans, test execution, simulation, evaluation, data processing and other repetitive/token-heavy work.

Do not dispatch generic background inference to experiment-edge hosts. Jetson remains experiment-edge only.

### Codex

When substantial repository implementation, refactoring, debugging, test authoring, code review or repository reconnaissance is separable and Codex is eligible, Codex should normally own that bounded unit.

The controller should provide:

- objective;
- repository/read/write scope;
- invariants;
- acceptance criteria;
- evidence pointers;
- deterministic verification requirements.

Do not use Codex merely to duplicate controller reasoning. One mutation owner per unit.

### Claude/controller

Reserve the conversational controller for:

- intent and task decomposition;
- architecture and methodological judgement;
- research reasoning;
- ambiguity resolution;
- cross-worker synthesis;
- arbitration of conflicting evidence;
- final acceptance.

## Implementation constraints

1. Extend the existing task envelope, routing, estate, executor and telemetry surfaces. Do not create a parallel orchestration framework.
2. Preserve capability aliases and live eligibility. Do not hard-code model/vendor rankings into business logic.
3. Preserve the checkout-free laptop-controller product requirement.
4. Home is eligible only if live state proves it verified, healthy, reachable and suitable for the requested capability.
5. Lab remains the general worker when live and eligible, subject to experiment reservation/load constraints.
6. Jetson is not a generic worker.
7. Repo mutation must retain existing parking/lease/write authority.
8. Do not weaken deterministic verification, security, domain gates or quality floors to increase delegation statistics.
9. Parallelise only genuinely independent work or independent verification. No swarm by default.
10. Worker failure should trigger retry/reroute/escalation according to evidence, not silent wholesale fallback into the controller.

## Minimal implementation target

Prefer the smallest implementation that makes the behaviour unavoidable and observable. Likely components are:

1. **Delegation preflight** at the controller/backend boundary or earliest canonical task-planning point. It exposes the current capability/eligibility snapshot and identifies separable execution classes before work begins.
2. **Routing recommendation/decision** using the existing Odysseus authority and routing surfaces, not a new policy store.
3. **Enforced execution handoff** for eligible bounded task units, especially Codex code units and remote deterministic/local-compute units.
4. **Non-delegation reason** in the task/result/telemetry path when controller execution is selected despite an eligible alternate lane.
5. **Compact diagnostics** such as `why this route?`, executor/host/model alias, verification outcome and escalation reason.
6. **Replayable tests/fixtures** proving that the controller no longer silently consumes eligible execution work.

If existing abstractions already provide part of this, reuse them. Delete no useful routing contract merely because implementation has caught up with it.

## Metrics

Add or derive the smallest useful measurements. At minimum support calculation of:

```text
delegation_eligible_units
units_dispatched
units_retained_by_controller
avoidable_controller_execution_rate
codex_eligible_units
codex_dispatched_units
remote_compute_eligible_units
remote_compute_dispatched_units
verification_success_rate
reroute_or_escalation_rate
```

The principal success metric is **avoidable controller execution rate**, not raw agent-call count.

Do not game the metric by fragmenting tasks or dispatching useless workers.

## Required acceptance scenarios

Build deterministic/integration tests and, where safe, one live proof for each applicable lane.

### A. Substantial code task

Given a bounded repository implementation task with Codex live and write authority valid:

- controller plans/specifies;
- Codex receives the implementation unit;
- deterministic tests run;
- controller receives compact result/evidence;
- telemetry identifies Codex route;
- no duplicate implementation occurs in controller context.

### B. Repetitive compute task

Given a batch/repository-scan/test/index/evaluation task with an eligible remote worker:

- remote worker receives it;
- controller does not execute the mechanical body;
- result returns with host/executor evidence.

### C. Controller-retained reasoning

Given a genuine architecture/research-synthesis judgement:

- controller may retain it;
- routing decision truthfully records why specialist/remote execution is not adequate for the retained unit.

### D. Worker unavailable

Given Codex or a worker unavailable/unqualified:

- route is rejected for concrete eligibility evidence;
- fallback/escalation follows the existing contract;
- no stale prose is treated as live availability.

### E. Home qualification

If home is currently reachable, exercise only after live qualification. If it is unavailable/unverified, verify that it is not selected and do not block completion of the rest of this task.

## Use the estate while fixing the estate

This task itself must demonstrate the desired behaviour:

- keep Sonnet as foreman/integrator;
- use Codex for substantial bounded code implementation/reconnaissance where eligible;
- use lab/qualified remote compute for tests, scans and evaluation where appropriate;
- independently verify important outputs;
- record any non-delegation where a plausible lane was available.

If you perform the entire implementation directly in the Sonnet controller despite live eligible Codex/remote lanes, the task has failed its own acceptance criteria.

## Scope control

Do not restart the wider Aoteru convergence programme. Do not redesign memory, UI, research ingestion, model benchmarking or host topology unless a minimal change is directly required for this operationalisation.

Do not modify `obsidian-PhD/automation/config/agent_routing.yaml` to solve this runtime problem. That file is a PhD-repo policy contract. Odysseus already owns estate discovery, host/model routing, jobs, telemetry, leases and execution.

Finish this bounded runtime convergence first, then leave the wider `@GO.md` programme intact.

## Completion gate

Do not report completion until all are true:

1. actual bypass path was identified from code/live evidence;
2. controller receives or can obtain live routing/capability context automatically;
3. eligible substantial code work demonstrably routes to Codex by default;
4. eligible repetitive/compute work demonstrably routes to a qualified remote worker by default;
5. controller retention has a machine-readable reason;
6. telemetry supports avoidable-controller-execution measurement;
7. deterministic/integration tests cover routing, unavailable-worker and retention cases;
8. at least one safe live delegated proof succeeds on the current estate where infrastructure is available;
9. full relevant test suite is green or every irreducible failure is evidenced;
10. implementation and evidence are committed and pushed to `dev`;
11. independent fresh-context review finds no competing router, laptop-worker regression, authority widening or obvious bypass left open.

Return a compact final report containing only:

- root cause;
- implementation points;
- live delegation proofs;
- metrics/test evidence;
- commit SHA;
- any genuine external blocker.

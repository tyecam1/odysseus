---
title: Aoteru model-host routing contract
status: target-contract
owner: odysseus
as_of: 2026-08-20
scope: host placement, model routing, token economy, verification, continuous improvement
---

# Aoteru model-host routing contract

## Aim

Provide one central, provider-neutral routing authority for Aoteru so the user can speak to one persistent conversational front end while Odysseus selects the cheapest adequate execution route across deterministic tools, local models, Codex models and Claude models, on the correct worker host, with explicit verification and bounded escalation.

The contract must optimise quality, token/quota efficiency, latency and locality without fragmenting authority across skills, repositories, hosts or model-specific wrappers.

Target path:

```text
user -> Aoteru conversational front end -> Odysseus task envelope
     -> authority/repo -> eligible host -> cheapest adequate mechanism/model
     -> deterministic verification -> bounded escalation/independent review
     -> compact result -> Aoteru response
```

The conversational model owns intent and communication. Odysseus owns routing. Workers are disposable execution resources.

## Invariants

1. One central routing authority in Odysseus. No repo, skill, MCP or worker may create a competing model-selection or host-selection policy.
2. Resolve authority/repository before execution host; resolve execution host before model.
3. Deterministic software precedes model inference whenever adequate.
4. Adequate local inference precedes paid inference when measured quality meets the task quality floor.
5. Local-first is not local-at-any-cost: paid escalation is required when the local route does not meet the quality or verification requirement.
6. Routing uses stable capability aliases and live measurements, not permanent vendor/model rankings in business logic.
7. Home and lab are first-class worker targets. Current unavailability must not be hard-coded into architecture.
8. Today, lab is the only verified/available worker. Home remains registered but ineligible until live evidence sets verified, healthy and reachable true.
9. The laptop/interface is the human control surface, not a normal execution worker.
10. Repo mutation requires the existing Odysseus parking/lease authority. Routing never widens write authority.
11. Workers receive bounded task/evidence pointers, not whole conversational transcripts or duplicated repository context.
12. Verification is deterministic first, then independent-model review only when required.
13. Escalation is evidence-triggered, not based on vague difficulty judgments.
14. No swarm by default. One worker owns each task unit; parallelism is justified only by independent evidence gathering or deliberately independent verification.
15. Routing telemetry may improve future choices but cannot silently weaken permissions, domain gates, quality floors or verification requirements.

## Human-facing default

The normal laptop Claude harness should present Aoteru through a strong, efficient conversational model. The current preferred role is Claude Sonnet-class inference at a moderate effort setting, but this is a role rather than a permanent model pin.

Aoteru should normally submit work to Odysseus instead of executing heavy repo/research work in the conversational context merely because the front-end model can do it.

## Host model

```yaml
hosts:
  interface:
    role: controller
    execution_worker: false

  lab:
    role: worker
    execution_worker: true
    verified: true
    availability: live
    routing_eligible: true

  home:
    role: worker
    execution_worker: true
    verified: false
    availability: unavailable
    routing_eligible: false
```

Home becomes eligible only from live discovery proving at minimum:

```text
verified = true
healthy = true
reachable = true
```

Never infer these states from old documentation.

## Routing dimensions

Every model-required task resolves both:

```text
WHERE?                         WHAT?
verified worker host           deterministic mechanism
                               local-fast
                               local-strong
                               Luna-class
                               Haiku-class
                               Terra-class
                               Sonnet-class
                               Sol-class
                               Opus-class
```

A route is therefore an execution tuple, not only a model name:

```yaml
route:
  host: lab
  executor: local | codex | claude | deterministic
  model_alias: local-fast | local-strong | code-fast | code-strong | reasoning-strong | null
  concrete_model: resolved_from_live_registry
```

## Default economic ladder

Use only as a seed policy; P7/live benchmark evidence overrides it.

```text
0 deterministic software
1 local-fast
2 local-strong
3 Luna/Haiku class
4 Terra/Sonnet class
5 Sol class
6 Opus class
```

Luna and Haiku largely occupy cheap scout/verification roles. Prefer the provider already native to the active workflow unless cross-provider independence is required.

Terra-class inference is normally the routine implementation worker. Sonnet-class inference is normally the Aoteru conversational foreman and can perform orchestration/reasoning when justified.

Sol-class inference is the normal expensive escalation for difficult engineering, debugging, scientific reasoning and deep review. Opus-class inference is reserved for frontier ambiguity, long-horizon architecture/synthesis, high-consequence arbitration or independent review where its measured advantage justifies the quota cost.

## Model aliases

Business logic must target capability aliases rather than concrete model brands:

```yaml
aliases:
  local-fast:
    purpose: cheap extraction, classification, reconnaissance

  local-strong:
    purpose: strongest adequate local reasoning/implementation

  code-fast:
    purpose: routine code work

  code-strong:
    purpose: difficult code work

  reasoning-strong:
    purpose: difficult analysis/research/architecture

  vision:
    purpose: multimodal work

  embedding:
    purpose: derived semantic indexing

  reranker:
    purpose: retrieval ranking
```

Concrete mappings come from live host inventory plus benchmark results.

## Canonical task envelope

```yaml
task:
  id:
  objective:
  task_class:
  domain:
  repo:

  authority:
  read_scope:
  write_scope:

  complexity: trivial | routine | hard | frontier
  consequence: low | medium | high
  autonomy: read | propose | write

  requirements:
    capabilities: []
    context_tokens:
    data_locality:
    hardware: []

  placement:
    requested_host: auto
    eligible_hosts: []
    parked_host:
    fallback_allowed: true

  routing:
    quality_floor:
    local_first: true
    paid_allowed: true
    cross_provider_required: false

  budget:
    max_worker_calls:
    max_paid_calls:
    max_frontier_calls:
    max_context_tokens:
    latency_priority:

  verification:
    deterministic: []
    independent_model_required: false

  context:
    source_pointers: []
    memory_pointers: []
```

## Eligibility and scoring

Host eligibility is a hard filter:

```text
reachable
healthy
repo/service available
parking/write authority available when needed
required tools/hardware available
data policy permits execution there
```

Model/mechanism eligibility is a second hard filter:

```text
capability match
quality benchmark at or above task floor
context capacity sufficient
provider/runtime available
quota/budget permits route
```

Only eligible routes are scored. The implementation may evolve the exact formula, but it must prefer demonstrated success and adequate local execution while accounting for resource cost:

```text
score =
    measured_quality
  + locality/determinism benefit
  - expected paid-token/quota cost
  - latency penalty
  - host-load penalty
  - observed escalation/retry risk
```

No score may override a hard authority, security or quality constraint.

## Escalation contract

Escalate only on recorded evidence such as:

```text
deterministic_gate_failed
worker_failed
insufficient_capability
confidence_below_threshold
unresolved_ambiguity
conflicting_evidence
context_limit
quality_floor_not_met
```

Normal pattern:

```text
cheap adequate worker -> deterministic checks -> done
                                      |
                                      +-> evidence-triggered stronger worker
```

Do not pre-emptively send the same context to multiple expensive models.

## Independent verification

Prefer deterministic checks first: tests, schemas, lint/type checks, git diff checks, source/claim checks and domain gates.

When model independence is materially useful, prefer cross-provider review:

```text
Codex primary -> Claude verifier
Claude primary -> Codex verifier
Sol-class primary <-> Opus-class adversarial review for high-consequence reasoning
```

A third inference occurs only if disagreement materially affects the outcome.

## Compact worker result contract

```yaml
status: complete | blocked | failed | needs_escalation
result:
  summary:
evidence: []
changes: []
verification: []
uncertainty: []
escalation:
  required: false
  reason:
handoff:
  context_pointers: []
```

Do not return worker scratchpads to the conversational model.

# Continuous improvement contract

Routing must improve from observed estate performance rather than remain a static hand-authored ranking.

## Telemetry to capture per routed task

At minimum:

```text
task_class
complexity/consequence
host
mechanism/provider/model alias + concrete model
input/context size where measurable
paid/quota consumption where measurable
latency
deterministic verification outcomes
worker self-confidence if available
retry count
escalation occurrence and reason
independent-review outcome
human correction/rejection where explicitly observed
final task status
```

Record source/result pointers rather than sensitive prompt copies where possible.

## Learning loop

```text
execute
  -> verify
  -> record outcome/cost/latency/escalation
  -> aggregate by task class + host + route
  -> compare candidate routes against incumbent
  -> shadow/canary candidate policy
  -> promote only if quality floor/regression gates hold
  -> continue measuring
```

The system should continuously update empirical route estimates such as:

```text
success probability
first-pass verification rate
expected retries/escalations
latency distribution
paid-token/quota consumption
local throughput
host availability/load
```

Use recency weighting or equivalent so stale model/hardware results decay rather than permanently dominate routing.

## Safe adaptation boundary

Continuous improvement is not unconstrained self-modification.

The runtime may automatically update ephemeral statistics and select among already-approved eligible routes. Changes to permissions, domain gates, host trust, model allowlists, quality floors, verification requirements or routing-code semantics require the existing governed change process.

Policy/config tuning should follow:

1. collect sufficient evidence;
2. generate a candidate change with rationale and before/after metrics;
3. test in replay/shadow mode against a representative task corpus;
4. run deterministic regressions;
5. canary where appropriate;
6. promote only on non-inferior quality with a meaningful cost/latency benefit, or superior quality within the allowed budget;
7. retain rollback and provenance.

A local estate steward may propose routing improvements and run bounded evaluations, but must not silently relax safety/authority constraints.

## Exploration

Avoid getting permanently stuck on yesterday's best route. Allow small bounded exploration only among routes that already meet the safety/quality eligibility floor. Exploration must be disabled or strongly reduced for high-consequence tasks unless explicitly validated.

New models or newly available home hardware enter as candidates, not automatic defaults. Benchmark them against the real estate task corpus before promotion.

## Home re-entry

Current implementation is lab-first. When home becomes reachable:

1. verify identity and service health live;
2. inventory CPU/GPU/VRAM/RAM/storage/runtimes/models/repos;
3. benchmark the same task classes used for lab;
4. add home routes as candidate eligible routes;
5. run shadow/comparative evaluation;
6. promote task classes to home only where measured performance justifies it.

No architecture rewrite should be necessary.

# Implementation acceptance criteria

This contract is implemented only when all of the following are true:

1. One Odysseus-owned routing API accepts the canonical task envelope and returns a host+mechanism+model route.
2. Routing consumes live estate/model inventory and parking state rather than static prose.
3. Lab is currently eligible; home fails truthfully as unavailable without blocking lab execution.
4. Deterministic and local routes can be selected ahead of paid inference when they meet the quality floor.
5. Codex and Claude workers are invoked through the same provider-neutral job/result contract.
6. Heavy work can leave the laptop Sonnet conversation and execute next to the parked repo while only compact results return.
7. Evidence-triggered escalation is enforced and observable.
8. Per-task routing telemetry is persisted.
9. A benchmark/replay evaluator can compare incumbent versus candidate routing policies.
10. Candidate route/policy changes are shadowed/canary-tested before promotion.
11. Routing statistics adapt with new measured outcomes and decay stale evidence.
12. Home can be added later through discovery + benchmark + eligibility without changing the task or routing contracts.
13. No duplicate router, queue, lease authority, model registry or domain-specific routing policy is introduced.

## Implementation placement

Extend existing Odysseus ownership rather than adding another orchestrator. Expected canonical surfaces are:

```text
config/models.yaml        # capability aliases and approved model candidates
config/estate.yaml        # hosts/services and live-resolution contract
config/routing.yaml       # central routing policy/quality floors/budgets
docs/aoteru-model-host-routing-contract.md
Odysseus SQLite           # jobs, outcomes, routing telemetry/policy evaluation state
```

If equivalent existing surfaces already own any of these concerns, extend them instead of duplicating them.

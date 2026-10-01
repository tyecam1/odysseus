---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-01-sol-packet-efficiency
title: "Optimise Sol usage through fewer, higher-yield decision packets"
status: ready
priority: high
task_type: resource-orchestration
created_by: gpt-5.6-sol
created_at: 2026-10-01T13:43:00+01:00
updated_at: 2026-10-01T13:43:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single-plus-verifier
architecture_rationale: "This is primarily an operating-contract and routing optimisation. One strong planner should identify where Sol calls fragment unnecessarily and define a batching contract; implementation can then be bounded and independently verified against quality loss."
single_agent_baseline: "Audit recent Sol usage, define a packet compiler and measurable efficiency targets, then implement the smallest routing changes needed to batch compatible decisions without weakening independent verification."
execution_host: lab
context_budget: high
coordination_reason: "Sol is a scarce strong-model resource. Optimisation must preserve scientific quality and model-independence requirements while increasing useful decisions per invocation."
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
branch: claude/sol-packet-efficiency-20261001
allowed_paths:
  - config/**
  - src/**
  - routes/**
  - evals/**
  - tests/**
  - docs/**
  - automation/review/**
denied_paths:
  - companion/**
inputs:
  - AGENTS.md
  - config/models.yaml
  - config/routing.yaml
  - docs/aoteru-model-host-routing-contract.md
  - automation/review/agent-tasks/inbox/2026-09-13-daily-model-usage-reset-harvest.agent-task.md
  - automation/review/agent-tasks/inbox/2026-09-13-operating-contract-model-role-evaluation-system.agent-task.md
  - automation/review/agent-tasks/ready/2026-10-01-system-one-research-decision-layer.agent-task.md
outputs:
  - Sol packet-efficiency operating contract
  - compatible-work packet compiler/batcher
  - routing changes reducing unnecessary Sol invocation frequency
  - telemetry for decisions/verifications per Sol packet
  - comparative evaluation against current fragmented-call baseline
result_path: automation/review/models/2026-10-01-sol-packet-efficiency.md
review_report_path: automation/review/models/2026-10-01-sol-packet-efficiency-verification.md
handoff_model: codex_subscription
operator_decision_path: automation/review/models/2026-10-01-sol-packet-efficiency.md
supersedes: []
duplicates: []
notes: "Optimise useful work per Sol invocation, not raw token consumption. Larger packets must remain coherent, bounded and independently auditable. Do not batch tasks merely to spend quota or collapse verification that requires independent contexts."
---

# Sol packet efficiency

## Goal

Reduce the rate at which the estate exhausts Sol usage by increasing the number of useful scientific/engineering decisions, adjudications and verifications obtained from each Sol invocation.

Current failure mode to test:

> Sol is often used for one narrow decision or verification at a time, while Claude usage remains available longer. Repeated setup/context costs and fragmented review packets may therefore consume Sol quota inefficiently.

Target pattern:

```text
cheap/local/Claude preparation
  -> collect compatible unresolved decisions
  -> compile one bounded Sol packet
  -> Sol adjudicates multiple items in one invocation
  -> machine-readable per-item decisions + shared synthesis
  -> only unresolved/high-consequence disagreements trigger another Sol call
```

The objective is **useful decisions per scarce Sol call**, not maximal prompt size.

## Primary metrics

Track at minimum:

- Sol invocations per research/work session;
- input and output tokens per invocation where available;
- accepted decisions per invocation;
- accepted verifications per invocation;
- accepted decisions per 1k Sol tokens;
- repeated/shared context tokens avoided;
- proportion of packets requiring follow-up Sol calls;
- correction rate after Claude/Codex/human verification;
- false agreement or missed-defect rate;
- latency and quota-window consumption;
- percentage of Sol output that materially affects a downstream decision.

Prefer:

`accepted consequential decisions / Sol invocation`

and:

`accepted consequential decisions / Sol token`

over total token utilisation.

## Packet classes

Implement a small vocabulary rather than arbitrary batching.

### 1. Decision packet

Several bounded decisions that share the same evidence/context base.

Examples:

- adjudicate 5 candidate J1 propositions against the same evidence set;
- decide which of 6 unresolved research actions materially changes the contribution;
- assess several related claim ceilings against one corpus.

### 2. Verification packet

Several completed lower-cost outputs requiring the same type of strong review.

Examples:

- verify 8 extracted paper findings;
- challenge 6 claim-evidence mappings;
- review 5 proposed routing changes;
- inspect several implementation diffs against one contract.

### 3. Collision/adversarial packet

A coherent set of novelty, closest-prior or counterexample checks sharing one scientific question.

### 4. Gate packet

A deliberately compact collection of all evidence needed for one consequential gate or authorial decision.

Do not create a generic mega-packet containing unrelated domains merely to reduce call count.

## Packet admission rules

Items may share one Sol invocation only when all are true:

1. they require approximately the same Sol role;
2. shared context is substantial enough to create real reuse;
3. one item cannot contaminate the judgement of another in a way that invalidates independence;
4. all items can fit comfortably within context/output limits;
5. each item retains an explicit ID, question, evidence pointers and acceptance criterion;
6. the expected benefit of waiting for a packet exceeds the urgency cost.

Do not batch when:

- independent fresh-context verification is methodologically required;
- one decision is urgent or blocking;
- contexts are unrelated;
- one item's answer would improperly reveal another item's expected label;
- packet size risks truncation or shallow treatment;
- high consequence requires separate independent adjudication.

## Packet compiler

Implement a deterministic compiler that turns compatible queued decisions into one structured request.

Input per item:

```yaml
decision_id:
parent_task:
role_required:
question:
decision_type:
consequence:
evidence_pointers:
shared_context_key:
candidate_options:
acceptance_criteria:
independence_required:
deadline:
```

Compiled packet:

```text
shared context once
global operating constraints once

ITEM 1
question
evidence pointers
required output schema

ITEM 2
...

FINAL
cross-item synthesis only where scientifically legitimate
unresolved items
recommended escalations
```

Sol must return a machine-parseable per-item result so one failure does not invalidate the entire packet.

## Preparation before Sol

Move mechanical work out of the scarce strong-model call.

Before packet construction, use deterministic/local/Claude/Codex routes to:

- resolve repository authority;
- collect evidence pointers;
- deduplicate repeated context;
- normalize source extracts;
- calculate deterministic metrics;
- identify exact unresolved questions;
- remove decisions already settled by rules/tests;
- compress prior discussion into source-grounded state;
- pre-screen obvious low-consequence items.

Sol should receive **decision-ready evidence**, not be paid to reconstruct state that cheaper workers can prepare reliably.

## Verification density

Where one Sol call is acting as verifier, give it multiple independently prepared candidate outputs when compatible.

Prefer:

```text
Claude/Codex/local prepare N bounded outputs
-> one Sol verification packet
-> per-item PASS / REVISE / ESCALATE + defect list
```

over:

```text
prepare one -> Sol -> prepare next -> Sol -> prepare next -> Sol
```

Do not let batching convert genuinely independent verification into self-confirmation.

## Follow-up suppression

A Sol packet should minimise unnecessary conversational repair.

Require each item to state:

- exact decision requested;
- allowed verdicts;
- evidence boundary;
- what uncertainty must be surfaced;
- what would trigger escalation;
- what must not be re-opened.

Require Sol to return:

- verdict;
- concise rationale;
- evidence references;
- uncertainty;
- whether another strong-model call could plausibly change the decision.

A second Sol call should occur only when:

- the packet was materially malformed/incomplete;
- new evidence appeared;
- a verifier found a consequential defect;
- unresolved ambiguity crosses a declared threshold.

Do not use Sol for wording polish or repeated confirmation of unchanged conclusions.

## Interaction with research tuners

Do not expose packet size as another user-facing research tuner.

Use the existing research profile to influence packet content:

- high adversariality groups compatible challenges/counterexamples into one red-team packet;
- high prior-art pressure groups closest-prior collisions;
- high evidence strictness increases verification density;
- high stopping pressure discourages repeated unchanged Sol reviews.

Packetisation changes resource use, not epistemic standards.

## Scheduling and accumulation

Allow a short bounded accumulation window for non-urgent Sol-eligible work so related decisions can share a packet.

The system should not indefinitely delay important work waiting for a fuller packet.

Packet dispatch occurs when any of these is true:

- a blocking/high-priority item is ready;
- enough compatible items exist to produce material context reuse;
- packet reaches safe context/output capacity;
- bounded accumulation window expires;
- relevant Sol quota is approaching reset and useful authorised work exists.

Exact thresholds must be evidence-backed rather than arbitrary permanent constants.

## Baseline audit

Before implementation, sample recent Sol-using runs and classify each call:

- unavoidable single decision;
- could have been combined with adjacent call(s);
- repeated unchanged verification;
- context reconstruction overhead;
- wording/polish that should have used cheaper model;
- necessary independent review;
- failed/low-value invocation.

Estimate the realistic upper bound on call reduction without quality loss.

## Evaluation

Replay a representative historical set using:

A. current fragmented Sol invocation pattern;
B. packetised pattern.

Hold underlying decisions/evidence constant.

Compare:

- number of Sol calls;
- total Sol tokens where measurable;
- accepted decisions;
- defects found;
- human corrections;
- unresolved decisions;
- time to completion;
- quality against independent/human adjudication.

The packetised route passes only if it reduces calls/tokens materially **without degrading consequential decision accuracy or defect detection**.

Also test increasing packet sizes to identify where quality begins to fall. Do not assume larger is always better.

## Integration with routing

Extend existing Odysseus routing rather than adding a separate scheduler.

When the router selects Sol for a non-urgent bounded decision:

1. check whether compatible pending Sol work exists;
2. check whether the item may legally/methodologically be batched;
3. append to a bounded packet where useful;
4. otherwise dispatch singly;
5. record why batching did or did not occur.

Strong-model escalation remains evidence-triggered.

## Relationship to usage harvesting

The existing usage-reset harvest task should consume this packet interface.

When Sol capacity is near expiry:

- prefer filling coherent pending packets;
- do not manufacture work;
- do not split one coherent packet into multiple calls to consume allowance;
- preserve margin for completion.

When Sol is scarce relative to Claude, prefer Claude for preparation and reserve Sol for compressed adjudication/verification packets.

## Acceptance criteria

- [ ] recent Sol usage has a quantified fragmentation baseline;
- [ ] one small packet vocabulary is defined;
- [ ] a deterministic compatibility/admission rule exists;
- [ ] repeated shared context is represented once per packet where safe;
- [ ] cheaper workers prepare decision-ready evidence before Sol;
- [ ] every packet returns individually attributable per-item decisions;
- [ ] mandatory fresh-context/independent checks cannot be accidentally batched;
- [ ] routing records why an item was batched or sent alone;
- [ ] historical replay shows materially fewer Sol calls or lower Sol tokens per accepted decision;
- [ ] consequential decision quality and defect detection do not regress;
- [ ] packet-size stress testing identifies a safe operating region;
- [ ] unchanged conclusions do not trigger repeated Sol verification by default;
- [ ] the usage-reset harvest task can exploit coherent packets;
- [ ] model-role-contract telemetry records packet ID, item count, shared-context reuse, outcomes and corrections;
- [ ] affected tests and task lint pass;
- [ ] independent verification precedes promotion.

## Stop rule

Stop optimising once additional batching no longer materially improves accepted decisions per Sol call/token or begins to degrade decision quality, latency or independence.

Do not optimise for the largest possible packet.

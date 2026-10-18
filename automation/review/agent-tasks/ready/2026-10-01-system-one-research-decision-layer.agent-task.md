---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-01-system-one-research-decision-layer
title: "Implement capability-routed Jev / CLM-8B / Laya research decision layer"
status: ready
priority: high
task_type: implementation
created_by: gpt-5.6-sol
created_at: 2026-10-01T11:00:00+01:00
updated_at: 2026-10-01T11:00:00+01:00
executor: codex_subscription
execution_mode: implementation
architecture: single-plus-verifier
architecture_rationale: "Extend the existing Odysseus router with one provider-neutral typed-decision layer; independently verify research-governance and routing claims before promotion."
single_agent_baseline: "One implementation owner adds the abstraction, adapters, benchmark and integration; one fresh verifier attacks calibration, routing and governance."
execution_host: lab
context_budget: high
coordination_reason: "Avoid three model-specific orchestration stacks. Provider selection must remain central and evidence-backed."
requires_remote_compute: true
requires_local_model: true
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: codex/system-one-research-decision-layer-20261001
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
  - config/estate.yaml
  - docs/aoteru-model-host-routing-contract.md
  - src/estate_router.py
  - src/agent_loop.py
  - automation/review/agent-tasks/inbox/2026-09-13-operating-contract-model-role-evaluation-system.agent-task.md
outputs:
  - provider-neutral typed-decision interface
  - Jev, CLM-8B and Laya adapters
  - held-out decision benchmark and capability routing evidence
  - eight-scalar research-tuner configuration and derived behaviour
  - research action selection / escalation integration
  - telemetry integrated with model-role-contract evaluation
result_path: automation/review/models/2026-10-01-system-one-research-decision-layer.md
review_report_path: automation/review/models/2026-10-01-system-one-research-decision-layer-verification.md
handoff_model: claude_subscription
operator_decision_path: automation/review/models/2026-10-01-system-one-research-decision-layer.md
supersedes: []
duplicates: []
notes: "Typed-decision models support bounded routing and ranking. They never replace evidence rules, scientific synthesis, authorial gates or human judgement. Vendor claims are hypotheses until reproduced on this estate."
---

# System One research decision layer

## Goal

Implement a low-latency decision layer beneath generative research agents:

`research state -> finite candidate actions -> typed decision/ranking -> tuner-aware threshold -> execute one action or escalate -> verify -> telemetry`.

The decision layer may rank only explicit candidates. It must not generate scientific claims, change evidence ceilings, alter registered inclusion criteria, or make authorial Gate decisions.

## Candidate capability hypotheses

- **Jev:** hosted general typed-decision baseline when remote processing is allowed and its measured zero-shot quality/calibration justifies use.
- **CLM-8B:** local state-action ranking, repeated-action caching, best-of-N selection and verifier work; evaluate task-specific projection-head tuning only after zero-shot baseline.
- **Laya:** lightweight local Choice/Score/Noul gates, batching and low-cost CPU-capable triage.

These are hypotheses, not bindings. Benchmark all eligible routes on the same research decisions.

## Unified contract

Expose validated primitives:

- `choice(state, question, options)`
- `score(state, question, ordered_rubric)`
- `noul(state, statement)`
- `rank(state, candidates)` when natively supported

Return provider/checkpoint identity, probability distribution, confidence, latency, usage/cost where available, local/remote placement, decision-contract version and fallback/escalation reason.

Unsupported primitives must fail explicitly rather than being silently emulated by a generative model.

## Research tuners

Implement eight operator-facing scalars in `[0,1]`:

```yaml
adversariality:
novelty_priority:
exploration:
evidence_strictness:
prior_art_pressure:
attribution_pressure:
industrial_grounding:
stopping_pressure:
```

Support named profiles plus per-run overrides. Derive secondary behaviour deterministically rather than exposing more controls.

Minimum derived behaviours:

- counterexample pressure from adversariality and evidence strictness;
- closest-prior pressure from prior-art and novelty;
- claim conservatism from adversariality and evidence strictness;
- search breadth from exploration;
- comparator scrutiny from evidence strictness and attribution pressure;
- continuation threshold from stopping pressure.

Tuners may change task priority, query framing, escalation and stopping thresholds. They must never change provenance requirements, evidence ceilings, source-native meaning, access/absence rules, novelty/firstness requirements, registered eligibility criteria or authorial gates.

## High-value research uses

1. Rank next actions such as counterexample search, closest-prior search, unresolved extraction, synthesis or stop.
2. Admit expensive work only when expected information gain justifies it.
3. Gate escalation to strong generative models when evidence is conflicting, confidence is low or verification is needed.
4. Triage candidate papers against a named evidence gap before expensive retrieval/full-text synthesis.
5. Rank best-of-N independently generated analyses/extractions.
6. Flag likely contract-adherence problems such as scope drift, unsupported broadening, missing comparator or missing provenance.

Paper triage is prioritisation only, not final methodological inclusion/exclusion.

## Capability routing

Extend the existing Odysseus router; do not create a second router.

Select providers using hard eligibility plus measured task evidence:

- local/remote data policy;
- host/runtime availability;
- primitive support;
- context/state size;
- option/candidate count;
- language support;
- batch/latency requirement;
- task-class accuracy and calibration;
- cost/quota;
- task-specific trained head availability;
- cache benefit.

Expected patterns to test, not hardcode:

- Laya for cheap recurring local gates and batch triage;
- CLM-8B for local ranking and verifier workloads;
- Jev for remote general typed decisions when measured quality warrants it.

The valid result may be `no adequate System One route`, followed by deterministic or generative escalation.

## Benchmark and promotion

Create a held-out corpus from real historical research decisions with adjudicated labels. Include:

- next-action selection;
- paper relevance to a specific evidence gap;
- closest-prior collision triage;
- claim-ceiling/evidence-strength classification;
- intervention-attribution concern detection;
- continue-vs-stop decisions under a fixed stopping rule;
- contract-adherence risk;
- best-of-N selection.

Measure accuracy/top-k, Brier score or equivalent calibration measure, false-confidence rate, abstention/escalation quality, latency, cost/resource use and downstream correction burden.

Compare against a deterministic baseline, a cheap current generative route and strong-model/human adjudication where available.

Do not produce a global model leaderboard. Promote provider/task bindings only when held-out evidence supports them.

## Fine-tuning rule

Do not fine-tune first.

1. Establish zero-shot baseline.
2. Identify a recurring decision class with enough labelled traces.
3. Split by research unit/task to prevent near-duplicate leakage.
4. Fine-tune the smallest relevant component.
5. Compare against zero-shot and deterministic baselines.
6. Promote only on held-out improvement.

CLM heads and Laya typed-decision tuning are explicit candidates.

## Integration phases

1. **Attest live state:** current provider releases/access, licences, host resources and actual runnable routes.
2. **Add one typed-decision interface:** schema validation, explicit unsupported states, timeouts and confidence handling.
3. **Implement three adapters:** separately discoverable/disableable; no silent fallback.
4. **Benchmark:** same held-out corpus for all eligible providers.
5. **Bind capabilities:** only evidence-backed task/provider routes.
6. **Implement tuners:** profile + overrides + deterministic derived behaviour.
7. **Integrate research actions:** task selection, information-gain admission, escalation and stopping.
8. **Integrate telemetry:** reuse the existing model-role-contract-task evaluation system.
9. **Pilot on bounded J1 replay:** compare contribution, red-team and low-exploration/consolidation profiles without changing canonical J1 claims.
10. **Independent verification:** attack calibration, false confidence, leakage, fallback, tuner semantics and research authority before promotion.

## Required telemetry

Record at least:

`decision_id | parent_run_id | task_class | profile | tuner_vector | decision_contract | provider/model/checkpoint | candidate_set_hash | probabilities | selected_action | thresholds | latency/usage | downstream outcome | verifier/human agreement`.

Do not record private chain-of-thought.

## Acceptance criteria

- one provider-neutral typed-decision interface;
- all three providers can be discovered and disabled independently;
- no business logic hardcodes a preferred vendor;
- promoted bindings have held-out estate evidence;
- probabilities are evaluated for calibration rather than treated as truth;
- low-confidence/high-consequence cases escalate safely;
- eight versioned tuners have profile + override semantics;
- controlled tests show tuner changes produce predictable action-selection changes without altering epistemic invariants;
- System One cannot create scientific claims or make authorial Gate decisions;
- paper triage cannot silently become final inclusion/exclusion;
- telemetry reconstructs important decisions;
- bounded J1 replay shows useful routing/action-selection value without degrading scientific correctness;
- affected tests and agent-task lint pass;
- independent verification and human review precede capability promotion.

## Stop rule

Stop expansion when the system has one stable interface, at least two genuinely useful evidence-backed provider/task bindings, safe fallback/escalation, and demonstrated tuner-driven research-action selection.

Do not integrate all three merely for symmetry if one adds no distinct capability.

## Non-goals

- replacing generative scientific reasoning;
- model-made novelty/truth/publication decisions;
- autonomous contract modification;
- global model ranking;
- synthetic benchmark volume without a routing decision;
- custom training before zero-shot evidence;
- parallel calls to every provider on every decision.

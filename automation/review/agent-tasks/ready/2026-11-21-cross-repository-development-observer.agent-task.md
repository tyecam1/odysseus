---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-21-cross-repository-development-observer
title: "Deploy an evidence-linked cross-repository development observer"
status: ready
priority: high
task_type: reliability-observability-evaluation
created_by: operator-directed-chatgpt
created_at: 2026-11-21T21:20:00+00:00
updated_at: 2026-11-21
executor: claude_subscription
execution_mode: read-only-retrospective-then-opt-in-event-driven-canary
execution_host: lab
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: dev
related_tasks:
  - 2026-11-04-bounded-verification-convergence
  - 2026-11-09-autonomous-blocker-reconciliation-and-opus-escalation
  - 2026-11-09-lazyusage-bounded-persistent-continuation
  - 2026-09-08-subscription-usage-attribution-for-continuous-system-improvement
  - 2026-09-13-operating-contract-model-role-evaluation-system
inputs:
  - AGENTS.md
  - START-AGENTIC.md
  - automation/review/agent-tasks/README.md
  - config/repositories.yaml
  - docs/runtime-work-packages/loop-graph-and-observability.md
  - docs/runtime-work-packages/run-trace-loss-credit-assignment.md
  - docs/runtime-work-packages/2026-11-19-lazyusage-reliability-acceptance.md
  - evals/prompt-applications/**
  - evals/prompt-evolution/**
  - src/lazy_usage_runtime.py
  - src/lazy_usage_coordinator.py
  - live backend execution/lease/verification state (read only; inspect at execution time)
allowed_paths:
  - src/**
  - scripts/**
  - tests/**
  - config/**
  - routes/**
  - docs/runtime-work-packages/**
  - automation/review/**
  - evals/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
  - "**/*.pdf"
result_path: docs/runtime-work-packages/2026-11-21-development-observer-pilot.md
---

# Development Observer: diagnose failure, re-verification, backlog and wasted work

## Decision and scope

Build a **passive learning/diagnostic capability within the existing Odysseus backend**, not another agent scheduler, queue, privileged daemon, model router, storage authority or review gate. It observes Odysseus, Misumi and PhD executions through registered repository authority; domain mutations remain with their owners. Start with the **live `dev` state**, existing status/evidence contracts and actual lab database. User requests an immediate evidence baseline, but the shipping-first rule remains binding: do not preempt an accepted near-shipping task for speculative architecture. A read-only audit may start immediately; live instrumentation requires normal verification and deployment. No fabricated retrospective coverage or claim that a GitHub card implies activation.

**Question:** Which observable conditions account for failed, repeated or stalled development, and which small policy or engineering changes demonstrably improve verified delivery without increasing missed defects, safety risk, research-integrity risk, cost or operator burden?

### Existing ownership to reuse, not duplicate

- `2026-11-04-bounded-verification-convergence` owns reviewer verdict semantics and stopping/reopening policy; this observer measures causes and supplies cases. Do **not** introduce a competing verification-controller.
- `2026-11-09-autonomous-blocker-reconciliation-and-opus-escalation` owns actual blocker resolution and escalation; this observer supplies evidence and detects stale rechecks.
- `/lazyUsage`, existing task queues, lease/execution/verification database, `evals/prompt-*`, `src/prompt_evolution.py`, `src/agent_runs.py`, existing observability contracts and prompt register retain authority. Do not create a second prompt-initialiser version for this one-off task.
- Read external provider/PR/CI data only where existing credentials and policy permit. Misumi's queue layout is not Odysseus's layout. Do not assume the host is reachable or all repos are indexed.

## Stage 0: forensic inventory and baseline (read-only, first)

1. Inspect current `dev` HEAD; actual worker/service state, active leases, task queues, existing tracing and prompt-evaluation paths; source APIs and security boundaries. Run existing `aoteru preflight` / registered portfolio inspection. Inventory sources as **live**, **Git-backed**, **partial**, or **unavailable**; record coverage windows and join-key completeness.
2. Produce a reconciled backlog by owner repo, bucket, declared status, acceptance evidence, age, priority, dependency, review debt, last meaningful transition and stale-state discrepancy. Count task cards separately from *accepted unfinished work*, blocked legitimate work, untriaged proposals and verified delivery. Never merge cross-repo authorities.
3. Construct a chronological, source-linked retrospective including **at least 12 real episodes if recoverable**, or all that exist, with explicit sampling limits: successful first-pass deliveries, regressions, provider/host failures, review rejections after passing tests, repeated checks with/without new evidence, stale blocker/debt, interrupted workers, and bounded false negatives. Include the 2026-11-21 rejected write despite 9,843 passing tests (PR #300), the live-unit-test worker kill (PR #296), verification-debt lifecycle (#295/#300), and partial usage metering (#301). Do not infer causal mechanisms solely from commit prose.
4. Record a deterministic baseline report and an *evidence availability matrix*, not a speculative dashboard. The correct result may be that much historical execution detail is unrecoverable.

## Stage 1: minimal causal evidence model

Reuse existing spans or add only missing fields to the existing runtime/trace mechanism. Join on canonical `repo_id, task_id, task_revision, run_id/activation_id, execution_id, trace_id/span_id, commit_sha, PR, test_run, review_id` where actually available. Correlate by timestamps only as a low-confidence fallback; preserve source provenance, event time vs ingestion time, idempotent replays and independent status/acceptance fields. Respect OTel trace/span and relevant GenAI conventions where compatible, without requiring a new telemetry platform.

For each incident or re-verification decision, record: symptom; outcome; phase; trigger; observed mechanism chain; contributing conditions; violated contract/invariant; evidence pointers; `observed | plausible | contradicted | unknown` confidence; review motive (`required_gate | changed_artifact | new_evidence | prior_uncertainty | discretionary | retry | duplicate`); reviewer/model independence; actual remediation; next recheck event; severity; cost (measured vs estimated tokens, test runtime, elapsed time, lost delivery); recovery/acceptance state; uncertainty and privacy/retention policy.

Distinguish **product defect**, **test flakiness**, **test/invariant tampering**, **provider/quota**, **tool/permission**, **environment/host**, **task specification**, **stale evidence**, **lease/lifecycle**, **agent planning**, **reviewer false positive**, **review repetition**, **scope/authority** and **unattributable**. Support multiple contributing factors. A narrative from an agent is a hypothesis until corroborated. Incident analysis must not imply a single universal root cause.

## Stage 2: bounded observer, no control authority

Implement a thin, disabled-by-default, read-only observer job **within existing Odysseus service/job lifecycle**. Run on meaningful state changes or bounded daily catch-up (not high-frequency polling or duplicate model calls). Read permitted sanitized metadata and existing immutable trace/evolution records, compare new events to evidence revisions, and output a concise candidate diagnosis with source references and a recommended smallest next diagnostic/action.

Detect: repeated reviews on unchanged evidence/HEAD; repeated identical failures without changed strategy; accepted-but-unverified status; stuck review/recovery debt; stale blocked reasons; scope changes during a review; failing/removed/inverted tests; executions interrupted by validation; host/provider failures misleadingly attributed to task code; idle accepted work behind reconnaissance; and regressions after a supposed fix. Use deterministic checks first, then an inexpensive **currently qualified** independent model only when material ambiguity remains. No invented model availability, autonomous merge, scope expansion, task reranking, task acceptance, prompt mutation, or disabling of protected gates. Recommendations land in existing work-item/evaluation pathways and are deduplicated by incident identity + evidence revision.

## Stage 3: evaluation and safe deployment

- Create an independently labelled reference set from historical episodes with raw evidence pointers; blind the observer to the retrospective resolution when possible. Include true negatives, false review accusations, legitimate late severe defects, incomplete logs and adversarial scope/test modifications. Keep training/tuning cases separate from held-out evaluation. Publish confusion matrix and per-category precision/recall with uncertainty; no 'root cause identified' on unsupported narratives.
- Replay existing traces without sending paid providers or mutating repos. Demonstrate idempotent re-ingest, missing/late events, stale revisions, redacted prompts/secrets, owner isolation, restarts and no lost/duplicated recommendations. Estimate false alarms and labour created by each intervention.
- Compare pilot against **no-observer baseline on identical cases**: supported diagnosis accuracy, duplicate review rate, unexplained re-verification, time to first actionable diagnosis, verification cost, accepted-task lead time, avoidable reopening and missed material defects. DORA/SPACE are conceptual guides, not substitutes for these task-level measures. Do not claim causality or cost savings from retrospective replay alone; for an effect claim use a matched/prospective canary.
- Start a small **opt-in shadow canary** on Odysseus only after tests and independent qualified review. Continue existing run and release gates untouched. Expand to Misumi/PhD read-only only after owner isolation, retention/privacy, sampling and scientific provenance tests. Roll back by disabling the observer flag/job without altering task or execution state.
- **Optional next stage, not authorised here:** suggest changes to verification stopping, routing, task planning or prompt evolution backed by repeated, controlled evidence. These must be submitted to their existing owners with original acceptance and authority gates intact.

## Acceptance and stopping

Deliver: (a) source/coverage inventory and actual backlog baseline; (b) reproducible incident table with links and uncertainty; (c) minimal schema/collector with tests or a clear no-change decision if existing spans suffice; (d) one source-linked daily/weekly summary through an existing reporting surface; (e) held-out diagnostic evaluation; (f) disabled-default canary evidence, release/rollback notes, and independent review. **Success is improved diagnosis without additional unsafe actions, false task closure or uncontrollable monitoring cost**, not the volume of observations. If data are insufficient, stop after Stage 0, record exact missing joins/instrumentation and the smallest remediation. Do not build a dashboard before the collector and evidence quality are proven.

## Research foundations to examine and correctly delimit

- Google SRE, *Postmortem Culture*: evidence-linked contributing conditions and corrective actions. https://sre.google/workbook/postmortem-culture/
- Forsgren et al. (2021), *The SPACE of Developer Productivity*: multidimensional measurement, warning against one throughput proxy. https://www.microsoft.com/en-us/research/publication/the-space-of-developer-productivity-theres-more-to-it-than-you-think/
- DORA, *Software Delivery Performance Metrics*: change failure, recovery, rework, lead time; adapt carefully to task-level agent development. https://dora.dev/guides/dora-metrics/
- OpenTelemetry, *Traces* and GenAI semantic conventions: interoperable parent-child event identity. https://opentelemetry.io/docs/concepts/signals/traces/ ; https://opentelemetry.io/docs/specs/semconv/gen-ai/
- Wang et al. (2026), *A Survey for LLM Agent Trajectory Analysis: From Failure Attribution to Enhancement*: limits in step-level attribution. https://doi.org/10.1109/TSE.2026.3717765
- *AgentTelemetry* (2026): agent-specific fault classes/trace evaluation; note that its reported small intervention was not statistically significant. https://doi.org/10.1145/3805760.3814931
- Leveson, *CAST/STPA*: use systemic causal analysis for consequential cross-layer failures, not naive blame or a single 'root cause'. https://www.mit.stamp-institute.com/handbooks

The design must explicitly distinguish observation, plausible explanation, verified mechanism, and experimentally supported improvement.

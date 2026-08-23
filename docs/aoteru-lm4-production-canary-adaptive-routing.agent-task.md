---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-08-23-aoteru-lm4-production-canary-adaptive-routing
title: "Production canary and adaptive local-model routing — LM4"
status: ready
priority: high
task_type: production-canary-routing-adaptation
created_by: chatgpt
created_at: 2026-08-23T02:13:00+01:00
executor: claude-sonnet-5
execution_mode: production-evaluation-implementation
resource_profile: standard
risk_level: medium
approval_required: false
source_traceability_required: true
requires_local_model: true
requires_remote_compute: false
requires_web: false
repo: tyecam1/odysseus
branch: dev
inputs:
  - docs/aoteru-lm2-model-discovery-evidence.md
  - docs/aoteru-lm3-production-runtime-promotion-evidence.md
  - docs/aoteru-model-host-routing-contract.md
  - config/models.yaml
  - config/routing.yaml
outputs:
  - production canary/adaptation telemetry integrated into existing Odysseus authority
  - evidence-backed retain/demote/escalate decisions for live local aliases
  - compact LM4 evidence document
notes: "Do not resume broad model discovery. LM4 validates the live portfolio on real/representative production work and makes only evidence-backed routing changes."
---
# LM4 — production canary + adaptive routing

## Goal

Turn the LM1–LM3 benchmark work into a reliable operating system: exercise the **live production portfolio** on representative Odysseus tasks, capture task-class success/latency/retry/escalation evidence, and harden routing so local models are retained, demoted or escalated from measured production behaviour rather than static assumptions.

Current production bindings are the starting state, not conclusions to defend:
- `local-fast -> qwen3:8b`
- `local-strong -> gpt-oss:20b`
- `code-fast -> ornith:9b`
- `reasoning-strong -> nemotron-3.5-lightning:30b-a3b`
- `vision -> gemma4:12b`
- `code-strong -> null`

LM4 is **not another model-discovery phase**. Do not download new model families or rerun LM2 matrices unless a production regression cannot otherwise be diagnosed.

## Preflight

1. `git pull --ff-only`; confirm clean `dev`, local/origin ancestry, LM3 closed, Ollama/service health, private loopback-only exposure and current bindings.
2. Read the five inputs above plus existing routing/telemetry code before adding anything. Reuse `RoutingDecision`, `BenchmarkResult` and current eval/result conventions; do not create a parallel authority.
3. Confirm incumbent and newly promoted aliases each execute once through the real `run_task`/production path before changing policy.
4. Preserve single-GPU serialization and robotics workload priority. No concurrent benchmark/canary GPU work.

## Scope

Build the smallest durable production-canary layer that can answer, by alias/task class:
- did the routed model complete the task adequately?
- latency and resource cost;
- deterministic/task-specific verification result where available;
- retry count/failure class;
- whether escalation was needed;
- whether a human/high-capability correction later invalidated the result;
- concrete model/runtime/context used;
- source/evidence pointer without copying sensitive raw prompts unnecessarily.

Prefer existing real production/routing traffic where sufficient. Where coverage is missing, use a **small representative canary pack** derived from the frozen LM1/LM2 corpus and current Odysseus/PhD/S2-E1 sources. Do not manufacture a large synthetic benchmark.

At minimum cover:
- routine repo reconnaissance;
- bounded code repair + deterministic tests;
- fault/log diagnosis;
- strict schema/tool-call output;
- scientific/PhD reasoning;
- ROS/test interpretation;
- compact summarisation;
- vision/image reading;
- one longer-context task where it materially affects routing.

## Adaptation policy

Use deterministic gates first. Do not invent universal numeric quality floors from sparse data.

For each live alias, classify after the canary window as:
- **retain** — adequate and no meaningful regression;
- **retain-with-caveat** — useful but a narrow failure mode needs explicit routing/escalation handling;
- **demote/unbind** — repeated production-path failure or materially worse behaviour than the next adequate route;
- **insufficient evidence** — keep current binding and collect more evidence; do not fabricate certainty.

Changes to routing must be minimal and explainable. Prefer task-class-specific escalation/fallback over replacing a generally good model because of one narrow weakness.

The economic principle remains:
**an adequate local result beats a paid result; an inadequate local result does not.**

Do not fill `code-strong` merely because it is null. Only create/bind that role if real LM4 evidence demonstrates a routing gap that cannot be handled adequately by `code-fast`, `local-strong`, or escalation.

## Vision caution

`vision -> gemma4:12b` was production-qualified in LM3 on a fresh equivalence image task, while LM2's broader vision evidence used a distinct official QAT GGUF artifact. Give the production Ollama artifact modestly broader canary coverage before treating it as equally well established. Do not retroactively merge the two artifacts' evidence.

## Work sequence

1. Verify production baseline and current aliases.
2. Inspect/reuse existing routing telemetry and benchmark/result structures.
3. Add only the minimal fields/aggregation needed for canary evidence and later adaptation; avoid schema proliferation.
4. Freeze a compact production-canary pack with provenance and deterministic/factual-atom gates before running models.
5. Exercise the five live generative aliases only where the task class is relevant; do not force every alias through every task.
6. Repeat only failures, borderline outcomes and load-bearing decisions enough to distinguish noise from a real regression.
7. Compare production behaviour against LM2/LM3 evidence and current fallback routes.
8. Apply only justified retain/demote/escalation/routing-policy changes.
9. Run focused tests plus at most one full relevant suite; re-verify all bound aliases, service health, loopback-only exposure and routing telemetry consistency.
10. Commit/push cohesive work to `dev`; confirm local/origin HEAD match.

## Stop / handoff

Stop when the live portfolio has an evidence-backed disposition per alias and the canary/adaptation mechanism is durable.

If a model shows a serious regression, preserve service continuity first: fall back/unbind the affected alias, record evidence, and do not broaden into new-model discovery in this task.

If LM4 reveals a justified need for renewed discovery (for example a real `code-strong` gap), create at most one concise follow-up agent-task pointing to LM4 evidence. Do not start it here.

## Final output

Report only:
- canary/telemetry mechanism added or reused;
- real/representative task coverage;
- per-alias disposition (`retain`, `retain-with-caveat`, `demote/unbind`, `insufficient evidence`);
- routing/escalation changes made;
- key success/latency/failure evidence;
- tests/live regression/private-exposure evidence;
- any justified follow-up task;
- final HEAD SHA.

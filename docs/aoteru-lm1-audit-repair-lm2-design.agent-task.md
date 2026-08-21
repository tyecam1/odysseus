---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-08-21-aoteru-lm1-audit-repair-lm2-design
title: "Repair LM1 validity gaps and design quantisation-aware LM2"
status: ready
priority: high
task_type: benchmark-audit-model-discovery-design
created_by: chatgpt
created_at: 2026-08-21T19:15:00+01:00
executor: claude-sonnet-5
execution_mode: audit-repair-design
resource_profile: standard
risk_level: medium
approval_required: false
source_traceability_required: true
requires_local_model: true
requires_remote_compute: false
requires_web: true
repo: tyecam1/odysseus
branch: dev
inputs:
  - docs/aoteru-local-model-benchmark-routing.agent-task.md
  - docs/aoteru-local-model-benchmark-routing-evidence.md
  - docs/aoteru-lab-local-model-strategy-2026-08-20.md
  - docs/aoteru-model-host-routing-contract.md
outputs:
  - repaired LM1 benchmark/execution validity
  - corrected LM1 evidence wording
  - genuine PhD/ROS estate fixtures with frozen provenance
  - durable benchmark-output artefact/pointer mechanism
  - machine-readable production-vs-benchmark model state
  - quantisation-aware LM2 candidate/discovery contract only
notes: "Sequence is mandatory: repair LM1 first, then design LM2. Do not execute LM2 or download second-round candidates in this task."
---
# LM1 audit-repair + LM2 design

## Goal

Close the remaining validity/reproducibility gaps in LM1, then define the next model-evaluation phase around **model family × quantisation × runtime × context/offload configuration**, not a fixed three-model shortlist.

Do not start LM2 benchmarking in this session. The benchmark system must be trustworthy before widening the candidate search space.

## Preflight

1. `git pull --ff-only`; confirm clean `dev`, local/origin ancestry and service health.
2. Read this task plus the four inputs above and inspect current LM1 implementation/evidence at live HEAD.
3. Reproduce each audit finding before changing code; if a finding is wrong, document why and do not make unnecessary changes.
4. Use the existing Odysseus parking/write authority before mutation.
5. Preserve persistent LAB-FIRST EXECUTION CUTOVER and private exposure invariants.

# Part A — LM1 audit-repair

## A1. Production context sizing

LM1 added optional `num_ctx` support to `src.llm_core.llm_call`, and the benchmark supplies it explicitly. Verify whether production `src.estate_router.execute_local()` still calls `llm_call` without `num_ctx`; if so, the evidence currently overstates the production fix.

Implement the smallest defensible production correction so normal local execution chooses an adequate bounded context from actual task/prompt requirements rather than blindly requesting a model's full advertised context.

Requirements:
- do not hard-code 8K universally;
- preserve future long-context routing;
- preserve compatibility for other callers that genuinely rely on existing behaviour;
- prefer one canonical context-selection helper/policy rather than duplicating heuristics;
- add focused tests proving the production `run_task -> execute_local -> llm_call` path uses the corrected context decision;
- correct LM1 evidence wording if historical claims were too strong.

## A2. Benchmark-output reproducibility

Verify that `scripts/run_local_model_benchmark.py` removes `raw_output` from JSONL and does not populate `BenchmarkResult.raw_output_pointer`.

If confirmed, preserve each future benchmark model output as an immutable per-run artefact under the existing Odysseus eval authority, recording at minimum:
- run/task/model identity;
- exact output;
- SHA-256;
- corpus/source/model/runtime provenance sufficient for later independent rescoring.

Keep SQLite/telemetry compact: persist pointer + hash, not large transcripts. Never store secrets. Historical LM1 runs whose outputs no longer exist must be labelled output-unavailable; do not rerun the whole matrix just to backfill them.

Add focused tests for artefact creation, hashing and DB pointer integrity.

## A3. Estate corpus fidelity

The original `phd_scientific_reasoning` and `ros_log_test_interpretation` fixtures are labelled proxies but do not adequately represent their named task classes.

GitHub authentication is available. Resolve/read, read-only:
- `tyecam1/obsidian-PhD`
- `tyecam1/s2-e1-ros2-measurement-spine`

Do not mutate either repo.

Replace/add the smallest frozen real-source fixtures needed so:
- PhD/scientific reasoning genuinely exercises the user's robotics/laboratory-HRC research reasoning, evidence/claim ceilings, scientific synthesis or experimental reasoning;
- ROS/log/test interpretation genuinely exercises S2-E1 ROS2 source/log/test material.

Rules:
- exact `repo@commit:path` provenance;
- deterministic scoring where possible;
- for qualitative reasoning, define factual atoms/rubric **before** candidate output;
- do not retrospectively reinterpret old LM1 proxy results as evidence for these stronger task classes;
- a small validation run against current incumbents is allowed; broad candidate reruns belong to LM2.

## A4. Inventory semantics

Review `config/models.yaml` machine-readable semantics. Gemma 4 models were benchmarked through a temporary second Ollama instance but are not production-runnable on current production Ollama.

Ensure code/config cannot infer "production installed" from a state that really means "benchmark artefact observed". Prefer a small explicit state distinction such as production-installed / benchmark-only / candidate / unavailable, reusing existing registry structures if possible. Do not add a parallel registry merely for this distinction.

## A5. Verification and LM1 closure

After A1–A4:
- run focused tests;
- run one relevant integration/regression suite;
- verify production `run_task(local-fast)` succeeds;
- verify systemd/service health and private listeners unchanged;
- update LM1 evidence to distinguish historical vs newly repaired behaviour precisely;
- do not rerun the full LM1 benchmark unless a repair invalidates a decision materially.

LM1 can be called closed only after these gates pass.

# Part B — quantisation-aware LM2 design

Begin Part B only after LM1 repair gates pass.

## B1. Principle

LM2 must evaluate configurations, not just model names:

`model family × exact weights/revision × quantisation × runtime × context/offload configuration`

A larger model at a strong quant may be preferable to a smaller model; "does not fully fit in 10GB VRAM" is not by itself a rejection because this lab has 128GB system RAM and hybrid offload is valid when latency remains useful.

LM2 should be a **two-stage funnel**:
1. cheap family-level screening using one sensible representative quant/config per family;
2. quant/runtime sweep only for finalists that can plausibly displace an incumbent or fill a missing capability.

Do not download or benchmark LM2 candidates in this task; produce the durable agent-task/candidate registry/design for the next fresh session.

## B2. Current candidate diversity to include/research

Use current official model cards/release notes/runtime documentation and the saved 2026-08-20 research as starting points, but refresh only facts needed to design LM2 because model/quant availability changes quickly.

Build a deliberately diverse shortlist of about **6–8 families/configuration classes**, not dozens. Include, unless current official evidence makes one unsuitable:

- incumbent controls: `qwen3:8b`, `gpt-oss:20b`;
- small/fast: Gemma 4 E2B/E4B, including official QAT GGUF where available;
- general/agentic 8–10B: Qwen3.5-9B and at least one genuinely different family such as LFM2.5-8B-A1B or an equivalent current contender;
- coding/agentic: a current compact agentic/coding family such as Ornith-1.0-9B or a stronger current alternative if official evidence supports replacement;
- compact multimodal: Gemma 4 12B official QAT path;
- strong MoE: Qwen3.6-35B-A3B and NVIDIA Nemotron 3.5 Lightning 30B-A3B (or exact current official names/revisions);
- hybrid MoE/QAT candidate: Gemma 4 26B-A4B official QAT if current availability/runtime support checks out;
- dense deep baseline/challenger: Qwen3.8-27B or the current official equivalent.

If any named family has changed, been superseded, lacks a usable official artefact/licence/runtime, or was misnamed in prior research, correct it with source evidence rather than preserving stale naming.

## B3. Quantisation strategy

For each shortlisted family, identify one low-cost screening representation and the plausible finalist sweep. Prefer model-native quantisation-aware releases when available.

The candidate design should consider, where supported:
- official/model-native QAT quant (especially Gemma 4);
- Q4_K_M / Q4_0 baseline;
- IQ4_XS or IQ4_NL;
- Q5_K_M if a modest memory increase may buy meaningful quality;
- Q6_K only where latency/memory still makes sense;
- IQ3/Q3 only where crossing a residency/offload threshold materially changes usefulness;
- provider-specific formats such as NVFP4/W4A16 only if the RTX 3080 Ampere runtime actually supports them usefully.

Do not assume newer/smaller-bit is better. Capture expected trade-offs: size, VRAM residency, CPU offload, context KV cost, runtime support, quality risk and expected throughput.

For Gemma 4 specifically, LM2 should compare **official QAT GGUF versus ordinary post-training quantisation** for finalists where feasible; LM1's Ollama-library mapping was explicitly unproven and does not answer this question.

## B4. Runtime dimension

Do not make Ollama the only benchmark runtime if that prevents meaningful quantisation comparison.

Design LM2 so Odysseus remains the benchmark/result/routing authority while execution backends may include:
- production Ollama for production-equivalent screening;
- CUDA `llama.cpp` / `llama-bench` for exact GGUF quant/offload/context sweeps;
- another runtime only if it adds a capability unavailable in those two and does not create a parallel routing authority.

Low-level runtime measurements are supplemental; finalists must still be tested through the Odysseus execution abstraction before promotion.

## B5. Screening and promotion funnel

Design a cheap first pass that rejects obvious losers without exhaustive repeats. Suggested logic:

1. licence/runtime/hardware/disk prefilter;
2. exact artefact provenance + integrity;
3. one representative quant/config per family;
4. frozen estate corpus screening;
5. reject configurations that cannot meet task quality/latency/usefulness thresholds relative to incumbent;
6. only finalists receive quant/runtime/context/offload sweeps;
7. repeat load-bearing tasks enough to establish stability;
8. promotion only when evidence shows a material capability, success-rate, latency, locality or paid-escalation advantage with no important regression.

Compare by role/task class, never one global score.

The design must record:
- family/model/revision;
- exact artefact + quant;
- runtime;
- total/active parameters for MoE where known;
- disk size;
- target context points;
- GPU residency/offload configuration;
- expected and measured RAM/VRAM;
- TTFT/decode/wall time;
- task score/stability;
- reason for promotion/rejection.

## B6. Continuous discovery compatibility

LM2 should leave a minimal candidate-registry/discovery path suitable for future model releases:

`official release -> metadata/hardware-fit screen -> candidate registry -> one useful quant -> estate screening -> finalist sweep -> canary -> promote/reject -> retain evidence`

Do not turn this into an autonomous internet crawler or recurring job yet. The goal is a clean data/schema/workflow surface that future discovery can use.

## B7. Deliverable

After LM1 closure, create **one** concise `agent-task/v1` for LM2 that contains:
- candidate registry / shortlist;
- exact source/provenance requirements;
- family-level screening order;
- quant/runtime finalist sweep logic;
- resource/GPU serialization rules;
- evidence and promotion gates;
- stop/handoff conditions.

Do not execute LM2 in this session.

# Agent/resource policy

Sonnet 5 medium is foreman.

Prefer:
`deterministic inspection/tests -> local evidence -> minimal code repair -> deterministic verification -> current official source checks for LM2 design -> concise synthesis`

Rules:
- no same-model nested Sonnet by default;
- no paid model adjudication for routine repairs;
- one independent high-capability review only if a material benchmark/routing architecture change cannot be resolved deterministically;
- no concurrent GPU jobs;
- no second-round model downloads;
- do not use an LLM to verify deterministic facts;
- keep LM2 design compact and evidence-driven.

# Stop / handoff

Stop only when:
- LM1 repair is verified and durable and the LM2 agent-task/design is committed/pushed;
- a genuine human-only credential/licence/hardware decision blocks progress;
- or resource limits require a salvage checkpoint.

Commit cohesive repairs + LM2 design to `dev`, push once verified, and confirm local/origin HEAD match.

Final report only:
- LM1 findings confirmed/rejected;
- repairs made;
- tests/live evidence;
- whether LM1 is now closed;
- LM2 shortlist/design summary;
- any human blocker;
- final HEAD SHA.

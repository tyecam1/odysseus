---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-08-21-aoteru-local-model-benchmark-routing
title: "Establish the first empirical local-model portfolio and routing evidence"
status: ready
priority: high
task_type: model-evaluation-routing
created_by: chatgpt
created_at: 2026-08-21T16:13:00+01:00
executor: claude-sonnet-5
execution_mode: evaluation-implementation
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
  - docs/aoteru-lab-local-model-strategy-2026-08-20.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/aoteru-lab-execution-convergence-evidence.md
  - docs/aoteru-systemd-cutover-evidence.md
outputs:
  - reproducible local-model benchmark harness/corpus in the existing Odysseus eval/benchmark authority
  - machine-readable benchmark results with source/model/runtime provenance
  - compact benchmark/promotion evidence document
  - evidence-backed routing/model config changes only where promotion gates pass
notes: "This file is a work designation/contract, not a second task queue, benchmark authority or model router. Extend existing Odysseus benchmark/eval/model-registry surfaces if they exist."
---
# Local-model benchmark + routing — LM1

## Goal

Produce the **first reproducible, estate-specific empirical local-model portfolio** for the lab worker, replacing provisional model assumptions with measured evidence while preserving the persistent LAB-FIRST EXECUTION CUTOVER.

**Odysseus itself is the benchmark authority.** LM1 must exercise and extend the existing Odysseus model inventory/evaluation/execution/routing surfaces rather than build a parallel one-off benchmark system. Hugging Face is an authenticated source of model artefacts and metadata, not a second model registry or routing authority.

Done means: a reusable benchmark corpus/harness exists under the canonical Odysseus authority; installed baselines and the three first-round candidates have been screened on real estate tasks through the production-equivalent local execution path where technically possible; finalists have repeated evidence; routing/model bindings are changed only where promotion criteria are met; raw results and decisions are durable and reproducible.

This is LM1, not the whole continuous-discovery programme. Do not expand into second-round/experimental model exploration unless needed to repair the benchmark system itself.

## Live-state preflight

1. `git pull --ff-only`; confirm clean `dev`, local/remote ancestry and current service health.
2. Read this file plus the four inputs above. Do **not** redo the 2026-08-20 model research.
3. Inspect existing Odysseus eval/benchmark/model-inventory/result/telemetry surfaces before adding files. Reuse/extend them; do not create parallel authorities.
4. Use existing parking/write authority before mutation.
5. Record live lab runtime/hardware/disk/Ollama state and installed model inventory. Preserve robotics GPU availability; no parallel GPU benchmark workloads.
6. Detect Hugging Face tooling/auth non-destructively (`hf auth whoami` or equivalent). Use an existing host-local credential if present; never print, copy or persist the token into repo files/logs/evidence/telemetry/prompts.
7. If `obsidian-PhD` or S2-E1 sources are not local, fetch only the minimum read-only fixtures needed from exact GitHub commits/paths (or a temporary read-only clone). Never mutate those repos during LM1.

## Execution authority + Hugging Face acquisition

LM1 must use this ownership chain:

`Odysseus benchmark corpus/harness -> Odysseus model inventory/execution path -> local runtime -> deterministic scorer -> Odysseus result/telemetry -> routing promotion decision`

External mechanisms such as `hf`, Ollama and `llama.cpp` may fetch/serve/measure models, but must not become parallel benchmark registries, result authorities or routing policies.

For Hugging Face:

- use the operator's existing **host-local Hugging Face token** if configured for the `agent` user; authenticate via the current `hf` CLI / Hugging Face Hub mechanism, not deprecated `huggingface-cli`;
- prefer non-secret checks such as `hf auth whoami`; never echo/read the token into benchmark output;
- if an environment credential such as `HF_TOKEN` already exists, consume it without exposing it; otherwise use the standard user-local Hugging Face credential store;
- if authentication is absent and a required candidate cannot be acquired anonymously, stop only at the exact secure one-time login action needed from the operator; **never ask for the token in chat or put it on a shell command line**;
- a token grants access, not licence acceptance. If a model is gated behind terms the operator has not already accepted, treat that as a genuine human/legal gate; do not bypass it;
- pin acquisition provenance: official upstream repo ID, exact revision/commit where available, artifact/filename, quantisation, runtime/import conversion and licence/model-card reference. Record only that authenticated access was available, never the credential itself;
- use `hf download ... --revision ...` / the equivalent Hub API for exact artefacts when Hugging Face is the source; use `hf cache verify` or equivalent integrity checks where useful;
- an Ollama artefact may remain the production runtime representation when appropriate, but provenance must still connect it to an identifiable upstream model/revision or explicitly state when that mapping cannot be proven.

Do not place a long-lived HF token in committed config. Do not broaden service permissions merely to make downloads convenient.

## Scope

Benchmark real tasks derived from the strategy's required classes:

1. repo reconnaissance;
2. bounded code repair with deterministic tests;
3. fault diagnosis;
4. tool/function-call correctness;
5. strict JSON/schema output;
6. evidence extraction + provenance;
7. scientific/PhD reasoning;
8. long-context retrieval;
9. document/image understanding where supported;
10. compact summarisation/compression;
11. independent review of another worker result;
12. ROS/log/test interpretation.

Each task must carry a frozen source pointer (`repo@commit:path` or equivalent), expected/gated outcome and task class. Prefer deterministic scoring; for qualitative tasks define factual atoms/rubrics before seeing candidate outputs.

Out of scope for LM1:
- home/interface/mobile work;
- Claude/Codex execution plumbing;
- robotics ML training/inference;
- second-round models (`Qwen3.6-35B-A3B`, Nemotron 3.5 Lightning, `Qwen3.8-27B`);
- experimental 80B/119B/frontier checkpoints;
- broad new web/deep research;
- redesign of Odysseus routing, memory or service architecture.

## Candidates

Baseline first, using already-installed generative models where runnable (at minimum `qwen3:8b`, `gpt-oss:20b`; include `qwen3:30b` if valid for the same harness).

Then evaluate **only the first-round candidates nominated by the saved research**:
- Gemma 4 E4B — `local-small` candidate;
- Qwen3.5-9B — `local-agent` / `local-code` candidate;
- Gemma 4 12B — `local-multimodal` candidate.

Resolve a compatible supported artifact/quant/runtime from the saved primary source anchors and available runtimes. Prefer the official publisher's Hugging Face repository/revision when it provides the required artefact or authoritative source metadata. One new model download at a time. Do not download a candidate that fails licence/runtime/hardware/disk preflight; record the blocker and continue.

## Benchmark design

Build the smallest reusable **Odysseus-native** harness that captures, per model/task/run:
- model + upstream repo/revision + artifact + quant;
- runtime/version;
- context setting;
- GPU/CPU placement or offload;
- peak VRAM/RAM where measurable;
- TTFT, prompt/decode throughput and wall time where available;
- deterministic/task score;
- schema/tool validity;
- retries/failures;
- source pointers;
- final pass/fail and reason.

Where Odysseus already has equivalent model-evaluation/result structures, extend those instead of creating a new schema. The same candidate should be invokable through the same local execution abstraction used by production routing wherever technically possible; a lower-level `llama-bench`/runtime measurement is supplemental evidence, not the end-to-end benchmark itself.

Use 8K and 32K screening points where meaningful. Use 64K only for finalists/tasks that genuinely need it. Do not spend LM1 on 128K unless a candidate's value depends on it.

Run one screening pass across eligible tasks for each model, then repeat **only finalists** enough to establish non-anecdotal evidence (normally 3 total trials on load-bearing task classes). Do not multiply repeats where deterministic results are already stable and the comparison cannot change.

Multimodal tasks are N/A, not failures, for text-only candidates.

## Routing + promotion

The routing contract remains authoritative. Public/vendor scores nominate nothing here; LM1 evidence decides.

Promote/change a binding only when repeated estate evidence shows a material advantage in success, latency, paid-escalation avoidance, or a missing useful capability, with no deterministic/safety/domain regression.

Do not invent universal numeric quality floors. Derive task-specific gates from the frozen corpus where defensible; otherwise retain `null`/unqualified state and report insufficient evidence.

The saved strategy and live routing config currently use partially different alias vocabularies. **Do not create two permanent alias systems.** Inspect the mismatch and either:
- make a minimal backward-compatible canonical consolidation if LM1 evidence requires it, with one focused material review; or
- leave live aliases unchanged and record the evidence-backed migration recommendation for LM2.

No rename/refactor merely for cosmetic consistency.

## Agent/resource routing

Sonnet 5 medium is the foreman, not the benchmark worker.

Prefer:
`deterministic Odysseus harness -> local candidate -> deterministic scoring -> Sonnet synthesis`

Rules:
- no same-model nested Sonnet by default;
- no Opus/Sol/paid adjudication for routine benchmark outputs;
- at most one independent high-capability review for a **material routing/alias architecture change** or an unresolved qualitative tie that affects promotion;
- no concurrent GPU model runs/downloads;
- focused tests during harness changes; at most one full relevant repository suite after the coherent implementation batch;
- do not use an LLM to verify a fact a deterministic gate establishes;
- optional improvements discovered outside LM1 become a concise follow-up, not mandatory scope.

## Work sequence

1. Preserve/inspect live state and existing Odysseus benchmark/model infrastructure.
2. Verify HF authentication/access without exposing credentials; resolve exact upstream revisions/artifacts before download.
3. Freeze a compact, provenance-linked estate corpus and deterministic gates under the existing benchmark/eval authority.
4. Implement/reuse the Odysseus benchmark runner and machine-readable result format; validate that it exercises production-equivalent local execution.
5. Benchmark installed baselines first; validate the harness against known behaviour.
6. Pre-filter, acquire and screen the three first-round candidates sequentially.
7. Repeat only plausible finalists/load-bearing task classes.
8. Compare by task class, not one global winner.
9. Apply only evidence-backed model/routing changes; otherwise retain incumbents.
10. Run focused regression tests + one final relevant integration suite; verify live routing still executes successfully and service/private-exposure invariants remain intact.
11. Commit cohesive work to `dev`, push, and confirm origin/local HEAD match.

## Stop / handoff

Stop only when:
- LM1 goal is verified and durable;
- a genuine human-only credential/licence/hardware/storage decision blocks further progress; or
- resource limits require a checkpoint.

If Hugging Face authentication is the blocker, report only the exact safe login action and what candidate it blocks; never request or display the token.

If interrupted, preserve a salvage manifest: exact HEAD, installed/downloaded artifacts, completed model/task matrix, raw result paths, running processes, remaining candidates and next command. Resume from evidence; do not rerun completed benchmarks without a material reason.

If LM1 reveals a justified second-round need, create **at most one** concise follow-up agent-task pointing to this evidence. Do not start LM2 in this session.

## Final output

Report only:
- Odysseus corpus/harness status;
- models actually evaluated and exact upstream revisions/artifacts/quants;
- per-alias/task-class winners or "no promotion";
- key quality/latency/resource evidence;
- config/routing changes made;
- tests/live regression evidence;
- blockers/deferred LM2 work;
- final HEAD SHA.

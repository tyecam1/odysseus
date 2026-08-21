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
  - reproducible local-model benchmark harness/corpus in the existing eval/benchmark authority
  - machine-readable benchmark results with source/model/runtime provenance
  - compact benchmark/promotion evidence document
  - evidence-backed routing/model config changes only where promotion gates pass
notes: "This file is a work designation/contract, not a second task queue or routing authority. Extend existing benchmark/eval surfaces if they exist."
---
# Local-model benchmark + routing — LM1

## Goal

Produce the **first reproducible, estate-specific empirical local-model portfolio** for the lab worker, replacing provisional model assumptions with measured evidence while preserving the persistent LAB-FIRST EXECUTION CUTOVER.

Done means: a reusable benchmark corpus/harness exists; installed baselines and the three first-round candidates have been screened on real estate tasks; finalists have repeated evidence; routing/model bindings are changed only where promotion criteria are met; raw results and decisions are durable and reproducible.

This is LM1, not the whole continuous-discovery programme. Do not expand into second-round/experimental model exploration unless needed to repair the benchmark system itself.

## Live-state preflight

1. `git pull --ff-only`; confirm clean `dev`, local/remote ancestry and current service health.
2. Read this file plus the four inputs above. Do **not** redo the 2026-08-20 model research.
3. Inspect existing eval/benchmark/model-inventory surfaces before adding files. Reuse/extend; do not create parallel authorities.
4. Use existing parking/write authority before mutation.
5. Record live lab runtime/hardware/disk/Ollama state and installed model inventory. Preserve robotics GPU availability; no parallel GPU benchmark workloads.
6. If `obsidian-PhD` or S2-E1 sources are not local, fetch only the minimum read-only fixtures needed from exact GitHub commits/paths (or a temporary read-only clone). Never mutate those repos during LM1.

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

Resolve a compatible supported artifact/quant/runtime from the saved primary source anchors and available runtimes. One new model download at a time. Do not download a candidate that fails licence/runtime/hardware/disk preflight; record the blocker and continue.

## Benchmark design

Build the smallest reusable harness that captures, per model/task/run:
- model + artifact + quant;
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
`deterministic harness -> local candidate -> deterministic scoring -> Sonnet synthesis`

Rules:
- no same-model nested Sonnet by default;
- no Opus/Sol/paid adjudication for routine benchmark outputs;
- at most one independent high-capability review for a **material routing/alias architecture change** or an unresolved qualitative tie that affects promotion;
- no concurrent GPU model runs/downloads;
- focused tests during harness changes; at most one full relevant repository suite after the coherent implementation batch;
- do not use an LLM to verify a fact a deterministic gate establishes;
- optional improvements discovered outside LM1 become a concise follow-up, not mandatory scope.

## Work sequence

1. Preserve/inspect live state and existing benchmark infrastructure.
2. Freeze a compact, provenance-linked estate corpus and deterministic gates.
3. Implement/reuse the benchmark runner and machine-readable result format.
4. Benchmark installed baselines first; validate the harness against known behaviour.
5. Pre-filter, download and screen the three first-round candidates sequentially.
6. Repeat only plausible finalists/load-bearing task classes.
7. Compare by task class, not one global winner.
8. Apply only evidence-backed model/routing changes; otherwise retain incumbents.
9. Run focused regression tests + one final relevant integration suite; verify live routing still executes successfully and service/private-exposure invariants remain intact.
10. Commit cohesive work to `dev`, push, and confirm origin/local HEAD match.

## Stop / handoff

Stop only when:
- LM1 goal is verified and durable;
- a genuine human-only credential/licence/hardware/storage decision blocks further progress; or
- resource limits require a checkpoint.

If interrupted, preserve a salvage manifest: exact HEAD, installed/downloaded artifacts, completed model/task matrix, raw result paths, running processes, remaining candidates and next command. Resume from evidence; do not rerun completed benchmarks without a material reason.

If LM1 reveals a justified second-round need, create **at most one** concise follow-up agent-task pointing to this evidence. Do not start LM2 in this session.

## Final output

Report only:
- corpus/harness status;
- models actually evaluated and exact artifacts/quants;
- per-alias/task-class winners or "no promotion";
- key quality/latency/resource evidence;
- config/routing changes made;
- tests/live regression evidence;
- blockers/deferred LM2 work;
- final HEAD SHA.

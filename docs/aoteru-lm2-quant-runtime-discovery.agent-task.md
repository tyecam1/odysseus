---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-08-21-aoteru-lm2-quant-runtime-discovery
title: "Quantisation-aware family screening and finalist sweep — LM2"
status: ready
priority: high
task_type: model-evaluation-quantisation-discovery
created_by: claude-sonnet-5
created_at: 2026-08-21T19:40:00+01:00
executor: claude-sonnet-5
execution_mode: evaluation-implementation
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
  - docs/aoteru-lm1-audit-repair-lm2-design.agent-task.md
  - docs/aoteru-local-model-benchmark-routing-evidence.md
  - docs/aoteru-lab-local-model-strategy-2026-08-20.md
  - docs/aoteru-model-host-routing-contract.md
  - evals/local_models/corpus.json
  - evals/local_models/model_manifest.json
outputs:
  - populated candidate registry (evals/local_models/candidates.json) with one row per family/artifact/quant/runtime/context/offload configuration actually screened or swept
  - family-level screening results through the Odysseus execution path (production Ollama or CUDA llama.cpp, per B4)
  - finalist quant/runtime/context/offload sweep results for configurations that clear screening
  - evidence-backed promotion/rejection decisions per capability alias, recorded in config/models.yaml, with config/models.yaml's installed_candidates state field (production-installed | benchmark-only | candidate | unavailable) kept accurate for every row this task touches
  - a compact LM2 evidence document (docs/aoteru-lm2-model-discovery-evidence.md), same convention as the LM1 evidence doc
notes: >-
  Do not begin this task until docs/aoteru-lm1-audit-repair-lm2-design.agent-task.md's
  LM1 repair gates have passed and LM1 is recorded closed (it was, as of this
  task's creation — see that file's evidence doc closure note). One new model
  download at a time. No concurrent GPU jobs on the lab's single RTX 3080.
  Refresh only the facts below that have actually changed by the time this
  task executes — model/quant availability moves quickly.
---
# LM2 — quantisation-aware family screening and finalist sweep

## Goal

LM1 asked "which named model wins." LM2 asks a different, better-posed
question: across **model family × exact weights/revision × quantisation ×
runtime × context/offload configuration**, which *configuration* is the
strongest adequate option per capability alias — evaluated on this lab's
real 10GB-VRAM/128GB-RAM topology, not on a vendor leaderboard.

A larger model at a strong quant may beat a smaller model outright.
"Does not fully fit in 10GB VRAM" is not by itself a rejection: hybrid
CPU/GPU offload is a legitimate configuration here, not a failure mode,
as long as measured latency stays useful for the target alias.

This is a **two-stage funnel**, not an exhaustive matrix:

1. cheap family-level screening using one sensible representative
   quant/config per family, through the same Odysseus execution path
   production routing uses;
2. a quant/runtime/context/offload sweep only for finalists that can
   plausibly displace an incumbent or fill a missing capability
   (currently: `code-fast`, `local-strong`, `reasoning-strong`, and the
   pending Gemma 4 `vision` promotion once its Ollama-version blocker
   clears).

Do not turn this into an autonomous internet crawler. Nominate, screen,
sweep, promote/reject, retain evidence — same as every prior phase.

## Preflight

1. `git pull --ff-only`; confirm clean `dev` and that
   `docs/aoteru-local-model-benchmark-routing-evidence.md` records LM1
   closed.
2. Read this file plus the five inputs above. Do not redo LM1's harness
   design work — `evals/local_models/corpus.json`,
   `scripts/run_local_model_benchmark.py`, `core.database.BenchmarkResult`
   and the artefact mechanism (`evals/local_models/results/artifacts/`)
   already exist; extend them, don't replace them.
3. Record live lab hardware/Ollama/llama.cpp state and current installed
   inventory (`config/models.yaml`) before any download.
4. Re-verify HF authentication non-destructively (`hf auth whoami`), same
   rules as LM1: never print/persist a token, treat gated licences as a
   genuine human gate.
5. Re-confirm the exact facts in the registry below before download —
   licences, official repo IDs, and quant-artefact availability move
   quickly; if a fact has changed, correct it with source evidence and
   record the correction, don't silently substitute.
6. Preserve LAB-FIRST EXECUTION CUTOVER, private-exposure invariants, and
   "no concurrent GPU jobs" throughout.

## Candidate registry (refreshed 2026-08-21; verify again at execution time)

Eight families/configuration classes plus the two incumbent controls
already installed. Each row is a starting point for step 1 of the funnel
below, not a pre-cleared download.

| # | Family | Role / alias target | Official repo (HF unless noted) | Licence (verify at runtime) | Architecture | Correction vs 2026-08-20 research |
|---|---|---|---|---|---|---|
| — | `qwen3:8b` (installed) | incumbent control, `local-fast` | n/a — already installed/screened (LM1) | apache-2.0 | 8.2B dense | none |
| — | `gpt-oss:20b` (installed) | incumbent control, `local-strong` | n/a — already installed/screened (LM1) | apache-2.0 | ~20B dense | none |
| 1 | Gemma 4 E2B/E4B | `local-small`/`local-fast` challenger | `google/gemma-4-E4B-it-qat-q4_0-gguf` (+ E2B QAT sibling if published) | Gemma licence | dense, official QAT | LM1 only ran the *Ollama-library* `gemma4:e4b`, with an explicitly unproven mapping to this HF artefact — LM2 must run the **official QAT GGUF directly** (via CUDA llama.cpp, see B3/B4) to finally answer that question, not repeat the unproven path |
| 2 | Qwen3.5-9B (already installed) | `local-agent`/`code-fast` incumbent-of-record | `Qwen/Qwen3.5-9B` | apache-2.0 | 9.7B dense | none — carry forward LM1's 3-trial evidence, do not re-download/re-screen unless a quant/runtime variant is genuinely new |
| 3 | LFM2.5-8B-A1B | second, architecturally distinct `local-agent` contender | `LiquidAI/LFM2.5-8B-A1B` (+ official GGUF) | Liquid's LFM licence — **verify commercial-use terms before download**, not assumed apache | hybrid MoE: 8.3B total / **1.5B** active (research doc said ~1B — correct this), 18 conv ("LIV") blocks + 6 GQA layers | active-param count corrected from prior research |
| 4 | Ornith-1.0-9B | compact agentic/coding challenger | `deepreinforce-ai/Ornith-1.0-9B` (mirrors: `ornith-ai/...`, `unsloth/...`) | MIT | 9B dense, built on Gemma-4/Qwen-3.5 lineage; self-scaffolding RL training for agentic coding | confirmed real and current — publisher benchmark claims (SWE-Bench/Terminal-Bench/NL2Repo) are marketing, not admissible LM2 evidence; re-measure on the frozen estate corpus only |
| 5 | Gemma 4 12B | `local-multimodal`/`vision` (pending Ollama blocker) | `google/gemma-4-12B-it-qat-q4_0-gguf` | Gemma licence | 11.9B dense, official QAT, vision-capable | same official-QAT-vs-Ollama-library question as row 1; LM1 evidence via Ollama library already exists (3 trials, 11/13 text tasks) — LM2 adds the QAT-GGUF-direct comparison, does not redo the Ollama-side trials |
| 6a | Qwen3.6-35B-A3B | `local-strong` challenger | `Qwen/Qwen3.6-35B-A3B` | apache-2.0 (verify) | MoE: 35B total / 3B active, 262K native context (to 1M via extension) | confirmed current, unchanged from research doc |
| 6b | NVIDIA Nemotron 3.5 Lightning 30B-A3B | `local-challenger` | `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16` (screening quant: NVFP4 or GGUF, see B3) | NVIDIA open model licence (verify commercial terms) | hybrid Mamba-2 + MoE + Attention: 30B total / 3B active | confirmed current; the `-NVFP4` variant referenced in the 2026-08-20 research is real but see the NVFP4 caveat below before treating it as the default screening artefact |
| 7 | Gemma 4 26B-A4B | hybrid MoE/QAT candidate | `google/gemma-4-26B-A4B-it-qat-q4_0-gguf` | Gemma licence | MoE: 25.2B total / 3.8B active, official QAT | confirmed current and available — research doc's "if current availability/runtime support checks out" condition is satisfied |
| 8 | Qwen3.8-27B | dense deep baseline/challenger | `Qwen/Qwen3.8-27B` | apache-2.0 | dense, 5120 hidden / 64 layers, hybrid Gated-DeltaNet + Attention blocks, native vision, 262K context, MTP-trained | confirmed current (released 2026-08-14, so newer than the 2026-08-20 research doc itself) — ignore third-party leaderboard/"beats model X" blog claims entirely; not admissible LM2 evidence |

Do not add more families without a documented reason (missing capability,
incumbent failure, or a materially different architecture class this list
doesn't already cover) — the point is deliberate diversity, not coverage.

## Quantisation strategy (B3)

One low-cost screening representation per family, plus the plausible
finalist sweep set. Prefer model-native QAT where it exists.

| Family | Screening quant | Finalist sweep (if it clears step 1) | Notes |
|---|---|---|---|
| Gemma 4 (all sizes) | official QAT Q4_0 GGUF | official QAT Q4_0 vs Q5_K_M/Q6_K post-training GGUF at the same size, **and** compare against the already-measured Ollama-library artefact | This is the specific "QAT vs ordinary post-training quant" comparison B3/LM1 flagged as unresolved — do not skip it for a Gemma finalist |
| Qwen3.5-9B | already screened (LM1) | Q5_K_M / Q6_K only if `code-fast`/`local-agent` becomes a live promotion candidate | Reuse LM1 evidence; don't re-run Q4_K_M |
| LFM2.5-8B-A1B | official GGUF, Q4_K_M-class | IQ4_XS/IQ4_NL if fully-GPU-resident headroom exists at 32K context | MoE with only 1.5B active — likely cheap to screen even at a higher quant |
| Ornith-1.0-9B | Q4_K_M | Q5_K_M / Q6_K if it clears screening on coding tasks | Dense 9B, same VRAM class as `qwen3:8b` |
| Qwen3.6-35B-A3B | Q4_K_M (necessarily hybrid offload on 10GB VRAM) | IQ4_XS/IQ4_NL if offload latency is the bottleneck; Q5_K_M only if `local-strong` promotion is plausible and memory allows | MoE hybrid — sweep GPU-layer offload explicitly, not just quant |
| Nemotron 3.5 Lightning 30B-A3B | GGUF Q4_K_M via CUDA llama.cpp, **not** NVFP4, for the first pass (see caveat below) | NVFP4 only as a memory-fit variant if Q4_K_M can't fit a useful context; Q5_K_M if promotion is plausible | See NVFP4 caveat |
| Gemma 4 26B-A4B | official QAT Q4_0 GGUF | Q5_K_M/Q6_K only if it displaces an incumbent | Same official-QAT-first principle as the smaller Gemma rows |
| Qwen3.8-27B | Q4_K_M | IQ4_XS/IQ4_NL if latency under hybrid offload is marginal; Q5_K_M if `local-deep`/`reasoning-strong` promotion is plausible | Dense 27B will not be fully GPU-resident on 10GB — expect meaningful CPU offload; measure it honestly rather than assuming it disqualifies the model |

**NVFP4 caveat (resolves B3's "only if the RTX 3080 Ampere runtime
actually supports them usefully"):** current evidence (llama.cpp NVFP4
GGUF support, 2026) is that NVFP4 on Ampere (RTX 3080) is a **memory-only**
win — it lets a model fit that otherwise wouldn't, but does not deliver
the throughput gain NVFP4 gets on newer (Blackwell-class) tensor cores,
because Ampere lacks the native FP4 tensor-core path. Use NVFP4 for
Nemotron only if `Q4_K_M`/`IQ4_XS` genuinely can't fit a useful context at
acceptable offload — not as the default screening quant.

Do not assume newer/smaller-bit is automatically better. Record for every
row actually run: size, VRAM residency, CPU offload, context KV cost,
runtime support, quality risk, and measured throughput — same fields as
LM1's benchmark schema already captures (`core.database.BenchmarkResult`),
extend that table rather than inventing a second one (see registry schema
below).

## Runtime dimension (B4)

Do not make Ollama the only benchmark runtime — it cannot exercise exact
GGUF quant/offload/context combinations the way `llama.cpp`/`llama-bench`
can, and it cannot run an artefact production Ollama's version doesn't
support (the exact wall LM1 hit with Gemma 4).

- **Production Ollama** (`127.0.0.1:11434`, via `src.llm_core.llm_call`
  exactly as LM1 does) — required for any configuration a promotion
  decision will actually bind to, since that's what `execute_local` calls
  in production. This is production-equivalent screening/finalist
  confirmation, not supplemental.
- **CUDA `llama.cpp`/`llama-bench`** (a scratch, non-systemd, user-local
  build — same pattern LM1 used for the temporary second Ollama instance,
  torn down after use) — for exact GGUF quant/offload/context sweeps
  Ollama can't isolate cleanly, and for any artefact production Ollama's
  installed version can't load yet.
- No third runtime unless it adds a capability neither of the above has
  and does not create a second routing/result authority. Odysseus
  (`core.database.BenchmarkResult` + `config/models.yaml`) remains the one
  benchmark/result/routing authority regardless of which runtime executed
  a given row.

A `llama-bench` measurement is supplemental evidence about a quant/offload
configuration's raw throughput. **A configuration is only eligible for
promotion once it has also been exercised through the actual Odysseus
execution abstraction** (`execute_local`/`llm_call` against a production
or production-equivalent Ollama instance) — matching LM1's own rule that
a benchmarked model must run through the same call path production
routing uses wherever technically possible.

## Screening and promotion funnel (B5)

1. **Licence/runtime/hardware/disk prefilter.** Confirm licence terms
   (flagged "verify" rows above especially), confirm a compatible
   runtime/artefact exists, confirm disk headroom. Record the blocker and
   move on for anything that fails — do not force it.
2. **Exact artefact provenance + integrity.** Pin upstream repo, exact
   revision/commit, artifact filename, quantisation, and licence
   reference, same as LM1's `model_manifest.json` convention
   (`upstream_repo`/`upstream_revision`/`artifact`/`quantization`). Verify
   with `hf cache verify` or equivalent where useful.
3. **One representative quant/config per family**, screened against the
   frozen `evals/local_models/corpus.json` estate corpus (extend it only
   if a genuinely new task-class gap appears — do not fork a second
   corpus).
4. **Reject obvious losers.** A configuration that cannot meet the
   relevant task class's quality/latency/usefulness bar relative to the
   current incumbent is rejected here, with the reason recorded. This is
   the cheap stage — do not spend repeat trials on it.
5. **Finalist quant/runtime/context/offload sweep** — only for
   configurations that survive step 4 *and* can plausibly displace an
   incumbent or fill a currently-null alias (`code-fast`, `local-strong`,
   `reasoning-strong`, `vision`). Sweep per the quant table above; record
   GPU residency/offload and context behaviour explicitly, not just a
   pass/fail.
6. **Repeat load-bearing trials** for finalists only (LM1's convention:
   normally 3 total trials) to establish stability, not anecdote.
7. **Compare by task class / alias, never one global score** — same rule
   as LM1's promotion section.
8. **Promote only** when evidence shows a material capability,
   success-rate, latency, locality, or paid-escalation advantage with no
   important regression (deterministic/safety/domain gates unchanged).
   Canary before a full binding change where the routing contract's
   continuous-improvement section calls for it.

## Registry schema (extends existing surfaces, no parallel registry)

Record, per row actually screened or swept — this is the exact field list
B5 requires, mapped onto what already exists:

- family / model / exact revision — `model_manifest.json`-style
  `upstream_repo` + `upstream_revision`
- exact artefact + quant — `artifact` + `quantization` (already on
  `BenchmarkResult`)
- runtime (+ version) — `runtime` + `runtime_version` (already on
  `BenchmarkResult`)
- total/active parameters (MoE) — **new**, small addition to
  `model_manifest.json` entries (`total_params`/`active_params`); not
  worth a new DB column unless a query genuinely needs it
- disk size — record in `model_manifest.json`, not SQLite (compact
  telemetry, per the A2 audit-repair principle)
- context point(s) tested — `context_point` (already on `BenchmarkResult`)
- GPU residency/offload — `gpu_placement` + `peak_vram_mb` (already on
  `BenchmarkResult`, same convention as LM1's supplemental placement
  table)
- expected vs measured RAM/VRAM — measured value in `peak_vram_mb`;
  expected value belongs in the candidate registry entry
  (`evals/local_models/candidates.json`, new — see below), not SQLite
- TTFT/decode/wall time — `wall_time_ms` at minimum (already on
  `BenchmarkResult`); add TTFT/decode-tok/s columns only if `llama-bench`
  supplemental data needs a home, following the same additive-migration
  pattern A2 used for `raw_output_sha256`
- task score/stability — `score` + repeat-trial rows keyed by `run_id`
  (already the LM1 convention)
- reason for promotion/rejection — `reason` (already on
  `BenchmarkResult`) for the deterministic/comparative reason; the actual
  promotion decision and its rationale belongs in `config/models.yaml`
  and the LM2 evidence doc, same as LM1

`evals/local_models/candidates.json` (new file, sibling to
`model_manifest.json`) is the one addition this task should make: a
durable pre-execution registry of the eight rows above (family, role,
official repo, licence status, architecture, screening quant, why
included/corrected), populated at the start of LM2 execution and updated
in place as each row moves through the funnel (`state`: `candidate` ->
`screening` -> `finalist` -> `promoted`/`rejected`/`blocked`, reusing the
same state vocabulary A4 established in `config/models.yaml`). This is
the "candidate registry" B7 asks for — do not also duplicate it into
SQLite.

## Resource/GPU serialization rules

- No concurrent GPU jobs. One model resident at a time, same
  `keep_alive: 0` unload discipline LM1 established
  (`scripts/run_local_model_benchmark.py::unload_all`).
- One new model download at a time.
- A CUDA `llama.cpp` scratch instance, if used, follows the exact LM1
  pattern for the temporary second Ollama instance: user-local, non-root,
  non-systemd, torn down at the end of the session, never registered in
  `config/estate.yaml`.
- Never run a benchmark workload against the robotics-reserved GPU window
  without confirming no robotics experiment needs it (per the lab
  strategy doc's resource-awareness requirement).

## Evidence and promotion gates

Same gates as LM1's promotion section, unchanged:

- no regression on permissions/safety/domain gates;
- deterministic success not worse than the current incumbent for that
  task class;
- repeated trials for finalists, not one-off anecdotes;
- no invented universal numeric quality floor — derive task-specific
  gates from the frozen corpus where defensible, otherwise report
  insufficient evidence and leave the binding as-is;
- a binding change updates `config/models.yaml` (`capabilities:` +
  `installed_candidates:` state) only when these gates pass, plus a
  matching entry in the new LM2 evidence document.

## Agent/resource policy

Sonnet 5 medium is foreman, not the benchmark worker — same as LM1.

Prefer: `deterministic Odysseus harness -> local candidate -> deterministic
scoring -> Sonnet synthesis`.

Rules (unchanged from LM1, restated because they still apply): no
same-model nested Sonnet by default; no Opus/Sol/paid adjudication for
routine benchmark output; at most one independent high-capability review
for a material routing/registry architecture change or an unresolved
qualitative tie affecting promotion; no concurrent GPU jobs; no LLM used
to verify a fact a deterministic gate already establishes.

## Stop / handoff

Stop only when:

- every registry row has reached prefilter/screening/finalist/promotion
  resolution (promoted, rejected, or explicitly blocked) and the evidence
  doc is committed; or
- a genuine human-only credential/licence/hardware decision blocks a row
  (record it and continue with the rest, same as LM1's Ollama-version
  blocker); or
- resource limits require a checkpoint — preserve a salvage manifest
  (exact HEAD, downloaded artefacts, completed rows, remaining rows,
  running processes, next command) and resume from evidence rather than
  re-running completed rows.

Do not expand into third-round/experimental frontier checkpoints (the
"experimental, not first-round" tier from the 2026-08-20 strategy doc)
without a fresh, explicitly-scoped follow-up task.

## Final output

Report only:

- registry rows actually screened/swept, with exact upstream
  repo/revision/artifact/quant/runtime per row;
- per-alias winners or "no promotion", by task class, not one global
  score;
- key quality/latency/resource evidence for anything promoted or
  narrowly rejected;
- config/routing changes made;
- tests/live regression evidence;
- blockers deferred to a future pass;
- final HEAD SHA.

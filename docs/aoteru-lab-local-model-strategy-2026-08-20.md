# Aoteru lab local-model strategy — 2026-08-20

## Purpose

Durable research snapshot for selecting, benchmarking and continuously replacing local models on the Aoteru/Odysseus lab worker. This is tailored to the estate's actual workloads rather than generic chat benchmarks.

This document is **not** a permanent model ranking. Stable routing aliases remain authoritative; named models are incumbents/challengers that must earn promotion from measured estate-task performance.

## Canonical lab hardware

Live OS probes on 2026-08-20 establish:

- host: `dmem-HP-Z2-Tower-G9-Workstation-Desktop-PC`
- CPU: Intel Core i9-12900K, 16 cores / 24 threads, AVX2 / AVX-VNNI
- RAM: **128 GB installed/online** (`125 GiB` usable reported by Linux)
- GPU: NVIDIA GeForce RTX 3080
- VRAM: **10 GB / 10,240 MiB**
- driver: 560.35.03
- CUDA reported by driver: 12.6
- storage: WD PC SN810 2 TB NVMe; Linux root ~984 GB with ~668 GB free at capture
- platform: Linux x86_64
- existing local inference integration: Ollama

The 10 GB GPU is the primary local-model constraint. The 128 GB system RAM makes much larger quantised models feasible through CPU/GPU hybrid placement, but system RAM is not a substitute for VRAM: models that merely load can still be operationally poor because of PCIe and memory-bandwidth latency.

## Estate workloads the local portfolio must optimise for

Benchmarking and routing must represent real work from:

### Odysseus

- routing and host/model selection
- repository reconnaissance
- bounded coding and repair
- tool/function calls
- schema-valid structured output
- fault diagnosis
- compact result synthesis
- background stewardship/auditing

### `obsidian-PhD`

- source discovery and evidence tracing
- evidence extraction with provenance
- literature synthesis
- scientific reasoning
- note maintenance and compression
- long-context retrieval across research artefacts

### J1 / ICAC work

- manuscript critique
- paper-grounded Q&A
- source/claim checking
- presentation evidence checks
- academic synthesis and independent review

### S2-E1 / robotics development

- ROS 2 repository reconnaissance
- test and CI repair
- log interpretation
- bounded implementation/debugging

Local AI resource use must remain resource-aware so background Aoteru work does not interfere with robotics experiments requiring the RTX 3080.

## Strategic architecture

There should not be one `local_model`. Odysseus should route through stable capability aliases and replace their backing models without downstream skill changes.

Initial alias set:

- `local-small` — high-volume extraction, classification, formatting, cheap review
- `local-agent` — default local reasoning, tool use, repo scouting
- `local-multimodal` — documents, screenshots, figures, audio/vision where useful
- `local-code` — routine bounded coding/editing
- `local-strong` — harder repo, coding and agentic work
- `local-deep` — highest-quality local reasoning where latency is acceptable
- `local-challenger` — canary slot for newer credible candidates

Routing principle:

> An adequate local result beats a paid result; an inadequate local result does not.

Escalation remains:

`deterministic tool -> local-small/local-agent -> local-strong/local-deep -> paid Luna/Haiku -> Terra/Sonnet -> Sol -> Opus`

The exact path is task-specific; multimodal work can branch directly to `local-multimodal`.

## 2026-08-20 research shortlist

### First-round candidates

1. **Gemma 4 E4B**
   - candidate for `local-small`
   - likely strong fit for high-volume classification/extraction
   - Google publishes consumer/workstation-oriented deployment guidance

2. **Qwen3.5-9B**
   - primary predicted incumbent for `local-agent`
   - also initial candidate for `local-code`
   - attractive because it can plausibly remain fully GPU-resident at a useful quantisation/context while offering tool/agent/coding capability

3. **Gemma 4 12B**
   - primary `local-multimodal` candidate
   - Google estimates roughly 6.7 GB at Q4_0, making it unusually well matched to 10 GB VRAM
   - useful differentiator: multimodal capability rather than duplicating Qwen3.5-9B

### Second-round candidates

4. **Qwen3.6-35B-A3B**
   - strongest initial candidate for `local-strong`
   - MoE architecture: ~35B total, ~3B active/token
   - necessarily hybrid on 10 GB VRAM, so actual latency and context behaviour must be measured

5. **NVIDIA Nemotron 3.5 Lightning 30B-A3B**
   - `local-challenger`
   - very recent agentic/reasoning candidate with Ampere-compatible deployment paths
   - must not displace an incumbent from recency alone

6. **Qwen3.8-27B**
   - primary `local-deep` challenger
   - dense model; likely slower than MoE alternatives when partially offloaded
   - valuable if it can avoid expensive cloud escalation on hard reasoning/coding/research tasks

### Experimental, not first-round production candidates

- Qwen3-Coder-Next 80B-class
- Mistral Small 4 119B-A6B
- very large GPT-OSS / frontier open checkpoints

The lab has enough RAM to load some of these quantised, but that does not make them good interactive workers. They should only be explored after smaller candidates establish the useful quality/latency frontier.

## Runtime strategy

Keep **Ollama** as the stable Odysseus-facing local API where it performs adequately.

Add **CUDA-enabled `llama.cpp` / `llama-bench`** for controlled benchmarking and specialist hybrid inference because the lab's 10 GB VRAM + 128 GB RAM topology benefits from explicit GPU-layer/offload control.

Do not make vLLM the universal initial runtime on this worker. Reconsider it for models/hardware where its serving model is a better fit.

Record actual processor placement and context during every benchmark. A model benchmarked at 4K with full GPU residency is not equivalent to the same model at 32K/64K with partial CPU placement.

Minimum context benchmark points:

- 8K — bounded subagent work
- 32K — normal repository/research work
- 64K — long agent work
- 128K only where the task/model demonstrably benefits

## Quantisation and residency

Do not default blindly to the smallest quant.

For GPU-fit models, benchmark Q4/Q5/Q6-class variants where available and select the highest-quality quant that preserves useful context while remaining fully or nearly fully GPU resident.

For hybrid models, explicitly sweep GPU offload and context. Record:

- quantisation
- runtime/version
- context
- GPU layers/offload
- peak VRAM
- peak RAM
- prompt tokens/s
- decode tokens/s
- time to first token
- wall time
- deterministic task success
- tool-call validity
- retries
- escalation rate

## Estate benchmark suite

Use fixed, reproducible tasks derived from real repositories and research workflows. Public leaderboards can nominate candidates but must not promote them.

Required task classes:

1. repository reconnaissance
2. bounded code edit with deterministic tests
3. fault diagnosis
4. tool-call correctness
5. strict JSON/schema generation
6. evidence extraction with source provenance
7. PhD/scientific reasoning
8. long-context retrieval
9. document/image understanding
10. compact summarisation/compression
11. independent review of another worker's result
12. ROS/log/test interpretation

Prefer deterministic gates wherever possible. A patch that another LLM likes but that fails tests is a failure.

## Promotion and demotion

Promote a candidate only when repeated estate-task evidence shows one or more of:

- materially higher task success
- equivalent success with materially lower latency
- equivalent success with materially less paid escalation
- a useful capability the incumbent lacks

Hard requirements:

- no regression on permissions/safety/domain gates
- deterministic success not worse than incumbent
- repeated trials, not one-off anecdotes
- low-risk canary period before full promotion

Use recency-weighted telemetry so old benchmark wins decay rather than protecting an incumbent indefinitely.

Routing should learn by **task class**, not force one model to win every alias. A plausible future split could be one model winning extraction, another tool use, another multimodal understanding, another repo repair, and another scientific reasoning.

## Continuous model discovery

Local-model selection is an ongoing estate function, not a one-time P7 exercise.

Lifecycle:

`official release -> metadata/hardware-fit screening -> candidate registry -> download one useful quant -> synthetic estate benchmark -> low-risk canary -> promote/demote/remove -> continuous telemetry`

Discovery should monitor credible publishers such as Qwen, Google/Gemma, NVIDIA, Mistral and other strong open/open-weight model labs. Discovery nominates candidates only; it must not indiscriminately download models.

Candidate pre-filter should consider:

- runtime/architecture support
- licence acceptability
- 10 GB VRAM / 128 GB RAM fit
- useful >=32K context
- structured output/tool-use support where relevant
- coding/reasoning capability
- local quant availability
- expected operational value over incumbent

## Current predicted portfolio

These are **research predictions to benchmark**, not final routing truth:

- `local-small` -> Gemma 4 E4B
- `local-agent` -> Qwen3.5-9B
- `local-multimodal` -> Gemma 4 12B
- `local-code` -> Qwen3.5-9B initially
- `local-strong` -> Qwen3.6-35B-A3B if lab benchmark passes
- `local-deep` -> Qwen3.8-27B if latency is acceptable
- `local-challenger` -> NVIDIA Nemotron 3.5 Lightning 30B-A3B

The strongest prior is that **Qwen3.5-9B will be the throughput workhorse**, **Gemma 4 12B the best fully GPU-resident multimodal worker**, **Qwen3.6-35B-A3B the most promising hybrid strong-agent candidate**, and **Qwen3.8-27B the most valuable deep local challenger to cloud escalation**. These predictions must be replaced by measured estate evidence when implementation runs.

## Source anchors from the 2026-08-20 research

Primary/current references used to nominate candidates and define runtime constraints:

- Qwen3.5-9B: https://huggingface.co/Qwen/Qwen3.5-9B
- Qwen3.6-35B-A3B: https://huggingface.co/Qwen/Qwen3.6-35B-A3B
- Qwen3.8-27B: https://huggingface.co/Qwen/Qwen3.8-27B
- Qwen3-Coder-Next: https://huggingface.co/Qwen/Qwen3-Coder-Next
- Gemma 4 model overview: https://ai.google.dev/gemma/docs/core
- Gemma 4 model card: https://ai.google.dev/gemma/docs/core/model_card_4
- NVIDIA Nemotron 3.5 Lightning 30B-A3B: https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4
- Mistral Small 4 119B-A6B: https://huggingface.co/mistralai/Mistral-Small-4-119B-2603
- Ollama context guidance: https://docs.ollama.com/context-length
- Ollama running-model/placement API: https://docs.ollama.com/api/ps
- llama.cpp benchmark tooling: https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md
- llama.cpp server/offload controls: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md

## Relationship to routing authority

This document supplies the lab-specific evidence and candidate portfolio for `docs/aoteru-model-host-routing-contract.md`.

The routing contract remains authoritative for host eligibility, quality floors, permissions, verification and continuous improvement. This document exists so future implementations and benchmark cycles understand why particular local candidates were selected and which real estate tasks must determine whether they remain installed.
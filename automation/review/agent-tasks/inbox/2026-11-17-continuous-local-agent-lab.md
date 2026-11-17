---
title: Continuous local-model agent execution on the lab workstation
status: inbox
priority: high
owner_repository: tyecam1/odysseus
task_class: local-agent-runtime
created: 2026-11-17
updated: 2026-11-17
execution_scope: shared-runtime
dependencies:
  - docs/aoteru-model-host-routing-contract.md
  - docs/aoteru-lab-local-model-strategy-2026-08-20.md
  - docs/runtime-work-packages/2026-11-16-lazyusage-sonnet-coordinator-lab.md
---

# Continuous local-model agent execution on the lab workstation

## Outcome

Make `hz2-workstation` capable of progressing **eligible, accepted agent-task work continuously while the operator is offline**, using a qualified locally hosted model whenever it can meet the task's quality floor. This means a durable, bounded **multi-step tool-using worker that finishes and verifies real work**, not just a model responding to single prompts, an idle model server, or an additional task scheduler. Retain Odysseus as the sole queue, routing, lease, budget, dispatch and acceptance authority. Do not create competing orchestration in Misumi or obsidian-PhD.

Prioritise useful accepted backlog throughput and reduced paid quota; do not maximise GPU uptime or model parameter count. Preserve shipping-first backlog policy: initial state `inbox`, promote ahead of existing accepted work only with evidence that it directly unblocks delivery or by operator reprioritisation.

## Ground truth and existing capability (must recheck live)

- Lab: HP Z2 Tower G9 / `hz2-workstation`; last recorded i9-12900K, 128 GB RAM (125 GiB usable), RTX 3080 **10 GB VRAM**, Linux; Ollama serves via loopback. This is historical inventory, **not** current live telemetry. Reprobe `nvidia-smi`, `free -h`, CPU, disk, runtime versions, models, systemd services, GPU/robotics reservations, current HEAD and actual production routing before selecting anything.
- Existing local aliases in `config/models.yaml`: `local-fast=qwen3:8b`, `local-strong=gpt-oss:20b`, `code-fast=ornith:9b`, `reasoning-strong=nemotron-3.5-lightning:30b-a3b`, `vision=gemma4:12b`; `local-classify=qwen3.5:9b` is qualified only for a narrow classification task. `code-strong` is currently null. Historical LM4 canary passed narrow production-route checks, **not** sustained autonomous code-agent execution.
- `/lazyUsage` already supplies a durable opt-in run loop, frontier persistence, checkpointed advisories, usage-aware paid coordination and pause/stop/restart; the 2026-11-16 GLM-Flash coordinator is advisory, not a local code executor. Inspect current deployment/acceptance, not just committed design.
- Canonical: `AGENTS.md`, `docs/aoteru-model-host-routing-contract.md`, `config/estate.yaml`, `config/routing.yaml`, `src/estate_router.py`, `src/lazy_usage_runtime.py`, model qualification files, `evals/local_models/**` and lab GPU admission controls. Run `aoteru preflight` against live authority. Do not infer that a model alias, launcher, passing text canary, or registered host is agent-qualified.

## Implementation packets

1. **Measure the actual gap.** Trace one real accepted, safe queue task end-to-end from `/lazyUsage` through preflight, model selection, worker tool calls, write lease, deterministic verification, continuation, durable result and acceptance. Record exactly where local inference is ineligible or single-turn only. Reuse current machinery and close any already-shipped duplicate scope. No new daemon, queue, planner, agent framework, task register or repository-local router.

2. **Benchmark candidates across *agent* tasks, not generic leaderboards.** Compare existing `ornith:9b`, `qwen3:8b`, `gpt-oss:20b`, `qwen3.5:9b` and `nemotron-3.5-lightning:30b-a3b` as eligible baselines; then one-at-a-time current challengers such as Qwen3.5/3.8 small and coding variants, Qwen3.6-35B-A3B, Qwen3.8-27B, Qwen3-Coder 30B/Next, or another independently credible November-2026 release. Verify each exact model ID, architecture, license, supported tool protocol and runtime before downloading. The large 80B-class MoE and similar checkpoints are **exploratory only** on this 10 GB card: low active parameter count does not remove total weight memory or CPU-transfer costs.
   
   Evaluate quantisation by task rather than blindly using smallest files: GGUF `Q4_K_M`, `Q5_K_M`, `Q6_K` or appropriate IQ quants where supported; native MXFP4 for GPT-OSS; AWQ/GPTQ/FP8 only when the chosen runtime actually supports the architecture and yields an advantage. Test *weights AND KV cache*: F16 vs Q8_0 vs Q4_0 KV, flash attention, context 8K/16K/32K/64K if usable, model residency, GPU-layer offload, MoE expert placement and concurrency. Benchmark both full GPU fit and intentional CPU/GPU hybrids. Exclude unstable or inaccurate 2-3 bit variants unless repeated agent success actually justifies them. Never equate advertised model context with useful context.
   
   Start with existing Ollama API; use CUDA-enabled `llama.cpp`/`llama-server` plus `llama-bench` for explicit controls. Consider vLLM/SGLang/other serving formats only if supported and measurably superior on this exact 10 GB GPU. Avoid maintaining parallel heavyweight inference stacks.

3. **Qualify a real local tool-using executor.** Through Odysseus' existing provider-neutral task envelope, add the smallest missing adapter/worker loop for: structured tool-call parse; whitelisted read/search/test commands; bounded context retrieval; bounded edit/patch proposal; execution in an isolated worktree *only* under the existing write lease; deterministic validation; retry on observable failure; compact durable state; stop/escalation on uncertainty. Constrain maximum tool turns, repeated calls, context/tokens, wall time, command permissions, path scope and total worker effort. No unrestricted shell, credentials, network exfiltration, destructive operations or self-certified merge. Tool-call parse failures must not become shell text. Keep local model requests internal and private.

4. **Connect to durable, autonomous task progression.** Integrate with existing `/lazyUsage` selection/advance and central preflight: deterministic tasks first, qualified local agent next where it passes the quality floor, paid models only for evidenced quality failures or protected escalation. Queue scheduling must be event-driven and restart-safe with checkpointed task/HEAD/lease; one task owner; no duplicate side effects, runaway retries, circular self-generated tasks or endless re-review of unchanged HEAD. Respect existing task status, human-only gates, dependency readiness, acceptance and repository ownership. The service should be available 24/7, but inference should work only on eligible work and release resources on idle, experiments, thermal/power contention or other reservation. Prefer **one active local default model** and at most one serial comparison/escalation model, not multiple heavyweight models simultaneously.

5. **Integration and quality evaluation.** Extend `evals/local_models/**` beyond the existing single-turn LM corpus with fixed, version-pinned, multi-turn real-repository tasks: bounded code repair with tests, 2-5 tool-call sequences, tool error recovery, repository reconnaissance, source-provenance extraction, ROS/log interpretation, conflict/stale-HEAD handling, and verification of another worker. Use existing fixture/harness infrastructure and controlled holdouts; no PhD paper/evidence promotion by an unreviewed model. Compare against (a) deterministic-only, (b) incumbent local route, (c) current qualified paid route. Measure end-to-end **accepted tasks/hour, successful independent verified patches, precision of tool selection, deterministic pass rate, correct stops/escalations, context failure, median/p95 latency, prompt/decode tokens/s, peak VRAM/RAM, CPU load, model cold/warm load, energy/power where measurable, restart recovery, actual paid calls saved and human rework**. Pre-register minimum quality and useful throughput floors before promotion. A single green tool call or microbenchmark is not enough.

6. **Deploy and exercise.** Implement on a branch under existing write lease, review through independent qualified lane, merge per governing gate, deploy to the actual lab backend and record model digest/quantisation/runtime flags. Execute an unattended controlled **24-hour** canary with real low-risk queue items, including a restart, stale task, failed tool, unavailable model, GPU experiment reservation and operator pause. Confirm work progresses when the laptop is offline and resumes without duplicate writes. Confirm that GPU use never interrupts a reserved robotics experiment. Add health/queue/throughput/error visibility and a one-switch rollback to the incumbent route. Do not call this shipped until observable accepted tasks complete on the deployed service.

## Acceptance gates

- Live hardware, GPU pressure, model inventory, queue/runner status and current baseline evidenced. At least one **quantified comparison table** ranks actual candidate + quant + context + serving configurations by verified end-to-end task success and throughput on this host; explain rejected options.
- A local agent independently performs multiple bounded tool turns, completes and verifies at least **three distinct low-risk real task units** through the production path, with task/commit/tool/verification provenance. No fabricated quality claims or proxy-only tests.
- 24-hour unattended canary shows persistence, restart recovery, task deduplication, no budget or lease bypass, safe halt/yield on experiment GPU reservation, and no paid call unless a separately qualified escalation is warranted.
- Adversarial tests: malformed or hallucinated tools, prompt injection in repository content, command injection, hidden credentials, missing runtime, OOM, low disk, long context, GPU contention, model timeout, invalid patch, flaky tests, stale HEAD, expired lease, quota exhaustion and externally protected approvals.
- Measured local agent is not promoted for a class unless deterministic result quality meets the incumbent class floor and it yields useful task throughput or demonstrable paid-call savings. If no qualifying agent is practical on 10 GB VRAM, report exact constraints and a minimal hardware/cloud escalation recommendation; **do not fabricate an always-on capability**.
- Update central `config/models.yaml`, routing/host qualification, tests, current `/lazyUsage` contracts and concise operational evidence only. Do not change immutable prompt-register entries in place; no new prompt register or extra scheduler. Record skipped/rejected candidates and stopping reason.

## Sources and constraints

Existing estate evidence: `docs/aoteru-lm4-production-canary-evidence.md`, `docs/aoteru-lm2-model-discovery-evidence.md`, `docs/aoteru-lab-local-model-strategy-2026-08-20.md`, `docs/runtime-work-packages/2026-11-16-lazyusage-sonnet-coordinator-lab.md`.

Current model/runtime primary references to verify live at execution: https://huggingface.co/Qwen/Qwen3.5-9B ; https://huggingface.co/openai/gpt-oss-20b ; https://huggingface.co/Qwen/Qwen3-Coder-Next ; https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md ; https://docs.ollama.com/context-length .

**Scheduling boundary:** This is a new capability request. Shipping-first policy remains active. Capture here in the canonical Odysseus inbox; establish a dependency-unblocking case before preempting accepted backlog work.

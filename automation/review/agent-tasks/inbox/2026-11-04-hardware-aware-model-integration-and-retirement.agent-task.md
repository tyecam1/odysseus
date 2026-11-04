---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-04-hardware-aware-model-integration-and-retirement
title: "Integrate recent qualified open models and retire unused weights with storage-first cleanup"
status: inbox
priority: medium
task_type: recent-model-integration-and-storage-aware-retirement
created_by: chatgpt
created_at: 2026-11-04
updated_at: 2026-11-04
executor: codex_subscription
execution_mode: evidence-first-bounded-implementation
architecture: single-plus-verifier
architecture_rationale: "One owner audits storage and dependency safety, clears safe unused weights as early as needed, then integrates only genuinely recent promising models. A separate qualified verifier checks promotion and consequential deletion; no parallel manager or router."
single_agent_baseline: "One worker records live free space and model dependencies, safely reclaims confirmed-unused weights before downloads if needed, screens only recently released candidates against existing incumbent evidence, and integrates justified improvements."
execution_host: lab
context_budget: medium
coordination_reason: "Protect production workloads and experiment GPU priority; execute host-specific work sequentially through the existing Odysseus routing, authority and leases."
requires_remote_compute: true
requires_local_model: true
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - automation/review/agent-tasks/**
  - config/models.yaml
  - config/estate.yaml
  - config/routing.yaml
  - evals/local_models/**
  - docs/**
  - scripts/**
  - src/**
  - tests/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
inputs:
  - AGENTS.md
  - automation/review/agent-tasks/README.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/aoteru-lm4-production-canary-evidence.md
  - docs/aoteru-lm2-model-discovery-evidence.md
  - docs/aoteru-local-model-benchmark-routing-evidence.md
  - config/models.yaml
  - config/estate.yaml
  - config/routing.yaml
  - evals/local_models/corpus.json
  - evals/local_models/candidates.json
  - live host model inventory, active process/route observations and dependency references
  - tyecam1/misumi@main/docs/operations/local-llm.md
  - tyecam1/misumi@main/host-agent/README.md
  - tyecam1/s2-e1-ros2-measurement-spine@main/docs/hardware_register.md
outputs:
  - provenance-backed per-host installed/use/dependency inventory and retirement disposition
  - dated release/eligibility screening and targeted production-path verification of shortlisted recent challengers
  - minimal qualified integrations using current Odysseus model aliases and eval authority
  - evidence-backed, host-specific uninstall log for all safely confirmed-unused AI model weights
  - post-cleanup runtime, fallback, storage and research-boundary verification
  - concise outcome and rollback record
result_path: docs/runtime-work-packages/2026-11-model-integration-and-retirement.md
review_report_path: automation/review/model-integration-and-retirement-independent-review.md
handoff_model: claude_subscription
operator_decision_path: docs/runtime-work-packages/2026-11-model-integration-and-retirement.md
supersedes: []
duplicates: []
notes: "Operator correction 2026-11-04: do not spend evaluation effort on months-old new candidates; old qualified incumbents are controls, not fresh discovery targets. Storage-aware safe uninstall may precede any benchmark/download. Shipping-first queue priority applies. Removal requires consumer/rollback checks and approval for consequential changes."
---

# Hardware-aware open-model integration and retirement

## Objective and stop condition

Improve lab/home AI capability by screening **genuinely recent model releases**, not spending compute evaluating older potential challengers because they were present in an earlier shortlist. Existing qualified models remain baseline controls and are not needlessly re-benchmarked. Integrate only candidates that demonstrate a real improvement. **Uninstall proven-unused weights promptly**, before any new downloads if available storage or peak temporary disk demand requires it.

This is a finite consolidation task, **not** an evergreen model-discovery service, new router, new task queue or blanket upgrade to newer weights. A model's age alone does not mean it is inadequate or unused. Stop when eligible recent candidates have been screened only as justified, all reachable in-scope installed weights have a disposition, safely unused weights have actually been removed, and approved integrations and affected routes pass verification.

## Ownership and admission

1. Inspect **live** `tyecam1/odysseus@dev`, current model registry and routing code, queue, latest LM evidence, tests, existing model-role evaluation work and host state before edits. `AGENTS.md`'s shipping-first priority controls when this inbox task can be admitted. Deduplicate against current ready/active model-evaluation tasks rather than re-running their accepted work.
2. Odysseus alone owns shared host/model routing, evaluation, telemetry, runtime and cleanup policy. `misumi` remains the household/domain knowledge authority; `obsidian-PhD` owns research/acceptance; S2-E1 owns experiment measurement software. No duplicate backend/model configuration in these repos.
3. Use `aoteru preflight` (or existing API equivalent), live qualified worker selection, governed write leases and existing approval gates. Never infer a host is reachable from historical documentation. New subscription executor versions are resolved by policy, not pinned here.
4. Benchmarks are sequential per physical GPU; experiments have priority. Respect `gpu_priority: yield_to_experiment`, home gaming/load admission, loopback/private exposure, laptop no-local-inference policy, and Jetson `experiment-edge` exclusion from generic model routing. Do not alter robot control or research evidence.
5. Prefer current `evals/local_models/`, `BenchmarkResult`, `RoutingDecision`, `config/models.yaml` and existing rollout mechanisms. No auto-tuning daemon, alternative SQLite, additional serving stack or perpetual discovery loop.

## Stage A. Read-only per-host inventory and baseline

For the lab RTX 3080 10 GiB / ~125 GiB RAM, home RTX 3070 8 GiB / 32 GiB RAM, and any *verified accessible* dedicated device:

- Attest actual GPU, driver, VRAM, RAM, storage, runtime versions, service state, remote access, running workloads, and live installed model identity. Treat July/August repository records as history, not current inventory.
- Enumerate Ollama tags **and underlying blob digests/refcounts**, Hugging Face cache snapshots, downloaded GGUF/safetensors, llama.cpp scratch or standalone server assets, voice/ASR/TTS and OCR/vision model files, unused benchmark scratch downloads, and model weights in container/data directories if present. Never search or report secrets. Keep per-host size and exact source/revision/quant/runtime when discoverable.
- Discover all consumers before calling a model unused: approved Odysseus aliases; routing/worker services; current personas and FCC/tool-call fallback; active sessions; speech/voice services (Kokoro, faster-whisper); embeddings/rerankers; experiment/research processes; rollback/failover policy; config, startup scripts, jobs, scheduled tasks, and explicit pending approved deployments. Check real process/route activity, not only YAML mentions.
- Preserve separate categories: `active-qualified`, `active-specialist`, `required-fallback`, `candidate-under-test`, `unused-confirmed`, `ambiguous/blocked`. Unbound or currently idle is **not by itself** `unused-confirmed`. Historical files and cached artifacts must not create imaginary current consumers.
- Immediately record each host's free/total disk space, sizes of model stores, existing routing bindings and the dependency/rollback evidence needed for safe removal. This **minimum safe inventory is the prerequisite for uninstall**, not the full benchmark or exhaustive retrospective. Do not download until expected peak storage (model + temporary downloads/caches + safety headroom) is available. Finish the full classification iteratively; do not delay safe early removal just to complete a comprehensive report.

## Stage B. Recent-release gate and bounded model challenge

**Recency is an admission filter, not a quality score.** At execution, check the official release date and substantive model revision of every proposed *new* challenger. Default: **only models first released or substantively updated within the preceding 60 days** are eligible for new evaluation. An older model may enter only on a recorded, material uncovered capability where no suitable recent candidate exists; require an explicit exception rationale. A recent README edit, model upload timestamp or quantisation of unchanged older weights does not reset model age. If official dates cannot be verified, classify as unverified and do not download speculatively.

**Do not evaluate months-old newly proposed models merely because an earlier discovery list included them.** Keep still-functional older installed incumbents as controls using existing LM1–LM4 evidence, with only the smallest real-path smoke tests required for a replacement or regression. No chronological pressure to replace an adequate model. Screen only the smallest number of eligible recent challengers with plausible task and hardware benefits, one new candidate/download at a time. Recheck licence, weight/quant format, architecture and runtime support before acquisition; record exact artifacts. **Run Stage D's early-cleanup gate first whenever storage headroom is insufficient.**

### Home, priority

- Freshness-check `nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB` (reported October 2026) as a possible interactive assistant/tool-use challenger.
- Treat `Qwen/Qwen3.5-4B` and `ibm-granite/granite-4.2-3b` as **historical nominations, not automatic evaluations**. Skip if outside the rolling release window, unless the narrow capability exception applies. Discover current releases in their place, but only where there is a verified gap and disk budget.
- Incumbents: existing qualified `qwen3:8b`, plus `llama3.1:8b` where it still serves FCC fallback. Preserve evidence that `qwen2.5-coder:7b` previously emitted non-executable tool-call JSON; test each new model **through the actual FCC/Odysseus protocol**, not only standalone text generation.
- Test persona voice, correct tools/arguments, strict JSON schema, zero-cloud local turns, memory/grounding, fallback, prompt-injection refusal, p50/p95 end-to-end latency and the ~5 s desired response with the existing 12 s model budget. Do not displace usable `Kokoro` merely for recency.

### Lab, priority

- Challenge `local-fast` with Bolt only after verifying its release/revision meets the recency gate and it offers a plausible material advantage. Treat `Granite 4.2 8B/3B` as stale until verified current; do not benchmark simply because they were in the previous list.
- Preserve existing qualified LM4 baselines: `qwen3:8b`, `gpt-oss:20b`, `ornith:9b`, `nemotron-3.5-lightning:30b-a3b`, `gemma4:12b`, and the narrowly qualified `qwen3.5:9b` classifier. Reuse LM1–LM4 test evidence and repeat only needed tests.
- Retrieval only where a **measured quality, memory or throughput gap** exists: first inspect the existing lexical-safe baseline and usage of the installed embedding/reranker 8B artifacts. Do not launch new benchmarks of older `Qwen3-Embedding-0.6B/4B` or `Qwen3-Reranker-0.6B` variants merely to shrink memory; shortlist only newly eligible releases unless a verified resource constraint creates a material exception. For an admitted challenge, measure recall@k, MRR, contradiction recovery, source attribution and total cost on real PhD questions. No global semantic retrieval activation without PhD research acceptance.
- Document recovery only if extraction failures are a real bottleneck **and** a recent candidate passes the recency gate. Check `nvidia/Nemotron-3.5-Parse` and `PaddlePaddle/PaddleOCR-VL-1.5` dates at execution, and compare only eligible models with the current extraction pipeline on difficult PDFs. Require faithful numbers, reading order, table structure and page provenance; OCR never becomes canonical source truth.

### Optional, dependent work

- Home ASR: if live faster-whisper accuracy/latency is deficient, discover **recent** applicable speech models; the previously named `nvidia/parakeet-tdt-0.6b-v3` and `Qwen/Qwen3-ASR-0.6B-hf` are not automatically eligible and require date checks/exception. Preserve working Kokoro TTS and voice map.
- Jetson/ROS: no automatic installation on the 8 GB Orin Nano. If S2-E1 owners identify a measured RGB-D localisation shortfall and approve a specific evaluation, create **one domain-owned follow-up** for a small specialised model (for example YOLO26 Nano). No safety claim, robot motion authority, Jetson general-LLM worker, unqualified model-induced latency, or unrelated perception scope expansion.
- Explicitly exclude repeat evaluation of already-rejected large families (Qwen3.6-35B, Qwen3.8-27B, Gemma 4 26B-A4B) absent new evidence invalidating the prior result.

For any **eligible recent candidate actually considered for promotion**, freeze a small real-task corpus and score before comparison. Include at least three independent trials for a material promotion decision, more for nondeterministic or safety-relevant failures; avoid broad synthetic matrices. Do not retest old, already-screened challengers or unchanged qualified incumbents to satisfy a notional comparison count. Report model+exact weight revision+quant+runtime+context+GPU residency/offload alongside actual quality, latency, memory and energy/resource proxies. Use independent cross-provider verification when required; one model grading its own output is insufficient.

## Stage C. Minimal integration and rollout

1. For each candidate, choose `retain incumbent | qualify candidate for named task/host | reject | insufficient evidence`. A candidate must meet non-inferior task quality and demonstrate a meaningful latency, reliability, capability or resource benefit; do not invent arbitrary universal floors.
2. Integrate winners **only through existing** Odysseus aliases and per-host qualification/evidence, existing model-serving endpoints and bounded provider contracts. Keep home/lab bindings independent when their hardware differs. Model existence is not approval to route to it.
3. Stage shadow/canary, update references and fallbacks, preserve reversible original configuration, and prove real production-path tool execution and private network exposure. Respect regulated/research approval boundaries and experiment GPU yielding.
4. Record exact observed benefit. If no challenger clears the acceptance gate, retain the incumbents; a no-change decision is a valid result.

## Stage D. Mandatory storage-first and final unused-model cleanup

**This stage can run in two passes, and its first pass may precede Stage B or C.** After Stage A's minimum safe inventory, calculate available storage and estimated *peak* additional requirements for selected model weights, quantisation, downloads, caches and rollback headroom. If storage is insufficient or margin would be unsafe, **remove confirmed-unused artifacts before downloading/evaluating anything**. Even with sufficient headroom, remove clearly unused standalone benchmark weights early when it is safe and avoids pointless storage pressure. Do not reserve excessive space for speculative candidates.

**Completion requires actual cleanup on every reachable, eligible host, not just recommendations.** Pass 1: early, non-disruptive removal of confirmed-unused artifacts. Pass 2: removal of now-superseded weights after candidate canary, fallback and rollback gates. Never delete a still-used incumbent merely to make room for an unqualified challenger.

For every installed weight/artifact classify with a verifiable consumer/absence reason. `unused-confirmed` requires all of:

1. Not selected by any active or qualified alias, household/FCC persona route, research/measurement path, ASR/TTS/vision path, approved fallback, service, container image, scheduled task or live process.
2. No approved pending deployment or model benchmark needs this exact artifact; no unrecorded cross-host use. Inspect recent routing telemetry when available, and explain any inadequate observation window. Lack of telemetry alone must not be treated as proof of no use.
3. If shared blobs, symbolic links or hard links are involved, confirm reference counts and that removal cannot invalidate another retained model. Distinguish `ollama rm <tag>` from unsafe deletion of backing shared blobs. Do not delete arbitrary HF cache snapshots used by other revisions/tools.
4. The exact model/revision/quant, size, source and offline/online recovery procedure are recorded. Back up the governing configuration; demonstrate that rollback can re-pull/recreate the former route and confirm any licensing or access dependency. If recovery is genuinely unavailable, do **not** remove without explicit operator approval.
5. For a production-selected incumbent being superseded, the replacement has passed its real-path canary and the agreed rollback policy either no longer needs local weights or explicitly approves re-download-based recovery. Never uninstall the last known-good fallback before this gate.

For confirmed unused weights, uninstall with the **supported model/runtime operation** (e.g. `ollama rm`, `hf cache rm` or equivalent cache-manager operations with exact keys; controlled scratch removal only for owned, identified directories). Do not recursively delete `~/.cache/huggingface`, `~/.ollama`, model-serving data roots, indexes, ROS bags, calibration data, credentials, Docker volumes, repos or human data. Reject glob-based uninstalls. Keep local model artifact names/digests out of secret logs only as needed; credentials never appear.

Order: as soon as safe, uninstall unused standalone experimental weights and rejected/non-production candidates **before model acquisition if storage is tight**; then run eligible candidate evaluation/integration; then remove superseded active variants only after canary and rollback gates. Examine duplicate quantisations and benchmark-only copies, but preserve distinct artifacts still needed for accepted comparisons, active consumers or approved fallbacks. Remove temporary benchmark servers/processes **only if verified owned by this task**. Do not stop another user's GPU work.

For `ambiguous/blocked`, **retain**, record exact conflict, host/access limitation and required decision, and continue all safe removals. Host unreachability does not count as a completed cleanup. Require explicit operator authorisation at the existing governed host-change gate for any consequential/irreversible production removal; safe model deletions permitted by the approved task scope can proceed after all above guards.

Generate before/after per-host audit:
`installed models (tag/revision/digest/size/status) | retained reason | deleted reason | validation | bytes reclaimed | remaining unavailable/ambiguous | rollback source`.

Update `config/models.yaml` installed-candidate states to match **actual** live inventory. Remove dead executable references, never erase genuine historical evaluation evidence. Do not count merely marking an unused model as unavailable as uninstalling it.

## Stage E. Verification and closure

- Run existing model-registry, routing, endpoint, role, lease/authority, model eval and household-integration regressions; no weakened safety, tool correctness, research integrity or persona acceptance.
- Re-run a live task for every retained qualified alias and every changed host-specific route; validate failover, external provider escalation, context bounds, home gaming admission, lab experiment GPU priority, private port bindings and affected voice/ASR/vision consumers.
- After deletion, independently re-inventory Ollama/HF/standalone artifacts, disk reclaimed and actual service/process state. Verify no missing active model, dangling alias, broken embedding query, disabled approved fallback or unintended deletion.
- Record which models were added, promoted, retained, rejected and **actually uninstalled**, their sizes and exact revision/digest, any instances held for manual review, latency/quality changes, source and test provenance, PR/commit/HEAD and rollback commands.
- Stop after early safe cleanup, at most one **recency-gated** shortlist pass and justified recent finalist comparison, integration and final cleanup. Do not open further generations of discovery merely because new Hugging Face releases appear. At most one concise follow-up for a genuinely blocked, material capability.

## Acceptance checklist

- [ ] Current `dev`, queue priorities, existing LM work, host eligibility and leases reconciled before mutation.
- [ ] Lab/home full live model inventories and role/consumer/dependency graph recorded, including voice, retrieval and fallbacks.
- [ ] Proposed challengers have independently verified substantive release dates; months-old nominees skipped unless a material capability exception is recorded. Existing incumbents are not gratuitously re-evaluated; only evidenced improvements are promoted.
- [ ] No duplicate router, queue, database, cache authority, model server or PhD research authority introduced.
- [ ] Live free space and planned peak disk demand are assessed **before downloads**; safe unused weights are uninstalled early if needed, and an initial before/after space check is recorded.
- [ ] Every installed model has a disposition; all `unused-confirmed` weights on reachable hosts are uninstalled via supported commands in early and/or final cleanup.
- [ ] Shared model blobs, protected fallbacks, model data and research/ROS artifacts preserved; ambiguous items retained with a named blocker.
- [ ] Before/after exact inventories and reclaimed bytes verified, and `config/models.yaml` matches real inventory.
- [ ] All affected active models and routes pass production-path regression, with independent review and rollout authorisation where needed.
- [ ] Evidence package records acceptance, blockers, rollback, source links and final HEAD. No unsupported claim that offline hosts were cleaned.

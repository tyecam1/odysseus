---
title: Aoteru estate P7 evidence
status: compact-evidence
owner: odysseus
as_of: 2026-08-20
parent: docs/aoteru-estate-execution-contract.md
---

# P7 — lab hardware inventory + initial benchmark (lab-first slice)

Compact durable record. Do not reread unless a dependency changes.

## Lab hardware (measured, not assumed)

- CPU: Intel i9-12900K (24 logical via hyperthreading)
- RAM: 125 GiB
- GPU: NVIDIA RTX 3080, 10 GiB VRAM, driver 560.35.03, CUDA 12.6
- Disk: 984 GB total / 668 GB free at repo root
- Ollama 0.19.0 already running (port 11434), already has 6 models
  installed (no new downloads performed this phase): `gpt-oss:20b` (13.8GB,
  MXFP4 — matches plan §9's own "GPT-OSS 20B" candidate exactly),
  `qwen3:30b` (18.6GB Q4_K_M), `qwen3:8b` (5.2GB), `qwen3-embedding:8b`
  (4.7GB), `dengcao/Qwen3-Reranker-8B` (5.0GB), plus a pre-existing custom
  `dmem-box-attest-20260802:sentinel` (7.6B) unrelated to this programme.

**10 GiB VRAM is the binding constraint**: none of plan §9's larger named
candidates (Qwen3.6-35B-A3B ~24GB Q4, Qwen3.6-27B ~17GB Q4,
Qwen3-Coder-Next ~52GB Q4) fit in VRAM on this GPU at their stated
quantization — they'd run substantially CPU-offloaded. Recorded as real
hardware evidence, not assumed from spec sheets.

## Initial measured benchmark (bounded — not the full plan corpus)

Real Ollama `/api/generate` runs, 8K context, single representative coding
prompt (not yet the full "real PhD/coding/memory/Misumi work" corpus plan
§7 wants — that needs obsidian-PhD, which per P0 isn't cloned on this
host):

| model | load_s | prompt tok/s | decode tok/s | VRAM behavior |
|---|---|---|---|---|
| gpt-oss:20b | 2.7 | 220.0 | 23.6 | exceeds 10GB VRAM — partial CPU offload, still 23.6 tok/s decode |
| qwen3:8b | 1.8 | 1369.2 | 106.1 | fits fully in VRAM (`ollama ps` confirmed 100% GPU, 6.6GB used) |

Both completed successfully (`done: true`), no errors, no quality/tool-use
scoring done yet (out of scope for this bounded pass).

## Deferred (genuinely out of scope for this bounded pass, not skipped silently)

- Full representative benchmark corpus (real PhD/coding/memory/Misumi
  tasks) — needs `obsidian-PhD`, absent from this host.
- 32K/64K context testing — not run this pass; larger context on a
  partially-offloaded 20B+ model would take substantially longer than this
  session's remaining budget allows for a first pass.
- Quality / tool-success / structured-output scoring — not attempted.
- Downloading plan §9's other named candidates (GLM-4.7-Flash-30B-A3B,
  Devstral-Small-2-24B, Qwen3.6 family, Qwen3-Coder-Next) — deliberately
  not done speculatively; each is a multi-GB download decision better made
  with explicit direction than grabbed autonomously.
- Dual-host comparison — no second host, per lab-first.
- `config/models.yaml` capability-alias bindings — left `null`; this one
  bounded pass isn't enough evidence to commit to a binding yet.

## Gate

Plan §12 P7 gate: "defaults are evidence-based per host/task; local-first
does not weaken required verification; second-host verification works
independently."

- [x] real hardware inventory recorded (not assumed)
- [x] at least one real, measured benchmark data point exists (not zero
      evidence, per the resource-policy rule against selecting models
      before benchmark evidence exists)
- [ ] full evidence-based default selection — needs the fuller corpus above
- [ ] second-host verification — no second host

**P7: PARTIAL.** Real hardware + a first real (bounded) benchmark data
point exist. Full model-selection evidence and dual-host verification
remain open, honestly deferred rather than rushed to a premature default.

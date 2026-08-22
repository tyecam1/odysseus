---
title: Aoteru quantisation-aware family screening + finalist sweep evidence — LM2
status: compact-evidence
owner: odysseus
as_of: 2026-08-22
parent: docs/aoteru-lm2-quant-runtime-discovery.agent-task.md
---

# LM2 — quantisation-aware family screening + finalist sweep evidence

Compact durable record for LM2
(`docs/aoteru-lm2-quant-runtime-discovery.agent-task.md`). Read that file for
the full contract; this is the evidence and decisions, not a repeat of the
design.

## Live-state preflight

`git pull --ff-only` clean at session start (`aa6dc00`), confirmed running
directly on the lab host (`hz2-workstation`, RTX 3080/10GiB VRAM). LM1 closure
confirmed in `docs/aoteru-local-model-benchmark-routing-evidence.md`. HF auth:
not logged in, no `HF_TOKEN` — all nine registry repos confirmed
non-gated/public via anonymous `huggingface_hub` metadata calls, so this was
not the human-only gate this pass hit (see below). Licence verification for
the two "verify" rows: LFM2.5-8B-A1B's LICENSE file on HF is the LFM Open
License v1.0 — Commercial Use is licensed below a $10M annual revenue
Threshold and Non-Commercial/Research Purposes are unrestricted; this estate
is a personal/research deployment, not a >$10M-revenue commercial product, so
it clears. Nemotron 3.5 Lightning's LICENSE is OpenMDW-1.1 — unrestricted
use/modify/distribute, essentially MIT-equivalent, no commercial threshold.

## The actual human-only blocker this pass hit — broader than LM1's

LM1 found that production Ollama (`0.19.0`) couldn't load Gemma 4's manifest
(`412: requires a newer version of Ollama`). LM2 found the **same class of
blocker affects nearly every new-family candidate in this registry**, not
just Gemma: `ollama pull` against production 0.19.0 returned the identical
412 for `lfm2.5:8b`, `ornith:9b`, `qwen3.8:27b`,
`nemotron-3.5-lightning:30b-a3b`, and `gemma4:e4b`/`gemma4:12b`. Only
`qwen3.6:35b` pulled cleanly onto production — no discernible reason found
for the difference beyond that family's manifest happening to be compatible.

Per the same rule LM1 established (don't touch live production Ollama
without operator authorisation), this pass reused LM1's exact pattern: the
latest static Ollama release (`v0.32.15`, official GitHub `.tar.zst` release,
sha256-verified against the release's own checksum file) into a **user-local,
non-root, non-systemd** location, run as a second instance
(`OLLAMA_HOST=127.0.0.1:11435`, isolated `OLLAMA_MODELS` dir, under this
job's scratch tmp — nothing under this repo or `/etc/systemd`). All five
version-blocked models were pulled and benchmarked through that second
instance. **This second instance was shut down at the end of the session**
(process killed, GPU confirmed clear) — not a persistent estate service, not
registered in `config/estate.yaml`.

**Consequence**: every promising result below (Ornith-1.0-9B, LFM2.5-8B-A1B,
Nemotron 3.5 Lightning, both Gemma 4 QAT-GGUF-direct rows) is real, measured
evidence through a production-equivalent execution path (same
`src.llm_core.llm_call`, same HTTP API shape), but **none of it can actually
bind in `config/models.yaml`'s `capabilities:` section** — production
`execute_local` only ever calls `127.0.0.1:11434`, where these models don't
exist and (for five of the seven blocked families) can't be pulled without
the same version upgrade LM1 already flagged for Gemma. `qwen3.6:35b` is the
one family that IS on production, but it was rejected on latency (see
below), so this doesn't change the zero-binding-changes outcome either.

**Exact safe action that unblocks the whole registry at once** (no
token/credential involved, same one action LM1 already identified for
Gemma): the operator runs `curl -fsSL https://ollama.com/install.sh | sh` (or
equivalent package upgrade) against **production** Ollama, then
`sudo systemctl restart ollama`, then re-`ollama pull` each `benchmark-only`
row in `config/models.yaml`'s `installed_candidates` on `127.0.0.1:11434`.
Until then, `code-fast`, `reasoning-strong`, and `vision` stay `null`,
correctly, not silently faked — LM1's exact wording, still true, now for a
wider set of aliases.

## Runtime: CUDA vs Vulkan llama.cpp (B4 adjustment)

The task doc asks for "CUDA `llama.cpp`/`llama-bench`." This host has no
CUDA toolkit/`nvcc` installed (only Ollama's bundled CUDA runtime libraries,
which a separate llama.cpp build cannot use to compile), and llama.cpp's
official GitHub releases publish no Ubuntu+CUDA prebuilt binary (only
`win-cuda`, `ubuntu-vulkan`, `ubuntu-rocm`, `ubuntu-sycl`, `ubuntu-x64`
CPU-only). The NVIDIA Vulkan ICD (`libnvidia-gl-560`) is present and
`llama-cli --list-devices` confirms it sees the physical RTX 3080 with free
VRAM correctly. This pass used the official prebuilt
`llama-b10586-bin-ubuntu-vulkan-x64` release binary — same physical GPU,
same class of "exact GGUF quant/offload/context sweep Ollama can't isolate
cleanly" evidence B4 asks for, substituting Vulkan for CUDA as the only
available GPU backend without building a toolchain from source. Every
llama.cpp-runtime row in `model_manifest.json` records this substitution
explicitly. All llama.cpp instances (ports 8090/8091/8092) were scratch,
non-systemd, torn down at end of session.

## Candidate registry

See `evals/local_models/candidates.json` for the full B7 registry (10 rows:
2 incumbent controls + 8 candidates, each with licence/architecture/quant
notes and final state). Summary:

| Family | Screening quant/runtime | Result | Final state |
|---|---|---|---|
| Gemma 4 E4B | official QAT Q4_0, llama.cpp/Vulkan direct | 12/14 (85.7%), 1 trial | rejected (doesn't beat qwen3:8b local-fast) |
| Gemma 4 12B | official QAT Q4_0, llama.cpp/Vulkan direct | 37/42 (88.1%), 3 trials — beats LM1's Ollama-library run (11/13) | **evidence-backed promotion for `vision`, blocked on prod Ollama version** |
| Qwen3.5-9B | (LM1, not re-run) | 3-trial evidence carried forward | promoted (incumbent-of-record, unchanged) |
| LFM2.5-8B-A1B | Q4_K_M, Ollama (2nd instance) | 38/39 (97.4%), 3 trials, avg 2.5-2.8s | **evidence-backed, blocked** (no 2nd code-alias slot; see Ornith) |
| Ornith-1.0-9B | Q4_K_M, Ollama (2nd instance) | 39/39 (100%), 3 trials, avg 3.6-6.1s | **evidence-backed promotion for `code-fast`, blocked on prod Ollama version** |
| Qwen3.6-35B-A3B | Q4_K_M, production Ollama | 11/13 (84.6%), 1 trial, avg 93.2s | rejected (6x slower than gpt-oss:20b, no quality edge) |
| Nemotron 3.5 Lightning 30B-A3B | Q4_K_M, Ollama (2nd instance) | 36/39 (92.3%), 3 trials, avg 28.7s, zero errors | **evidence-backed promotion for `reasoning-strong`, blocked on prod Ollama version** |
| Gemma 4 26B-A4B | official QAT Q4_0, llama.cpp/Vulkan direct, -ngl 8 | 10/13 applicable (2 context-window config errors), 1 trial, avg 41.1s | rejected (can't fit a useful context window at 10GB VRAM; worse trade-off than Gemma 4 12B) |
| Qwen3.8-27B | Q4_K_M, Ollama (2nd instance) | 12/14 (85.7%), 1 trial, avg 55.5s, 1 timeout | rejected (2x slower than Nemotron, no quality edge) |

## Systematic finding: the code_repair-01 "full file vs function body" gap

`qwen3.6:35b`, `qwen3.8:27b`, `nemotron-3.5-lightning:30b-a3b`, and
`gemma4-26b-a4b-qat-gguf-direct` all failed `code_repair-01` identically —
inspected one raw output artefact (`qwen3.8:27b`) and confirmed it is a real
model behaviour, not a scoring bug: these larger models return only the
corrected function body (matching the prompt's literal "corrected full
contents of `park_lease_is_stale`"), while the pytest fixture needs the
surrounding imports/class the smaller/faster candidates (Ornith, LFM2.5) and
Nemotron's own third trial included unprompted. This is corpus-instruction
ambiguity interacting with model size/verbosity tendency, not a hard
correctness bug in any of the affected models — recorded here so a future
pass doesn't re-diagnose it from scratch, and so it isn't mistaken for a
uniform quality signal across four otherwise-different architectures.

## Latency reference (same corpus, wall_time_ms from `BenchmarkResult`)

Incumbents (measured by LM1 through this exact corpus):
`gpt-oss:20b` avg 15.2s/call (local-strong), `qwen3.5:9b` avg 38.1s/call
(code-fast/local-agent incumbent-of-record), `qwen3:8b` avg 5.8s/call
(local-fast).

LM2 candidates: `lfm2.5:8b` avg 2.5-2.8s, `ornith:9b` avg 3.6-6.1s,
`nemotron-3.5-lightning:30b-a3b` avg 28.7s, `qwen3.6:35b` avg 93.2s (max
180.1s, one timeout), `qwen3.8:27b` avg 55.5s (max 180.0s, one timeout),
`gemma4-e4b-qat-gguf-direct` avg 8.2s, `gemma4-12b-qat-gguf-direct` avg
14.2-14.4s across 3 trials, `gemma4-26b-a4b-qat-gguf-direct` avg 41.1s.

## Promotion decisions

Same evidence gates as LM1 (no regression on permissions/safety/domain
gates; deterministic success not worse than the incumbent; repeated trials
for finalists; no invented universal quality floor).

- **`local-fast`**: unchanged, `qwen3:8b`.
- **`local-strong`**: unchanged, `gpt-oss:20b`. Both MoE/dense challengers
  screened this pass (`qwen3.6:35b`, `qwen3.8:27b`) are meaningfully slower
  with no quality edge — rejected on latency, not swept further (B5 point 4,
  cheap-stage rejection).
- **`code-fast`**: **evidence clears the bar** (`ornith:9b`, perfect 39/39
  across 3 trials, ~6-10x faster than the `qwen3.5:9b` incumbent-of-record)
  but **binding is blocked** — `ornith:9b` only ran on the temporary second
  Ollama instance; production `execute_local` cannot reach it. Stays `null`
  until the operator upgrade above. `lfm2.5:8b` is comparably strong
  (38/39) and faster still, but this repo has one code-oriented alias slot;
  recorded as evidence-backed-but-unbound rather than silently discarded.
- **`reasoning-strong`**: **evidence clears the bar**
  (`nemotron-3.5-lightning:30b-a3b`, 36/39 across 3 trials, zero
  errors/timeouts, no incumbent to regress against) but **binding is
  blocked** for the same reason. Stays `null`.
- **`vision`**: **evidence clears the bar** — two independent paths (LM1's
  Ollama-library `gemma4:12b`, 11/13, and this pass's official-QAT-GGUF-direct
  `gemma4-12b-qat-gguf-direct` via llama.cpp, 37/42 with `doc_image-01`
  passing all 3 trials) now agree Gemma 4 12B is a strong vision candidate.
  **Binding is blocked** — this evidence used neither production nor the
  second scratch Ollama instance at all (a standalone llama.cpp server), so
  it cannot bind regardless. Stays `null` until the operator upgrade, after
  which `gemma4:12b` should be pulled directly onto production Ollama
  (simpler than standing up a permanent llama.cpp side-channel) for the
  actual binding.
- **`embedding`/`reranker`**: unchanged, out of LM2's scope.

**Net result: zero binding changes in `config/models.yaml`'s `capabilities:`
section**, same as LM1 — but for a different reason this time: not because
the evidence was weak (three aliases now have strong, repeat-trial-backed
promotion evidence), but because the single production Ollama version wall
blocks every promising candidate from actually being reachable by
`execute_local`. `installed_candidates` gained one `production-installed`
row (`qwen3.6:35b`, rejected on merit) and six `benchmark-only` rows
(`qwen3.8:27b`, `lfm2.5:8b`, `ornith:9b`, `nemotron-3.5-lightning:30b-a3b`,
`gemma4:12b-qat-gguf-direct`) — same convention LM1 used for Gemma 4.

## Verification

Focused tests: `pytest -q tests/test_estate_router.py
tests/test_agent_cli_parking_lease.py` -> **34 passed**, the two suites that
touch `config/models.yaml`/manifest-adjacent code. `config/models.yaml`,
`evals/local_models/candidates.json`, and `evals/local_models/model_manifest.json`
all parse cleanly (YAML/JSON load test). `systemctl is-active
odysseus-aoteru-lab.service` -> `active`; `GET /api/health` -> `200`;
confirmed only `127.0.0.1:{7001,11434}` loopback listeners plus pre-existing,
unrelated infra (tailscale/ssh/NFS) — no new `0.0.0.0` exposure introduced
this pass. Live e2e smoke through production `execute_local` after all
config edits: `run_task({"task_class": "lm2-closure-smoke", "objective":
"Reply with exactly the single word: pong", "requirements": {"capabilities":
["local-fast"]}})` -> `executed: true`, `output: "pong"`, `latency_ms: 2709`,
`deterministic_gate: pass`. No production Ollama model was pulled, removed,
or altered this pass beyond the one clean `qwen3.6:35b` pull; no systemd
unit touched; no code in `src/`/`core/` changed — only `config/models.yaml`,
`evals/local_models/{candidates.json,model_manifest.json}`, benchmark
results/artefacts, and this document.

## Blockers deferred to a future pass

- **The production Ollama version wall** (above) — the single blocker that
  determines whether any of this pass's positive evidence can ever bind.
  Genuine human-only action; not something this session can safely take
  unilaterally against a systemd-managed production service.
- Gemma 4 E4B/26B-A4B were both measured and rejected on merit this pass
  (not blocked) — no further action needed unless a future pass wants a
  different offload/context trade-off for 26B-A4B specifically.
- `code-fast`'s single-slot alias means `lfm2.5:8b`'s strong evidence has
  nowhere to bind even after the operator unblock, unless a future task
  either adds a second code-oriented alias or explicitly picks between the
  two on some criterion beyond raw pass-rate/latency (e.g. architectural
  diversity as a hedge, which was `lfm2.5:8b`'s original nomination
  rationale).

## Final HEAD

Committed to `dev`; see commit immediately following this file's addition
for the exact SHA (`git log -1`).

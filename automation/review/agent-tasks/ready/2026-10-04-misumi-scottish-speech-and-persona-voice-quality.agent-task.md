---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-04-misumi-scottish-speech-and-persona-voice-quality
title: "Benchmark and upgrade Misumi speech recognition and persona voices for real Glasgow household use"
status: ready
priority: high
task_type: evaluation
created_by: chatgpt
created_at: 2026-10-04T12:30:00+01:00
updated_at: 2026-10-04T12:30:00+01:00
executor: glm_flash
execution_mode: staged-loop
architecture: single-plus-verifier
architecture_rationale: "GLM Flash coordinates a local-first benchmark/evaluation loop; GLM handles bounded difficult implementation only where needed; Sol independently verifies claims and regression evidence. Misumi owns user/persona voice preferences and real-user acceptance; Odysseus owns ASR/TTS runtime selection, host/model routing, performance evidence and fallback behaviour."
single_agent_baseline: "One coordinator can prepare corpora, run local benchmarks, compare quality/latency/resource use, implement the chosen runtime route and persist evidence. Separate specialist agents are not required unless a bounded implementation problem justifies them."
execution_host: laptop
context_budget: medium
coordination_reason: "Speech quality spans real microphone capture, Glasgow/Scottish-English ASR, general-English regression, local GPU/CPU constraints, persona-specific TTS, fallback routing and physical kiosk acceptance."
requires_remote_compute: true
requires_local_model: true
requires_zotero: false
requires_mcp: true
requires_web: true
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - automation/review/**
  - config/**
  - docs/**
  - evals/**
  - routes/**
  - scripts/**
  - services/**
  - src/**
  - tests/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
inputs:
  - current tyecam1/odysseus@dev
  - current tyecam1/misumi@main
  - current home hardware: RTX 3070 8 GB, Ryzen 7 5800X, ~32 GB RAM
  - current Misumi ambient speech path and physical kiosk
  - current ASR/STT implementation and deployed models
  - current TTS implementation, :4500 compatibility path and persona voice mapping
  - user-provided or locally recorded consented speech samples
outputs:
  - reproducible Glasgow/Scottish-English ASR benchmark corpus and results
  - standard-English regression corpus and results
  - ASR route recommendation and production implementation
  - persona-specific TTS benchmark and voice-profile evidence
  - compute-aware TTS fallback route
  - physical kiosk acceptance record
  - integration into the persona-growth/background programme
result_path: docs/misumi-speech-quality-closeout.md
review_report_path: automation/review/misumi-speech-quality-sol-verification.md
handoff_model: gpt-5.6-sol
supersedes: []
duplicates: []
notes: "Activate as an early child of the persona-growth/background successor after the current convergence programme closes. Non-mutating benchmark preparation may proceed earlier if it does not interfere with current acceptance work. Do not park while a dependency-ready local benchmark or implementation packet exists."
---

# Misumi Scottish speech recognition and persona voice quality

## Objective

Make Misumi reliably understand the operator's natural Glasgow / Scottish-English speech and make spoken replies sound substantially more natural, characterful and enjoyable than the current lightweight baseline.

This work must optimize for the real household environment rather than public benchmark scores alone.

Two independent problems are in scope:

1. **ASR/STT:** what Misumi hears and transcribes.
2. **TTS:** how Misumi and its personas sound when replying.

Do not confuse the two during evaluation or closeout.

---

# Product target

The end-state should feel approximately like:

```text
natural Glasgow speech
    -> robust local ASR
    -> transcript with names/slang/technical terms preserved
    -> persona/team reasoning
    -> persona-specific expressive TTS
    -> spoken reply
```

with compute-aware fallback:

```text
GPU free
    -> preferred expressive ASR/TTS route

GPU busy / game active
    -> cheaper qualified route or CPU-safe fallback
    -> no user application is terminated automatically
```

The system should be measurably better than the current deployed baseline, not merely newer.

---

# 1. Build a real-user Scottish-English ASR corpus

Create a **local-only** evaluation corpus from consented recordings of the operator.

Initial target: roughly 15–30 minutes, expandable later.

Cover at least:

- natural conversational Glasgow speech;
- fairly standard English;
- fast connected speech;
- quiet / mumbled speech;
- far-field speech from realistic room distances;
- TV/music/background-noise conditions;
- questions and commands;
- interruptions / false starts;
- household-specific vocabulary;
- Scottish/Glasgow place names;
- persona names;
- Misumi/Odysseus terminology;
- PhD/technical vocabulary where appropriate;
- Scots words/phrasing that occur naturally.

Create hand-checked reference transcripts.

Raw audio:

- stays local;
- is never committed to Git;
- is not uploaded to external services without explicit operator approval;
- may be deleted after benchmark completion if not needed for future regression.

Store only corpus metadata, hashes, anonymized/sanitized fixtures and aggregate results in Git unless the operator explicitly authorizes more.

---

# 2. Keep a separate general-English regression set

A Scots-specialized model must not win simply by overfitting Scottish speech.

Maintain two primary evaluation buckets:

```text
A. Glasgow / Scottish-English natural speech
B. general / standard English
```

Also report specialist sub-buckets:

- names/proper nouns;
- technical vocabulary;
- far field;
- noisy speech;
- fast speech;
- Scots vocabulary.

A production candidate must either:

- materially improve bucket A while staying within an agreed regression tolerance on B; or
- be used as a conditional second-pass specialist rather than the universal default.

Do not silently "Scotsify" standard-English transcripts.

---

# 3. ASR candidate benchmark

Re-verify current availability, licences, runtime support and model versions immediately before downloading or benchmarking.

Candidate set should initially include, where still viable:

- current deployed Whisper/faster-whisper baseline;
- Whisper large-v3 / large-v3-turbo class;
- a current Scots-fine-tuned Whisper large-v3 candidate;
- Qwen3-ASR 0.6B;
- Qwen3-ASR 1.7B;
- NVIDIA Parakeet TDT 0.6B v3;
- TheWhisper / another strong current Whisper-derived candidate if still credible.

The list is provisional, not ratified. Replace stale candidates with stronger current equivalents if evidence justifies it.

## ASR metrics

Measure at least:

- WER overall;
- WER by corpus bucket;
- proper-name error rate;
- deletion / insertion / substitution breakdown;
- Scots-word accuracy;
- technical-term accuracy;
- punctuation usefulness where applicable;
- language hallucination rate;
- empty-output rate;
- latency: cold and warm;
- real-time factor;
- peak VRAM;
- peak RAM;
- CPU utilization;
- model load/unload time;
- failure behaviour under GPU contention.

Record exact artifact/version/runtime for every result.

## Routing experiments

Evaluate at minimum:

### Route A — one general model

One model handles all speech.

### Route B — fast-first escalation

```text
fast ASR
 -> confidence/quality check
 -> difficult/low-confidence utterance
 -> stronger ASR second pass
```

### Route C — Scottish specialist fallback

```text
general ASR
 -> likely Scottish / low confidence / anomaly
 -> Scots-tuned specialist second pass
```

Do not implement a language/accent classifier unless it demonstrably improves the result over simpler confidence/anomaly triggers.

---

# 4. ASR production-selection rules

The winner is selected by real-user evidence, not vendor claims.

Prefer the smallest route that clears the quality bar.

A Scots-tuned Whisper model may become:

- the default;
- a second-pass specialist;
- or rejected,

depending on measured performance on both Scottish and general-English sets.

If two routes are statistically/operationally close, prefer:

1. lower latency;
2. lower GPU contention;
3. simpler lifecycle;
4. better failure behaviour;
5. less model duplication.

No model is promoted solely because its public benchmark is better.

---

# 5. TTS / persona voice benchmark

Treat the current Kokoro route as the baseline, not the target.

Re-verify current model availability/licensing first.

Initial candidate families should include, where still viable:

- Kokoro baseline;
- Chatterbox Turbo / current Chatterbox equivalent;
- Qwen3-TTS 0.6B;
- F5-TTS;
- Orpheus-class expressive TTS where hardware allows;
- any clearly stronger current local candidate discovered during the benchmark.

Do not assume one engine must serve every persona.

## Voice identity principle

Do not clone living actors or performers without a suitable authorized/consented source.

Persona voices should be **character-inspired in behavioural qualities**, not unauthorized replicas of voice actors.

Target qualities include:

- cadence;
- energy;
- warmth;
- restraint;
- confidence;
- dry humour;
- expressiveness;
- pacing;
- emotional range.

---

# 6. Persona-specific voice profiles

Each active persona should eventually have a compact voice profile.

Examples of dimensions:

- pitch range;
- speaking pace;
- pause style;
- energy;
- warmth;
- formality;
- expressiveness;
- humour/dryness;
- confidence;
- emotional restraint;
- preferred nonverbal cues if supported.

Profiles must stay distinct from the canonical personality definition.

Illustrative targets to test rather than blindly ratify:

- Aoteru: composed, authoritative, calm;
- Kurisu: crisp, intelligent, slightly impatient;
- Sanji: animated, warm, playful;
- L: quiet, irregular rhythm, understated;
- Misato: relaxed, personable, warm;
- Erwin: deliberate, commanding;
- Ginko: soft, calm, measured;
- Jin: restrained, cool.

Persona voice changes should be evaluated blind where practical.

---

# 7. TTS evaluation

Use both objective runtime measurements and human listening evaluation.

Measure:

- time to first audio;
- total synthesis latency;
- cold/warm latency;
- peak VRAM/RAM;
- streaming capability;
- glitch/dropout rate;
- pronunciation of household/persona names;
- long-response stability;
- punctuation/prosody handling;
- concurrency with local LLM inference;
- behaviour while the GPU is busy.

Human ratings should cover:

- naturalness;
- intelligibility;
- personability;
- character fit;
- distinctiveness;
- emotional expressiveness;
- fatigue/annoyance over repeated listening;
- "would I want this persona speaking to me every day?"

Do not let one novelty demo dominate the selection.

---

# 8. Compute-aware TTS routing

Evaluate a route such as:

```text
GPU free
 -> expressive preferred engine

GPU constrained
 -> lighter qualified TTS

GPU unavailable / failure
 -> CPU-safe Kokoro or other proven fallback
```

Kokoro may remain valuable as a low-cost fallback even if it loses the quality benchmark.

Do not load several large TTS models simultaneously merely to preserve persona identity.

Prefer shared model + persona voice/profile switching where quality permits.

---

# 9. Integrate with automatic persona routing

This task is an early child of:

`2026-10-02-misumi-persona-growth-background-collaboration`

The automatic persona route plan should eventually select:

- lead persona;
- persona voice profile;
- TTS engine/profile;
- host;
- compute budget.

Speech quality evidence should feed the persona growth graph:

- pronunciation failures;
- disliked voice behaviours;
- successful expressive styles;
- user corrections;
- latency problems;
- persona confusion.

Do not make TTS engine choice part of persona canon.

---

# 10. Physical household acceptance

Synthetic audio is not sufficient.

Final acceptance must use the actual kiosk/microphone and realistic household conditions.

Minimum ASR acceptance:

1. operator speaks a held-out Glasgow/Scottish-English set naturally;
2. transcript is compared against reference;
3. proper names and technical terms are included;
4. far-field and moderate-noise trials are included;
5. the chosen route meets the agreed quality and latency floor;
6. general-English regression remains acceptable.

Minimum TTS acceptance:

1. actual kiosk plays each selected core persona voice;
2. at least several short and long responses are heard;
3. no duplicate playback;
4. no unacceptable delay;
5. voice remains intelligible from normal listening position;
6. operator rates whether each voice is genuinely preferable to Kokoro baseline;
7. at least one GPU-busy fallback trial is demonstrated.

---

# 11. Anti-overfitting and regression rules

Do not accept:

- a Scots specialist that materially damages ordinary English and is still made universal;
- a high-quality TTS model that makes the assistant too slow for conversation;
- a persona voice that is amusing once but tiring in normal use;
- a benchmark run only on clean close-mic audio;
- a model promotion without exact artifact/runtime provenance;
- a route that silently uses cloud inference when the test claims local;
- a route that competes with household gaming instead of yielding.

Every promoted route becomes a regression target.

---

# 12. Background execution

Once the persona-growth/background programme is active, this task should progress automatically when compute is idle.

Suitable autonomous packets:

- corpus preparation and validation;
- deterministic audio segmentation;
- local candidate download after resource/licence checks;
- benchmark sweeps;
- transcript scoring;
- error clustering;
- latency/VRAM measurements;
- candidate ranking;
- voice sample generation;
- blind sample packaging;
- implementation and unit tests;
- regression reruns.

Human-only gates:

- recording/approving personal speech;
- subjective voice preference scoring;
- physical kiosk hearing/acceptance;
- any use of third-party voice material requiring consent/rights judgment.

A human gate on one stage must not park independent benchmark work.

---

# 13. Deliverables

Produce:

- `evals/speech/` corpus schema and sanitized fixtures;
- reproducible ASR benchmark runner;
- ASR results with Scottish/general-English split;
- error-analysis report;
- selected ASR route with exact model/runtime evidence;
- reproducible TTS benchmark runner;
- persona voice profile schema;
- blind listening pack;
- TTS runtime/resource results;
- selected expressive + fallback route;
- integration tests;
- physical kiosk acceptance record;
- `docs/misumi-speech-quality-closeout.md`.

---

# Completion boundary

Complete only when:

1. current baseline has been measured;
2. Scottish/Glasgow and general-English sets are independently scored;
3. a Scots-specialized model has been explicitly tested for general-English regression;
4. the production ASR route is evidence-backed and locally deployable;
5. the selected ASR route is live on the real kiosk path;
6. multiple TTS candidates have been compared against Kokoro;
7. core personas have distinct evidence-backed voice profiles or a documented reason not to;
8. a compute-aware expressive/fallback TTS route is implemented;
9. gaming/GPU contention behaviour is truthful and non-destructive;
10. physical household acceptance is complete;
11. Sol independently reviews the benchmark design, promotion evidence and regression claims;
12. the resulting speech-quality evidence is linked into the persona-growth programme rather than left as an isolated benchmark.

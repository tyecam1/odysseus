---
title: Diagnose and improve live Misumi speech transcription quality
owner_target: odysseus
priority: high
status: open
created: 2026-10-17
updated: 2026-10-17
source: operator-reported live interface failure
---

# Diagnose and improve live Misumi speech transcription quality

## Problem and objective

On 2026-10-17 the operator reported very poor recognition while speaking close to the Misumi interface display. The visible TRANSCRIPT SAVED window shows repeated/implausible fragments such as "Okay. Alright. Okay. Yes ... Let's go ..." and "game is updated, just ...", rather than useful speech. This is an observed **end-to-end voice-input quality failure**, not proof that the STT model alone is at fault. The physical microphone may not be in the speaker location.

Restore intelligible, dependable speech capture/transcription on the **actual household interface box**, with evidence-based fixes to the smallest responsible layer.

## Scope and ownership

- Odysseus owns the live in-process local STT backend and `/misumi/transcript/audio` path. Inspect **live dev/deployment**, model and processing config rather than historical assumptions.
- Misumi owns box/browser microphone selection, capture/segmentation, `interface-box/misumi.html`, and the local `/transcript/audio` bridge. If a defect resides there, implement under Misumi repository authority and cross-link the fix; do not copy domain-specific runtime ownership into Odysseus.
- The retired Misumi standalone STT `:4600` server is **not** the production route. Existing `tyecam1/misumi/agent-tasks/inbox/voice-stt-whisper.md` documents the transition and unfinished model evaluation.
- Respect `tyecam1/odysseus/AGENTS.md` shipping-first priority; this is a user-reported correctness defect. Do not expand into unrelated voice architecture work.

## Bounded execution plan

1. **Baseline on the actual box.** Verify selected audio input device, physical mic location/orientation, mute state, meter levels, sample-rate/channel properties, WebRTC/browser capture settings, codec/container, and whether room/TTS playback leaks into input. Confirm runtime endpoint, model name/size/device/quantisation/language, STT logs, VAD/endpointing behaviour and audio segment duration. Do not infer from source-only tests that production matches.
2. **Localise the fault.** Use consented, ephemeral test utterances at close range and normal intended distance; compare mic-level/capture quality, source audio segmentation, transport/decode, and actual STT output. Include silence, background noise, conversational phrases, short commands, names, and speech during/after TTS playback. Distinguish wrong microphone, clipping/low gain, truncated chunks, speech detection, codec conversion, acoustic echo, and recognition-model errors. Never fabricate ground-truth transcripts.
3. **Make the smallest measured correction.** First fix wrong input device, mic placement/routing, capture constraints (evaluate echo cancellation, noise suppression, auto gain control), chunk boundary/VAD errors and format mismatches if evidenced. Only then benchmark local STT candidates/configurations (current model versus larger feasible Whisper/faster-whisper models, decoding, language and appropriate prompt/hotword bias). Avoid replacing a working pipeline or indiscriminate model upgrades.
4. **Replay and live-check.** Use identical consented test phrases before/after with separately labelled ambient and push-to-talk runs. Verify live interface text against reference and that Odysseus persists only the correctly acknowledged transcript. Compare quality against resource cost and time-to-text; provide rollback and configuration provenance.

## Acceptance evidence

- Record reproducible baseline and post-change **word error rate (WER)**, omissions, invented/hallucinated words, segment drop rate and end-of-utterance-to-text latency, split by close-range and intended operating-distance recordings, with at least 20 reference utterances per condition (or explicitly report if insufficient).
- Show a material reduction in recognition errors versus baseline without increased false transcript storage. Provisional quality targets to evaluate, not silently assert: WER <= 15% in a quiet close-range test and <= 25% at normal intended distance, with zero fabricated speech across at least 10 representative silence/noise/TTS-only probes. Where hardware cannot meet these targets, document the measured constraint and smallest viable remediation.
- Confirm UI-labelled input source is the actual selected microphone; capture and audio routing remain reliable after restart. Validate any capture/bridge change with the existing Misumi transcript tests and relevant Odysseus STT tests plus a live end-to-end proof.
- No raw microphone audio is durably stored, sent to cloud STT, committed, or included in logs. Any ephemeral listening/diagnostic clips require explicit consent and deletion after testing. Preserve mute, ambient-transcript consent/retention contracts and existing authority.
- Provide an operator-facing concise outcome: fault layer, root cause evidence, changed repo/commit, before/after metrics, deployed version or exact deployment blocker, and rollback. **Do not mark done** based only on simulation or a green unit test.

## Routing

Run the current `aoteru preflight` / estate preflight before implementation; use the cheapest verified adequate worker and relevant write lease. Initial investigation can be deterministic/local; escalate to a code-strong lane only if tests establish a harder defect. Review production evidence before closeout.

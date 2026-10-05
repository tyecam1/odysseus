# MISUMI_PROGRAMME — authoritative live queue (full roadmap)

Canonical queue for the Misumi/Odysseus long-horizon programme. Expanded 2026-10-05 (application -09 reconciliation): the previous terminal state (after -06..-08) applied only to the then-current executable queue and is explicitly superseded as *roadmap* completion — the full roadmap below restores every expected frontier. Distilled from the standing programme directive, the v4 registered prompt, `automation/review/misumi-long-horizon-programme-evidence.md`, the -06/-07/-08 traces, and the agent-task cards.

Rule of use: at each frontier reconcile live state, select by `user-visible value × leverage × evidence value × dependency reduction / risk × cost × uncertainty`, implement, test, merge under valid authority, deploy, exercise the real path, preserve failures, reconcile evidence, update this file, continue. Every item carries exactly one disposition: `complete` / `executable` / `dependency-blocked` / `operator-gated` / `household-gated` / `nature-gated` / `verification-debt` / `successor/rejected-with-rationale`.

## Completed foundations

- **-06 deterministic lead-persona routing** — `complete`. Chain proven live: utterance → contract → lead persona → UI leader state → trace (12/12 fixtures; releases through `ce8d353a8f`). PRs #92/#58/#93.
- **-07 governed persistent routing adaptation** — `complete`. Full causal chain live-proven incl. restart persistence and rollback; immutable evidence; reserved matters protected. PRs #94/#60/#95.
- **-08 repeated behavioural evidence + ratification surface** — `complete` with an explicit executable remainder split out as **-08b** below (the directive's own unproven-item checklist is honoured there; do not overclaim).

## Active queue (executable)

### -08b — residual ratification/adaptation proofs — `executable`
Unproven items from the -08 checklist, each small and testable: (a) silence/no-response must not promote — add the explicit test (an eligible candidate with no ratification act persists unchanged across restart); (b) contradictory-evidence handling exercised live on a labelled scratch instance (tests exist; live flow not yet run); (c) live reject-path exercise on scratch (tests + 404 live only); (d) conversational/user-facing proposal surface (persona asks the user to ratify an eligible candidate in dialogue, instead of API-only) — design with -12 embodiment, implement in the runtime first.

### -09 natural-language routing robustness — `executable` (IN PROGRESS)
The labelled router weaknesses (negation blindness, indirect phrasing, novel wording) become first-class experimental targets. Build the compact labelled corpus covering all ten directive categories (paraphrase, indirect, underspecified, competing cues, multi-intent, follow-ups, corrections, irrelevant-keyword injection, near-neighbour intents, unresolved/default); preserve the deterministic fixtures byte-identically; commission the GLM redesign reasoning; evaluate candidate algorithms strictly as *proposals* measured against the corpus — **the routing algorithm is ratified-contract behaviour (v0.1), so any algorithm change stops at the precise authority boundary** (contract amendment requires operator ratification). Base-vs-learned distinction maintained throughout.

### -10 bounded persona-state adaptation — `executable` (queued after -09)
Generalise the proven evidence/candidate/revision machinery to bounded persona state (response depth, technical depth, communication structure, intervention style, project familiarity, domain confidence, collaboration affinity, recurring-task familiarity). Immutable persona identity + foundational role contract never rewritten. Full chain per change: evidence → candidate → evaluation → authority → revision → observable behaviour → rollback. Required demonstration: before/after behaviour, restart persistence, rollback with history. Sol architecture challenge at closeout (or explicit debt).

### -11 dynamic multi-persona team formation — `executable` (queued)
Real collaboration on top of the existing deterministic consultation layer (`_consultation_plan`/`_consult_persona`): justified support selection, explicit handover, meaningful disagreement, coherent synthesis, structured per-persona contribution tracing, no-recruitment-when-unneeded. Required demonstration: measurable single-persona baseline vs multi-persona improvement or caught error. GLM-heavy coordination semantics; Sol judges value-vs-theatre.

### -12 embodiment and persona expression — `executable` (software parts) / `household-gated` (physical parts)
Software: support-persona visual state, handover transitions, `persona → voice profile → TTS` abstraction (decouple from Kokoro), restrained learned-state indication, conversational ratification UI (with -08b). Physical: realistic-environment STT, audibility, latency, speaker correctness, reboot/crash behaviour — `household-gated` until the kiosk bridge returns (B1).

## Blocked frontiers (each with its precise gate)

### B1 physical kiosk acceptance — `household-gated`
Box bridge (192.168.4.37:8770) unreachable at 2026-10-05 reconciliation (connection timed out; household pause in force). On return: canonical box-proxy verification + physical audio/latency/reboot acceptance (with -12).

### B2 runtime resilience — partially `complete`; remainder `executable`
Already proven live (-05): agent kill recovery, whole-service recovery, Ollama recovery, maintenance hold, three real reboots. Not yet proven: TTS failure/recovery drill, network loss/recovery, output-device change, degraded-state reporting from the box side. Queue as bounded drills on the home host.

### B3 security/console hardening — `operator-gated`
Blank-password restriction, idle lock, BitLocker, router/tailnet exposure review, unnecessary listeners. Decisions and posture details live in the private misumi repository. Do not break required embodiment for checklist compliance.

### B4 backup + restore — `operator-gated` (inputs: provider/path, public age recipient, permission to install `age`)
When inputs arrive: configure encrypted backup, verify it, then **prove an actual restoration**; record failure behaviour. A backup without restore testing is incomplete.

### B5 lab deployment — `operator-gated` (sudo on hz2-workstation)
Lab still `d2fc0bac32`; authoritative dev is `ffbef0d740` (re-resolve immediately before presenting). Unblocks the Sol lane (D1) and closes the multihost drift.

### B6 memory-policy reconciliation — `operator-gated`
Policy v0.2 uniformly "proposed for ratification with named gaps" (re-verified -07/-08: no contradictory markers). Behavioural-process routing state remains correctly separated from memory scope.

## Verification / reasoning debts (discharge when lanes return; never fabricate)

### D1 Sol review of -06/-07/-08 — `verification-debt` (blocked with B5)
Dispatch failed truthfully 2026-10-05: `ok:false`, `worker_failed`, `code-strong` unresolved on the stale lab backend. On B5: provide the accumulated evidence and request genuine retrospective challenge; repair substantive findings.

### D2 Sol at -09/-10/-11/-12 stage gates — `verification-debt` (conditional)
Required at consequential gates; attempt at each stage, carry explicit debt if the lane is down.

### D3 GLM heavy-reasoning lane — `verification-debt`
The dedicated heavier GLM lane is not a separately available actor in the current runtime; consequential reasoning this arc was validated by directive text, ratified contracts, deterministic tests and live proof. Attempt the lane for -09's redesign reasoning; record per-attempt outcomes.

### D4 Opus/v3 closeout (Opus synthesis + Sol #3 + closeout doc) — `verification-debt` (lane-gated)
Sequenced behind B1-B5 evidence per the v3 closeout contract.

### D5 longitudinal adaptation evidence — `nature-gated`
Repetition-derived candidates and persona-state learning need real household interaction over time; inspection endpoints are live (watch item).

## Other open PRs (not programme-owned)
#36, #39, #40, #42, #90, #91 (odysseus) predate/parallel this programme and are not merged without their own authority. Recorded, not actionable here.

## Done history
- -06, -07, -08: see traces 2026-10-04/05 in `evals/prompt-applications/misumi-long-horizon-programme/`; releases `a4851dbddd` → `ce8d353a8f`; PRs #92, #58, #93, #94, #60, #95, #96, #97, #98.

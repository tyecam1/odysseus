# MISUMI_PROGRAMME — authoritative live queue (full roadmap)

Canonical queue for the Misumi/Odysseus long-horizon programme. Expanded 2026-10-05 (application -09 reconciliation): the previous terminal state (after -06..-08) applied only to the then-current executable queue and is explicitly superseded as *roadmap* completion — the full roadmap below restores every expected frontier. Distilled from the standing programme directive, the v4 registered prompt, `automation/review/misumi-long-horizon-programme-evidence.md`, the -06/-07/-08 traces, and the agent-task cards.

Rule of use: at each frontier reconcile live state, select by `user-visible value × leverage × evidence value × dependency reduction / risk × cost × uncertainty`, implement, test, merge under valid authority, deploy, exercise the real path, preserve failures, reconcile evidence, update this file, continue. Every item carries exactly one disposition: `complete` / `executable` / `dependency-blocked` / `operator-gated` / `household-gated` / `nature-gated` / `verification-debt` / `successor/rejected-with-rationale`.

## Completed foundations

- **-06 deterministic lead-persona routing** — `complete`. Chain proven live: utterance → contract → lead persona → UI leader state → trace (12/12 fixtures; releases through `ce8d353a8f`). PRs #92/#58/#93.
- **-07 governed persistent routing adaptation** — `complete`. Full causal chain live-proven incl. restart persistence and rollback; immutable evidence; reserved matters protected. PRs #94/#60/#95.
- **-08 repeated behavioural evidence + ratification surface** — `complete` with an explicit executable remainder split out as **-08b** below (the directive's own unproven-item checklist is honoured there; do not overclaim).

## Active queue (executable)

### -08b - residual ratification/adaptation proofs - (a)(b)(c) `complete`; (d) `executable` (folded into -12)
Live-proven 2026-10-05 on a labelled scratch instance (release `ce8d353a8f`; evidence `automation/review/misumi-08b-live-proof-2026-10-05.md`): (a) an eligible candidate with no ratification act stays eligible/inert across a real process restart and further cue traffic (plus unit test `test_silence_never_promotes_an_eligible_candidate`); (b) a contradicting correction returns the candidate to shadow and promote is refused (409); (c) reject is terminal, re-reject and promote-after-reject refused (409), evidence preserved. Remaining: (d) conversational/user-facing proposal surface (persona asks the user to ratify an eligible candidate in dialogue instead of API-only) - design with -12 embodiment, implement in the runtime first.

**Defect found and fixed (2026-10-06, while designing -10):** in the -07 store an explicit durable instruction arriving after inferred corrections toward a *different* persona was filed as contradicting evidence (candidate -> `shadow`, unpromotable), silently ignoring the strongest evidence tier. Reproduced at store level, fixed so a durable instruction supersedes inferred proposals (earlier evidence kept, `superseded_proposals` recorded; authority model unchanged), regression test `test_explicit_durable_supersedes_conflicting_inferred_corrections`. Not yet deployed (home runs `ce8d353a8f`); deploy with the next runtime release.

### -09 natural-language routing robustness - non-mutating scope `complete`; activation `operator-gated` (B7)
Delivered 2026-10-05 (PR #100 merged, odysseus dev `62cbcc35ec`; not deployed because nothing runtime changed): labelled corpus `evals/misumi-routing/` (78 dev + 44 held-out items; ten directive categories + negation; `intended` = human label, never router output; held-out immutable by digest), evaluator `scripts/misumi_routing_corpus_eval.py`, failure taxonomy, candidate algorithm `src/misumi_routing_candidates.py` (proposal, NOT wired; a test asserts no runtime module imports it), 27 tests, and the amendment proposal `automation/review/misumi-routing-v0.2-amendment-proposal.md`. Measured (strict): baseline v0.1 dev 43/78, held-out 14/44; candidate dev 72/78, held-out 28/44; zero strict regressions; 12 deterministic fixtures identical. Preserved negative findings: dev->held-out gap 92%->64%, open-vocabulary failures (6 held-out), lenient regression c05, injection k05, near-neighbour q05. A real candidate bug (stemmer `notes`->`not`) was caught by the corpus and fixed with a regression test. Base routing and learned revisions stay distinct; learned cues stay on exact v0.1 matching under the recommendation.
Residual: **-09b** model-assisted classification for open vocabulary - `dependency-blocked` (GLM design reasoning + Sol review lanes unavailable; needs a third fresh held-out split).

### -10 bounded persona-state adaptation — `executable` (queued after -09)
Generalise the proven evidence/candidate/revision machinery to bounded persona state (response depth, technical depth, communication structure, intervention style, project familiarity, domain confidence, collaboration affinity, recurring-task familiarity). Immutable persona identity + foundational role contract never rewritten. Full chain per change: evidence → candidate → evaluation → authority → revision → observable behaviour → rollback. Required demonstration: before/after behaviour, restart persistence, rollback with history. Sol architecture challenge at closeout (or explicit debt).

### -11 dynamic multi-persona team formation — `executable` (queued)
Real collaboration on top of the existing deterministic consultation layer (`_consultation_plan`/`_consult_persona`): justified support selection, explicit handover, meaningful disagreement, coherent synthesis, structured per-persona contribution tracing, no-recruitment-when-unneeded. Required demonstration: measurable single-persona baseline vs multi-persona improvement or caught error. GLM-heavy coordination semantics; Sol judges value-vs-theatre.

### -12 embodiment and persona expression — `executable` (software parts) / `household-gated` (physical parts)
Software: support-persona visual state, handover transitions, `persona → voice profile → TTS` abstraction (decouple from Kokoro), restrained learned-state indication, conversational ratification UI (with -08b). Physical: realistic-environment STT, audibility, latency, speaker correctness, reboot/crash behaviour — `household-gated` until the kiosk bridge returns (B1).

## Blocked frontiers (each with its precise gate)

### B7 routing contract v0.2 ratification - `operator-gated` (created by -09)
The routing algorithm is ratified-contract behaviour. Exact action required from the user: ratify (or reject / amend) the v0.2 amendment in `automation/review/misumi-routing-v0.2-amendment-proposal.md` (algorithm + `routing.aliases` manifest field) and decide how learned-revision cues are matched (recommended: stay exact). Only then: wiring PR with kill switch `MISUMI_ROUTING_ALGORITHM=v0.1`, live proof of fixtures + corpus through `/misumi/respond`, Sol gate or recorded debt.

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

### D2 Sol at -09/-10/-11/-12 stage gates — `verification-debt` (conditional; -09 gate NOT discharged: lab stale `d2fc0bac32`, `code-strong` unbound, recorded 2026-10-05)
Required at consequential gates; attempt at each stage, carry explicit debt if the lane is down.

### D3 GLM heavy-reasoning lane — `verification-debt`
The dedicated heavier GLM lane is not a separately available actor in the current runtime; consequential reasoning this arc was validated by directive text, ratified contracts, deterministic tests and live proof. Attempt log: 2026-10-05 -09 - `aoteru route --capability glm` -> `ok:false`, `unknown alias 'glm'` (no GLM binding in the estate); `code-strong` -> no evidence-backed binding; `reasoning-strong` resolves to local `nemotron-3.5-lightning:30b-a3b` (NOT GLM; advisory only, ranked below tests): one critique run produced one useful point (record ignored meta text in provenance - adopted as `ignored_meta`) and otherwise generic risks. -09 design therefore rests on the measured corpus + deterministic tests, with GLM/Sol review carried as debt.

### D4 Opus/v3 closeout (Opus synthesis + Sol #3 + closeout doc) — `verification-debt` (lane-gated)
Sequenced behind B1-B5 evidence per the v3 closeout contract.

### D5 longitudinal adaptation evidence — `nature-gated`
Repetition-derived candidates and persona-state learning need real household interaction over time; inspection endpoints are live (watch item).

## Other open PRs (not programme-owned)
#36, #39, #40, #42, #90, #91 (odysseus) predate/parallel this programme and are not merged without their own authority. Recorded, not actionable here.

## Done history
- -06, -07, -08: see traces 2026-10-04/05 in `evals/prompt-applications/misumi-long-horizon-programme/`; releases `a4851dbddd` → `ce8d353a8f`; PRs #92, #58, #93, #94, #60, #95, #96, #97, #98.

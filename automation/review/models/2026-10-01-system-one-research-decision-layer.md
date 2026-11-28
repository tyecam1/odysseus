# System One research decision layer implementation evidence

**Status** Partial implementation. Zero promoted bindings. Acceptance and delivery are pending.

The worker started at `6ee3d361bcf3cf098a1aa83083dcdb8bcde81d72`, also the local `origin/dev` reference. That revision contained the owning card and the central estate router. The named result and verification artifacts and System One implementation were absent. The current controller run used `estate-queue-priority-execution@v2`.

## Authority and placement

- The live decision ledger showed active owner approval `dee0b118-c346-41a2-afb6-1d06a931f2a2` matching current scope digest `b23fe25aa10b671c1425a94373ab3f7dbbd8eecf76417632e249f671152821a9`. The controller dispatched write execution `c48c3d7b-f07b-4176-a48b-218639cc169f` on lab under existing lease `137bc1c9-ad4b-4f39-a17c-4bdfb25374c4`. The standalone CLI was missing, the checkout's thin client lacked a configured backend, and direct sandbox access to the lab API failed. The live controller record showed the existing governed dispatch, whose implementation path runs preflight before creating the execution. Subscription allowance levels for Codex, Claude, and GLM could not be established from this worker. There was no verified quota failure.
- **`protected_handoff`, hosted Jev evaluation.** The owner retains the decision to release the exact replay corpus for hosted processing and incur a bounded cost. The implementation approval covered the card's repository changes. The plan also stops before remote provider invocation. No authenticated Jev model or quota lookup and no inference request were made. Recheck when the owner has approved a specific dataset and evaluation budget.
- The independent reviewer and the human reviewer have distinct roles. The reviewer should inspect frozen implementation evidence for calibration, false confidence, leakage, fallback, tuner effects, and research authority. The owner retains the `V2_HUMAN_VERIFIED` acceptance and provider binding promotion decisions.

## Code delivered for review

- `src/system_one.py` defines a validated candidate space, Choice, Score, Noul, and native Rank. HTTP responses must identify the expected model and preserve the candidate set, score rubric, and probability distribution. The contract returns both a recommendation and a distribution. Its common confidence statistic is the selected candidate's probability. Provider-specific confidence figures are not used as a common calibration scale. Timed-out, rejected, mismatched, or unsupported responses have explicit outcomes.
- `src/estate_router.py` adds a trusted in-process research entry point on the central router. It checks host eligibility, placement, primitive, language, candidate count, request size, held-out quality and latency criteria before selecting a local adapter. It keeps the recommendation advisory and logs the existing routing decision row with the tuner, candidate-set hash, indexed probabilities, outcome, and optional verifier and human agreement. A missing or failed trace withholds the recommendation. High-consequence, conflicting and verification-required requests go directly to governed verification. Trace rows store no research text or private reasoning.
- `config/models.yaml` lists three individually discoverable and disableable adapter entries. All are disabled and the binding list is empty. Adapter checkpoint text is configured provenance. Runtime response validation checks the returned model name. A deployment still needs attestation that the server's configured name resolves to the checkpoint used for benchmark evidence. Hosted requests remain excluded from the central route.
- `config/system-one-tuners.yaml` has eight versioned scalars with contribution, red-team, and consolidation profiles. Deterministic derived behaviour affects advisory ordering and information-gain thresholds. Candidate recommendations stay within the caller's explicit response space and known next-action types. The interface has no mutation path for evidence ceilings, provenance, registered inclusion or stopping rules, claims or authorial Gates. Paper triage returns retrieval priority.
- Existing PhD decision summaries supplied eight development replay candidates with source and historical outcome references. They cover next action, triage, closest prior, claim ceiling, attribution, stopping, contract adherence, and best-of-N. The reconstructions need source-level adjudication before any become held-out cases. The scorer requires matching ordered candidate-set hashes and complete accounting across routes, rejects split overlap by research unit, and reports per-task accuracy, top-2, normalised Brier score, false confidence, abstention, latency, usage/cost, and corrections. Ineligible routes carry no scored distributions.

## Provider attestations and blockers

| Provider | Public contract | Worker observation for this execution |
| --- | --- | --- |
| Jev | Typed Choice, Score and Noul. Hosted authenticated endpoint. [TypeSafe API schema](https://api.typesafe.ai/openapi.json) | Protected handoff above. Access, concrete model, costs and calibration unmeasured. |
| CLM-8B | Typed endpoint plus native Rank. Local contrastive checkpoint with separate encoder. [CLM API and licence](https://github.com/Contrastive-LM/CLM#api-reference) | Reference port 8700 unreachable from the sandbox. No serving runtime or usable GPU attested for this worker. |
| Laya | Typed Choice, Score and Noul. Local HTTP service and CPU runtime documented. [Laya serving reference](https://github.com/NandhaKishorM/laya#self-hosting-http-server-jev-compatible), [checkpoint licence](https://huggingface.co/convaiinnovations/laya-typed-decisions) | Reference port 8000 unreachable from the sandbox. No local Laya serving runtime or checkpoint attested. |

A vendor result concerns that vendor's benchmark. No current estate provider/task binding is supported by it. Recheck local eligibility when the lab controller can attest installed runtimes, checkpoints, available resources, and reachable pinned endpoints. A paired run needs research-owner-adjudicated holdout cases and captures from all eligible routes, with a deterministic comparator and a qualified generative comparator where available.

## Verification and remaining acceptance

- The offline J1 development replay exercised 24 requests with the three shipped profiles. It yielded 15 governed-verification escalations and nine no-adequate-route results. No action was selected. This verifies the default handling and historical case wiring. It leaves comparative action quality and scientific correctness in a live J1 replay open.
- Tests, reconciled per suite by the controller (2026-11-28): test_system_one.py 8 passed; with the estate-router and models-config regression files 135 passed (the writer's earlier "145" figure is uncorroborated and is restated here per-suite).  The selected suites cover System One, estate routing, delegation preflight, card hygiene, HTTP authorization scope and task-envelope parsing. Controlled System One tests exercise native wire shape, redirect refusal, invalid responses, unsupported primitives, remote approval, a tuner-driven action change at unchanged probabilities, held-out eligibility filters, advisory authority boundaries, telemetry round-trip, and paired scorer validation. Provider responses in these tests are fixtures. The full HTTP route suite did not complete in this worker. Its first end-to-end request test also timed out in a clean archive of the baseline commit. `git diff --check` passed.
- Odysseus loaded the owning task's existing schema and scope. The card-hygiene check reported the existing `owner_gate_class_required` warning. The owner card was outside this worker's write scope. The PhD linter applies a different write-scope and host vocabulary and cannot certify this card.
- Remaining acceptance requires source-level adjudication of the replay cases, live native zero-shot benchmarks and calibration, reviewed evidence for at least two useful bindings, a bounded J1 benefit replay through a research caller, and independent and human verification. The research entry point currently has an offline replay caller. A production caller and batch, provider quota, runtime checkpoint attestation and cache-aware routing still need implementation and live qualification.
- Acceptance remains open. No merge, deployment, provider promotion, canonical research change, owner-card edit, or prompt trace was performed.

Run the offline development replay from the repository root:

```sh
DATABASE_URL=sqlite:///:memory: PYTHONPATH=. python -B evals/system-one/run_j1_preflight.py
```

## Independent review (Opus 5.5, 2026-11-28)

- VERDICT: APPROVE_WITH_CONDITIONS (cross-family to the Codex author; read-only; receipt in full at `automation/review/agent-tasks/review-receipts/REVIEW-opus-system-one-20261128.md`).
- No gate bypass found: the router addition is additive and fail-closed on every eligibility check; stock config is inert; hosted Jev is unreachable without remote authorisation; no secrets.
- Condition 1 (done in this revision): the test figure above is restated per-suite as controller-verified.
- Condition 2 (recorded as a standing rule): `reviewed`/`held_out_evidence` in `config/system-one-tuners.yaml` are self-attested. The FIRST binding change to that file must cite review evidence naming the change; until then the evidence fields carry no authority.
- Minor findings (recorded, none blocking): executor/host recorded for failed calls; choice ties hard-rejected in decode before the router's low-confidence tie path; rank abstention ignored; only ~12 of the eligibility branches covered by min-accuracy tests.

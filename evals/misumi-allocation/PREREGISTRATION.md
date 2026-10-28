# Persona-allocation shadow evaluation: pre-registration (2026-10-28)

Written before the candidate (`src/misumi_allocation_shadow.py`) existed and before any production output on the held-out corpus was
looked at. The held-out corpus is `corpus-heldout-v1.yaml` (SHA-256 below); the design corpus is `corpus-dev-v1.yaml`.

## Question

Does an evidence-triggered allocation proposal (solo / team / abstain / escalate, with the reason, eligible personas, required tool
authority and expected overhead) decide better than the ratified deterministic production path (`resolve_auto_lead` routing contract
v0.2 followed by `plan_team`), or than trivial baselines, on requests neither was designed against? "Better" is measured on the
allocation decision only. It is not a claim about answer quality, which needs live execution (Phase B, owed).

## Scope and non-scope

- Offline and deterministic: no model calls, no tool calls, no live routing change. The candidate returns a proposal and a trace.
- Persona identity is not competence and grants no authority. Required tool authority is derived from the request and capability
  registry, then only *checked* against the persona policy ceiling; it is never granted by the persona that was selected.
- Phase B (owed, not run here): answer correctness, specialist contribution, character fidelity and measured latency / model calls /
  tokens / retries / rework / human correction, using matched tasks, a blinded non-subject-family judge and a small human-audited
  sample, against solo, deterministic-tool, solo-plus-verifier and cheap-first plans. Nothing in this report supplies those quantities.

## Rubric for the expected decision (fixed before labelling)

- `abstain`: no ratified persona domain applies, so no specialist is eligible; Aoteru (the head interfacer) answers directly.
- `solo`: exactly one specialist domain applies, or a short follow-up inherits the previous lead; no second domain needs to check it.
- `team`: two distinct registered domains apply AND the request asks for a cross-check (compare, cross-check, reconcile, check against,
  contradict, clash, mismatch, "does ... match"), or the user names a second persona. Cross-checks inside one domain are `solo`.
- `escalate`: a reserved matter (standards, values, boundaries, ratification, Level 5/6), a privacy-sensitive capture or deletion
  involving other people, or an action whose required tool authority is beyond what the lead's ceiling allows (sending email, moving
  money, destructive deletion, covert recording).
- `expect.lead` lists acceptable leads; `expect.supports` lists acceptable supports. The labels are the author's own, made in the same
  session that built the candidate; an independent blinded relabel of the held-out prompts (non-subject model family, rubric only) and
  a human audit of a sample are owed and will be reported beside these numbers, with disagreements listed rather than hidden.

## Policies compared (same cases, same personas, same canon)

1. `production`: `resolve_lead` v0.2 + `plan_team`, mapped to a decision (reserved/escalation reasons -> `escalate`; lead fell back to
   Aoteru with no support -> `abstain`; supports -> `team`; otherwise `solo`). Production has no tool-authority concept (the runtime
   policy enforces it at execution), so authority cases are excluded from the production comparison and scored for the candidate only.
2. `always_solo`: the specialist lead alone, never a team.
3. `max_team`: every justified-by-edge support up to the cap.
4. `candidate`: the shadow allocation proposal.

## Metrics (all on the held-out corpus, n = 50 independent prompts; prompts are not clustered, so a paired bootstrap over cases is used)

- A1 team-axis accuracy: correct on "team vs not-team".
- A2 four-way decision accuracy: solo / team / abstain / escalate.
- A3 lead accuracy (a lead in `expect.lead`), reported but not a gate.
- S1 safety floor, candidate only: every `reserved_tool` case must be `escalate`; no support may be proposed on a reserved matter;
  required authority must be identical whichever persona leads (checked by test).
- C1 overhead: proposed extra model calls (1 per support) against production's on the same cases.

## Acceptance for any step beyond shadow mode (all must hold; failing is a legitimate result)

- A1: candidate not worse than production (paired 95% interval lower bound above -5 points).
- A2: candidate better than production by at least 10 points with the paired 95% interval excluding zero.
- S1 holds in full. C1: candidate never proposes more supports than production unless a persona is named.
- Phase B has run on at least 20 distinct tasks with a non-subject-family blinded judge. This PR cannot satisfy that, so this PR can never
  promote the candidate: the strongest outcome here is "shadow trace retained".

## Held-out discipline

The held-out corpus is evaluated once, after the candidate is frozen against the dev corpus only. If any change is made after seeing its
result, those cases become design data and a new held-out v2 is required. The result is reported whatever it is.

## Seed and method

Bootstrap seed 1, 2000 resamples (the corrected `src/efficiency_pareto.py` analyser), percentile 95% interval, paired over cases. Every
case is its own cluster here, so the flat and hierarchical bootstraps coincide; the distinct-case count is the evidence floor (20).

## Amendment 1 (2026-10-28, after the dev run, before the held-out run)

The rubric omitted the ratified consult-edge rule (contract rule 5): a support may be recruited only along the lead's `consults` edges
(Aoteru as head excepted), and `plan_team` enforces it. Where a cross-check is wanted but no edge exists (for example `kurisu` and `misato`
do not consult each other) the correct decision is `solo`, with the excluded second domain recorded in the trace. Two dev labels were
corrected for this. Two held-out labels (`h-res-4`, `h-anom-7`) have the same defect; the frozen file is NOT edited, its hash stands, and
the report gives the as-frozen reading (the pre-registered one) and a sensitivity reading with those two amended to `solo`.

## Held-out corpus hash

`corpus-heldout-v1.yaml` SHA-256: 1f1b9808cad4ed1938d66b0ff274828af0da9d741f06b4f9bec6570ef74884e2

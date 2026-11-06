# Sol packet batching: calibration and paired-replay protocol (proposed, unratified)

Status: **design proposal, not run, not approved.** It answers what must be true before the packet wiring merged in #220 may leave its inert state, using the evidence collected so far (`2026-11-04-sol-fragmentation-baseline.md`, `2026-11-06-sol-call-classification.md`, `2026-11-06-sol-packet-size-stress.md`, `system-efficiency/2026-11-06-usage-attribution-diagnosis.md`). The design below is the substance of a read-only gpt-6.1-sol consult on 2026-11-06 (budget: one script of at most 250 lines plus one evidence document; no new table, scheduler or subsystem), condensed and organised here by Claude Sonnet 5.5. Nothing here has been independently reviewed beyond that consult.

**Standing conclusion: keep batching inert.** Current evidence cannot establish that batching preserves quality or saves calls: the baseline has token and template figures but no per-call subject or reviewed head, 98% of calls are review-class under 7 templates, and no outcome record links a Sol decision to a later correction.

## 1. Calibrating the Policy fields

| Field | How it is set | Source |
|---|---|---|
| `wrapper_overhead_tokens` | maximum tokenised compiler-envelope overhead | exact prompts and request-level token counts in rollouts, joined to the `\|call=` identity |
| `headroom_tokens` | maximum positive sizing error plus an owner-set safety margin | same |
| `min_net_reuse_tokens` | p10 of positive net reuse among pilot packets that demonstrated savings | pilot packets |
| `max_input_tokens`, `max_output_tokens` | quality-passing pilot envelope, capped by explicit owner-attested runtime ceilings (historical successes cannot establish hard limits) | pilot; owner |
| `max_items` | owner-set **2**, subject to replay passing | owner |
| `max_wait_seconds` | owner-set **0** (only already-prepared items in one request) | owner |
| `wait_benefit_lower_bound`, `urgency_cost_upper_bound` | conservative measured input saving; owner-set zero for added accumulation delay, in the same units. Positive waiting needs separate evidence | pilot; owner |
| `role_equivalence` | owner-governed identity only; templates cannot establish equivalence | owner |
| `evidence_version` | immutable commit or hash of the evidence document, covering policy, compiler and dataset identities | evidence doc |

`EstateExecution` gives write-execution provenance and timing, not advisory-review quality. GitHub PR and CI history gives candidate corrections and confirmed defects.

## 2. Paired replay (feasible form)

- **Selection:** deterministic, stratified by template, size and confirmed defects, from reconstructable historical review calls. Require the exact reviewed head, an identical versioned shared context, the same repo, parent and protocol, and evidence of non-contamination. Exclude mandatory separate-context checks. Freeze the policy after a small pilot.
- **Pairing:** replay each eligible two-item packet both as two fresh single calls and as one batch, with identical evidence and the same resolved current model and effort. Withhold later outcomes from the model.
- **Scoring:** independent and blinded, from human-confirmed corrections, reproducible CI failures and later confirmed defects. A PR merged unchanged is not proof of correctness; unexplained edits stay "unknown".
- **Size and stop:** about 60 independent parent or subject clusters (roughly 120 decisions); at most 200 launches and a preregistered token budget. Stop on a consequential regression or when the budget is exhausted; too few eligible cases means **inconclusive**, not pass.

## 3. Activation gate

All must hold before batching leaves inert, and the activation is recorded as the `evidence_version`:

- 100% identity and result attribution, zero independence violations, no additional P1 misses.
- A one-sided 95% upper bound on batch-only quality loss below 5 percentage points (60 independent clusters with zero losses meet that bound).
- At least 20% fewer calls per accepted decision, no increase in tokens per accepted decision including retries, and no deadline violations.
- Independent verification of the evidence, then owner approval of the evidence version.
- **Rollback** on any additional confirmed consequential miss, an independence breach, or an exceeded capacity bound.

## 4. Collect now (cannot be reconstructed later)

1. Dispatch subject, head and launch identity: already recorded in the `|call=` rows once the lab runs #225/#226/#227 and callers pass `--subject` and `--head-sha` (blocked on the lab deploy).
2. The exact prompt and context snapshot, output and usage, kept in the existing rollouts, with join pointers in the evidence document.
3. Confirmed correction or defect links, recorded in the evidence document and referencing GitHub history.

## 5. Human decisions (genuinely required, later)

Approve the bounds and safety margin, the quota cap for the replay, and the activation; adjudicate ambiguous outcomes. None is needed to begin collecting data.

## 6. Top review risks

False joins between calls and outcomes; contaminated independence between paired arms; outcome labels biased in ways that mask missed defects.

## Open dependency

Nothing above can start until the lab backend runs #225/#226/#227 (the recorded deploy decision) and review callers pass subject and head. Until then, the usable offline work is limited to this protocol.

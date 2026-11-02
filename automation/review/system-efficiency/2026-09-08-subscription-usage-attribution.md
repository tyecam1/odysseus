# Subscription usage attribution — stage 1-2 baseline (PARTIAL)

Task: `2026-09-08-subscription-usage-attribution-for-continuous-system-improvement`
Status: **partial**. Telemetry discovery and a laptop-side token baseline are done. Function-level attribution, the ranked diagnosis, routing recommendations and the independent Sol review are **not** done and remain owed.
Observed: 2026-11-02 ~13:40Z, laptop control-plane only. Produced with Claude Sonnet 5.5; no Sol, Codex or GLM pass has reviewed this.
Method: read-only aggregation of numeric fields from local transcripts; no message content, credentials or account identifiers read or recorded. The aggregation scripts are small enough to reproduce from the field names below.

## 1. Telemetry discovery

| Provider | Source | Signal | Granularity | Window / reset | Machine-readable | Auth burden | Attribution suitability |
|---|---|---|---|---|---|---|---|
| Claude (laptop) | `~/.claude/projects/**/*.jsonl` | per-call `message.usage` (input, output, cache write, cache read), model, timestamp, requestId | per API call | none: **no allowance or percent-remaining signal** | yes | none | high for tokens per call/day/model/project; **none for % of allowance** |
| GLM via `claude-glm*` wrapper (laptop) | same transcripts, model `glm-5.3` / `glm-5.3-flash` | per-call tokens | per API call | none | yes | none | high for tokens; allowance unknown |
| Codex (laptop app) | `~/.codex/sessions/**/*.jsonl` `token_count` events | cumulative session tokens and `rate_limits` (`used_percent`, `window_minutes`, `resets_at`, credits) | per turn | 300-minute and 10080-minute windows, provider-stated reset time | yes | none | high for tokens and window %; per-function attribution needs session-to-function mapping |
| Codex (lab) | not read in this pass | n/a | n/a | n/a | n/a | n/a | **open**: the laptop reading may be a different account from the lab's |

Observations are single-host. Estate-side usage on lab and home is not covered.

## 2. Claude and GLM token baseline (laptop, 2026-10-02 to 2026-11-02)

22,547 unique API calls across 1,149 transcript files, de-duplicated on message id plus request id. Token counts are exact per call. Native provider units are not comparable across providers and are not compared here.

| Model | Calls | Input | Output | Cache write | Cache read |
|---|---:|---:|---:|---:|---:|
| claude-sonnet-5-5 | 12,324 | 26 k | 11.66 M | 76.9 M | 4,827 M |
| glm-5.3-flash | 6,119 | 26.8 M | 2.59 M | 0 | 597 M |
| glm-5.3 | 2,260 | 18.2 M | 4.29 M | 0 | 130 M |
| claude-opus-5-5 | 1,328 | 2.7 k | 61 k | 20.8 M | 269 M |
| claude-haiku-5-5 | 88 | 0.2 k | 3 k | 1.6 M | 5.7 M |
| other (opus-4-8, sonnet-4-6) | 15 | 18.6 k | 55 k | 0.6 M | 0.9 M |

Findings (high confidence on counts, **low confidence on any allowance interpretation**):
- Sonnet 5.5 is 55% of calls and by far the largest consumer of cache reads. The workload is long-context coordination sessions.
- Opus 5.5 is 6% of calls but carries 21 M cache-write tokens, about 15.6 k per call. Opus use is infrequent but each call re-primes a large context.
- GLM (both variants) is 37% of calls, so GLM carries a large share of delegated volume. Its input-token totals are far larger than Claude's because it is not cache-reported.
- Daily call volume ran from 86 to 2,729 on days with substantial activity (peak 2026-10-26). What drove the peaks was not examined: no transcript content was read.
- By project directory, about half of calls come from the control-plane home directory and about a third from the PhD notes repository.

## 3. Codex quota state (provider-stated, laptop account)

Latest populated reading, event timestamp 2026-11-02T10:50:02Z:
- 5-hour window: **99% used, resets 2026-11-02T14:47:28Z**.
- Weekly window: 15% used, resets 2026-11-09T09:47:28Z.
- Credits: none (`has_credits: false`, balance 0).

Confounders: the reading is about 2 h 50 min old at time of writing; the window reset time is fixed by the provider but usage since 10:50Z is unknown. It is the laptop Codex account and may not be the account the lab worker uses. Per-day Codex token totals in the rollouts are cumulative per session and have gaps (no 10-31 or 11-01 rollouts), so they are not reported as a trend.

## 4. Open work (not done)

1. Read the lab's Codex telemetry and confirm whether it shares this account and window.
2. Recover the recurring-function taxonomy from repository activity and map sessions to functions.
3. Bounded before/after attribution for one representative function (not done; none of this baseline is function-level).
4. Ranked diagnosis, routing/cadence/batching recommendations and a minimal telemetry schema.
5. Independent Sol review of the final report (handoff model in the task contract). Owed; not run.
6. Claude allowance percent-remaining has **no local source**; a provider usage surface or connector would be required (browser fallback only per the task's hierarchy, with manual operator authentication).

# Lab Codex telemetry (partial)

Closes the "Codex (lab): not read in this pass" row of `2026-09-08-subscription-usage-attribution.md`. It is **partial** and says so below. Numeric fields only were read; no message content was read or is reproduced.

## Method

The same numeric-only script as the laptop baseline (`2026-11-04-sol-fragmentation-baseline.md`) ran on the lab over `~/.codex/sessions/**/rollout-*.jsonl` (model from `turn_context`, final `token_count` totals, `rate_limits` samples). Sampled once on 2026-11-06. The rollout files stay on the lab; only the summary figures are committed.

## Results (lab `~/.codex`, 2026-03-23 to 2026-11-02)

| Measure | Value |
|---|---|
| Rollouts | 264; Sol-class 259 (`gpt-6-sol` 139, `gpt-5.6-sol` 64, `gpt-6.1-sol` 55, `gpt-6-1-sol` 1), other 5 |
| Busiest days (last 10 active) | 10-26: 74, 10-21: 33, 10-27: 27, 10-29: 25 |
| Input tokens, total | 174.0 M, 92% cached (14.4 M uncached) |
| Output tokens, total | 1.76 M |
| Uncached input per session | p25 38.5 k, median 59.1 k, p75 78.0 k, p90 101.4 k |
| Output per session | p25 4.0 k, median 7.0 k, p75 10.0 k, p90 14.0 k |
| Sessions with output under 500 tokens | 7 (3%) |

Every Sol-class rollout is a single-turn `codex exec` invocation (no multi-turn sessions), as on the laptop. Per call, the lab uses about twice the uncached input of the laptop (median 59 k vs 29.6 k) and about 1.5 times the output (7.0 k vs 4.7 k); the 3% near-empty share is the same.

## Which account

The newest lab `rate_limits` sample (2026-11-02T09:26Z) has a 5-hour window resetting 13:40Z and a weekly window resetting 2026-11-05T17:07Z. The newest laptop sample (2026-11-06T07:00Z) has a weekly reset at 2026-11-11T16:03Z. Weekly windows are fixed-length, so a reset 17:07Z on 11-05 would imply 11-12 on the following cycle, not 11-11 16:03Z. This is **consistent with the lab using a different account or plan anchor than the laptop**, but it is not proof (the samples are four days apart and a plan change would also move the anchor). Credentials were not read or compared.

## Gaps

- The lab rollouts stop on 2026-11-02 although governed lab Codex runs continued afterwards (the lab `codex` is 0.116 at `/usr/bin/codex`; runs use `/home/agent/.local/bin/codex`, apparently with a separate or non-persisted session store). So this is **not current**: usage after 11-02 is unmeasured here.
- No per-function attribution, no call classification, and no reading of which calls share context; those items in the attribution task remain owed, as does its independent Sol review.
- Limit hits are not in rollouts as numbers; the stated reset texts are in the queue checkpoint instead.

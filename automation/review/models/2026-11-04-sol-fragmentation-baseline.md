# Sol call-fragmentation baseline (partial, laptop rollouts)

First measurement toward the `2026-10-01-sol-packet-efficiency` acceptance criterion "recent Sol usage has a quantified fragmentation baseline". It is **partial** and says so below.

## Method

Numeric fields only were read from the laptop's Codex rollouts (`~/.codex/sessions/**/rollout-*.jsonl`): the model name from `turn_context`, and the final `token_count` totals of each rollout. No message content was read or is reproduced here. One rollout is one `codex exec` invocation; per-call tokens are the rollout's last `total_token_usage`. Sampled once on 2026-11-04. The rollout files are local to the laptop and are not committed, so only the summary figures below can be checked from the repository.

## Results (2026-10-25 to 2026-11-04, laptop account)

| Measure | Value |
|---|---|
| Rollouts | 639, all `gpt-6.1-sol` |
| Active days / busiest days | 8 / 224 (10-29), 172 (10-27), 123 (11-02) |
| Input tokens, total | 497.8 M, of which 94% cached (27.5 M uncached) |
| Output tokens, total | 4.13 M |
| Uncached input per call | p25 23.7 k, median 29.6 k, p75 38.1 k, p90 50.7 k |
| Output per call | p25 3.3 k, median 4.7 k, p75 6.0 k, p90 7.9 k |
| Calls with output under 500 tokens | 17 (3%) |

## What this does and does not show

- Calls are not trivially tiny: a typical call carries about 30 k uncached input and returns about 4.7 k output, and only 3% are near-empty. Fragmentation is therefore **not** the "many near-empty calls" shape; the open question is how much of each call's uncached input is context shared with neighbouring calls.
- Uncached input per call is about six times the output. That ratio is consistent with the task's hypothesis (repeated setup/context cost per call) but does not prove it: the rollouts do not say which input was shared.
- Calls cluster in bursts (three days account for 519 of 639), which is the pattern in which a bounded accumulation window could group compatible work.

## Not measured (still owed)

- Classification of each call (unavoidable single decision / combinable / repeated unchanged verification / reconstruction overhead / polish / necessary independent review / failed). This needs reading call purpose, which these numeric fields do not give.
- Lab and home Codex usage (the lab worker may use a different account); only this laptop is covered.
- Shared-context token share between adjacent calls, and the realistic upper bound on call reduction.
- Accepted decisions per call, defect detection and correction rates (need the outcome records).

Treat any call-reduction figure as unmeasured until the classification is done.

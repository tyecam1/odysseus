# -11 evaluation v2 — results (2026-10-06)

Pre-registration: `PREREGISTRATION.md` (merged before any data). Raw replies, verdicts, the 48-row audit and every analysis output are in `data/`.
Scripts: `collect.ps1` (collection), `judge.py` (blind judging), `analyse.py` (pre-registered rule), `compare3.py` (four-condition follow-up).

## Design as run

8 conflict/clean prompt pairs (a planted conflict, and a clean twin with the conflict removed), N=12 per prompt per condition = 192 replies per
condition, interleaved in a fixed-seed shuffled order through a scratch `:1420` instance (production untouched, persistence off).
Detection = the reply explicitly flags the planted issue (conflict prompts). False alarm = the reply flags an issue or raises an unfounded concern on a
clean prompt. Intervals: Wilson 95% (rates), paired bootstrap over task x run cells (differences).

Conditions: `solo` (MISUMI_CONSULT=0); `team` (the pre-fix behaviour: the lead sees every support contribution, including `OK:` text);
`teamfix` (#115: an `OK:` contribution is summarised to the lead as "no issue found"); `teamdrop` (#116, release f75eb723a8: an `OK:` contribution is dropped
from the lead's input; `RISK:` and unmarked contributions pass through).
`teamfix` and `teamdrop` are **post-hoc follow-ups** aimed at a mechanism the pre-registered comparison exposed. They were measured on the same task set,
so they are not independent confirmation and carry selection risk (a variant chosen after seeing data).

## Deviations from the pre-registration (all disclosed, none hidden)

1. **The pre-registered primary judge (Nemotron via aoteru `reasoning-strong`) was infeasible**: cold-load 502 timeouts and about 150 s per row. The partial output is kept
   (`judged-nemotron-ABANDONED-partial.jsonl`, 24 rows) and is not used.
2. **llama3.1:8b (independent family) was substituted as primary, and proved unreliable**: against a stratified 48-row AI audit of the replies it agreed 58% of the time, versus 94% for
   qwen3:8b (`audit-48.json`). The audit labels are an AI reading, not human labels. So the more accurate judge is the same-family qwen3:8b, whose independence from the
   subject model is the thing the pre-registration wanted to avoid. Both are reported; **qwen3:8b is the better-validated one, llama3.1:8b is shown for transparency.**
3. Inter-judge agreement is poor (kappa 0.34 for flags_issue, 0.14 for unfounded_concern), so every conclusion is capped at **indicative**.

## Pre-registered comparison (solo vs team) — verdict stands

`SENSITIVITY GAINED AT THE PRICE OF FALSE ALARMS (not a net improvement)`, capped at indicative (`data/analysis-preregistered-rule.txt`).
Under qwen3:8b: detection 97% vs 89% (+8.3 points, CI +1.0 to +16.7) but false alarm on clean requests 43% vs 0% (+42.7 points, CI +33.3 to +53.1).
Under llama3.1:8b: detection 44% vs 18%, false alarm 82% vs 54%. The audit agreed on direction: 4/12 team clean replies were false alarms against 1/12 solo.
The supports themselves were not the source: they opened `RISK:` on 0/96 clean prompts. The lead relayed the caveat padding in `OK:` contributions as warnings.

## Follow-up: four conditions (`data/analysis-four-conditions.txt`)

| condition | qwen3:8b detection | qwen3:8b false alarm | llama3.1:8b detection | llama3.1:8b false alarm | median latency |
|---|---|---|---|---|---|
| solo | 89% (81-93) | 0% (0-4) | 18% | 54% | 3.3 s |
| team | 97% (91-99) | 43% (33-53) | 44% | 82% | 4.3 s |
| teamfix (OK summarised) | 75% (65-83) | 0% (0-4) | 32% | 41% | 4.0 s |
| teamdrop (OK dropped) | 93% (86-96) | 1% (0-6) | 31% | 48% | 4.6 s |

Paired differences, teamdrop, qwen3:8b: vs solo detection +4.2 points (CI -4.2 to +12.5), false alarm +1.0 (CI 0.0 to +3.1); vs team detection -4.2 (CI -10.4 to +1.0), false alarm -41.7 (CI -51.0 to -32.3);
vs teamfix detection +17.7 (CI +7.3 to +28.1). llama3.1:8b: vs solo detection +13.5 (CI +4.2 to +24.0), false alarm -6.2 (CI -15.6 to +3.1).

## Reading

- `teamfix` was worse than solo on detection (-13.5 points, CI -24.0 to -4.2, qwen3:8b): a support that misses about half the real conflicts (it opened `RISK:` in 46-50% of conflict consults) and then
  tells the lead "no issue found" reassures the lead out of noticing a conflict it would have caught alone. Reassurance is a harm of its own.
- `teamdrop` removes the false-alarm cost (1% vs 0% solo, within the pre-registered +5 point limit) without that reassurance, and on both judges is at least as good as solo on detection.
- **It is not shown to help.** Under the pre-registered bar (detection up at least 15 points with a CI excluding 0) it fails under qwen3:8b (+4.2, CI spans 0). llama3.1:8b meets the interval but not
  the 15-point bar (+13.5) and is the less reliable judge. The honest claim is: **no measurable harm, a small and unproven detection gain, about one extra second of latency.**
- A support that finds a real problem does add value only about half the time it is relevant; its recall (46-50%) is the limiting factor, not the lead's synthesis.

## Limits

One model family under test (qwen3:8b); 8 task pairs authored by the same session that built the feature; judges are small local models validated against an AI audit, never a human;
post-hoc variants on the same tasks; no frontier-model judging (Sol, GLM and Opus are unavailable and are carried as debt). Treat all numbers as indicative.

## Decision

`teamdrop` (#116) is the evidence-best variant and is the behaviour on dev. Specialist-lead teams stay available (`MISUMI_CONSULT=0` still disables them), with no claim that they improve answers.
A frontier-model re-judge and a human audit of a sample are the next evidence steps when Sol or the lab returns; this evaluation is the first priority retrospective review (with -10).

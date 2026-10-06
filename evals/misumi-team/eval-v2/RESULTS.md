# -11 evaluation v2 — results (2026-10-06)

Pre-registration: `PREREGISTRATION.md` (merged before any data). Raw replies, verdicts, the 48-row audit and every analysis output are in `data/`.
Scripts: `collect.ps1` (collection), `judge.py` (blind judging), `analyse.py` (pre-registered rule), `compare3.py` (four-condition follow-up).

## Design as run

8 conflict/clean prompt pairs (a planted conflict, and a clean twin with the conflict removed), N=12 per prompt per condition = 192 replies per
condition, interleaved in a fixed-seed shuffled order through a scratch `:1420` instance (production untouched, persistence off).
Detection = the reply explicitly flags the planted issue (conflict prompts). False alarm = the reply flags an issue or raises an unfounded concern on a
clean prompt. Intervals: Wilson 95% (rates), paired bootstrap over task x run cells (differences) - **the cell bootstrap is superseded for the differences, see "Correction" below.**

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

## Pre-registered comparison (solo vs team)

**Superseded label - see "Correction".** As first reported (flat-cell bootstrap): `SENSITIVITY GAINED AT THE PRICE OF FALSE ALARMS (not a net improvement)`, capped at indicative (`data/analysis-preregistered-rule.txt`).
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

- (Flat-cell interval; **not established under the hierarchical interval, see "Correction"**.) `teamfix` was worse than solo on detection (-13.5 points, CI -24.0 to -4.2, qwen3:8b): a support that misses about half the real conflicts (it opened `RISK:` in 46-50% of conflict consults) and then
  tells the lead "no issue found" reassures the lead out of noticing a conflict it would have caught alone. (Hypothesis: reassurance may be a harm of its own; not established, see Correction.)
- `teamdrop` removes the false-alarm cost (1% vs 0% solo, within the pre-registered +5 point limit) without that reassurance; on detection no difference from solo is established (see Correction: the hierarchical intervals are compatible with both a small loss and a gain).
- **It is not shown to help.** Under the pre-registered bar (detection up at least 15 points with a CI excluding 0) it fails under qwen3:8b (+4.2, CI spans 0). llama3.1:8b (the judge in the registered primary slot) gives +13.5, below the 15-point bar, with a hierarchical CI of -5.2 to +37.5.
  The honest claim is: **no harm established on this task set (the detection interval against solo is compatible with a loss and with a gain), no benefit shown, about one extra second of latency.**
- Hypothesis, not a finding: a support that finds a real problem adds value only about half the time it is relevant (recall 46-50%), so its recall, not the lead's synthesis, may be the limiting factor. This design does not isolate that mechanism (it would need a factorial or contribution-level analysis).

## Correction (2026-10-06, after the independent Sol review)

The pre-registration says the 95% intervals for differences use a "paired bootstrap (resampling tasks and runs)". `analyse.py` and `compare3.py` resampled the flat list of 96 task x run cells as independent, so the 12 repeated runs of one task counted as 12 pieces of task evidence although there are only 8 tasks. That understates uncertainty. `reanalyse_hierarchical.py` resamples tasks, then runs within each chosen task (paired across conditions); its full output is `data/analysis-hierarchical.txt`, and the original outputs are kept unchanged. Point estimates do not change; the intervals do.

| comparison (qwen3:8b) | point | flat-cell CI (original) | hierarchical CI (pre-registered reading) |
|---|---|---|---|
| detection, team - solo | +8.3 | +1.0 to +16.7 | **-6.2 to +26.0** |
| false alarm, team - solo | +42.7 | +33.3 to +53.1 | +17.7 to +67.7 |
| detection, teamdrop - solo | +4.2 | -4.2 to +12.5 | -5.2 to +16.7 |
| false alarm, teamdrop - solo | +1.0 | 0.0 to +3.1 | 0.0 to +4.2 |
| false alarm, teamdrop - team | -41.7 | -51.0 to -32.3 | -67.7 to -16.7 |
| detection, teamfix - solo | -13.5 | -24.0 to -4.2 | **-36.5 to +8.3** |
| detection, teamdrop - teamfix | +17.7 | +7.3 to +28.1 | **-3.1 to +42.7** |
| detection, teamdrop - solo (llama3.1:8b) | +13.5 | +4.2 to +24.0 | -5.2 to +37.5 |
| detection, team - solo (llama3.1:8b, registered primary slot) | +26.0 | +14.6 to +36.5 | +9.4 to +43.8 |
| false alarm, team - solo (llama3.1:8b, registered primary slot) | +28.1 | +15.6 to +40.6 | 0.0 to +60.4 |

What changes in the conclusions:

- **The verdict depends on which judge is read, and the earlier prose quoted the wrong one.** The pre-registered decision rule applies to the PRIMARY judge. The registered primary (Nemotron) was infeasible, so llama3.1:8b was substituted into the primary slot (`data/analysis-preregistered-rule.txt` labels it PRIMARY, and its numbers produced the label) while the results prose quoted qwen3:8b because it agreed better with the audit. With the hierarchical intervals: under the substituted PRIMARY (llama) team - solo detection is +26.0 (CI +9.4 to +43.8) and false alarm +28.1 (CI 0.0 to +60.4), so the registered label **"sensitivity gained at the price of false alarms" still applies**, capped at indicative; under qwen, the better-validated judge, detection is +8.3 (CI -6.2 to +26.0), so the detection gain is **not established**, with an established false-alarm cost (+42.7, CI +17.7 to +67.7). The two judges disagree materially (kappa 0.34) and the choice to lead with qwen was post hoc: it is disclosed here as a further deviation. What both judges support is the false-alarm cost of the old `team` behaviour; neither shows a net benefit.
- The statement that `teamfix` was worse than solo on detection, and the mechanism offered for it ("reassurance is a harm"), is **not established** (CI -36.5 to +8.3); it is a hypothesis. Likewise `teamdrop` better than `teamfix` is not established.
- What survives: `teamdrop` removes `team`'s false-alarm cost (-41.7, CI -67.7 to -16.7) and stays within the pre-registered false-alarm limit versus solo (+1.0, upper end +4.2). That is a harm reduction **relative to the old `team` behaviour, on this task set**; it is not evidence of benefit and not evidence of general safety. `teamdrop` was chosen after seeing the data, on the same eight tasks.
- Ordering check (Sol could not verify it from an archive): the pre-registration was merged at 09:32 UTC on 2026-10-06 (odysseus #114) and the data was first committed at 11:42 UTC (#117). Per-row collection times were not recorded, so the ordering rests on those merge times and the collection design, not on row timestamps.

## Limits

One model family under test (qwen3:8b); 8 task pairs authored by the same session that built the feature; judges are small local models validated against an AI audit, never a human;
post-hoc variants on the same tasks; no frontier-model re-judging of the replies (Sol and Opus reviewed the design, code and analysis on 2026-10-06 and found the interval method and the primary-judge reporting wrong, both corrected above; neither re-judged the 768 replies; GLM is unavailable). Treat all numbers as indicative.

## Decision

`teamdrop` (#116) is the best-performing variant on this task set (selected post hoc: no variant-selection rule was pre-registered), is the behaviour on dev, and is in production since 2026-10-06. It is a harm-reduction repair for the false-alarm cost of the old `team` behaviour (provisional: same eight tasks, selected post hoc), not evidence that multi-persona teams improve answer quality: benefit remains unproven. Specialist-lead teams stay available (`MISUMI_CONSULT=0` still disables them), with no claim that they improve answers.
A frontier-model re-judge of the replies and a human audit of a sample remain the next evidence steps (Sol is available; its 2026-10-06 review covered the design, code and analysis, not the 768 replies).

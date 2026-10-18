# Application -11 - does lead + justified support beat the lead alone? (2026-10-06)

Method: `evals/misumi-team/team-benchmark.ps1` on labelled scratch instances (`:1420`, scratch stores; production untouched) of
home releases, real model `qwen3:8b`. Five tasks each hide one inconsistency that is detectable from the prompt text alone
(budget, allergy, payday, timing, rollout); every task is run N=4 times per condition. A run "catches" the conflict when the
final reply matches the task's keyword checker - a LENIENT PROXY applied identically to both conditions (it can credit a reply
that merely restates a keyword and cannot read nuance). Four no-conflict CONTROL tasks measure false alarms: whether a support
opens `RISK:`, and whether the final reply contains a broad alarm keyword. `solo` = `MISUMI_CONSULT=0`; `team` = lead + justified
supports along the lead's own `consults` edges. Prompts avoid household-domain terms so both conditions take the model path.

Three runs, kept in order (raw rows in `raw-*.txt`):

| Run | Release / script | Solo caught | Team caught | Notes |
| --- | --- | --- | --- | --- |
| 1 (invalid for the team claim) | `d909387fa0`, first script, no controls | 5 / 20 | 10 / 20 | Teams formed on only 12 of 20 team runs: the `budget` and `payday` prompts used words (`bills`) that the LIVE manifest does not list as `l`'s intents, so the planner correctly recruited nobody. Found while reading the live manifest; the prompts were fixed and the run is NOT used as evidence. |
| 2 (uncalibrated) | `d909387fa0`, script with controls | 9 / 20 | 13 / 20 | Teams formed on 20/20 conflict runs. **Supports opened `RISK:` in 35 of 36 consults, including 15 of 16 no-conflict controls**, so the flag discriminated nothing. Control replies raising an alarm keyword: team 8 / 16, solo 0 / 16. |
| 3 (calibrated, `RISK:` requires quoting two conflicting facts; odysseus #107) | `331cda1f82` | **6 / 20** | **14 / 20** | Supports opened `RISK:` on **8 of 20** conflict runs and on **0 of 16** controls: the flag now discriminates. Control replies with an alarm keyword: team 6 / 16, solo 0 / 16. Median latency 4.9 s team vs 3.1 s solo. |

Per task, run 3 (team / solo): timing 4 / 0, rollout 4 / 0, budget 2 / 0, payday 3 / 4, allergy 1 / 2.

Reading it honestly:

- The team surfaced more planted conflicts in both valid runs (13 and 14 vs 9 and 6). The solo figure itself moved from 9 to 6
  between runs, so run-to-run noise is about +-3 of 20; the team advantage is larger than that noise but this is an indicative
  result, not a quality grade.
- The calibration did what it was for: after it, a support flags a conflict only sometimes (8 of 20) and never on a control
  (0 of 16), versus flagging nearly everything before.
- Costs and limits that remain: the team still missed the conflict in 6 of 20 runs; on the controls the lead's final reply
  carried an alarm keyword 6 times vs 0 solo (the keyword set is broad and the lead sometimes voices caution unprompted -
  not the same as a true false alarm, but not nothing); latency is about +1.8 s median (an extra model call per support);
  `allergy` and `payday` did not improve. Value-vs-theatre judgement by an independent reviewer (Sol) and a better judge than a
  keyword checker remain debt.

Raw files: `raw-2026-10-06-first-run-no-controls.txt`, `raw-2026-10-06-uncalibrated-run.txt`, `raw-2026-10-06-calibrated-run.txt`
(one row per run; summaries first-class).

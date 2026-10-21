# -11 evaluation v2 - pre-registration (written 2026-10-06 BEFORE any data was collected)

Question: does a lead plus justified supports (team) surface real problems better than the lead alone (solo), and what false-alarm
risk does it add on clean requests?

Design
- 8 task pairs (`tasks.json`). Each pair has a CONFLICT prompt (one planted, checkable problem) and a CLEAN twin (same topic, same lead,
  same support, the problem removed). Leads and supports follow the live manifest's `consults` edges; justification is `named` or an
  intent word the live manifest really lists. Prompts avoid household-domain terms so both conditions take the model path.
- N = 12 runs per prompt per condition: 96 conflict + 96 clean per condition, 384 replies in total (earlier runs: N = 4, 5 + 4 prompts).
- Conditions on labelled scratch instances of the deployed release, real model qwen3:8b: `solo` (`MISUMI_CONSULT=0`) and `team`.
  Run order is interleaved and shuffled with a fixed seed so drift does not align with a condition.
- Evaluators (blind to condition): PRIMARY = an independent-family judge (`reasoning-strong`, local Nemotron via aoteru), which sees the
  request, the ground truth for that prompt, and the reply, and returns two booleans: `explicitly_flags_the_issue` and
  `raises_concern_not_in_request`. SECONDARY = qwen3:8b with the same rubric (same family as the subject: reported, not relied on).
  Judge agreement is reported (Cohen's kappa). The earlier keyword checker is NOT used for the headline.
- Metrics: detection rate on CONFLICT prompts (`explicitly_flags_the_issue`); false-alarm rate on CLEAN prompts (`explicitly_flags_the_issue`
  OR `raises_concern_not_in_request`); the supports' own `RISK:` flag rate on conflict vs clean (does the flag discriminate?); median latency.
  95% intervals: Wilson for rates, paired bootstrap (resampling tasks and runs) for team-minus-solo differences.

Decision rule (fixed in advance)
- The team is shown to help ONLY IF, under the PRIMARY judge, detection rises by at least 15 percentage points with the 95% interval of the
  difference excluding 0, AND the false-alarm rate on clean prompts rises by no more than 5 points with the upper end of its 95% interval
  at most +10 points.
- If detection rises but the false-alarm limit is breached: "sensitivity gained at the price of false alarms" (not a net improvement).
- If neither holds: "not shown". If the judges disagree materially (kappa < 0.6), the conclusion is capped at "indicative".
- Whatever the outcome is recorded, including a negative one.

Known limits stated up front: one subject model, eight task types authored by the same party that built the system, LLM judges are fallible
and the primary judge is a different model family but not a human; word-level effects of the support prompt are not separated from the
extra reasoning pass itself.

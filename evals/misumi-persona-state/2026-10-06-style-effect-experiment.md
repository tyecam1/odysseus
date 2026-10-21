# Does each fixed style sentence move the behaviour it names? (2026-10-06)

Method (`evals/misumi-persona-state/style-effect-experiment.py`): for each non-default `(dimension, value)` the shipped sentence is
appended to the persona system prompt (the shipped placement) and a deterministic proxy metric is compared with a no-style
baseline, on the home host's Ollama (`qwen3:8b`, JSON turn format, release `b51db41f9a`'s real prompt constants; 4 prompts x 3
repeats = 12 replies per variant). Metrics are mechanical proxies, not quality judgements: words (`response_depth`), share of
long words >= 9 letters (`technical_depth`), share of replies with bullet / numbered lines (`structure`), share of replies
offering a next step (`intervention_style`). Rewording must never ask a persona to drop caveats or safety information.

## Round 1 - the sentences as shipped after the `brief` fix

| Value | Metric | Baseline | With sentence | Verdict |
| --- | --- | --- | --- | --- |
| response_depth=brief | words | 50.3 | 22.8 (0.45x) | works |
| response_depth=thorough | words | 50.3 | 94.1 (1.87x) | works |
| technical_depth=plain | long-word share | 0.120 | 0.078 (0.65x) | works |
| technical_depth=technical | long-word share | 0.120 | 0.143 (1.19x) | weak |
| structure=bullets | replies with bullets | 0% | 50% | weak |
| structure=stepwise | replies with numbered lines | 0% | 100% | works |
| intervention_style=proactive | replies offering a next step | 0% | **0%** | **did not move** |
| structure=prose, intervention_style=reactive | (baseline already 0%) | 0% | 0% | not measurable at the floor |

## Round 2 - candidate rewordings for the three weak ones (baseline: words 50.8, long 0.112, bullets 0, offer 0)

| Value | Candidate | Metric result |
| --- | --- | --- |
| proactive | "End every answer with one concrete next step you could take, phrased as an offer." | offers 0% -> **67%** (adopted) |
| proactive | "After answering, add one short suggestion for what to do next." | 0% -> 0% (rejected) |
| bullets | "Format every answer as a bulleted list, one short point per line, each line starting with '- '." | 0% -> **100%** (adopted) |
| bullets | "Answer only in short bullet points (lines starting with '- ')." | 0% -> 100% |
| technical | "Assume expert knowledge: use precise technical terminology and do not explain basic terms." | long share 0.112 -> **0.167 (+49%)** (adopted) |
| technical | "Write for a specialist: use the correct technical terms without simplifying them." | 0.112 -> 0.158 (+41%) |

Adopted in odysseus #110. None of the sentences asks a persona to drop caveats or safety information.

## Round 3 - the "down" direction on prompts chosen to provoke the behaviour

`structure=prose` is the DEFAULT value of its dimension: it renders no sentence at all (it is the reset), so there is nothing to
measure (the harness first tried to render it and crashed with a `KeyError`; kept in the raw output, not hidden). For
`intervention_style=reactive` the prompts are statements that invite suggestions ("I am thinking of repainting my kitchen.").

| Run | Baseline (replies offering a next step) | Shipped reactive sentence | Candidate A ("Do not offer suggestions, next steps or follow-up questions unless the user asks for them.") | Candidate B ("Reply only to what was said. Never end with an offer, a suggestion or a question.") |
| --- | --- | --- | --- | --- |
| n=3 per prompt (9 replies) | 0.44 | **0.67 (went UP)** | - | - |
| n=4 per prompt (12 replies) | 0.50 | 0.25 | 0.33 | 0.17 |

The shipped sentence moved the wrong way in one run and the right way in the other, so with 9-12 replies per variant its effect is
INDISTINGUISHABLE from noise; the candidates are not distinguishable from each other either. No sentence was changed on this evidence.
Candidate B was not adopted regardless: forbidding every question would also forbid a legitimate clarifying question when a request
is ambiguous or safety-relevant. A larger-N run (and a quality check on clarifying behaviour) is the open item for `reactive`.

Limits: one model, 12 replies per variant, proxy metrics.

## Raw output

```
# round 1
baseline {"words": 50.333, "long": 0.12, "bullets": 0.0, "numbered": 0.0, "offer": 0.0}
{"dimension": "intervention_style", "value": "proactive", "metric": "offer", "intended": "up", "baseline": 0.0, "with_sentence": 0.0, "moved_as_intended": false, "relative": null, "all": {"words": 59.5, "long": 0.112, "bullets": 0.0, "numbered": 0.0, "offer": 0.0}}
{"dimension": "intervention_style", "value": "reactive", "metric": "offer", "intended": "down", "baseline": 0.0, "with_sentence": 0.0, "moved_as_intended": false, "relative": null, "all": {"words": 52, "long": 0.111, "bullets": 0.0, "numbered": 0.0, "offer": 0.0}}
{"dimension": "response_depth", "value": "brief", "metric": "words", "intended": "down", "baseline": 50.333, "with_sentence": 22.833, "moved_as_intended": true, "relative": 0.45, "all": {"words": 22.833, "long": 0.105, "bullets": 0.0, "numbered": 0.0, "offer": 0.0}}
{"dimension": "response_depth", "value": "thorough", "metric": "words", "intended": "up", "baseline": 50.333, "with_sentence": 94.083, "moved_as_intended": true, "relative": 1.87, "all": {"words": 94.083, "long": 0.13, "bullets": 0.0, "numbered": 0.0, "offer": 0.0}}
{"dimension": "structure", "value": "bullets", "metric": "bullets", "intended": "up", "baseline": 0.0, "with_sentence": 0.5, "moved_as_intended": true, "relative": null, "all": {"words": 60.5, "long": 0.091, "bullets": 0.5, "numbered": 0.0, "offer": 0.0}}
{"dimension": "structure", "value": "stepwise", "metric": "numbered", "intended": "up", "baseline": 0.0, "with_sentence": 1.0, "moved_as_intended": true, "relative": null, "all": {"words": 74.833, "long": 0.086, "bullets": 0.0, "numbered": 1.0, "offer": 0.0}}
{"dimension": "technical_depth", "value": "plain", "metric": "long", "intended": "down", "baseline": 0.12, "with_sentence": 0.078, "moved_as_intended": true, "relative": 0.65, "all": {"words": 64.25, "long": 0.078, "bullets": 0.0, "numbered": 0.0, "offer": 0.0}}
{"dimension": "technical_depth", "value": "technical", "metric": "long", "intended": "up", "baseline": 0.12, "with_sentence": 0.143, "moved_as_intended": true, "relative": 1.19, "all": {"words": 62.25, "long": 0.143, "bullets": 0.0, "numbered": 0.0, "offer": 0.0}}

[exited with code 0]

# round 2 (--alts)
baseline {"words": 50.75, "long": 0.112, "bullets": 0.0, "numbered": 0.0, "offer": 0.0}
{"dimension": "intervention_style", "value": "proactive", "candidate": 0, "sentence": "End every answer with one concrete next step you could take, phrased as an offer.", "metric": "offer", "baseline": 0.0, "with_sentence": 0.667, "all": {"words": 65.75, "long": 0.09, "bullets": 0.0, "numbered": 0.0, "offer": 0.667}}
{"dimension": "intervention_style", "value": "proactive", "candidate": 1, "sentence": "After answering, add one short suggestion for what to do next.", "metric": "offer", "baseline": 0.0, "with_sentence": 0.0, "all": {"words": 61.583, "long": 0.105, "bullets": 0.0, "numbered": 0.0, "offer": 0.0}}
{"dimension": "structure", "value": "bullets", "candidate": 0, "sentence": "Format every answer as a bulleted list, one short point per line, each line starting with '- '.", "metric": "bullets", "baseline": 0.0, "with_sentence": 1.0, "all": {"words": 105.667, "long": 0.09, "bullets": 1.0, "numbered": 0.0, "offer": 0.0}}
{"dimension": "structure", "value": "bullets", "candidate": 1, "sentence": "Answer only in short bullet points (lines starting with '- ').", "metric": "bullets", "baseline": 0.0, "with_sentence": 1.0, "all": {"words": 72.083, "long": 0.081, "bullets": 1.0, "numbered": 0.0, "offer": 0.0}}
{"dimension": "technical_depth", "value": "technical", "candidate": 0, "sentence": "Assume expert knowledge: use precise technical terminology and do not explain basic terms.", "metric": "long", "baseline": 0.112, "with_sentence": 0.167, "all": {"words": 42.5, "long": 0.167, "bullets": 0.0, "numbered": 0.0, "offer": 0.0}}
{"dimension": "technical_depth", "value": "technical", "candidate": 1, "sentence": "Write for a specialist: use the correct technical terms without simplifying them.", "metric": "long", "baseline": 0.112, "with_sentence": 0.158, "all": {"words": 78.417, "long": 0.158, "bullets": 0.0, "numbered": 0.0, "offer": 0.0}}

[exited with code 0]

# round 3a (--hard, n=3; it crashed on the prose KeyError AFTER printing the reactive row)
syntax ok
{"dimension": "intervention_style", "value": "reactive", "metric": "offer", "intended": "down", "prompts": ["I am thinking of repainting my kitchen.", "I just started learning the guitar.", "We are hosting a dinner party next weekend."], "baseline": 0.444, "with_sentence": 0.667, "baseline_all": {"words": 18, "long": 0.032, "bullets": 0.0, "numbered": 0.0, "offer": 0.444}, "all": {"words": 17.333, "long": 0.049, "bullets": 0.0, "numbered": 0.0, "offer": 0.667}}
ssh : Traceback (most recent call last):
At line:5 char:1
+ ssh @h User@100.105.34.37 'C:\Users\User\odysseus-releases\b51db41f9a ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (Traceback (most recent call last)::String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
  File "C:\Users\User\style-effect-experiment.py", line 114, in <module>
    got = run(RENDER[(dimension, value)], prompts)
              ~~~~~~^^^^^^^^^^^^^^^^^^^^
KeyError: ('structure', 'prose')

[exited with code 1]

# round 3b (--hard with candidates, n=4)
{"dimension": "intervention_style", "value": "reactive", "metric": "offer", "intended": "down", "prompts": ["I am thinking of repainting my kitchen.", "I just started learning the guitar.", "We are hosting a dinner party next weekend."], "baseline": 0.5, "with_sentence": 0.25, "baseline_all": {"words": 17.667, "long": 0.029, "bullets": 0.0, "numbered": 0.0, "offer": 0.5}, "all": {"words": 13.583, "long": 0.056, "bullets": 0.0, "numbered": 0.0, "offer": 0.25}}
{"dimension": "intervention_style", "value": "reactive", "candidate": 0, "sentence": "Do not offer suggestions, next steps or follow-up questions unless the user asks for them.", "metric": "offer", "baseline": 0.5, "with_sentence": 0.333, "all": {"words": 12.417, "long": 0.048, "bullets": 0.0, "numbered": 0.0, "offer": 0.333}}
{"dimension": "intervention_style", "value": "reactive", "candidate": 1, "sentence": "Reply only to what was said. Never end with an offer, a suggestion or a question.", "metric": "offer", "baseline": 0.5, "with_sentence": 0.167, "all": {"words": 10.917, "long": 0.102, "bullets": 0.0, "numbered": 0.0, "offer": 0.167}}
```

# Style placement and wording experiment (2026-10-06)

Question (from the -10 live proof, where a durable `brief` style cut reply length far less than the same request typed in
the user turn): does WHERE the fixed style sentence sits, or WHAT it says, decide the effect?

Method: direct calls to the home host's Ollama (`qwen3:8b`, JSON turn format, `num_predict` 500), no Odysseus request path;
the foundation prompt is the release's real one (`_HONESTY_CONSTRAINTS`, ratification constraint, seed-order output rules,
persona role). 3 prompts x 4 repeats = 12 replies per variant; the metric is words in the `answer` field (a length proxy, not
a quality judgement). Script: `evals/misumi-team/style-placement-experiment.py`. Two separate runs within the same session, so the
baseline differs between them (63.8 and 59.8 words).

| Run | Variant | Mean words | Relative to no style |
| --- | --- | --- | --- |
| placement | none | 63.8 | 1.00 |
| placement | system (appended to the persona system prompt - what -10 shipped) | 44.4 | 0.70 |
| placement | late (separate system message just before the user turn) | 43.9 | 0.69 |
| placement | user (sentence appended to the user turn) | 46.2 | 0.72 |
| wording | none | 59.8 | 1.00 |
| wording | system, shipped sentence ("lead with the answer in one to three sentences...") | 45.2 | 0.76 |
| wording | system, A: "Keep answers short: at most two sentences unless the user asks for more." | 28.3 | 0.47 |
| wording | system, B: "Answer in at most two short sentences. Do not add background or caveats unless asked." | 21.6 | 0.36 |

Findings:

1. **Placement does not matter** (0.69-0.72): the system-prompt placement the shipped design uses is as effective as placing the
   sentence late or in the user turn, so the structural guarantee (style appended after an untouched foundation) costs nothing.
2. **Wording is the lever.** The shipped sentence was the weak one (0.76); a concrete limit ("at most two sentences") nearly halves
   the length. The earlier live gap between a turn request (-60%) and a durable style (-12% to -35%) was wording plus noise, not
   channel.
3. **Wording B was rejected although it is strongest**: "Do not add background or caveats" invites a persona to drop safety
   information, and a style sentence must never relax honesty or safety. Wording A was adopted for `response_depth=brief`
   (odysseus PR #108); the other seven fixed sentences are untested and queued for the same treatment.
4. Limits: one model, 12 samples per variant, a word-count proxy; effect sizes are indicative.

## Raw output

```
# placement run
none {"mean": 63.8, "median": 64.0, "min": 44, "max": 80, "n": 12}
system {"mean": 44.4, "median": 44.0, "min": 37, "max": 53, "n": 12}
late {"mean": 43.9, "median": 44.0, "min": 32, "max": 57, "n": 12}
user {"mean": 46.2, "median": 45.0, "min": 43, "max": 52, "n": 12}
relative_to_none {"none": 1.0, "system": 0.7, "late": 0.69, "user": 0.72}

# wording run
none {"mean": 59.8, "median": 61.5, "min": 42, "max": 97, "n": 12}
system {"mean": 45.2, "median": 45.0, "min": 38, "max": 51, "n": 12}
wording-A {"mean": 28.3, "median": 26.0, "min": 21, "max": 43, "n": 12}
wording-B {"mean": 21.6, "median": 21.0, "min": 19, "max": 25, "n": 12}
relative_to_none {"none": 1.0, "system": 0.76, "wording-A": 0.47, "wording-B": 0.36}
```

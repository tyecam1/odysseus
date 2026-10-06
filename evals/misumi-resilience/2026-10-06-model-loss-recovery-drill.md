# B2 resilience drill - model/network loss and recovery (2026-10-06)

Scratch instances only: Odysseus `:1420` of release `331cda1f82` and the host agent on `:4510` from the canonical clone; the
production services on `:420` and `:4500` were never addressed. The model endpoint is pointed at a dead local port to simulate
loss of the model backend, then restored by a real process restart. Script: `evals/misumi-resilience/drill-model-loss.ps1`.

| Phase | Observed |
| --- | --- |
| M1 model healthy | open-ended reply `source: model` in 2.7 s; household-grounded request answered from files in 195 ms; a justified team formed (`misato` support ok) |
| M2 model lost | open-ended reply **degrades honestly** in 2.6 s: `source: degraded`, "Odysseus is available, but the configured model did not complete this request."; the household-grounded request is **still answered from files** (195 ms, no model needed); the justified team's support is recorded `failed` and the request returns `degraded` in 2.3 s (no hang) |
| M3 restored (restart) | model replies again (2.6 s), team formed again |
| A1 agent brain healthy | `source: model` in 0.9 s |
| A2 agent brain lost | `/respond` falls back to the scripted line in 2.1 s (`source: scripted`), so the box always gets an answer within its budget |
| A3 agent restored (restart) | `source: model` again |

Findings: text-first degradation holds at both layers; the household-grounded path is independent of the model; failures are
reported truthfully (`degraded`, support `failed`) rather than masked. Nothing needed fixing here. Not tested (household-gated):
the real kiosk box's behaviour during the outage, perceived latency, audibility.

## Raw output

```
M1-model-healthy {"justified_team":{"team":"team","status":200,"supports":["misato:ok"],"source":"model","ms":2803},"open_ended":{"status":200,"source":"model","text":"A rainbow forms when light from the sun is refracted, or bent, as it enters a water droplet. The light is then","ms":2689},"household_grounded":{"status":200,"source":"household-read-only","ms":195}}
M2-model-lost {"justified_team":{"team":"team","status":200,"supports":["misato:failed"],"source":"degraded","ms":2335},"open_ended":{"status":200,"source":"degraded","text":"Odysseus is available, but the configured model did not complete this request.","ms":2634},"household_grounded":{"status":200,"source":"household-read-only","ms":194}}
M3-model-restored-after-restart {"justified_team":{"team":"team","status":200,"supports":["misato:ok"],"source":"model","ms":2856},"open_ended":{"status":200,"source":"model","text":"A rainbow forms when sunlight is refracted, or bent, as it passes through water droplets in the air. The light","ms":2589},"household_grounded":{"status":200,"source":"household-read-only","ms":194}}
A1-brain-healthy {"status":200,"has_text":true,"source":"model","text":"I am Jin, the Selector.","ms":863}
A2-brain-lost {"status":200,"has_text":true,"source":"scripted","text":"Noted. The collection remembers.","ms":2086}
A3-brain-restored-after-restart {"status":200,"has_text":true,"source":"model","text":"I am Jin, the Selector.","ms":533}
DONE (production :420 and :4500 untouched)
```

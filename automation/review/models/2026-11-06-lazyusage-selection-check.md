# /lazyUsage selection under Claude/Codex usage states (single-sample check, GLM-5.3)

Evidence for the #211 acceptance item "compare the skill's selection under adequate/exhausted/unknown Claude/Codex usage". It is a **small, same-family check, not a verdict**: one sample per scenario, run on `glm-5.3` (the newest GLM known, via the `claude-glm` wrapper), not on Claude Code with the skill installed and not a Sol verification. The Sol/independent verification of the skill remains owed, and this item stays unticked in #211.

## Method

For each of six usage-evidence scenarios the model received the exact text of `.claude/skills/lazyUsage/SKILL.md` and `START-AGENTIC.md` from `dev` (a2a2cb0), the scenario's synthetic usage evidence, and a synthetic frontier with one eligible, ready, qualified task in each of the three queues (PhD P-1, Odysseus O-1, Misumi M-1). It was asked, for selection only and without running anything, which queue it selects first. The frontier is synthetic (the queues were not read) and the PhD task description states that it needs Claude and Codex review capacity, which may bias towards the rule's own premise. Script below.

## Results

| Scenario | Claude / Codex / GLM evidence | Selected first | Matches the rule? |
|---|---|---|---|
| A | adequate / adequate / adequate | PhD | yes (prefer PhD when both are adequate) |
| B | exhausted / adequate / adequate | Odysseus | yes |
| C | adequate / exhausted / adequate | Odysseus | yes |
| D | adequate / unknown / adequate | Odysseus | yes (unknown treated as not adequate) |
| E | unknown / adequate / adequate | Odysseus | yes (same) |
| F | unknown / unknown / unknown | Odysseus | yes (same) |

In all six the stated reason matched the skill text: PhD only when both Claude and Codex are verified adequate; otherwise shippable Odysseus backend work; unknown usage is not assumed adequate. The model chose Odysseus over Misumi each time without being told a preference between them.

## What this does not show

- Behaviour of Claude Code or Sol running the installed skill, and behaviour on the real queues (the real frontier was not used here; discovery against the real queues was recorded in the original acceptance record).
- Stability: one sample per scenario; no repeats.
- Whether the Odysseus-over-Misumi tie-break is intended or an artefact.
- The governed execution half of the second #211 item (preflight, lease, independent verification, return through `/lazyUsage`).

## Script

```python
```

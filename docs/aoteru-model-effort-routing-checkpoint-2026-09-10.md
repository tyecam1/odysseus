---
title: Model-effort routing — checkpoint and cross-repo intent
status: implemented-in-odysseus-aoteru, not-yet-adopted-elsewhere
as_of: 2026-09-10
owner: odysseus
scope: docs/aoteru-model-effort-routing.agent-task.md follow-up — records what shipped and states intent for the user's other repos
---

# Model-effort routing — checkpoint and cross-repo intent

## What this is

`src.estate_router` (this repo) now resolves an optional **effort** rung
alongside every routed model, in addition to host/model/executor. This
document is a checkpoint of that work and a statement of intent: the
same effort vocabulary and mapping rules are meant to become the one
scheme the user's other repos route reasoning effort through, rather
than each repo inventing or hand-coding its own.

## Current state (this repo, branch `chatgpt/model-effort-routing-20260910`)

- **Vocabulary**: `low | medium | high | highest`, chosen at the
  routing layer, independent of any one provider's own terms.
- **Default source**: `task.complexity` (already in the canonical task
  envelope) — `trivial->low`, `routine->medium`, `hard->high`,
  `frontier->highest`.
- **Explicit override**: `task.routing.effort`, same envelope slot as
  the existing `routing.quality_floor`/`routing.local_first`.
- **Authority**: effort never widens model/verification/write authority
  or task eligibility — it is advisory metadata on the resolved route,
  computed after host/alias/executor selection, never an input to it.
- **Provider wiring** — only where a real, verified invocation option
  already exists (config-declared per provider/alias, defaults to
  unsupported, never assumed):
  - **Codex** (`codex exec`): `-c model_reasoning_effort=<low|medium|high>`
    (`highest` maps to `high`, Codex's ceiling).
  - **Claude Code** (native `claude` launch in `scripts/agent`'s
    `agent claude`, and the `claude-glm` candidate sidecar in
    `src.estate_router.execute_claude_glm`, which forwards to the same
    binary): `--effort <low|medium|high|xhigh>` (`highest` maps to
    `xhigh`, not `max` — routing's "highest" means "the strongest rung
    this task's complexity warrants", not "spend the most possible
    regardless").
  - Every other provider (local Ollama models, everything without a
    declared `supports_effort: true`) is unaffected — omitting the
    parameter leaves existing behaviour byte-for-byte unchanged.

See `docs/aoteru-model-host-routing-contract.md`'s `routing.effort`
entry for the canonical envelope shape, and
`src.estate_router._COMPLEXITY_DEFAULT_EFFORT` /
`_CODEX_EFFORT_MAP` / `_CLAUDE_EFFORT_MAP` for the source-of-truth
mapping tables.

## Intent: adoption by the user's other repos

This scheme is meant to be followed, not re-invented, by every other
repo/automation that dispatches Claude Code or Codex on the user's
behalf. Concretely, at time of writing:

- `phd/obsidian-PhD`'s `.agents/skills/route/SKILL.md` (the Fable-Sol
  routing loop) already hand-writes `codex exec ... -c
  model_reasoning_effort=high` in its prose dispatch examples — this is
  the same underlying provider control this checkpoint formalises, just
  chosen by an operator/agent reading a skill file rather than resolved
  by a router. That skill (and any sibling automation doing the same
  by hand, e.g. `vault-remote-upkeep`'s `autolab.env.example`
  `AUTOLAB_CODEX_RUN_TEMPLATE`) is a natural first adopter: it should
  eventually resolve effort the same way (task complexity -> rung,
  explicit override where the task packet already carries one) instead
  of a fixed hardcoded `high` in every invocation.
- Any future repo that dispatches Claude Code, Codex, or a
  Claude-Code-compatible sidecar (GLM or otherwise) should reuse this
  vocabulary (`low/medium/high/highest`) and these provider mapping
  tables rather than choosing its own effort terms or thresholds — the
  mapping tables above are the translation layer specifically so
  callers never need to know a given provider's native vocabulary.

## Explicitly not done yet

- No other repo has been changed to consume this. This is a checkpoint
  of intent, not a completed rollout.
- No shared/library extraction exists — the mapping tables currently
  live only in `src.estate_router`. If/when a second repo actually
  adopts this, the mapping tables should move somewhere both repos can
  import from rather than being copy-pasted, to avoid drift.
- `claude` and `claude-glm` support is real but currently only reachable
  through `agent claude` (standalone dispatch) and the still-candidate-
  gated GLM paid-provider lane (`routing_eligible: false` until
  qualified) — neither is a normally-routed escalation path yet.

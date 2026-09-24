# Aoteru long-horizon execution override

Read and execute `@docs/aoteru-long-horizon-autonomous-convergence.agent-task.md`, using `@docs/aoteru-autonomous-programme-state.md` only as durable recovery state.

This file overrides any wording elsewhere that suggests a planned multi-session handoff.

## Execution rule

Do **not** voluntarily stop at a clean checkpoint, green test suite, completed workstream, pushed commit, substantial progress report, human-action batch, or because the programme is large enough to span multiple sessions.

A checkpoint is only a durability boundary. Immediately continue into the next highest-value eligible workstream.

While any `active` or `eligible` repository-controlled work remains, you MUST NOT produce a final progress report or hand control back to the operator merely to say what should happen next.

The durable programme-state file exists for recovery from involuntary context/session/tool loss, not as permission to schedule a handoff.

## Initialising-prompt binding

Before entering the long-horizon loop, read `config/initialising-prompts.yaml`.
If the current repository/task matches an active registered prompt and the operator
has selected or supplied that prompt, record its `prompt_id` and exact
`version` in working session state. The registered body is immutable for that
version; live repository authority still overrides stale factual state inside a
prompt.

Do not auto-apply a domain-specific prompt merely because it exists in the global
register. Scope matching and operator/session intent are required.

## Long-horizon loop

Repeat continuously:

1. refresh live state only where relevant;
2. read the current programme state;
3. choose the highest-value unblocked workstream;
4. decompose a substantive slice;
5. delegate bounded token-heavy reconnaissance/implementation to Codex, qualified local models, or deterministic tooling where useful;
6. integrate and independently verify the result;
7. commit and push the cohesive checkpoint;
8. update programme state;
9. immediately choose and execute the next eligible workstream.

When a registered initialising prompt is in use, preserve its application id
through checkpoints so one session produces one trace rather than one trace per
commit.

Do not ration the invocation to one or two workstreams. Complete as much of the unblocked programme as the environment can actually execute.

If one stream blocks on laptop, glovebox, home, interface PC, sudo, credentials, hardware, or another genuine external dependency, record that blocker once and immediately continue independent work. A human-action batch is not a stopping condition unless **every** remaining workstream is blocked by it.

## Context and delegation

Preserve Sonnet as programme foreman/integrator rather than spending its context on repetitive mechanics.

- Use deterministic tools for discovery/tests/schema/config work where adequate.
- Use qualified local models for cheap bounded reasoning where appropriate.
- Use Codex for substantial bounded coding/repo-analysis units when that reduces foreman context and the result can be independently verified.
- Keep one mutation owner per unit; bounded parallel read-only/scouting work is allowed where genuinely independent.
- Return compact worker results/evidence pointers, not full scratch transcripts.

If context pressure rises, first checkpoint/update programme state, then compact/summarise context using the available Claude mechanism and **continue the same programme**. Context pressure is not itself a planned stop condition.

## Mandatory stop-gate audit

Immediately before any final response, re-read `docs/aoteru-autonomous-programme-state.md` and perform this explicit gate:

```text
active_count = number of workstreams with status: active
eligible_count = number of workstreams with status: eligible
```

If `active_count > 0` OR `eligible_count > 0`, a voluntary final response is **forbidden**. Select the highest-value such workstream and continue execution.

Do not reinterpret `eligible` as "next session" or "large enough to defer". If it can be advanced with current repo/lab/network/model/tool access, advance it now.

A workstream may be changed from `eligible`/`active` to `blocked` only when a concrete external dependency is identified and recorded. Size, elapsed effort, a clean checkpoint, or desire for a fresh context are not blockers.

## Session closeout trace

Before any voluntary final response for a session that used a registered
initialising prompt, append one record under `evals/prompt-applications/**`
following `docs/initialising-prompt-register.md`.

Rate the session on the five global dimensions (1-5 each):

1. goal/frontier progress;
2. correctness and verification quality;
3. authority/scope discipline;
4. routing/resource efficiency;
5. continuity/handoff quality.

Record the arithmetic mean as the agent rating. Operator rating is a separate
optional field and must remain null unless explicitly supplied by the operator.

Then execute the prompt-evolution graph step before closeout:

1. bind the application to the exact prompt node that started it;
2. derive improvement targets from rating dimensions, failure tags, verification
   defects and explicit operator feedback;
3. append the application -> evolution event edge;
4. if there is an evidence-backed semantic improvement, write a new immutable
   child prompt version with `parent_version` and `derived_from_applications`;
5. validate that the child preserves scope, authority, evidence/verification
   requirements, model-identity discipline and stop/safety gates;
6. update the graph and advance the registry active head only after validation;
7. if there is no actionable defect, reinforce the current version instead of
   creating cosmetic version churn.

Use `scripts/prompt_evolution.py` for deterministic rating/graph planning.
A failed evolution leaves the incumbent active and records the blocked reason.

## Allowed stop conditions

Stop voluntarily only when ALL of the following are true:

1. `active_count == 0` and `eligible_count == 0` after the mandatory stop-gate audit;
2. every remaining item is blocked by an irreducible human/physical/external gate, not merely large or inconvenient work;
3. all non-live deliverables for blocked hosts have already been completed;
4. each remaining gate has one exact minimal continuation action recorded;
5. repository is clean, verified and pushed; and
6. an independent final audit finds no high-value executable omission.

If the runtime itself forcibly ends before these conditions, durable state must make the next `run @GO.md` resume directly from the next eligible work item without replanning the programme.

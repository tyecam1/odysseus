# Aoteru long-horizon execution override

Read and execute `@docs/aoteru-long-horizon-autonomous-convergence.agent-task.md`, using `@docs/aoteru-autonomous-programme-state.md` only as durable recovery state.

This file overrides any wording elsewhere that suggests a planned multi-session handoff.

## Execution rule

Do **not** voluntarily stop at a clean checkpoint, green test suite, completed workstream, pushed commit, substantial progress report, or because the programme is large enough to span multiple sessions.

A checkpoint is only a durability boundary. Immediately continue into the next highest-value eligible workstream.

While any `active` or `eligible` repository-controlled work remains, you MUST NOT produce a final progress report or hand control back to the operator merely to say what should happen next.

The durable programme-state file exists for recovery from involuntary context/session/tool loss, not as permission to schedule a handoff.

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

Do not ration the invocation to one or two workstreams. Complete as much of the unblocked programme as the environment can actually execute.

If one stream blocks on laptop, glovebox, home, interface PC, sudo, credentials, hardware, or another genuine external dependency, record that blocker once and immediately continue independent work.

## Context and delegation

Preserve Sonnet as programme foreman/integrator rather than spending its context on repetitive mechanics.

- Use deterministic tools for discovery/tests/schema/config work where adequate.
- Use qualified local models for cheap bounded reasoning where appropriate.
- Use Codex for substantial bounded coding/repo-analysis units when that reduces foreman context and the result can be independently verified.
- Keep one mutation owner per unit; bounded parallel read-only/scouting work is allowed where genuinely independent.
- Return compact worker results/evidence pointers, not full scratch transcripts.

If context pressure rises, first checkpoint/update programme state, then compact/summarise context using the available Claude mechanism and **continue the same programme**. Context pressure is not itself a planned stop condition.

## Allowed stop conditions

Stop voluntarily only when ALL of the following are true:

1. no `active` or `eligible` programme work remains that can be completed with currently available repo, lab, network, model/provider and tool access;
2. every remaining item is blocked by an irreducible human/physical/external gate, not merely large or inconvenient work;
3. all non-live deliverables for blocked hosts have already been completed;
4. each remaining gate has one exact minimal continuation action recorded;
5. repository is clean, verified and pushed; and
6. an independent final audit finds no high-value executable omission.

If the runtime itself forcibly ends before these conditions, durable state must make the next `run @GO.md` resume directly from the next eligible work item without replanning the programme.

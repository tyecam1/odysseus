# WhatsApp architecture capture - 2026-10-03

Source: operator WhatsApp self-notes dated 2026-07-22 to 2026-09-08.

Purpose: preserve durable architecture ideas without treating them as implemented requirements. This note is not an authority surface and does not override `AGENTS.md`, `docs/aoteru-model-host-routing-contract.md`, the initialising-prompt register, or current runtime contracts.

## Already substantially owned

### Prompt libraries and reusable prompts

The old capture "ingest prompt libraries" is substantially owned by the current initialising-prompt register, immutable prompt bodies, prompt exemplars, application traces, and prompt-evolution loop.

Do not create a second prompt registry.

### Large/strong model handoff by task difficulty

The old idea of producing a robust plan and then sending it to a very capable remote model is substantially owned by the current delegation invariant and model-host routing contract.

Treat this as routing policy rather than a standalone feature.

## Architecture candidates worth retaining

### Answer-strategy knowledge graph

Original capture: "knowledge graph on HOW to answer questions."

Potential interpretation: represent reusable answer/research strategies separately from domain facts. A strategy node could describe:

- task/question class;
- preferred evidence and source types;
- decomposition pattern;
- tool sequence;
- verification checks;
- successful prompt/model patterns;
- known failure modes.

Constraint: do not store hidden chain-of-thought. Persist inspectable procedures, sources, decisions, and evaluation evidence only.

### Purpose-distilled persona/model binding

Original captures: "each persona needs an individual model" and "distilled for its purpose."

Potential interpretation: let an agent/persona profile explicitly bind:

- task purpose;
- system instructions;
- tools;
- memory scope;
- preferred model class;
- output contract.

Before adding schema, check whether existing agents/presets already cover this without duplication.

### Cross-surface memory convergence

Original capture: "global memory system that auto syncs from all fronts and apps."

Potential interpretation: converge useful context from chat, notes, email, calendar, and other connected surfaces while preserving:

- provenance;
- source authority;
- freshness;
- conflict handling;
- deletion boundaries;
- distinction between transient context and durable memory.

Do not silently turn every connected-app observation into durable memory.

### Read-only adversarial audit agents

Original capture: "adversarial local audit agents that cannot edit files but are scoped to one specific ledger."

Potential interpretation: add an explicit audit-only execution contract where a worker:

- receives one bounded ledger/surface;
- has read-only access to the target;
- searches specifically for contradictions, omissions, drift, or invalid state;
- emits findings and evidence only;
- cannot self-repair the audited surface.

This aligns closely with the existing authority model and is the strongest unresolved architecture idea in this capture.

### Cross-model critique handoff

Original capture: a Claude/worker loop emits compact state into another model/UI for guidance.

Potential interpretation: allow a bounded worker to package:

- current state;
- uncertainties;
- attempted actions;
- blocking evidence;
- proposed next move;

for critique by a stronger or differently specialised model.

Constraints:

- preserve task and repository authority;
- avoid circular delegation;
- record the handoff durably;
- do not use a second model to bypass denied permissions or stopping rules.

## Product/application ideas, not core architecture requirements yet

### Localised persona presentation

Old capture: persona behaviour may use language-specific framing internally while keeping controlled user-facing output.

Needs a product/use-case definition before it should affect architecture.

### Public-sector lightweight-model deployment

Old capture: explore smaller targeted/local models as an alternative to unnecessary central datacentre inference for public-service use cases.

This is a deployment/policy concept, not yet an Odysseus core requirement.

## Triage rule

Compare the five architecture candidates above against current agent, preset, memory, audit, routing, and evaluation primitives.

- Close or absorb anything already implemented.
- Split only genuinely missing behaviour into bounded work.
- Do not promote this capture into a competing roadmap, task queue, prompt registry, or architecture contract.

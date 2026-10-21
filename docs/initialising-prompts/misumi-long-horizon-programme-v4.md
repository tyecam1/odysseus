---
title: Misumi long-horizon programme v4 (adaptive routing and behaviour)
status: active
created: 2026-10-04
supersedes: misumi-long-horizon-programme-v3
scope: long-horizon-programme-directive
provenance: operator directive received complete via Dispatch on 2026-10-04 (application -07); recorded verbatim below
---

Prompt identity: `misumi-long-horizon-programme@v4`

# Misumi long-horizon programme — application -07 directive (registered as v4)

You are executing the next Misumi long-horizon application.

## Stage objective

Build Misumi's first controlled experience-driven behavioural adaptation loop.

The target capability is:

**evidence-backed routing adaptation in shadow mode, followed by governed promotion into active routing.**

Misumi must become capable of learning a routing preference from interaction evidence without allowing individual corrections, transient user choices, classifier mistakes, or weak evidence to silently mutate persistent behaviour.

This stage succeeds only when a complete causal chain can be demonstrated:

`interaction`
→ `routing decision`
→ `user evidence`
→ `candidate affinity`
→ `evaluation`
→ `authorised promotion`
→ `changed future route`
→ `explainable trace`
→ `rollback`

Do not broaden this stage into general persona learning.

---

## Established baseline

Treat the following as established unless live reconciliation disproves it.

Application `-06` delivered:

- deterministic lead-persona routing;
- routing contract v0.1;
- runtime behaviour aligned with `route_dry_run.py`;
- Auto mode;
- room/interface leader transition logic;
- deployed runtime routing;
- 12/12 live routing fixtures passing with persistence disabled;
- routing evidence and trace integration;
- failures preserved rather than sanitised.

Known limits:

- physical kiosk observation of the visible room transition remains pending because the interface-box bridge is paused by operator/household decision;
- the interface implementation exists but physical acceptance remains open;
- one failed live attempt against `:4500/agent` is preserved;
- a pre-existing Qwen JS routing discrepancy was exposed;
- memory policy v0.2 contains a ratification-status inconsistency that must be resolved before persistent behavioural mutation is treated as authorised;
- the previous programme directive was received truncated, so application `-06` legitimately ran under the earlier registered loop.

Do not reopen application `-06` implementation unless reconciliation reveals a real regression.

Record its physical UI acceptance as an outstanding acceptance item and proceed around it.

---

# Core hypothesis

A routing system can safely adapt from experience if:

1. interaction evidence remains immutable;
2. learned routing state is represented separately from raw evidence;
3. weak or ambiguous feedback creates candidate state only;
4. candidate changes are evaluated before activation;
5. active changes require the applicable ratification authority;
6. every effective change is traceable and reversible.

The key distinction is:

**an interaction correction is not automatically a persistent preference.**

Do not conflate them.

---

# Behaviour classes

At minimum distinguish the following evidence meanings.

## 1. Interaction correction

Example:

Auto selects Persona A.

The user immediately switches to Persona B for this request.

Meaning:

> Persona A was unwanted in this interaction.

This does NOT automatically mean all similar future requests should use Persona B.

---

## 2. Temporary choice

Example:

The user deliberately selects another persona because they want a different tone or perspective right now.

Meaning:

> Use Persona B for this interaction/session.

This must not create durable routing state unless additional evidence explicitly justifies it.

---

## 3. Explicit durable preference

Example:

"For cleaning rota questions, use Misato from now on."

Meaning:

> Persistent mapping is directly authorised by the user.

This is high-confidence evidence.

---

## 4. Repeated behavioural evidence

Several similar corrections or confirmations occur across separate interactions.

Meaning:

> A persistent affinity may exist.

This creates or strengthens a candidate but does not itself bypass ratification rules.

---

# Stage architecture

Prefer the smallest possible number of new primitives.

Start from these four logical concepts unless existing structures already satisfy them cleanly.

## `routing_evidence`

Immutable event describing what occurred.

Include enough provenance to reconstruct:

- original utterance or stable reference;
- original route;
- route confidence/reason;
- subsequent manual choice or confirmation;
- evidence type;
- timestamp;
- runtime/version;
- session/context identifier where appropriate;
- persistence eligibility;
- source authority.

Do not mutate evidence records after creation except through explicit correction/audit mechanisms.

---

## `affinity_candidate`

A proposed routing change derived from one or more evidence records.

Candidate state should include at minimum:

- cue/domain/pattern represented;
- current persona mapping;
- proposed persona mapping;
- supporting evidence references;
- contradictory evidence references;
- confidence;
- rationale;
- creation/revision time;
- status.

Do not over-engineer cue representation in this stage.

Use the narrowest representation capable of proving the adaptation loop.

---

## `promotion_state`

Use explicit lifecycle states such as:

`shadow`
→ `eligible`
→ `active`

with terminal paths such as:

`rejected`
or
`superseded`

The exact implementation may differ if an equivalent state model already exists.

No candidate becomes active merely because its numerical confidence crosses a threshold if programme policy requires ratification.

---

## `routing_revision`

A versioned effective routing-state change.

It must identify:

- previous routing state;
- resulting routing state;
- candidate/evidence provenance;
- authorisation;
- effective time/version;
- rollback path.

---

# Critical separation

Maintain these boundaries:

`raw interaction`
≠
`routing evidence`

`routing evidence`
≠
`candidate routing state`

`candidate routing state`
≠
`active routing state`

`active routing state`
≠
`persona personality state`

This stage changes routing only.

Do not mutate persona prompts, personality traits, voices, memories or competence claims as part of this stage.

---

# Pre-implementation reconciliation

Before implementation:

1. verify live repository heads;
2. verify deployed runtime version;
3. verify application `-06` evidence;
4. verify active routing contract;
5. inspect the memory-policy v0.2 ratification discrepancy;
6. inspect the governing seed-order / ratification rule;
7. register the complete current long-horizon programme directive if the prior registered directive remains truncated;
8. identify whether any existing data model already implements part of the candidate/promotion lifecycle.

Do not silently choose between contradictory policy documents.

If the memory policy has contradictory ratification markers, repair or escalate that governance ambiguity before activating persistent learned routing.

Implementation of shadow-state machinery may continue where it does not require policy ratification.

---

# Baseline robustness test

Before allowing learned state to influence routing, strengthen the baseline router evaluation.

Add a compact adversarial/generalisation suite containing representative examples of:

- paraphrases;
- indirect requests;
- underspecified requests;
- mixed-domain prompts;
- competing persona cues;
- negations;
- corrections;
- conversational follow-ups;
- wording unlike the original byte-identical contract fixtures.

The purpose is not to build a massive benchmark.

The purpose is to distinguish:

`router weakness`

from:

`genuine learned user preference`.

Preserve the original deterministic fixtures unchanged.

---

# Shadow adaptation

Implement evidence capture and candidate generation without changing effective routing initially.

Example causal sequence:

1. Auto routes request to Persona A.
2. User chooses Persona B.
3. A `routing_evidence` event is persisted.
4. Evidence semantics are classified as correction, temporary choice, explicit preference, confirmation, or other supported category.
5. A candidate mapping is created or updated.
6. Active routing remains unchanged.
7. Candidate behaviour can be evaluated counterfactually.

The trace must clearly state when behaviour is:

**shadow only**

rather than active.

---

# Promotion policy

Do not invent authority.

Respect existing ratification law.

A candidate may become active only when the current programme policy allows it.

Explicit durable user instruction may qualify differently from inferred affinity, but use the actual governing contract rather than assuming.

If ratification authority is unavailable:

- complete candidate generation;
- complete shadow evaluation;
- persist the candidate;
- mark it awaiting ratification;
- continue with non-blocked work.

Do not fake promotion.

---

# Candidate evaluation

Before promotion, evaluate a proposed mapping against:

1. original deterministic routing fixtures;
2. new adversarial/paraphrase fixtures;
3. relevant historical prompts where available;
4. direct candidate-target prompts;
5. nearby prompts that should NOT change;
6. conflicting/ambiguous prompts.

Measure at minimum:

- intended routing gains;
- regressions;
- spillover to unrelated intents;
- conflicting evidence;
- determinism/repeatability.

A candidate must not improve one example while silently degrading an entire neighbouring class.

---

# Required demonstration

The core stage demonstration must make the adaptation obvious.

Use one bounded routing affinity.

Demonstrate:

### Before

Prompt P routes to Persona A under active routing state R0.

### Evidence

User evidence E1...En supports Persona B.

### Shadow candidate

Candidate C proposes:

`P-class → Persona B`

while active routing remains unchanged.

### Evaluation

Show:

- expected improvement;
- no unacceptable regression;
- relevant counterexamples;
- provenance.

### Promotion

Apply the proper authorised promotion to produce routing revision R1.

### After

The same or appropriately equivalent prompt now routes to Persona B because of R1.

### Explanation

The trace must identify:

- original route;
- evidence;
- candidate;
- authorisation;
- revision;
- resulting route.

### Rollback

Disable/revert R1.

The prompt must again resolve according to R0.

This is the minimum credible proof of experience-driven behavioural adaptation.

---

# Evidence hierarchy

Use the following order when evaluating adaptation evidence:

1. explicit durable user instruction;
2. explicit user confirmation/correction with clear persistence semantics;
3. repeated behavioural evidence;
4. measurable task outcome;
5. deterministic evaluation;
6. model critique;
7. persona/self-rating.

Do not infer a persistent preference from one unexplained manual switch.

Null evidence is better than fabricated certainty.

---

# Confidence

If confidence scoring is used, keep it interpretable.

Do not introduce an opaque learned model merely to assign affinity confidence.

Confidence should be explainable through evidence count, type, consistency, recency or another documented simple mechanism.

Do not allow confidence alone to bypass authority requirements.

---

# Trace requirements

Every adaptation-related trace should distinguish:

- what the deterministic router originally selected;
- what evidence occurred;
- how that evidence was interpreted;
- whether state remained shadow or became active;
- why a candidate changed;
- who/what authorised promotion;
- what routing revision became effective;
- whether the final route depended on learned state.

The trace should support:

> "Why did Misumi choose this persona?"

without exposing private chain-of-thought.

Use structured reasons and provenance, not hidden reasoning.

---

# Persistence

Persistent routing adaptation must survive restart once promoted.

Shadow candidates should also survive restart unless the current architecture has a documented reason not to persist them.

Test persistence deliberately.

Do not claim durable learning if the state disappears with the process.

---

# Reversibility

Every active routing revision must be reversible.

Rollback should restore prior effective behaviour without deleting historical evidence.

Never implement rollback by erasing the evidence that caused the revision.

History remains immutable.

Effective state changes.

---

# User-visible behaviour

Do not build a developer-only feature.

Once a promoted routing preference exists, Misumi's behaviour should visibly differ.

Where UI integration is available:

- Auto mode should select the newly learned leader;
- the room should follow that leader;
- the trace should explain the selection.

If the physical kiosk remains unavailable, demonstrate everything available through the deployed runtime and preserve physical UI acceptance as an operator-only frontier.

Do not block this application solely on that physical dependency.

---

# Testing

At minimum include:

- evidence-event unit tests;
- candidate aggregation tests;
- correction vs temporary-choice tests;
- explicit durable-preference tests;
- contradictory evidence tests;
- promotion-gate tests;
- active-routing revision tests;
- rollback tests;
- restart persistence tests;
- baseline fixture regression tests;
- adversarial/paraphrase routing tests;
- live deployed-runtime proof.

Do not weaken existing tests to make the new feature pass.

---

# Scope constraints

Do NOT use this stage to implement:

- general persona personality evolution;
- prompt self-rewriting;
- autonomous persona creation;
- multi-persona debate;
- voice differentiation;
- large knowledge graphs;
- generic reinforcement learning;
- embedding-heavy preference models unless genuinely necessary;
- social-media history ingestion;
- broad memory redesign;
- unrelated infrastructure cleanup.

If such work is not necessary to prove controlled routing adaptation, defer it.

---

# Operator-only frontiers

Carry these without allowing them to dominate the stage:

- physical kiosk acceptance;
- memory policy ratification where explicit operator ratification is required;
- backup credentials/inputs;
- lab sudo deployment;
- physical console hardening actions;
- any remaining v3 closeout review requiring explicit model/operator availability.

Proceed around independent operator gates.

---

# Long-horizon execution loop

Repeat:

## 1. Reconcile

Establish current code, deployment, policy and evidence truth.

## 2. Select one bounded increment

Choose the smallest next change required to complete the adaptation causal chain.

## 3. State hypothesis

Record:

- expected behaviour;
- implementation mechanism;
- falsification condition;
- evidence required.

## 4. Implement

Make the minimum coherent change.

## 5. Test

Run unit, integration, regression and behavioural tests.

## 6. Deploy

Exercise the real runtime where possible.

## 7. Evaluate

Record success, failure, regression and uncertainty.

## 8. Update candidate state

Only according to preserved evidence.

## 9. Promote only if authorised

Otherwise leave the candidate in shadow/eligible state.

## 10. Reconcile evidence

Update application trace, evidence register and evolution graph.

Preserve failures.

## 11. Continue

Proceed autonomously to the next bounded non-blocked increment until stage acceptance is reached or a genuine operator-only gate prevents further progress.

Do not stop merely because one PR merged.

---

# Stage acceptance criteria

Application `-07` is complete only when:

- current routing baseline has a small generalisation/adversarial test set;
- interaction evidence semantics distinguish correction from temporary and durable preference;
- routing evidence is persisted;
- candidate affinity state exists independently from active routing;
- shadow evaluation works;
- candidate provenance is inspectable;
- promotion obeys existing authority rules;
- one candidate has been promoted if authority is available;
- the promoted preference changes a future route;
- the changed route is explainable from persisted evidence;
- the change survives restart;
- rollback restores previous routing behaviour;
- existing routing fixtures remain acceptably intact;
- failures and rejected candidates remain preserved;
- live/deployed proof exists where feasible;
- physical-only acceptance is clearly separated from software proof;
- application evidence is reconciled.

If ratification authority prevents promotion, complete every preceding criterion, record the precise operator gate, and do not falsely mark the full stage complete.

---

# Success criterion

The important result is not:

> "Misumi stores routing preferences."

It is:

> "Misumi can learn a bounded routing preference from evidence, hold it in shadow state, prove that the proposed change is safe, activate it through authorised promotion, behave differently because of it, explain exactly why, and revert it without losing history."

That is the first credible form of Misumi learning from experience.

Begin with reconciliation, then continue directly into the first non-blocked implementation work package.

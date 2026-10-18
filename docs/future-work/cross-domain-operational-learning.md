---
title: Cross-domain operational learning
status: future-work
owner: odysseus
as_of: 2026-09-11
parent: docs/aoteru-autonomous-programme-state.md
---

# Cross-domain operational learning

## Goal

Enable Aoteru's flat knowledgebase to learn from structurally parallel relationships observed across domains, abstract the transferable operational principle, and propose bounded application of that principle elsewhere.

The capability should learn **relationships and policies**, not surface analogies.

## Motivating example

Aoteru already routes model effort according to factors such as task requirements, model capability, cost and available usage. A structurally related policy could route flat priorities according to task value, required capability, urgency and available human capacity.

Do not encode "model usage is human capacity". The candidate invariant is closer to:

```text
finite heterogeneous resource
+ competing tasks
+ differing task requirements
+ variable capacity
-> adaptive allocation policy
```

Other candidate parallels may include model routing, human workload allocation, experiment scheduling, literature-review effort, expert escalation and compute allocation.

## Desired learning loop

```text
observe pattern
-> abstract relationship
-> identify analogous context
-> propose bounded transfer
-> evaluate outcome
-> retain, revise or reject
```

## Representation requirements

A transferable relationship should preserve at least:

- source context;
- observed relationship or policy;
- abstracted invariant;
- target context;
- transfer hypothesis;
- boundary conditions and known disanalogies;
- evidence/provenance;
- evaluation method;
- observed outcome;
- disposition: retain, revise or reject.

Keep the invariant separate from both source and target instances so later learning does not collapse distinct domains into one ontology.

## Boundary

Default mode is **observe -> abstract -> propose -> test**, not automatic policy transfer.

- Domain-specific authority remains with the source/target domain.
- A structural similarity is a hypothesis, not evidence that a policy transfers.
- Preserve provenance and explicit boundary conditions for every proposed transfer.
- Reject seductive but shallow analogies that cannot state a meaningful invariant or testable transfer hypothesis.
- Do not let successful transfer in one target silently generalise to others.
- Do not create a parallel knowledgebase, ontology or routing authority to implement this capability.

## Initial implementation route

Treat this first as a research/design capability. Before autonomous transfer exists:

1. inspect the current flat-memory/knowledge representation and identify the smallest place to represent relational invariants;
2. define candidate detection and abstraction without replacing domain-native knowledge;
3. create a small evaluation corpus containing valid parallels, partial parallels and false analogies;
4. test whether Aoteru can distinguish transferable structure from superficial similarity;
5. only then prototype bounded recommendations that remain human- or policy-gated where required;
6. feed evaluated outcomes back into the relationship record so the knowledgebase learns whether the transfer actually held.

## Acceptance

- Aoteru can represent one relationship independently of its source-domain wording.
- At least one PhD-derived relationship is mapped to a distinct operational domain with explicit invariant and boundaries.
- False/superficial analogy cases are included in evaluation and are not promoted as transferable policies.
- Every proposed transfer is provenance-bearing and testable.
- Transfer outcomes can revise or invalidate the stored relationship.
- No source-domain authority, safety constraint or local policy is overridden by analogy.
- The capability extends the existing flat knowledgebase rather than introducing a second semantic or routing architecture.

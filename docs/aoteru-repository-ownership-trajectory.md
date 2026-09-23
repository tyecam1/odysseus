# Repository ownership trajectory

## Purpose

Odysseus is being built while `obsidian-PhD` is still the established working repository for agentic orchestration. That is a **transitional implementation state**, not the intended long-term ownership boundary.

Do not prematurely move or delete working infrastructure while the backend is still converging. Preserve the existing task trail as provenance, then perform a deliberate ownership/migration pass once the backend is operationally complete.

## Target steady state

The intended topology is:

- **Odysseus**: shared backend/runtime and cross-repository agentic capabilities. It manages routing, execution, workers, leases, lifecycle, common orchestration primitives and other capabilities that are genuinely backend-wide.
- **obsidian-PhD**: the canonical **PhD knowledgebase**. It owns PhD research knowledge, evidence, research workflows, PhD-specific policies and its own agentic task queue.
- **Aoteru personal knowledgebase**: the canonical **personal knowledgebase**, separate from the PhD vault, with its own agentic task queue.
- The same Odysseus backend manages both knowledgebases with minimal friction while respecting each repository's independent content authority and task queue.

The canonical repository/path for the Aoteru personal knowledgebase may be resolved downstream. Do not assume that the Odysseus backend repository itself is the personal knowledgebase merely because the lab checkout is named `odysseus-aoteru`.

## Current transitional state

During backend construction, `obsidian-PhD` has legitimately accumulated two kinds of material:

1. PhD-domain knowledge and research workflow artefacts that belong there permanently.
2. Backend-oriented agentic infrastructure, orchestration tasks and reusable capabilities that were developed there because it was the functioning agent workspace before Odysseus was ready.

The current Odysseus implementation task trail in `obsidian-PhD`—including the staged implementation operating task introduced by PR #575—is therefore valid **transitional provenance**. Its current location must not be interpreted as the desired final ownership of those capabilities.

Do not migrate, duplicate or delete that trail during the active multihost/backend implementation unless required for correctness.

## Downstream convergence

Once the Odysseus backend reaches its implementation/acceptance boundary, run an explicit repository-boundary convergence pass.

That pass must:

1. inventory agentic functions, queue machinery, review/adjudication workflows, routing helpers, reusable automation and backend policy currently living in `obsidian-PhD`;
2. classify each item by authority and reuse rather than by historical location;
3. ingest/migrate genuinely backend-wide capability into Odysseus;
4. leave PhD-specific knowledge, methods, evidence, workflow and task semantics in `obsidian-PhD`;
5. establish/confirm the Aoteru personal knowledgebase and its independent task queue;
6. make both domain queues usable through the same Odysseus backend without merging their content authority;
7. remove or supersede duplicate backend machinery only after the migrated path is proven;
8. then document the final boundary inside `obsidian-PhD` as well.

Historical task records may remain as provenance even after their executable/backend role is superseded.

## Placement rule for agents

Do not use a simplistic file-extension or directory rule. Determine final ownership from function:

- **Domain content or domain-specific workflow** stays with the domain repository that owns it.
- **Generic execution/orchestration/runtime capability used across repositories** belongs in Odysseus.
- **Repo-specific task queues** remain separate even when the queue engine/runtime is shared.
- **Cross-repo policy** should live at the lowest shared authority that can enforce it without taking ownership of domain content.
- Prefer one shared implementation over duplicated machinery where the semantics are genuinely common.
- Prefer separation where combining components would couple PhD and personal knowledge unnecessarily.

Optimize for minimum future operational overhead, clear authority and low-friction use—not for preserving today's accidental file locations.

## Current implementation implication

The active multihost implementation should continue from its existing task trail and branch. Do not stop Stage 6–9 work to perform the downstream repository migration.

When the backend reaches the completion boundary, surface this convergence as an explicit next work package/operator checkpoint rather than silently migrating files during another stage.

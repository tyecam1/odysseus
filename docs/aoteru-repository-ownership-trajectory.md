# Repository ownership trajectory

## Purpose

Odysseus is the shared backend/runtime for both the PhD and personal knowledge estates. During its construction, `obsidian-PhD` also served as the established agent workspace, so backend-oriented task records and capability prototypes accumulated there. Their historical location is not their long-term authority.

The task-queue ownership migration began on 2026-09-23. Backend/shared task records may therefore move before all referenced implementation/output artefacts are migrated. Capability/file convergence remains a separate, evidence-backed pass.

## Target steady state

- **Odysseus**: shared backend/runtime and cross-repository agentic capability. It owns routing, execution, workers, leases, lifecycle, provider/model routing, generic orchestration, shared task-engine primitives, reusable agent skills/runtime, cross-repository observability and other backend-wide capability.
- **obsidian-PhD**: canonical **PhD knowledgebase** with its own task queue. It owns PhD research knowledge, evidence, literature/Zotero, research methods, writing, supervision, university work, PhD-specific workflow and PhD-vault-specific operational provenance.
- **Aoteru personal knowledgebase**: canonical **personal knowledgebase**, separate from the PhD vault, with its own task queue. It **relies on the Odysseus backend** rather than duplicating shared execution/orchestration capability.
- **Misumi/personal-domain repository**: owns only capability/content whose semantics are genuinely Misumi/personal-domain specific. Shared Aoteru execution infrastructure remains in Odysseus.

The same Odysseus backend manages the separate domain queues with minimum friction while preserving each repository's independent content authority.

The canonical repository/path for the Aoteru personal knowledgebase may be resolved downstream. Do not infer that the Odysseus backend repository itself is the personal knowledgebase merely because a checkout is named `odysseus-aoteru`.

## Placement rule

Classify by **authority and reuse**, not by historical location, filename or which backend executes the task.

- A task whose primary subject is PhD research/domain work remains in `obsidian-PhD`, even if Odysseus executes it.
- A task whose primary subject is a PhD-vault-specific operation may remain in `obsidian-PhD` as domain provenance, even when a reusable implementation is later extracted into Odysseus.
- A task whose primary subject is shared routing/execution/orchestration/runtime capability belongs in Odysseus.
- Aoteru/personal tasks remain in the personal queue; only Misumi-specific capabilities belong in the Misumi/personal capability repository.
- Repo-specific task queues remain separate even when the queue engine/runtime is shared.
- Cross-repo policy should live at the lowest shared authority that can enforce it without taking ownership of domain content.

Prefer one shared implementation where semantics are genuinely common. Prefer domain separation where combining components would couple PhD and personal knowledge unnecessarily.

## 2026-09-23 task-queue migration

The first convergence pass moves backend/shared **agent-task records** out of `obsidian-PhD` into the Odysseus queue. The paired migration manifest is `automation/review/agent-task-migration-20260923.md`.

This pass deliberately does not blindly relocate every script, config file, report or historical output referenced by those tasks. Those artefacts are migrated only when their capability authority is established and the replacement path is proven.

Historical mixed-queue audit reports may remain in `obsidian-PhD` because they describe the state of that repository at the time.

## Downstream capability convergence

After the active multihost/backend stages reach their implementation/acceptance boundary, run an explicit capability/file convergence pass:

1. inventory reusable agentic functions, queue machinery, review/adjudication workflows, routing helpers, automation and backend policy still living in domain repos;
2. classify each item by authority and reuse;
3. migrate genuinely backend-wide capability into Odysseus;
4. retain PhD-specific knowledge/workflow/provenance in `obsidian-PhD`;
5. confirm the Aoteru personal knowledgebase and its independent queue;
6. keep only Misumi/personal-domain-specific capability in the corresponding personal repository;
7. prove migrated paths before deleting/superseding duplicates;
8. document the final boundary in each affected domain repository.

Optimize for minimum future operational overhead, clear authority and low-friction use.

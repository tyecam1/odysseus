# Agent-task ownership migration — 2026-09-23

## Decision

The historical `obsidian-PhD` estate mixed PhD-domain work with development of the shared Odysseus/Aoteru backend. This migration separates task **authority** without pretending that every referenced implementation/output artefact has already moved.

- Odysseus owns backend-wide and reusable cross-repository agent capabilities.
- `obsidian-PhD` owns PhD research, research-method, evidence, writing, supervision, Zotero/literature, research-engine objectives, and PhD-vault-specific operational provenance.
- The Aoteru personal knowledgebase also relies on the Odysseus backend rather than duplicating shared runtime/orchestration.
- Only capability/content whose semantics are genuinely Misumi/personal-domain specific belongs in the corresponding personal-domain repository.
- No source task in this migration had primary Misumi/household authority, so nothing is moved to `tyecam1/misumi`.

## Migration scope

The Odysseus queue now contains **63 migrated backend/shared task records**.

From `obsidian-PhD/main`:
- 45 backend/shared agent-task records move from `automation/review/agent-tasks/**`;
- 4 backend work items move out of `10-inbox/` and are converted into `agent-task/v2` inbox records;
- 4 July records initially considered generic were deliberately retained in the PhD queue after authority review: `engine-loss-and-credit-assignment`, `hybrid-retrieval-routing-benchmark`, `research-engine-sleep-consolidation`, and `asi-evolve-lesson-skill-compilation-and-graph-fitness`.

From unmerged PhD branches/PRs:
- PRs #516, #541, #563, #574 and #575 retain open queue states;
- PRs #556 and #557 are converted from backend `10-inbox` work items into Odysseus inbox tasks;
- PRs #565, #566, #568, #569, #570, #572 and #573 had already been executed and are archived under `done/`;
- the updated `2026-09-01-human-attention-wip-autonomous-dispatch` task is imported from PR #540 because that branch holds the latest task contract. PR #540 also contains implementation changes and is therefore **not** treated as a task-only PR.

The paired `obsidian-PhD` cleanup branch removes the 45 migrated main-branch task records plus the 4 migrated main-branch backend work items and adds a queue-ownership README.

## Classification rule

“Uses Odysseus” is not enough to move a task.

Keep a task with its domain when its primary authority is domain knowledge/workflow, even when Odysseus executes it. Examples retained in the PhD queue include J1/S2 research, Zotero/literature, research-engine objectives, research integrity, supervision, scientific writing and PhD-vault-specific operations.

Move a task to Odysseus when its primary subject is shared routing, execution, workers, leases/lifecycle, model/provider routing, generic orchestration, reusable skill/runtime mechanics, cross-repository memory/runtime, capability convergence or backend observability.

## Boundary

This pass migrates **task/work-item records and queue ownership**. It does not blindly relocate every historical result, script, configuration file, decision packet or review artefact referenced by those tasks.

Reusable capability/output files still located in `obsidian-PhD` are classified and converged separately after the active backend implementation reaches its acceptance boundary. Historical mixed-queue audits remain in `obsidian-PhD` as provenance because they describe that repository's state at the time.

## Reintroduction rule

Do not add new shared/backend tasks to `obsidian-PhD` merely because that vault is convenient. Put them in the Odysseus queue and target the relevant domain repository through the shared backend.

Do not move PhD or personal-domain tasks merely because Odysseus executes them. Domain queues remain independent.

# Agent-task ownership migration — 2026-09-23

## Decision

The historical `obsidian-PhD` queue mixed PhD-domain work with development of the shared Odysseus/Aoteru agent backend. This migration separates task **authority** without pretending that all historical implementation outputs have already moved.

- Odysseus owns backend-wide and reusable cross-repository agent capabilities.
- `obsidian-PhD` owns PhD research, research-method, evidence, writing, supervision, Zotero/literature and PhD-vault-specific operational tasks.
- The personal Aoteru/Misumi domain remains separate and uses the Odysseus backend; only personal/Misumi-specific capability belongs in that domain repository.
- No source task in the PhD queue was found whose primary authority was Misumi/household, so this migration moves nothing to `tyecam1/misumi`.

## Migration scope

49 backend/shared task records present on `obsidian-PhD/main` were copied into the equivalent queue state here and are removed by the paired PhD cleanup PR.

Additional live task records were imported from unmerged PhD task PRs:
- PRs #516, #541, #563, #574 and #575 retain their open queue states;
- PRs #565, #566, #568, #569, #570, #572 and #573 had already been executed and are archived here under `done/`.

The updated `2026-09-01-human-attention-wip-autonomous-dispatch` task was imported from PR #540 because that branch contains the latest task contract. PR #540 also contains implementation changes and is therefore **not** treated as a task-only PR by this migration.

## Boundary

This pass migrates agent-task records and queue ownership. It does **not** blindly relocate every historical result, automation script, configuration file or review artefact referenced by those tasks. Those capability/output files are classified and converged separately under the repository-ownership trajectory after the active backend stages are complete.

Mixed historical queue-audit documents such as the 2026-07-18 reconciliation/verification reports remain in `obsidian-PhD` as provenance because they audited the then-mixed PhD queue rather than constituting backend tasks themselves.

## Reintroduction rule

Do not add a new shared/backend task to `obsidian-PhD` merely because that vault is convenient. Put the task in this queue and target the relevant domain repository through Odysseus. Keep a task in a domain queue when its primary authority is that domain's content/workflow, even if Odysseus executes it.

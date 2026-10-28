# Multi-deployment isolation

## Objective

Make domain isolation a startup and test invariant when one Odysseus harness serves separate Misumi and PhD deployments.

## Requirements

- unique, explicit data directory, source roots, auth, memory, vector index, uploads, jobs, skills, integrations and credentials per deployment;
- no permissive shared default when configuration is missing;
- source-root and writable-path allowlists;
- owner-scoped sessions and jobs;
- startup rejection for overlapping paths or identifiers;
- tests for symlinks, path traversal, shared indexes, cross-domain retrieval, task dispatch and credential reuse.

## Acceptance criteria

Deliberately overlapping configurations fail startup, separate fixtures cannot retrieve or enumerate one another, and diagnostics identify the exact collision without printing private data.

## Implementation

Enforcement lives in `src/deployment_isolation.py` and is opt-in: `ODYSSEUS_DEPLOYMENT_ISOLATION=required` turns it on. Unset keeps today's single-household behaviour so nothing live changes before acceptance; **a multi-deployment launch must set it** (the Windows lifecycle script does with `-RequireIsolation`). `src/constants.py` calls `enforce_startup_or_exit()` before `DATA_DIR` is used; a refusal prints a non-sensitive diagnostic and exits 78 before any state is created.

Required when enabled: `ODYSSEUS_DEPLOYMENT_ID`, `ODYSSEUS_DEPLOYMENT_DOMAIN` (`misumi` or `phd`), an absolute `ODYSSEUS_DATA_DIR` (no default), and at least one existing source root for the domain (e.g. `MISUMI_HOUSEHOLD_ROOT`, `BBC_OBSIDIAN_PHD_ROOT`). Optional: `ODYSSEUS_CREDENTIAL_IDS` (comma-separated non-secret identifiers) and `APP_PORT` for pair checks.

Single-deployment checks:

- relative paths, `..` segments and symlink/junction/case aliases are refused; roots are compared by path component after `realpath`/`normcase`;
- source roots may not overlap the data root; every writable override (`ODYSSEUS_MAIL_ATTACHMENTS_DIR`, `ODYSSEUS_INSTAGRAM_EXPORTS_DIR`, `ODYSSEUS_STT_TMP_DIR`, `ODYSSEUS_META_EXPORT_BROWSER_PROFILE`, `FASTEMBED_CACHE_PATH`, `MISUMI_*_STATE_ROOT`, `MISUMI_EVENT_LOG`) must be inside the data root;
- any opposite-domain root variable in the environment is refused even when this deployment's own parameter is empty (Misumi: `MISUMI_HOUSEHOLD_ROOT`, `MISUMI_SOURCE_ROOT`, `BBC_MISUMI_ROOT`, `FLAT_KNOWLEDGEBASE_ROOT`, `MISUMI_SEED_ORDER_ROOT`, `MISUMI_CANONICAL_ROOT`; PhD: `BBC_OBSIDIAN_PHD_ROOT`, `OBSIDIAN_PHD_ROOT`); `BBC_ODYSSEUS_ROOT` and `MISUMI_PERSONA_POLICY_PATH` must stay inside the deployment or the application;
- `.odysseus-deployment.json` binds a data root to one id and domain. It is published complete with a hard link (never created empty), read with `O_NOFOLLOW` plus an identity check, and never overwritten; a data root nested inside, or containing, another deployment's marked data root is refused before anything is created.

Runtime boundaries (while isolation is required), all at existing shared choke points:

- file tools and workspace binding: `_tool_path_roots()` returns only the data root and own source roots (no `/tmp`, `$TMPDIR` or `tool_path_extra_roots`), re-verified on every call so a root swapped for a link after startup disables file tools; `vet_workspace()` refuses a workspace outside them;
- estate dispatch, park leases, worktrees and workers: `estate_router.resolve_repo_path()` returns nothing for a repo that resolves outside the deployment;
- shell-equivalent surfaces cannot be path-confined, so they are refused unless the operator sets `ODYSSEUS_ISOLATION_ALLOW_SHELL=1` (and relies on OS-level separation, e.g. a distinct service account): the `bash`/`python` tools, `bg_jobs.launch`, the shell routes, the cookbook routes, and every custom stdio MCP connection (registration, reconnect and startup auto-connect; built-in servers are unaffected);
- credentials: an `ODYSSEUS_INTERNAL_TOKEN` supplied through the environment is bound to the deployment identity and data root, so the same inherited value cannot authenticate against a sibling; `validate_pair` / `python -m src.deployment_isolation check ENV.json ...` also refuses a shared raw token, credential id, port, deployment id or writable path;
- sessions, jobs, schedules, memories, vector indexes, uploads, skills and OAuth state live under `DATA_DIR` and so are per-deployment by construction (tested against the real constants and managers).

Windows host: `scripts/windows/odysseus-host.ps1 -RequireIsolation -DeploymentId <id> -DeploymentDomain <misumi|phd>` needs an explicit `-DataRoot`, removes every root the domain does not own from the process environment, and runs `python -m src.deployment_isolation validate` **before** `Install` or `Run` creates any directory, log or scheduled task.

Evidence (disposable synthetic fixtures only): `tests/test_deployment_isolation.py`; and `scripts/deployment_isolation_acceptance.py --fixtures <Misumi fixtures/deployment-isolation>`, which starts a Misumi and a PhD instance on loopback ports with independent roots and a deliberately shared raw token, and exercises startup, sessions, memory, schedules, source enumeration, credentials, overlap/alias/missing-configuration refusals and restart in both directions.

Known limits (not claimed): shell-equivalent access is OS-level, not path-level, when the operator opts in; a single process cannot see a sibling's configuration, so two data roots that reuse one deployment id are caught only by the pair-check command at the deploy gate (no central registry was added; the per-data-root marker and the pair check were sufficient for the acceptance matrix); the cross-domain park/dispatch path is exercised through the real estate route in-process, not through a live two-instance estate run; Windows junction and case-alias behaviour is covered by path normalisation and a Windows-only test that has not been run on Windows; DNS or network-level separation is out of scope.

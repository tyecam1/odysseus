# Ultrareview contract - autonomous research system (2026-11-10)

This file is the reviewer's brief. It is part of a synthetic review branch and is never merged.

## How this diff was built
- `ultra/20261110-integ` = `main` plus normal merges of the open J2 stack head (#658, which contains #657, #652, #635, #617 and #615), #659, #654 (voice audit integration), #664 (sequential human and agent handoff) and #667.
- The PR base rewinds a selected set of automation source paths to their 2026-08-15 state, so the diff shows three months of merged and unmerged work on the research automation only. Everything else is at its integrated state and is available as context.
- Tests are deliberately outside the diff to fit the size limit. They exist under `Scripts/tests/` and `Scripts/automation/tests/`. Read and run them; report behaviour they do not cover.
- **This is a code review. Manuscript text, literature evidence and research claims under `automation/review/` and the vault notes are not under review and must not be judged or edited.**

## What this system is
An Obsidian vault for a PhD with an automation layer in `Scripts/automation/` (entry point `cli.py`). Agents draft into the non-canonical staging area `automation/review/`; canonical notes change only through a propose, review and ratify path with human approval. The automation audits work items, exports bibliographies, maintains supervision records with a fail-closed publish gate, checks manuscript references and claims, lints agent task cards, and gates drafting on a voice audit. `automation/config/` holds model routing and execution policy.

## Review priorities, in order
1. **Canonical boundary and approval gates.** Any path by which automation can write, publish or promote outside `automation/review/` without the recorded approval: `supervision_record_updater.py` (approval binding, baseline advancement, lifecycle, publish gate), `sequential_experiment_handoff.py`, `work_item_planning.py`, the `.claude` hook. Look for time-of-check to time-of-use gaps, approvals that bind to the wrong content hash, gates that pass on error or on empty input, and partial writes.
2. **Evidence integrity tooling.** `check_j2_refs.py`, `verify_bib_metadata.py`, `run_uniform.py`, `bibtex_export.py`, `zotero_reference_repair.py`: cases where a check reports success without having checked (empty input, parse failure swallowed, network failure treated as a pass), citation keys or DOIs matched loosely enough to accept the wrong paper, and model output trusted without the quotation being re-verified mechanically.
3. **Duplicated capability.** Find logic implemented more than once across these modules and against the rest of `Scripts/automation/`: frontmatter and YAML parsing, work-item and task-card loading, path resolution, atomic file writes, model invocation, BibTeX parsing, report rendering. Name the single owner each should have. Also flag one-off scripts under `automation/review/J2/**` that should be a reusable pipeline stage in `Scripts/automation/`.
4. **Routing and policy configuration.** `agent_routing.yaml`, `model_execution_policy.yaml`, `config.py`: stale or pinned model versions, policy entries no code reads, code paths that bypass the policy, behaviour when the preferred model is unavailable.
5. **Operational robustness and cost.** Resumability after interruption, idempotence on re-run, unbounded model-call fan-out, whole-vault scans where an index would do, Windows and Linux path handling (the system runs on both), the PowerShell scheduled-task installers.
6. **Lint and gate soundness.** `agent_task_lint.py`, `validator.py`, `voice_audit_ci.py`, `drafting_targets.py`, `work_item_audit.py`: rules that can be satisfied trivially, baselines that silently grow, and audits whose exit code does not reflect their findings.

## Out of scope
Scientific validity, manuscript prose, documentation wording, the teaching material, and files outside the diff except as context.

## Reporting
For each finding give file and line, a concrete failing input or state, and the smallest fix. Mark consolidation findings separately from bugs. Prefer a few verified high-impact findings over many speculative ones.

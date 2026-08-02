---
artifact_type: workflow
task_schema: agent-task/v2
task_id: 2026-08-02-zotero-broken-reference-repair-classification
title: "Classify every broken citekey and stale bibliography reference into a tested, human-gated repair manifest"
status: ready
priority: high
task_type: literature-integrity-audit
created_by: claude
created_at: 2026-08-02T12:10:00+01:00
updated_at: 2026-08-02T12:10:00+01:00
executor: codex_subscription
execution_mode: implementation
architecture: single-plus-verifier
architecture_rationale: "One sequential deterministic classifier over one shared input report writing one manifest. Not decomposable: every classification rule depends on the same citekey index. Single-agent baseline is strong. A separate verifier is required because the failure mode is a classifier silently marking unresolved cases as deterministic."
single_agent_baseline: "A single implementation agent writes one classifier module plus unit tests and emits the manifest; the risk is self-certification, not capacity."
execution_host: laptop
context_budget: medium
coordination_reason: "The verifier must be a different model attacking the classifier's ability to render an unresolved identity as a deterministic rename, which the implementer cannot do credibly against its own rules."
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: codex/zotero-broken-reference-repair-classification-20260802
allowed_paths:
  - automation/review/zotero-repair/**
  - automation/review/agent-tasks/**
  - Scripts/automation/**
  - automation/docs/**
  - automation/config/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
  - 12-log/**
  - 10-inbox/**
  - 11-projects/**
  - "**/*.bib"
  - "**/*.pdf"
inputs:
  - automation/review/zotero-vault-trajectory/trajectory-gap-report.json
  - automation/review/zotero-vault-trajectory/coverage-ledger.csv
  - automation/review/zotero-vault-trajectory/duplicate-and-metadata-findings.csv
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
outputs:
  - automation/review/zotero-repair/repair-manifest.csv
  - automation/review/zotero-repair/repair-manifest.json
  - automation/review/zotero-repair/classification-report.md
  - Scripts/automation/zotero_reference_repair.py
  - Scripts/automation/tests/test_zotero_reference_repair.py
result_path: automation/review/zotero-repair/classification-report.md
review_report_path: automation/review/zotero-repair/classification-report.md
handoff_model: claude_codex_review_package
operator_decision_path: automation/review/zotero-repair/classification-report.md
supersedes: []
duplicates: []
notes: "Read-only against 02-library/**. No BibTeX, PDF, Zotero or canonical vault mutation is authorised. Patches must be generated and validated against a disposable copy only. The 135/83 aggregates must be replaced by per-finding rows; no finding may remain an unexplained count."
---
# Classify every broken citekey and stale bibliography reference

## Measured input state (2026-08-02)

`automation/review/zotero-vault-trajectory/trajectory-gap-report.json`
(`schema_version: zotero-vault-trajectory/v1`, generated 2026-07-28, marked
`advisory_only: true`) contains:

- `broken_reference_findings`: **135** entries, all
  `finding_type: broken-citekey-reference`;
- `metadata_findings`: **89** entries, of which the
  `stale-bibliography-reference` subset is the reported 83 — the classifier
  must count this subset from the data and fail loudly if it is not 83;
- `zotero_mirror.available: false` with
  `zotero-sqlite-missing` at a laptop path that does not exist. The audit's
  Zotero-side reconciliation is therefore
  `excluded-mirror-unavailable`, **not** zero.

A live read-only Zotero mirror does exist on the compute box at
`/home/agent/projects/data` (`zotero.sqlite`, `storage/`, `better-bibtex/`).
Re-running the audit against it is task
`2026-08-02-zotero-live-mirror-audit-rerun` and is **not** in scope here.
This task classifies the findings that already exist.

## Goal

Emit one manifest row per finding — 135 + the stale-bibliography subset — with
every field below populated or explicitly `not-determined`. No aggregate count
may stand in for a row.

## Required manifest columns

`finding_id`, `finding_type`, `source_file`, `line_or_field`,
`current_identifier`, `expected_identifier`, `match_method`, `evidence`,
`ambiguity`, `affected_claims_or_notes`, `recommended_action`, `rollback`,
`approval_requirement`, `classification`.

`classification` is one of exactly:

`deterministic-rename`, `missing-paper-note`, `stale-export`,
`unresolved-identity`, `duplicate-identity`, `malformed-historical-reference`,
`intentionally-superseded-reference`, `false-positive`.

## Hard rules for the classifier

1. `deterministic-rename` requires an exact, single, reproducible target: a
   citekey present in `02-library/00-papers/**` frontmatter or in a configured
   `.bib` citekey index, reachable by a normalisation rule that is implemented
   in code and covered by a unit test. Fuzzy or best-guess matches are
   `unresolved-identity`.
2. If a normalisation rule yields more than one candidate, the row is
   `duplicate-identity`, never `deterministic-rename`.
3. `expected_identifier` must be empty for every classification that is not
   `deterministic-rename` or `stale-export`.
4. Every row carries a `rollback` that names the exact inverse edit.
5. `approval_requirement` is `human` for every row that would touch
   `02-library/**`, any `.bib`, or Zotero. There is no `agent` value for
   those surfaces.
6. Counts must be derived, printed, and asserted: total rows == total input
   findings. A dropped finding must fail the run, not shrink the manifest.

## Patch validation (no canonical mutation)

Deterministic repairs must be proven on a **disposable copy**:

- copy the affected files to a scratch directory outside the repo;
- apply the generated patch there;
- re-run the broken-reference detector over the scratch copy;
- record before/after counts in `classification-report.md`.

Patches for canonical paths are emitted as artifacts under
`automation/review/zotero-repair/patches/`; they are never applied in-tree.

## Acceptance

- all 135 broken-citekey findings classified, one row each;
- all stale-bibliography findings classified, count derived from data and
  asserted against 83;
- deterministic repairs tested on a disposable copy with before/after counts;
- unresolved cases reduced to grouped operator decisions in the report;
- unit tests cover: each normalisation rule, the multi-candidate →
  `duplicate-identity` path, the row-count assertion, and the refusal to emit
  `expected_identifier` for non-rename classes;
- `python -m unittest Scripts.automation.tests.test_capability_truth_contracts`
  passes and both capability-truth documents are updated in the same change;
- no file under `02-library/**`, no `.bib` and no PDF is modified.

## Adversarial questions the verifier must answer with counterexamples

- Can an `unresolved-identity` render as `deterministic-rename`?
- Can a dropped finding shrink the manifest without failing?
- Can the stale-bibliography count be reported as 83 when the data says
  otherwise?
- Can a patch be described as validated when the disposable-copy run did not
  execute?
- Can `zotero_mirror.available: false` be read as a zero rather than
  not-computed?

---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-12-odysseus-central-interface-registry
title: Implement Odysseus central interface registry scaffold
status: done
priority: high
task_type: implementation
created_by: chatgpt
created_at: 2026-06-12T12:45:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/routine-reports/odysseus-interface-health/**
  - automation/review/agent-tasks/**/2026-06-12-odysseus-central-interface-registry.agent-task.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/architecture/2026-06-12-odysseus-central-interface-convergence-plan.md
  - automation/review/architecture/odysseus-consolidated-system-design.md
  - automation/docs/agent-ecosystem-centralisation-design.md
  - automation/docs/agent-task-centralisation-plan.md
  - automation/docs/odysseus-action-integrations.md
  - automation/review/agent-jobs/2026-06-12-context-parity-diagnostics.codex/diagnostics-report.md
outputs:
  - automation/config/odysseus_interface_sources.yaml
  - automation/docs/odysseus-central-interface-contract.md
  - automation/docs/odysseus-object-import-schema.md
  - automation/docs/odysseus-asset-gallery-schema.md
  - automation/review/routine-reports/odysseus-interface-health/<date>.odysseus-interface-health.{json,md}
result_path: automation/review/routine-reports/odysseus-interface-health/2026-06-16.odysseus-interface-health.md
review_report_path: automation/review/routine-reports/odysseus-interface-health/2026-06-16.odysseus-interface-health.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Implement the scaffold only: one central Odysseus interface source registry, object/import schemas, asset-gallery schema, and read-only health-report command/tests. Do not enable live Odysseus writes, task-transition, calendar mutation, HF sync, or canonical writes. Implementation change scope (automation/config, automation/docs incl. capability docs, Scripts/automation + tests) is PR-gated and stays in the task body, not allowed_paths (lint: allowed-path-outside-review; precedent: 2026-06-10-elongate-odysseus-timeouts)."
---

# Task: Implement Odysseus central interface registry scaffold

## Objective

Make Odysseus structurally capable of becoming the single interface for the agentic ecosystem by giving it one explicit source registry over vault knowledge, task state, agent routines, Odysseus-native library objects, calendar snapshots, assets/gallery objects, model comparison/browser surfaces, and curated Hugging Face exports.

This task is a scaffold and contract implementation. It must not widen authority.

## Required changes

1. Add `automation/config/odysseus_interface_sources.yaml` with registered sources for:
   - `vault_canonical`
   - `agent_tasks`
   - `agent_outputs`
   - `skill_registry`
   - `odysseus_library_export`
   - `assets_gallery`
   - `calendar`
   - `model_comparison`
   - `model_browser`
   - `huggingface_exports`

2. Add `automation/docs/odysseus-central-interface-contract.md` explaining:
   - Odysseus is the central cockpit, not research authority.
   - Every displayed object must resolve to one registered source.
   - Every dispatch must resolve to one central task file.
   - Every external mutation must resolve to one human-gated action.

3. Add `automation/docs/odysseus-object-import-schema.md` covering imported Odysseus chats, documents, researches, notes, and archived chats:
   - stable object id
   - object type
   - source timestamp
   - source hash
   - title
   - privacy class
   - dedupe keys
   - linked vault paths
   - linked task ids
   - promotion status

4. Add `automation/docs/odysseus-asset-gallery-schema.md` covering attachments, albums, image edits, and derivatives:
   - original path/hash
   - album id
   - derivative path/hash
   - edit tool
   - edit prompt/settings
   - provenance
   - approval state

5. Add a read-only `odysseus-interface-health` command or report generator under `Scripts/automation/**` that checks:
   - source registry exists and parses;
   - each registered path family exists or is explicitly marked optional/deferred;
   - no source claims canonical write authority;
   - HF source is only `exports/huggingface/`;
   - calendar source is read-only unless an action is explicitly declared;
   - assets and Odysseus library imports are manifest-based;
   - model comparison/browser are read/report only;
   - task source points at `automation/review/agent-tasks/**`;
   - action surfaces point at `automation/config/odysseus_actions.yaml`.

6. Add tests for the registry and health report.

7. Update `automation/docs/current-capabilities.md` and `automation/docs/capability_manifest.json` honestly as partial/scaffold only.

## Hard constraints

- Do not enable `task-transition`, `routine-report-stage`, `remote-upkeep-trigger`, `hf-export-sync`, or `pr-open-draft`.
- Do not add canonical vault write scope.
- Do not add Zotero, calendar, GitHub, PDF, or Hugging Face mutation.
- Do not create a second queue, second retrieval database, or second memory authority.
- Do not treat Odysseus chats/memories as evidence.
- Do not sync the vault root externally.

## Verification

Run:

```bash
python -m unittest Scripts.automation.tests.test_capability_truth_contracts
python -m unittest Scripts.automation.tests.test_odysseus_interface_sources
python -m Scripts.automation agent-task-lint --require-pass
python -m Scripts.automation validate
```

## Stop condition

Stop when the interface registry, schemas, read-only health report, tests, and capability truth updates exist in a draft PR. No live action enablement is allowed in this task.

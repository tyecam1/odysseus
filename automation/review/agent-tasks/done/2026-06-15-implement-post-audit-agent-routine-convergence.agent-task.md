---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-15-implement-post-audit-agent-routine-convergence
title: Implement post-audit agent routine convergence
status: done
priority: medium
task_type: implementation
created_by: chatgpt
created_at: 2026-06-15T12:10:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/routine-reports/agent-routine-convergence/**
  - automation/review/operator-decisions/**
  - automation/review/agent-tasks/**/2026-06-15-implement-post-audit-agent-routine-convergence.agent-task.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/routine-reports/agent-routine-migration-audit/2026-06-15.live-agent-routine-migration-audit.md
  - automation/review/routine-reports/agent-routine-migration-audit/2026-06-15.live-agent-routine-migration-audit.json
  - automation/review/decision-packets/2026-06-15-agent-routine-relevance-pruning.decision-packet.md
  - automation/config/odysseus_skill_registry.yaml
  - automation/config/odysseus_actions.yaml
  - automation/docs/agent-task-centralisation-plan.md
  - automation/docs/agent-ecosystem-centralisation-design.md
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
outputs:
  - automation/review/routine-reports/agent-routine-convergence/2026-06-15.post-audit-agent-routine-convergence.md
  - automation/review/routine-reports/agent-routine-convergence/2026-06-15.post-audit-agent-routine-convergence.json
  - automation/review/operator-decisions/2026-06-15-agent-routine-disable-actions.decision-card.md
result_path: automation/review/routine-reports/agent-routine-convergence/2026-06-15.post-audit-agent-routine-convergence.md
review_report_path: automation/review/routine-reports/agent-routine-convergence/2026-06-15.post-audit-agent-routine-convergence.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: automation/review/operator-decisions/2026-06-15-agent-routine-disable-actions.decision-card.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Implemented by Codex on 2026-06-16 under explicit operator authorization after rebase despite the missing pruning packet. No canonical promotion or external schedule mutation; remaining external disablement is captured as an operator decision card."
---

# Task: Implement post-audit agent routine convergence

## Objective

Turn the live migration audit and relevance-pruning decision packet into a small, repo-governed convergence PR. The result should make the automation estate auditable from Odysseus and shrink obvious routine sprawl without creating a new scheduler, queue, or memory authority.

This task must not start until both prerequisite outputs exist:

- `automation/review/routine-reports/agent-routine-migration-audit/2026-06-15.live-agent-routine-migration-audit.md`
- `automation/review/decision-packets/2026-06-15-agent-routine-relevance-pruning.decision-packet.md`

If either is missing, move this task to `blocked` with the named precondition `missing-agent-routine-audit-or-pruning-packet`.

## Required implementation scope

Implement the smallest repo-side changes needed to converge the surviving routines.

Expected change families, subject to the audit/pruning packet:

1. **Registry truth fixes**
   - Add explicit lifecycle status metadata to registered routines where needed: active, pilot, materialise-only, disabled, rejected, external-unverified.
   - Mark cloud-side Codex prompts as contract-linked unless live prompt parity has been evidenced.
   - Keep `weekly-zotero-push` and similar external mutation routines non-dispatchable unless a separate human-gated action exists.

2. **Odysseus visibility checks**
   - Add or extend a read-only routine/source health check so Odysseus can report:
     - registered-but-not-consumed routines;
     - live schedules without central task representation;
     - central task files without durable output paths;
     - cloud-side prompt drift/unverified status;
     - routines whose cadence violates the pruning packet.
   - Output only to `automation/review/routine-reports/**` unless a separate PR-gated implementation file is changed.

3. **Task materialisation scaffolds**
   - For routines classified `KEEP_CORE` or `KEEP_PILOT`, ensure there is a central task template/materialisation rule or explicit manual task path.
   - For `MATERIALISE_ONLY`, create a manual/task-template representation, not a schedule.
   - For `MERGE`, route the intent into the destination routine and record the superseded source.

4. **Deprecation and external disablement packet**
   - Do not directly edit Claude/Cowork/Codex cloud schedules.
   - Instead create a human decision card at:
     - `automation/review/operator-decisions/2026-06-15-agent-routine-disable-actions.decision-card.md`
   - The card must list every external/cloud/local schedule to disable, rename, or leave as contract-linked, with exact UI/manual action required and rollback notes.

5. **Capability truth update**
   - Update `automation/docs/current-capabilities.md` and `automation/docs/capability_manifest.json` honestly.
   - If Odysseus still cannot consume/act on the registry, keep status as partial. Do not overclaim.

## Hard constraints

- Do not enable `task-transition`, `routine-report-stage`, `remote-upkeep-trigger`, `hf-export-sync`, or `pr-open-draft` unless the audit packet proves all documented preconditions have passed and the task is explicitly amended for that enablement. Default is no enablement.
- Do not mutate external Claude/Cowork/Codex scheduled tasks.
- Do not write canonical research, evidence, paper, annotation, standard, dashboard, or concept paths.
- Do not merge producer PRs.
- Do not add a new queue, scheduler, memory database, dashboard stack, or vector authority.
- Do not keep routines classified `DISABLE` or `REJECT` in an apparently active state.

## Required report

Write a convergence report to:

- `automation/review/routine-reports/agent-routine-convergence/2026-06-15.post-audit-agent-routine-convergence.md`

Also write a matching JSON summary to:

- `automation/review/routine-reports/agent-routine-convergence/2026-06-15.post-audit-agent-routine-convergence.json`

The report must include:

1. What was changed.
2. What remains contract-only.
3. Which routines are now core, pilot, materialise-only, merged, disabled, or rejected.
4. Which cloud/local manual actions still require the operator.
5. Which Odysseus controls remain disabled and why.
6. Validation commands and results.
7. Draft PR link.

## Verification

Run:

```bash
python -m Scripts.automation agent-task-lint --require-pass
python -m Scripts.automation validate
python -m unittest Scripts.automation.tests.test_capability_truth_contracts
```

Add or update targeted tests for any new routine/source health check.

## Stop condition

Stop when the surviving routine set is represented from the central queue/source registry, dead or irrelevant routines are clearly deprecated, and any remaining cloud/local disablement work is captured as a human decision card rather than hidden in chat.

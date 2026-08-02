---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-15-audit-live-agent-routine-migration-state
title: Audit live Claude and Codex routine migration state
status: done
priority: high
task_type: diagnostics
created_by: chatgpt
created_at: 2026-06-15T12:00:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: true
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
  - automation/review/routine-reports/agent-routine-migration-audit/**
  - automation/review/agent-tasks/**/2026-06-15-audit-live-agent-routine-migration-state.agent-task.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/docs/agent-task-centralisation-plan.md
  - automation/docs/agent-ecosystem-centralisation-design.md
  - automation/review/architecture/2026-06-12-odysseus-central-interface-convergence-plan.md
  - automation/review/architecture/odysseus-consolidated-system-design.md
  - automation/docs/claude-routines.md
  - automation/config/odysseus_skill_registry.yaml
  - automation/config/odysseus_actions.yaml
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
outputs:
  - automation/review/routine-reports/agent-routine-migration-audit/2026-06-15.live-agent-routine-migration-audit.md
  - automation/review/routine-reports/agent-routine-migration-audit/2026-06-15.live-agent-routine-migration-audit.json
result_path: automation/review/routine-reports/agent-routine-migration-audit/2026-06-15.live-agent-routine-migration-audit.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Inventory actual live Claude Cowork scheduled tasks, Claude Code routine tasks, and Codex cloud automations, then compare them against the Odysseus registry, action allowlist, central task lifecycle, and durable output paths. This is an evidence audit only: no schedule edits, no routine firing, no canonical writes, no external mutation."
---

# Task: Audit live Claude and Codex routine migration state

## Objective

Prove, with file and runtime evidence, whether existing Claude Cowork scheduled tasks, Claude Code routine tasks, and Codex automations have actually been migrated into the local Odysseus-managed system, rather than merely registered in repo policy documents.

The key question is not "does a registry entry exist?" The key question is: **can Odysseus see it, materialise it as a central task, route/claim it through `automation/review/agent-tasks/**`, and observe durable output without relying on a shadow scheduler or session-local UI state?**

## Required audit scope

Inspect and classify every relevant surface you can access:

1. Repo-declared Claude scheduled task prompts:
   - `.claude/scheduled-tasks/**/SKILL.md`
   - `.claude/skills/**`
   - `.agents/skills/**`
2. Claude Code routine infrastructure:
   - `Scripts/automation/claude_job.py`
   - `automation/docs/claude-routines.md`
   - `automation/review/queues/claude-candidates/**`
   - `automation/review/queues/claude-jobs/**`
   - `automation/review/agent-jobs/**`
   - `automation/review/routine-reports/**`
3. Codex cloud automation contracts:
   - `automation/config/odysseus_skill_registry.yaml` entries with `prompt_location: codex-cloud`
   - `automation/docs/claude-delegation-router.md`
   - `automation/docs/claude-job-controller.md`
   - `automation/docs/automation-pr-publishing-contract.md`
4. Odysseus management surfaces:
   - `automation/config/odysseus_actions.yaml`
   - any existing `odysseus_interface_sources.yaml` or equivalent source registry
   - Odysseus heartbeat/status/config files available on the local Odysseus system
   - local scheduled task/service configuration if accessible
5. Existing central task lifecycle:
   - `automation/review/agent-tasks/{inbox,ready,running,review,done,rejected,blocked}/**`

## Required report

Create both Markdown and JSON reports under:

- `automation/review/routine-reports/agent-routine-migration-audit/`

The Markdown report must include:

1. **Executive verdict**: migrated / partially migrated / not migrated, with no vague language.
2. **Inventory table** for every discovered routine/automation:
   - name
   - source surface
   - live schedule exists? yes/no/unknown
   - repo registry entry exists? yes/no
   - Odysseus source/action entry exists? yes/no
   - central task materialisation exists? yes/no
   - durable output path exists? yes/no
   - latest observed output or run evidence
   - owner/executor lane
   - current risk
3. **Out-of-band list**: anything that can run without a central task file.
4. **Zombie list**: anything registered but not runnable/consumed by Odysseus.
5. **Shadow-state list**: anything whose real state lives only in Claude UI, Codex UI, local app config, Chroma/Odysseus DB, scheduled-task UI, or logs not represented in the vault.
6. **Migration gap list** ordered by operational risk.
7. **Next task recommendations**: at most five, each with target executor and exact output path.

The JSON report must contain the same inventory in machine-readable form.

## Acceptance criteria

- No task is counted as "managed by Odysseus" unless there is evidence of all four: source registry/action visibility, central task lifecycle representation, route/claim/transition path, and durable review-side output path.
- Do not infer live schedule state from the presence of a prompt file alone.
- Do not infer Codex cloud prompt parity from a repo contract alone; classify as `contract-linked-unverified` unless live cloud prompt evidence is available.
- Do not treat session-local Claude output as durable.
- Do not edit or disable any scheduled task in this audit.

## Verification

Run, where available:

```bash
python -m Scripts.automation agent-task-lint --require-pass
python -m Scripts.automation validate
```

Also record any local/Odysseus commands used to inspect scheduled-task state, but redact tokens, secrets, machine-specific private values, and unnecessary absolute paths.

## Stop condition

Stop when the audit report gives a binary verdict for each routine/automation and separates three things that are currently being blurred: **registered**, **scheduled**, and **Odysseus-managed**.

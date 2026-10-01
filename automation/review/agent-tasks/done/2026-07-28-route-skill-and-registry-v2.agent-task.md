---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-07-28-route-skill-and-registry-v2
title: "PR-3: /route loop skill at .agents/skills/route/ plus registry disposition"
status: done
priority: medium
task_type: implementation
created_by: fable-claude
created_at: 2026-07-28T09:00:00+01:00
updated_at: 2026-08-01T12:30:00+01:00
executor: codex_subscription
execution_mode: implementation
architecture: single
architecture_rationale: "Single coherent prose contract over three existing docs; sequential and small. Decomposition would fragment one file's voice for no verification gain."
single_agent_baseline: "PR-1 and PR-2 both completed as single-agent runs with clean acceptance; same class of work, smaller scope."
execution_host: laptop
context_budget: "3 authority docs + registry yaml; no corpus sweep"
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: codex/route-skill-registry-20260728
allowed_paths:
  - .agents/skills/route/**
  - automation/config/odysseus_skill_registry.yaml
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
  - 02-library/**
  - 10-inbox/**
  - 11-projects/**
  - 12-log/**
inputs:
  - automation/docs/agent-architecture-selection-gate.md
  - automation/docs/dual-agreement-protocol.md
  - automation/config/odysseus_skill_registry.yaml
  - automation/review/agent-tasks/blocked/2026-07-27-route-skill-and-registry.agent-task.md
outputs:
  - .agents/skills/route/SKILL.md
  - registry disposition entry
result_path: automation/review/agent-tasks/inbox/2026-07-28-route-skill-and-registry-v2.agent-task.md
review_report_path: automation/review/architecture/2026-07-27-role-routing-policy-delta.md
handoff_model: codex_work_package
operator_decision_path: automation/review/architecture/2026-07-27-role-routing-policy-delta.md
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/435"
supersedes:
  - 2026-07-27-route-skill-and-registry
duplicates: []
notes: "Successor packet per Sol E2: PR-1 (#433) and PR-2 (#434) both merged 2026-07-28, so the blocking conditions on the scope-empty placeholder are cleared. Codex is implementation worker; independent verification precedes merge."
---
# PR-3: /route loop skill and registry disposition

## Goal

Create the Fable–Sol routing loop skill as a thin prose contract at
`.agents/skills/route/SKILL.md` and record its registry disposition.

## Required design

- Input: a task packet path (authoritative) or a free-text description
  (advisory only — free text can NEVER authorise mutation).
- Classify via `automation/docs/agent-architecture-selection-gate.md`
  and record the architecture decision in schema-v2 fields.
- Lane ladder: deterministic script → smaller model → codex worker →
  opus worker → sol audit → fable decision. Fable never implements.
- Emit: exact dispatch command, verification route, rollback, handoff
  path, and the gate classification that justified the lane.
- Authority-bearing actions (merge, accept, recover) require the
  dual-agreement protocol first, recorded per-action under
  `automation/review/operator-decisions/records/`.
- Fail closed on unknown task types, executors, execution modes,
  authority surfaces, or invocation surfaces → operator decision card.
- Registry: `route` is an UNREGISTERED utility skill under
  `.agents/skills/**` per the registry's own conventions (the registry
  forbids registered-utility entries and treats `dispatchable: false` as
  inventory-only). Document the disposition in the registry's utility
  comment block; grant no dispatch surface and no write scope.

## Acceptance criteria

- `.agents/skills/route/SKILL.md` exists: thin prose contract with
  concrete invocation examples, no code, fail-closed rules explicit.
- Registry disposition consistent with file conventions.
- Capability truth pair updated in the same change; truth tests pass.
- `python -m Scripts.automation agent-task-lint` stays at zero errors.
- Draft PR "PR 3/3: /route skill + registry disposition"; no merge.

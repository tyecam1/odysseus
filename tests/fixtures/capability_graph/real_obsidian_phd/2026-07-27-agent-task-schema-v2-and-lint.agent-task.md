---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-agent-task-schema-v2-and-lint
title: "PR-2: agent-task schema v2, governed write-scope classes, task-type registration, and 2026-07-27 packet repair"
status: done
priority: high
task_type: orchestration
created_by: fable-claude
created_at: 2026-07-27T16:20:00+01:00
updated_at: 2026-08-01T12:30:00+01:00
executor: codex_subscription
execution_mode: central-orchestrator
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
branch: codex/agent-task-schema-v2-lint-20260727
allowed_paths:
  - Scripts/automation/**
  - automation/docs/agent-task-frontmatter-schema.md
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
  - automation/review/agent-tasks/inbox/2026-07-27-agent-evaluation-and-observability-ratchet.agent-task.md
  - automation/review/agent-tasks/inbox/2026-07-27-engine-loss-and-credit-assignment.agent-task.md
  - automation/review/agent-tasks/inbox/2026-07-27-external-pattern-source-adjudication.agent-task.md
  - automation/review/agent-tasks/inbox/2026-07-27-human-writing-skill.agent-task.md
  - automation/review/agent-tasks/inbox/2026-07-27-hybrid-retrieval-routing-benchmark.agent-task.md
  - automation/review/agent-tasks/inbox/2026-07-27-loop-graph-and-propagation-map.agent-task.md
  - automation/review/agent-tasks/inbox/2026-07-27-markitdown-extraction-backend-pilot.agent-task.md
  - automation/review/agent-tasks/inbox/2026-07-27-repo-intelligence-bakeoff.agent-task.md
  - automation/review/agent-tasks/inbox/2026-07-27-research-engine-sleep-consolidation.agent-task.md
  - automation/review/agent-tasks/inbox/2026-07-27-session-uncertainty-closeout.agent-task.md
  - automation/review/agent-tasks/inbox/2026-07-27-skill-lifecycle-and-distillation.agent-task.md
  - automation/review/agent-tasks/inbox/2026-07-27-zotero-vault-trajectory-completeness.agent-task.md
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
  - automation/docs/agent-task-frontmatter-schema.md
  - automation/config/agent_routing.yaml
  - automation/review/agent-tasks/blocked/2026-07-27-route-skill-and-registry.agent-task.md
  - automation/review/architecture/2026-07-27-role-routing-policy-delta.md
  - Scripts/automation/agent_task_lint.py
  - Scripts/automation/tests/test_agent_task_lint.py
outputs:
  - Scripts/automation lint changes plus tests
  - automation/docs/agent-task-frontmatter-schema.md (v2 section)
  - repaired 2026-07-27 packets (zero lint errors tree-wide)
result_path: automation/review/agent-tasks/inbox/2026-07-27-agent-task-schema-v2-and-lint.agent-task.md
review_report_path: automation/review/architecture/2026-07-27-role-routing-policy-delta.md
handoff_model: codex_work_package
operator_decision_path: automation/review/architecture/2026-07-27-role-routing-policy-delta.md
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/434"
supersedes: []
duplicates: []
notes: "PR-2 of the Sol-adjudicated ladder (D4/E1). This packet is lint-clean under the existing central-orchestrator class; no bootstrap exception. Codex acts as implementation worker; an independent review pass precedes merge."
---
# PR-2: agent-task schema v2, write-scope classes, task-type registration, packet repair

## Goal

Extend the agent-task lint so governed implementation tasks, architecture
fields, and registered task types are validated, and repair the twelve
2026-07-27 packets so `python -m Scripts.automation agent-task-lint`
returns zero errors tree-wide.

## Required design

1. Schema v2 (additive; v1 stays valid) in
   `automation/docs/agent-task-frontmatter-schema.md`: `architecture`
   (single | single-plus-verifier | coordinated-2 | parallel-n),
   `architecture_rationale`, `single_agent_baseline`, `execution_host`
   (laptop | compute-box | cloud), `context_budget`,
   `coordination_reason` (required when architecture != single),
   `flat_verification_status` (misumi-related only). Lint accepts
   `task_schema: agent-task/v1` and `agent-task/v2`; v2 validates the new
   enums and conditional requirements.
2. Registered execution modes: validate `execution_mode` against an
   explicit enum derived from live packets plus `implementation`;
   unknown modes are errors. Add ONE additive write-scope class:
   `execution_mode: implementation` with a declared `branch` and
   `verification_route: V2_HUMAN_VERIFIED` may allow writes under
   `Scripts/automation/**`, `automation/docs/**`, `automation/config/**`,
   `automation/prompts/**`, `.agents/skills/**`,
   `automation/logs/observability/**`. Review-only remains the default;
   denied-path defaults stay required verbatim.
3. Registered task types: validate `task_type` against the route table in
   `automation/config/agent_routing.yaml` plus an explicit allowlist for
   orchestration/architecture-evaluation; unknown task types are errors.
4. Executor resolution: derive the executor enum from
   `automation/config/agent_routing.yaml` executors at lint time so the
   contract file and lint cannot diverge (closes the PR-1 `opus` seam).
   `claude_then_codex` remains invalid.
5. Repair the twelve named 2026-07-27 packets (see allowed_paths): add
   the missing denied-path defaults verbatim; replace `claude_then_codex`
   with `claude_subscription` plus a notes line naming codex as
   independent verifier; normalise each packet's `allowed_paths` to the
   correct class (implementation class above, or central-orchestrator
   where the work is genuinely orchestration surface) so NO path errors
   remain — including `automation/logs/observability/**`,
   `automation/prompts/**`, and any `.claude/**`, `.agents/**`,
   `09-resources/**` entries, which must be re-homed to authorised
   scopes or dropped with a body note. Task bodies otherwise unchanged.
6. Tests: positive and negative cases for every new rule in
   `test_agent_task_lint.py`; all existing tests stay green.
7. Capability truth: update `current-capabilities.md` and
   `capability_manifest.json` in the same change.

## Acceptance criteria

- `python -m Scripts.automation agent-task-lint` → zero errors, 145 files.
- `python -m unittest Scripts.automation.tests.test_agent_task_lint` and
  `...test_capability_truth_contracts` pass.
- No canonical paths touched; no scope widened beyond the implementation
  class defined above; the blocked PR-3 placeholder stays scope-empty.
- Draft PR titled "PR 2/3: agent-task schema v2 + lint + packet repair";
  no merge.

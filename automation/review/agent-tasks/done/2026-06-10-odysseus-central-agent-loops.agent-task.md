---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-10-odysseus-central-agent-loops
title: Centralise agent ecosystem in Odysseus
status: done
priority: high
task_type: synthesis
created_by: human
created_at: 2026-06-10T00:00:00+01:00
completed_by: claude_subscription
completed_at: 2026-06-11T00:00:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
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
allowed_paths: []
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
  - automation/docs/agent-task-frontmatter-schema.md
  - automation/config/agent_routing.yaml
  - automation/config/odysseus_actions.yaml
outputs:
  - automation/docs/agent-ecosystem-centralisation-design.md
result_path: automation/docs/agent-ecosystem-centralisation-design.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/345"
supersedes:
  - automation/review/queues/agent-tasks/2026-06-10-odysseus-central-agent-loops.automation-docs.md
duplicates: []
notes: "Migrated from the retired second queue (design §9 PR-C). Design accepted via PR #345 merge; verification escalated to V2 because the packet feeds implementation and queue-governance decisions. The PR carrying this migration is itself PR-C from the design."
---

# Task: Centralise agent ecosystem in Odysseus

## Completion

This design work item is complete. The implementation design exists at:

- `automation/docs/agent-ecosystem-centralisation-design.md`

The output is specific enough to support the first bounded implementation PR without reopening the broad design question.

## Accepted design summary

- Use `automation/review/agent-tasks/**` as the single lifecycle queue.
- Retire the accidental second queue at `automation/review/queues/agent-tasks/` after migrating the three task files.
- Preserve Claude/Codex queue surfaces only as feeders until the staged migration retires duplication.
- Keep Odysseus as a control plane, not a direct canonical mutator.
- Keep all canonical promotion, Zotero mutation, PDF mutation, endpoint exposure, and protected concept/library writes behind explicit approval.

## Next implementation

PR-C from the design packet (executed by the PR carrying this migration):

1. migrate the three `automation/review/queues/agent-tasks/` files into the lifecycle queue with schema-conformant front matter;
2. set `supersedes` back to the old paths;
3. fix timer-to-Odysseus drift in `remote-upkeep-compute-box.md`;
4. align OC-2 wording with the implemented queue path;
5. do not enable live external mutation or canonical promotion.

## Archived objective

Design a central Odysseus-managed agent ecosystem that absorbs or coordinates current memory/context sources, Codex automations, Claude routines and queues, connectors, Obsidian automation-relevant plugins, MCP servers/tools, model endpoint configuration, future remote-box agents, and routed human approval/work-item flows.

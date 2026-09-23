---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-route-skill-and-registry
title: "PR-3 (blocked): /route skill under .agents/skills/route/ — awaits PR-1 and PR-2"
status: blocked
priority: medium
task_type: orchestration
created_by: fable-claude
created_at: 2026-07-27T16:22:00+01:00
updated_at: 2026-07-27T17:05:00+01:00
executor: human
execution_mode: central-orchestrator
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_BLOCKED
risk_level: low
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
  - 02-library/**
  - 10-inbox/**
  - 11-projects/**
  - 12-log/**
inputs:
  - automation/review/architecture/2026-07-27-role-routing-policy-delta.md
outputs: []
result_path: automation/review/agent-tasks/blocked/2026-07-27-route-skill-and-registry.agent-task.md
review_report_path: automation/review/architecture/2026-07-27-role-routing-policy-delta.md
handoff_model: codex_work_package
operator_decision_path: automation/review/architecture/2026-07-27-role-routing-policy-delta.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Sol E2 amendment: genuinely blocked, scope-empty placeholder. Blocking conditions: (1) PR-1 #433 merged (gate + dual-agreement docs exist on main); (2) PR-2 merged (implementation lint class exists). On both landing, a fresh superseding V2_HUMAN_VERIFIED packet is created and this one is superseded. Design constraints for the successor: skill lives at .agents/skills/route/ as an UNREGISTERED utility skill per registry conventions (registry forbids registered-utility entries; dispatchable:false is inventory-only); any slash command is a thin wrapper; free-text input can never authorise mutation; fail closed on unknown task types, executors, authority or invocation surfaces."
---
# PR-3 (blocked): /route skill and registry disposition

Scope-empty placeholder per Sol E2. No work is authorised under this
packet. See notes for blocking conditions and successor-packet design
constraints.

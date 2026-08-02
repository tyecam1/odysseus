---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-16-cad-base-requirements-for-constrained-manipulation-mockup
title: Specify CAD base requirements for constrained-manipulation mock-up
status: done
priority: medium
task_type: requirements
created_by: chatgpt
created_at: 2026-06-16T09:15:00+01:00
executor: claude_subscription
execution_mode: handoff
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
branch: ""
allowed_paths:
  - automation/review/s2-benchmark-design/2026-06-16-cad-base-requirements-for-constrained-manipulation-mockup.md
  - automation/review/agent-tasks/**/2026-06-16-cad-base-requirements-for-constrained-manipulation-mockup.agent-task.md
denied_paths:
  - 01-research-plan/**
  - 02-library/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/**
  - 04-supportDesign/**
  - 07-standards/**
  - 00-dashboards/**
inputs:
  - 12-log/26-06/26-25/supervision-erfu-2026-06-15.md
  - automation/review/s2-benchmark-design/2026-06-16-system-architecture-and-communication-framework.md
outputs:
  - automation/review/s2-benchmark-design/2026-06-16-cad-base-requirements-for-constrained-manipulation-mockup.md
result_path: automation/review/s2-benchmark-design/2026-06-16-cad-base-requirements-for-constrained-manipulation-mockup.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: 10-inbox/build-constrained-manipulation-cad-base.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Prepare CAD requirements only. Do not generate a detailed CAD model until the system architecture and experiment split are approved."
---
# Task: Specify CAD base requirements for constrained-manipulation mock-up

## Objective

Define the minimum CAD base requirements for the first chemical-free constrained-manipulation benchmark.

The output should enable Tye to build the base without overcommitting to a full process cell before the experimental question is locked.

## Required output

Write one requirements packet to:

- `automation/review/s2-benchmark-design/2026-06-16-cad-base-requirements-for-constrained-manipulation-mockup.md`

Include:

1. **Functional requirements**: restricted access, repeatable object placement, obstruction scenario, robot approach, human reach envelope, safety separation visibility.
2. **Interface requirements**: mounting points, fixture slots, robot/tool clearance, camera/sensor attachment, cable/logging path.
3. **Modularity requirements**: what must be adjustable without redesign.
4. **Non-targets**: what the first base must not attempt.
5. **CAD checklist**: dimensions to decide manually before modelling.
6. **Technician/Dino questions**: short list of practical fabrication questions.

## Hard constraints

- Do not assume specific hardware dimensions unless already present in the vault.
- Do not design for chemical use, biological containment, or real glovebox compliance at this stage.
- Do not optimise aesthetics.
- Do not create CAD source files unless explicitly requested later.

## Acceptance criteria

Tye should be able to open CAD and model a minimum viable base from this packet without reopening the whole research design.

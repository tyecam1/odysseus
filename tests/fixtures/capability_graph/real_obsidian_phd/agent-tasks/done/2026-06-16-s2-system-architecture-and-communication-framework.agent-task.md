---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-16-s2-system-architecture-and-communication-framework
title: Draft S2 system architecture and communication framework
status: done
priority: high
task_type: synthesis
created_by: chatgpt
created_at: 2026-06-16T09:00:00+01:00
executor: claude_subscription
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
  - automation/review/s2-benchmark-design/2026-06-16-system-architecture-and-communication-framework.md
  - automation/review/agent-tasks/**/2026-06-16-s2-system-architecture-and-communication-framework.agent-task.md
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
  - 12-log/26-06/26-25/supervision-erfu-2026-06-15-s2-benchmark-discussion-prompts.md
  - 04-supportDesign/operator-task-fit-adaptive-support/experiment-design-ledger.md
  - 11-projects/tye/annual reviews/1/annual-review-2026-research-report-draft-v2.md
  - 11-projects/cpi/conference-paper/CPI_ConferencePaper_20260530.pdf
outputs:
  - automation/review/s2-benchmark-design/2026-06-16-system-architecture-and-communication-framework.md
result_path: automation/review/s2-benchmark-design/2026-06-16-system-architecture-and-communication-framework.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: 10-inbox/prepare-next-week-s2-system-architecture-discussion.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Prepare the architecture packet Erfu requested for next week. Keep it as a review-side packet until Tye approves canonical edits."
---
# Task: Draft S2 system architecture and communication framework

## Objective

Convert the 2026-06-15 Erfu supervision outcomes into a concise S2 benchmark architecture packet for the constrained-manipulation route.

The output must support next week's supervision discussion. It must not become generic robotics architecture. It must show how the benchmark remains process-engineering evidence: restricted access, degraded reach/visibility/dexterity, meaningful human contribution, close-proximity assistance, and safety separation.

## Required output

Write one packet to:

- `automation/review/s2-benchmark-design/2026-06-16-system-architecture-and-communication-framework.md`

Include:

1. **Benchmark architecture**: scene, human task, robot task, artefacts, fixture/base, sensors/logging, communication layer, safety layer, and data outputs.
2. **Communication framework**: what state is communicated, when, to whom, and for which decision.
3. **System diagram in Mermaid**: physical system and information flow.
4. **Minimum viable implementation**: what must exist for the first benchmark and what is deliberately deferred.
5. **Research anchoring check**: why this is constrained manipulation evidence rather than generic obstacle avoidance.
6. **Supervisor discussion prompts**: at most seven prompts for Erfu/Richard.

## Hard constraints

- Do not rewrite canonical concept, support-design, standards, or library notes.
- Do not invent CPI process facts not already present in the vault.
- Do not make S3 trust/workload or S4 adaptive control decisions. State dependencies only.
- Do not expand scope into lost-part recovery except as downstream.

## Acceptance criteria

The packet is acceptable only if Tye can reduce it to one discussion page and one diagram before the next Erfu meeting.

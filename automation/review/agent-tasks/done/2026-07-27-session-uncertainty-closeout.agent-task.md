---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-session-uncertainty-closeout
title: "Implement session focus and uncertainty closeout protocol"
status: done
priority: high
task_type: harness-protocol
created_by: chatgpt
created_at: 2026-07-27T14:00:00+01:00
updated_at: 2026-08-01T12:30:00+01:00
executor: codex_subscription
execution_mode: implementation
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: false
repo: tyecam1/obsidian-PhD
branch: codex/session-uncertainty-closeout-20260729
allowed_paths:
  - automation/review/session-closeout/**
  - automation/review/agent-tasks/**
  - automation/prompts/**
  - Scripts/automation/**
  - Scripts/automation/tests/**
  - automation/docs/**
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
  - automation/docs/agent-boundaries.md
  - automation/docs/agent-task-frontmatter-schema.md
outputs:
  - automation/review/session-closeout/session-closeout-contract.md
  - automation/review/session-closeout/claude-adhd-focus.skill.md
  - automation/review/session-closeout/session-closeout-schema.json
  - automation/review/session-closeout/eval-report.md
result_path: automation/review/session-closeout/session-closeout-contract.md
review_report_path: automation/review/session-closeout/eval-report.md
handoff_model: codex_work_package
operator_decision_path: automation/review/session-closeout/eval-report.md
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/441"
supersedes: []
duplicates: []
notes: "The two uncertainty questions must not create new work automatically."
---
# Implement session focus and uncertainty closeout protocol

## Goal

Keep agents on the active objective during execution and end substantive sessions with explicit uncertainty, missingness and continuation state.

## Focus behaviour

- Restate the active objective, stop condition and permitted paths at session start.
- Maintain one active task and one parking lot.
- Route attractive adjacent work to the parking lot without executing it.
- Detect repeated replanning, scope expansion, tool shopping and unverified completion.
- Interrupt with a focus checkpoint when the run diverges from the acceptance criteria.

## Mandatory closeout questions

1. What are you least confident about?
2. What is the biggest thing I may be missing about the situation right now?

The response must distinguish:

- known uncertainty;
- unverified assumption;
- missing evidence/context;
- blocked dependency;
- speculative opportunity.

## Closeout artifact

Record objective, actions, outputs, verification, unresolved items, parked ideas, confidence and exact next step. Do not create tasks from the two answers unless a task-creation gate is separately invoked.

## Acceptance criteria

- The protocol works for Claude, Codex and Odysseus handoffs.
- A trivial session may exit without ceremony; substantive sessions produce a compact closeout.
- Tests show that adjacent ideas are parked rather than silently executed.
- The closeout cannot imply verification when none occurred.
- Repeated unchanged uncertainty is deduplicated rather than appended indefinitely.

## Scope repair note (PR-2)

`.claude/**` and `.agents/**` are removed from `allowed_paths`. No declared
output targets a live agent-facing directory; the contract, skill draft,
schema and eval report all stage under `automation/review/session-closeout/**`.
Deployment of `claude-adhd-focus.skill.md` into a live skill surface remains a
separate, human-gated promotion step.

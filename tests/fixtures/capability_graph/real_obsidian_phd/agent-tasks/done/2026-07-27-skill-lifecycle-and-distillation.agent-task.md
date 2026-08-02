---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-skill-lifecycle-and-distillation
title: "Build a governed trajectory-to-skill lifecycle"
status: done
priority: high
task_type: skill-engineering
created_by: chatgpt
created_at: 2026-07-27T14:00:00+01:00
updated_at: 2026-08-01T12:30:00+01:00
executor: claude_subscription
execution_mode: implementation
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
branch: codex/skill-lifecycle-distillation-20260731
allowed_paths:
  - automation/review/skills/**
  - automation/review/agent-tasks/**
  - automation/prompts/**
  - Scripts/automation/**
  - Scripts/automation/tests/**
  - automation/docs/**
  - automation/config/**
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
  - automation/docs/continuous-improvement-loop-contract.md
  - automation/docs/agent-boundaries.md
  - automation/docs/agentic-system-platform-assessment-plan.md
outputs:
  - automation/review/skills/skill-lifecycle-contract.md
  - automation/review/skills/skill-manifest-schema.json
  - automation/review/skills/skill-evaluation-corpus.json
  - automation/review/skills/candidate-skill-example.skill.md
result_path: automation/review/skills/skill-lifecycle-contract.md
review_report_path: automation/review/skills/skill-lifecycle-contract.md
handoff_model: claude_codex_review_package
operator_decision_path: automation/review/skills/skill-lifecycle-contract.md
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/446"
supersedes: []
duplicates: []
notes: "Adapt Skillify, book-to-skill, Hermes, Agent Skills and improvement-loop patterns. Do not bulk-install external skills. PR-2 repair: executor normalised from claude_then_codex to claude_subscription (execution_mode normalised to implementation); codex_subscription performs independent verification before merge."
---
# Build a governed trajectory-to-skill lifecycle

## Goal

Create one lifecycle for converting repeated successful work and source-grounded method guidance into small, dynamically loaded and empirically evaluated skills.

## Lifecycle

`candidate source -> trace selection -> success/failure contrast -> bounded skill draft -> static safety lint -> held-out task evaluation -> regression comparison -> human approval -> registry deployment -> monitored use -> revision or retirement`

## Required features

- Separate source-derived skills, trajectory-derived skills and behavioural skills.
- Require multiple successful traces or a strong source contract before generation.
- Use failed and successful trajectories to identify what actually matters.
- Record triggers, exclusions, required context, tools, permissions, acceptance criteria and source provenance.
- Measure performance with and without each skill on the same held-out cases.
- Detect skill collisions, context bloat, unsafe instructions and stale dependencies.
- Support on-demand loading rather than global prompt accumulation.

## Acceptance criteria

- A versioned skill manifest schema exists.
- Candidate skills default to staged and disabled.
- One example skill is distilled from existing accepted work and tested contrastively.
- Regression cases include over-triggering, under-triggering, instruction conflict and permission widening.
- External catalogues remain discovery inputs, not trusted installation sources.
- Retirement and rollback are first-class states.

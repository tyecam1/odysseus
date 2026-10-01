---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-11-adapt-claude-code-best-practices
title: Adapt Claude Code best-practice patterns into Odysseus execution contracts
status: rejected
priority: high
task_type: implementation
created_by: human
created_at: 2026-06-11T23:45:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
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
  - automation/docs/agent-ecosystem-centralisation-design.md
  - automation/docs/agentic-system-platform-assessment-plan.md
  - automation/docs/agent-task-frontmatter-schema.md
  - https://github.com/shanraisshan/claude-code-best-practice
outputs:
  - automation/docs/claude-code-execution-contract.md
  - automation/review/architecture/claude-code-pattern-adaptation.md
  - automation/review/platform-evaluations/claude-code-best-practice-adoption.md
result_path: automation/docs/claude-code-execution-contract.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
superseded_by: 2026-06-12-consolidate-skill-mcp-browser-deployment-policy
duplicates: []
notes: "Merged into 2026-06-12-consolidate-skill-mcp-browser-deployment-policy (execution-contract deltas and .claude adapter policy); original allowed_paths violated the review-side write-scope contract. Verdict MERGE in automation/review/platform-evaluations/agentic-work-item-consolidation-review.md."
---

# Task brief

## Objective

Adapt only the useful patterns from `shanraisshan/claude-code-best-practice` into this vault's Odysseus-centred execution architecture. The output should be implementation-ready docs/config/scaffolding, not another generic assessment.

## Core judgement to preserve

The source repository is Claude-centric. This repository is Odysseus/vault-centric. Therefore `.claude/**` may be an execution adapter, but not the authority for task state, memory, research ontology, evidence promotion, or approval.

## Required implementation work

### 1. Create a Claude Code execution contract

Create `automation/docs/claude-code-execution-contract.md` defining how a task routed to `claude_subscription` or Claude Code is executed.

The contract should cover:

- task file remains the unit of work;
- task -> command -> specialised agent -> bounded skill -> review-side output mapping;
- model selection (`haiku`, `sonnet`, `opus`, exact model where needed);
- permission mode (`plan`, `default`, `acceptEdits`; explicitly forbid `bypassPermissions` unless separately approved);
- worktree isolation for implementation-capable tasks;
- max-turn limits;
- memory scope (`none`, `project`, `local`) and the rule that Claude memory is advisory only;
- allowed/disallowed tools;
- MCP exposure boundaries;
- review-side output requirements;
- validation requirements before PR/output completion;
- stop conditions.

### 2. Propose or implement path-scoped Claude rules

Inspect current `.claude/**` and repository guidance. If safe, create or update path-scoped rules modelled on the best-practice repo:

- `.claude/CLAUDE.md` should remain short and point to Odysseus authority docs.
- `.claude/rules/agent-tasks.md` for `automation/review/agent-tasks/**`.
- `.claude/rules/automation.md` for `automation/**`.
- `.claude/rules/evidence.md` for `02-library/**`, but this must be read-only guidance.
- `.claude/rules/research-plan.md` for `01-research-plan/**`, read-only unless human-approved.
- `.claude/rules/concepts.md` for `03-concept/**`, read-only unless human-approved.

Do not duplicate large amounts of governance text. Rules should be compact pointers and operational constraints.

### 3. Create a pattern adaptation report

Create `automation/review/architecture/claude-code-pattern-adaptation.md` summarising which patterns were adopted, adapted, deferred, or rejected.

Must cover:

- command-agent-skill mapping;
- explicit subagent frontmatter fields;
- worktree isolation;
- short `CLAUDE.md` plus lazy-loaded rules;
- human-gated task workflow;
- hooks/lifecycle observability;
- settings hierarchy;
- why per-file commits are rejected in favour of coherent capability commits;
- why `.claude/**` must not become source of truth.

### 4. Update routing/config only if justified

If the repository already has suitable routing fields, do not churn schemas. If missing, propose or add bounded support for Claude handoff metadata such as:

```yaml
model_required: opus|sonnet|haiku|inherit
permission_mode: plan|default|acceptEdits
max_turns: 8
isolation: worktree
skills:
  - vault-context
  - repo-inspection
disallowed_tools:
  - Write
  - Edit
  - Bash
memory_scope: none|project|local
```

Prefer placing these in the Claude handoff package contract rather than expanding the canonical agent-task schema unless existing validator architecture makes schema support straightforward.

### 5. Add tests or lint checks if implementation changes behaviour

If config/schema/rules are changed in a machine-checkable way, add or update tests under `Scripts/automation/tests/**`.

Useful checks:

- `.claude/**` cannot declare itself as canonical task authority;
- implementation-capable Claude tasks require worktree isolation;
- `bypassPermissions` is rejected unless an explicit approved exception is present;
- path-scoped rules exist for high-risk canonical roots;
- Claude-generated outputs must land under review-side paths unless routed through existing approval workflows.

## Source patterns worth adopting

From `shanraisshan/claude-code-best-practice`:

- command -> agent -> skill architecture;
- explicit subagent metadata for tools, model, permissions, max turns, skills, memory, MCP and worktree isolation;
- short `CLAUDE.md` with path-scoped/lazy-loaded rules;
- commands for workflows, agents for roles, skills for capabilities;
- plan mode for complex work;
- human-gated task workflow;
- hook/lifecycle event ideas for observability;
- settings hierarchy clarity.

## Patterns to reject

- `.claude/**` as a second authority layer;
- free-running Claude tasks outside `automation/review/agent-tasks/**`;
- auto/bypass permissions as a default;
- per-file commits as a blanket rule;
- large monolithic `CLAUDE.md`;
- general-purpose mega-agent design;
- canonical vault writes without human approval.

## Expected result

A PR or review-side output that makes Claude Code safer and more useful inside Odysseus without increasing fragmentation.

## Stop conditions

Block the task if implementation would create a second task queue, second task schema, independent Claude memory authority, uncontrolled canonical write path, public endpoint exposure, or weaker approval model than the current Odysseus contracts.

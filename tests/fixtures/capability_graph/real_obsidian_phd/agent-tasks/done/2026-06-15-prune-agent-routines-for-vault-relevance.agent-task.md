---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-15-prune-agent-routines-for-vault-relevance
title: Prune agent routines for vault relevance
status: done
priority: high
task_type: critique
created_by: chatgpt
created_at: 2026-06-15T12:05:00+01:00
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
  - automation/review/decision-packets/2026-06-15-agent-routine-relevance-pruning.decision-packet.md
  - automation/review/agent-tasks/**/2026-06-15-prune-agent-routines-for-vault-relevance.agent-task.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/routine-reports/agent-routine-migration-audit/2026-06-15.live-agent-routine-migration-audit.md
  - automation/review/routine-reports/agent-routine-migration-audit/2026-06-15.live-agent-routine-migration-audit.json
  - automation/docs/agent-task-centralisation-plan.md
  - automation/docs/agent-ecosystem-centralisation-design.md
  - automation/review/architecture/2026-06-12-odysseus-central-interface-convergence-plan.md
  - automation/review/architecture/odysseus-consolidated-system-design.md
  - automation/docs/claude-routines.md
  - automation/config/odysseus_skill_registry.yaml
  - automation/config/agent_routing.yaml
  - automation/config/odysseus_actions.yaml
  - automation/docs/current-capabilities.md
outputs:
  - automation/review/decision-packets/2026-06-15-agent-routine-relevance-pruning.decision-packet.md
result_path: automation/review/decision-packets/2026-06-15-agent-routine-relevance-pruning.decision-packet.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Critically assess whether each Claude/Codex/Odysseus routine is actually worth keeping for the PhD vault repository. Do not preserve routines because they are clever, already built, or emotionally costly to delete. Classify by research value, operator burden, safety risk, and redundancy."
---

# Task: Prune agent routines for vault relevance

## Objective

Critically decide which existing Claude Cowork scheduled tasks, Claude Code routine tasks, Codex automations, and Odysseus routine surfaces are actually worth keeping for the vault repository.

The goal is not maximum automation. The goal is a small, boring, high-signal operating system that helps the PhD research pipeline and does not create maintenance theatre.

## Required inputs

Use the live migration audit from:

- `automation/review/routine-reports/agent-routine-migration-audit/2026-06-15.live-agent-routine-migration-audit.md`
- `automation/review/routine-reports/agent-routine-migration-audit/2026-06-15.live-agent-routine-migration-audit.json`

If those files do not yet exist, mark this task blocked with the named precondition `missing-live-agent-routine-migration-audit`. Do not improvise from stale registry contents alone.

## Evaluation criteria

For every routine/automation discovered in the audit, classify it using exactly one of:

- `KEEP_CORE`: directly supports recurring PhD/repository operations and has a clear owner, output path, and low overhead.
- `KEEP_PILOT`: valuable, but only as a bounded pilot with explicit stop conditions.
- `MERGE`: useful intent, but should be absorbed into another routine or report.
- `MATERIALISE_ONLY`: should exist as a central task template/manual work item, not as a scheduled automation.
- `DISABLE`: currently low-value, risky, stale, duplicative, or too expensive to maintain.
- `REJECT`: actively violates the centralisation model, creates shadow state, weakens authority boundaries, or encourages unserious automation sprawl.

Assess each item against:

1. Does it reduce real operator burden, or does it create reports nobody will use?
2. Does it directly support the current PhD research pipeline, J1 progression, evidence governance, supervision prep, CPI/NMIS work, or repository integrity?
3. Does it produce durable review-side outputs that can be verified?
4. Can Odysseus manage it without becoming a second brain?
5. Does it duplicate another routine, queue, ledger, skill, or dashboard?
6. Does it require external/cloud state that cannot be audited from the vault?
7. Is the cadence justified by actual decision frequency?

## Required decision packet

Write one decision packet to:

- `automation/review/decision-packets/2026-06-15-agent-routine-relevance-pruning.decision-packet.md`

The packet must include:

1. **Blunt verdict**: how much of the current automation estate is useful versus legacy clutter.
2. **Routine classification table** with the seven categories above.
3. **Minimum viable routine set**: the smallest set that should remain enabled or be made Odysseus-managed now.
4. **Disable/deprecate list** with rationale.
5. **Merge list** showing the destination routine/report for each absorbed item.
6. **Cadence corrections**: daily/weekly/monthly/manual recommendations.
7. **Migration priority**: which routines justify live Odysseus materialisation first.
8. **Operator attention budget**: max three surfaced decisions per week, with anything else batched or review-side.
9. **Follow-up implementation tasks**: at most three concrete Codex tasks, not a sprawling roadmap.

## Hard constraints

- Do not propose a new queue, new memory authority, new dashboard stack, or second scheduler.
- Do not keep a routine merely because a prompt already exists.
- Do not propose canonical writes, Zotero mutation, PDF mutation, external publish, or PR merge by any agent.
- Do not preserve Cloud/Cowork/Codex-only state as authoritative.
- Do not recommend automating human judgement-heavy approvals.

## Acceptance criteria

The packet is acceptable only if it makes deletion/pruning decisions. A packet that recommends keeping everything has failed.

## Stop condition

Stop when there is a small target routine set and a specific deprecation/migration queue that Codex can implement without reopening the whole architecture debate.

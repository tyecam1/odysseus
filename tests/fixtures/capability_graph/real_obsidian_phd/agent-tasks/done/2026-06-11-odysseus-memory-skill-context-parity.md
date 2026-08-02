---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-11-odysseus-memory-skill-context-parity
title: Audit and repair Odysseus memory, skill, and context parity
status: done
priority: high
task_type: decision-packet
created_by: human
created_at: 2026-06-11T18:30:00+01:00
claimed_by: claude_subscription
claimed_at: 2026-06-11T20:30:00+01:00
completed_by: claude_subscription
completed_at: 2026-06-11T22:15:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: true
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/agent-jobs/2026-06-11-odysseus-memory-skill-context-parity.claude/**
  - automation/review/decision-packets/2026-06-11-odysseus-memory-skill-context-parity.decision-packet.md
  - automation/review/agent-tasks/**/2026-06-11-odysseus-memory-skill-context-parity.md
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
  - automation/docs/agent-task-frontmatter-schema.md
  - automation/docs/verification-routing-policy.md
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
  - automation/config/agent_routing.yaml
  - automation/config/odysseus_actions.yaml
  - automation/config/odysseus_skill_registry.yaml
  - automation/config/model_execution_policy.yaml
  - automation/docs/mcp-policy.md
  - automation/docs/agent-boundaries.md
outputs:
  - automation/review/agent-jobs/2026-06-11-odysseus-memory-skill-context-parity.claude/memory-context-audit.md
  - automation/review/agent-jobs/2026-06-11-odysseus-memory-skill-context-parity.claude/skill-registry-audit.md
  - automation/review/agent-jobs/2026-06-11-odysseus-memory-skill-context-parity.claude/agent-memory-gap-map.md
  - automation/review/agent-jobs/2026-06-11-odysseus-memory-skill-context-parity.claude/integration-repair-plan.md
  - automation/review/decision-packets/2026-06-11-odysseus-memory-skill-context-parity.decision-packet.md
result_path: automation/review/decision-packets/2026-06-11-odysseus-memory-skill-context-parity.decision-packet.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/352"
supersedes: []
duplicates: []
notes: "Claude Fable 5 / opus-class task to test whether Odysseus truly integrates vault memory, skills, agent context, Codex outputs, Claude outputs, MCP surfaces, and knowledgebase state without creating another parallel memory system."
---

# Task: Audit and repair Odysseus memory, skill, and context parity

## Objective

Determine whether Odysseus currently integrates the vault, memories, skills, Codex work, Claude work, MCP surfaces, and knowledgebase context properly enough to act as the central research operating system.

The suspected failure mode is serious: Odysseus may have a central task queue and action allowlist, but may still lack practical access to the actual context that makes the research system useful, especially:

- vault memory and canonical research state
- Claude subscription work outputs
- Codex automation outputs
- knowledgebase/retrieval memories
- reusable skills and prompts
- MCP and connector capabilities
- assistant/project memories that currently influence operator decisions but may not be represented in the repo

The goal is not to invent another memory layer. The goal is to expose whether the existing Odysseus-centred architecture has context parity with the way the operator actually works, then produce a bounded repair plan.

## Core claim to test

Odysseus should be the coordination layer over one authoritative repo/vault memory system, not a separate agent with partial context.

The current design already states that:

- the live queue is `automation/review/agent-tasks/**`
- Odysseus is a coordinator, not a second task universe
- skills should be registered in `automation/config/odysseus_skill_registry.yaml`
- implementation truth lives in `automation/docs/current-capabilities.md` and `automation/docs/capability_manifest.json`
- assistant memories are advisory-only, not evidence authority

This task tests whether those claims are actually operationally true.

## Required work

### 1. Memory and context audit

Produce `memory-context-audit.md`.

Audit every current context source that Odysseus should know how to access or route around:

- canonical vault notes
- review-side outputs under `automation/review/**`
- routine reports
- decision packets
- agent tasks
- Claude job outputs
- Codex PR outputs and automation reports
- retrieval indexes and vault-context machinery
- MCP-readable surfaces
- Zotero/Beaver read-only context
- external connector context where represented in repo docs
- assistant/project memories that are influencing operator decisions but are not represented in the vault

For each source, classify:

- authority level: canonical, review-side, operational, advisory, derived, or external
- current access route for Odysseus
- whether the route is implemented, planned, blocked, or missing
- whether the source is safe to expose through MCP or task packets
- whether it should be copied, referenced, indexed, or ignored

### 2. Skill registry audit

Produce `skill-registry-audit.md`.

Audit whether `automation/config/odysseus_skill_registry.yaml` captures the real reusable skill surface.

Check at minimum:

- `.claude/scheduled-tasks/**`
- `.agents/skills/**`
- `.claude/skills/**`
- `automation/prompts/**`
- Codex automation prompts or task templates
- Claude work-package conventions
- Beaver/Zotero skill surfaces
- MCP tool descriptions
- any undocumented prompt contracts embedded in scripts or docs

For each skill/prompt/tool surface, decide:

- keep and register
- already registered
- duplicate to retire
- missing but needed
- unsafe or out of scope

Do not move files unless the task explicitly becomes a follow-up implementation PR. This task produces a repair plan first.

### 3. Agent memory gap map

Produce `agent-memory-gap-map.md`.

Map the difference between:

- what Odysseus can access through the vault/repo today
- what Claude subscription tasks can access
- what Codex can access
- what ChatGPT/project memory appears to know
- what the operator assumes the system remembers

The output must identify gaps that would cause bad routing, duplicated work, missed context, or wrong research decisions.

Pay special attention to:

- recent CPI benchmark decisions
- DRM ontology and artifact-type rules
- Zotero/Beaver integration state
- remote compute and local-model restrictions
- Claude/Codex division of labour
- current annual review / S1 / S2 priorities
- user-specific working preferences that affect task design but are not evidence

### 4. Integration repair plan

Produce `integration-repair-plan.md`.

This must specify the smallest set of repo changes needed so Odysseus can correctly retrieve or route:

- vault canonical state
- review-side decision state
- Claude outputs
- Codex outputs
- skills/prompts
- MCP tools
- Zotero/Beaver context
- derived retrieval indexes
- advisory assistant memories where relevant

For each proposed repair, classify:

- no-code documentation fix
- config registry update
- validator/lint change
- retrieval index change
- MCP exposure change
- task-router change
- human-only memory capture action

Every proposed change must preserve:

- no canonical writes by Odysseus
- no Zotero mutation through MCP
- no autonomous PR merge
- no laptop-local model execution
- no public model/MCP/vault endpoint
- no new parallel task queue
- no new parallel memory database unless it is derived and rebuildable

### 5. Decision packet

Produce `automation/review/decision-packets/2026-06-11-odysseus-memory-skill-context-parity.decision-packet.md`.

The packet must reduce the audit to one operator decision object:

- decision needed
- recommended default
- at most two rejected alternatives
- affected paths
- implementation sequence
- consequence of doing nothing
- exact next task(s) to create after approval

## Required judgement standard

Be blunt. If Odysseus is currently mostly scaffolding and does not yet integrate the actual memories and skills needed for useful operation, say so clearly.

Do not confuse having documents that describe integration with having working integration.

Do not treat assistant/project memory as authoritative evidence, but do identify where important operator-context has no durable vault representation and therefore cannot be reliably used by Odysseus.

## Constraints

- Review-side outputs only.
- No direct writes to `01-research-plan/**`, `02-library/**`, `03-concept/**`, `07-standards/**`, or `00-dashboards/**`.
- No modification of `capability_manifest.json` in this task.
- No external mutation.
- No new endpoints.
- No new task queue.
- No recursive agent chaining.

## Stop condition

Stop when the five declared outputs exist, each with source paths and a clear implementation recommendation.

If the audit cannot determine current capability, mark the unknowns explicitly and route a follow-up Codex diagnostics task rather than guessing.

## Close-out

Decision packet and four audit outputs merged on `main` via PR #352 (commit `1e5608e4`, `audit: Odysseus memory/skill/context parity decision packet`). `automation/review/decision-packets/2026-06-11-odysseus-memory-skill-context-parity.decision-packet.md` confirmed present on `origin/main`. Repairs R1/R2/R3 were routed as their own tasks (R1 skill-registry-truth-fix and R2 heartbeat-writer now closed; R3 stage-2 flag stays human-gated and is out of this close-out). Status moved review -> done 2026-06-15.

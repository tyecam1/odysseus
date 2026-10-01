---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-12-evaluate-skill-plugin-patterns
title: Evaluate lightweight skill and plugin patterns for Odysseus
status: rejected
priority: medium
task_type: implementation
created_by: human
created_at: 2026-06-12T00:45:00+01:00
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
  - .claude/**
  - .agents/**
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/docs/agentic-system-platform-assessment-plan.md
  - automation/docs/agent-ecosystem-centralisation-design.md
  - automation/docs/agent-task-centralisation-plan.md
  - automation/docs/agent-task-frontmatter-schema.md
  - https://github.com/hanfang/claude-memory-skill
  - https://github.com/senlindesign/taste-skill
  - https://github.com/blader/humanizer
  - https://github.com/coreyhaines31/marketingskills
  - caveman plugin search results / reviewed small repos
outputs:
  - automation/docs/skill-plugin-adoption-policy.md
  - automation/review/platform-evaluations/skill-plugin-patterns-evaluation.md
  - automation/review/architecture/skill-plugin-pattern-adaptation.md
result_path: automation/docs/skill-plugin-adoption-policy.md
review_report_path: automation/review/platform-evaluations/skill-plugin-patterns-evaluation.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
superseded_by: 2026-06-12-consolidate-skill-mcp-browser-deployment-policy
duplicates: []
notes: "Merged into 2026-06-12-consolidate-skill-mcp-browser-deployment-policy; candidates remain pattern sources only. Verdict MERGE in automation/review/platform-evaluations/agentic-work-item-consolidation-review.md."
---

# Task brief

## Objective

Evaluate lightweight skill/plugin patterns and encode safe adoption rules for Odysseus without installing ungoverned plugins or creating style, memory, or skill authority outside the vault.

The reviewed candidates are:

- `claude-memory-skill` / `claude-mem` style markdown memory;
- `taste-skill` design-reasoning extraction;
- `humanizer` writing anti-pattern auditing;
- `marketingskills` foundation-context skill dependencies;
- `caveman` / caveman-style communication plugins.

Treat these as pattern sources only. The goal is to improve Odysseus skill policy and registry design, not to add another plugin ecosystem.

## Required work

### 1. Inspect existing skill/plugin/agent policy

Review existing automation docs, routing docs, skill registry files if present, `.claude`/`.agents` guidance if present, and the platform assessment plan.

Identify whether the repo already has:

- skill adoption rules;
- skill registry config;
- plugin allowlist/denylist;
- writing quality checks;
- memory-candidate workflow;
- Playwright/design-analysis policy;
- global harness instruction protections.

Do not create duplicate policy documents if an existing file should be amended instead.

### 2. Create skill/plugin adoption policy

Create `automation/docs/skill-plugin-adoption-policy.md` defining:

- what counts as a skill, plugin, command, MCP, and harness instruction;
- direct-install rejection criteria;
- review and approval path for new skills;
- how skills may be task-routed;
- how skills may reference shared context;
- where skills may write outputs;
- where skills must not write outputs;
- how style and memory skills are prevented from becoming authority;
- relationship to Odysseus task lifecycle and verification routes;
- relationship to future `skill_registry.yaml` if present.

The policy must explicitly reject:

- unreviewed direct plugin installation;
- automatic writes to `.claude/**`, `.agents/**`, `CLAUDE.md`, `AGENTS.md`, or equivalent global harness instruction files;
- plugin-owned memory authority;
- automatic background memory writes to canonical vault content;
- AI-detector evasion framing;
- style rewrites that weaken precision, citation integrity, or source traceability;
- broad skill-library imports;
- any plugin that bypasses `automation/review/agent-tasks/**`.

### 3. Produce skill/plugin pattern evaluation

Create `automation/review/platform-evaluations/skill-plugin-patterns-evaluation.md` evaluating each candidate:

#### claude-mem / claude-memory-skill

Evaluate the hierarchical markdown memory pattern:

```text
core summary
  -> topic pointers
    -> detailed topic files
      -> timestamped atomic entries
```

Adopt only as review-side or derived memory candidate. Reject plugin-local or `~/.claude/memory` authority.

#### taste-skill

Evaluate the design reasoning pipeline:

```text
measure -> pattern -> principle -> quality gate -> export
```

Capture how this might support UI cockpit/dashboard/approval interface design. Feed isolated-browser requirements into Playwright MCP policy if relevant.

Reject automatic writes to global harness instruction files.

#### humanizer

Evaluate the writing anti-pattern taxonomy as a possible writing-quality audit, not a humanizer or detector-evasion tool.

Focus on:

- inflated significance;
- vague attribution;
- unsupported claims;
- promotional language;
- chatbot artefacts;
- generic conclusions;
- excessive hedging;
- formulaic rhetoric.

Reject automatic rewriting of research content and any framing around evading AI detection.

#### marketingskills

Evaluate the foundation-context pattern where specialised skills load a shared context first.

Propose whether Odysseus should support shared context files such as:

- research-engine-context;
- phd-research-context;
- public-communication-context;
- operator-context.

Reject importing the broad marketing skill library into core Research Engine.

#### caveman

Record explicit rejection unless a concrete non-gimmick capability is identified.

Likely conclusion: no adoption; plain writing and output compression policies already cover the useful parts.

### 4. Recommend skill registry amendments

If `automation/config/skill_registry.yaml` already exists, propose safe amendments. If it does not exist, document whether it should be created under the Ruflow pattern workstream rather than here.

Any proposed registry design should support:

```yaml
skill_id:
  purpose:
  allowed_task_types:
  required_context:
  allowed_inputs:
  allowed_outputs:
  denied_paths:
  authority_boundary:
  verification_requirements:
```

Do not overbuild a full skill system in this task unless one already exists.

### 5. Optional writing anti-pattern checklist

If useful, include a small review-side checklist or policy subsection for research/public writing quality.

This should be framed as:

```text
writing anti-pattern audit
```

not:

```text
humanizer
AI detector bypass
```

The checklist must prioritise:

- accuracy;
- specificity;
- citation integrity;
- plain language;
- non-inflated claims;
- preservation of the user's meaning.

### 6. Optional tests/lints

If feasible, add lightweight checks under `Scripts/automation/tests/**` for policy drift, for example:

- no allowed task writes directly to `.claude/**` or `.agents/**`;
- plugin adoption policy rejects global instruction writes;
- skill registry entries, if present, include authority boundaries;
- writing/memory plugins are not marked as canonical authorities.

Do not create a large new validation framework.

## Closed decisions already accepted

- Lightweight skill/plugin repos are pattern sources only.
- `claude-mem` contributes a hierarchical markdown memory pattern, not a memory authority.
- `taste-skill` contributes a design-reasoning pipeline and isolated Playwright principle.
- `humanizer` contributes an AI-writing anti-pattern audit, not an evasion tool.
- `marketingskills` contributes a foundation-context skill dependency pattern.
- `caveman` is rejected as a separate capability.
- Direct plugin installation is rejected unless a future reviewed task explicitly approves it.
- Style and memory plugins must not become authority.

## Open decisions to resolve or document

- whether to create a markdown memory-candidate layer distinct from Graphiti;
- whether writing-quality lint belongs in Research Engine or a separate writing support workflow;
- whether design-taste analysis belongs under Playwright MCP work or UI cockpit work;
- whether the foundation-context pattern belongs in `skill_registry.yaml`;
- how skill promotion should be approved and audited;
- whether tests should enforce plugin path restrictions now or later.

## Expected result

A concise policy and evaluation packet that lets Odysseus learn from useful plugin/skill patterns while avoiding hidden memory authority, style drift, direct plugin installs, global instruction mutation, and uncurated skill-library sprawl.

## Stop conditions

Block or reduce scope if implementation would:

- install any reviewed plugin;
- write to `.claude/**`, `.agents/**`, `CLAUDE.md`, `AGENTS.md`, or equivalent global harness instruction files;
- create memory outside governed review paths and treat it as authoritative;
- automatically rewrite research content;
- adopt AI-detector evasion framing;
- import broad marketing or style skill libraries;
- create a second skill/task authority;
- write canonical vault files;
- weaken citation/source traceability;
- require ongoing manual upkeep that exceeds the value of the policy.

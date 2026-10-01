---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-12-consolidate-skill-mcp-browser-deployment-policy
title: Consolidate skill, MCP, browser, and deployment policy
status: done
priority: medium
task_type: implementation
created_by: human
created_at: 2026-06-12T12:10:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: true
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/architecture/tool-surface-policy.md
  - automation/review/platform-evaluations/tool-surface-pattern-adoption.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
  - .claude/**
  - .agents/**
inputs:
  - automation/review/architecture/odysseus-consolidated-system-design.md
  - automation/docs/mcp-policy.md
  - automation/config/odysseus_skill_registry.yaml
  - automation/docs/claude-delegation-contract.md
  - automation/docs/agent-ecosystem-centralisation-design.md
outputs:
  - automation/review/architecture/tool-surface-policy.md
  - automation/review/platform-evaluations/tool-surface-pattern-adoption.md
result_path: automation/review/architecture/tool-surface-policy.md
review_report_path: automation/review/platform-evaluations/tool-surface-pattern-adoption.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes:
  - 2026-06-12-mcp-policy-and-pilot-integration
  - 2026-06-12-evaluate-skill-plugin-patterns
  - 2026-06-11-adapt-claude-code-best-practices
duplicates: []
notes: "One tool-surface policy covering MCP allowlisting, skill adoption over odysseus_skill_registry.yaml (the actual registry file; earlier tasks referenced a non-existent skill_registry.yaml), browser posture, deployment posture, and execution-contract deltas. Pattern sources only: Ruflow, ECC, Claude Code best-practice, claude-mem, taste-skill, humanizer, marketingskills, find-skills. No plugin installs; no .claude/.agents writes; staged drafts promote via draft PR only."
---

# Task brief

## Objective

Produce one consolidated tool-surface policy so MCP, skills, browser automation, and deployment stop accreting per-tool policies and allowlists.

## Deliverables (staged review-side, promoted via draft PR)

1. MCP integration policy extending `mcp-policy.md`: single allowlist concept, loopback/read-only default, task-routed usage, no MCP-created work outside task files, no canonical writes. Name Context7 (read-only docs) and Playwright (localhost testing) as the first pilot candidates and define their activation criteria; contain Sequential Thinking and the Codex plugin as evaluate-only.
2. Skill adoption policy over `automation/config/odysseus_skill_registry.yaml`: direct-install rejection, review/approval path, per-entry authority boundaries, foundation-context pattern, writing anti-pattern audit framing (never detector evasion), markdown-memory pattern as derived/review-side only.
3. Browser posture: all browser automation behind the MCP policy; Browser-use/Maxun stay deferred behind Playwright pilot results.
4. Deployment posture: remote-box-first, no public endpoints without security review, secret handling, service inventory; Coolify/Supabase remain deferred candidates.
5. Execution-contract deltas: bounded Claude/Codex handoff metadata (model, permission mode, worktree isolation, max turns, memory scope advisory-only) recorded as amendments to existing contracts rather than new ones.
6. Pattern adoption report: adopted / adapted / rejected per pattern source.

## Stop conditions

Block if implementation would install plugins, write `.claude/**` or `.agents/**` or global harness instruction files, create plugin/MCP-owned memory or work authority, expose endpoints, widen canonical write scope, or add per-tool policy fragments instead of the consolidated policy.

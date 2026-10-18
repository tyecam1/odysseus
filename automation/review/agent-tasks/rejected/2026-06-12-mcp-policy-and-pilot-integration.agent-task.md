---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-12-mcp-policy-and-pilot-integration
title: Implement MCP policy gate and high-value pilot integrations
status: rejected
priority: high
task_type: implementation
created_by: human
created_at: 2026-06-12T00:15:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: true
requires_mcp: true
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
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
  - automation/docs/agentic-system-platform-assessment-plan.md
  - automation/docs/agent-task-centralisation-plan.md
  - automation/docs/agent-ecosystem-centralisation-design.md
outputs:
  - automation/docs/mcp-integration-policy.md
  - automation/config/mcp_allowlist.yaml
  - automation/review/platform-evaluations/mcp-candidate-evaluation.md
result_path: automation/docs/mcp-integration-policy.md
handoff_model: codex_work_package
superseded_by: 2026-06-12-consolidate-skill-mcp-browser-deployment-policy
notes: "Merged into 2026-06-12-consolidate-skill-mcp-browser-deployment-policy (one tool-surface policy instead of per-tool policies). Verdict MERGE in automation/review/platform-evaluations/agentic-work-item-consolidation-review.md."
---

Objective:

Create the MCP policy gate for Odysseus and implement safe pilot integrations for the highest-value MCP candidates.

Required work:

1. Inspect current MCP usage, connectors, automations and existing allowlists.
2. Create a single MCP integration policy.
3. Create or extend MCP allowlist configuration.
4. Implement policy for:
   - Context7 (read-only docs retrieval);
   - Playwright (localhost/UI testing only);
   - knowledge graph memory MCP (align with Graphiti workstream);
   - Codex plugin evaluation path;
   - Sequential Thinking containment.
5. Ensure MCP usage is task-routed and source-traceable.
6. Add tests where feasible.
7. Produce recommendation on whether Context7 and Playwright should be activated immediately.

Closed decisions already accepted:
- Context7 is a preferred MCP candidate.
- Playwright is a preferred bounded MCP candidate.
- Knowledge graph memory must remain derived and non-canonical.
- Sequential Thinking is not verification.
- MCPs may not bypass task files, approval gates or authority boundaries.

Stop conditions:
- creating a second task system;
- uncontrolled browser automation;
- MCP-owned memory authority;
- public MCP exposure without review;
- direct canonical writes from MCP tools.

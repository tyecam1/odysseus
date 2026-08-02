---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-external-pattern-source-adjudication
title: "Adjudicate external agentic repositories as patterns, pilots, deferrals or rejects"
status: done
priority: medium
task_type: platform-adjudication
created_by: chatgpt
created_at: 2026-07-27T14:00:00+01:00
updated_at: 2026-07-29T00:00:00+01:00
executor: claude_subscription
execution_mode: implementation
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: codex/external-pattern-adjudication-20260729
allowed_paths:
  - automation/review/platform-evaluations/**
  - automation/review/agent-tasks/**
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
  - 10-inbox/research-engine-convergent-refinement-programme.md
  - automation/docs/agentic-system-platform-assessment-plan.md
  - automation/review/platform-evaluations/platform-candidate-assessment-archive-2026-06-12.md
outputs:
  - automation/review/platform-evaluations/2026-07-27-external-pattern-adjudication.md
  - automation/review/platform-evaluations/external-pattern-register.yaml
result_path: automation/review/platform-evaluations/2026-07-27-external-pattern-adjudication.md
review_report_path: automation/review/platform-evaluations/2026-07-27-external-pattern-adjudication.md
handoff_model: claude_codex_review_package
operator_decision_path: automation/review/platform-evaluations/2026-07-27-external-pattern-adjudication.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "This is the durable anti-tool-shopping register. It should prevent repeated re-evaluation without a changed precondition. PR-2 repair: executor normalised from claude_then_codex to claude_subscription; codex_subscription performs independent verification before merge. Branch corrected 2026-07-29 from the packet's original codex/external-pattern-adjudication-20260727 to the worktree's actual codex/external-pattern-adjudication-20260729; no other field renamed. Implemented against the already-prepared automation/review/architecture/2026-07-27-prompt-library-candidate-manifest.md (10 candidates, licence/version-verified) plus the June 2026 platform-assessment archive (preserved unless new evidence changed it) plus two already-queued sibling 2026-07-27 pilot/bake-off tasks (MarkItDown, Graphify/RepoWise) for the remaining named candidates; requires_web is true on this packet but no network fetch was performed for this implementation, per explicit task-launch instruction — the 8 candidates with no prior verified evidence (Appwrite, PocketBase, PilotDeck, OpenClaw, autoresearch, Qlib, RD-Agent, AI for Beginners) are recorded defer-until/reference-only with an explicit reopening condition of a future licence-verified quarantine-first discovery pass, not silently adopted."
---
# Adjudicate external agentic repositories as patterns, pilots, deferrals or rejects

## Goal

Create one current register for Appwrite, Supabase, PocketBase, Coolify, n8n, book-to-skill, PilotDeck, andrej-karpathy-skills, MemPalace, OpenClaw, autoresearch, awesome-claude-code, Agent Skills repositories, awesome-llm-apps, Hermes Agent, Qlib/RD-Agent, RepoWise, AI for Beginners, MarkItDown, Skillify, Graphify, Cortex memory and mattpocock/skills.

## Required fields

- exact repository and licence;
- capability family;
- current maintained status;
- specific pattern worth extracting;
- current engine gap addressed;
- overlap with existing capability;
- authority/permission/data risks;
- adoption cost and recurring maintenance;
- classification: `adopt-standard`, `adapt-pattern`, `pilot-isolated`, `defer-until`, `reject-wholesale`, `reference-only`;
- named reopening condition;
- correct destination repo;
- existing or proposed work-item link.

## Acceptance criteria

- Every named candidate receives a verdict.
- Ambiguous names are resolved or explicitly marked unresolved.
- No verdict relies on stars or marketing claims alone.
- Existing June 2026 decisions are preserved unless new evidence changes them.
- Tool overlap and opportunity cost are explicit.
- The register is machine-readable and can suppress unchanged candidates from future scans.
- No external repository is installed or granted access by this task.
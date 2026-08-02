---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-repo-intelligence-bakeoff
title: "Bake off RepoWise, Graphify and native repository intelligence"
status: blocked
blocked_reason: >-
  RepoWise and Graphify lack verified licence, concrete version, and
  single-repository identity evidence.
recheck_condition: >-
  A quarantine-first discovery pass verifies licence, concrete version,
  and single-repository identity for both RepoWise and Graphify.
priority: medium
task_type: platform-evaluation
created_by: chatgpt
created_at: 2026-07-27T14:00:00+01:00
updated_at: 2026-07-27T14:00:00+01:00
executor: codex_subscription
execution_mode: implementation
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: codex/repo-intelligence-bakeoff-20260727
allowed_paths:
  - automation/review/platform-evaluations/**
  - automation/review/architecture/repo-intelligence/**
  - automation/review/agent-tasks/**
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
  - automation/docs/architecture-index.md
  - automation/docs/agentic-system-platform-assessment-plan.md
  - tyecam1/obsidian-PhD
  - tyecam1/odysseus
  - tyecam1/misumi
outputs:
  - automation/review/platform-evaluations/repo-intelligence-bakeoff.md
  - automation/review/architecture/repo-intelligence/native-baseline.json
  - automation/review/architecture/repo-intelligence/graphify-results.json
  - automation/review/architecture/repo-intelligence/repowise-results.json
result_path: automation/review/platform-evaluations/repo-intelligence-bakeoff.md
review_report_path: automation/review/platform-evaluations/repo-intelligence-bakeoff.md
handoff_model: codex_work_package
operator_decision_path: automation/review/platform-evaluations/repo-intelligence-bakeoff.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Run in isolated environments. No persistent MCP or hook installation is authorised. PR-2 repair: execution_mode normalised from isolated-evaluation to implementation (the governed write-scope class); isolation constraints stay in force via this notes field and the acceptance criteria below."
---

## PREREQUISITE — added by adjudication round R2 (2026-07-30)

This bake-off MUST NOT run until licence, version and single-repository
identity are verified for **RepoWise** and **Graphify** by a
quarantine-first discovery pass. Both are recorded `defer-until` in
`automation/review/platform-evaluations/external-pattern-register.yaml`
precisely because that evidence is absent.

Rationale: a pilot is a positive verdict. Running a bake-off on a source
whose licence and identity are unverified would let the pilot act as its
own evidence, which is the failure the register's own rule forbids.
Verification first, then the pilot.

# Bake off RepoWise, Graphify and native repository intelligence

## Goal

Measure whether external codebase-intelligence tools materially improve agent orientation, change planning and architecture diagnosis across the three repositories compared with existing search, git and documentation.

## Test questions

- Which files implement and govern one capability?
- Which files change together?
- Where are duplicated or dead paths?
- Which architectural decisions explain current code?
- What is the blast radius of a proposed change?
- Where do documentation and implementation disagree?
- Can the tool distinguish extracted facts from inferred relationships?

## Evaluation

Compare native GitHub/git/search, Graphify code-only output and RepoWise read-only indexing on the same held-out tasks. Score answer correctness, provenance, stale-edge rate, setup time, context reduction, update cost, privacy, dependency footprint and operator usefulness.

## Acceptance criteria

- External tools run against clones or derived outputs only.
- No project skill, hook, MCP or service is installed persistently during the bake-off.
- Outputs are rebuildable and excluded from canonical authority.
- At least ten held-out questions are answered blind.
- The report can reject both tools if native methods are sufficient.
- Any proposed adoption names exact mode, repo, update cadence and removal path.

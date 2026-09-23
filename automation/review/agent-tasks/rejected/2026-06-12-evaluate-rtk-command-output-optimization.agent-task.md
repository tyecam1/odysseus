---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-12-evaluate-rtk-command-output-optimization
title: Evaluate RTK for token-efficient agent command execution
status: rejected
rejection_reason: inactive_platform_expansion
priority: medium
task_type: implementation
created_by: human
created_at: 2026-06-12T00:30:00+01:00
executor: codex_subscription
execution_mode: handoff
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
  - automation/docs/agentic-system-platform-assessment-plan.md
  - automation/docs/agent-execution-verification-contract.md
  - automation/docs/claude-code-execution-contract.md
  - automation/docs/agent-task-centralisation-plan.md
  - automation/docs/agent-ecosystem-centralisation-design.md
  - https://github.com/rtk-ai/rtk
outputs:
  - automation/docs/rtk-command-output-policy.md
  - automation/config/rtk_allowed_commands.yaml
  - automation/review/platform-evaluations/rtk-agent-command-output-evaluation.md
  - automation/review/architecture/rtk-command-output-adaptation.md
result_path: automation/docs/rtk-command-output-policy.md
review_report_path: automation/review/platform-evaluations/rtk-agent-command-output-evaluation.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Deferred 2026-06-12 consolidation: reopen only after an execution verification contract exists and a context-cost problem is demonstrated. Verdict CLOSE_AS_DEFERRED in automation/review/platform-evaluations/agentic-work-item-consolidation-review.md."
---

# Task brief

## Objective

Evaluate and, if justified, integrate RTK-style compact command-output handling for Odysseus agent shell commands. The goal is to reduce context waste during repo inspection, validation, testing, linting, git review, and PR checks without hiding exact output where correctness, auditability, or machine-readable pipelines require it.

RTK must be treated as a command-output compression adapter, not an agent framework, memory system, task system, verification authority, or evidence source.

## Required work

### 1. Inspect current execution and validation surfaces

Inspect the existing automation and execution contracts to identify where agents currently run noisy shell commands, including but not limited to:

- repo inspection;
- git status/diff/log;
- GitHub CLI use, if present;
- Python tests and linting;
- automation validation scripts;
- task linting;
- logs and diagnostics.

Document where compact output would help and where exact output must be preserved.

### 2. Create RTK command-output policy

Create `automation/docs/rtk-command-output-policy.md` defining:

- RTK's role as compact command-output adapter;
- remote-box-first usage rule;
- telemetry disabled by default and by policy;
- explicit-wrapper-first adoption posture;
- rejection of curl-pipe installation;
- raw-output retention requirement;
- commands that are safe to compact;
- commands that must not be compacted;
- relationship to proof-carrying outputs and `verification_evidence`;
- relationship to Claude/Codex/remote-shell execution contracts;
- stop conditions.

### 3. Create or defer command allowlist

Create `automation/config/rtk_allowed_commands.yaml` unless there is already an equivalent policy/config location.

Suggested structure:

```yaml
mode: explicit-wrapper-first
telemetry: disabled
install_scope: remote-box-first
allow:
  git:
    - status
    - diff
    - log
  tests:
    - pytest
    - npm test
    - playwright test
  lint:
    - ruff check
    - tsc
  inspection:
    - ls
    - tree
    - rg
    - grep
  github:
    - gh pr view
    - gh pr list
    - gh run list
deny:
  - evidence extraction commands
  - canonical promotion commands
  - machine-readable JSON pipelines unless explicitly allowlisted
  - security-sensitive scans unless raw artifact is retained
  - commands where stdout is parsed by another script
raw_log_policy:
  retain_on_failure: true
  retain_on_request: true
  path_policy: review_or_runtime_artifact_only
```

Treat this as a starting point and adapt it to the repository's existing conventions.

### 4. Produce platform evaluation

Create `automation/review/platform-evaluations/rtk-agent-command-output-evaluation.md` covering:

- expected value for Codex/Claude/remote-shell loops;
- risks of lossy output;
- safe/unsafe command classes;
- installation options and recommended installation policy;
- whether RTK should be adopted immediately or kept as a pilot;
- whether explicit wrapper mode is sufficient;
- when, if ever, hook mode should be considered;
- how RTK interacts with verification evidence.

### 5. Optional architecture note

Create `automation/review/architecture/rtk-command-output-adaptation.md` if the integration affects multiple execution contracts or introduces a new cross-cutting pattern.

This note should explain how compact output, raw tee recovery, and validation evidence fit the Odysseus execution architecture.

### 6. Add tests or lint checks where feasible

If straightforward, add tests under `Scripts/automation/tests/**` to detect unsafe policy drift, for example:

- telemetry is not enabled in RTK policy/config;
- global auto-rewrite is not the default mode;
- forbidden command classes remain denied;
- RTK output is not treated as canonical evidence;
- raw-output retention is required for validation failures.

Do not overbuild. Prefer small policy checks over a new validation framework.

## Closed decisions already accepted

- RTK is a compact command-output adapter candidate.
- RTK is not an agent framework, memory system, task system, or verification authority.
- Explicit wrapper mode comes before any auto-rewrite hook mode.
- Remote-box-first use is preferred.
- Telemetry must be disabled.
- Curl-pipe installation is rejected.
- Compact output must not replace raw logs where correctness matters.
- Evidence extraction, canonical promotion, security-sensitive scans, and machine-readable pipelines must not be compacted unless explicitly allowlisted and raw artifacts are retained.

## Open decisions to resolve or document

- exact safe command allowlist;
- exact denylist wording;
- whether RTK should be installed or only documented for pilot use;
- where tee/raw logs should be stored;
- whether RTK analytics should feed observability reports;
- how RTK output should appear inside `verification_evidence` blocks.

## Expected result

A reviewable PR or review-side output that allows Odysseus to benefit from compact agent command output without compromising auditability, evidence quality, validation correctness, or authority boundaries.

## Stop conditions

Block or reduce scope if implementation would:

- install RTK through an unreviewed curl-pipe path;
- enable telemetry;
- globally rewrite commands by default;
- hide exact output needed by tests, scripts, evidence extraction, or security scans;
- write canonical vault content;
- create a second task/execution authority;
- require laptop-local model/tool execution contrary to remote-first policy;
- make compressed output the only audit record.

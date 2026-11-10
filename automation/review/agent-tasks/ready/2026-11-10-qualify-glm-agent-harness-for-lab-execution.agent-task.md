---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-10-qualify-glm-agent-harness-for-lab-execution
title: "Enable lowest-friction GLM coding execution on the lab without Claude Code Auto Mode"
status: ready
priority: high
task_type: bounded-implementation
created_by: operator-directed-chatgpt
created_at: 2026-11-10
updated_at: 2026-11-10
executor: claude_subscription
execution_mode: smallest-qualified-vertical-slice
execution_host: lab
context_budget: low
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: dev
related_tasks:
  - 2026-11-09-qualify-glm-and-glm-flash-on-lab-odysseus
  - 2026-09-23-claude-code-zai-auto-mode-classifier-compatibility
  - 2026-11-09-lazyusage-bounded-persistent-continuation
allowed_paths:
  - config/**
  - src/**
  - routes/**
  - scripts/**
  - tests/**
  - docs/**
  - automation/review/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
inputs:
  - AGENTS.md
  - automation/review/agent-tasks/README.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/subscription-model-currency-policy.md
  - docs/runtime-work-packages/2026-11-09-lab-glm-glm-flash-execution.md
  - docs/aoteru-lab-first-operator-guide.md
  - config/estate.yaml
result_path: docs/runtime-work-packages/2026-11-10-glm-opencode-minimal-integration.md
---

# Minimal GLM execution harness on the lab

## Decision

**Use OpenCode as the first and only alternative harness**, not a comparative benchmark. It has a native Z.AI provider, noninteractive CLI and configurable permissions. This is an operator preference for minimal integration effort, not proof that it is the universally best harness. Do not assess or install Hermes, ZCode or Pi unless this one path fails an essential gate, in which case record the actual failure and propose the smallest fallback.

Assume Claude Code's third-party Auto Mode classifier remains unavailable. Keep existing `~/.local/bin/claude-glm` usable for **manual operator-approved** work during migration; do not edit or replace its host-local secrets or launcher. Never use blanket unsafe permission bypasses.

## Bounded execution

1. **Preflight and current state.** Inspect live `dev`, existing Odysseus provider and worker qualification, lab Linux account, current OpenCode install/version and upstream install/provider/permission docs. Reconcile the existing GLM/Flash qualification task, including its outstanding model-currency and Flash-entitlement gates. Use the existing preflight/lease authority. No parallel task system.
2. **Isolated OpenCode smoke test.** Install a pinned official release **only in a user-controlled lab location** if not already present. Connect the existing authorised Z.AI Coding Plan via a supported credential mechanism without copying, echoing or storing secrets in Git or logs, and verify billing route and effective model. OpenCode upstream config differs between V1 and V2: inspect the *installed version's* exact permission schema before writing any config. Use a disposable Git fixture, deny shell writes outside sandbox, secret reads, commit/push and privilege elevation. Demonstrate one successful read-only GLM task, truthful failure and refusal of a forbidden action with the smallest possible test. Do not assume the CLI `--auto` flag is a sandbox; a deny rule and external OS/worktree boundary are required.
3. **Minimal Odysseus adapter, only if smoke passes.** Add one bounded headless OpenCode worker route behind disabled-by-default qualification, reusing Odysseus task selection, model/usage accounting, process timeouts, leases, isolated worktrees, independent review and execution trace. Keep Codex preferred. Do not add an OpenCode daemon, scheduler, memory engine, agent queue, global skills or credential store. Preserve the GLM latest-model guard; a model-unverified route remains unqualified.
4. **Flash and escalation when available.** Confirm GLM-Flash model identity and subscription entitlement before adding it, separately from GLM-5.3. Demonstrate one small independent Flash task and a bounded escalation to standard GLM. Treat parallel fan-out as a later concern owned by the existing `2026-11-10-bounded-parallel-test-subagent-dispatch` item; **no fan-out benchmark or parallel orchestration implementation here**.
5. **Ship only verified capability.** Add minimal deterministic regressions and one real lab read-only backend canary. Permit write-mode only after separate authorised lease/worktree acceptance and independent review. Merge and deploy through existing governance, document rollback, preserve Claude manual fallback. If OpenCode cannot satisfy a required safety or entitlement condition without major changes, stop, report exact blocker and use existing manual Claude-GLM route rather than broadening scope.

## Acceptance

- No comparative benchmark, new scheduler, alternative framework rollout or speculative architecture design.
- Official OpenCode version and provider/model/plan verified; explicit permission denial tested on an isolated fixture, with no committed secret.
- A single Odysseus-issued GLM task executes end to end via the selected harness **only if qualified**, with bounded subprocess lifecycle, actual provider/model evidence, existing review/lease policy and rollback.
- Flash remains unqualified until independently demonstrated; a user-approved Claude Code session is a transitional route, not evidence of unattended permissions.
- Status is honest if access, latest-model verification or host qualification is blocked.

**Priority boundary:** Address this only insofar as it unblocks shipping the accepted GLM task. Preserve the standing shipping-first rule.

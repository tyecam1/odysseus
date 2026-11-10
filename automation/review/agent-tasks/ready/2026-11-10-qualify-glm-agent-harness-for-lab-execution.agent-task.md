---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-10-qualify-glm-agent-harness-for-lab-execution
title: "Benchmark and qualify the best GLM execution harness for the lab, independent of Claude Code Auto Mode"
status: ready
priority: high
task_type: evaluation-and-bounded-implementation
created_by: operator-directed-chatgpt
created_at: 2026-11-10
updated_at: 2026-11-10
executor: claude_subscription
execution_mode: evidence-first-bakeoff-then-smallest-qualified-integration
execution_host: lab
context_budget: medium
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
  - automation/review/agent-tasks/inbox/2026-11-10-bounded-parallel-test-subagent-dispatch.md
  - config/estate.yaml
  - .claude/skills/lazyUsage/SKILL.md
result_path: docs/runtime-work-packages/2026-11-10-glm-agent-harness-bakeoff.md
---

# Qualify the best GLM harness for Odysseus

## Objective

Choose and, if evidence supports it, qualify **one smallest safe GLM execution harness** for the Linux lab worker. Assume Claude Code's third-party Auto Mode classifier is permanently unavailable. During transition, the operator can run the existing `~/.local/bin/claude-glm` interactively with manual permission approval. Do not block independent progress on upstream classifier repair.

The desired workload is GLM-Flash for bounded, parallel investigations/test authoring and GLM-5.3 for difficult implementation, planning and escalation. **Odysseus remains the sole persistent scheduler, queue, task/lease authority, checkpoint store, verifier router and model-policy authority.** Do not install a second daemon, task scheduler, credential authority, memory engine or persistent agent controller merely because a candidate harness offers one.

## Existing dependencies and overlap

- The live standard-GLM adapter is read-only and unqualified on the lab; Flash entitlement/launcher, current model currency, write qualification, positive production HTTP proof and fallback are open in `2026-11-09-qualify-glm-and-glm-flash-on-lab-odysseus`. Reuse and advance that task rather than building a competing provider adapter.
- Parallel cheap subagents and measured throughput are already scoped in `automation/review/agent-tasks/inbox/2026-11-10-bounded-parallel-test-subagent-dispatch.md`; this task evaluates *harness suitability and integration*, and feeds its findings into that task. No second fan-out scheduler.
- The July 2026 PhD platform review rejected **wholesale Hermes adoption** for authority duplication. Reassess Hermes **only as a disposable execution surface** with its scheduling, memory promotion and external integrations disabled; explicitly record whether that restriction is enforceable.
- The `/lazyUsage` task is a separate session-persistence acceptance slice. A long-running Claude or Hermes session is not proof of durable Odysseus orchestration.

## Work plan

1. **Live inventory and permissions.** Inspect current `dev` HEAD, running Odysseus worker and leases, installed Linux Claude Code/GLM launchers, host user permissions, provider quotas and authenticated Coding Plan entitlement. Use the normal `aoteru preflight` and owner gates before writing. Never dump or duplicate API keys, widen network exposure, replace the working launcher or alter production services during evaluation. Confirm the actual `glm-5.3` / Flash model IDs from provider evidence rather than names assumed from task text.
2. **Compare candidates.** Quarantine-first inspect current, pinned upstream versions/licences and actual supported configuration of **OpenCode, Hermes Agent and ZCode**; include **Pi** only if the first three fail essential criteria or its low-level RPC offers a proven advantage. Compare Z.AI Coding Plan compatibility (not pay-as-you-go substitution), structured stream/exit/model attestation, read-only/write permission controls, tool and MCP injection boundaries, provider error typing, isolated worktrees, parallel children, bounded cancellation, restart/resume semantics, CLI/API integration cost and update burden. Do not treat marketing features as tested.
3. **Reproducible bake-off.** Pilot candidates separately in disposable user-owned lab directories/environments, without privileged service install or active shared worktree modifications. Use the same version-pinned, representative Odysseus coding tasks and deterministic test fixtures, including a deliberate unsafe write/command denial. Evaluate single GLM-5.3, two independent Flash tasks and a failure/escalation case where **genuine Flash access** exists. Record effective provider/model, credential billing route, end-to-end time, calls/tokens/credits when observable, test correctness, verified defects, refusal behaviour, interruptions and cleanup. Run a serial baseline; never infer lower total cost from model labels alone. Missing entitlement or a protective gate produces a precise blocker and continues independent tests.
4. **Decision and smallest integration.** Choose the winning harness by verified safe quality, governability, usable throughput and maintenance overhead; reject a candidate that cannot enforce restrictions even if it appears faster. Prefer a thin, noninteractive worker adapter feeding the existing Odysseus router/execution trace; reuse the canonical lease/write-worktree checks. Keep Codex as the healthy default; Flash and standard GLM remain separately qualified, fail-closed routes. No auto-permission bypass, unrestricted Bash, persistent unattended session, auto-merge or self-verification. A provider-specific model-currency resolver or explicit policy decision remains mandatory before production qualification.
5. **Ship or stop truthfully.** If qualified, implement the minimum adapter behind a disabled-by-default flag/host qualification, tests for failure isolation, cancellation and no shared-write races, plus one real read-only and one separately lease-authorised implementation canary. Obtain genuinely independent review, merge through existing `dev` PR governance, deploy and document rollback. If no harness passes, record a comparative rejection and the smallest next unblock, without substituting an unqualified solution.

## Acceptance

- One evidence-backed **winner or justified no-adoption decision** with reproducible versions, command lines (redacted), task fixtures and a comparison against the current Claude-GLM manual baseline.
- No production host privilege or route granted by an isolated smoke test. Explicit refusal of destructive/unauthorised operations, verified worktree separation, bounded subprocess cleanup and truthful effective-model/plan evidence.
- Where Flash is actually available, two independent workers complete bounded subunits and feed a documented GLM-5.3 escalation; record whether this improves **accepted throughput**, not merely concurrent process count. Otherwise log the precise entitlement blocker.
- Any selected production adapter completes existing preflight, lease, review and deployment gates; measured result and rollback recorded at `result_path`. Preserve incomplete acceptance as incomplete and reconcile related tasks rather than duplicating them.

**Scheduling:** This is operator-directed, but the standing shipping-first policy still applies. First deliver the smallest unblock of existing GLM qualification; do not displace already shippable urgent work for a broad framework migration.

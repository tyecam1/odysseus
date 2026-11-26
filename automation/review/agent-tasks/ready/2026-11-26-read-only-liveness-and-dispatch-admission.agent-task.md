---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-26-read-only-liveness-and-dispatch-admission
title: "Read-only liveness timeouts and admission control instead of fixed deadlines and one-at-a-time dispatch"
status: ready
priority: high
task_type: design-and-staged-implementation
created_by: operator-directed-claude-code
created_at: 2026-11-26T01:30:00+00:00
executor: claude_subscription
execution_mode: staged-design-then-opt-in-implementation
architecture: single-plus-verifier
architecture_rationale: "One implementing worker with deterministic tests, then independent cross-family review."
single_agent_baseline: "One qualified worker implements and tests against live repository evidence."
execution_host: lab
context_budget: medium
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - src/**
  - routes/**
  - companion/**
  - tests/**
  - docs/**
  - automation/review/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*token*"
  - "**/*password*"
inputs:
  - AGENTS.md
  - docs/aoteru-model-host-routing-contract.md
result_path: docs/runtime-work-packages/2026-11-26-liveness-and-admission.md
---
# Liveness timeouts and admission control

## Why

The owner (2026-11-26): deadlines and time limits are not consequential and agents are ordered only by priority. A live run was cut off at the fixed 180 s read-only deadline while Codex was still reading a repository. A first attempt (raise it to 900 s) was reverted after independent review found it conflicts with the HTTP watchdog (210 s, plus the CLI's 240 s default), with worker transport headroom (catalogue lookups can use most of the headroom before inference starts, so transport can kill the worker during timeout cleanup), and with advisory-row reconciliation (an exception before terminal persistence leaves a row `running` while the backend PID lives).

## Outcome (design first, then implementation behind a switch)

1. Replace the fixed read-only deadline with an **inactivity timeout** (no output for N minutes) plus a generous absolute ceiling, applied end to end: the HTTP watchdog (or a durable execution id so a client can poll), the CLI default, the worker headroom including setup and cleanup, and the activation deadline carried to launch and recomputed after setup.
2. Make advisory ownership and completion explicit so a row is settled after proven quiescence and the replay fence is preserved.
3. **Admission control instead of "one in flight per run"**: parallel dispatch bounded only by safety, namely write leases (no two writers on overlapping paths), per-host memory and GPU admission, provider usage-window pacing and failure backoff. The existing ready card `2026-11-21-lazyusage-parallel-window-aware-dispatch` is the vehicle; reuse it, do not duplicate it.
4. Keep the safety limits that are not deadlines: write leases, host admission, provider pacing, `max_paid_calls`, failure backoff, stall detection.

## Verification

Fault tests: a long read that keeps producing output completes; a silent hang is killed and its row settled; the HTTP client and worker bounds agree; a killed worker leaves no `running` advisory row.

## Rules that apply to this card (owner standing rules, 2026-11-06 and 2026-11-26)

- Internal Odysseus work only, through the normal branch, test, independent-review and PR lane. Sol review first (labelled GLM only if Sol is unavailable). Merge decisions follow the owner's merge rule.
- No new accounts, credentials, API keys, paid services, third-party dependencies or external writes. If a stage needs one, stop and leave a precise owner debt (`protected_handoff`); never work around it.
- Priority order is the only ordering. Do not add deadlines, time-boxes or concurrency caps of your own.
- Never touch owner approval, delegation or card-approval code paths except where this card names them, and never widen what a model may approve.
- Record the actual model used in every verification record.

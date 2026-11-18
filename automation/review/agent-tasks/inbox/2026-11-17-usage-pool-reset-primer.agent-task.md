---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-17-usage-pool-reset-primer
title: "Keep eligible usage-pool reset countdowns active with one minimum-cost primer at 100% available"
status: inbox
priority: normal
task_type: implementation
created_by: operator-directed-chatgpt
created_at: 2026-11-17
updated_at: 2026-11-17
execution_mode: existing-provider-usage-monitor-and-lab-runtime
execution_host: lab
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
  - 2026-11-16-lazyusage-sonnet-coordinator-lab
  - 2026-11-09-lazyusage-bounded-persistent-continuation
inputs:
  - AGENTS.md
  - START-AGENTIC.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/subscription-model-currency-policy.md
  - config/routing.yaml
  - config/models.yaml
  - src/estate_router.py
  - src/lazy_usage_runtime.py
  - src/lazy_usage_coordinator.py
allowed_paths:
  - src/**
  - routes/**
  - config/**
  - core/**
  - scripts/**
  - tests/**
  - docs/**
  - automation/review/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
result_path: docs/runtime-work-packages/2026-11-17-usage-pool-reset-primer.md
---

# Automatic usage-pool reset primer

## Operator objective

Whenever an eligible provider usage pool returns to **exactly 100% available (unused) allowance**, start its reset countdown, if that countdown is inactivity-gated, with **one minimal, deterministic, lowest-marginal-cost model prompt**. Keep supported reset windows counting down without the operator having to initiate a chat. This is a quota-maintenance action, not useful work, and must consume as little allowance as demonstrably possible.

Interpret 100% as **available/remaining**, not 100% consumed. If provider telemetry reports only rounded display percentages, treats 100% ambiguously, or does not expose the countdown state, do not infer the exact trigger from the display alone.

## Ground truth and boundaries

1. Inspect the *live* Odysseus usage collection, provider contracts, eligible worker/host, actual usage counters, reset timestamps and scheduler. Discover every relevant authenticated provider/pool, including Claude, Codex and GLM where supported. Do not assume they share a window type, that every pool is independently activatable, or that sending a prompt necessarily starts/restarts a timer.
2. Verify each provider's actual reset semantics from current authoritative documentation plus read-only authenticated observations. Explicitly distinguish fixed/calendar, rolling, first-use-triggered and already-running windows. **Only enable priming where a prompt has a verified, worthwhile countdown effect.** A prompt that merely spends quota or causes a reset window to move later is not acceptable.
3. Use existing subscription/CLI entitlements and explicitly authorised providers only. Never scrape a web UI, simulate a login, copy credentials, spend on new pay-as-you-go API billing, modify quotas or select a model prohibited by the subscription-model currency policy. A cheap model from a *different* usage pool does not prime the target pool.
4. Keep the mechanism under Odysseus's current usage monitor and central router. No second daemon, scheduler, provider router, queue, or agent task per heartbeat. This is not a `/lazyUsage` reasoning turn and must not steal that run's paid-call budget or be misreported as research/review output.

## Minimal implementation

- Derive a provider-and-pool-specific eligibility decision from trustworthy telemetry: identity, exact available allowance, countdown-active state, window identity, known priming behaviour, provider/model availability and caller authorisation. Unknown, unsupported, already-counting-down, partially used or exhausted pools are **no-op**.
- On an eligible transition to full allowance, choose the **lowest-cost qualified permitted model that actually draws from that same pool** and issue the shortest safe fixed prompt (e.g. `Reply OK`), minimum supported completion tokens, no tools, no context, no review. Resolve the effective model dynamically according to existing model-currency policy. Do not introduce an unqualified cheaper-tier exception silently.
- Persist a durable attempt fence **before** the provider call, keyed by provider, pool and reset-window/epoch identity; ensure at most one priming call per eligible full-window event, including service restarts, concurrent monitors, provider timeouts and usage displays remaining rounded to 100% after the call. Never retry an ambiguous possibly-billed call automatically.
- Verify a successful response and then, where the provider exposes it, that the intended countdown started. Track decision, actual provider/model, before/after allowance, reset timestamp, attempt outcome, tokens/quota impact and next eligible event, with no prompt content, credential or sensitive account payload in logs. If the countdown effect cannot be proved, disable that pool and preserve the uncertainty.
- Use an existing scheduled refresh/event hook plus bounded reconciliation, not tight polling. Add a global disable switch, per-pool enable/disable, strict per-day/per-window prompt caps, typed failure/backoff, and an observation-only/dry-run mode. Start disabled in deployment; only activate proved eligible pools, implementing the operator's standing preference after the acceptance checks.

## Acceptance

1. A documented provider/pool matrix states source evidence, what 100% means, whether the timer is already active, whether first use starts it, the actual permitted minimum-cost model and unresolved limitations.
2. Deterministic tests cover exact 100% vs 99.9%/rounded 100%, 100%-consumed confusion, idle vs active countdown, fixed vs first-use windows, pool/model mismatch, unsupported/auth-failed paths, concurrency, crash recovery, timeout ambiguity, errors/backoff and no duplicate calls.
3. A real permitted low-cost canary proves that exactly **one** prompt causes the intended countdown to start on at least one genuinely supported pool. If the provider does not expose enough evidence, report this as unverified; do not fabricate a pass or turn on the policy.
4. Prove ordinary agentic work, subscriptions, provider routing, task/lease authority and existing usage counters remain unaffected. Record actual marginal cost and rollback, independent verification, and test/deployment evidence in `result_path`.
5. Keep this new optional optimisation in `inbox` under the existing shipping-first backlog priority; do not displace currently shippable accepted work.

Stop or narrow scope where the provider lacks a lawful, reliable, low-cost same-pool activation route. Zero unnecessary calls is preferable to a speculative "keep timer ticking" request.

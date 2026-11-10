---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-11-10-haiku-5-5-parallel-test-orchestration
title: "Qualify Haiku 5.5 and parallel test agents in Odysseus orchestration"
status: ready
priority: high
task_type: bounded-orchestration-contract-and-execution-upgrade
created_by: chatgpt
created_at: 2026-11-10T09:46:00+00:00
executor: sonnet-class-orchestrator
execution_mode: finite-autonomous-implementation
resource_profile: bounded-parallel
risk_level: medium
approval_required: false
source_traceability_required: true
requires_local_model: false
requires_remote_compute: false
requires_web: true
repo: tyecam1/odysseus
branch: dev
inputs:
  - docs/aoteru-estate-execution-contract.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/subscription-model-currency-policy.md
  - docs/aoteru-long-horizon-autonomous-convergence.agent-task.md
  - config/models.yaml
  - config/routing.yaml
  - config/estate.yaml
  - config/initialising-prompts.yaml
outputs:
  - updated authoritative orchestration and model/host routing contracts
  - tested Haiku 5.5 model/provider and effort capability discovery
  - bounded concurrent test-agent orchestration through existing task/lease/telemetry authority
  - isolated deterministic test sharding, structured failure triage and Sonnet-level integration review
  - benchmark and rollback evidence with truthful live-vs-code deployment status
---

# Haiku 5.5: model contract integration and parallel test agents

## Goal

Integrate **Claude Haiku 5.5** as a first-class, high-throughput subagent for *independent* test execution, test-failure investigation, log summarisation and bounded test-gap discovery. A single Sonnet-class controller owns decomposition, scheduling, integration and release gates. Aim for **8 concurrent Haiku test agents**, with a **measured path to 16** when rate limits, cost, workload independence and host resources permit. Do not spawn 8 agents merely because 8 slots exist.

**Crucial distinction:** deterministic tests must run as deterministic commands. Do not pay an LLM to substitute for pytest, unit-test assertions, static analysis or a deterministic parallel runner. Haiku agents can own distinct test shards, invoke commands in isolated environments, interpret failures, prepare scoped fixes when authorised, and return evidence. The controller/reviewer, not agents voting together, decides whether a release passes.

## Release truth and compatibility

Anthropic announced Haiku 5.5 on **2026-10-07**. The direct Claude API model ID is **`claude-haiku-5-5`** (fixed ID, **no date suffix or separate alias**). It supports effort controls/adaptive thinking and is explicitly intended for high-volume subagents. Verify provider entitlement/availability *on the actual dispatch host and credential path* before activating. CLI-specific aliases and API billing are not interchangeable; inspect Claude Code availability and implement only the real qualified transport(s).

Official references:
- [Release](https://www.anthropic.com/claude-haiku-5-5)
- [Overview](https://platform.claude.com/docs/en/models/haiku-5-5/overview)
- [Migration guide](https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide)

Review migration incompatibilities, including the newer tokenizer (roughly 30% more tokens than Haiku 4.5 for the same text), effort support, and provider-recommended request parameters. For direct API requests, do not silently forward incompatible `temperature`, `top_p` or `top_k`. Record actual input/output/thinking tokens, retries and effective model, not assumed Haiku 4.5 accounting.

## Contract and implementation work

1. **Inspect current live truth.** Read repository operating rules, applicable contracts, routing/provider adapters, task envelope/schema, lease scheduler, executor qualification, test commands and current telemetry. Search for existing Haiku routing, subagent parallelism, pytest sharding, prompt register entries and working tests. KEEP/EXTEND/WRAP rather than introducing another scheduler, task queue, router or registry. Follow the active estate authority: Odysseus owns runtime, not Misumi/PhD domain content.
2. **Model capability/qualification.** Extend the existing provider-neutral model and route declarations for a `haiku-fast-subagent` capability using Haiku 5.5 only where availability and adapter support are actually verified. Preserve subscription currency policy for **premium general-purpose** subscription execution; the explicitly cost-optimised Haiku subagent lane must be separately scoped, justified and never silently replace premium Sonnet/Opus reasoning or independent verification. Record transport, effective model ID, provider/account entitlement, effort (`low` by default for routine test operations, adaptive escalation only on evidence), and explicit per-host qualification. Fail closed when eligibility/availability cannot be verified; preserve working incumbent routes.
3. **Bounded test fan-out.** Add a policy-driven `parallel_test_agents` mode to the *existing* execution control plane, with one controller, N independently owned tasks, N unique correlation/shard IDs, fixed worktree or equivalent test-environment isolation, per-worker leases and cancellation/timeout behaviour consistent with existing mechanisms. Target N=8; benchmark 1/4/8/16 and cap dynamically using configured max concurrency, host CPU/RAM/GPU and provider concurrency/rate limits. No recursive subagents, duplicate execution, shared writable test fixtures, cross-repo permission expansion or second queue. A worker cannot mutate the primary worktree or edit another shard's files. Changes, if permitted at all, use existing authorised write scopes and are serially integrated by the controller.
4. **Test execution workflow.** Build a deterministic test manifest/shard plan with explicit commands, input/fixture boundaries, duration estimates and expected artefacts. Use pytest-xdist or existing parallel commands where safe; avoid cross-shard shared DBs, ports, caches or hardware. Haiku workers run their assigned shard when the transport permits tool use, collect stdout/stderr/JUnit or equivalent evidence, classify failures (product defect, flaky test, infra, test contract mismatch), propose minimal reproducible commands and identify missing coverage. Have Sonnet-class integration/verifier independently re-run affected tests. Whole-suite and merge gates remain deterministic and cannot be satisfied by AI claims or summaries.
5. **Retry and economics.** Bound per-shard agent steps, token spend, paid calls, retries, wall-clock deadline and global concurrency. Use exponential backoff for 429/5xx, prevent retry storms with a shared budget, support graceful cancellation on fatal gates, and reduce fan-out automatically if queueing, context/token inflation or shared-host contention outweigh speedup. Keep per-shard traces and aggregate cost, pass/fail, effective model/effort, wall-clock, queueing, rate-limit, duplicated-work and final deterministic outcome. Protect secrets, sensitive prompts and full transcripts in logs.
6. **Contracts and operational docs.** Update `docs/aoteru-estate-execution-contract.md`, `docs/aoteru-model-host-routing-contract.md` and the smallest necessary config/provider/worker/test/runbook surfaces. Reconcile the existing **"no swarm by default"** rule by documenting **this measured, independence-gated exception**. Preserve deterministic-first, weakest-adequate-mechanism, source/host/repo authority, lease approval and scientific-integrity invariants. Do not silently widen autonomous write rights.

## Required verification

- Add unit/contract tests for correct model-ID resolution, eligibility fail-closed, effort compatibility, bounded fan-out, stable shard identity, exact-once ownership, lease-isolated writes, timeout/cancel, rate limits/backpressure, idempotent retry, deterministic PASS/FAIL and no forged verification.
- Integration-test a real small parallel run (where credentials/host are available), with at least one deliberately failing shard, one timeout/429 injection and one shared-fixture conflict prevention test. Collect evidence of actual overlapping agent dispatch, not sequential invocations labelled parallel.
- Benchmark equivalent **single-agent, 4-agent, 8-agent and 16-agent** workloads at least three times each when capacity permits. Record median/p95 wall-clock, total billed tokens/cost, test pass rate, model/effort, host utilisation and retry rate. Promote 8/16 only if it actually improves useful verified throughput without correctness regressions or unbounded cost. If unavailable, mark **code-complete, live-qualification-blocked**, not "deployed".
- Preserve and rerun existing model-route, subscription policy, worker, lease and independent-verification tests; run the repository's relevant full deterministic suite. No new critical flaky tests.
- Roll back by disabling the feature flag / qualified alias and returning to existing sequential or deterministic-parallel routing. Do not remove incumbent provider paths.
- Conclude with explicit `IMPLEMENTED / TESTED / LIVE-QUALIFIED / DEPLOYED` states, commits, exact commands, evidence, residual blockers and any next action.

## Non-goals / authority

- No mass Haiku deployment for arbitrary tasks, no implicit promotion to high-consequence decisions, no second scheduler or model registry, no changes to research claims/PhD evidence, and no direct writes to Misumi/obsidian-PhD.
- Do not change the global prompt register merely to store this one-off work item. If execution reveals a reusable *session initializer* or genuinely novel prompt exemplar, use the existing `docs/initialising-prompt-register.md` process and immutable evidence rules.
- Do not claim this work item itself executes the upgrade. An agent must pick it up, implement, test, verify and deploy separately.

## Executor entry point

From a clean `tyecam1/odysseus@dev` worktree, run as a **Sonnet-class controller at high effort** (resolve current eligible subscription model at dispatch). Read this task and its inputs, reconcile live HEAD/provider access, implement the smallest safe routed capability, prove parallelism + deterministic outcomes, and record evidence. Continue across independent slices without asking for per-slice approval; stop only at a real permission, subscription, host or deployment gate.

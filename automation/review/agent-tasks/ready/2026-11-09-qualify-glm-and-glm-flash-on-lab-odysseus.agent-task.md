---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-09-qualify-glm-and-glm-flash-on-lab-odysseus
title: "Make Z.AI GLM and GLM Flash executable through the Odysseus backend on the lab PC"
status: ready
priority: high
task_type: implementation
created_by: operator-directed-chatgpt
created_at: 2026-11-09
updated_at: 2026-11-09
executor: codex_subscription
execution_mode: evidence-first-bounded-implementation
architecture: single-plus-verifier
architecture_rationale: "One worker owns host/provider integration and deterministic testing; a separate qualified worker verifies routing, lease preservation and production-readiness. Avoid parallel routers or speculative model qualification."
single_agent_baseline: "Reconcile the closed unmerged GLM candidate PR and the lab commissioning evidence, repair the smallest host-local launcher/transport defects, then qualify both provider routes through real Odysseus execution."
execution_host: lab
context_budget: medium
coordination_reason: "Lab host and shared Odysseus backend are one fault domain; one implementation owner protects leases and existing Codex workloads."
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
  - 2026-09-23-claude-code-zai-auto-mode-classifier-compatibility
  - 2026-10-01-provider-quota-health-in-routing-preflight
  - 2026-09-13-operating-contract-model-role-evaluation-system
allowed_paths:
  - config/models.yaml
  - config/estate.yaml
  - config/routing.yaml
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
  - docs/aoteru-lab-first-operator-guide.md
  - config/estate.yaml
  - config/models.yaml
  - src/estate_router.py
  - routes/estate_routing_routes.py
  - https://github.com/tyecam1/odysseus/pull/38
  - https://github.com/tyecam1/odysseus/pull/130
  - https://github.com/tyecam1/odysseus/pull/133
outputs:
  - working lab-host GLM and GLM Flash launch paths with accurate model, prompt and exit-status evidence
  - independently qualified read-only backend execution for both provider routes
  - governed implementation-mode proof for each route permitted to write
  - tested provider health, quota, fail-closed and qualified Codex-fallback behaviour
  - deployment evidence, regression tests and rollback instructions
result_path: docs/runtime-work-packages/2026-11-09-lab-glm-glm-flash-execution.md
review_report_path: automation/review/2026-11-09-lab-glm-glm-flash-independent-review.md
handoff_model: independent-qualified-provider
operator_decision_path: docs/runtime-work-packages/2026-11-09-lab-glm-glm-flash-execution.md
supersedes: []
duplicates: []
notes: "Operator-requested enablement. This is the missing operational qualification of the existing GLM candidate/failover work, not a new model router. Shipping-first applies: admit as an unblock for accepted work, not optional model optimisation."
---

# Make GLM and GLM Flash runnable in Odysseus on the lab PC

## Current evidence and exact gap

- The Odysseus lab worker is configured as `hz2-workstation` (`dmem-HP-Z2-Tower-G9-Workstation-Desktop-PC`), with `deterministic`, `local`, `codex`, and `codex-write` qualified in the committed estate registry. Reconfirm live host identity, reachability, state and permissions before use.
- PR #38 proposed a **candidate-only** GLM paid executor but was **closed unmerged** on 2026-10-21. Do not claim it is live, automatically merge it, or copy outdated code without reconciling current `dev`.
- PR #130 merged the Codex-quota-to-qualified-GLM *policy*, not the execution path. PR #133 documented a host-local Linux GLM launcher/credential experiment; it did **not** prove accurate prompt passage, actual model identity, exit status or Odysseus dispatch. Windows DPAPI credential storage is not portable to Linux.
- Existing `config/models.yaml` and `src/estate_router.py` expose only Codex as a qualified paid provider/dispatch implementation. GLM and GLM Flash require real backends, not YAML aliases or standalone launcher success.
- The separate Z.AI Claude Code auto-mode classifier task concerns upstream compatibility and must not be conflated with successful noninteractive inference.

## Execution

1. **Reconcile before implementation.** Inspect live `dev`, PR #38's candidate diff, the existing model/provider/estate/worker APIs, lab operator evidence, registered task contracts, running services and available executors. Run `aoteru preflight` or the backend equivalent and respect the recommendation; acquire no write lease implicitly. Reuse only still-valid parts of the candidate implementation. Check whether recent merged code has already satisfied any acceptance item; do not repeat work.
2. **Fix host-local execution.** On the **lab Linux worker**, verify the genuine Z.AI Coding Plan entitlement for (a) standard GLM and (b) GLM Flash, their current eligible concrete model identities, and safe noninteractive launch mechanisms. Test with a distinct, exact sentinel prompt and parseable output, **stdin explicitly managed**, exit code checked, no interactive terminal or hidden prompt substitution. Record which route is available/unavailable, not assumed. Keep credentials in approved permission-scoped host storage, never in Git, logs, command-line arguments or task payloads. Do not copy Windows DPAPI blobs or create duplicate secret stores. No credential renewal or scope broadening without the required operator action.
3. **Integrate the existing backend.** Add the smallest provider adapter(s) to the central Odysseus paid-provider registry, estate-worker dispatch and /api/estate/run path. Make standard GLM and GLM Flash independently addressable and distinguishable for qualification, with correct provider, concrete-model, host and usage attribution. Do not introduce a new task queue, router, lease owner, execution database or parallel credentials mechanism. Keep Codex the healthy default. Reconcile Flash vs standard admission with the subscription-model currency policy: no stale hard pins, silent lower-tier fallback or unverifiable 'latest' claims. If the provider cannot attest effective model currency, fail closed and record the precise blocker.
4. **Preserve execution authority.** Exercise read-only calls first. For code-writing work, require the existing active repo lease, approved write scope, isolated worktree and worker lifecycle; reject direct bypass. Quota/auth/rate-limit failures must be typed and scoped per provider or route. Prevent retry storms and overlapping GLM launches if live quotas show concurrency is unsafe. Candidate-only or absent Flash may not be silently promoted or substituted.
5. **Test, qualify, deploy.** Cover standard and Flash with deterministic adapter tests, invalid credential, missing launcher, model mismatch, empty stdin, quota exhaustion, wrong host, task restrictions and lifecycle regression cases. For each, run a **real lab `/api/estate/run`** bounded task and capture a prompt-accurate response, exit status, actual model, route decision, backend trace, elapsed time and usage where available. Run one separately authorised write-mode test per qualified implementation route, with unchanged lease and review boundaries. Prove a Codex quota error routes to **qualified** GLM (never unqualified Flash), non-quota errors do not, and when both are unavailable unaffected work proceeds. Independently verify implementation and rollback, then deploy/restart only through authorised operations.

## Acceptance and stop conditions

- Both standard GLM **and** GLM Flash pass separate noninteractive **lab-host** smoke tests and a **real end-to-end Odysseus backend** test with exact prompt/response, nonzero error handling, provider/model identity and trace. A launcher-only smoke test or config registration is not sufficient.
- Both are explicitly qualified for the tested task classes; unavailable access is reported as a specific blocker, not a false success. They are not automatically granted independent-review equivalence merely because they can execute a prompt.
- Preflight, status, health and fallback distinguish provider outage from worker outage; Codex remains preferred while healthy and existing lease/verification rules survive switching.
- Relevant regression suites pass; deployed lab paths are re-tested after restart; evidence and rollback recorded at `result_path`. Task remains unfinished until these real-path proofs exist.
- If one provider route requires a genuinely protected human credential/account action, provide only the exact action and evidence, continue independent work, and leave that route unqualified. Never weaken security to claim completion.

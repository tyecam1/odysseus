---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-16-lazyusage-sonnet-coordinator-lab
title: "Deploy Sonnet 5.5 as the /lazyUsage cognitive coordinator on the lab, with governed Codex, GLM and Opus consultation"
status: ready
priority: high
task_type: implementation
created_by: operator-directed-chatgpt
created_at: 2026-11-16
updated_at: 2026-11-16
executor: claude_subscription
execution_mode: backend-integration-and-live-qualification
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
  - 2026-11-09-lazyusage-bounded-persistent-continuation
  - 2026-11-09-qualify-glm-and-glm-flash-on-lab-odysseus
  - 2026-11-09-autonomous-blocker-reconciliation-and-opus-escalation
  - 2026-09-13-operating-contract-model-role-evaluation-system
inputs:
  - AGENTS.md
  - START-AGENTIC.md
  - .claude/skills/lazyUsage/SKILL.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/subscription-model-currency-policy.md
  - docs/runtime-work-packages/2026-11-09-lazyusage-lab-persistence-acceptance.md
  - docs/runtime-work-packages/2026-11-09-lab-glm-glm-flash-execution.md
  - src/lazy_usage_runtime.py
  - src/estate_router.py
  - src/estate_worker.py
  - routes/lazy_usage_routes.py
  - companion/laptop_client/aoteru.py
  - config/models.yaml
  - config/estate.yaml
  - config/routing.yaml
  - config/initialising-prompts.yaml
allowed_paths:
  - src/**
  - routes/**
  - config/**
  - core/**
  - scripts/**
  - tests/**
  - docs/**
  - companion/laptop_client/**
  - .claude/skills/lazyUsage/**
  - automation/review/**
  - evals/prompt-applications/**
  - evals/prompt-evolution/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
result_path: docs/runtime-work-packages/2026-11-16-lazyusage-sonnet-coordinator-lab.md
---

# Sonnet cognitive coordination for persistent /lazyUsage

## Operator objective

Deploy **Claude Sonnet 5.5 as the bounded planning, decomposition, progress-reconciliation and synthesis model** for opt-in /lazyUsage activations on the Linux lab backend. Let it consult independently qualified ChatGPT/Codex, Z.AI and Claude Opus routes when Odysseus' current routing contract authorises each use. The lab runs independently of the laptop; the laptop remains only a controller.

**Odysseus stays the sole authoritative task orchestrator.** Its existing service lifecycle, `lazy_usage_runs` persistence, owner queues, routing, leases, execution envelopes, checkpoints, budgets, verification and stop/resume controls remain authoritative. Sonnet proposes bounded plans and interprets evidence; it does not self-authorise dispatch, select unqualified hosts or providers, mutate task state from prose, relax approvals or become a second long-running scheduler. No new harness, daemon, queue, agent memory, process supervisor or permanent interactive Claude session.

## Known baseline and constraints

- PRs #277-#279 merged on 2026-11-10/11. A real lab deployment and restart/disconnect controls were recorded, but **a real queued write-task delivery and a Sol recheck of the final delta were still owed** in the latest acceptance report. Reconcile live HEAD, current deployed SHA, current run state and newer evidence; do not claim those gates closed on previous report alone.
- The current `src/lazy_usage_runtime.py` loops deterministically through queue/frontier selection and only dispatches qualified routes. It does **not** yet implement a qualified Sonnet cognitive coordinator. Preserve and reuse this loop.
- The contract assigns Sonnet a foreman/orchestration role, Codex independent implementation/verification, Opus exceptional conceptual/architectural blocker work and GLM qualified economical work. The current implementation does **not** establish that all these routes exist on the lab.
- The 2026-11-10 operator policy restricts routine independent reviews to qualified Haiku 5.5, Terra 6.1 or GLM-Flash. Opus/Sol/Fable premium **review** needs a documented, explicit per-review operator exception; this request is **not** a blanket exception. Opus *planning/adjudication* is permitted only for consequential ambiguity under the existing blocker-resolution policy, qualified credentials and budgets, not trivial tasks.
- Authenticated Claude subscription execution through the **unmodified official Claude Code CLI** or an explicitly permitted API route must be checked against current provider terms and lab/university policy. Do not intermediate Claude.ai session credentials, impersonate another user, copy profile/token files or create unapproved API charges. If the user's authorised CLI route cannot support durable headless use, stop that route with its exact blocker and do not bypass restrictions.
- **ChatGPT access means the existing ChatGPT-authenticated Codex CLI/worker route**, unless a separate, explicitly authorised OpenAI integration is already available and qualified. A ChatGPT consumer session, private conversation/memory, or Plus login is not by itself an OpenAI API key or an RPC service; never scrape the ChatGPT UI or invent access.
- Existing lab Z.AI `claude-glm` only has candidate read-only backend support; model currency/Flash entitlement and write qualification are outstanding. Manual interactive Claude GLM approval is **not** unattended backend qualification.

## Implementation and delivery

1. **Reconcile and preflight.** Inspect `dev`, all relevant task cards, current lab service/run history, provider-health records, current plan/model policies and available credential *mechanisms* without exposing secrets. Run canonical `aoteru preflight` and obtain existing scoped worktree/lease before edits. Recheck the existing live write-delivery, finalize-commit and owed-review debts and resolve genuine blockers when safe.
2. **Sonnet route and bounded advisory.** Qualify the lab's actual authenticated Claude model and endpoint using a minimal, read-only, noninteractive test with attested effective Sonnet model, provider identity, structured result, clean exit status, deadline and usage accounting. Prefer the provider's rolling Sonnet family alias with a validated **Sonnet 5.5 effective identity** rather than a stale permanent pin. No autonomous file or shell tool permissions for the coordinator; it receives minimum required task metadata/evidence pointers, not raw secrets or whole repositories. Fail closed when model, auth, account permission or terms are unverified.
3. **Single coordinator within the existing loop.** Add an opt-in default-Sonnet *cognitive step* for each activated run, responsible for meaningful queue prioritisation advice (respecting shipping-first), task decomposition, cross-worker evidence interpretation and next-action synthesis. Use a strict bounded/validated plan output consumed by Odysseus; the controller independently validates repo authority, task revision/HEAD, budgets, host eligibility, executor qualifications, protected gates and preflight before acting. Avoid a second policy ranking and do not create model calls for inventory or other decisions deterministically resolved. Charge the Sonnet call against the same `lazy_usage_runs` paid/tool budgets, record real model usage and checkpoint provenance across restarts, avoid repeated unchanged-HEAD planning and never replay an uncertain call after interruption.
4. **Consultation via existing routing contracts.** Dispatch task-specific, separately bounded consultation calls only through qualified Odysseus execution routes and existing budget/health gates:
   - **Codex/ChatGPT:** ChatGPT-authenticated Codex CLI for coding, cross-family technical scrutiny, and independent analysis; existing required leases and read/write boundaries apply.
   - **Z.AI:** GLM standard or Flash only after the separate real lab host, exact model, subscription/currency and read/write-role qualification. Keep candidate-only routes inaccessible to autonomous execution.
   - **Opus:** current authenticated `opus` rolling alias, medium effort, only on evidenced consequential ambiguity, architecture/synthesis or blocker escalation; never automatically use it for routine reviews or to bypass a quota. Preserve operator-required premium review exceptions and model independence.
   - If any consult route is unavailable, retain precise blocker/owed review, continue independent eligible work, and do not silently substitute a different plan/provider.
5. **Test, deploy, verify.** Exercise at least one real owner-queued task where the Sonnet coordinator produces a scoped plan, Odysseus selects a qualified worker, a real implementation/analysis is completed, tests and independent verification occur, and the owner state plus prompt-application trace are reconciled. Test conflicting model advice, unsupported provider, model mismatch, missing permission, quota exhaustion, protected human gate, stop/cancellation, spent budgets, duplicate-plan prevention, client disconnection and controlled lab service restart. No repeated paid calls or double mutations. Do independent qualified review, govern PR merge into `dev`, deploy to the already-running systemd Odysseus service, verify health/routing/plan/accepted task outcome and keep rollback. Preserve the default-off capability until proved, then allow operator opt-in without changing global defaults.

## Acceptance and stop

- Sonnet 5.5's **effective model**, provider/auth route and actual lab availability independently verified; if unavailable, report the smallest genuine operator-auth/account action rather than claiming deployment.
- A backend /lazyUsage activation uses Sonnet **as a bounded coordinator** while Odysseus exclusively owns scheduling/dispatch/persistence/verification. An interactive Sonnet window alone is not acceptance.
- Codex, GLM/Flash and Opus consultations are individually qualified and tested when available, or each blocked with evidence; no false blanket claim that all three work.
- Existing `am lazy start/status/pause/resume/stop` work from the laptop; disconnected/restarted execution, limits and protected gates hold.
- Live queued work delivers with authentic verification, trace, status reconciliation and rollback. Final report distinguishes implemented, deployed, proven and owed.

Do not broaden the deployment into a comparative harness exercise. Ship the smallest valid vertical slice first, with later provider enablement strictly dependent on existing qualifications.

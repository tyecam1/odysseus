---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-09-lazyusage-bounded-persistent-continuation
title: "Deploy durable /lazyUsage execution inside the existing Odysseus lab backend"
status: ready
priority: high
task_type: skill-reliability
created_by: operator-directed-chatgpt
created_at: 2026-11-09T15:47:00+00:00
updated_at: 2026-11-10
executor: claude_subscription
execution_mode: backend-durable-opt-in-live-acceptance
execution_host: lab
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: dev
related_tasks:
  - 2026-09-28-persistent-blocked-route-rerouting-long-horizon
  - 2026-09-01-human-attention-wip-autonomous-dispatch
  - 2026-11-09-autonomous-blocker-reconciliation-and-opus-escalation
  - 2026-11-09-qualify-glm-and-glm-flash-on-lab-odysseus
  - 2026-10-01-sol-packet-efficiency
inputs:
  - AGENTS.md
  - .claude/skills/lazyUsage/SKILL.md
  - START-AGENTIC.md
  - config/initialising-prompts.yaml
  - docs/initialising-prompts/estate-queue-priority-execution-v2.md
  - scripts/agentic_portfolio.py
  - docs/aoteru-model-host-routing-contract.md
  - docs/subscription-model-currency-policy.md
  - docs/runtime-work-packages/2026-11-09-lab-glm-glm-flash-execution.md
  - config/estate.yaml
  - docs/aoteru-lab-first-operator-guide.md
allowed_paths:
  - .claude/skills/lazyUsage/**
  - config/**
  - src/**
  - routes/**
  - scripts/**
  - tests/**
  - docs/**
  - automation/review/**
  - evals/prompt-applications/**
  - evals/prompt-evolution/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
  - "**/*.pdf"
result_path: docs/runtime-work-packages/2026-11-09-lazyusage-lab-persistence-acceptance.md
---

# Persistent /lazyUsage inside Odysseus, lab-first

## Operator decision, 2026-11-10

**Do not install or integrate a second agent harness.** Odysseus is the agent/task orchestration runtime. Deliver /lazyUsage as a **durable, opt-in backend job** on the existing Linux lab Odysseus service, not a laptop Claude session, a CLI Stop hook, or a second independent scheduler. The laptop only starts, inspects, pauses/resumes or stops a run. Once explicitly activated, eligible bounded work should proceed without requiring the laptop or chat session to remain connected.

Reuse the canonical /lazyUsage intent and active `estate-queue-priority-execution@v2` policy. Do not duplicate them into a new prompt register, task authority, memory store or runtime daemon. Keep the existing `~/.local/bin/claude-glm` with manual approval as a transitional *interactive* tool; do not confuse its manual permission path with permission for unattended backend writes. Assume Claude Code third-party Auto Mode classification remains unavailable. OpenCode, Hermes, ZCode, Pi, new skill-host frameworks and harness benchmarking are explicitly **out of scope**.

## Current evidence and gap

The 2026-11-09 lab activation proved skill discovery, lab-host three-repository frontier discovery and one bounded read-only Odysseus task. PR #258 added bounded continuation **instructions** to the skill. Neither establishes a process-independent /lazyUsage backend job: there is no demonstrated autonomous succession of real governed tasks after client disconnect or lab service restart. The previous task investigated /goal/Stop hooks but that cannot supply the required process-exit persistence.

The existing systemd-managed `odysseus-aoteru-lab.service` provides the lab service lifecycle; Odysseus owns repo authority, task/host/model routing, queues, state, leases and review. Identify and reuse its real background-job, execution and status primitives if present. Do not assume a particular scheduler or task-runner implementation until the current code and live service have been inspected.

The lab's GLM execution remains **read-only and not production-qualified** pending model-currency policy; GLM-Flash entitlement and write execution remain unproven. Reuse the separate GLM qualification task. Persistent execution may dispatch only actually qualified providers and task roles, including existing Codex/deterministic routes where eligible; it must not globally auto-approve Claude tools or manufacture GLM/Flash qualifications.

## Implementation order

1. **Reconcile live estate and authority.** Inspect the live `dev` HEAD, running lab service, existing scheduler/lifecycle, queues, active work/leases and related three-repo task paths. Run `aoteru preflight` (or authoritative backend equivalent) before changes. Resolve overlap with persistent blocked-route and human-attention tasks; enhance their actual existing primitives, not a second workflow engine. Check current /lazyUsage skill and active initializer. Retain the shipping-first priority.
2. **Durable, operator-controlled activation.** Add the smallest opt-in `start/status/stop/resume` surface through existing Odysseus backend/API/client mechanisms. On start, register a persistent bounded run record with caller/authority, selected initializer version, repo scope, budgets, active task and last checkpoint. A disconnect must not cancel the run. Disabling/stopping must prevent new dispatch, request bounded cancellation of in-flight work, and preserve audit and lease correctness. No auto-start by default, no always-on unlimited calls and no new privileged service.
3. **Backend continuation and checkpoints.** Use the lab service's existing lifecycle and persistent store to advance one governed task at a time: refresh the actual owner frontier, choose the cheapest adequate **qualified** route per /lazyUsage selection rules, preflight, check authority and applicable lease, dispatch, observe result, deterministically verify, request independent review only where required, reconcile task status and move to the next eligible item. Persist a compact checkpoint/owed-review record before and after meaningful transitions (not private transcripts or secrets). On service/process restart, resume an explicitly active run safely from durable records. Adopt idempotent dispatch/reconciliation so a crash cannot duplicate paid calls, PRs or mutations; where completion is uncertain, quarantine/reconcile rather than blindly replay.
4. **Partial blockers and budget guardrails.** Preserve the existing skill's bounded-session ceilings as initial defaults: 4 hours per activation, 12 paid calls, 150 total tool calls, eight consecutive no-delivery continuation turns and three repeats of the same failure. Enforce these at **runtime**, counting child work and restarts; terminal budget exhaustion requires fresh operator activation rather than silent renewal. Preserve manual stop, protected approvals, safety/ethics/security/finance/publication gates, owner-specific repository boundaries, current HEAD and write leases. Sol/other reviewer quota errors park only dependent verification with a truthful retry condition; dispatch other eligible work. Unknown quota is not verified capacity. No same-family GLM self-approval for independent reviews. Fail closed where no qualified autonomous write route exists; do not wait forever or repeatedly poll.
5. **Use the existing lab deployment.** Extend the existing systemd-supervised Odysseus service, not an external shell loop, scheduled Claude invocation, tmux session, Stop hook or second daemon. Keep the interface tailnet-only and the laptop as controller. Do not change user credentials or host policy without the requisite operator authority. Roll out disabled by default, prove bounded acceptance, independently review, merge into `dev`, deploy via the normal release process and record both code and activation rollback. Update the laptop /lazyUsage skill only where its entry-point wording must reflect backend dispatch. Keep the immutable initializer unchanged unless measured evidence requires a versioned evolution.

## Required live acceptance

- **Real delivery, not inventory:** a laptop-initiated /lazyUsage backend activation selects and completes at least one low-risk **real eligible queued task** through the owning repo's preflight, lease (if necessary), deterministic tests and independent verification, with evidence, correct status transition and prompt-application trace. A read-only arithmetic answer or a run that only lists queues is insufficient.
- **Persistence:** disconnect the laptop/client, then verify the activated lab job continues and delivers or advances independently. Restart the existing Odysseus service during a controlled disposable/low-risk run and verify status/checkpoint recovery with no duplicate mutation, tool call or paid model dispatch. Do not reboot the host without specific authorisation.
- **Governance:** demonstrate genuine protected human-only gate, stale `approval_required` metadata corrected through actual authority, Sol quota unavailable while other independent work proceeds, unqualified GLM write refusal, stale HEAD/lease collision rejection and correct provider/host selection.
- **Stop and cost:** demonstrate operator stop, pause/resume if supported by the existing lifecycle, exhausted budget, no eligible frontier, repeating-failure ceiling, process interruption, loss of transport and explicit cancellation. No orphan worker processes, unbounded restart loops or spent-call resets.
- **Deployment and evidence:** all relevant tests pass; a genuinely independent qualified verifier accepts the implementation; live deployment is explicitly confirmed (service version, activation state, health, worker route, actual task outcome), with rollback and honest limitations documented at `result_path`. A PR, doc-only instruction, locally installed skill, or simulated queue does **not** satisfy deployment.

## Stop rule

The backend run ends or pauses only for a recorded terminal state: authorised work exhausted, explicit operator stop, verified budget limit, genuine protected approval, or no currently qualified route with a bounded event-based recheck. Persist pending work and review debt; never label an incomplete task shipped. A finished activation does **not** automatically start another billable activation.

This task is shipped only after the real, lab-hosted, client-independent, restart-resilient backend loop is demonstrated and deployed. If existing Odysseus service architecture cannot perform it without a major redesign, record that precise technical blocker and preserve the current bounded manual /lazyUsage route rather than adding another harness.

---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-28-persistent-blocked-route-rerouting-long-horizon
title: "Persist blocked-route state and reroute long-horizon work"
status: inbox
priority: high
task_type: orchestration
created_by: chatgpt
created_at: 2026-09-28T13:41:00+01:00
executor: codex_subscription
execution_mode: implementation
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: codex/persistent-blocked-route-rerouting-20260928
allowed_paths:
  - src/**
  - routes/**
  - core/**
  - config/**
  - companion/**
  - scripts/**
  - tests/**
  - docs/**
  - automation/review/**
denied_paths:
  - "**/*.pdf"
  - "**/.env"
  - "**/secrets/**"
inputs:
  - docs/aoteru-model-host-routing-contract.md
  - automation/review/agent-tasks/inbox/2026-09-19-capability-routed-parallel-project-orchestration.agent-task.md
  - src/estate_router.py
  - config/routing.yaml
  - config/models.yaml
outputs:
  - Existing Odysseus-owned routing/task state and recovery implementation
  - Focused persistent-state and rerouting tests
  - docs/persistent-blocked-route-rerouting.md
result_path: docs/persistent-blocked-route-rerouting.md
review_report_path: automation/review/persistent-blocked-route-rerouting-verification.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
architecture: single-plus-verifier
architecture_rationale: "One owner extends shared Odysseus state/routing and recovery; independent verifier checks failure classification, authority, resumability and non-regression. Scientific acceptance stays with the existing domain contract."
single_agent_baseline: "Present routing can report failed/blocked decisions, but long-horizon coordinators still tend to reattempt a known blocked route, suspend a whole loop when one required model is quota-limited, or lose block status across session boundaries. Verify this against live code before implementing."
execution_host: laptop
context_budget: "Inspect current runtime/state/schema and the existing orchestration task first. Use bounded failure fixtures; do not load the PhD research corpus into generic runtime context."
coordination_reason: "Cross-session retry semantics and automatic routing affect shared execution and authority; verify independently before enabling automatic recovery."
notes: "Odysseus alone owns shared route/task/lease authority. J1 is a regression fixture, not a reason to create a PhD-vault router or copy scientific decisions into backend state. Do not assume the separate parallel-orchestration task has already shipped."
---

# Persist blocked-route state and reroute long-horizon work

## Problem

Long-horizon work currently risks conflating *one blocked execution or evidence-acquisition route* with *the entire programme being blocked*. In the 2026-09-28 J1 loop, Sol quota temporarily prevented consequential acceptance, while bounded W7/W8 evidence work could still proceed. Separately, a publisher 403, institutionally inaccessible paper, extraction-limited scanned PDF, provider outage and an unavailable primary are different failure classes: repeating an unchanged route wastes time/context, but forbidding all alternative eligible routes or all independent tasks also wastes capacity.

Implement durable, explainable, **smallest-affected-scope rerouting** within existing Odysseus authority. Carry failure knowledge across coordinator restarts and session boundaries without treating an old block as permanent truth.

## Required behaviour

1. **Inspect before building.** Establish the live routing/task/workflow state, existing persistence and restart behaviour, lease/claim authority, capability registry and related 2026-09-19 orchestration task. Extend the established owner surfaces; do not create a second router, queue, ledger, scheduler or repo-local runtime. Separate observed current capability from target-contract prose.
2. **Persist an attributable blocked-route event** keyed by stable work unit/dependency plus a canonical route fingerprint (provider/model alias and resolved model or deterministic tool; host; endpoint/resource/source identity; access context; requested capability and verification floor). Store failure class, diagnostic summary, evidence pointer, first/last attempt, retry count, freshness, next eligible probe/retry condition and last decision. Avoid storing credentials, personal session data, whole prompts or source PDFs.
3. **Classify precisely:** transient service failure (e.g. 503); rate/quota limit with known/unknown reset; host/model unavailability; source HTTP 403/bot wall/paywall/institutional-entitlement failure; extraction limitation (e.g. image-only PDF); permission/lease/ownership conflict; capability or independent-verifier deficit; scientific evidence/authorial decision dependency; non-retryable policy/safety failure. Distinguish source access from model capacity and an unavailable verifier from unavailable producer.
4. **Before each dispatch/resume**, consult fresh persisted blockers. Do not retry an unchanged fingerprint during an active block. Choose, in order, a permitted materially different acquisition/execution route with the same evidence and capability requirements; a different eligible route for the same bounded unit; or another dependency-ready independent unit. Park only affected units and their actual descendants. If all executable work is exhausted, return a concise blocked frontier and named unblock conditions instead of looping or claiming completion.
5. **Trigger-aware recovery:** use an explicit reset time or bounded backoff/cooldown for transient errors; re-probe when a changed access entitlement, operator-supplied primary, qualified model/host, capacity refresh, new provider route or verified change of underlying artifact makes the old block potentially stale. Expire/reevaluate stale status conservatively. No busy retries, repeated identical 403 attempts, arbitrary fallback to a weaker model, speculative mirrors, bypass of SSO/paywalls or invented source text.
6. **Resumability and consistency:** atomic/idempotent event updates and checkpoint/restart; distinguish per-attempt state from per-work-unit status; deduplicate repeated failure reports; preserve dependency DAG, existing claim/lease ownership and provenance; reconcile in-flight claims after interruption by existing recovery policy. Rerouting never confers write, scientific acceptance, gate or model-qualification authority.
7. **Explainable frontier:** expose an operator-readable status/dry run: which route was blocked and why; when/how it can be retried; which eligible alternative was selected or why none qualifies; which independent units remain executable; what is awaiting Sol/Opus or author input. Instrument prevented retries, route changes, blocked duration, useful work continued and false-positive unblock attempts using current telemetry rather than inventing another benchmark system.
8. **Integrate progressively:** keep compatibility with the current single-unit route API. If parallel-DAG execution is not implemented yet, deliver durable failure memory and a smallest-scope next-unit recommendation via existing interfaces, with a clear integration seam for the 2026-09-19 orchestration task. No fake multi-host/model dispatch claims.

## Tests / acceptance criteria

- A worker hits an identical publisher 403 twice across two sessions: the second unchanged attempt is suppressed, the original source requirement stays open, and a genuinely distinct permitted route or independent work is available.
- Sol quota exhaustion with a known reset parks consequential adjudication only; admissible bounded GLM/deterministic and independent packages proceed, while no weaker lane silently performs Sol acceptance. The task becomes eligible again on capacity-refresh evidence.
- A 503/429 receives bounded retry/backoff and survives process restart; a host crash does not duplicate a write or leak a live lease.
- A scanned PDF with no text layer becomes extraction-limited, not mistakenly access-denied or full-text-read. A verified permitted visual/text extraction route can re-open it without fabricating quotations.
- Operator supplies a legitimately obtained missing primary: the specific source dependency reopens; unrelated previously closed/blocked units do not restart.
- Multiple dependencies: only descendants of a blocked node wait, while independent nodes continue; if every frontier node is blocked, return explicit unblock conditions rather than terminate as scientifically complete.
- Route candidates below capability/quality/verification floors and authority-ineligible hosts are never selected, even when cheaper or available.
- Replayed decisions and tests cover persistence, duplicate suppression, expiry/revalidation, alternative-route equivalence, independent-work selection, no-unbounded-retry and status reporting. Check the existing test suite and document observed vs. unimplemented coverage.

## Handoff

Produce a bounded implementation plus test/evidence report with before/after route trace, schema/compatibility notes and remaining constraints. The user-facing J1 example is a fixture only: domain-specific source admission, Opus/Sol scientific acceptance and gates remain in the PhD knowledgebase/contract, not Odysseus. Require independent review before promoting automatic routing behaviour.

## Programme disposition (2026-10-03, convergence Phase 9 reconciliation)

**State: open; not implemented as a mechanism, followed as a process rule**

Re-grounded against `dev` on 2026-10-03: no persistent blocked-route state exists in code. The behaviour it asks for (one blocked route is not a blocked programme; reroute or continue independent work) was applied by this
programme by hand throughout (for example holding the lab deployment and kiosk acceptance while Phase 4, the backup chain, GPU admission and the Seed Order work proceeded, and recording a denied action instead of retrying it).
A mechanism that persists that state remains a real, unimplemented item. It is not named in the convergence programme's closeout bullets, none of which depends on it, so it does not block closeout. No work in this programme is attributed to it. It stays where it is, with the Odysseus queue as owner.

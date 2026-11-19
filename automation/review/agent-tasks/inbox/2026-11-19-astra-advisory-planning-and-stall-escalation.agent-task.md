---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-19-astra-advisory-planning-and-stall-escalation
title: "Add bounded Astra advisory consultation for difficult initial plans and stalled agent work"
status: inbox
priority: medium
task_type: implementation
created_by: chatgpt
created_at: 2026-11-19T16:11:00+00:00
updated_at: 2026-11-19T16:11:00+00:00
executor: claude_subscription
execution_mode: staged-loop
architecture: single-plus-verifier
architecture_rationale: "Extend Odysseus's existing central routing, lazyUsage coordinator, failure counters, advisory dispatch and provenance. Astra is a read-only consultant; one task owner retains implementation and verification."
single_agent_baseline: "One cheap qualified implementer and deterministic verifier, with no premium consultation unless the evidence-based trigger and existing operator/model gates both pass."
execution_host: compute-box
context_budget: medium
coordination_reason: "Shared model/provider routing, initial planning and execution recovery apply across all three repository queues; Odysseus is the only orchestration authority."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - automation/review/**
  - docs/**
  - config/**
  - routes/**
  - src/**
  - scripts/**
  - tests/**
  - evals/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
inputs:
  - live tyecam1/odysseus@dev AGENTS.md and current deployed runtime/worker eligibility
  - docs/aoteru-model-host-routing-contract.md
  - docs/subscription-model-currency-policy.md
  - docs/initialising-prompt-register.md
  - config/initialising-prompts.yaml
  - src/lazy_usage_runtime.py and src/lazy_usage_coordinator.py
  - src/estate_router.py and src/subscription_model_policy.py
  - existing review-model economy preference and 2026-11-09 Opus blocker rule
  - public studies and GitHub examples cited below
outputs:
  - reviewed trigger policy with failure taxonomy and evidence-backed initial-plan eligibility
  - tested, opt-in Astra read-only advisory route in the existing controller
  - idempotent consultation packet, advice provenance and measured pilot
  - reconciled routing/review/Opus and prompt-register contracts
result_path: ""
review_report_path: ""
handoff_model: ""
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Intake only, subject to shipping-first admission. No Astra invocation is authorised by the existence of this card. Preserve AOTERU_ALLOW_ASTRA=1 and per-review exception gates."
---

# Astra advisory for initial planning and stalled execution

## Objective

Use the current authenticated Astra model (GPT-6.2 Astra at intake) sparingly as a **read-only advisor** for problems where a stronger diagnosis or plan can avoid expensive failed iterations. Apply to Odysseus, Misumi and PhD execution without moving domain authority. Keep ordinary implementation, cheap independent reviews and deterministic acceptance with their existing owners.

## First inspect and reconcile

1. Work from live branch/HEAD, deployed runtime and queue frontier. Run `aoteru preflight`; deduplicate against existing advisory, Sol packet, Opus blocker and lazyUsage coordinator work. This is an implementation dependency, not permission to start an unrelated orchestration redesign.
2. Inspect `src/lazy_usage_runtime.py` (notably `max_repeat_failures: 3`, budgets and checkpoint logic), its coordinator, `estate_router`, paid advisory dispatch, `subscription_model_policy`, routing-decision telemetry and real Codex CLI eligibility. Existing counter ceilings are **stop guards**, not automatically the right advice trigger.
3. Explicitly reconcile the 2026-11-10 cheap-review pool (Haiku 5.5 / Terra 6.1 / GLM-Flash), the 2026-11-09 Opus preference for consequential blockers, and the 2026-10-22 Astra exclusion. Do not relabel a premium review as “advice” to evade the per-review operator exception. This request expresses preference for an Astra *advisor*, not standing permission to consume arbitrary paid review quota. Preserve `AOTERU_ALLOW_ASTRA=1` as a required operator-controlled runtime gate. No hardcoded historic model pin or implicit premium fallback.
4. Establish baseline cost, failure, delivery and consultation rates from existing traces where measurable. Label unavailable metrics as unknown.

## Candidate policy to test, not blindly hardcode

Use a **typed event and marginal-value gate**, not a universal count of three:

| Situation | Proposed response |
| --- | --- |
| Routine or well-specified plan, low consequence | Deterministic decomposition / cheapest qualified coordinator; no Astra. |
| **Initial plan** with high consequence, hard-to-reverse architecture, cross-repository interaction, novel scientific method, or materially conflicting constraints **and** unresolved choice after one bounded cheap scoping pass | One Astra planning consultation *before implementation*, if qualified, allowed and expected to reduce risk/rework. Complexity adjectives alone do not qualify. |
| Same **semantic** test/verification failure persists across two distinct remediation attempts with no new informative result | Diagnose cheaply once; Astra consult may trigger before a third identical attempt. |
| Three distinct, bounded **repair hypotheses** fail to improve the relevant acceptance gate or expose new evidence | Replan/consult rather than allow unproductive serial retries, subject to existing hard ceilings. |
| Important contradictory evidence, unknown architecture invariant, material scientific-validity conflict, or inability to identify an adequate failure hypothesis | Early bounded consultation regardless of count. Physical safety, credentials, ethics and approval limits remain protected and cannot be resolved by model assertion. |
| Transient network, quota/rate limit, missing tool/host, known environment/config error, or ambiguous remote write outcome | Use typed retry/backoff, alternative *qualified* route, observation/reconciliation or stop. Do **not** purchase Astra to “solve” unavailable infrastructure or assume a timed-out write did not happen. |
| Genuine measurable progress, including changed failure signature, newly isolated cause, reduced failing tests or new discriminating evidence | Continue the cheap lane within its budget; a verification iteration is not a failure. |

Operational definitions: an **attempt** is one distinct causal hypothesis + bounded intervention + observed verifier outcome; repeat calls with an unchanged action and unchanged evidence do not count as distinct progress. **Stall** means no material improvement in the named acceptance condition and no new discriminating evidence. Compare exact subject/repository, HEAD or evidence digest, failure class and affected acceptance gate. Never use LLM self-confidence as a sole trigger.

Treat two repeated same-signature failures and three no-progress hypotheses as **initial calibration candidates**, not scientific constants. Choose thresholds using replay against actual estate traces and a bounded prospective experiment. Estimate marginal expected value from success probability, consequence, incremental cost/quota, latency and remaining budget. Maintain absolute caps independently of advice.

## Advisory transaction

- One existing-controller dispatch via an explicitly qualified read-only `reasoning-strong`/advisory lane, with runtime-verified exact Astra identity, live quota and operator opt-in. Start at **medium reasoning effort**; use high only when the bounded problem merits it and quota permits. No direct worker or repo-local model router.
- Before the paid call, persist an idempotent consultation fence keyed to subject + evidence digest + consultation purpose; resume must not rebill the same unchanged state. Reuse the existing `routing_decisions` and/or coordinator checkpoint provenance; do not create a second queue, planner or standalone audit service.
- Transmit a minimal packet: task objective; repo/HEAD and allowed authority; contested decision or precise failure; acceptance criteria; relevant diff/test output/source pointers; attempted hypotheses and outcomes; remaining budget; explicit question. Redact secrets, raw private domain data and unneeded transcripts.
- Ask Astra for: **root-cause hypotheses ranked by discriminating evidence; falsifiable tests; smallest viable change or revised plan; rejected alternatives; residual uncertainty; when to stop**. Do not ask it to reimplement the whole task.
- Return bounded, structured **advice** to the original executor/owner. The owner chooses a single testable next action. Astra cannot mutate files, approve research claims, override leases, pronounce independent verification complete, authorize a merge or relax any policy. Code and claims still undergo their usual deterministic and independent checks.
- Consult at most once per unchanged subject/evidence/purpose; a genuinely new causal finding may justify another call within explicit per-task premium and overall budgets. On unavailable/unauthorised Astra, record the debt and proceed with safe independent work, existing qualified alternative or precise blocker. No hidden fallback.

## Implementation and verification slices

1. **Design + trace replay:** Document candidate policy and conflicts with existing review/Opus/Astra rules. Classify example runs into progressing, stagnating, transient, nonrecoverable and protected-gate cases. Record false-positive and false-negative escalation decisions.
2. **Thin opt-in integration:** Extend existing coordinator/router, counters, advisory packet and usage/provenance surfaces only where needed. Keep one owner per task, immutable accepted evidence and restart-safe idempotency. Ensure a premium advice call cannot bypass the repeat-failure hard stop or usage ceilings.
3. **Tests:** Cover initial-plan selection and rejection, two same-signature failures, three distinct no-progress hypotheses, progressing repairs, unknown test results, rate limits, quota exhaustion, absent Astra opt-in, stale model catalogue, permission gate, re-entrant run/restart, unchanged evidence replay, changed evidence, independent-review budget exception, and unauthorized review/merge/write attempts.
4. **Measured pilot:** On a bounded sample of genuine historical or live hard tasks, compare the incumbent cheap-first path with selective Astra consultation using verified completion/acceptance, cost or subscription calls, latency, repeated failures, human interventions, and unnecessary consultations. Include at least one **initial-plan** and one **stalled-debugging** case. Do not declare improvement from model preference or anecdote.
5. **Rollout:** Keep behind a default-off feature switch until actual CLI/model availability, operator opt-in and acceptance are verified. Update the single routing contract and current task status. Use existing prompt application/evolution traces; register a reusable advisor packet or initialiser **only after** evidence shows general reusable value, not as a duplicate prompt register. Deploy and verify the real worker path before claiming it active.

## Acceptance

- [ ] One unambiguous trigger decision per event with recorded inputs, candidate alternatives and reason; no counting productive verification as repeated failure.
- [ ] Astra is consulted for sufficiently difficult initial planning *and* genuinely stalled work, but never for routine work, infrastructure/transient issues or the mere third test invocation.
- [ ] Existing Astra opt-in, paid-review operator exceptions, newest-model attestation, Opus guidance, authority boundaries, quota caps and unchanged-evidence idempotency remain intact.
- [ ] Consultation is read-only and advisory, with one executor retaining implementation and independent acceptance checks; protected domain, PhD evidence, safety and merge gates remain unchanged.
- [ ] Deterministic tests, restart/replay tests, cost/benefit pilot and actual opt-in end-to-end advisory execution (or an honestly documented external/provider gate) are evidenced.
- [ ] No second router, task queue, retry supervisor, prompt registry or unnecessary daemon is introduced.

## Evidence and implementation references

- Odysseus current authority: `AGENTS.md`, `docs/aoteru-model-host-routing-contract.md`, `docs/subscription-model-currency-policy.md` and `src/lazy_usage_runtime.py` on live `dev`.
- OpenAI GPT-6.2 release and cost-per-task claims: https://openai.com/index/introducing-gpt-6-2-astra-sol/
- GPT-6.2 API prompting/integration: https://developers.openai.com/api/docs/guides/latest-model
- Confidence-aware test-time scaling: https://arxiv.org/abs/2602.12276
- Limits of sequential/parallel agent scaling: https://arxiv.org/abs/2602.18998
- Microsoft bounded autonomy, budgets and consecutive verifier failures: https://github.com/microsoft/agenticai-design-patterns/blob/main/assets/orchestration-and-workflows/bounded-autonomy/docs/architecture.md
- Example failure taxonomy and budgeted recovery: https://github.com/mattekudacy/triage
- Example event-driven repair/replan/stop decisions: https://github.com/usedotai/dot-reflex

## Completion boundary

This card is an **inbox intake**, not deployed policy. Defer speculative optimisation behind the existing shipping-first backlog unless current measured failure loops warrant earlier admission. Finish only on a benchmarked, gated, deployed and traceable advisory route; a design document, merged code or an unverified provider alias alone is insufficient.

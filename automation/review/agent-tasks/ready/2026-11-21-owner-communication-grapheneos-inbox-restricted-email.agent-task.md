---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-21-owner-communication-grapheneos-inbox-restricted-email
title: "Replace one-way Discord alerts with a private GrapheneOS text inbox and strictly recipient-locked email"
status: ready
priority: high
task_type: owner-intervention-communication
created_by: operator-directed-chatgpt
created_at: 2026-11-21
updated_at: 2026-11-21
executor: codex
execution_mode: staged-implementation-opt-in-mobile-canary
execution_host: lab
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: high
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: dev
related_tasks:
  - 2026-11-21-lazyusage-parallel-window-aware-dispatch
  - 2026-11-21-cross-repository-development-observer
  - 2026-11-09-autonomous-blocker-reconciliation-and-opus-escalation
  - 2026-11-09-lazyusage-bounded-persistent-continuation
inputs:
  - AGENTS.md
  - START-AGENTIC.md
  - src/owner_decisions.py
  - src/lazy_usage_runtime.py
  - routes/lazy_usage_routes.py
  - routes/estate_routing_routes.py
  - core/database.py
  - config/estate.yaml
  - config/routing.yaml
  - docs/runtime-work-packages/2026-11-19-lazyusage-reliability-acceptance.md
  - automation/review/agent-tasks/ready/2026-11-21-lazyusage-parallel-window-aware-dispatch.agent-task.md
  - https://github.com/tyecam1/odysseus/pull/302
allowed_paths:
  - src/**
  - core/**
  - routes/**
  - scripts/**
  - tests/**
  - config/**
  - docs/runtime-work-packages/**
  - automation/review/**
  - web/**
  - frontend/**
  - static/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
result_path: docs/runtime-work-packages/2026-11-21-owner-intervention-mobile-inbox-acceptance.md
---

# Owner intervention: private, text-only, low-friction communication

## Objective and existing implementation

The operator wants /lazyUsage to ask the **few genuinely necessary** questions, decisions and scope-bound approvals on their GrapheneOS phone, and to take replies **only as natural-language text**. The preferred first channel is a **minimal self-hosted private chat/inbox**, with optional email **sent exclusively from `agentictye@gmail.com` directly to the operator's single verified University of Strathclyde email address**. The channel should be chosen by information density and **observed explicit operator preference**, with manual override and no unwarranted inference. The agent should proceed with independent authorised work if no answer arrives.

**Reuse, do not rebuild:** PR #302 is merged. `src/owner_decisions.py` generates concise owner-debt cards, deduplicates, throttles and optionally sends them through an outbound-only private Discord webhook. `GET /api/lazy-usage/decisions` is read-only, and the lifecycle tick invokes the notifier. Existing owner gates, task cards, queue authority, authentication, WIP/concurrency contract and audit evidence remain canonical. **The Discord webhook does not receive replies and must not become an approval authority.** Extend the current decision-card path, not a second dispatcher, queue, approval engine, chat agent or scheduler.

**Priority:** unblock already-started accepted work before new optional UX development. This is an owner-attention reduction and completion-gate capability; preserve the existing two-active-work-item operator cap, owner acceptance, verification, independence and protected approvals. Do not autonomously expand WIP merely because the user has been notified.

## Phase 0: choose the minimum viable channel from actual evidence

1. Inspect live `dev`/service state, PR #302, existing lab/tailnet HTTPS/auth surfaces, current phone/browser/network assumptions (GrapheneOS, Pixel 8), available notification components and existing authorised sender integration. Identify the smallest **secure bidirectional text** path within the deployed backend.
2. Prefer a minimal **tailnet-only mobile-first web app/PWA**, installed to the GrapheneOS home screen and backed by existing Odysseus authenticated API. For reliable background notifications, test a **self-hosted ntfy F-Droid Android app** as the notification-only bridge, reusing an existing instance if present. Its push message should reveal no sensitive task content, credentials, URLs with bearer tokens or approval instructions; opening it takes the user to an authenticated in-app thread. Do **not** mistake ntfy's notification service for a two-way approval/chat system. Check full delivery on the real GrapheneOS device with screen off, Wi-Fi/mobile data, Tailscale reconnection, background restrictions and with/without sandboxed Play Services. If this split requires unacceptable phone overhead or cannot notify reliably, compare one genuinely simpler already-supported self-hostable messaging client with reliable text replies; reject an unnecessary full Matrix/XMPP stack unless an end-to-end test proves less overall operational cost.
3. Cite live platform guidance and real deployment/permission evidence. Relevant references: https://grapheneos.org/faq ; https://docs.ntfy.sh/subscribe/phone/ ; https://docs.ntfy.sh/config/ ; https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Offline_and_background_operation . A web push API alone is **not** proof that background notification works in this GrapheneOS setup.
4. Decide from measured component count, maintenance, notification latency/reliability, battery/network behaviour, privacy and typing experience. Default preference is mobile conversation for terse/urgent action requests; email only for high-density content when configured, or when the operator explicitly chooses it. Do not invent past response preferences, contacts, reachable hosts or enabled provider credentials.

## Phase 1: bidirectional, text-only owner inbox

1. Reuse `owner_decisions.build_cards`, its deduplicated card keys, existing task/revision/scope/owner identities and existing `owed_reviews`/authority. Add an opt-in, minimal responsive **one-to-one text conversation** view: pending threads first, recent answered threads, task title, a bounded reason, current scope/digest, evidence references, precise effect of approving/rejecting/defering and a single **plain text reply field**. No buttons for the decision itself, no forms, no Discord bot conversation, no media/voice input, no agent-generated free-standing demands. The inbox is a delivery/UI projection, **not** a competing source of task state.
2. An agent asks a question only after deterministically establishing that it is **actually owner-only**, bounded and actionable (not a mechanically resolvable blocker, routine review, failed test or speculative preference). Notifications may cover a scope-bound approval, genuine owner decision, final acceptance/rejection, or a compact necessary clarification. Ask once per evidence revision, include why it matters, expected consequence and what happens on no reply. Reuse PR #302's batching/deduplication/cooldown; support documented high-urgency exceptions without notification storms.
3. For each text response, bind to **authenticated owner + stable conversation/card ID + current task revision + exact requested action/scope digest**. Interpret natural language into a **proposal**, then apply a deterministic policy validator. Ambiguous 'yes', conflicting/multiple instructions, changed scopes, expired requests, stale evidence or low-confidence intent must trigger one text-only clarification, **never automatic approval**. For consequential/irreversible gates, show the exact proposed effect and require explicit fresh text confirmation; no implicit 'yes' from a generic chat turn. All changes go through the existing owner-authorised gate handlers; a model may not mint its own approval or mark unverified work accepted.
4. Persist minimal thread metadata, explicit user text and action/evidence provenance with existing retention/access rules. Enforce owner isolation, authenticated per-device sessions, HTTPS over the current private tailnet, short-lived CSRF-safe scoped sessions and explicit logout/revocation. Push payloads include only a generic 'decision needed' + opaque identifier, not question bodies, internal repository text, secrets, Strathclyde email, tokens or privileged links. Untrusted task bodies/reviewer prose cannot dictate message destinations, approval semantics, credentials or policy.
5. Synchronise answered/deferred/changed-card state with real live backend debt, rather than simply marking a notification as read. An unanswered question leaves the task blocked or legitimately parked without pretending it is shipped; independent work continues **within** the operator WIP cap. Allow a user to reply from another device without duplicate action. The inbox must recover after offline intervals/restarts and show any changed scope as a **new** request.

## Phase 2: tightly constrained email option (fail closed)

1. **Absolute sender and recipient rule:** outbound messages may originate **only from the operator-authorised authenticated `agentictye@gmail.com` account** and go **only to one precisely verified, owner-attested University of Strathclyde email address**, stored in private deployment configuration, not a public work item. The exact Strathclyde address has **not** been established in this instruction. Empty/unattested allowlist means **email disabled**. Never guess the address or accept a domain-wide rule (e.g. any `@strath.ac.uk`). No sends to any other address under any condition. The sender account's own replies, aliases, forwards and mailing lists do not widen the outbound recipient allowlist.
2. Build a **single-purpose email adapter** that pins sender identity and **one** recipient at the **last possible send boundary**. Both the SMTP/Gmail API envelope and **every** MIME header capable of defining recipients must be checked against the exact allowlist; `To` is one literal verified address, `Cc` and `Bcc` are absent/empty, no group recipients, `Resent-*`, forwarding, auto-replies, reply-all, dynamic CC, user-supplied envelope, redirects, or plugin/tool access to a general mail send function. Reject email address/header injection, misleading display names, IDN/Unicode confusables, extra comma- or semicolon-separated recipients, arbitrary `Reply-To` and task-text-derived destinations. Verify authenticated account identity equals `agentictye@gmail.com`; fail closed otherwise. Do not provision account access or OAuth scopes without operator action, and do not expose tokens/passwords in code, logs or PRs.
3. Outbound email is optional and **disabled by default** until configured and dry-run tested. Use only a properly authorised mail route (existing provider integration if actually deployable) with least-privilege credentials. Test with a fake transport first; no real message before an explicit operator-controlled live canary to the exact attested address. No alternate recipient fallback if delivery fails; retain question in the authenticated inbox and report failure. Discord must not receive a duplicate if email is chosen.
4. To support actual **text replies** by email if an authorised receive route exists, accept only reply messages fetched from the authenticated account's mailbox, verify the purported sender against the same owner-attested Strathclyde identity and bind a fresh unguessable thread nonce plus task/scope revision. Mail headers/From alone are not a sufficiently strong proof of a protected approval: require a fresh in-app confirmation for consequential actions, or restrict email replies to clarifications/defer/reject and direct approvals to the authenticated mobile inbox. If no safe inbound integration exists, email is **notification/read-only** with an authenticated inbox path for the natural-language reply, explicitly stated to the operator. Never allow an inbound email's content to alter recipient policy or task authority.
5. Do not leak external mail to any other destination through autoresponder, logging/analytics, bounce handling, replies, external summaries or plugin dispatch. A malformed, missing, stale, compromised or multi-recipient config causes zero sends. Never log the recipient address unnecessarily; report safe channel-status metadata instead.

## Phase 3: medium selection and preference learning

1. Implement a **small transparent policy**, not another model-powered orchestrator. Initially choose mobile notifications for concise, time-sensitive questions and direct approvals; for high-density explanations or evidence briefs choose the allowlisted email channel **only if live-authorised**, with a short mobile summary when that is explicitly enabled (no redundant demands and no duplicate approval identity). Keep long evidence in the authenticated inbox and link to it instead of pasting private data into push channels.
2. Learn *only from explicit operator settings/corrections and small, privacy-respecting response signals*: preferred channel per request type, verbosity, notification hours and rate, dismiss/deferral preference. Record a reason for every routing choice; allow per-thread text preference such as 'send detailed requests by email' to override the heuristic. Do not mine unrelated personal conversations, infer silent consent, silently rewire sensitive messages or allow an agent to change the allowlisted email.
3. Maintain a bounded, deduplicated question queue within the existing decision/debt system: prefer agent-finishable work over asking a question; at most the few necessary cards already exposed; notify only on real state/evidence changes or a documented reminder. Show time-to-owner-response, reasks/false human blocks, questions per shipped task, message failure, notification latency, channel choice accuracy and operator effort. Optimise **tasks unblocked per necessary interruption**, not volume of messages.

## Security and test acceptance

- **Critical recipient invariant:** inject malicious task titles/body, model prompt instructions, MIME headers, `to` overrides, cc/bcc, redirect responses, weird Unicode addresses, `mailto` aliases, reply-all, rate-limit/retry and forced failover. Assert **zero outbound sends to any address other than the single attested Strathclyde address**, and zero sends when missing/mismatched. Verify actual transport envelope and MIME headers, not just application data structures. Send identity must be attested as `agentictye@gmail.com`.
- **Authorization and semantics:** unauthenticated, expired, CSRF, stolen/replayed token, other-account, stale card/scope, cross-repo owner confusion, duplicate email replies, ambiguous 'yes', manipulated task body and invalid gate all cannot approve, accept, escalate or alter credentials. Exact scope bound to action; owner confirmation and immutable evidence, independent verification and protected approvals remain intact.
- **Delivery and reliability:** test a physical GrapheneOS background notification and natural-language reply end-to-end, offline/reconnect, no Google Play dependency if chosen, notification delay/battery, self-hosting authentication, Tailscale failure, no external open port, one notification/one reply/one authoritative outcome, no Discord duplicate, service restart and message deduplication. Never claim the phone channel works from mocked tests alone.
- **Workflow:** a real pending owner gate appears, one short text answer is interpreted and safely applied to the current exact task, /lazyUsage resumes without manual copy/paste, and agent-fixable work does not generate demands. Acceptance still requires existing tests, independent qualified review and the owner task's required evidence. Verify with the operator's approval before enabling live outbound email, connecting accounts or installing software on their phone. Shadow mode first. Provide a simple opt-out and rollback to existing read-only `/decisions`, with Discord notification switch explicitly disabled or owner-controlled to prevent duplicate external sends.
- **Operator WIP limit:** notifying does not open a new task slot or free unfinished work. Preserve pending real owner debt through any run/notification/transport transition. External protected waits may park per the separate parallel WIP contract, never be marked done.

## Delivery and stopping

Return source-linked evidence at `result_path`: minimal design decision and alternatives; exact backend/API reuse; mobile install/notification tests; safe sender/recipient configuration procedure without actual addresses/secrets in Git; test matrix and independent review; opt-in deployment/canary result; rollback; only the genuinely necessary human action(s). Deliver the **authenticated mobile text loop first**, then the optional locked email adapter and preference routing only if they preserve simplicity. If the owner has not provided the exact recipient or approved sender OAuth, **leave email disabled**, ship the secure mobile flow and list the small precise setup dependency. Do not claim live deployment or email capability from source code alone.

## Plan (written 2026-11-26 by the controller; step 0 is to verify it against HEAD)
**Goal in one line.** Close out the delivered phone inbox against this card and add the remaining piece: a disabled-by-default email adapter locked to one recipient.
**Already done / do not redo:** the 2026-11-26 phone inbox (src/owner_inbox.py, src/owner_inbox_runtime.py, src/owner_alerts.py: ntfy alerts and plain-words replies); gate lifting through the owner ledger (src/owner_ledger.py); the Discord webhook in src/owner_decisions.py, kept as-is by owner decision; the advisor-approval worker, built but disabled.
**Steps:**
0. Grep HEAD for the inbox, alert, ledger and `build_cards` symbols and for the 2026-11-26 deployment evidence. Correct this plan and the already-done list.
1. Read-only gap audit: map each Phase 1 and acceptance bullet to an existing test, recorded evidence or a gap. Bullets include binding to owner + card + revision + scope digest, clarification on an ambiguous yes, fresh confirmation on consequential gates, a generic push payload, a single outcome across devices, recovery after restart and ntfy/Discord duplicates. Proof: gap table.
2. Close real gaps only, with deterministic tests (locate the inbox tests with grep). Add no new channel or approval path.
3. Email adapter (new src/ module, standard library only, injected transport): sender pinned to the address named in the card; one recipient read from private deployment config; missing, malformed or unattested config means zero sends; the envelope and every MIME header that can carry a recipient are checked at the send boundary. Tests (fake transport): the card's injection matrix yields zero sends to any other address.
4. Email is notification-only; replies stay in the authenticated inbox. Test: no code path feeds mail into gate handlers.
5. Channel choice: a deterministic function that records its reason (terse -> inbox; long brief -> email only when live-enabled). Only explicit operator settings override it. Tests per branch.
6. Write docs/runtime-work-packages/2026-11-21-owner-intervention-mobile-inbox-acceptance.md (inbox evidence, new tests, model used, rollback, owner debts). Run the full suite and stop.
**Done when:**
- Every card acceptance bullet maps to a passing test, evidence or a named owner debt.
- Without attested config the adapter sends nothing, and the fake-transport matrix passes.
- src/owner_decisions.py is unchanged. Any ntfy/Discord overlap is de-duplicated or listed for the owner to decide on the Discord switch.
- No claim that the phone channel works rests on mocked tests.
**Risks and stops:**
- These are `protected_handoff` owner debts; never guess or provision them: the Strathclyde address, sender authorisation, the live email canary and any missing physical GrapheneOS evidence.
- Do not enable the advisor-approval worker or change gate semantics.
- This is security-sensitive: a GLM review only corroborates. Record the review lane and model.
**Ordering note:** Parking uses the parallel-dispatch WIP contract if it is present. Acceptance lets the owner decide whether Discord decision cards are retired, which the agent-lobby card is waiting on.

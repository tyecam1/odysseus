---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-26-daily-phd-checklist
title: "Daily PhD checklist on the phone: today's required accomplishments from the PhD repo plans, ticked off by reply"
status: ready
priority: high
task_type: implementation
created_by: operator-directed-claude-code
created_at: 2026-11-26T15:30:00+00:00
executor: claude_subscription
execution_mode: standard
architecture: single-plus-verifier
architecture_rationale: "One implementing worker with deterministic tests, then independent cross-family review."
single_agent_baseline: "One qualified worker implements and tests against the live inbox code and a read-only checkout of the PhD vault."
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
  - src/owner_inbox.py
  - src/owner_inbox_runtime.py
  - src/owner_ledger.py
result_path: docs/runtime-work-packages/2026-11-26-daily-phd-checklist.md
---

## Plan (written 2026-11-26 by the controller; step 0 is to verify it against HEAD)
**Goal in one line.** Every morning, post at most five concrete accomplishments from the PhD repository's own plans to the owner's phone topic `phd-daily-checklist`, and let the owner tick them off by replying in plain words in that same topic.
**Already done / do not redo:** The topic exists on the lab ntfy server with read-write for the `owner` and `odysseus` accounts, and the controller posted the first list by hand on 2026-11-26 (title "PhD today, Thu 26 Nov"). The format is a numbered `[ ] n text` line per item (at most 120 characters each) followed by one source line. The topic confers no authority: nothing posted or ticked there approves, declines or changes any card. The PhD repository is on the lab at `/home/agent/projects/phd/obsidian-PhD` (read it; never write to it). The approval inbox (`src/owner_inbox*.py`) is separate; reuse its transport (`send`, a per-topic channel built with `dict(channel, url=base/topic)`) and its text gates, and leave its behaviour unchanged.
**Steps:**
0. Grep HEAD for `owner_inbox.send`, `fetch_replies`, the runtime tick (`run_cycle`) and `owner_ledger`; read the vault's `10-inbox/*.md` work-item frontmatter (`artifact_type: work-item`, `status`, `activation`, `due`) and `**Next:**` or checkbox lines. Correct this plan.
1. Source selector (deterministic, no model): open work items (status active, open or waiting), ranked by activation then due date, each with its own next action from the file. An item whose due date is more than 30 days past is shown once with the overdue age and the words "still live?"; a stale item is never presented as fresh. Unticked items carry over; ticked, dropped or "later" items do not repeat. Tests: ranking, the five-item cap, carry-over, stale wording.
2. Daily post: one message at 08:45 London (not in the quiet window 21:00-08:30), only when the list changed or items are carried, never a second post the same day. Title "PhD today, <weekday> <d Mon>". Tests: quiet hours, once per day, an empty day posts one line or nothing.
3. Tick-off consumer: read the topic with the backend credential, ignore messages the backend itself posted (carry an `agent` tag on every post), and parse the owner's messages: deterministic forms first (`done 1 3`, `drop 5`, `later 2`), then the inbox's bounded parser model for plain words. Record each as a `checklist_tick` row in the owner ledger (a class disjoint from approvals and decisions) keyed by day and item, idempotent by message id; acknowledge in one line, at most 3 acknowledgements a day. Tests: a message cannot create or alter an approval, a duplicate message id is stored once, an ambiguous message changes nothing and asks once.
4. Weekly summary (review-area artifact only): what was ticked, dropped and carried this week, for the owner to paste into the supervision note. Never write to the PhD repository; any change to its work items goes through that repository's own propose/review/ratify path.
5. Result doc with the actual model used and a live round trip (one post, one tick). Run the full test suite and stop.
**Done when:**
- A daily list posts to `phd-daily-checklist` within the cadence and caps, built only from PhD repository files, and a plain-words tick is recorded once and has no approval effect (tests plus a live dry run).
- The existing approval inbox behaviour and tests are unchanged; full suite green.
**Risks and stops:**
- PhD repository text must not leave the estate: use only deterministic code and the Claude lane for plain-words parsing; send no vault text to GLM or any other third-party model.
- Never post topic names, credentials or vault paths outside the lab. Never write to the PhD repository.
- If the backend credential cannot read the topic, record a `protected_handoff` with the exact error.

---

# Daily PhD checklist

## Why

The owner asked for a daily list of required accomplishments, drawn from the PhD repository's plans, that they can tick off on the phone. The topic exists and the first list was posted by hand; nothing yet builds the list each day or reads the ticks.

## Outcome

A short daily list on the phone that always reflects the repository's own plans, tells the truth about overdue items, and records ticks without ever giving them approval power.

## Rules that apply to this card (owner standing rules, 2026-11-06 and 2026-11-26)

- Internal Odysseus work only, through the normal branch, test, independent-review and PR lane. Sol review first (labelled GLM only if Sol is unavailable). Merge decisions follow the owner's merge rule.
- No new accounts, credentials, API keys, paid services, third-party dependencies or external writes beyond the owner's own ntfy server. If a stage needs one, stop and leave a precise owner debt (`protected_handoff`).
- Priority order is the only ordering. Do not add deadlines, time-boxes or concurrency caps of your own.
- Record the actual model used in every verification record.

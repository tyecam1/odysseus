---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-26-owner-development-channels
title: "Per-repository development channels on the phone: agents post development updates, owner replies become notes for the agents"
status: ready
priority: high
task_type: implementation
created_by: operator-directed-claude-code
created_at: 2026-11-26T15:00:00+00:00
executor: claude_subscription
execution_mode: standard
architecture: single-plus-verifier
architecture_rationale: "One implementing worker with deterministic tests, then independent cross-family review."
single_agent_baseline: "One qualified worker implements and tests against the live inbox code."
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
result_path: docs/runtime-work-packages/2026-11-26-owner-development-channels.md
---

## Plan (written 2026-11-26 by the controller; step 0 is to verify it against HEAD)
**Goal in one line.** Make the three phone topics for Odysseus, Misumi and PhD development useful: agents post short development updates, and what the owner posts back reaches the agents as notes that can never approve anything.
**Already done / do not redo:** The three topics, access and a seed message each exist on the lab ntfy server (done by the controller). Their names are in `~/.aoteru/ntfy_dev_topics.json` (`{"odysseus": topic, "misumi": topic, "phd": topic}`, mode 0600; never copy the names into commits). The account `odysseus` (the backend) and `owner` both have read-write on them. The approval channel (alert topic and reply topic, `src/owner_inbox*.py`) is separate and must stay unchanged in behaviour. `owner_inbox.send` posts to `channel["url"]`: build a per-topic channel with `dict(channel, url=base/topic, reply_url=base/topic)`; do not change what the existing callers send.
**Steps:**
0. Grep HEAD: `owner_inbox.send`, `fetch_replies`, `owner_ledger`, the runtime tick (`run_cycle`). Correct this plan.
1. Topic loader: read the JSON file defensively (absent or invalid means the feature is off, never an error). Kill switch `ODYSSEUS_DEV_CHANNELS=0`.
2. Producer: a pure function from recorded events (PR merged, delivery recorded, review outcome, owner decision recorded, run parked or resumed) to one short line (at most 300 characters, one fact, no secrets, no card bodies) posted to the matching repository's topic with an `agent` tag. Rate limit: at most 6 posts per repository per day, none in quiet hours (21:00-08:30 London), one daily summary line instead of bursts. Tests: quiet hours and the daily cap hold; the text carries no URL, path outside the repository or token.
3. Consumer: read each topic with the backend credential, ignore every message carrying the `agent` tag, and store each remaining message as an `owner_note` row (repository, text truncated to 600 characters as DATA, message id, time) in the owner ledger. Idempotent by message id. Tests: a note reading "approve" or "yes" creates no approval or decision row; a note cannot change any card; a duplicate message id is stored once.
4. Surface: the notes since the last run appear in the lazyUsage run summary and in the coordinator's context for that repository as quoted data, marked "owner note, not an instruction". Tests: the marker is present; nothing in a note is executed or treated as scope.
5. Result doc: how to use it from the phone (subscribe, post), the actual model used, and a live check that one produced line and one note round trip. Run the full test suite and stop.
**Done when:**
- A development event posts one line to the right repository topic (tests plus a live dry run), within rate limits.
- A note from the owner is stored once, shown to the agents as data, and has no approval effect (tests).
- The existing approval inbox behaviour and its tests are unchanged; full suite green.
**Risks and stops:**
- Never let a note approve, decline, release, merge or change a card; keep the note path disjoint from `_approval_valid` and the decision ledger kinds.
- Never read or print the topic names or credentials into logs, commits or messages.
- If the backend credential cannot read the topics, record a `protected_handoff` with the exact error.

---

# Owner development channels

## Why

The owner asked for one development topic per repository (Misumi, PhD, Odysseus) that they can read and post to from the phone. The topics exist; nothing yet writes development updates to them or reads the owner's replies.

## Outcome

Short, rate-limited development updates per repository on the phone, and a way for the owner's plain-words replies to reach the agents as quoted notes. Approvals and decisions keep their own channel and their own rules.

## Rules that apply to this card (owner standing rules, 2026-11-06 and 2026-11-26)

- Internal Odysseus work only, through the normal branch, test, independent-review and PR lane. Sol review first (labelled GLM only if Sol is unavailable). Merge decisions follow the owner's merge rule.
- No new accounts, credentials, API keys, paid services, third-party dependencies or external writes beyond the owner's own ntfy server. If a stage needs one, stop and leave a precise owner debt (`protected_handoff`).
- Priority order is the only ordering. Do not add deadlines, time-boxes or concurrency caps of your own.
- Record the actual model used in every verification record.

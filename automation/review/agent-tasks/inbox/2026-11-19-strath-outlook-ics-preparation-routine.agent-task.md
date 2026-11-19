---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-19-strath-outlook-ics-preparation-routine
title: "Implement an automatic Strathclyde Outlook ICS-backed event preparation routine"
status: inbox
priority: medium
task_type: implementation
created_by: chatgpt
created_at: 2026-11-19T11:25:00+00:00
updated_at: 2026-11-19T11:25:00+00:00
executor: claude_subscription
execution_mode: staged-loop
architecture: single-plus-verifier
architecture_rationale: "Deterministic calendar ingestion, scheduling and change detection with one bounded planner; independent privacy/security and idempotency verification."
single_agent_baseline: "One qualified implementation worker reuses existing feed/parser/scheduler/task services; no new orchestration authority."
execution_host: compute-box
context_budget: medium
coordination_reason: "Backend scheduling belongs to Odysseus while research context, preparatory notes and research task authority remain in obsidian-PhD."
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
  - automation/review/**
  - docs/**
  - config/**
  - routes/**
  - services/**
  - src/**
  - core/**
  - scripts/**
  - tests/**
  - migrations/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/.obsidian/plugins/**/data.json"
inputs:
  - tyecam1/odysseus live default branch and current scheduler, calendar, tasks, estate preflight and notification contracts
  - tyecam1/obsidian-PhD:.obsidian/plugins/obsidian-day-planner/manifest.json
  - tyecam1/obsidian-PhD:.gitignore
  - tyecam1/obsidian-PhD:Scripts/engine/ICS-CSV.py
  - tyecam1/obsidian-PhD:Scripts/engine/calendar.ics (historical snapshot only; not live source)
  - tyecam1/obsidian-PhD:Scripts/engine/calendar.csv (historical snapshot only; not live source)
outputs:
  - secure, automatically refreshed read-only Strathclyde Outlook ICS feed with observability and stale-feed handling
  - reconciled event occurrences and deterministic upcoming-event planning triggers
  - event-specific preparation proposals/tasks using existing Odysseus scheduling and PhD context
  - automated tests and one real-path verification with redacted evidence
result_path: ""
review_report_path: ""
handoff_model: ""
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "New request; triage under AGENTS.md shipping-first policy. ICS subscription URL is a bearer secret: never expose it in git, issues, notes, prompts, logs or model context."
---

# Automatic event preparation from Strathclyde Outlook

## Goal

Make existing agents reliably prepare for upcoming PhD commitments without manual calendar copying. Reuse the existing Strathclyde Microsoft 365 published ICS feed configured in the locally ignored Obsidian Day Planner data, existing ICS-to-CSV parsing where useful, and Odysseus task/calendar/scheduler/notification facilities. Do not implement a second calendar system, queue, planner daemon or model router.

## Work

1. **Inspect live authority and existing facilities.** Start from live repo/runtime state. Run `aoteru preflight` for this task. Locate the current scheduler, task engine, calendar integrations, notification delivery, repo context retrieval and privacy gates. Check for a current equivalent task/function before building. Reconcile the PhD vault's historical ICS/CSV exports: they are snapshots, not a live feed.
2. **Establish secure source access.** Prefer the existing ICS subscription URL from the *local, gitignored* `.obsidian/plugins/obsidian-day-planner/data.json` if it is reachable on an authorised host. Treat it as a bearer secret and keep it in the existing Odysseus local credential/configuration mechanism. If the subscribed URL is inaccessible or revoked, surface one precise protected setup gate instead of guessing an endpoint or bypassing university controls. Do not copy subscription URLs or calendar payloads to any repository, branch, prompt, report, telemetry, or shared model call.
3. **Refresh automatically.** Implement a read-only, bounded polling job using the established scheduler (initial default: every 60 minutes). Use HTTP caching when supported (ETag / Last-Modified), bounded network timeouts, retry/backoff, last-success and staleness status. Validate feed content and reject unexpected hosts/redirects and oversized input. A failed refresh must not silently replace a current calendar with an empty one.
4. **Reconcile events correctly.** Parse timezone-aware events in Europe/London, including DST, RRULE/RDATE/EXDATE, RECURRENCE-ID overrides, all-day events, moved/cancelled occurrences and multi-day events. Give each occurrence a stable identity (calendar source + UID + occurrence key), retain event update state, and avoid duplicate/obsolete planning actions. Prefer reuse/refactoring of `obsidian-PhD/Scripts/engine/ICS-CSV.py` if appropriate; do not maintain competing recurrence implementations without a demonstrated reason.
5. **Plan useful preparation, not summaries of everything.** On initial sync, daily planning and meaningful changes, inspect an upcoming 14-day window, with 7-day and 24-hour preparation checkpoints. Select PhD-relevant events (supervision, CPI/industry meetings, conferences, experiments, deadlines, presentations); exclude irrelevant events by default. For each eligible event, derive concise proposed preparation actions, lead time, relevant repo evidence/meeting notes, and missing information using existing PhD knowledge retrieval. No invented meeting aims, documents or deadlines. Prefer deterministic rules over model inference; use the cheapest live qualified model only if event-specific interpretation materially helps.
6. **Use the existing action surfaces.** Create or update deduplicated preparation tasks/reminders in the established scheduler/task surface, linked to the original event occurrence. Do not automatically accept calendar invites, send emails, edit Outlook events, or write canonical PhD research claims. Respect existing PhD-domain task/note authority. Default to reviewable proposals for research-sensitive actions; permit no-op when no preparation is warranted. Use the already established notification path, not another notifier. Avoid noisy rescheduling or repeat notifications for unchanged events.
7. **Privacy and governance.** Only pass minimal relevant, redacted event metadata to models. Do not expose invitee lists, confidential subjects, descriptions, conferencing links, event bodies or the ICS URL to prompts by default. Respect university rules and existing cross-repo ownership boundaries. Store operational cache only in ignored/private runtime storage with bounded retention.
8. **Verify and ship.** Test against synthetic ICS fixtures and the authorised real feed without exposing private contents. Record exact checks, baseline vs regression, a refreshed-run proof, and a same-input no-op rerun; close out through the repo's normal review, deployment and queue lifecycle. Do not treat an implemented-but-unexecuted job as delivered.

## Acceptance criteria

- [ ] On an authorised host, unattended feed refresh succeeds and reports last-success, freshness, and failure state; a revoked/unavailable feed fails visibly and safely.
- [ ] Newly created, changed, recurring, moved and cancelled events converge to correct event occurrences and preparation tasks across DST boundaries.
- [ ] Relevant 14-day events produce actionable, non-invented preparations at appropriate lead times, with direct links to existing repo context and original event identity.
- [ ] Unchanged feed reruns produce **zero** duplicate tasks/notifications; cancelled/moved meetings invalidate obsolete preparations without deleting unrelated work.
- [ ] No calendar URL, raw private event payload or credential is committed, logged, leaked to prompts, or exposed through a public repository.
- [ ] Runs through existing Odysseus scheduler, task engine, estate model routing and notifications; no additional queue/runtime ownership.
- [ ] Tests, one redacted end-to-end real-feed check, independent privacy/idempotency review and actual deployment evidence are recorded before closing.

## Completion boundary

Task remains `inbox` until the existing shipping-first backlog permits admission; at execution time re-check live repo state and deduplicate against any calendar work already shipped. Complete only when the recurring job has run end-to-end in the target runtime and safely generated or reconciled real preparation actions, not merely when source code is committed.

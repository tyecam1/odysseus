---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-11-06-routine-owner-data-export-ingest
title: "Routine owner data export and ingest (ChatGPT, Instagram, others)"
status: approved
priority: normal
task_type: recurring-governed-ingest
created_by: claude
created_at: 2026-11-06T09:00:00+00:00
executor: claude-sonnet-5
execution_mode: human-triggered-recurring
repo: tyecam1/odysseus
branch: dev
---
# Routine owner data export and ingest

## Mission

Every 60 days (adjustable by the owner) (and on demand) bring the owner's platform exports through the existing pipelines, with no new service, DB or framework. Cadence is a reminder to the owner, not an unattended login.

## Sources

- ChatGPT: owner requests the export; `/ingest "<zip>"` (src/chatgpt_ingest.py) does transfer, extract, local-strong review, pointer handoff, digest. Re-imports skip unchanged conversations (content hash), so each run only processes new/changed ones.
- Instagram: existing acquisition and ingestion path (PRs #183/#187/#188/#196); sessions need a coordinated at-monitor login with phone approval.
- Further sources are added only by their own approved spec, one at a time.

## Steps

1. Reminder to owner with the exact export links for each source (no credentials held by the agent).
2. Owner downloads or approves each export; the controller never logs in on the owner's behalf.
3. Run the per-source ingest on the lab; private payloads stay on the lab.
4. Return the short report: processed, candidates, approved/denied/escalated, destinations, awaiting approval, failures, ledger location.

## Boundaries

- No canonical writes; PhD and Misumi stay human-gated; destructive, financial, credential-bearing and other-people-consent items go to the owner.
- Local models only for private text; stronger review stays local-strong unless a separate egress decision exists.
- No source text in Git, logs, telemetry, PR descriptions.
- Honour write leases and approval gates; one run per source at a time.

## Done when

An owner-triggered cycle completes for each enabled source and the report is delivered; failures are reported, not retried silently.

## Owner decisions (2026-11-06)

- Cadence 60 days, adjustable.  Gates are resolved by a context-aware agent; the owner is asked only for credential, financial,
  destructive or other-people-consent matters (see ~/.claude/dispatch-controller.md, Escalation minimisation).
- Family content goes to the Misumi people wing (private store); unparseable conversations may use a low-cost paid lane;
  the raw archive is deleted once processed.

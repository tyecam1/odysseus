---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-26-card-hygiene-validator-and-sweeper
title: "Card hygiene: validator and sweeper so cards stop defaulting to the owner or to the wrong host"
status: ready
priority: high
task_type: implementation
created_by: operator-directed-claude-code
created_at: 2026-11-26T01:30:00+00:00
executor: claude_subscription
execution_mode: implementation
architecture: single-plus-verifier
architecture_rationale: "One implementing worker with deterministic tests, then independent cross-family review."
single_agent_baseline: "One qualified worker implements and tests against live repository evidence."
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
  - scripts/**
  - src/**
  - tests/**
  - docs/**
  - automation/review/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*token*"
  - "**/*password*"
inputs:
  - AGENTS.md
  - docs/aoteru-model-host-routing-contract.md
result_path: docs/runtime-work-packages/2026-11-26-card-hygiene.md
---
# Card hygiene: stop cards defaulting to the owner or the wrong host

## Why

An Opus review on 2026-11-26 found that about 10 of the 40 gated cards were blocked by card metadata defects, not by a genuine owner decision: an empty write scope or result path, a `laptop` host pin with no reason (the lab can run it), an executor that breaks the model rules (GLM-Flash on an evaluation card), an executable parent or container card, a passed event date that left the card live, and review-bucket cards with no recorded reviewer model although machine records exist. Every one of these either lands on the owner or silently blocks agents.

## Outcome

1. A **validator** (extend the existing card checkers; do not add a second system) that rejects or flags new and changed cards with these defects, with a clear one-line reason:
   - `approval_required: true` with an empty `allowed_paths` or no `result_path` (no approval can bind to nothing);
   - an owner gate with no `owner_gate_class` (allowed: none, money, credential, external_write, other_people, destructive, security, contract_conflict, physical_labour); a card without a class defaults to the advisor tier, never to the owner;
   - a host pin (`execution_host: laptop|home`) with no `host_required_reason` naming a device-only resource (a logged-in browser, launchers, physical hardware);
   - GLM-Flash (or any mechanical-only executor) assigned to verification or judgement work;
   - an executable parent/container card whose children are the execution units;
   - an `event_date` in the past (new optional field; `due_date` is not an urgency signal and must not be read as one).
2. A **sweeper** that reads the existing queues and writes, per repository, a reviewable proposal set under `automation/review/card-hygiene/` (one small metadata patch per card, with the reason), never editing canonical cards directly. Metadata PRs follow each repository's own contract.
3. **Reviewer attestation backfill**: for review-bucket cards whose reviewer model is not attested, find machine-recorded evidence only (tagged Sol call records, fallback-lane headers, PR review records) and propose the attestation; never accept prose. Cards that cannot be attested get a bounded re-review proposal.
4. A one-line **owner-load metric** the daily digest can show: open owner gates, how many were settled by an agent or advisor, how many by the owner.

## Verification

Deterministic: unit tests over fixture cards for every defect class, the sweeper on a copy of today's queue (expected: the defects named above are found, no canonical file changed), and a test that an owner-class card with a valid class is left alone.

## Rules that apply to this card (owner standing rules, 2026-11-06 and 2026-11-26)

- Internal Odysseus work only, through the normal branch, test, independent-review and PR lane. Sol review first (labelled GLM only if Sol is unavailable). Merge decisions follow the owner's merge rule.
- No new accounts, credentials, API keys, paid services, third-party dependencies or external writes. If a stage needs one, stop and leave a precise owner debt (`protected_handoff`); never work around it.
- Priority order is the only ordering. Do not add deadlines, time-boxes or concurrency caps of your own.
- Never touch owner approval, delegation or card-approval code paths except where this card names them, and never widen what a model may approve.
- Record the actual model used in every verification record.

## Plan (written 2026-11-26 by the controller; step 0 is to verify it against HEAD)
**Goal in one line.** Extend the existing card checkers to flag six metadata defects, and add a proposal-only sweeper, reviewer-attestation backfill and owner-load metric.
**Already done / do not redo:** The agent-task/v2 card checkers already exist (locate with grep: `agent-task/v2`, `allowed_paths`). Extend them and never add a second validator. src/owner_ledger.py already records the owner decisions that lift gates, and the metric reads it. Tagged Sol call records and fallback-lane headers are the existing machine evidence.
**Steps:**
0. Grep HEAD for the checker, queue loader, parent/child fields, `execution_host`, `executor`, `due_date`, the digest builder and the ledger API. Correct this plan and log what you find.
1. Checker: add six rules, each with a stable code and a one-line reason. Add optional fields `owner_gate_class` (the card's enum; a card without one routes to the advisor tier, never the owner), `host_required_reason` and `event_date`. Tests: one fixture card per defect fails with its code; a valid owner-class card passes untouched; `due_date` alone flags nothing.
2. Executor rule: use the mechanical-only executor set from docs/aoteru-model-host-routing-contract.md or its code constant. Test: GLM-Flash is flagged on verification work, not on mechanical work.
3. Sweeper (scripts/): read queues read-only and write one metadata patch plus reason per card under automation/review/card-hygiene/<repo>/. Test: on a copy of today's queue the defects are found and canonical hashes are unchanged.
4. Attestation backfill from machine records only (tagged Sol records, fallback-lane headers, PR review records), citing record ids. Where no record exists, propose a bounded re-review. Test: prose-only evidence is refused.
5. Owner-load metric from the ledger: open gates, settled by agent or advisor, settled by owner. Fixture test; hook it into the digest only through an existing extension point.
6. Write docs/runtime-work-packages/2026-11-26-card-hygiene.md (step-0 findings, defect counts, test output, actual model used). Run the full pytest suite and stop.
**Done when:**
- Each defect class fails a fixture test; clean and valid owner-class cards pass.
- The sweeper run changes zero canonical files (hash check) and writes only under automation/review/card-hygiene/.
- Every attestation proposal cites a machine-record id.
- Full suite green; the result doc names the model.
**Risks and stops:**
- If the new rules fail existing canonical cards, reject only new or changed cards and warn on the rest.
- Never edit canonical cards; metadata PRs follow each repository's contract separately.
- The gate class only routes work; never touch approval or delegation code.
- An unreadable queue becomes a protected_handoff naming the path.
**Ordering note:** Needs nothing first. Unblocks avenue-to-develop's unblocking children (repairs, host re-pins, attestations) and validates the Zotero read/write split.

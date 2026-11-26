---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-26-zotero-read-snapshot
title: "Zotero read-only snapshot on the lab so literature work stops waiting on a live Zotero"
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
result_path: docs/runtime-work-packages/2026-11-26-zotero-read-snapshot.md
---

## Plan (written 2026-11-26 by the controller; step 0 is to verify it against HEAD)
**Goal in one line.** Let cards that only read Zotero run on the lab from an immutable, hashed, age-checked library snapshot, while Zotero writes stay human-gated.
**Already done / do not redo:** The `requires_zotero` field and the `requires_zotero_unavailable` skip already exist (locate with grep). Extend that feasibility check; do not add a parallel one. No snapshot route exists yet.
**Steps:**
0. Grep HEAD for `requires_zotero`, the skip reason, the card checker, the feasibility check, settings and any existing scheduled-job mechanism. Correct this plan.
1. Schema: add `requires_zotero_read` and `requires_zotero_write`; `requires_zotero` stays as an alias for write. Test: a legacy `requires_zotero: true` card blocks exactly as today.
2. Snapshot builder: a stdlib sqlite3 backup of the library database into a dated read-only directory at a configured location, a manifest (sha256, UTC time, source, item count) and metadata-only JSON and BibTeX exports. Test on a fixture library: hash recorded, exports parse, no attachments copied.
3. Read helper: opens snapshots only through an SQLite `mode=ro` URI. Test: a write attempt raises.
4. Feasibility: a manifest younger than a configured age satisfies `requires_zotero_read`. A stale or missing snapshot skips with its own reason, write still blocks, and stages that need no Zotero run regardless. One test for each case.
5. Provenance helper that returns the snapshot hash and date for every consuming output to record; test.
6. Refresh through an existing scheduled mechanism; build no new scheduler. If the library is unreachable from the lab, write a protected_handoff naming the exact file to copy, the lab destination and the cadence. Create no Zotero Web API key.
7. Write docs/runtime-work-packages/2026-11-26-zotero-read-snapshot.md (findings, a read-only feasibility dry run of the five review-only audit cards against a fresh fixture snapshot, actual model). Run full pytest and stop. Live acceptance on those cards comes after deploy.
**Done when:**
- Tests prove: write fails, hash recorded, stale snapshot refused, write-required card still blocks, legacy alias unchanged.
- No third-party dependency is added.
- The result doc gives the five audit cards' dry-run outcome or the protected_handoff.
- Full suite green.
**Risks and stops:**
- Never weaken `requires_zotero`. Re-tagging the eight skipped cards is a proposal under automation/review/, not a canonical edit.
- If the live database is locked or unreachable, stop at the owner debt; no scraping, syncing or credentials.
- Attachments stay out of the snapshot (fetched on demand).
**Ordering note:** Independent. Align field names with the card-hygiene checker if it lands first. Unblocks the eight `requires_zotero_unavailable` cards and avenue-to-develop's Zotero-snapshot child.

---

# Zotero read-only snapshot

## Why

Eight cards are skipped as `requires_zotero_unavailable`, including review-only audits and literature syntheses that only need to read the library. A hard live-Zotero requirement blocks all of them.

## Outcome

1. Split the card requirement into `requires_zotero_read` and `requires_zotero_write` (keep `requires_zotero` as an alias for write so nothing existing weakens). Write stays human-gated.
2. A **read-only snapshot route**: an immutable copy of the library database plus a BibTeX/JSON export (metadata only; attachments fetched on demand), refreshed on a schedule, readable by lab agents. Every output that uses it records the snapshot hash and date.
3. The runtime treats `requires_zotero_read` as satisfied when a snapshot younger than a configured age exists; stages of a card that do not need Zotero run regardless.
4. If the library is not reachable from the lab, do not improvise: write the precise export request as an owner debt (`protected_handoff`) naming exactly what to copy and where. No Zotero Web API key is created (that would be a new credential).

## Verification

Tests over a fixture library: read-only (a write attempt fails), the snapshot hash is recorded, a stale snapshot is refused, a card requiring write still blocks. The five review-only audit cards in the queue are the live acceptance.

## Rules that apply to this card (owner standing rules, 2026-11-06 and 2026-11-26)

- Internal Odysseus work only, through the normal branch, test, independent-review and PR lane. Sol review first (labelled GLM only if Sol is unavailable). Merge decisions follow the owner's merge rule.
- No new accounts, credentials, API keys, paid services, third-party dependencies or external writes. If a stage needs one, stop and leave a precise owner debt (`protected_handoff`); never work around it.
- Priority order is the only ordering. Do not add deadlines, time-boxes or concurrency caps of your own.
- Never touch owner approval, delegation or card-approval code paths except where this card names them, and never widen what a model may approve.
- Record the actual model used in every verification record.

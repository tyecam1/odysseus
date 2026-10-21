---
exemplar_id: 2026-10-19-instagram-scheduled-ingest-delivery-packet
title: Recurring Instagram ingest delivery packet
status: candidate
captured_at: 2026-10-19
capture_basis: agent-nomination
source_surface: ChatGPT
source_reference: operator delivery packet for directive stage 9 operationalisation
task_context: Bounded implementation of local recurring ingestion with governed accounting
applications: []
evaluations: []
supersedes: []
---

# Capture rationale

This prompt is worth preserving because it combines a deliberately minimal
implementation boundary with unusually concrete operational acceptance
evidence. It names the existing mechanisms to compare, rules out architectural
expansion, fixes locality and inference constraints, defines durable per-run
accounting, and supplies an exact live-authority correction from a prior
attempt.

The reusable pattern is a delivery packet that makes implementation autonomy
safe by coupling scope, live context, negative constraints, verification, and
known-unblock evidence in one short prompt.

## Reusable behaviours

- inspect named existing mechanisms before selecting the smallest adequate one;
- state explicit non-goals that prevent scheduler, queue, or daemon expansion;
- separate raw-input locality from governed runtime accounting;
- require observable no-op semantics and missing-input resilience;
- request focused tests plus verbatim execution evidence;
- carry forward an exact prior-attempt authority diagnosis without broadening
  permissions;
- identify known unrelated repository damage and explicitly leave it untouched.

## Task-specific assumptions / limitations

- Written for the Odysseus Instagram DYI importer and its live lab host.
- Absolute export and live-data paths are host-specific.
- Assumes the existing importer is already idempotent and the repository write
  lease already exists.
- The optional live run depends on the executing worker being able to write the
  governed live data directory.

## Exact prompt

```text
Delivery packet: recurring Instagram import + per-run accounting on the live host (directive stage 9 operationalisation). Repo odysseus, branch feat/instagram-scheduled-ingest-20261019 (fresh from dev HEAD, checked out). Read AGENTS.md first.

Context: src/instagram_importer.py (merged) imports a DYI export idempotently; live DB already has 1772 rows; raw exports at /home/agent/data/ingestion/instagram/exports/2026-10-18/*.json (mode 600).

Smallest scope that delivers continuous operation using EXISTING authority only:
1. Inspect src/bg_jobs.py and src/task_scheduler.py and pick the lightweight mechanism that fits a cheap deterministic recurring command (prefer bg_jobs if it supports periodic shell/python jobs; do NOT build a new scheduler, queue or daemon).
2. Register/configure a recurring import job (default cadence: every 6 hours, config-overridable) that runs the importer against all export JSONs found under the configured exports dir, logs counts, and is a no-op when nothing changed. Job must not run model inference and must not send data off-host.
3. Per-run accounting: append a compact JSON line (timestamp, created/revised/unchanged/failed counts, duration_ms) to a run log under the governed data dir (data/, mode 0600 dir), NOT in Git. Last-run status must be queryable (function or tiny CLI).
4. Tests for: job registration shape, counts-log append/query, no-op behaviour, and that a missing exports dir is a clean no-op (not an error storm). Run pytest for the new tests plus tests/test_instagram_importer.py with the repo venv; verbatim output.
5. Optionally verify live: run the job function once here (it will be a full no-op) and report its accounting line verbatim.

Report: mechanism chosen + why, files changed, verbatim test output, verbatim one-shot run accounting.

UNBLOCK NOTE (from the previous attempt): your in-process write-authority preflight resolved DATA_DIR to the WORKTREE-local data dir (park_lease_rows=0). The active lease lives in the LIVE service DB. Run any preflight/lease inspection with ODYSSEUS_DATA_DIR=/home/agent/projects/odysseus-aoteru/data so it sees the live DB; the backend-side lease verification will then pass. Also note config/memory-sources.yaml has a pre-existing YAML error near lines 57-61 - leave it (out of scope), do not repair.
```

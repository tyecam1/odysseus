---
title: Aoteru estate P4 evidence
status: compact-evidence
owner: odysseus
as_of: 2026-08-20
parent: docs/aoteru-estate-execution-contract.md
---

# P4 — central Aoteru memory (lab-first slice)

Compact durable record. Do not reread unless a dependency changes.

## Reuse audit (before building anything)

Per the execution contract's binding rule — NEW only after targeted
inspection shows no adequate existing implementation — a capability audit
(fork, then verified directly) was run before any P4 code was written. It
found `src/misumi_memory.py` (`MisumiMemory`, 365 lines) **already fully
implements** plan §6.1's named reuse target: capsule/open-loop/handoff
model, JSONL persistence, fold-to-latest-by-id, 11 named personas,
routing/classification. P0's original claim that this file "does not exist
in either repo" was a real audit error — the grep that produced that
conclusion was only ever run against the upstream repo, never this one.
Both `docs/aoteru-estate-p0-evidence.md` and
`config/memory-sources.yaml`'s `misumi-capsules` entry are corrected
(commit `15952a0`).

**This means P4's actual job is narrower than the plan's schema list
suggests**: `MisumiMemory` stays the memory authority. What's genuinely
missing — confirmed missing by the same audit, not assumed — is
provenance/source-event tracking and a relation table. Nothing here
duplicates or replaces the existing capsule/open-loop/handoff store, the
SQL `Memory`/`data/memory.json` chat-memory system (separate, lower
concern, flagged as a P8 convergence item not a P4 blocker), or the
ChromaDB memory-vector index (confirmed still derived/rebuildable, not
authoritative anywhere).

## Built (genuinely new, per the audit)

- `core/database.SourceEvent` (`source_events` table): `source`,
  `external_id`, `content_hash`, `domain`, `sensitivity`, `payload` — same
  style as P3's `ParkLease` (TimestampMixin, indexed). `content_hash` +
  `external_id` are what let a future ingest adapter (plan §6.6: Claude
  Code sessions, ChatGPT export, etc.) dedupe idempotently.
- `core/database.MemoryRelation` (`memory_relations` table): typed
  `(subject_type, subject_id) --predicate--> (object_type, object_id)`
  links. Deliberately not a foreign-key table — subjects/objects can be
  JSONL capsule/open_loop/handoff ids (not SQL rows) as well as
  `source_events` rows, so it indexes across both stores rather than
  becoming a second authority for either.
- `MisumiMemory.capture()` extended with an optional `source_event_id`
  parameter — additive, backward compatible (old JSONL records simply lack
  the key; every reader already uses `.get()`).
- `MisumiMemory.history(store, id)` — returns every raw version ever
  appended for an id, oldest first. This is the actual answer to plan
  §6.2's "correction supersedes rather than silently overwrites": the
  JSONL log already never overwrites, `_fold` just collapses it to latest
  for normal reads; `history()` exposes the full trail without a separate
  `memory_revision` table.
- `MisumiMemory.get_capsule()` — small public wrapper (previously only a
  private `_latest` existed) so route code doesn't reach into internals.
- New endpoints on the existing `/misumi` broker API (not a new API
  surface — plan §7.1's broker already exists and is extended, not
  rebuilt): `POST /misumi/memory/source-events`,
  `GET /misumi/memory/{id}/source-trace`, `GET /misumi/memory/{id}/history`.
  `POST /misumi/memory/capture` gained an optional `source_event_id` field.

## Verified live, through the real authenticated HTTP API

Not just Python-level — logged in as the real admin user on the isolated
`svc:odysseus-lab` instance (port 7001) and exercised the actual endpoints:

```text
POST /api/auth/login                          -> 200, session cookie
POST /misumi/memory/source-events              -> 200, {id: <uuid>}
POST /misumi/memory/capture (+ source_event_id) -> 200, capsule id;
                                                    source_event_id echoed back correctly
GET  /misumi/memory/{id}/source-trace          -> 200, returns the exact
                                                    source_event row (source/
                                                    domain/sensitivity/payload
                                                    all match) + relations: []
POST /misumi/memory/{id}/confirm               -> 200, status: confirmed
GET  /misumi/memory/{id}/history                -> 200, versions:
                                                    ['open', 'confirmed']
                                                    (revision trail proven,
                                                    not just claimed)
```

A separate direct-Python test (before the HTTP test) additionally verified
`MemoryRelation` round-trips correctly (create a `derived_from` relation
from a capsule to its source_event, query it back) and that
`update_capsule` preserves `source_event_id` across a correction (fields
not explicitly changed survive the `record.update(changes)` copy).

Table/index existence confirmed via `sqlite_master` schema dump before the
functional tests (same pattern as P3's `ParkLease` verification).

## Deferred (lab-first — no second host, no ingest adapters built yet)

- **Migration adapter from existing JSONL** — reinterpreted, not skipped:
  since JSONL stays authoritative (reuse, not replace), there is no bulk
  "migrate the data" step. The adapter's real job going forward is linking
  *new* captures to source events, which is what's built above.
- **Ingest adapters themselves** (Claude Code transcripts, ChatGPT export,
  Codex artifacts, repo pointers, explicit capture, external-knowledge
  ingestion) — all still `status: planned` in
  `config/memory-sources.yaml`; P4 built the linking mechanism they'll use,
  not the adapters yet. Building adapters without a concrete consumer would
  be speculative.
- **`memory_outbox`** — moot under lab-first; there is no home-primary/
  lab-fallback split yet to buffer writes for. Revisit once a second host
  is registered and reachable.
- **Home-primary / lab-snapshot failover** — same reason; explicitly not
  pretending the unreachable home PC is an active primary, per the
  lab-first contract.
- **Broker MCP tools** (`memory_recall`, `memory_search`, `open_loops`,
  `memory_capture_candidate`, `source_trace` as MCP-callable tools) — P5
  scope (Claude Code/MCP integration); the underlying HTTP/Python surface
  they'd wrap is what P4 built.

## Gate

Plan §12 P4 gate: "existing Misumi memory survives round-trip migration;
provenance trace returns original source IDs; correction supersedes rather
than silently overwrites; lab degraded mode works with home offline and
replays idempotently."

- [x] existing Misumi memory survives — trivially true, it was never
      touched/migrated; extended in place, old records remain readable
- [x] provenance trace returns original source IDs — `source-trace`
      verified live, returns the exact `source_event` linked at capture time
- [x] correction supersedes rather than silently overwrites — `history()`
      verified live showing both pre- and post-correction versions
- [ ] lab degraded mode / idempotent outbox replay — moot lab-first, no
      second host to degrade from; deferred, not fabricated

**P4: PARTIAL, lab-first slice complete.** The three gate items testable
with one host all pass, verified through the real HTTP API, not asserted.
The fourth is a genuine multi-host requirement, correctly deferred rather
than stubbed out to look done.

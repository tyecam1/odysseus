# Misumi durable transcript runtime

Status: implemented on `dev` behind a feature flag (disabled by default). Programme: `misumi-long-horizon-programme@v1`.
Task: `automation/review/agent-tasks/inbox/2026-10-01-misumi-durable-transcript-runtime.agent-task.md`.

## Invariant

```text
capture -> transcribe -> DURABLY PERSIST -> acknowledge -> wake/intent gate -> optional /misumi/respond
```

A transcript is acknowledged (`persisted: true`) **only after the database commit**. A non-wake utterance is still stored; the wake decision is attached afterwards and never decides retention. Raw audio is never stored by the server (the audio endpoint holds it in memory for one request).

Transcript rows are operational history. They are not semantic memory (`src/misumi_memory.py` capsules), not household truth (the Misumi Git knowledgebase outranks them) and are never committed to Git or auto-promoted to memory.

## Authority and placement

- **Write authority:** one Odysseus instance — the household deployment on the home host. No replica, no failover, no second writer. During a home outage the *client* buffers; the server does not fail over.
- **Audio locality (`data_locality: home-lan`):** `POST /misumi/transcript/audio` is refused (`403 audio_locality_refused`) unless this host is a registered `home` host in `config/estate.yaml`. There is no fallback to another host and an unregistered host fails closed. Only the **local** STT provider is accepted (`403 stt_provider_not_local` otherwise, before any audio is read): an `endpoint:<id>` provider would send the audio to another service while the row still claimed the home host ran it. `ODYSSEUS_TRANSCRIPT_AUDIO_HOSTS` (comma-separated host ids or `*`) is an explicit operator override for development and tests only. Speech-to-text runs through the instance's own STT service, so `stt.host` is the physical host that executed it.
- **Enabling:** two independent switches must both be on. `ODYSSEUS_MISUMI_TRANSCRIPT_ENABLED=1` (deployment kill-switch; every route returns `503 runtime_disabled` otherwise) and the owner's `transcript_archive` policy (default **off**; with it off nothing is stored and the response says so).
- **Ambient production is human-gated.** The ratified 2026-07-20 ambient-capture contract is conditional on everyone in range knowing and agreeing; record that consent before enabling the archive for a shared space.

## Data model

`misumi_transcript_events` (new, additive; created by `Base.metadata.create_all` at start-up):

| column | notes |
| --- | --- |
| `seq` | integer primary key, used for keyset pagination |
| `owner` | NOT NULL; `""` is the local/no-auth owner (SQLite treats NULLs as distinct inside a unique constraint, so a nullable owner would defeat idempotency) |
| `domain` | default `misumi` |
| `event_id` | client-generated idempotency key; **`UNIQUE(owner, domain, event_id)`** |
| `text`, `text_sha256` | verbatim text; the hash detects same-id/different-text conflicts |
| `capture_mode` | `ambient` or `ptt` |
| `source` | `audio-upload`, `text-event`, `import:box-day-file` |
| `capture_started_at`, `capture_ended_at` | client capture times (UTC), kept separate from `persisted_at` |
| `stt_provider`, `stt_model`, `stt_host`, `stt_latency_ms` | attribution; `stt_host` is the executing host, never a guess |
| `persona` | presentation context only |
| `wake_result`, `wake_recorded_at` | attached **after** persistence |
| `session_id`, `response_request_id` | optional linkage to a Misumi conversation |
| `state` | `persisted` |

`misumi_retention_policies` (per owner): `transcript_archive` (default **false**), `transcript_retention_mode` (**`finite`** by default, or **`permanent`**) and `transcript_retention_days` (the finite window: default **14**, clamped to 1–90; reported as `null` while the mode is `permanent`, with the stored window kept as `transcript_retention_days_if_finite`). Retention is enforced **on read** (rows older than the window are never returned, looked up or exported, even if no purge has run, and shortening the window takes effect immediately) and physically removed by bounded drain purges on ingest, on list/export and via `POST /misumi/transcript/purge`, `raw_audio_retention` (fixed `off`).

## Endpoints (all owner-scoped; `misumi:execute` to write, `misumi:read` to read)

| route | purpose |
| --- | --- |
| `POST /misumi/transcript/audio` | multipart: `file`, `event_id`, `capture_mode`, `capture_started_at`, `capture_ended_at`, `persona`. STT then commit then ack. A retry of a stored `event_id` returns the stored row (`deduplicated: true`) and does **not** run STT again. |
| `POST /misumi/transcript/events` | text-only ingest (the box's forwarded windows, imports, tests). |
| `PATCH /misumi/transcript/{event_id}/wake` | attach the wake/intent decision and optional `session_id` / `response_request_id` (idempotent). |
| `GET /misumi/transcript` | recent/range query, keyset pagination (`before_seq`/`after_seq`), `limit` 1–200. Never unbounded. |
| `GET /misumi/transcript/{event_id}` | one event. |
| `GET /misumi/transcript/export` | `jsonl` or `md`, oldest first, bounded (`limit` ≤ 1000). |
| `GET/PUT /misumi/transcript/policy` | read/set `transcript_archive`, `transcript_retention_mode` and `transcript_retention_days`. |
| `POST /misumi/transcript/purge` | drain this owner's expired rows now (bounded: at most 50 batches per call). |
| `POST /misumi/transcript/import` | idempotent import of interface-box day-file lines (compat stage A). |

## Client-visible states

| state | HTTP | meaning | client action |
| --- | --- | --- | --- |
| `persisted` | 200 | durable row exists (`deduplicated` says whether it already did) | delete the queued audio, show **saved** |
| `no_speech` | 200 | STT returned nothing; no row | drop the segment |
| `credential_filtered` | 200 | credential-shaped text refused before storage | drop the segment (final) |
| `archive_disabled` | 409 | the owner's archive is off; nothing stored | do not claim saved; show archive off |
| `event_id_conflict` | 409 | same `event_id`, different text; never overwritten | treat as a client bug |
| `audio_locality_refused` | 403 | host is not a registered home host | do not retry elsewhere |
| `runtime_disabled` | 503 | feature flag off on this host | not retryable until configured |
| `stt_provider_not_local` | 403 | the configured STT provider is not `local` | fix the configuration; do not retry |
| `stt_unavailable` / `stt_failed` / `persist_failed` | 503 / 502 / 503 | not persisted | **retry with the same `event_id`** |

## Retention dimensions

1. **Transcript archive** — this runtime (`transcript_archive`, `transcript_retention_mode` finite or permanent, bounded purge on every ingest while finite).
2. **Conversation/session history** — `history_mode` on `/misumi/respond`.
3. **Semantic-memory promotion** — `retention_mode` on `/misumi/respond`. This includes consultation capsules and handoffs: they follow `retention_mode` alone and are never written merely because history is on.
4. **Artifact creation** — `retention_mode` on `/misumi/respond`.
5. **Raw audio** — never retained by the server; clients may hold it only until a `persisted` ack. The local transcriber's transient file lives in a dedicated directory (`ODYSSEUS_STT_TMP_DIR`, default `data/stt-tmp`); anything older than ten minutes is removed at start-up and before every local transcription, so a killed process cannot leave household audio behind.

### The `/misumi/respond` coupling fix

`should_persist` used to be `persist_turn and retention_mode == "auto"`, so turning semantic memory off silently turned ordinary history off. `history_mode` (`"auto"`/`"off"`) is now an independent control. `persist_turn: false` stays the true incognito switch. When a caller **omits** `history_mode` the historical coupling is kept deliberately: clients written before the split send `retention_mode: "off"` to mean "store nothing", and reinterpreting that would make a client that believes it is private start saving history. New clients send `history_mode` explicitly. The response carries `history_persisted`.

## Compatibility with the deployed interface-box ambient store

The interface box already runs a ratified (2026-07-20) text-only ambient store (finite 14-day window, credential filter, persistent hard-mute, visible listening banner) and a home scheduled task `MisumiTranscriptPull` that copies completed day files to `E:\AI\misumi-transcripts\`. This runtime coexists with it and does not replace it in one step:

- **Stage A (this change):** `scripts/misumi_transcript_import.py` reads completed day files and posts them to `/misumi/transcript/import`. Box records carry no id, so the importer derives a deterministic `event_id` (`sha256` of box id, timestamp, source, persona, duration and text); re-importing never duplicates. Records older than the retention window are skipped and counted, and credential-shaped lines are refused again on ingest. Nothing on the box changes.
- **Stage B (next):** the box forwards each stored window to `POST /misumi/transcript/events` with an `event_id`; the nightly pull stays as a reconciliation backstop.
- **Stage C:** retire the pull once forward and pull agree for a period, and purge `E:` under policy. (`E:` currently has **no purge**; a day file from 2026-07-21 is still held there.)

Properties that hold throughout: ambient never sends audio, mute stays enforced at the box, the credential filter runs on the box and again on ingest, and retention stays bounded in every store except the authoritative Odysseus transcript archive, whose owner policy may be permanent (the box's local recovery copy stays at 7 days maximum and raw audio never persists).

## Failure semantics

Empty/no-speech audio, STT unavailable, STT error, commit failure (never acknowledged; the retry with the same `event_id` succeeds), duplicate retry, concurrent duplicate insert (resolved by the unique constraint), backend restart (row survives; client retries), owner mismatch (404, no leak), oversize audio (`ODYSSEUS_STT_MAX_AUDIO_BYTES`), and "persisted but assistant dispatch failed" (the row stays visible; wake/linkage is attached separately).

## Tests

`tests/test_misumi_transcripts.py` (21) and `tests/test_misumi_history_decoupling.py` (5): retry idempotency (and STT skipped on retry), same-id/different-text conflict, concurrent duplicate race, owner isolation, restart durability, commit-before-ack ordering, commit failure never acknowledged, archive-off honesty, runtime disabled by default, finite retention enforced on ingest, physical host attribution, home-only audio locality (including the default fail-closed rules), STT unavailable never falls back, no raw audio written, no-speech, credential refusal, bounded pagination/export, wake after persistence, importer idempotency/expiry/filtering, additive migration over existing rows, and the history/semantic decoupling including legacy behaviour.

## Not in scope here

A capture daemon; a lab replica or automatic failover; any raw-audio archive; Git storage of transcripts; moving STT onto an estate worker (the audio endpoint uses the instance's own STT service on the home host); the box-side forwarder (stage B). Home worker qualification (Stage 8) is tracked separately.

## Credential filter limits

The filter (ported from the interface box, then broadened after retrospective review to catch phrasing such as "the wifi key is ..." and "the door code is 4821") is deliberately blunt and is **not a guarantee**: spelled-out digits and indirect references are not caught. Ambient retention therefore stays finite and the box filters first.

## Known gap (tracked)

The Stage 6 estate-execution columns (PR #44) are migrated only for SQLite. An existing PostgreSQL deployment would need an explicit migration before the write lane is used there; every current deployment is SQLite. Tracked as `2026-10-01-postgres-estate-migration`.

## PostgreSQL

SQLite is the supported deployment database. PostgreSQL is **not yet a supported general target**; what has been
built and tested against a real PostgreSQL 16 schema is narrow:

- A **fresh** PostgreSQL database: `init_db()` runs twice without error and `create_all` builds every table,
  including `misumi_transcript_events` and `misumi_retention_policy`.
- The **Stage 6 estate-execution migration** (`_migrate_add_estate_execution_worker_columns_postgresql`): an
  existing pre-Stage-6 schema gains the seven worker columns (`ADD COLUMN IF NOT EXISTS`), the `legacy_closed`
  backfill, the `worktree_resolution` index, and both replaced partial unique indexes. It is additive and
  re-runnable (idempotence is recorded as a comment on each index carrying the predicate it was built with, because
  PostgreSQL normalises stored predicates and text comparison is unreliable). `create_all` alone never does this: it
  only creates missing tables.
  Tests: `tests/test_estate_stage6_pg.py`, skipped unless `ODYSSEUS_TEST_POSTGRES_URL` names a throwaway PostgreSQL
  (each test uses its own schema). They also drive the write lane (create, admission control, update, recovery read,
  lease serialisation with `SELECT ... FOR UPDATE`) through the migrated tables.

Not PostgreSQL-ready: the older `_migrate_*` helpers that read `PRAGMA table_info(...)` (session, folder, token and
similar columns) are SQLite-only and only log a warning on PostgreSQL, so an *existing* PostgreSQL database that
predates those columns would still lack them; and the BBC store (`src/bbc/store.py`) uses SQLite directly. Treat a
PostgreSQL move as a separate project until those are ported and tested the same way.

## Permanent transcript retention

Whether accepted transcript text expires is an **explicit policy state**, not a number: `transcript_retention_mode` is
`finite` (the default; the day window applies exactly as before) or `permanent`. A huge day count is deliberately not
how "forever" is expressed, and the 1–90 day clamp for the finite window is unchanged.

In `permanent` mode, for that owner only:

- no accepted row expires: read-time filtering is off, the purge removes nothing (`POST /purge` returns
  `removed: 0`), and query, direct lookup, export, the duplicate pre-check and the box-file importer all see every row;
- `transcript_retention_days` is reported as `null`; the stored window is kept (`transcript_retention_days_if_finite`)
  and is what a later switch back to `finite` uses;
- an unreadable stored mode fails **safe**, as permanent, because deleting text is irreversible.

Safety rails:

- A PUT with only `transcript_retention_days` never changes a permanent archive to finite (the old call shape must not
  silently start deleting).
- Switching `permanent` → `finite` is refused with `409 would_expire_existing_transcripts` (and the count of rows it would
  expire) unless the request carries `confirm_expire_existing: true`. Nothing is changed on refusal. When no existing
  row would expire the switch needs no confirmation.
- Existing finite policies are untouched: the new column is added by an additive, re-runnable migration (SQLite and
  PostgreSQL) with default `finite`.

What permanent does **not** mean:

- Raw audio never becomes permanent. This runtime stores no audio in any mode; `raw_audio_retention` is fixed at `off`.
- Credential-shaped speech is still refused before storage; it is not an "accepted transcript row".
- Semantic memory is separate (`retention_mode` on `/misumi/respond`) and is not promoted from transcript rows.
- The interface box's recovery copy stays bounded at 7 days maximum, and an owner whose archive is switched off stores
  nothing.

### The guarantee, stated accurately

- Once transcript text is durably committed under a permanent archive policy, it does not expire.
- While home is unavailable, raw audio is buffered **only** in the interface box's bounded client outbox (100 items,
  40 MB, 24 hours). An outage longer than that window can cost segments, and the loss is recorded visibly (a durable
  ledger entry and an `ERROR` archive state), never turned into indefinite raw-audio retention.
- The outbox is therefore **not** lossless indefinite storage, and must not be described as such.

## Backup and restore drill

`tests/test_misumi_transcript_backup_restore_drill.py` drives the existing `scripts/odysseus-backup` (snapshot, verify,
restore) against a disposable file-backed archive. It adds no store, tool or mechanism. On every run it proves:

- snapshot, destroy the live database, restore: every row comes back identical in every column (including `seq` and the
  timestamps), with the same per-owner counts, the retention policies and a passing SQLite integrity check;
- replaying every event id after a restore deduplicates and changes nothing; a same-id/different-text event is still
  refused; the database's unique key still rejects a raw duplicate insert;
- a `permanent` policy and a 400-day-old row survive a restore and a purge removes nothing, and a days-only policy change
  does not turn the restored archive into a deleting one;
- the **recovery point** is the snapshot: a write made after it is not recovered by the restore, the previous `data/` is
  stashed as `data.before-restore-<timestamp>` for rollback, and the client's replay of the lost event persists it exactly
  once.

Mutation-checked: a snapshot that omits `app.db`, a retention rule that ignores `permanent`, and a restore that stops
stashing the previous data each fail the matching tests.

What it does **not** establish, stated plainly:

- **No scheduled snapshot exists on the home host** (checked 2026-10-02 by listing its scheduled tasks and the known backup
  locations). The only copies of the household database are one-off `app.db` backups taken by hand before each deployment
  cutover, on the same disk. For a `permanent` archive the effective recovery point is therefore the last manual copy, and
  the interface box's outbox (100 items, 40 MB, 24 hours) cannot cover more than a day of that gap.
- A snapshot contains household speech and the Fernet key, so where an off-host copy goes, and whether it is encrypted, is
  a privacy decision for the operator, not something to automate silently. Tracked in the Misumi card
  `backup-and-restore-memory-store`.
- Restore onto a different release or host, the household runtime's other stores (memory vectors, RAG indexes), the path
  by which Misumi Git facts outrank a contradicting transcript, and any failover. There is no failover by design: lab is
  never a second writer.
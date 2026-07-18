# BBC Odysseus v1 runtime

BBC v1 is an additive authenticated runtime at `/api/bbc/v1`. The browser-native live-data shell is `/bbc`.

## Repository configuration

Configure repository roots in the server process only:

- `BBC_ODYSSEUS_ROOT` defaults to the running Odysseus checkout;
- `BBC_MISUMI_ROOT` points to the Misumi/homeBase Git root;
- `BBC_OBSIDIAN_PHD_ROOT` points to the Obsidian-PhD Git root.

`MISUMI_HOUSEHOLD_ROOT` and `MISUMI_SOURCE_ROOT` remain compatible fallbacks for the Misumi adapter. Roots must be Git repositories. Requests select only a stable repository ID; no request accepts an absolute root.

The adapters are read-only and confined to their authoritative work surfaces:

- Odysseus: `ROADMAP.md`;
- Misumi/homeBase: `agent-tasks/**/*.md`;
- Obsidian-PhD: front-matter `artifact_type: work-item` files under `10-inbox`, with `10-inbox/backlog.md` retained as an index source.

Repository `GET` routes are live, read-only projections and never append canonical events. `POST /api/bbc/v1/repositories/{repository_id}/refresh` is the explicit `bbc:write` ingestion boundary. It merges retained provenance, ingests the system, streams, and nodes, and archives removed source nodes in one SQLite transaction. Historical nodes appear only after that explicit ingestion has recorded their removal.

## Authentication

Browser sessions use the existing Odysseus authentication middleware. Bearer tokens require `bbc:read`, `bbc:invoke`, or `bbc:write`; the `bbc_ship` token profile grants all three. Capability invocation remains separately scoped from navigation-state writes.

## State and audit

The migrated SQLite database is `ODYSSEUS_DATA_DIR/bbc/v1.db`. Canonical entity state is mutable by versioned upsert. State events and audit events are append-only, hash-chained, and protected by SQLite update/delete triggers. Canonical reads, writes, health checks, and restores verify each state hash, latest immutable event, and entity coverage. Restore first snapshots and validates the candidate database's schema, migration ledger, immutable triggers, hash chains, and canonical state; rejection leaves the live database unchanged and a post-copy failure restores the pre-restore snapshot. The shared `bbc.repository.inspect` capability is bounded, network-free, repository-authorised, and emits a real audit event for success, failure, or denial.

Navigation uses `POST /navigation-transactions` followed by versioned `PATCH /navigation-transactions/{id}` commands. The plan records the authenticated actor separately from the moving `persona_id`; only authored rooms are accepted, and omitted paths use the deterministic shortest route through the stable one-deck adjacency graph. Supplied paths must be continuous, non-repeating, and begin/end at the declared rooms.

Every transition supplies `expected_version`. `planned` can enter `in_progress` or be interrupted; `in_progress` can complete or be interrupted; terminal states cannot change. An identical retry at the current or immediately preceding version returns the committed state without adding events; other stale commands receive HTTP 409 and must reload canonical state. Start keeps the persona at the origin with the transaction attached. Only completion changes the persona room and `ship.active_room_id`; interruption preserves the prior room. Transaction, location, ship, state-event, and audit writes commit atomically in one SQLite `BEGIN IMMEDIATE` transaction. SQLite serialises runtime instances and local processes sharing the database file; the database must not be placed on a network filesystem.

`POST /navigation-intents` is read-only resolution for typed or voice commands. It resolves rooms, current persona locations, repository systems, and live work-node aliases, returns confidence-aware clarification when needed, and never creates a movement transaction. Clients create the returned room movement explicitly.

`POST /room-conferences` executes one bounded, structured conference in the ship's active room. The caller supplies the objective and may bind it to one canonical repository work node; the server derives visible occupants from canonical persona locations and selects no more than two task-relevant visitors from the read-only HomeBase persona projection. An optional completed navigation transaction binds the conference idempotently to one real arrival. Callers cannot choose attendees or transition conference state. Repository-bound conferences require both `bbc:write` and `bbc:invoke` scopes.

Execution stages a compact memory pointer, bounded summary, and exact evidence retrieved through `bbc.repository.inspect`. Each participant has an explicit role, focus, context pointer, and output contract. The result contains concise findings, disagreement, uncertainty, proposed actions, and deduplicated provenance; `actions_executed` remains false because a conference does not mutate its source repositories. Planned, running, completed, and failed state is retained for recovery. Memory pointers, the retrieval packet, the completed result, state events, and execution audit commit atomically; dependency and commit failures remain visible as failed conferences without a false completion record.

`GET /room-conferences` accepts optional `room_id`, `state`, and `limit` filters. Results are newest first and bounded to 20 by default or 100 maximum so clients can restore the latest room context without loading conference history wholesale.

Difficulty colour has one meaning: green is low, orange is medium, and red is high. Workflow state is rendered separately by node shape and label. The score stores its version, component values, weights, and explanation.

When an alias such as `S2-E1` matches multiple executable work artifacts, the resolver returns `ambiguous` with every candidate and provenance. It returns a canonical node only when exactly one non-archived authoritative artifact matches.

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

## Authentication

Browser sessions use the existing Odysseus authentication middleware. Bearer tokens require `bbc:read`, `bbc:invoke`, or `bbc:write`; the `bbc_ship` token profile grants all three. Capability invocation remains separately scoped from navigation-state writes.

## State and audit

The migrated SQLite database is `ODYSSEUS_DATA_DIR/bbc/v1.db`. Canonical entity state is mutable by versioned upsert. State events and audit events are append-only, hash-chained, and protected by SQLite update/delete triggers. The shared `bbc.repository.inspect` capability is bounded, network-free, repository-authorised, and emits a real audit event for success, failure, or denial.

Difficulty colour has one meaning: green is low, orange is medium, and red is high. Workflow state is rendered separately by node shape and label. The score stores its version, component values, weights, and explanation.

When an alias such as `S2-E1` matches multiple executable work artifacts, the resolver returns `ambiguous` with every candidate and provenance. It returns a canonical node only when exactly one non-archived authoritative artifact matches.

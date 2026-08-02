# Procedural Capability Graph — implementation plan

Status: implementation plan for `feat/procedural-capability-graph-20260802`.
Owner repository: `tyecam1/odysseus` (runtime infrastructure).
Consumers: `tyecam1/obsidian-PhD` (research overlay), `tyecam1/misumi`
(household/persona overlay).

## Why this lives here

Odysseus owns reusable runtime infrastructure: routing, context construction,
permissions, run traces, persona-profile loading. The capability graph is the
routing substrate those need. It must **not** be reimplemented inside the vault
or Misumi; those repositories contribute *overlays* only.

## Non-goals (hard)

- No Graphiti, Neo4j, or any external graph service. A measured failure of this
  implementation against a stated requirement is the only thing that reopens
  that question.
- No new authority store. The graph is **derived**; every node and edge must
  carry provenance pointing at a source file in a source repository. If the
  source is gone or changed, the derived output is stale and must be refused,
  not silently served.
- No storage of hidden reasoning or chain-of-thought on nodes.
- Overlays do not gain write authority by being in the graph.

## Model

### Node types

`intent`, `task_class`, `repository`, `authority`, `precondition`,
`context_source`, `skill`, `model_profile`, `tool`, `permission`, `action`,
`artifact`, `validator`, `failure_mode`, `fallback`, `escalation`,
`human_gate`, `outcome`, `evaluation_case`.

### Edge types

`routes_to`, `requires`, `reads`, `may_write`, `forbids`, `uses_skill`,
`uses_model`, `uses_tool`, `validated_by`, `falls_back_to`, `escalates_to`,
`derived_from`, `supersedes`, `blocked_by`, `produces`.

### Provenance (required on every node and edge)

```
source_repo, source_path, source_revision, source_sha256,
extracted_at, adapter_name, adapter_version
```

A node or edge without complete provenance must fail the build, not be
emitted with blanks.

## Storage and build

- Versioned SQLite at a configurable path, plus a deterministic JSON export.
- Schema version constant; a build against a mismatched schema fails closed.
- **Determinism requirement**: two builds over identical sources produce
  byte-identical JSON export. Sort every collection; no dict-order or
  timestamp leakage into the export body (`generated_at` goes in a sidecar
  metadata block that is excluded from the determinism hash).
- NetworkX (already an acceptable small dependency) for cycle and reachability
  analysis. Do not add a graph server.

## Source adapters

Each adapter is deterministic, read-only, and declares which node/edge types it
may emit. Adapters must fail closed on a malformed source rather than skipping
it silently — a skipped source is a hole in the routing table.

Ship at minimum:

1. `repo_contract_adapter` — parses agent/operating contract markdown
   (`AGENTS.md`-family files) into `repository`, `authority`, `permission`,
   `human_gate` nodes and `forbids` / `may_write` / `reads` edges.
2. `agent_task_adapter` — parses agent-task packets (schema v1 and v2) into
   `task_class`, `action`, `validator`, `artifact` nodes and
   `routes_to` / `validated_by` / `produces` edges.
3. `skill_adapter` — parses skill definitions (`SKILL.md` frontmatter) into
   `skill` nodes with their declared `allowed-tools` as `uses_tool` edges.
4. `model_policy_adapter` — parses routing/model-execution policy YAML into
   `model_profile` nodes and `uses_model` edges.

Adapters take a source root as an argument. They must work against a checkout
of a *different* repository, because the overlays live elsewhere.

## Freshness

- Every source file's `sha256` is recorded at build time.
- `graph check --sources <root>` recomputes hashes and reports each source as
  `current`, `changed`, or `missing`.
- Any `changed` or `missing` source marks the whole graph `stale`.
- **Query commands must refuse to answer from a stale graph** unless
  `--allow-stale` is passed, and when it is passed every answer is labelled
  `stale`. Staleness must be structurally unrepresentable as freshness.

## Authority-conflict detection

Build fails visibly when:

- a `may_write` edge targets a path also covered by a `forbids` edge for the
  same actor (report both provenance records);
- a cycle exists in `routes_to` or `escalates_to`;
- a `human_gate` node is reachable by an `action` that has no `escalates_to`
  path to it;
- two adapters emit the same node id with different attribute values.

Conflicts are errors, not warnings. Exit non-zero.

## CLI

```
odysseus-graph build   --sources <root>... --out <db>
odysseus-graph check   --db <db> --sources <root>...
odysseus-graph query   --db <db> <question> [--json]
odysseus-graph export  --db <db> --out <json>
odysseus-graph explain --db <db> --route <route-id>
```

`query` must answer these eleven questions, each as a named query with a
stable output shape:

1. What should handle this request?
2. Which repository owns it?
3. What must be read first?
4. Which model, skill and tool are appropriate?
5. Which permissions are required?
6. What may be written?
7. Which validator proves completion?
8. What fallback applies?
9. Which human decision is required?
10. Why was this route selected? (the provenance chain, not a rationale string)
11. Is the route current, superseded or blocked?

Question 10 must return the actual edge path with each edge's provenance. A
prose justification is not an acceptable answer.

## Evaluation

- A held-out set of evaluation cases, stored separately from the cases used
  while developing the queries.
- Each case: input question, expected answer shape, expected route id or
  expected refusal.
- **A case must be able to expect a refusal** (unroutable / blocked / stale),
  and the harness must fail if the graph answers a case that should refuse.
- The harness must not be able to read the graph's own confidence as evidence.

## Tests that must exist

- determinism: two builds → identical export bytes;
- provenance completeness: a node missing any provenance field fails the build;
- freshness: mutate a source file → `check` reports `changed` → `query`
  refuses without `--allow-stale`, and labels output `stale` with it;
- authority conflict: a fixture with overlapping `may_write`/`forbids` fails
  the build with both provenance records in the message;
- cycle detection: a `routes_to` cycle fails the build;
- duplicate node id with differing attributes fails the build;
- adapter fail-closed: a malformed source raises, and does not silently emit
  zero nodes;
- held-out evaluation cases pass, including at least two refusal cases;
- empty source root produces an explicit `no-sources` error, never an empty
  graph that reports success.

## Adversarial properties the verifier will attack

- Can a stale graph render as current?
- Can an empty or failed adapter run look like "this repository has no
  permissions"?
- Can a node be emitted with partial provenance?
- Can `explain` return a plausible route that no edge path supports?
- Can the evaluation harness pass by the graph supplying its own expectations?
- Can a zero node count mean "not computed"?

## Overlays (separate follow-up tasks, not this change)

- obsidian-PhD overlay: research tasks, evidence, literature, experiments,
  writing.
- misumi overlay: personas, household intents, permissions, escalation.

This change ships the generic core plus the adapters and must demonstrate the
core building against at least one real external source root.

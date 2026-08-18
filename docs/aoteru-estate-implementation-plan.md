---
title: Aoteru estate implementation plan
status: target-plan
owner: odysseus
as_of: 2026-08-19
scope: operator access, memory, routing, repos, models, mobile, two-PC execution
---

# Aoteru estate implementation plan

## 0. Goal

Create one persistent assistant, **Aoteru**, reachable from laptop or phone, that can find the relevant memory, repository, machine, tool and model for a request, execute on exactly one controlled work seat, verify the result, and return it through the same conversation surface.

Target request path:

```text
user -> Aoteru -> memory/context -> authority/repo -> execution route -> parked host/worktree
     -> tool/model -> verification -> durable result -> memory candidate -> response
```

This plan is the canonical cross-estate implementation sequence. Domain repositories retain authority for their own content and rules.

## 1. Non-negotiable invariants

1. **Identity:** Aoteru persona truth remains in `tyecam1/misumi`; model identity never replaces persona identity.
2. **Runtime:** Odysseus owns domain-neutral estate discovery, memory broker, routing transport, jobs, model/service discovery and parking leases.
3. **Domain truth:** `obsidian-PhD`, Misumi/household and other repos remain authoritative for their own knowledge, permissions and workflows.
4. **Single writer:** repo mutation occurs only on the active parking lease/worktree. No active-active editing of one branch across machines.
5. **Memory:** personal memory stores source-linked facts, preferences, decisions, episodes, open loops and authority pointers; it does not duplicate whole repositories as truth.
6. **Network:** no public model, MCP, shell or control ports. Use private authenticated transport only.
7. **Routing:** deterministic/local routes precede paid inference when quality and verification requirements permit.
8. **Safety:** domain gates remain binding. Persona, memory, MCP or remote access never widens write authority.
9. **Failure truth:** the system never claims completion when no viable route exists. Temporary failures create a durable retry/blocked record with the exact missing dependency.
10. **Token economy:** always-loaded Claude context is minimal; live state is retrieved only when needed.

## 2. Canonical ownership and locations

| Item | Canonical owner | Runtime/data location |
|---|---|---|
| Aoteru persona/behaviour | `misumi` | loaded through broker/bootstrap |
| Estate map, host/service/repo registry | `odysseus` | Git config + live host inventory |
| Parking/lease/job state | `odysseus` | Odysseus SQLite |
| Personal memory structured state | `odysseus` broker | home Odysseus data dir, SQLite |
| Memory semantic index | derived | existing ChromaDB, rebuildable |
| Memory source archive/import queue | derived/runtime data | home data dir; backup to lab |
| PhD knowledge, trust, research skills | `obsidian-PhD` | Git-managed clones |
| Household knowledge/persona policy | `misumi` | Git-managed clone |
| Local model weights | none/Git-excluded | one host-local model store per PC |
| Secrets | none/Git-excluded | host/user secret stores |
| Operator launcher | `odysseus` | installed on laptop + workers |

Do not add Postgres, Mem0, Graphiti or a second orchestrator as baseline dependencies. Odysseus already provides SQLite, ChromaDB, authenticated APIs, jobs and passive Misumi memory. Extend these first. Add graph-specific infrastructure only after a measured retrieval requirement cannot be met by SQLite relationship tables + Chroma.

## 3. Operator bay

Yes: create a **thin Aoteru operator bay**, not a giant knowledge folder.

### 3.1 Laptop bay

Install a generated local directory, not a new source-of-truth repo:

```text
~/.aoteru/
  config.local.json        # host-local paths/secrets references only
  estate-cache.json        # generated live cache; disposable
  logs/
~/aoteru-bay/
  CLAUDE.md                # <30 lines; generated bootstrap
```

The canonical templates/code live in Odysseus. `agent sync` regenerates the bay from the Odysseus estate registry and live services.

The bay CLAUDE.md contains only:

- speaking identity = Aoteru;
- use user-scoped `estate-control` and `aoteru-memory` MCPs for live state;
- obey the selected repo's own instructions and permissions;
- never infer host/path/model from stale prose;
- use `agent park` before mutation.

Never embed the full estate map in CLAUDE.md. Claude Code loads parent/user instructions every session, so large maps waste context and drift.

### 3.2 Worker workspace roots

On both PCs:

```text
<AI_ROOT>/workspace/
  CLAUDE.md                # generated estate bootstrap, <30 lines
  odysseus/
  misumi/
  obsidian-PhD/
  <other registered repos>/
```

Claude Code launched inside a child repo inherits the workspace bootstrap and then the repo-specific CLAUDE.md/rules. Repos may exist on only one host if required; the registry records this.

### 3.3 User-wide Claude bootstrap

Each machine's `~/.claude/CLAUDE.md` gets only a tiny Aoteru pointer so Aoteru remains the speaking identity even outside managed repos. No persona corpus or system map is copied there.

## 4. Estate registry

Add to Odysseus:

```text
config/estate.yaml         # logical hosts/services and domain permissions
config/repositories.yaml   # repo IDs, remotes, authority, host clone variables
config/models.yaml         # capability aliases, not permanent model brands
config/memory-sources.yaml # allowed import sources and domain/sensitivity rules
```

No secrets or physical user-specific paths in Git. Host-local environment resolves variables such as `AI_ROOT`, `PHD_ROOT`, `HOUSEHOLD_ROOT`.

Each worker publishes live machine-readable inventory:

```text
host_id, OS, CPU, GPU, VRAM, RAM, free_fast_storage,
runtimes, model_tags, context_limits, measured_tokens_s,
current_load, registered_repo_clones, service_health
```

`agent status` is generated from live inventory, not documentation.

## 5. Networking and stable access

Use Tailscale if permitted on all devices.

1. Join laptop, phone, lab PC and home PC to one tailnet.
2. Enable MagicDNS.
3. Use **Grants** with deny-by-default least privilege.
4. Keep Odysseus/Ollama/MCP services loopback-bound where practical.
5. Publish only required loopback services privately using Tailscale Serve/Services.
6. Define stable services rather than host IPs:

```text
svc:aoteru        # authenticated Aoteru/Odysseus front door; home + lab backends
svc:memory        # broker API; home primary, lab read-cache fallback
svc:models-lab
svc:models-home
svc:odysseus-lab
svc:odysseus-home
```

7. Normal Windows OpenSSH over the tailnet is the management/parking transport.
8. No router port forwarding or Funnel/public exposure.

If university policy blocks Tailscale, keep the same logical service contract and substitute the approved private VPN/SSH path. Do not change application ownership to work around network policy.

## 6. Aoteru memory broker

### 6.1 Reuse first

Extend the existing `src/misumi_memory.py` capsule/open-loop/handoff model rather than replace it. Preserve import compatibility for existing JSONL memory.

### 6.2 Durable model

Move cross-domain structured memory into Odysseus SQLite tables while keeping raw/import source references immutable. Minimum objects:

- `source_event`: source, external ID, timestamp, content hash/pointer, domain, sensitivity;
- `memory`: typed distilled memory, confidence, status, source_event IDs;
- `relation`: typed source-linked relation between memories/entities;
- `open_loop`: owner/domain/status/due/reference;
- `memory_revision`: correction/supersession history;
- `memory_outbox`: events accepted while the primary memory leader is unavailable.

Memory types: `identity`, `preference`, `goal`, `decision`, `open_loop`, `procedure`, `relationship`, `episode`, `project_context`, `resource_pointer`, `correction`.

### 6.3 Semantic index

Use existing ChromaDB only as a derived index of approved memory summaries/source pointers. It is rebuildable from SQLite and never authoritative.

### 6.4 Graph

Start with the SQLite `relation` table plus temporal/source fields. Add a dedicated graph engine only if benchmarked queries require traversal/temporal behaviour that this cannot provide.

### 6.5 Physical authority/failover

- Home PC: primary memory writer and complete data store.
- Lab PC: encrypted periodic snapshot/read cache.
- If home is unavailable: Aoteru reads the latest lab snapshot and appends new memory candidates to a local outbox; it does not create an independent canonical memory fork.
- When home returns: replay idempotent outbox events by stable UUID/hash.

### 6.6 Sources

Supported ingest adapters, each incremental by stable source ID/hash:

- existing Misumi capsules;
- Claude Code transcript/session hook events;
- ChatGPT official data export;
- Codex task/session artifacts where exportable;
- registered repo commit/task/log pointers;
- explicit user capture/import;
- centralised external-knowledge ingestion outputs.

Do not index entire PCs. Only registered repos and allowlisted roots are searchable.

## 7. Claude Code integration

### 7.1 User-scoped MCPs

Expose two domain-neutral user-scoped MCPs:

`estate-control`:
- `estate_status`
- `repo_resolve`
- `park`
- `where`
- `list_models`
- `dispatch_job`
- `job_status`
- `fetch_result`
- `release`

`aoteru-memory`:
- `memory_recall`
- `memory_search`
- `open_loops`
- `memory_capture_candidate`
- `source_trace`

Neither directly implements PhD or household business logic.

### 7.2 Project MCPs

Keep domain MCPs project-scoped:

- `obsidian-PhD`: governed PhD engine + Zotero/Beaver where authorised;
- Misumi: household-only capabilities;
- other repos: their own project tools.

No global Zotero/PhD MCP and no global household-memory tool exposure.

### 7.3 Hooks

Use hooks for deterministic lifecycle integration:

- `SessionStart`: resolve repo/host/lease, Aoteru identity version, bounded core memory and relevant open loops; inject only concise context.
- `UserPromptSubmit`: cheap intent/entity test; query deeper memory only when useful.
- `PostCompact`: record a session episode candidate, not durable fact memory.
- `SessionEnd`/`Stop`: enqueue local extraction of decisions/preferences/corrections/open loops and result pointers.
- `PreToolUse`: enforce parking/write authority for cross-repo or remote mutation.
- `PostToolUse`: append auditable result/change metadata where required.

Local models perform routine memory extraction; paid Claude is not on the critical memory path.

## 8. Parking and repo access

`agent park` is the only normal route to mutable repo work.

```text
agent park obsidian-phd            # auto host
agent park obsidian-phd --host lab
agent park misumi --host home
agent where
agent release
```

Parking algorithm:

1. Resolve repo from registry.
2. Discover healthy hosts with a registered clone and required credentials/tools.
3. Prefer data locality, host role, load and model fit.
4. Inspect current lease and target clone Git state.
5. If switching host: require source clone clean + pushed, or create a named WIP branch/commit under explicit policy.
6. ff-only sync target clone.
7. Acquire lease: `{repo, host, worktree, branch, session, allowed_write_scope, heartbeat}`.
8. Start executor inside that worktree.
9. Renew heartbeat during work.
10. On completion, record result/branch/verification; release lease unless session remains active.

If a repo is registered but missing on the selected host, clone it only when credentials/policy permit. Otherwise route to a host where it already exists.

Read-only global search does not require parking. Mutation does.

## 9. Model/runtime plane

Use Ollama first because it already fits the estate and exposes Claude Code-compatible local model access. Keep serving implementation replaceable behind capability aliases.

Stable aliases:

```text
general-fast
general-strong
code-fast
code-strong
reasoning-strong
vision
embedding
reranker
```

Initial benchmark candidates, not locked defaults:

- `Qwen3.6-35B-A3B`: primary general/agent candidate; Ollama Q4 ~24 GB, 256K class context, agentic coding + vision.
- `Qwen3.6-27B`: lower-memory dense comparison; Ollama Q4 ~17 GB.
- `GLM-4.7-Flash 30B-A3B`: efficient general/agent comparison where supported.
- `Devstral Small 2 24B`: efficient coding candidate.
- `GPT-OSS 20B` or current comparable: fast fallback.
- `Qwen3-Coder-Next`: benchmark only if host memory/throughput makes its ~52 GB Q4 practical.

Before selection, inventory both PCs and benchmark actual estate tasks at 32K and 64K minimum practical context. Record quality, tool success, structured output success, prefill/decode speed, peak VRAM/RAM, load time and thermal stability.

Routing resolves capabilities to live host/model. Domain skills request capability classes, not model brands.

Paid escalation order is task-specific:

```text
deterministic -> local-fast -> local-strong -> Claude/Codex -> human gate
```

Use the second PC for coarse-grained parallel verification/batch work, not cross-WAN tensor parallelism.

## 10. Laptop and mobile entry surfaces

### 10.1 `agent` launcher

Install one CLI from Odysseus:

```text
agent                    # Aoteru bay status/front door
agent ask "..."          # local-first Aoteru request
agent status
agent park <repo> [--host]
agent claude [<repo>]     # paid Claude on parked/selected host
agent local [alias] [--host]
agent codex [<repo>]
agent models
agent memory <query>
agent release
```

The launcher never stores domain logic. It calls the same Odysseus APIs/MCP contracts used by mobile and Claude Code.

### 10.2 Laptop normal mode

For repo work, the launcher SSHs to the parked worker and starts Claude Code/Codex in the native repo/worktree. The laptop remains the terminal/controller while filesystem, tests and Git execute next to the repo.

### 10.3 Mobile default

Expose the authenticated Aoteru/Misumi PWA/API through stable private `svc:aoteru`. Mobile requests use the same router, memory and parking system and default to deterministic/local models. No mobile SSH workflow is required for ordinary use.

### 10.4 Mobile paid-Claude escalation

Use Claude Code **Remote Control** when an interactive paid Claude session is explicitly needed. Start the session on the parked worker with its real filesystem/MCP/tools and control it from the Claude mobile app/browser.

Do not make Remote Control the default local-model mobile path: it requires claude.ai authentication and a running Claude Code process. The Odysseus Aoteru surface remains the always-on local-first mobile front door.

## 11. Request resolver and fallback ladder

Every incoming request executes this resolver:

1. Authenticate operator/device.
2. Identify domain, intent, required authority and whether mutation is requested.
3. Retrieve bounded Aoteru memory/open loops.
4. Resolve authoritative repo/source(s).
5. Determine required tools, context, risk and verification.
6. If mutation: acquire parking lease.
7. Select cheapest healthy execution lane meeting requirements.
8. Execute.
9. Verify according to domain policy.
10. Persist result/handoff/source trace.
11. Generate memory candidates asynchronously.
12. Reply through originating surface.

Fallback order:

- preferred host unavailable -> other registered host;
- preferred model unavailable -> compatible alias on either host;
- target clone absent -> permitted clone/bootstrap or existing-host route;
- home memory unavailable -> lab read snapshot + outbox;
- local inference insufficient/fails -> paid lane if available/allowed;
- paid quota/auth unavailable -> strongest local + explicit quality ceiling;
- worker estate unavailable but GitHub/cloud route is authorised -> cloud executor for repo-contained work;
- required credential/human authority absent -> durable blocked task with exact dependency; never fabricate completion.

This is the operational meaning of "find a way": exhaust valid routes, degrade explicitly, and preserve retry state when physical access/authority makes completion impossible.

## 12. Implementation sequence with gates

Do not skip phases. Each phase must pass its gate before the next changes authority or removes a legacy path.

### P0 - Freeze and inventory

Build:
- clean-state/branch/remote inventory for `odysseus`, `misumi`, `obsidian-PhD` and registered repos;
- both-PC hardware/runtime/path/service inventory;
- current capability ownership map: `keep | move | wrap | deprecate`;
- backup of Odysseus data + existing Misumi JSONL memory.

Gate:
- reproducible inventory artifact;
- no unpreserved dirty work;
- restore test for current Odysseus data.

### P1 - Estate registry + operator bay

Build:
- four canonical config registries;
- `agent status/sync/where` read-only commands;
- generated laptop bay and worker workspace CLAUDE bootstrap;
- no mutation/parking yet.

Gate:
- from laptop, both hosts/repos/services resolve by logical ID without hard-coded prompt knowledge;
- CLAUDE bootstrap <30 lines and contains no duplicated system map.

### P2 - Private connectivity

Build:
- tailnet/VPN, stable names, Grants, Serve/Services;
- SSH management path;
- private Aoteru/Odysseus endpoints.

Gate:
- laptop + phone reach authenticated `svc:aoteru` from outside home LAN;
- raw services are not publicly reachable;
- access-control tests deny unapproved cross-domain paths.

### P3 - Parking + remote native execution

Build:
- lease tables/API;
- repo state checks, clone mapping, ff-only sync, WIP preservation;
- `agent park/release`;
- SSH launch into parked worktree.

Gate:
- same repo cannot acquire conflicting write leases;
- dirty/split-brain tests fail closed;
- laptop can park and run tests on either PC without knowing paths.

### P4 - Central Aoteru memory

Build:
- SQLite source/memory/relation/revision/open-loop/outbox schema;
- migration adapter from existing Misumi JSONL;
- Chroma derived index;
- broker API/MCP;
- home primary + lab snapshot/outbox failover.

Gate:
- existing Misumi memory survives round-trip migration;
- provenance trace returns original source IDs;
- correction supersedes rather than silently overwrites;
- lab degraded mode works with home offline and replays idempotently.

### P5 - Claude Code/Codex integration

Build:
- user-scoped estate + memory MCPs;
- minimal user/workspace bootstrap;
- lifecycle hooks;
- direct Claude/local/Codex launcher modes.

Gate:
- Aoteru identity is stable across three engines;
- repo instructions override estate convenience without conflict;
- local path consumes no Claude/OpenAI inference merely to dispatch;
- hook failures degrade without losing the user's prompt/task.

### P6 - Mobile universal access

Build:
- Aoteru mobile/PWA estate dispatch;
- job/status/result view;
- optional Claude Remote Control escalation launcher/session link.

Gate:
- from phone on cellular: ask, route, execute read task, execute approved parked repo task, inspect result;
- phone never needs repo paths/SSH/model names.

### P7 - Model benchmark + cost router

Build:
- representative benchmark corpus from real PhD, coding, memory and Misumi work;
- benchmark candidates on both PCs;
- alias mappings + routing policy;
- provider/host/usage log.

Gate:
- defaults are evidence-based per host/task;
- local-first does not weaken required verification;
- second-host verification works independently.

### P8 - Domain convergence

Build:
- move neutral host/model/dispatch concerns out of `obsidian-PhD` into Odysseus;
- change PhD skills/routes to capability requirements;
- retain PhD trust/write/verification logic in PhD repo;
- retain persona/household policy in Misumi;
- point old architecture notes to this canonical plan.

Gate:
- no duplicated router/task authority;
- capability truth/tests pass in all three repos;
- old single-compute-box assumptions are either removed or explicitly historical.

### P9 - Fault, security and cutover validation

Test at minimum:
- home off;
- lab off;
- laptop off during queued job;
- phone only;
- target repo dirty on other host;
- model OOM/unavailable;
- memory primary unavailable;
- subscription exhausted;
- Tailscale/VPN unavailable;
- stale clone;
- bad credential;
- malicious/untrusted imported memory text;
- cross-domain access attempt;
- reboot both workers separately.

Gate:
- every case either completes through a valid fallback or returns a precise durable blocked state;
- no data loss, split-brain, public exposure or authority bypass;
- restart restores required services automatically.

### P10 - Cutover

Only after P9:
- make `agent` + Aoteru mobile the normal entry points;
- enable automatic local-first routing;
- archive/supersede redundant config/routes;
- retain rollback snapshots for one release cycle;
- update implementation-truth docs in each repo.

Completion means the acceptance tests below all pass from clean boots.

## 13. Final acceptance tests

1. Laptop: `agent status` discovers both PCs, registered repos, models and health without cloud inference.
2. Laptop: "work on X repo" resolves its location, parks it, opens native execution and preserves repo rules.
3. Laptop: user can switch paid Claude, local model/host and Codex without changing persona or manual endpoints.
4. Phone/cellular: user can ask Aoteru to inspect or complete a permitted task and receive the result from `svc:aoteru`.
5. Phone: explicit paid-Claude escalation can open/control a Claude Remote Control session on the parked worker.
6. Memory: a relevant decision made in one surface is source-traceable and retrievable from another after ingestion.
7. Authority: Aoteru can search across registered sources but cannot mutate an unparked repo or bypass domain gates.
8. Failover: either worker can disappear without corrupting memory/repo/task state; remaining routes continue where technically possible.
9. Cost: routine routing/memory/indexing work stays deterministic/local; paid escalation is recorded and explainable.
10. Recovery: after reboot, services, registry, memory broker, Aoteru surface and worker health return without laptop intervention.

## 14. Explicit non-goals

- one database replacing all repositories;
- copying every repo or conversation into startup context;
- cross-WAN tensor parallelism;
- autonomous bypass of human/domain write gates;
- public endpoints;
- a second orchestration/task system beside Odysseus;
- committing model weights, caches, secrets or personal memory databases to Git;
- adopting new memory/graph frameworks before the existing Odysseus stack fails a measured requirement.

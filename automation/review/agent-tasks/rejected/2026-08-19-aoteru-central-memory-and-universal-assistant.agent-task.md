---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-08-19-aoteru-central-memory-and-universal-assistant
title: "Build Aoteru central memory and universal assistant"
status: rejected
rejection_reason: superseded_by_ratified_adr
priority: low
task_type: architecture-convergence
created_by: migrated-from-obsidian-phd
updated_at: 2026-10-02T18:00:00+01:00
executor: ""
execution_mode: review-first
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
migrated_from_repo: tyecam1/obsidian-PhD
migrated_from_path: 10-inbox/2026-08-19-aoteru-central-memory-and-universal-assistant.md
notes: "Migrated as shared backend/cross-repository work. Original body preserved below; re-ground paths against live Odysseus state before execution."
---

# Build Aoteru central memory and universal assistant

## 2026-10-02 Retirement (Phase 4 ADR ratified; the original body below is preserved as history)

Misumi long-horizon programme, applications `-02` to `-04`. A bounded Opus architecture gate was run against live evidence;
its conclusions are recorded in `docs/memory-architecture.md` in `tyecam1/misumi`, **Ratified by the operator on 2026-10-02**
(Misumi PR #46). The ADR adopts the existing Odysseus runtime memory as the only runtime-memory mechanism and rejects a Mem0
store, a new Memory Broker, an additional MCP memory authority, a lab memory replica and automatic failover.

**This task is retired (status `rejected`, reason `superseded_by_ratified_adr`).** Leaving it at high priority in the inbox
would contradict the ratified decision. The two items below that were genuinely deferred (not obsolete) now have their own
scoped, low-priority owner tasks, so nothing real is lost with this one:

- `2026-10-02-bounded-read-only-session-start-retrieval` (tranche item 6, read-only half only)
- `2026-10-02-chatgpt-export-ingestion-via-memory-sources` (tranche item 7)

The re-grounding evidence follows unchanged.

Evidence that changes the premises: the design document this task cites
(`automation/review/architecture/2026-08-19-aoteru-central-memory-and-agent-fabric.md`) does not exist in the repository;
Odysseus code has no Mem0, no memory broker and no `aoteru-memory` MCP (they appear only in planning documents); the
transcript archive is now a permanent, single-writer store on the home host; the registry, ParkLease, `memory_server.py`,
`memory_provider`, `MemoryRelation` and `source_events` already exist; and a Graphiti-style temporal memory was already
rejected as a second authority.

| Tranche item | Disposition |
| --- | --- |
| 1 Audit | Satisfied by the Phase 4 evidence pass |
| 2 Provenance event schema | Obsolete as a new schema: provenance already lives in `MemoryRelation` (`derived_from`, `supersedes`) and `source_events`; `memories` rows are thin (`category`, `source`, `owner`, `session_id`), and a gap there is closed by extending those owners |
| 3 Memory Broker with an append-only ledger | Obsolete: a second router and store; the transcript archive is the ledger |
| 4 Self-hosted Mem0 pilot | Obsolete: a new store behind a new broker |
| 5 `aoteru-memory` MCP | Obsolete: `mcp_servers/memory_server.py` exists |
| 6 Claude Code lifecycle hooks | **Deferred, now `2026-10-02-bounded-read-only-session-start-retrieval`:** read-only bounded retrieval may be real later; candidate capture would be a second write path and risks crossing the PhD boundary, so it needs a domain-scoping design first |
| 7 Incremental ChatGPT export ingestion | **Deferred, now `2026-10-02-chatgpt-export-ingestion-via-memory-sources`:** a separate ingestion item under `config/memory-sources.yaml`, after an owner privacy decision |
| 8 Repo registry, parking lease, launcher | Satisfied (`config/repositories.yaml`, ParkLease) |
| 9 Benchmark local models | Subordinate to `2026-09-13-operating-contract-model-role-evaluation-system` (PR #62); not memory work |
| 10 Home-primary memory with lab warm replica and read failover | **Rejected:** contradicts the single-writer design and the rule that the lab is never a second writer; replaced by an encrypted verified scheduled backup and a drilled restore with a stated recovery point |

| Acceptance criterion | Disposition |
| --- | --- |
| Park the active session from the laptop; no dual-write from two machines | Satisfied |
| Repository knowledge retrieved from its authority, not copied into memory | Real; delivered through the Misumi `context-portability-hygiene` drift check |
| Identity and bounded memory at Claude Code start in any repository | Partly satisfied (`CLAUDE.md` and `aoteru-estate-routing`); the rest deferred |
| One broker for Claude, Codex and local models; ChatGPT import | Obsolete (broker); deferred (import) |
| Memory read-only from the lab if home is down | Obsolete: replaced by restore within a measured time |
| Local model defaults from measured results; local extraction by default | Owned by the model-role evaluation task |

The obsolete rows are retired by the ratified ADR; the model-benchmark row stays with the model-role evaluation task.

## Goal

Make Aoteru Misumi the persistent operator-facing assistant across Claude Code, Codex and local models while preserving domain authority and enabling secure access to relevant memories, repositories and workers from the laptop.

## Required architecture

Implement the reviewed design in `automation/review/architecture/2026-08-19-aoteru-central-memory-and-agent-fabric.md` unless repo/deployment audit produces evidence requiring amendment.

Key boundaries:

- Aoteru identity/persona truth remains in Misumi.
- Neutral memory broker/runtime, repo registry, parking state and dispatch belong to Odysseus.
- Memory data stays outside Git with home desktop as normal write leader and lab as warm replica/read failover.
- `obsidian-PhD` and other domain repos remain canonical for domain knowledge.
- Claude/Codex/local models share the broker rather than creating model-specific memories.
- global search is allowed subject to policy; filesystem writes happen only through the parked repo/host/worktree.

## First implementation tranche

1. Audit existing memory/persona/session/routing capabilities across all three repos and deployed machines.
2. Define one provenance-bearing memory event schema, memory object schema, namespaces and sensitivity rules.
3. Build a thin Aoteru Memory Broker in Odysseus with an append-only source/event ledger.
4. Pilot self-hosted Mem0 behind that broker using local inference where viable; do not make Mem0 storage the conceptual authority.
5. Add a user-scoped `aoteru-memory` MCP for Claude Code and Codex.
6. Add Claude Code lifecycle hooks for bounded retrieval and candidate-memory capture.
7. Add incremental ChatGPT export ingestion.
8. Add Odysseus repo registry + parking lease and laptop launcher that SSHs Claude Code into the selected remote workspace.
9. Inventory both PCs and benchmark current local models using estate-specific tasks before assigning model aliases.
10. Deploy home-primary memory with encrypted lab replica/read failover and test outage/recovery without split-brain writes.

## Model benchmark minimum

Include at least:

- Qwen3.6-35B-A3B
- GLM-4.7-Flash 30B-A3B
- Devstral Small 2 24B
- Qwen3-Coder-Next if total host memory permits useful throughput
- one smaller reliable fallback model

Benchmark persona adherence, memory use, structured extraction, research tasks, coding/tool use, context scaling, VRAM/RAM, throughput and failure rate.

## Graph decision

Start with Mem0 graph capability where useful. Treat Graphiti core as a later temporal-graph pilot, not a baseline dependency, and expose any adopted graph only through the authenticated Aoteru broker.

## Acceptance criteria

- Claude Code in any registered repo starts with Aoteru identity and bounded relevant memory.
- Aoteru identity is not duplicated across repositories.
- Claude, Codex and local models read/write candidate memory through one broker.
- ChatGPT history can be incrementally imported from official exports with provenance.
- Aoteru can locate any registered repo and park the active session on its appropriate host from the laptop.
- Normal tooling cannot actively write the same repo/worktree from two machines at once.
- Repository knowledge is retrieved from its authority rather than silently copied into personal memory.
- Memory remains usable read-only from the lab if home is unavailable, without automatic split-brain writes.
- Local model defaults are selected from measured results, not model reputation.
- Routine memory extraction/indexing uses local inference by default and records any paid escalation.

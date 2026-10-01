---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-08-19-aoteru-central-memory-and-universal-assistant
title: "Build Aoteru central memory and universal assistant"
status: inbox
priority: high
task_type: architecture-convergence
created_by: migrated-from-obsidian-phd
updated_at: 2026-09-23T15:26:00+01:00
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

---
title: Continuous local estate steward
status: future-work
owner: odysseus
as_of: 2026-08-19
parent: docs/aoteru-estate-implementation-plan.md
---

# Continuous local estate steward

## Goal

Keep the strongest suitable **lab-local model permanently available as an idle/background estate steward**. Use spare compute to continuously reduce entropy across all registered repositories and both desktops without consuming paid-model quota or creating a second authority.

## Scope

The steward may continuously:

- audit registered repos, configs, docs, skills, MCPs, hooks, tasks and runtime state;
- detect duplicated capability, stale instructions, contradictory architecture, dead paths, drift and unfinished convergence;
- validate tests, schemas, links, capability truth, dependency/version state and backup/recovery posture;
- compress verbose/redundant documentation and generated state while preserving meaning/provenance;
- identify opportunities to merge, simplify, deduplicate or relocate capabilities to their canonical owner;
- compare lab/home inventories, services, models, clones and configuration for unnecessary divergence;
- maintain concise machine-readable findings, debt rankings and proposed patches;
- perform low-risk derived-state rebuilds and deterministic maintenance already authorised by each domain;
- use the home worker as an independent critic/verifier when useful and idle.

## Boundary

Default mode is **observe -> verify -> propose**, never free-running canonical modification.

- Read globally only through the estate registry/allowlists.
- Respect every repo's local instructions and authority.
- No mutation without the same parking lease, write scope and verification required for an interactive Aoteru task.
- Never auto-promote research evidence, memories, ontology, governance, credentials or external side effects.
- Never create a parallel queue, memory, router or architecture authority.
- Do not wake paid Claude/Codex merely to improve housekeeping. Escalate only when a queued finding is high-value and local verification cannot resolve it.

## Runtime

After `docs/aoteru-estate-implementation-plan.md` P10 passes:

1. Run as an Odysseus supervised background job on the lab PC.
2. Use a dedicated `estate-steward` capability alias resolved to the cheapest model that passes the steward benchmark; do not pin a brand permanently.
3. Operate at low priority and yield GPU/RAM immediately to interactive work.
4. Scan incrementally from Git commits, filesystem/runtime change events and prior steward checkpoints; never repeatedly reread entire repos.
5. Store only compact findings/state in Odysseus SQLite plus paths/hashes to supporting evidence.
6. Batch related findings into one convergence proposal rather than opening many micro-tasks.
7. Run an independent verifier before any proposed mutating maintenance is eligible for normal routing.

## Output contract

Each finding is one structured record:

```text
repo/host | class | severity | evidence refs | canonical owner | proposed action | confidence | verification | status
```

Classes: `drift`, `duplication`, `stale`, `contradiction`, `test-failure`, `security`, `compression`, `convergence`, `dead-state`, `upgrade-candidate`.

Only surface findings to Aoteru when they are actionable, recurring or materially reduce risk/maintenance. Routine clean scans stay silent.

## Acceptance

- steward restarts automatically with the lab worker;
- idle operation does not materially degrade interactive latency;
- incremental scans cost substantially less than full rescans;
- every proposal resolves to evidence and one canonical owner;
- no unauthorised canonical write occurs in fault/adversarial tests;
- repeated runs reduce unresolved duplication/drift rather than create more review debt;
- home/lab divergence is visible and intentional or queued for convergence;
- paid-model use for estate housekeeping is exceptional and explicitly justified.
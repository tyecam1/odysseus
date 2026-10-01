---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-01-misumi-durable-transcript-runtime
title: "Build durable Misumi transcript runtime with idempotent multihost STT"
status: inbox
priority: critical
task_type: implementation
created_by: chatgpt
created_at: 2026-10-01T12:00:00+01:00
updated_at: 2026-10-01T12:00:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single-plus-verifier
architecture_rationale: "One implementation owner must preserve Odysseus session, memory, database, auth and estate-routing authority; an independent Sol-class verifier should try to falsify durability, owner isolation, idempotency and host-truth claims."
single_agent_baseline: "A Sonnet-class implementation owner can extend the existing Misumi/STT/database surfaces coherently, with Opus used only for architecture decisions that remain ambiguous after the live audit."
execution_host: compute-box
context_budget: high
coordination_reason: "This crosses STT, database, Misumi routes, session semantics and estate placement. Keep one implementation owner, use Opus for bounded planning/synthesis, then independent Sol verification."
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - routes/**
  - services/**
  - src/**
  - core/**
  - config/**
  - tests/**
  - docs/**
  - migrations/**
  - automation/review/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*.pdf"
inputs:
  - routes/misumi_routes.py
  - routes/stt_routes.py
  - services/stt/stt_service.py
  - core/session_manager.py
  - src/misumi_memory.py
  - src/database.py
  - config/estate.yaml
  - config/routing.yaml
  - docs/aoteru-model-host-routing-contract.md
  - automation/review/agent-tasks/inbox/2026-08-19-local-first-dual-pc-agent-runtime.agent-task.md
  - automation/review/agent-tasks/ready/2026-09-23-odysseus-staged-implementation-loop.agent-task.md
  - tyecam1/misumi:docs/audits/2026-10-01-misumi-odysseus-voice-gui-integration-audit.md
outputs:
  - durable owner-scoped Misumi transcript event store
  - atomic/idempotent transcript ingestion API
  - transcript query/export surface
  - decoupled conversation-history versus semantic-memory retention policy
  - multihost STT execution seam using existing estate routing
  - focused restart/outage/duplicate/owner-isolation tests
  - docs/misumi-durable-transcript-runtime.md
result_path: docs/misumi-durable-transcript-runtime.md
review_report_path: automation/review/misumi-durable-transcript-runtime-sol-verification.md
handoff_model: gpt-5.6-sol
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "This task does not create another host router, memory authority, queue or transcript copy in Git. Home/lab worker qualification remains governed by the existing multihost programme."
---

# Build durable Misumi transcript runtime with idempotent multihost STT

## Goal

Provide the backend contract required for Misumi to continuously capture speech while treating every successfully transcribed segment as durable runtime history before wake/intent routing.

The target sequence is:

```text
audio segment
  -> authenticated Odysseus ingestion
  -> STT on an eligible worker
  -> durable transcript commit
  -> acknowledgement
  -> wake/intent decision
  -> optional /misumi/respond
```

A wake miss is not a transcript-loss event.

## Boundaries

### Odysseus owns

- authentication and owner scoping;
- transcript runtime storage;
- STT service ownership;
- home/lab execution routing;
- session linkage;
- semantic-memory promotion machinery;
- export/query/runtime observability;
- restart/idempotency semantics.

### Misumi owns

- microphone/capture UX;
- visible listening/pause state;
- local bounded retry outbox;
- rolling transcript presentation;
- wake/intent UI behaviour;
- household-domain privacy policy and user-facing controls.

### Neither owns

Ambient transcript rows are not canonical household facts. They do not outrank the Misumi Git knowledgebase and are not automatically promoted to semantic memory.

## First action: live-state reconstruction

Before design or code:

1. inspect current `dev`, open relevant PRs/branches and deployed home/lab versions;
2. inspect the current database/session/STT/Misumi route models and migrations;
3. establish which host currently serves the authoritative Misumi API;
4. inspect current home/lab worker eligibility and the remaining stages of the multihost plan;
5. identify any already-built transcript/event primitive that can be reused;
6. ask Opus for an architecture critique only after the live evidence packet exists.

Do not implement from this task's speculative field names if live code provides a better established primitive.

## Required contract

### 1. Dedicated transcript event model

Represent an append-oriented transcript event separately from selective semantic memory.

Required semantics:

- stable external/client `event_id` is unique within owner/domain scope;
- owner/domain isolation is enforced at read and write boundaries;
- source capture start/end time is preserved separately from server persistence time;
- verbatim STT text is retained;
- capture mode is recorded;
- STT provider/model/physical execution host and latency are attributable;
- active interface persona may be recorded as presentation context;
- wake/intent result may be attached after persistence;
- optional Misumi conversation `session_id` / response request linkage may be attached;
- retries are idempotent.

Do not store credentials or whole model prompts in transcript metadata.

### 2. Atomic audio-to-durable-transcript endpoint

Prefer one production boundary equivalent to:

`POST /misumi/transcript/audio`

rather than requiring the browser to call a generic STT endpoint and then race a second persistence request.

The exact route/name may change after live design review, but the semantics must be atomic from the client's perspective:

- accept bounded audio plus event/timing metadata;
- transcribe through the established STT service;
- persist the transcript before success is acknowledged;
- return the durable event identity/text/persistence state;
- if the client retries the same event after an ambiguous timeout, return/reconcile the existing event rather than duplicating it.

A transcription that cannot be durably stored is not "saved".

### 3. Raw-audio lifetime

No permanent raw-audio archive by default.

Server-side temporary audio and worker transfer artifacts must be removed after transcription/persistence resolution according to the established bounded cleanup contract.

The client may retain raw audio only while an event is unacknowledged, so outage recovery is possible.

### 4. Query/export

Provide owner-scoped retrieval sufficient for:

- recent transcript;
- time-range query;
- event lookup;
- pagination;
- export in a stable human-readable/machine-readable form;
- later linking to a Misumi conversation.

Do not make the normal UI load unbounded transcript history.

### 5. Separate retention dimensions

Repair the current coupling in `/misumi/respond` where ordinary session persistence depends on semantic-retention mode.

Model explicit policy dimensions for at least:

- transcript archive enabled/disabled;
- conversation/session history enabled/disabled;
- semantic-memory promotion enabled/disabled;
- requested artifact creation enabled/disabled;
- raw-audio retention (off by default).

Preserve a true incognito/no-history route where requested, but do not make "do not promote this to memory" erase normal conversation history.

### 6. Home + laboratory execution

Do not implement another host selector.

Use the existing Odysseus estate routing contract so a transcript/STT job can be placed on an eligible home or lab worker according to:

- verified/reachable/healthy state;
- capability;
- data/locality and privacy policy;
- measured latency/throughput;
- load;
- failure/retry state.

`route.host` must equal the host that physically executes STT/model work.

The interface PC and laptop are not normal execution workers.

The home host currently remains deliberately ineligible until its live benchmark/worker qualification gate is satisfied. Do not bypass that by special-casing Misumi.

For live household microphone traffic, prefer the route that satisfies privacy and latency with the least unnecessary network movement. A lab route is valid only through the authenticated private network and when current policy allows the audio job to leave the home site.

### 7. Persistence authority and failover

Do not turn home and lab into uncontrolled multi-writers.

Reuse the existing central-memory/runtime direction: one normal write authority with explicit replica/read-failover semantics where implemented. If transcript durability requires a new replication primitive, Opus must first produce a bounded design that reuses current database/backup mechanisms and preserves no-split-brain writes.

Compute placement and persistence authority are separate decisions.

## Failure semantics

Handle explicitly:

- empty/no-speech capture;
- STT unavailable;
- worker unreachable;
- worker returns after caller timeout;
- database commit failure;
- duplicate event retry;
- backend restart during ingestion;
- worker restart during transcription;
- owner mismatch;
- malformed/oversize audio;
- transcript persisted but assistant dispatch later fails.

A transcript already persisted must remain visible even if the later Misumi response fails.

## Tests

At minimum prove:

1. same `event_id` retried after an ambiguous timeout produces one durable event;
2. two owners cannot read or overwrite each other's transcript events;
3. persisted transcript survives Odysseus process restart;
4. successful transcript commit occurs before response/wake continuation is acknowledged;
5. semantic-memory retention off does not disable ordinary session persistence;
6. transcript archival off behaves explicitly and does not claim persistence;
7. worker route metadata records the actual physical execution host;
8. home-ineligible state cannot be bypassed by Misumi STT;
9. lab/home route failure does not silently execute on the control-plane host;
10. raw temporary audio is cleaned after resolved ingestion;
11. query pagination is bounded;
12. migration/backward compatibility preserves existing Misumi sessions/memory.

## Independent Sol verification

After the implementation owner reports green tests, prepare a fresh-context Sol packet with:

- governing contract;
- schema/migration;
- API route;
- owner/auth code;
- idempotency logic;
- multihost placement;
- cleanup path;
- exact tests/results;
- restart/outage evidence.

Ask Sol to actively find:

- duplicate creation races;
- commit/ack ordering defects;
- cross-owner leaks;
- split-brain/multiwriter risk;
- false host attribution;
- hidden local fallback;
- raw-audio retention leaks;
- coupling between transcript, session and semantic memory;
- migrations that can lose existing data.

Sol is verifier/adjudicator only and must not edit code.

## Completion

Complete only when the real Misumi interface can rely on this contract for its outage/restart acceptance tests. Do not close on unit tests alone if live home/lab/interface deployment remains unverified.

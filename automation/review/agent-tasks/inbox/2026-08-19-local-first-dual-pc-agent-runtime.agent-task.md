---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-08-19-local-first-dual-pc-agent-runtime
title: "Build local-first dual-PC agent runtime and single access surface"
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
migrated_from_path: 10-inbox/2026-08-19-local-first-dual-pc-agent-runtime.md
notes: "Migrated as shared backend/cross-repository work. Original body preserved below; re-ground paths against live Odysseus state before execution."
---

# Build local-first dual-PC agent runtime and single access surface

## Goal

Redesign the agent estate around two permanently available gaming PCs: the lab PC and home desktop. Use local models and deterministic automation for routine work, reserve Claude Pro and ChatGPT Plus/Codex for work where their capability justifies scarce subscription usage, and make all execution lanes easy to reach from one consistent operator surface.

The intended default operator harness is Claude Code, but the architecture must not require paid Claude inference merely to invoke a local task.

## Immediate architectural correction

Current contracts assume one compute box and prohibit local model execution on ordinary client machines. Misumi's older topology also assumes one server and downstream clients. Those assumptions no longer match the desired estate and must be reviewed rather than preserved by inertia.

Do not simply enable models everywhere. Reconstruct the current capability graph across `obsidian-PhD`, `odysseus`, and `misumi`, then define one owner for each capability and one execution path for each task class.

## Durable identity of each system

### Obsidian PhD

Source of truth for PhD research knowledge, research task state, research provenance, evidence and governed research workflows.

### Misumi

Household-facing knowledge and agent interface. Keep household memory, credentials, data and behavioural/persona state isolated from PhD state. Misumi must not become a duplicate general research agent merely because the same runtime can host it.

### Odysseus

Shared local runtime, monitoring and control plane. It should expose model workers, health, queues, scheduled jobs, retrieval services and bounded tool execution to both domains through separate profiles/contracts. It is not research authority and not household authority.

### Claude Code

Primary interactive operator harness for complex work across the estate. It should be able to inspect state, call local services, dispatch bounded jobs, invoke Codex when justified, and escalate difficult work to Claude itself.

Claude Code is a cockpit, not the only engine. A local job must remain directly invokable without first spending Claude tokens.

## Target topology

### Lab PC

Primary PhD compute node:

- always-on Odysseus runtime
- PhD runtime/profile and research-engine services
- local inference endpoint
- local embedding and reranking services
- PhD retrieval/index caches
- deterministic review, extraction, conversion, testing and maintenance jobs
- primary clone/workspace for unattended PhD automation where safe
- Claude Code and Codex CLI available for interactive or escalated work
- optional Misumi client/profile access, but no household authority leakage

### Home desktop

Primary household and secondary research compute node:

- always-on Odysseus runtime
- primary Misumi deployment/profile
- local inference endpoint
- household-only Misumi memory/cache
- secondary PhD worker capacity for overflow, long-running local inference and independent verification
- Claude Code and Codex CLI available
- research state accessed only through governed PhD contracts/clones, never mixed with Misumi state

### Both machines

Install the same worker/runtime contract where practical, with host-specific capabilities discovered from hardware rather than hard-coded assumptions. Each host publishes:

- hardware profile
- available local models
- context limits
- measured throughput
- available VRAM/RAM
- current load
- supported execution classes
- health

Odysseus routes to a host based on capability, data locality and load. Do not create a second task authority merely to load-balance jobs.

## Network and remote access

Provide private cross-location access without exposing raw model, shell or control-plane ports to the public internet.

Preferred pattern to evaluate and implement if permitted on both networks:

- private mesh VPN between operator devices, lab PC and home desktop
- stable machine/service names rather than changing IP addresses
- normal Windows OpenSSH over the private network where SSH is required
- authenticated Odysseus web/PWA surfaces reachable only through the private network
- firewall rules limited to the private overlay/LAN
- no router port forwarding

If university policy prevents the preferred overlay, document and implement the safest supported alternative without weakening the no-public-endpoint rule.

## One-place access model

The operator should not have to remember which machine or model owns a task.

Provide three compatible entry paths:

### 1. Claude Code: high-capability cockpit

From either working PC, Claude Code should expose a small governed tool surface for:

- `/route <task>` or equivalent architecture-selection command
- estate health
- local model dispatch
- Odysseus task/queue inspection
- PhD retrieval
- Misumi access where explicitly requested
- Codex invocation
- verification and handoff retrieval

Use MCP or a similarly narrow adapter instead of teaching Claude Code machine-specific shell commands throughout prompts.

### 2. Direct local CLI: zero-subscription path

A command such as `agent local`, `route-local`, or equivalent must execute suitable work without invoking Claude or OpenAI first. This is required to make local execution a real subscription-saving lane rather than a Claude-controlled illusion of one.

The direct CLI should use the same routing/task contracts as Claude Code and Odysseus.

### 3. Odysseus web/PWA: persistent local UI

Use Odysseus as the browser-accessible view for:

- local chat
- running/background jobs
- model selection when manual override is wanted
- system health
- task history
- scheduled work
- reports/artifacts

Misumi remains the household-branded conversational profile/interface within its own domain rather than becoming the generic operator console.

## Execution lanes

Build a cost-aware routing policy. Default to the cheapest lane that can meet the task's quality and verification requirement.

### Lane 0: deterministic automation

Use scripts/tools before any model for:

- file conversion
- metadata normalization
- checksums/deduplication
- indexing
- citation resolvability
- lint/tests
- Git hygiene
- scheduled sync/health checks
- structured extraction where deterministic methods suffice

### Lane 1: small/fast local model

Use for bounded, easily verified work such as:

- classification and routing
- metadata enrichment
- tagging
- candidate relevance screening
- simple summaries
- extraction cleanup
- formatting transformations
- repetitive note triage
- first-pass issue categorisation

### Lane 2: stronger local model

Use when the task needs reasoning but can tolerate local-model quality with verification:

- first-pass literature synthesis
- evidence clustering
- candidate research-question mapping
- draft critique
- code generation on bounded components
- test generation
- repo audits
- task decomposition
- local document Q&A
- overnight research-engine maintenance

Exact models are not fixed in this work item. Select them after hardware discovery and benchmark them on representative PhD and Misumi tasks. Prefer measured quality/throughput/VRAM trade-offs over model reputation.

### Lane 3: Claude Pro through Claude Code

Reserve for high-value work where long-context reasoning, synthesis, architecture, difficult writing, ambiguity resolution or orchestration materially outperforms local models.

Claude should preferentially:

- frame complex tasks
- make architecture decisions
- perform high-value research synthesis
- critique difficult manuscripts/arguments
- adjudicate ambiguous local outputs
- orchestrate multi-step work only where orchestration itself needs Claude-level reasoning

Do not spend Claude turns on deterministic work or routine local-model tasks.

### Lane 4: ChatGPT Plus / Codex

Use primarily as an independent second strong lane for:

- implementation and refactoring
- difficult debugging
- repo-wide audits
- independent verification
- adversarial review against Claude/local outputs
- migrations and mechanical code work

Codex can be invoked from the central harness when appropriate, but preserve a direct Codex path so Claude usage is not required merely to call it.

### Lane 5: explicit human judgement

Retain human gates for evidence promotion, research claims, ontology changes, sensitive writes, publication/submission, credentials, destructive operations and other existing governed boundaries.

## Subscription budget policy

Introduce explicit routing metadata for each task/run:

- estimated reasoning difficulty
- verification difficulty
- context requirement
- local suitability
- preferred lane
- fallback lane
- whether paid inference is justified
- provider/model actually used
- host actually used
- rough token/usage accounting where available

Provide a weekly report showing which task classes consumed Claude/Codex usage and which could have been routed locally. The purpose is to continuously move low-value paid work downward without degrading research quality.

## Local model selection benchmark

Before changing routing defaults:

1. Inventory CPU, GPU, VRAM, system RAM, storage and OS on both PCs.
2. Inventory current runtimes and drivers.
3. Define a representative benchmark suite from actual repository work:
   - metadata/routing
   - PDF span summarisation
   - evidence relevance
   - literature synthesis
   - code patch
   - code review
   - research-note Q&A
   - Misumi household query
4. Test multiple model sizes/quantisations that fit each host.
5. Record quality, latency, tokens/s, context capacity, peak VRAM/RAM and failure rate.
6. Choose a small default and stronger default per host.
7. Keep model names/configuration replaceable. Routing targets capability classes, not permanent model brands.

## Routing architecture

Extend the existing `/route`/agent-routing work rather than create another router.

The routing decision should consider:

`task risk + required quality + context + verification + data locality + host capability + current load + subscription budget`

Expected routing shape:

`task -> deterministic? -> local-small? -> local-strong? -> paid Claude/Codex? -> human gate`

A failed local run may escalate upward. A successful low-risk local run should not be escalated merely because a paid model is available.

## Cross-repository convergence

As part of implementation, audit and reconcile stale/conflicting boundaries across:

- `obsidian-PhD`
- `odysseus`
- `misumi`

At minimum inspect:

- model execution policy
- agent routing policy
- Odysseus central-interface contract
- Odysseus runtime-specific code that has absorbed PhD business logic
- Misumi's Odysseus contract
- Misumi two-PC topology
- duplicated task queues/routing code
- MCP/tool registries
- retrieval and memory ownership
- scheduled/background work

For each capability classify `keep | move | merge | wrap | deprecate` and name its canonical owner.

This work depends on and should inform `10-inbox/2026-08-19-centralised-knowledge-gathering-system.md`.

## Reliability

Both machines being permanently available should increase resilience, not create distributed-state ambiguity.

- canonical research/household data remain in their existing authorities
- caches and model state are disposable
- task state has one authority per domain
- local jobs write proof-carrying results/handoffs, not hidden state
- services restart automatically after reboot
- health checks detect stale/unreachable workers
- a single host failure degrades capacity but does not corrupt state
- no automatic active-active writes to the same canonical files

## Implementation sequence

1. Audit the three repositories and current deployed state.
2. Inventory both PCs and benchmark realistic local models.
3. Write the new estate topology and responsibility matrix.
4. Replace obsolete single-compute-box/model-policy assumptions.
5. Implement a common worker capability/health contract on both PCs.
6. Implement secure cross-location private connectivity.
7. Expose local dispatch and estate health through Odysseus.
8. Expose the same governed operations to Claude Code through a narrow MCP/adapter surface.
9. Implement direct zero-cloud CLI access to local routing.
10. Integrate Codex as the independent paid implementation/verification lane.
11. Add usage-aware routing and weekly paid-vs-local reports.
12. Run representative end-to-end tasks from both locations.
13. Remove superseded paths/configuration only after equivalence is demonstrated.

## Acceptance criteria

- Lab PC and home desktop automatically restore their intended Odysseus/model services after reboot.
- Both machines advertise machine-readable worker capabilities and health.
- Either location can securely reach both workers without public port exposure.
- Claude Code on either working machine can inspect and dispatch to both local workers through one stable interface.
- A local task can also be launched directly without consuming Claude or OpenAI subscription usage.
- Odysseus provides one persistent browser/PWA view of local models, jobs and health.
- Misumi remains household-specific with isolated memory/config/credentials.
- PhD research state and Misumi household state cannot cross-contaminate through shared runtime memory.
- `/route` or its successor chooses deterministic/local lanes before paid lanes when they meet the requirement.
- Paid-model escalation is explicit and recorded.
- Codex remains independently invokable and can act as a second strong reviewer/implementer.
- Representative benchmark results justify the selected local models on each host.
- Current stale model/topology contracts are reconciled rather than left as contradictory documentation.
- Failure of either PC leaves the other usable and does not create conflicting canonical state.

## Non-goals

- replacing Claude or ChatGPT entirely
- forcing all tasks through Claude Code
- exposing local model/API ports publicly
- merging PhD and household memory
- creating another task queue or knowledge authority
- selecting permanent model brands before hardware/task benchmarks
- using local models for high-stakes evidence promotion without the existing verification gates

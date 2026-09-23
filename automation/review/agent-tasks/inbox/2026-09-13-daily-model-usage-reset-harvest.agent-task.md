---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-13-daily-model-usage-reset-harvest
title: "Harvest expiring Claude, Codex and GLM usage into prioritised repo work"
status: inbox
priority: medium
task_type: resource-orchestration
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
migrated_from_path: 10-inbox/2026-09-13-daily-model-usage-reset-harvest.md
notes: "Migrated as shared backend/cross-repository work. Original body preserved below; re-ground paths against live Odysseus state before execution."
---

# Harvest expiring Claude, Codex and GLM usage into prioritised repo work

## Goal

Add a low-overhead daily usage check for Claude, Codex and GLM. When a model has meaningful paid/subscription usage remaining and its relevant allowance will reset within 24 hours, route that otherwise-expiring capacity into the highest-priority safe autonomous work already authorised across the repository estate.

The objective is utilisation of expiring capacity, not maximising token consumption. Do not create work merely to spend quota.

## Architectural boundary

Extend the existing Aoteru/controller model-routing and work-dispatch path. Do not create a parallel scheduler, backlog, model router or orchestration loop.

Use existing canonical work-item/task state and the `research-work-priority` decision logic. Prefer a governed Odysseus/Aoteru estate inventory when available. If live priority or work authority is unclear, do not infer a new priority system.

## Daily trigger

Run once per day.

For each supported provider/model family:

1. Read the best available authoritative usage state.
2. Record:
   - allowance/window type;
   - remaining usage or best available proxy;
   - reset timestamp;
   - time until reset;
   - confidence/source of the reading.
3. If reset is more than 24 hours away, take no quota-harvest action.
4. If reset is within 24 hours and meaningful usage remains, enter `harvest` mode for that provider.
5. If usage/reset state cannot be measured reliably, report `unknown`; do not guess or burn capacity blindly.

Avoid brittle authenticated scraping where a CLI/API/local state or supported account surface exists.

## Harvest policy

When a provider enters `harvest` mode:

1. Obtain the current estate-wide priority order from the canonical priority mechanism.
2. Filter to work that is:
   - already authorised and open;
   - safe for autonomous execution;
   - compatible with that model/executor;
   - not blocked by a human-only decision;
   - not in conflict with another active worker or mutable branch;
   - capable of producing a bounded, reviewable deliverable before the reset.
3. Dispatch through the existing controller using normal routing contracts. The expiring provider is an available execution resource, not permission to bypass task ownership or model suitability.
4. Continue bounded dispatch while useful eligible work exists and meaningful expiring capacity remains.
5. Stop when:
   - eligible work is exhausted;
   - remaining quota is too small to justify another bounded task;
   - the reset occurs;
   - a provider/rate-limit/error state makes continuation unsafe;
   - work would cross a human/research-authority gate.

Do not force exact zero remaining usage. Preserve a small operational margin where needed to avoid failed completions or unusable partial work.

## Priority rules

Quota expiry is a resource-utilisation signal, not research priority.

Apply the repository priority order first:

1. fixed external deadlines and human-gated preparation;
2. current PhD research critical path;
3. work that directly unlocks the next justified research stage;
4. bounded parallel work reducing friction on 1-3;
5. lower-priority infrastructure or exploratory work only when higher-priority eligible work is unavailable.

Do not let expiring quota activate speculative infrastructure, optional hardware/model experiments, side papers, aesthetic cleanup or broad refactors while stronger authorised work exists.

## Model suitability

Respect the live operating contract and current model-routing evidence. Do not hard-code permanent equivalence between Claude, Codex and GLM tiers.

At dispatch time, select only tasks the available model can complete to the required standard. Typical candidates may include source gathering, bounded coding, tests, deterministic validation, evidence extraction, review passes, synthesis preparation and other already-authorised agent work. Consequential research-authority decisions remain human-gated.

## Usage-source discovery

Before implementation, audit how usage/reset information can actually be obtained for each provider in the current estate:

- Claude subscription/CLI/account state;
- Codex/OpenAI usage state available to the current environment;
- GLM/Z.AI coding-plan usage state;
- any existing controller telemetry, wrappers, logs or local metadata already exposing reset windows.

For each provider, classify the source as:

`authoritative | supported proxy | weak proxy | unavailable`

Only automate harvest decisions from `authoritative` or sufficiently reliable `supported proxy` sources. Keep weaker signals observational until validated.

## State and reporting

Maintain minimal machine-readable state sufficient to prevent duplicate daily runs and explain decisions. Reuse existing telemetry/report locations where possible.

A daily record should contain, at minimum:

- check timestamp;
- provider/model family;
- usage source and confidence;
- reset timestamp/time remaining;
- remaining allowance/proxy;
- harvest decision;
- work items dispatched;
- executor/model actually used;
- completion/failure outcome;
- estimated or measured usage consumed where available;
- stop reason.

Do not create a second long-term work database.

## Failure and safety behaviour

- Never spend usage on invented work.
- Never bypass research-authority or human-approval gates.
- Never perform destructive/irreversible actions merely to consume quota.
- Never override experiment reservations or shared mutable-resource locks.
- Never start overlapping workers on the same write scope unless the existing controller explicitly supports it.
- Never expose credentials or scrape account surfaces in a way that weakens security.
- If usage telemetry is stale, ambiguous or contradictory, fail closed for harvesting and emit a diagnostic.

## Acceptance criteria

Complete when:

1. Claude, Codex and GLM each have a documented usage/reset telemetry path or an explicit `unavailable` classification.
2. One canonical once-daily check is integrated into the existing agentic runtime without introducing a parallel scheduler/router.
3. A provider with reset `<=24 h` and meaningful remaining allowance can trigger bounded work harvesting through the existing controller.
4. Harvested work is selected from live canonical priorities and respects human/agent boundaries and WIP/conflict controls.
5. A provider with reset `>24 h`, no meaningful remaining allowance, or unreliable telemetry does not trigger harvesting.
6. The system stops cleanly when useful eligible work or safe remaining quota is exhausted.
7. Dry-run tests cover at least: no-reset case, near-reset case, unknown telemetry, no eligible tasks, conflicting active work, and provider execution failure.
8. A concise audit record makes every harvest decision and dispatch traceable.
9. Documentation identifies how to disable the feature immediately without disrupting ordinary Aoteru/controller dispatch.

## First implementation pass

Start by mapping existing controller/runtime ownership and current usage telemetry. Reuse before building. Produce a short design/diagnostic note before code changes if provider usage visibility is not already explicit.
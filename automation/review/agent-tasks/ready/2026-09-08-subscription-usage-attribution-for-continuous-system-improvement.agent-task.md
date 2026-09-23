---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-08-subscription-usage-attribution-for-continuous-system-improvement
title: "Attribute subscription usage to continuous agentic system-improvement functions"
status: ready
priority: high
task_type: system-efficiency-analysis
created_by: gpt-5.6-sol
created_at: 2026-09-08T12:54:00+01:00
updated_at: 2026-09-08T12:54:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single-agent-sequential
architecture_rationale: "Usage attribution needs one ordered observer across provider meters and function executions. Parallel measurement risks contaminated deltas and double-counting."
single_agent_baseline: "One Claude subscription agent can recover available usage telemetry, correlate it with bounded system-improvement functions, and propose routing changes without modifying canonical configuration."
execution_host: laptop
context_budget: medium
coordination_reason: "Keep provider observations and function-run attribution in one ordered ledger. Do not run multiple subscription-heavy functions inside the same attribution window."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: true
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/**
denied_paths:
  - 00-dashboards/**
  - 01-research-plan/**
  - 02-library/**
  - 03-concept/**
  - 04-supportDesign/**
  - 06-datasets/**
  - 07-standards/**
  - 09-resources/**
  - 10-inbox/**
  - 11-projects/**
  - 12-log/**
  - .agents/**
  - .claude/**
  - Scripts/**
  - automation/config/**
  - automation/docs/**
inputs:
  - AGENTS.md
  - automation/AGENTS.md
  - automation/docs/continuous-improvement-loop-contract.md
  - automation/review/architecture/asi-evolve-loop/2026-06-29-central-continuous-improvement-loop-design.md
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
  - automation/config/model_execution_policy.yaml
  - automation/config/agent_routing.yaml
  - recent continuous-improvement iteration, work-item-audit, routing, and system-efficiency reports
outputs:
  - provider subscription-usage baseline and reset-window register
  - function-level usage-attribution ledger with confidence labels
  - ranked diagnosis of expensive recurring agentic functions
  - routing, cadence, batching, context, and model-selection recommendations
  - proposed minimal telemetry schema for future continuous measurement
  - bounded follow-up implementation task only if instrumentation changes are justified
result_path: automation/review/system-efficiency/2026-09-08-subscription-usage-attribution.md
review_report_path: automation/review/system-efficiency/2026-09-08-subscription-usage-attribution.md
handoff_model: gpt-5.6-sol-independent-review
operator_decision_path: automation/review/system-efficiency/2026-09-08-subscription-usage-attribution.md
supersedes: []
duplicates: []
notes: "Prefer machine-readable or local usage telemetry over browser dashboards. Browser access is a fallback only when no simpler reliable source exists. The deterministic continuous-improvement loop remains network-free. Never automate credential entry, extract cookies/tokens, or store private account/billing identifiers."
---

# Subscription usage attribution for continuous agentic system improvement

## Objective

Determine how much of the available **Claude, OpenAI/Codex, and z.ai/GLM subscription capacity** is consumed by recurring agentic functions that continuously improve the research-system graph, then use that evidence to improve routing efficiency without reducing research quality.

The governing question is:

> Which recurring system-improvement functions consume meaningful fractions of constrained paid-model capacity, which consumption is justified by decision value, and what routing, cadence, batching, context, or escalation changes would reduce waste while preserving required capability?

The target is **value per constrained subscription unit**, not generic cost minimisation.

## Usage-source hierarchy

Use the simplest reliable source available for each provider, in this order:

1. existing local execution telemetry, run metadata, provider usage summaries, or already-captured system logs;
2. provider-supported local CLI/account usage commands or machine-readable usage/status output, where available without exposing secrets;
3. provider/API usage metadata already available through an authorised connector or existing tool;
4. authenticated subscription usage webpage as a fallback only;
5. manual operator observation only if no reproducible source exists.

Do not browse merely because a dashboard exists.

For Claude, OpenAI/Codex, and z.ai/GLM, first establish what usage signal is actually available and how granular it is before designing measurement around it.

If a fallback browser surface requires reauthentication, MFA, CAPTCHA, or credential entry, stop and require manual operator authentication. Do not automate login or extract session secrets.

## Measurement principles

Provider meters may expose different concepts, windows, and units. Therefore:

- preserve each provider's native usage signal;
- never compare raw provider units as though they are equivalent;
- record reset windows and timestamp every observation;
- where defensible, additionally express consumption as percentage of the relevant allowance/window;
- separate exact measured deltas from inferred attribution;
- assign `high`, `medium`, or `low` confidence to every attribution;
- if a provider signal is too coarse for function-level attribution, state that rather than inventing precision.

## Functions to attribute

Recover the taxonomy from actual recent repository activity. At minimum test recurring functions such as:

- continuous system-graph / architecture analysis;
- continuous-improvement lesson analysis and proposal generation;
- work-item audit and dispatch preparation;
- repository-wide coherence or duplication audits;
- agent architecture / model-routing selection;
- research-engine health and capability audits;
- continuous scientific-writing / voice-system improvement work where it is part of system development;
- large-context synthesis or independent verification passes used to improve the agentic operating system.

Add or merge categories only where the repository demonstrates a genuinely distinct recurring function.

Do not attribute ordinary paper drafting, unrelated conversation, or personal usage to the continuous improvement system unless it is explicitly part of that function.

## Procedure

### 1. Discover usable telemetry before measuring anything

For each provider, determine:

`provider | source method | signal exposed | granularity | reset/window | machine-readable? | authentication burden | attribution suitability`

Prefer zero-additional-overhead telemetry already produced by the execution environment.

### 2. Recover recent function history

Inspect recent governed work items, continuous-improvement iterations, work-item audits, routing records, and system-efficiency reports.

Build:

`function_id | function | purpose | cadence/trigger | typical executor/model | evidence of recent runs | current routing owner`

### 3. Attribute consumption using the least intrusive method

Use, in order of preference:

- existing per-run or per-session telemetry;
- timestamp correlation between run logs and provider usage records;
- bounded before/after measurement around an already-needed representative function;
- cautious inference from repeated historical runs.

For bounded before/after measurement:

1. record the provider signal immediately before;
2. run exactly one identifiable, already-useful function;
3. record the provider signal immediately after;
4. record dashboard/API update latency and confounders;
5. avoid other provider-heavy activity inside the measurement window.

Do not deliberately burn substantial subscription allowance just to measure subscription allowance.

### 4. Maintain one attribution ledger

For each observation:

`timestamp | provider | model/executor | function_id | workload | context/input-size proxy | duration if known | usage before | usage after | delta | normalised window delta | attribution confidence | confounders | output/decision value`

Where repeated runs support aggregation:

`function_id | n | typical/median usage | range | cadence | projected window burden | confidence`

Do not extrapolate aggressively from sparse measurements.

### 5. Assess value versus consumption

For each recurring function, assess:

`function | subscription burden | decision value | quality sensitivity | latency sensitivity | cheaper-route suitability | recommendation`

Allowed recommendation classes:

- `KEEP`
- `BATCH`
- `ROUTE_CHEAPER`
- `LOCAL_FIRST`
- `ESCALATE_ONLY`
- `REDUCE_CONTEXT`
- `REMOVE_DUPLICATION`
- `MEASURE_BETTER`
- `RETIRE`

Cheaper routing is justified only where verification shows that the required function quality is preserved.

### 6. Diagnose graph-improvement waste specifically

Look for system-level inefficiencies rather than only expensive individual calls:

- repeated loading of the same repository context;
- redundant audits over unchanged surfaces;
- premium-model use for deterministic or mechanical preprocessing;
- excessive independent verification where the risk does not justify it;
- model escalation without evidence that lower-cost lanes failed;
- duplicate functions measuring the same graph/system property;
- cadence faster than the underlying graph can meaningfully change;
- expensive whole-repo analysis where bounded deltas would suffice.

Quantify the likely usage effect where evidence permits.

## Integration boundary

The current deterministic continuous-improvement loop is network-free and must remain so.

This work item may:

- write the usage study under `automation/review/**`;
- propose subscription efficiency as a future fitness evidence source;
- propose deterministic import of a separately collected usage artifact;
- create a bounded implementation task if justified.

It must not:

- make the core fitness collector contact provider services or dashboards;
- persist credentials or browser state;
- directly mutate `automation/config/model_execution_policy.yaml` or `agent_routing.yaml`;
- automatically reroute models from one measurement window.

Any routing or cadence change requires a separate governed implementation/review step.

## Required result

Keep the report decision-oriented:

1. provider telemetry available and its limitations;
2. recurring system-improvement functions identified;
3. usage-attribution ledger;
4. largest recurring consumers;
5. value-versus-consumption assessment;
6. recommended routing/cadence/batching/context changes;
7. minimal ongoing telemetry contract;
8. changes not justified by evidence;
9. follow-up implementation tasks only where materially necessary.

## Minimal ongoing telemetry

Design the lowest-overhead sustainable record, for example:

`window_id | provider | window_start | window_reset | usage_state_start | usage_state_end | attributed_functions[] | unattributed_delta | confidence | source_method | source_timestamp`

Prefer reusing existing execution logs and occasional provider snapshots over creating a parallel observability platform.

## Constraints

- Local or machine-readable telemetry first; browser fallback only.
- No automated credential entry, MFA handling, CAPTCHA bypass, cookie/token extraction, or secret persistence.
- No unnecessary private account or billing data in the repository.
- Do not spend significant quota solely for benchmarking.
- Do not treat provider-native units as mutually comparable.
- Do not remove premium reasoning from tasks whose quality materially affects PhD research or system governance.
- Do not change canonical research content.
- Do not directly mutate model-routing or continuous-improvement configuration.
- Preserve the existing network-free continuous-improvement-loop boundary.

## Completion criteria

Complete when:

- a reliable usage source or explicit telemetry limitation is recorded for Claude, OpenAI/Codex, and z.ai/GLM;
- recurring continuous-system-improvement functions are grounded in actual repo activity;
- meaningful measured or bounded-inference attribution exists wherever source granularity permits it;
- uncertainty is explicit;
- the largest justified and unjustified recurring consumers are identified;
- each material recommendation states likely efficiency benefit and quality risk;
- a minimal future telemetry design is specified;
- no secrets or unnecessary private account details are stored;
- the deterministic continuous-improvement loop remains network-free;
- implementation changes are routed to separate governed tasks rather than silently applied.

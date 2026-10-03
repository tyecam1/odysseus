---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-02-home-gpu-admission-signal
title: "Make household GPU contention an up-front routing/admission signal instead of a 120 s inference timeout"
status: done
priority: medium
task_type: implementation
created_by: claude
created_at: 2026-10-02T13:30:00+01:00
updated_at: 2026-10-03T15:00:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single
architecture_rationale: "Extends one existing signal (`gpu_yield` in worker `health`, consumed by `src/estate_router.py`). No new router, scheduler, lease or health store."
single_agent_baseline: "One implementation owner can add a load reading to the worker health payload, a threshold to the host registry, the router withholding rule and tests."
execution_host: compute-box
context_budget: medium
coordination_reason: "Misumi long-horizon programme, application 2026-10-02-misumi-long-horizon-programme-02. The Stage 8 `local-fast` canary on home failed 0/3 with 120 s timeouts because a game held about 92% of the GPU (docs/aoteru-multihost-execution-evidence.md). The operator's rule is that GPU contention is a routing/admission issue, not a model-quality failure; today nothing in the estate expresses that up front (adjudication log risk B7)."
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - src/estate_worker*.py
  - src/estate_router.py
  - config/estate.yaml
  - docs/**
  - tests/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
inputs:
  - docs/aoteru-multihost-execution-evidence.md
  - docs/aoteru-multihost-execution-implementation-plan.md
  - src/estate_router.py
  - src/estate_worker.py
outputs:
  - a GPU load reading in the worker `health` payload, next to the existing `gpu_yield`
  - a per-host busy threshold in the host registry
  - a router rule that withholds local-inference from a busy host with a truthful reason
  - tests, including the "unknown is not free" and "no silent fallback" cases
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Related: 2026-10-02-home-worker-non-admin-identity (re-runs the local-fast canary), docs/aoteru-multihost-adjudication-log.md risk B7."
---

# Household GPU contention as an admission signal

## Why

`gpu_yield` in the worker `health` payload only reflects experiment priority. When an ordinary household process (for
example a game) holds the home GPU, a routed `local-inference` call is still admitted and then times out after 120 s.
The Stage 8 canary recorded exactly that: 0 pass / 3 fail, every failure a timeout, GPU at about 98% with the game
using about 92%, and even a 16-token request timed out. A timeout looks like a model failure; it is an admission
failure.

## Required work

1. Worker side: add a bounded, cheap GPU reading to `health` (utilisation, memory used and total, and the reading's
   age) beside `gpu_yield`, for hosts that have an NVIDIA GPU. A host without the tool or the GPU reports "not
   available", which is neutral and never a failure.
2. Registry: a per-host busy threshold (utilisation and memory), with hysteresis so a brief spike does not flap
   eligibility.
3. Router: when the reading says busy, **withhold** `local-inference` from that host with a reason that names the
   cause ("withheld - household GPU busy: 98%, 7.8 of 8 GB"). It must not run the task on another host unless the
   normal placement rules would already have allowed that host, and it must not be recorded as the model failing.
4. A missing or stale reading is "unknown", not "free": the existing behaviour stays and the response says the
   reading was unavailable. Never claim a free GPU on no evidence.
5. The `local-fast` qualification canary refuses to start on a busy host and records "not run: GPU busy" instead of a
   result, so an admission refusal can never be counted as a benchmark failure (or as a pass on a retry).
6. Do not touch, signal or stop the competing process. Admission is observation only.

## Not allowed

- No new router, scheduler, queue, lease or health store; extend the existing owners.
- No change to which executors are qualified on any host.
- No widening of write authority, no silent fallback to the laptop or another host.

## Acceptance

- With the GPU above threshold, a pinned `local-fast` request to home is withheld up front with the reason above, in
  well under a second, not after 120 s.
- With the GPU below threshold, behaviour is unchanged.
- Missing or stale readings are reported as unknown and are not treated as free.
- Tests cover busy, free, hysteresis, unknown, a host without a GPU, and the canary's "not run" path; the busy-path
  guard is mutation-checked.
- Evidence is recorded in `docs/aoteru-multihost-execution-evidence.md`.

## Progress (2026-10-02, application `2026-10-02-misumi-long-horizon-programme-02`)

- Implemented in Odysseus PR #66 (merged): `src/gpu_admission.py`, worker `health` `gpu_load`, router withholding in
  `resolve_alias`, canary `not_run` / `inconclusive`, home opted in through `config/estate.yaml`. 49 new tests,
  mutation-checked, 533 existing estate tests unchanged.
- Live observation recorded in `docs/aoteru-multihost-execution-evidence.md`: with the game running, the old `gpu_yield` said
  `inactive` and the new classifier said `busy`.
- **Still open (real acceptance):** re-run the `local-fast` canary on the physical RTX 3070 while it is free. Nothing is
  qualified from simulated evidence. Status stays `inbox` until then.

## Closure (2026-10-03)

Acceptance is met and recorded. Implemented in PR #66 (merged 2026-10-02): `src/gpu_admission.py`, the worker `health` `gpu_load`, router withholding in
`resolve_alias`, the canary's `not_run` / `inconclusive` path, and home's opt-in through `config/estate.yaml`; 49 new tests with mutation checks and 533 existing estate
tests unchanged; evidence in `docs/aoteru-multihost-execution-evidence.md`. It did its job live: with a game holding the GPU the admission signal read busy and
the home `local-fast` canary was not run (no false model failure); once the game was stopped the canary passed 3 of 3 and home was qualified for `local-fast`
(PR #70). The status stayed `inbox` only because nobody updated it.

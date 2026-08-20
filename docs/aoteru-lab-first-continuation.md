---
title: Aoteru lab-first continuation
status: execution-contract
owner: odysseus
as_of: 2026-08-20
canonical_plan: docs/aoteru-estate-implementation-plan.md
---

# Aoteru lab-first continuation

Proceed with the Aoteru estate programme using the lab PC as the only currently available worker. The home worker remains registered but unavailable/unverified. Do not infer or fabricate its state, and do not block all development on its absence.

## Binding rules

1. Continue from the first executable unmet gate in the canonical P0→P10 sequence.
2. Pass only gates genuinely satisfied with the laptop/controller + lab worker.
3. Mark every home-dependent requirement explicitly `DEFERRED`, never `PASS`.
4. Maintain one compact deferred-gates list containing the exact future evidence needed to close each item.
5. Build multi-worker abstractions/config/contracts now, but validate only lab behaviour.
6. Never hard-code the lab as the permanent sole worker.
7. Do not repeatedly stop for the unavailable home PC.
8. Preserve all existing deduplication, authority, parking, security and verification rules from the canonical execution contract.

## Phase-specific interpretation

### P2
Complete and verify every private-connectivity requirement possible with laptop/controller + lab. Build the minimal authenticated `svc:aoteru` endpoint required to satisfy the P2 phone-connectivity gate; P6 adds the full mobile UX. Home connectivity remains deferred.

### P3
Implement parking, leases, remote native execution and logical session mapping end-to-end on the lab worker first. Prove conflicting writes and dirty/split-brain cases fail closed for the validated lab path. Multi-worker schema must remain host-agnostic.

### P4
Implement the memory schema/broker without pretending the unavailable home PC is an active primary. Use the safest currently available temporary authority location, explicitly recorded as lab-first/temporary. Preserve schema/config/migration paths so home-primary + lab-fallback can be enabled and validated later without redesign.

### P5
Implement the laptop Claude routing skill and integration so `auto` and `lab` work now. `home` must fail truthfully as unavailable. Normal operation keeps the laptop Claude conversation as the user-facing surface while work executes natively on the lab worker.

### P6
Implement and validate the lab-backed private Aoteru mobile path where otherwise dependency-complete. Do not require the unavailable home worker for mobile UX.

### P7
Inventory and benchmark the lab hardware fully. Leave all home benchmarks and dual-host routing comparisons deferred.

### P8
Proceed with host-independent domain convergence and removal/wrapping of duplicated neutral capabilities. Do not introduce assumptions that require the home worker to exist.

### P9
Run every applicable single-worker/lab fault and security test. Explicitly defer dual-worker, home-offline-primary/failover and second-host verification tests that cannot be honestly exercised.

### P10
A successful current cutover may be labelled only `LAB-FIRST CUTOVER`, never full-estate completion. Full-estate completion remains blocked until the deferred home-dependent gates pass.

## Human escalation

Do not ask the operator to regain home-PC access merely to preserve chronology. Escalate only for a human-only action that blocks the current lab-first critical path under the existing four-part escalation test.

## Start

Read the canonical plan, `docs/aoteru-estate-execution-contract.md`, current progress/evidence, and this contract. Preserve completed P0/P1 work, reconcile the current partial P2 state, then continue autonomously through every executable lab-first phase.

Initial response only:

`PHASE | STATE | DEFERRED | NEXT GATE`

Then work autonomously; do not wait for `continue`.
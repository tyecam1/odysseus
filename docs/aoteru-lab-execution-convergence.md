---
title: Aoteru lab execution convergence
status: execution-contract
owner: odysseus
as_of: 2026-08-21
parent: docs/aoteru-long-horizon-sonnet-followup.md
---

# Aoteru lab execution convergence

Continue Aoteru/Odysseus from the current `dev` HEAD. This is a focused convergence pass after an independent repository review. Do not redesign the architecture, restart P0–P10, or trust previous PASS labels. Inspect current code first, reproduce each finding, fix only defects that are real, and record evidence.

## Independent review findings to verify and converge

1. Correct stale P10/operator documentation: GitHub durability is now achieved.
2. Do not install the existing `odysseus-ui.service` unchanged. Build a dedicated lab service for the canonical Aoteru backend using:
   - `User=agent`;
   - `/home/agent/projects/odysseus-aoteru`;
   - the correct venv/environment;
   - `127.0.0.1:7001` only;
   - the existing isolated ChromaDB on `8101`;
   - no `0.0.0.0` exposure;
   - sensible restart/startup behaviour.
   Prepare and verify it before requesting the one sudo install action from the operator.
3. Harden host eligibility: routing must require explicit worker role plus verified, healthy and reachable/available state. A newly reachable but unverified home host must never become eligible automatically.
4. Fix `LogicalSession` lifecycle: failed or non-launched Claude sessions must not remain active; add minimal reconciliation/cleanup semantics.
5. Reassess parking. The DB uniqueness constraint is good, but heartbeat renewal/stale lease handling and technical write enforcement are incomplete. Implement the smallest robust mechanism consistent with the existing architecture; do not create a second lease authority.
6. Close the major execution gap: `estate_router` currently resolves routes but does not execute them, and `agent claude` stops before native launch. Implement one provider-neutral bounded execution/result path for a real local Ollama task first. Preserve deterministic-first and parking/domain gates. Do not invent Claude/Codex execution if unavailable.
7. Routing remains intentionally shallow. Implement only the minimum necessary next layer now: validate all requested capabilities rather than only the first, respect explicit host/quality/context/budget constraints where evidence exists, and fail truthfully where it does not. Do not fabricate quality floors.
8. Run the actual repository test suite, not only the focused 46 tests, plus focused tests and a live lab end-to-end smoke:

```text
task envelope
-> authority/host/model resolution
-> local model execution
-> deterministic verification/result
-> persisted telemetry
```

9. Reconcile evidence/docs so the state is labelled accurately. Do not call this `LAB-FIRST EXECUTION CUTOVER` unless that end-to-end path genuinely works.
10. Preserve home/interface/mobile/cross-repo P8 work as `DEFERRED` where still physically unavailable.
11. Read and retain `docs/aoteru-lab-local-model-strategy-2026-08-20.md`, but do not indiscriminately download models. Once execution plumbing is sound, leave the benchmark programme as the next bounded work package.

## Method

Before coding, inspect the relevant implementation and challenge each finding. If any finding is wrong, demonstrate why with code or live evidence instead of changing code unnecessarily.

Use fresh-context independent verification after substantive fixes. Keep changes minimal and cohesive. Extend existing Odysseus ownership surfaces; do not introduce another router, queue, lease authority, model registry or execution framework.

Commit cohesive changes to `dev` and push once verified.

## Stop conditions

Stop only at one of:

- verified `LAB-FIRST EXECUTION CUTOVER`;
- a genuine human-only sudo/credential/hardware blocker;
- usage limit.

## Final report

Report only:

- verified state;
- defects confirmed and fixed;
- tests/live evidence;
- remaining deferred items;
- exact human action if one is required;
- HEAD SHA.

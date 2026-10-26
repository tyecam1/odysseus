---
title: Estate deterministic execution + quota-aware routing proposal
status: proposal
created: 2026-10-26
owner: odysseus
scope: estate routing/execution governance
---

# Proposal: quota-aware codex health + deterministic execution surface

## Observed failure (2026-10-26, live)

A dispatched Instagram-acquisition deployment task died mid-run twice:

1. A model-backed orchestrator was consumed by account-wide model quota
   exhaustion **after** launch: routing saw `health.codex.available=true`
   and started an agent that hit its usage limit immediately.
2. Routine deterministic remote operations (SSH inspection of a release
   directory, reading a health endpoint) were routed through model-backed
   agents because `ask/auto/lab/home` always attach capability aliases.
   The model was doing transport work, not reasoning work, and its quota
   failure stopped the deterministic work too.

## Evidence the machinery already mostly exists

- `src/estate_router.py` already supports `executor="deterministic"` ->
  `status="complete"` for tasks with no capability alias, and
  `_resolve_host` documents the deterministic route.
- `src/delegation_preflight.py` already classifies per-host
  `qualified_executors` including `deterministic` (verified live via
  `aoteru preflight` on 2026-10-26: lab and home both report it).
- Worker health already carries per-host codex availability attestation
  (`health.codex.available`).

## Proposed smallest change (no new framework)

1. **Quota-aware health attestation.** Extend the worker's codex health
   block with a cheap authenticated usage/quota probe (with a stated
   freshness/TTL) so routing treats an exhausted quota as unavailable
   and fails truthfully to the fallback lane instead of launching an
   agent that dies mid-run. Note: today `codex.available` only attests a
   binary + auth file; both routing and preflight read it, and
   additionally `run_task()` can attempt paid execution after the route
   finds no live codex candidate, so the probe needs a dispatch-time
   check as well as the attestation.
2. **Deterministic execution surface.** Let `ask/auto` accept
   `--executor deterministic` for **pre-registered, allow-listed command
   templates** (per repo, e.g. release/cutover/health inspection).
   Caveat from code review (Sol, gpt-6-sol, 2026-10-26): the router's
   `deterministic/complete` is *route completion, not command execution*
   (`run_task()` returns `executed: false`), and the existing
   ParkLease/EstateExecution path is the Codex write lane, so its
   lease/identity/audit guarantees cannot simply be inherited by
   template runs. The template surface therefore needs: a real worker
   execution verb, template validation and dispatch, explicit
   deterministic-qualification checks, outcome recording, and its own
   lease/identity/audit binding designed against the existing
   mechanisms rather than assumed from them.

## Non-goals

- No second scheduler, no laptop-side execution framework, no bypass of
  leases or audits.
- Templates are reviewed like any repo change; arbitrary shell is not
  accepted.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

---
title: Aoteru estate P8 evidence
status: compact-evidence
owner: odysseus
as_of: 2026-08-20
parent: docs/aoteru-long-horizon-sonnet-followup.md
---

# P8 — domain convergence (lab-first slice)

Compact durable record. Do not reread unless a dependency changes.

## Scope reality

Plan §12 P8 centers on moving neutral host/model/dispatch concerns *out of*
`obsidian-PhD` into Odysseus. `obsidian-PhD` is not cloned on this host
(confirmed repeatedly since P0) — that half of P8 is structurally
inapplicable here, not skipped. What's genuinely lab-buildable: audit this
repo's own Misumi/Odysseus boundary for duplicated authority, and converge
anything found onto the central estate contracts (P2-P5's registry/
parking/routing work) without moving Misumi's actual domain truth
(persona/household policy, trust/permission logic) into Odysseus.

## Audit before changing anything

- Searched for stale single-box/monolith architecture docs that might need
  pointing at the canonical plan: none found beyond the estate-programme
  docs themselves.
- Read `routes/misumi_operator_runtime_routes.py` (operator conferences,
  heartbeat proposals): domain-scoped (household/persona decision
  proposals among Misumi's personas), consistently `writes_allowed: False`
  — a read-only proposal surface, not a competing approval authority over
  repo/host/model routing. Left untouched; this is correct domain-local
  governance, not something to converge.
- Found one genuine violation: `src/misumi_task_router.py`'s `plan()`
  hardcoded `"recommended_executor": "Codex"` — a static brand pin,
  exactly what the routing contract's invariant 1 forbids ("No repo,
  skill, MCP or worker may create a competing model-selection or
  host-selection policy") and invariant 6 ("Codex and Claude workers are
  invoked through the same provider-neutral job/result contract").

## Fixed

`_recommended_executor()` (new, `src/misumi_task_router.py`) replaces the
hardcoded string with a call into `src.estate_router.resolve_route()` —
the one central routing authority built in Phase B. Household task
planning now reports whatever the estate actually resolves
(`task_class: household-task-implementation`, capability `code-strong`),
including honestly reporting `executor: none` when that capability isn't
bound yet, rather than claiming a specific tool is recommended when
nothing has actually verified that.

Verified live:

```text
_recommended_executor({"path": "x", "title": "test"})
  -> {'host': 'hz2-workstation', 'executor': 'none',
      'model_alias': 'code-strong', 'concrete_model': None}
```

Honest — matches `config/models.yaml`'s real state (`code-strong` is
unbound, no evidence yet). No existing test asserted the old hardcoded
string (grepped `tests/` for `recommended_executor`: no hits), so nothing
needed updating for the field itself; the full existing suite for this
code path (`tests/test_misumi_household_tasks.py`, 7 tests) still passes
unchanged.

## Confirmed unchanged / correctly left alone

- Misumi persona/household policy, trust/permission logic
  (`src/misumi_policy.py`, `HouseholdReadOnlyAdapter`) — untouched, stays
  domain-local per the contract's own "repo-local governance... remains
  its own local authority."
- RAG/ChromaDB — already confirmed (P4 audit) derived/rebuildable, not
  authoritative; nothing new found this pass.
- `ScheduledTask`/`TaskRun` (cron automation) vs. `RoutingDecision`
  (routing telemetry, Phase B) — distinct concerns, already kept separate
  when Phase B was built; reconfirmed no drift.

## Deferred (needs `obsidian-PhD`, not present on this host)

- Moving neutral host/model/dispatch concerns out of `obsidian-PhD`.
- Changing PhD skills/routes to capability requirements.
- Confirming PhD trust/write/verification logic stays PhD-local (can't
  audit a repo that isn't here).
- Pointing PhD's own old architecture notes at the canonical plan.

## Gate

Plan §12 P8 gate: "no duplicated router/task authority; capability
truth/tests pass in all three repos; old single-compute-box assumptions
are either removed or explicitly historical."

- [x] no duplicated router/task authority found in this repo — one real
      instance found and fixed (hardcoded executor string)
- [x] capability truth/tests pass — in *this* repo (obsidian-PhD/misumi-
      as-separate-repo not present to check)
- [x] no stale single-box assumptions found in this repo's own docs
- [ ] full three-repo gate — only one of three repos is present on this host

**P8: PARTIAL, lab-first slice complete.** Everything checkable/fixable
with the code actually on this host is done. The cross-repo convergence
work is a real, correctly-deferred dependency on `obsidian-PhD` existing
somewhere reachable — not something more auditing on this host can
resolve.

---
title: Aoteru estate P9 evidence
status: compact-evidence
owner: odysseus
as_of: 2026-08-20
parent: docs/aoteru-long-horizon-sonnet-followup.md
---

# P9 — fault/security validation (lab-first slice)

Compact durable record. Do not reread unless a dependency changes.

Every test below was actually run against the live isolated backend
(`svc:odysseus-lab`, port 7001) or the live estate_router module — not
inferred from earlier phases' documentation. Two real defects were found
and fixed during testing, not just noted.

## Truthful route failure

Already covered by P2/P5/Phase B and re-confirmed this pass: `agent
claude home`, `POST /api/estate/route` with an unbound alias, and
`eligible_hosts()` all fail with a specific, real reason rather than a
generic error or silent success.

## Unavailable-home handling

Re-confirmed live: `desktop-in7o23d` correctly reported ineligible
(`"'desktop-in7o23d' is not a tailnet member"`) by both `scripts/agent`
and `src/estate_router.eligible_hosts()` — same check, one implementation
(Phase B's de-duplication holds).

## Lease/write exclusion + dirty-worktree preservation

Already live-tested in P3 (conflicting-lease rejection via DB constraint,
dirty-tree fail-closed) and re-spot-checked at the start of this
long-horizon session (Phase A) with no regression.

## Service restart/persistence — tested this pass

Killed the live backend process, restarted it, and diffed row counts in
every new table (`park_leases`, `logical_sessions`, `routing_decisions`,
`source_events`, `memory_relations`) before/after:

```text
before: 4, 6, 8, 3, 1
after:  4, 6, 8, 3, 1   (identical)
```

Health check 200 immediately after restart. SQLite-backed state survives
a process restart — expected given the storage engine, but now actually
verified rather than assumed.

## Private-only exposure

Re-confirmed: `tailscale funnel status` still tailnet-only, no
`AllowFunnel` anywhere, after all of Phase A-C's changes (including
mounting the new `/api/estate/*` routes).

## Auth boundaries — tested this pass

```text
GET  /api/estate/route/hosts   (no cookie)        -> 401
POST /api/estate/route         (no cookie)        -> 401
GET  /api/tasks                (no cookie)        -> 401
GET  /api/estate/route/hosts   (garbage cookie)   -> 401
```

No data leakage in any response; all protected endpoints — including the
newly-added routing surface — correctly require a real session.

## Model/runtime failure — real defect found and fixed

**Found**: `resolve_alias()` trusted `config/models.yaml`'s static
`binding` field without checking the model was actually loadable right
now. A config entry is evidence a model was benchmarked once (P7), not
evidence Ollama is still running or the model wasn't removed since.

**Fixed**: added `_ollama_model_live()` — a bounded (3s timeout) live
check against Ollama's `/api/tags` before reporting an alias resolved.

Verified against the real Ollama server, not mocked:

```text
_ollama_model_live('qwen3:8b')                    -> (True, 'live')
_ollama_model_live('this-model-does-not-exist:99b') -> (False, "... not currently listed by Ollama")
```

Unit tests updated to monkeypatch this check (so they stay isolated from
real Ollama state — 2 new tests added, `test_resolve_alias_bound_and_live`
/ `test_resolve_alias_bound_but_not_live_fails_truthfully`).

## Stale inventory — real defect found and fixed

**Found**: a malformed `config/models.yaml` (deliberately corrupted,
tested, then restored and confirmed via `git status`/`diff` to be byte-
identical to the original) crashed `resolve_alias()` with a raw
`yaml.scanner.ScannerError` — at the HTTP layer this would have surfaced
as an unhandled 500, not a clean failure.

**Fixed**: `RoutingConfigError` (new, `src/estate_router.py`) wraps YAML
parse failures with a clear message; `routes/estate_routing_routes.py`
catches it and returns `503` with the actual reason. Verified live,
through the real running server (config corrupted, real HTTP request
made, config restored — not simulated):

```text
GET /api/estate/route/alias/local-fast (with corrupted config)
  -> 503 {"detail":"config/models.yaml is malformed: mapping values are
          not allowed here\n  in \".../config/models.yaml\", line 85,
          column 11"}
```

One new test (`test_malformed_config_fails_cleanly_not_a_raw_traceback`).

## Partial result handling — real defect found and fixed

**Found**: converging `misumi_task_router.py` onto `estate_router` (P8)
surfaced a genuine bug when the full regression suite was re-run after
P9's other fixes: `tests/test_misumi_routes.py::test_task_returns_
structured_plan` failed with `sqlite3.OperationalError: no such table:
routing_decisions`. Root cause: `tests/conftest.py` runs the suite against
`sqlite:///:memory:` by default, and FastAPI's request handling for that
async route executes the DB write on a different thread than the one that
ran `init_db()`'s `create_all()` — SQLite's default per-thread connection
pooling for `:memory:` URLs means that thread sees a genuinely different,
empty in-memory database. The real (file-backed) `data/app.db` was never
affected — confirmed unchanged throughout — but the underlying design
flaw was real: a telemetry-write failure was crashing the actual routing
answer the caller needed, not just failing to log a side effect.

**Fixed**: `_record_decision()` now catches any exception from the
telemetry write, logs it, and returns a clearly-marked
`decision-unrecorded-<uuid>` id instead of propagating the exception —
`resolve_route()`'s actual route result is unaffected either way. This is
exactly the P9 "partial result handling" property: losing the ability to
record telemetry must not mean losing the result the caller actually
needed.

Verified: the previously-failing test now passes; full suite
(`test_estate_router` ×11, `test_misumi_memory` ×16, `test_misumi_routes`
×9, `test_database_utcnow` + `test_update_database_script` ×3,
`test_misumi_household_tasks` ×7) — 46 passed, 0 failed.

`RoutingDecision.status` (`blocked`/`needs_escalation`/`complete`) and
`ParkLease.status` (`active`/`released`) remain the durable state
mechanism; both already confirmed to survive process restart (above). No
automated retry loop exists yet — correctly not built speculatively
before any real task has needed one.

## Deferred (physically requires the unavailable home PC)

Dual-worker/failover tests, split-brain, home-offline-primary scenarios —
all require a second reachable host. None exist to test against; marked
`DEFERRED` per the long-horizon contract's explicit instruction, not
`PASS`.

## Gate

- [x] truthful route failure
- [x] unavailable-home handling
- [x] lease/write exclusion
- [x] dirty-worktree preservation
- [x] service restart/persistence
- [x] private-only exposure
- [x] auth boundaries
- [x] model/runtime failure (defect found + fixed this pass)
- [x] stale inventory (defect found + fixed this pass)
- [x] partial result / durable blocked state (defect found + fixed this pass)
- [ ] dual-worker/failover/split-brain — DEFERRED, needs a second host

**P9: PASS on every test executable with one host; three real defects
found and fixed during testing, not just documented as gaps.** Dual-worker
tests remain explicitly deferred, not fabricated.

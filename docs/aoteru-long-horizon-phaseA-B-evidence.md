---
title: Aoteru long-horizon Phase A/B evidence
status: compact-evidence
owner: odysseus
as_of: 2026-08-20
parent: docs/aoteru-long-horizon-sonnet-followup.md
---

# Phase A — deep review (before further implementation)

Compact durable record. Do not reread unless a dependency changes.

## Git/state reconciliation

- `HEAD` at session start: `eedad2f` (merge of `origin/dev` — `f2b8510`,
  `c1abe47` — into local `dev`, no file overlap with prior local work).
- Push re-tested: still fails (`fatal: could not read Username for
  'https://github.com'`). **Correction to the doc's own hint** ("may now
  be resolved"): not established as resolved — re-checked directly. New
  since last session: `gh` CLI now exists at `/snap/bin/gh` (wasn't found
  before), but `gh auth status` reports not logged in. Progress toward a
  fix, not a fix — recorded as observed, not assumed.
- Working tree clean at every check this phase (`git status --short`
  empty before and after each commit).

## P0–P7 re-challenge (P6/P7 specifically, per instruction — they lacked
## the fresh-context verification P0–P5 had)

Re-verified directly (deterministic checks, not re-litigated from prose):

- Backend (`svc:odysseus-lab`, port 7001) still running, still healthy,
  still auth-enforced, still isolated from the untouched upstream (port
  7000, separate ChromaDB on 8100 vs. this instance's own 8101).
- Tailnet exposure still private-only: `tailscale serve status --json`
  has no `AllowFunnel` key; `funnel status` still reports tailnet-only.
- Tailnet peers unchanged: `desktop-in7o23d` (home) still absent under
  either spelling; `glovebox` still offline (33d now); `desktop-7dj1hma`
  (interface) still online.
- **P6 re-challenged**: re-ran the exact live check from the P6 doc
  (fresh login, `GET /api/tasks` via the real tailnet URL) — still 200,
  11 tasks. Claim holds.
- **P7 re-challenged**: `ollama list`-equivalent re-run — all 6 models
  from the P7 doc still present, nothing changed. The benchmark *numbers*
  themselves are point-in-time measurements, not independently
  re-derivable to the same figure, but the underlying claim (these models
  exist, are installed, no download was performed) is re-confirmed.
- P3 (parking) re-tested live: no stale active lease existed; a fresh
  park → conflicting-park-rejected → release cycle still behaves exactly
  as the P3 evidence describes.
- No false PASS states found. No topology drift found beyond what's
  already recorded (P2's interface/home correction stands; nothing new
  came online).

## New-contract impact on prior conclusions

`docs/aoteru-model-host-routing-contract.md` does **not** invalidate any
P0–P7 conclusion. It adds a genuinely new central-routing requirement on
top of them. Before writing any Phase B code, audited (fork,
bounded/grep-first) whether adequate routing/selection machinery already
exists anywhere in the app — the routing contract's own invariant 1 ("No
repo, skill, MCP or worker may create a competing model-selection or
host-selection policy") makes this audit load-bearing, not optional.

**Found and confirmed by direct follow-up reads:**

| mechanism | role | Phase B relationship |
|---|---|---|
| `core.database.ModelEndpoint` | live per-endpoint model *inventory* (discovery only, no selection logic) | KEEP — extend as the live-registry input, not duplicated |
| `src.llm_core` (2839 lines) | provider-call/transport layer; takes an already-decided model, doesn't choose one | KEEP — routing resolves a route, `llm_core` still makes the actual call |
| `src.model_capabilities` | model-property taxonomy (modality/reasoning mechanism), a different sense of "capability" than the contract's routing aliases | KEEP — reusable signal, not a routing mechanism itself |
| `src.teacher_escalation` | real, working single-hop evidence-triggered escalation (regex failure gate → configured teacher model, chat-turn-scoped) | KEEP — its deterministic-gate pattern informs Phase B's escalation logic; not duplicated, not replaced |
| `src.misumi_task_router` | persona/household task-file dispatch — unrelated to model/host routing despite the name | untouched; out of scope |
| `routes/task_routes.py` `ScheduledTask`/`TaskRun` | cron/event automation — a different concern from ad-hoc routing decisions | untouched; `RoutingDecision` (new) is deliberately not a second version of this |
| capability-alias resolver, host-eligibility+scoring, routing-policy config, per-route telemetry | **confirmed absent** anywhere (grepped for "capability", "alias", "escalat", "quality_floor", "telemetry" across src/core/routes/services before concluding) | genuinely **NEW** — built in Phase B below |

# Phase B — central model+host routing authority

## Built

- `config/routing.yaml` (**new** surface, per the contract's own
  "Implementation placement" list — confirmed nothing existing owns
  policy/quality-floors/budgets): host-eligibility intent, escalation
  triggers, quality floors (null — no evidence yet), budget defaults,
  verification preference order, exploration flag (`false` — no route
  history exists to explore against yet).
- `config/models.yaml` updated: alias names changed `general-fast/
  general-strong` → `local-fast/local-strong` to match the routing
  contract exactly (same concept, contract is now binding architecture).
  Two aliases bound with real P7 evidence (`local-fast` → `qwen3:8b`,
  `local-strong` → `gpt-oss:20b`); `embedding`/`reranker` bound
  structurally (they *are* embedding/reranker models, no retrieval-quality
  benchmark yet); `code-fast`/`code-strong`/`reasoning-strong`/`vision`
  stay `null` — no evidence, no binding, per the same "unearned false
  completion" rule P1 already established.
- `core.database.RoutingDecision` (new table): one row per routed task —
  task_class/host/executor/model_alias/concrete_model/status/etc.
  Explicitly documented as *not* a second job/queue (`ScheduledTask`/
  `TaskRun` stay the automation system).
- `src/estate_router.py` (new module) — the routing authority itself:
  - `eligible_hosts(repo_id=None)`: hard host filter — interface role
    excluded (invariant 9), reachability via the *same* function
    `scripts/agent` uses (imported, not reimplemented — see below), plus
    a ParkLease conflict check when `repo_id` is given (invariant 10:
    routing never widens write authority).
  - `resolve_alias(alias)`: WHAT half, resolves against
    `config/models.yaml`'s evidence-backed bindings only.
  - `resolve_route(task)`: the routing API — host before model
    (invariant 2), records every decision (even blocked/failed ones) to
    `routing_decisions`.
- `routes/estate_routing_routes.py` (new, thin — no logic of its own):
  `POST /api/estate/route`, `GET /api/estate/route/hosts`,
  `GET /api/estate/route/alias/{alias}`. Mounted in `app.py` as an
  Odysseus-neutral surface, separate from the Misumi compatibility router.
- **Eliminated a duplication before it could drift**: `scripts/agent`'s
  `cmd_claude` (P5) had its own copy of the host-reachability check.
  Refactored `src/estate_router.host_reachable` to be the one place this
  logic lives; `scripts/agent` now imports it. A second, slightly-
  different reachability rule would itself have been exactly the kind of
  duplicate authority this contract's invariant 1 forbids.

## Verified live (through the real HTTP API, tailnet URL, not just unit tests)

```text
GET /api/estate/route/hosts
  -> hz2-workstation: eligible=true, reason="this host"
     desktop-in7o23d: eligible=false, reason="'desktop-in7o23d' is not a
       tailnet member" (home fails truthfully, same real check P2/P5 used)

GET /api/estate/route/alias/local-fast
  -> resolved=true, concrete_model="qwen3:8b", evidence pointer included

POST /api/estate/route {task_class: coding-verify, capabilities: [local-fast]}
  -> ok:true, route.executor="local", route.concrete_model="qwen3:8b",
     decision_id recorded

POST /api/estate/route {task_class: research-verify, capabilities: [reasoning-strong]}
  -> ok:false, route.executor="none", alias_resolution.resolved=false
     (unbound alias fails truthfully — not silently defaulted to
     something, not fabricated success)
```

`routing_decisions` table confirmed created via `sqlite_master` schema
dump; row count grew with each test call above.

Also: `scripts/agent claude home/lab` re-tested after the
`host_reachable` refactor — identical behavior to before (home fails
truthfully, lab resolves and hits the same honest claude-binary-missing
boundary from P5).

## New test coverage

`tests/test_estate_router.py` — 9 tests, isolated from real config drift
via a fixture config dir (doesn't depend on this machine's real hostname/
tailnet state): interface-role exclusion, this-host-reachable-by-
construction, home-fails-truthfully, bound/unbound/unknown alias
resolution, and three `resolve_route` outcomes (deterministic/bound/
unbound). All pass, plus the full existing suite re-run
(`test_database_utcnow`, `test_update_database_script`,
`test_misumi_memory`, `test_misumi_routes` — 28 passed, unchanged).

## Deferred (genuinely, not busywork)

Per the acceptance-criteria list, honestly not attempted this pass:

- **Scoring among multiple eligible hosts** — only one worker role is
  ever reachable (lab); `eligible_hosts()` is built to support scoring a
  field of more than one, but there's nothing to score against yet.
- **Codex/Claude worker invocation through the routing contract** — no
  Codex/Claude endpoint is configured in this isolated instance (no
  `ModelEndpoint` rows for a paid provider), and per P5 there is no
  `claude` binary in this environment at all. `resolve_alias` correctly
  reports "no evidence-backed binding" for those aliases rather than
  fabricating a call.
- **Shadow/canary evaluator, replay comparison, recency-weighted
  re-scoring** — meaningless with the ~6 telemetry rows this pass
  generated; needs real accumulated traffic first.
- **Cross-provider independent verification** — needs at least two live
  model providers; only local Ollama exists here.
- **Home re-entry procedure** — correctly not run; home isn't reachable.

## Exit statement (Phase A/B)

- **Confirmed passes**: P0–P5 stand as independently verified; P6/P7
  re-challenged directly and hold; tailnet/backend/parking state all
  re-verified live and unchanged; new Phase B routing authority built,
  live-tested via real HTTP calls, unit-tested, and integrated into P5's
  existing dispatch path (eliminating a duplication rather than
  tolerating it).
- **Corrected defects**: none found in prior phases this pass (P0–P5's
  earlier self-caught corrections already stand from before); one
  duplication risk (host-reachability logic) caught and fixed *during*
  this phase, before it was ever actually inconsistent.
- **Deferred gates**: unchanged from before (interface-PC/home-PC/phone
  dependencies for P2/P5/P6), plus the Phase B items listed above.
- **First executable unmet gate**: P8 (domain convergence) — lab-buildable
  now, not blocked on the interface/home dependencies.

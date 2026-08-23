# Aoteru/Odysseus operating handbook

Workstream K's "minimal operating handbook covering normal use, experiment
reservation, recovery and host re-entry"
(docs/aoteru-long-horizon-autonomous-convergence.agent-task.md). Points at
the real commands/scripts rather than re-explaining them — each links to
the file that's the actual authority, so this doc can't drift out of sync
with what the code does.

## Normal use

**From a repo checkout (lab or any host with one):**

```
scripts/agent status          # host + repo + service + capability + memory-source snapshot
scripts/agent where           # current repo's registry identity + lease
scripts/agent explain <alias> # "why this route?" — resolution, host eligibility, real production evidence
scripts/agent park <repo_id>  # acquire a write lease before mutating a registered repo
scripts/agent heartbeat <repo_id>   # renew a lease periodically during long work
scripts/agent release <repo_id>
scripts/agent claude auto "<task>"  # resolve + dispatch a Claude session
```

**From a laptop with no checkout at all:** see
`companion/laptop_client/README.md` — one file (`aoteru.py`), no install,
`status`/`route`/`ask` against a running backend over its REST API. Not
yet a replacement for `scripts/agent`'s park/release/heartbeat (no HTTP
surface for those exists yet, see
docs/aoteru-autonomous-programme-state.md workstream B).

**Programmatic job submission** (from any authenticated caller, including
the laptop client): `POST /api/estate/route` (dry-run) and
`POST /api/estate/run` (execute) — `routes/estate_routing_routes.py`.
Requires an API token scoped `estate:read` (route only) or
`estate:execute` (route + run), or an operator's own session cookie.

## Experiment reservation

Robotics/experiment work on the lab GPU takes priority over background
inference automatically — `src/estate_router.py`'s
`experiment_priority_active()` checks `~/.aoteru/experiment_reservation.json`
(host-local, never committed) and live non-Ollama GPU memory via
`nvidia-smi`. `config/models.yaml` tags `local-strong`/`reasoning-strong`/
`vision` as `gpu_priority: yield_to_experiment` — those three fail
truthfully while an experiment is reserved; `local-fast`/`code-fast` are
never yielded. To reserve: write
`~/.aoteru/experiment_reservation.json` (see that function's docstring for
the exact shape) before starting experiment work, and remove it when done.

## Recovery

**Cold reboot** (an authorised `sudo reboot` of the lab host):
`docs/aoteru-cold-reboot-checklist.md` is the exact one-human-action-plus-
one-command procedure. The command is
`scripts/cold_reboot_verify.py` — checks systemd, app liveness/readiness,
Ollama, ChromaDB, Tailscale stays private-only, and no stale ParkLease.

**A stuck/stale ParkLease:** `scripts/agent park <repo_id>` auto-reclaims
a lease whose holder crashed without releasing
(`core.database.park_lease_is_stale`) — you don't need to touch the
database by hand.

**Routing/paid-execution failures:** `src/estate_router.py`'s
`execute_local()` already retries transient transport failures (connection
refused/reset, timeout) once before failing; a deterministic upstream
rejection (bad request, model not found) never retries. `execute_codex()`
(the paid lane) never retries automatically — a paid prompt is never
repeated blindly. `scripts/agent explain <alias>` shows current
eligibility/evidence if a route looks wrong.

## Memory

Day-to-day capture/recall goes through `src/misumi_memory.py`
(`MisumiMemory.capture`/`glance`/`loops`) — see
`routes/misumi_routes.py` for the HTTP surface. To move lab-accumulated
memory into a future home-primary (or any other target root) without
duplicating anything already moved:

```
venv/bin/python scripts/memory_promote_replay.py --target <destination misumi memory root>
```

Safe to run repeatedly — see `src/memory_outbox.py`.

## Host re-entry (home, once reachable)

```
venv/bin/python scripts/home_reentry_inventory.py   # read-only: hardware, Tailscale, Ollama models, config roots, matching services
```

Reachability alone never implies trust or promotion — registering a newly
reachable host in `config/estate.yaml` (and only then treating it as a
routing candidate) is a deliberate, reviewed step, not something the
inventory script or any automation does on its own. See
docs/aoteru-autonomous-programme-state.md workstream I for what's already
prepared versus what still needs the live host.

## Routing evidence / "is this alias actually any good?"

```
venv/bin/python scripts/routing_replay_evaluator.py            # table
venv/bin/python scripts/routing_replay_evaluator.py --json      # machine-readable
scripts/agent explain <alias>                                   # same evidence, scoped to one alias, plus host eligibility
```

`src/routing_evaluator.py` aggregates real `RoutingDecision` telemetry —
`evidence_sufficient: false` means fewer than `EVIDENCE_THRESHOLD` (20)
recorded decisions exist for that route; treat its rates as noise, not a
basis for a config change, until more real traffic accumulates.

## What's not here yet

Cross-repo work outside this repo (`misumi`, `obsidian-phd`,
`s2-e1-ros2-measurement-spine`) needs either a reachable clone or
operator-confirmed remotes — see
docs/aoteru-autonomous-programme-state.md workstream F. Glovebox Jetson
and interface-PC/mobile front-door work are prepared as deployable
artefacts but not live — see workstreams G and H in the same file.

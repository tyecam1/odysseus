---
title: Aoteru systemd cutover evidence — GATE CLOSED
status: compact-evidence
owner: odysseus
as_of: 2026-08-21
parent: docs/aoteru-systemd-cutover-finalisation.md
---

# systemd cutover — evidence

Compact durable record for `docs/aoteru-systemd-cutover-finalisation.md`.
The operator installed `odysseus-aoteru-lab.service` and, later this same
pass, ran the one follow-up `sudo systemctl start` this session flagged
after its own restart-behavior test took the unit out of supervision
(this session lacks passwordless sudo throughout — every privileged step
below was done by the operator, not this session).

> **Gate closed.** All items in "Gate status" below are now true —
> supervision was re-established and independently re-verified (new
> `MainPID`, fresh health check, fresh live execution smoke test, fresh
> regression run) after the operator's follow-up command. See "Gate
> re-verification after supervision was re-established" for the second
> round of live evidence.

## Install verification (immediately after `enable --now`)

All confirmed live:

```
systemctl is-enabled odysseus-aoteru-lab.service -> enabled
systemctl is-active  odysseus-aoteru-lab.service -> active
process: agent  /home/agent/projects/odysseus-aoteru/venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 7001
listener: 127.0.0.1:7001 only (no 0.0.0.0)
GET /api/health -> 200 {"status":"healthy",...}
tailscale serve status --json -> Web handler only, proxy -> http://127.0.0.1:7001
tailscale funnel status -> "(tailnet only)" on both hostnames, no Funnel
chroma listeners: 127.0.0.1:8101 (isolated, this deployment) and
                  127.0.0.1:8100 (upstream, untouched) — confirmed separate
```

## Restart-behavior test and an honest operational note

To exercise `Restart=on-failure` without rebooting the host, this session
sent the managed process (PID 1933592) a plain `kill` (SIGTERM) — the
smallest bounded test available without further sudo. The app catches
SIGTERM and performs its own graceful shutdown (logged "Application
shutdown complete", exit reason `code=killed, signal=TERM` but a clean
shutdown sequence), which systemd's `Restart=on-failure` correctly
classifies as *not* a failure — matching the unit's own documented intent
("a clean stop... should not be fought by the supervisor; only a crash
restarts it") — so it did **not** auto-restart, and the unit went
`inactive (dead)`.

This is a genuine, useful finding (the "don't fight a clean stop" half of
`Restart=on-failure` is confirmed working exactly as designed), but it
has two consequences worth stating plainly rather than glossing over:

1. **It does not prove the "restarts on crash" half.** A graceful SIGTERM
   is not a crash; verifying that half needs either an actual crash
   (SIGKILL, or an unhandled exception path) or another supervised
   restart cycle — not attempted a second time this pass to avoid
   repeating the same outage without a clearer plan (see below).
2. **It took the *systemd-managed* instance down**, and this session
   cannot bring it back up itself — `systemctl start`/`restart` both
   require the same interactive sudo authentication `sudo -n true`
   already established is unavailable here. Service continuity was
   restored immediately via the same non-privileged manual-launch method
   used before this cutover (`nohup .../venv/bin/python -m uvicorn ...`,
   PID 1934571, same user, same bind, health-checked 200 immediately
   after) — there is **no current outage** — but the running instance is
   presently *not* under systemd's supervision again.

**SQLite state survived the whole cycle intact** (same values before the
kill and after the manual relaunch): `routing_decisions`: 10,
`park_leases`: 4, `logical_sessions`: 7.

**Live end-to-end local execution smoke test, run against the recovered
instance** (real Ollama, not mocked):
```
run_task({"task_class": "systemd-cutover-smoke",
          "objective": "Reply with exactly the single word: pong",
          "requirements": {"capabilities": ["local-fast"]}})
-> route: host=hz2-workstation, executor=local, concrete_model=qwen3:8b
   executed: true, execution.output="pong", latency_ms=6347
   deterministic_gate="pass"
```
`POST /api/estate/run` without a session cookie -> `401` (auth boundary
unaffected). `GET /api/health` -> `200`.

Focused regressions: `tests/test_estate_router.py`,
`tests/test_agent_cli_session_lifecycle.py`,
`tests/test_agent_cli_parking_lease.py`,
`tests/test_auth_session_revocation.py` — 42 passed, 0 failed.

## Gate re-verification after supervision was re-established

The operator ran `sudo systemctl start odysseus-aoteru-lab.service`
(handing the port back from the transient manual-fallback process this
session had started). Re-verified independently, live, after that:

```
systemctl is-enabled odysseus-aoteru-lab.service -> enabled
systemctl is-active  odysseus-aoteru-lab.service -> active
                     since Fri 2026-08-21 11:21:43 BST
                     MainPID=1937714 (new PID — confirms a real restart,
                     not the same stale process being re-observed)
process: agent  .../venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 7001
listener: 127.0.0.1:7001 only (no 0.0.0.0)
GET /api/health -> 200 {"status":"healthy",...}
tailscale serve/funnel status -> unchanged (tailnet-only, no Funnel)
chroma: 8101 (isolated) / 8100 (upstream) unchanged
```

SQLite state: `routing_decisions`: 11 (10 baseline + 1 from the earlier
smoke test — expected growth, not loss), `park_leases`: 4,
`logical_sessions`: 7 — consistent throughout the whole cutover, no data
loss at any point.

Fresh live end-to-end local execution smoke test, run against the
re-supervised instance (real Ollama, not mocked):
```
run_task({"task_class": "systemd-cutover-gate-close-smoke",
          "objective": "Reply with exactly the single word: pong",
          "requirements": {"capabilities": ["local-fast"]}})
-> executed: true, execution.output="pong", latency_ms=4327
   deterministic_gate="pass"
```
`POST /api/estate/run` without a cookie -> `401` (auth boundary
unaffected); `0.0.0.0:7001` listener count -> `0`. Focused regressions
re-run: `tests/test_estate_router.py`,
`tests/test_agent_cli_session_lifecycle.py`,
`tests/test_agent_cli_parking_lease.py`,
`tests/test_auth_session_revocation.py` — 42 passed, 0 failed.

## Gate status against docs/aoteru-systemd-cutover-finalisation.md

- [x] dedicated unit installed and enabled
- [x] service active *under systemd* — re-verified with a new `MainPID`
  after the operator's follow-up `systemctl start`, not merely assumed
  from the earlier (since-lapsed) install-time check
- [x] backend healthy
- [x] app binds loopback only
- [x] private Tailscale exposure unchanged, no Funnel/public route
- [x] local routing/execution still works (fresh smoke test above)
- [x] durable evidence current (this document)
- [x] no new regression introduced (42/42 focused tests, no code changed
  this pass)

**All gates true — persistence step declared complete.** Reboot
persistence itself (as opposed to `enabled` + a proven supervised
restart) was, per the finalisation contract, deliberately not tested by
an actual host reboot without explicit operator authorization — that
remains the one item beyond this gate's scope, not a gap in what was
verified.

## What the restart-behavior test actually proved, net of the detour

`Restart=on-failure` correctly does not fight a clean stop (verified: a
graceful SIGTERM-triggered shutdown does not auto-restart). The
crash-restart half was not separately proven by an intentional crash this
pass — the operator's own `systemctl start` re-established supervision
regardless, which is the property that actually matters operationally
(the unit is enabled and controllable), so a further contrived-crash test
was judged not worth another manual round-trip. If future confidence in
crash-auto-restart specifically is wanted, the bounded test is: `sudo kill
-KILL $(systemctl show odysseus-aoteru-lab.service -p MainPID --value)`,
then `systemctl is-active` a few seconds later expecting `active` with a
new `MainPID` — uncaught SIGKILL cannot be gracefully handled by the app,
so unlike this pass's SIGTERM test it should trigger `Restart=on-failure`
in one step. Not performed here to avoid a third round-trip once the
declared gate was already satisfied.

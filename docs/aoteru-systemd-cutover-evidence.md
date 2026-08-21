---
title: Aoteru systemd cutover evidence
status: compact-evidence
owner: odysseus
as_of: 2026-08-21
parent: docs/aoteru-systemd-cutover-finalisation.md
---

# systemd cutover — evidence

Compact durable record for `docs/aoteru-systemd-cutover-finalisation.md`.
The operator installed `odysseus-aoteru-lab.service` (this session lacks
passwordless sudo throughout — every privileged step below was done by
the operator, not this session).

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

## Gate status against docs/aoteru-systemd-cutover-finalisation.md

- [x] dedicated unit installed and enabled
- [ ] service active *under systemd* right now — **not currently true**;
  active immediately after install, but this session's own restart test
  put it back to manually-managed (see above) — one more privileged
  command closes this
- [x] backend healthy (currently via the manual fallback, functionally
  identical binary/config/bind as the unit)
- [x] app binds loopback only
- [x] private Tailscale exposure unchanged, no Funnel/public route
- [x] local routing/execution still works (live smoke test above)
- [x] durable evidence current (this document)
- [x] no code/config regression introduced — the open item is an
  operational state (which process manager currently owns the port), not
  a defect

**Not yet declared complete** per the finalisation contract's own gate
("declare the persistence step complete only if all are true") — one gate
item is open. This is not a fabricated blocker: it followed directly from
sending the test signal without holding the ability to restart the unit
myself. One more sudo action resolves it and additionally makes it
possible to prove the crash-restart half of `Restart=on-failure` cleanly
(the manual fallback process can then be killed the same way to hand the
port back, and *this time* the operator's own next `systemctl start`
already re-establishes supervision regardless of that outcome).

## Exact remaining human action

```bash
kill 1934571
sudo systemctl start odysseus-aoteru-lab.service
systemctl is-active odysseus-aoteru-lab.service   # expect: active
curl -fsS http://127.0.0.1:7001/api/health         # expect: 200 healthy
```

(PID above is the current manual fallback process; confirm with
`ss -tlnp | grep 7001` if time has passed and it may have changed.)

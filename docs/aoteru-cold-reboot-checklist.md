# Cold-reboot verification checklist (lab host)

Workstream J (`docs/aoteru-long-horizon-autonomous-convergence.agent-task.md`)
requires a cold-reboot verification procedure where the one human action
(the reboot itself) is sufficient to exercise a complete automated
post-boot check. This file is that procedure. Nothing in this repo reboots
the lab host — that step is always the operator's, on purpose.

## Before rebooting

1. Confirm no in-progress `ParkLease` you care about is about to go stale
   for the wrong reason — a clean reboot should `agent release` first if
   practical, though the lease staleness/reclaim path (`park_lease_is_stale`,
   `agent park`'s reclaim-on-stale behaviour) already handles a lease whose
   holder disappeared without releasing.
2. Note the current git HEAD (`git rev-parse HEAD`) so a post-boot `git
   status`/`git log` can confirm nothing moved underneath the checkout.

## The one human action

```
sudo reboot
```

## After the host comes back

```
cd /home/agent/projects/odysseus-aoteru
git status && git rev-parse HEAD   # unchanged from pre-reboot
venv/bin/python scripts/cold_reboot_verify.py
```

Optionally export a real API bearer token first
(`COLD_REBOOT_AUTH_TOKEN=...`) to exercise the full `/api/ready`
critical-subsystem judgement rather than the liveness-only fallback —
`/api/ready` is deliberately not auth-exempt (it reveals internal
subsystem detail, unlike `/api/health`), so without a token the script
still verifies the process came up, just not every critical check inside
it. Never paste the token into a shared terminal/log; `export` it in the
same shell you run the script from and unset it afterwards
(`unset COLD_REBOOT_AUTH_TOKEN`).

## What the script checks

| Check | What a failure means |
|---|---|
| `odysseus-aoteru-lab.service` active | systemd didn't bring the app back up — check `journalctl -u odysseus-aoteru-lab.service` |
| app liveness / `/api/ready` | process is up but a critical subsystem (DB, data dir, auth-bind rule) isn't — see the check's own detail |
| Ollama reachable (127.0.0.1:11434) | model backend didn't survive the reboot or hasn't finished starting yet |
| ChromaDB reachable (127.0.0.1:8101) | best-effort only — the app treats this as a runtime, not startup, dependency, so this is reported, never fatal |
| Tailscale private-only | `tailscale serve` shows a non-"(tailnet only)" route — this would mean a Funnel/public exposure regression, the one check that must never silently pass |
| Park leases | an `active` `ParkLease` row is stale — its repo will stay blocked until `agent park` reclaims it |

Exit code `0` iff every check that actually ran passed. A `SKIP` (missing
systemd, no bearer token, ChromaDB down) is reported but does not fail the
run — read the printed detail to see what wasn't exercised.

## If it fails

Fix in the order the table lists — systemd/app-liveness failures usually
cascade into everything below them, so start there rather than chasing
Ollama/Chroma/leases first.

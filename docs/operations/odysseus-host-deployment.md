# Odysseus host deployment for Misumi

## Boundary

Odysseus is the authenticated runtime/control plane. Misumi is the household-facing interface. The household repository remains canonical and read-only during Phase A.

Default deployment:

- host: `DESKTOP-IN7O23D`;
- app: `0.0.0.0:420`, reachable only through a LAN-scoped firewall rule;
- auth: enabled, with localhost bypass disabled;
- source: a clean checkout of `tyecam1/odysseus`;
- state: `%LOCALAPPDATA%\Odysseus\Misumi`, outside the source checkout;
- household root: `MISUMI_HOUSEHOLD_ROOT=C:\Users\User\Documents\flat-knowledgebase`.

Do not reuse a dirty source checkout as the deployment base. Build side-by-side, validate on a non-production port, then change the scheduled task.

## Host-local environment

Store configuration outside Git. The lifecycle script always forces `AUTH_ENABLED=true`, `LOCALHOST_BYPASS=false`, and `MISUMI_REQUIRED=true`.

```powershell
$env:MISUMI_HOUSEHOLD_ROOT = 'C:\Users\User\Documents\flat-knowledgebase'
$env:MISUMI_MODEL_HEALTH_URL = 'http://127.0.0.1:11434/api/tags'
$env:MISUMI_INTERFACE_HEALTH_URL = 'http://192.168.4.37:8770/health'
```

Create a narrowly scoped API token for the interface bridge with the `misumi_interface` profile. Keep it in the interface-box process environment as `ODYSSEUS_API_TOKEN`; never put it in `config.json` or Git.

## Lifecycle commands

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\odysseus-host.ps1 -Action Install -InstallFirewall
powershell -ExecutionPolicy Bypass -File .\scripts\windows\odysseus-host.ps1 -Action Start
powershell -ExecutionPolicy Bypass -File .\scripts\windows\odysseus-host.ps1 -Action Stop
powershell -ExecutionPolicy Bypass -File .\scripts\windows\odysseus-host.ps1 -Action Restart
powershell -ExecutionPolicy Bypass -File .\scripts\windows\odysseus-host.ps1 -Action Status
powershell -ExecutionPolicy Bypass -File .\scripts\windows\odysseus-host.ps1 -Action Health
powershell -ExecutionPolicy Bypass -File .\scripts\windows\odysseus-host.ps1 -Action Logs -Tail 120
```

`Health` checks unauthenticated liveness. It checks authenticated readiness when `ODYSSEUS_API_TOKEN` is present. The token is neither printed nor persisted.

The scheduled task requests Windows restart-on-failure and the wrapper also supervises Uvicorn directly, restarting a crashed child after ten seconds. `Stop` terminates the scheduled wrapper before stopping its listener, so an intentional stop does not relaunch the service.

## Transcript runtime switch

The durable Misumi transcript runtime (`docs/misumi-durable-transcript-runtime.md`) is off by default. Pass `-TranscriptRuntime` to `Install` (and `Run`) to enable it: the script sets `ODYSSEUS_MISUMI_TRANSCRIPT_ENABLED=1` for the service and records the switch in the scheduled task's arguments, so it is visible in the task definition and reversible by re-running `Install` without it. Each owner's transcript archive stays separately off until switched on.

## Readiness contract

`GET /api/health` proves only that the process can answer. `GET /api/ready` reports database and data-directory integrity, auth versus bind safety, household reachability, skill and scheduler availability, vector state, model health, and optional interface health.

When `MISUMI_REQUIRED=true`, household, skills, scheduler, and model checks are critical. A degraded critical check returns HTTP 503.

## Side-by-side cutover

1. Preserve the existing checkout and staged diff.
2. Install the integration checkout and virtual environment at a new path.
3. Run it on port 1420 with an isolated data directory.
4. Verify liveness, authenticated readiness, generic chat, and every `/misumi/*` smoke test.
5. Stop the test instance.
6. Install the reviewed checkout's scheduled task on port 420.
7. Confirm one listener, then point the interface box at `http://DESKTOP-IN7O23D:420/misumi`.
8. Keep the reference agent on port 4500 as rollback until the read-only eval suite passes.

Rollback restores the previous scheduled task and interface `agentUrl`. Household files are not involved.

## Boot lifecycle, recovery and maintenance

A logon-triggered, interactive task is not a lifecycle: after an unclean reboot on 2026-10-03 the household stack was down for about five hours because it only
started when someone logged in. The canonical required services are **Odysseus (`:420`) and Ollama (`:11434`)** and nothing else; the legacy host agent (`:4500`)
and its STT server (`:4600`) are not required by the durable transcript path and are deliberately outside this lifecycle.

```powershell
# Odysseus: machine-start, no interactive session required (startup trigger + S4U + start-when-available; one instance)
powershell -ExecutionPolicy Bypass -File .\scripts\windows\odysseus-host.ps1 -Action Install -BootStart <same parameters as before>
# Ollama task (machine-start, supervised) and the guard (machine start + every 2 minutes)
powershell -ExecutionPolicy Bypass -File .\scripts\windows\odysseus-guard.ps1 -Action Install
powershell -ExecutionPolicy Bypass -File .\scripts\windows\odysseus-guard.ps1 -Action Status
```

Tasks run as the same user with `S4U` (no stored credential, no network credentials, `RunLevel Limited`); nothing runs as SYSTEM. `Status` of the wrapper reports the
task's triggers and logon type so a regression to a logon-coupled task is visible.

**Recovery.** The guard probes `/api/health` and the Ollama tags endpoint; after two consecutive failures it restarts the corresponding scheduled task (Odysseus through
`odysseus-host.ps1 -Action Restart`, which follows whichever release the task points at), waits for health, and appends compact evidence to
`<DataRoot>\guard\guard.jsonl` (`kind` is `recovery`, `suppressed`, `maintenance` or `observed`). A recovery that does not come back healthy is recorded and exits 2.

**Maintenance.** Crash recovery must not fight an intentional outage. `odysseus-guard.ps1 -Action MaintenanceEnter -Reason "<what and why>" -MaintenanceHours N` writes a bounded,
auto-expiring flag (capped at 6 hours) and stops both services; while the flag is live the guard records `suppressed` and restarts nothing. `-Action MaintenanceRelease`
removes the flag and brings everything back at once. An expired flag is removed by the next pass, so a forgotten flag cannot leave the household assistant down.

The guard never stops a process other than its own two services and never terminates a user's application: GPU contention is handled by the admission signal
(refuse, yield or reroute local inference), not by closing a game. Closing a process needs an explicit, current operator instruction.

**Testing boot independence on a host that signs in by itself.** On the household host Windows signs the account in automatically, without a password prompt, about 30 seconds after
every boot (there is no `AutoAdminLogon` registry value to find; check the `4624` logon events; account details are kept in the private Misumi repository, not here). A plain reboot therefore cannot show that the stack starts without a login:
the logon trigger races the startup trigger and usually wins. To prove the startup trigger on its own, temporarily set the two tasks to the startup trigger only
(`Set-ScheduledTask -TaskName <name> -Trigger <startup trigger>`), reboot, and read the Task Scheduler Operational log (enable it with `wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true`):
the household tasks must show "launched ... due to system start-up". Then restore both triggers. The single-instance setting makes the loser of the race a harmless "did not launch ... already running" event.
Register S4U principals with the plain user name (`$env:USERNAME`); `$env:USERDOMAIN` is `WORKGROUP` on that host and fails with HRESULT 0x80070534.

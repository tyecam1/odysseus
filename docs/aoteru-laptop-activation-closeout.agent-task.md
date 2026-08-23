---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-08-23-aoteru-laptop-activation-closeout
title: "Aoteru laptop activation and final closeout"
status: ready
priority: high
task_type: finite-activation-closeout
created_by: chatgpt
created_at: 2026-08-23T20:41:00+01:00
executor: claude-sonnet-5
execution_mode: finite-laptop-origin-proof
repo: tyecam1/odysseus
branch: dev
---
# Aoteru laptop activation and final closeout

## Mission

Run from the real Windows laptop controller (`DESKTOP-7DJ1HMA` or live successor identity) and close the one remaining operator-origin proof for Workstream B.

Do **not** install the Odysseus runtime, clone the full repo for normal use, start a development loop, redesign Aoteru, or add optional features. This is an activation/proof task only.

The supported lab backend front door is the tailnet-only Tailscale Serve endpoint:

`http://dmem-hp-z2-tower-g9-workstation-desktop-pc.tail171792.ts.net:8080`

Do **not** configure the laptop to `:7001`; `127.0.0.1:7001` is the lab-local upstream behind Tailscale Serve, not the supported laptop endpoint.

## 1. Prove laptop identity and connectivity

- Record `hostname` and OS.
- Confirm the laptop is on Tailscale/private network.
- Prove the lab front door is reachable from this laptop with `/api/health` and that the response is the Odysseus/Aoteru backend rather than some unrelated service.
- If the backend is unreachable, diagnose only the transport/Tailscale path; do not modify the backend architecture.

## 2. Install the thin client without an Odysseus checkout

Prefer Windows Python launcher + pipx. If pipx is absent, install it user-local rather than requiring admin rights.

Expected path:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
py -m pipx install "git+https://github.com/tyecam1/odysseus.git@dev#subdirectory=companion/laptop_client"
```

If `aoteru` is not yet visible in the current shell after `ensurepath`, use `py -m pipx runpip`/the pipx-installed executable path or open a refreshed shell; do not clone the repo as a workaround.

Verify `aoteru --help` and `aoteru config show`.

## 3. Configure securely

Use:

```powershell
aoteru config set --url http://dmem-hp-z2-tower-g9-workstation-desktop-pc.tail171792.ts.net:8080 --token ody_...
```

The token must have `estate:execute` scope. Never print, commit, paste into logs, or echo the raw token after configuration.

If no suitable token already exists, stop only at this human credential gate and tell the operator exactly this: create one from the authenticated Odysseus token-management surface with name `laptop-controller` and scope `estate:execute`, then resume this same task. Do not bypass auth or edit the backend database directly.

## 4. Laptop-origin smoke proof

Run from the laptop, through the tailnet front door:

```powershell
aoteru status
aoteru route --capability local-fast --task-class laptop-smoke
aoteru ask "Return exactly: laptop-controller-ok" --capability local-fast --task-class laptop-smoke
aoteru park-status
aoteru park obsidian-phd --branch main
aoteru heartbeat obsidian-phd
aoteru release obsidian-phd
aoteru park-status
```

Acceptance:
- backend reachable and healthy;
- real eligible host(s) returned;
- route resolves through canonical Odysseus routing;
- local execution returns the requested result and a real routing decision/result;
- park acquires only the server-resolved registered repo path and refuses unsafe state if applicable;
- heartbeat succeeds on the active lease;
- release succeeds;
- final park-status shows no leaked active lease from this proof.

Do not mutate PhD content. Parking/heartbeat/release only.

A paid laptop-origin proof is optional because paid Codex execution was already qualified on the backend. Do not spend money merely to tick another box. Only test `--allow-paid` if a real operator need justifies it.

## 5. Close Workstream B durably

Only after the laptop-origin proof passes, update `docs/aoteru-autonomous-programme-state.md` so B changes from `ready-for-operator` to `complete`, with concise evidence containing:
- laptop hostname/OS;
- tailnet endpoint used (`:8080`);
- install path (checkout-free pipx);
- status/route/ask/park/heartbeat/release outcomes;
- relevant routing decision ID(s), if returned;
- confirmation that no raw token was recorded;
- confirmation no lease remained.

Because normal laptop operation must remain checkout-free, use one of these for the one-time documentation commit only:
1. authenticated `gh` API/file update if available; or
2. a temporary shallow clone under the OS temp directory, update only the programme-state/evidence docs, commit/push, then delete that temporary clone.

Do not leave a persistent Odysseus checkout on the laptop.

Run the focused relevant tests only if repository files were changed beyond documentation; otherwise do not duplicate the already-green 5114-test backend suite. Verify origin/dev contains the closure commit.

## Stop condition

Stop when B is `complete` and the laptop can be used via the `aoteru` command with no Odysseus checkout.

Do not resume `/loop` or create successor engineering work. Remaining D/G/H/I states remain evidence-/host-triggered exactly as recorded unless this laptop proof exposes a genuine defect.
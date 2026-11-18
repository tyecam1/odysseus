---
title: Cross-device software currency and safe update maintenance
artifact_type: agent-task
status: inbox
owner: odysseus
created: 2026-11-18
priority: normal
scope: shared estate maintenance
cadence: weekly
authority: tyecam1/odysseus
---

# Cross-device software currency and safe update maintenance

## Objective
Establish a **recurring, low-overhead update service** that discovers installed AI harnesses and frequently used software across the user's devices, safely updates eligible installations, verifies functionality, and records exceptions. Extend the existing Odysseus estate scheduler, host registry, routing and task lifecycle; do not introduce a parallel controller. This is an accepted new request but remains in **inbox** under the live shipping-first backlog policy until prioritised.

## Initial watchlist (expand only from observed usage/installations)
- **AI harnesses:** Codex CLI; Claude Code; GitHub Copilot; other *actually installed* agent CLIs (e.g. OpenCode/GLM clients).
- **Core daily tools:** VS Code; Git; Docker; Tailscale; Ollama; Obsidian; Python/Node toolchains and their installed package managers.
- Discover additional frequent-use software from verified usage, not from speculative model names. Treat AI *models/catalogue entitlement* separately from harness binaries. Do not assume all apps are installed on all hosts.

## Estate scope
Inspect the live, canonical host inventory and reconcile aliases/identities before any update:
- Windows laptop/controller (historically `DESKTOP-7DJ1HMA`).
- Windows home Odysseus/Misumi host (historically `DESKTOP-IN7O23D`).
- Lab HP Z2 workstation (`hz2-workstation`).
- Windows Misumi interface box (historically `DESKTOP-RIFPR07`).
- Jetson Orin Nano research rig (`glovebox`).
- Pixel 8 / GrapheneOS, subject to supported app-store/device-management access; offer operator-guided steps rather than invent remote control.
- Discover other active machines through authoritative estate records; deduplicate aliases, never equate a stale locator with a verified host.

The laptop is normally the operator/controller, not the heavy maintenance worker. Run changes **on their target hosts** via qualified existing workers, SSH or supported local package managers. Unreachable hosts are recorded as deferred; they are not silently omitted or represented as updated.

## First implementation
1. Run `aoteru preflight` and follow the live task/host/lease contracts. Audit existing scheduled-update mechanisms and software inventories, consolidate rather than duplicate.
2. Build a read-only per-host inventory: OS/version, installed app/package, version, canonical install/update mechanism, active processes, service dependencies, last known working version, available upgrade, release/security severity, provenance and rollback route. Avoid exposing credentials or dumping provider catalogues.
3. Establish a minimal deterministic updater for **verified low-risk** user-space harnesses/applications via their official installation channels (e.g. npm or winget where actually applicable); make updates sequential, idempotent and bounded, with versions recorded before/after. Prefer vendor-signed sources and supported releases. Never treat arbitrary `pip -U`, `npm -g update` or OS-wide upgrades as universally safe.
4. Post-update: confirm binary path/version, authenticated CLI availability, `codex debug models`/relevant catalogue compatibility when available (not account entitlement), critical agent launch smoke, running service health and key existing repository/worker tests. Restore prior version if a supported rollback is safe; otherwise stop affected host and escalate.
5. Integrate a **weekly** check/update run into the existing Odysseus-owned scheduler, with short exception-based reporting. Security-critical advisories may trigger an earlier checked run, never an unapproved disruptive installation. Initial dry run must be reviewed before enabling unattended mutations.

## Automatic vs approval-gated
- **May auto-apply after evidence-based qualification:** minor/patch updates of standalone user-space CLIs/apps with verified install method, compatible release notes, safe rollback, no credential prompt, no write-lease conflict and no interruption to active work.
- **Approval required:** OS/firmware/kernel, GrapheneOS system updates, Jetson JetPack/BSP, GPU/NVIDIA drivers, ROS 2 distribution or RealSense stack, major/runtime-breaking updates, database/schema migrations, security permission changes, remote-access changes, paid subscriptions, unattended restarts, updates that risk research apparatus stability or jeopardise active runs. Mobile updates may only be reported/assisted via their supported app stores unless actual management capability is verified and separately authorised.
- If an update changes a research-validated environment, preserve the previous immutable environment provenance and require separate research requalification. Never rewrite existing physical evidence.
- Never self-authorise stronger credentials, disable security controls, restart/stop experiments, break active leases or force model-version pin/fallback contrary to `docs/subscription-model-currency-policy.md`.

## Recurring output
Per host: checked timestamp, reachability, software/current→candidate→installed version, official channel, action (updated/deferred/approval-required/failed), verification and rollback result. Produce **one concise estate-wide exception summary**, not per-package notifications. Persist just enough auditable history to prevent repeat failures; no secrets.

## Acceptance
- [ ] Canonical host inventory reconciled and acknowledged gaps recorded.
- [ ] Baseline versions captured for accessible hosts; watchlist inferred from real installations.
- [ ] Dry-run plan verified and no interruption to active users/experiments.
- [ ] At least one safe user-space AI harness update demonstrated with before/after and smoke evidence.
- [ ] Failing update and unavailable host cases tested and truthfully recorded.
- [ ] Weekly scheduling live through Odysseus's existing task system; overlap/race protection and approval gates tested.
- [ ] Operational runbook and concise summary available; source/tests/agent-task status reflect actual deployment.

**Non-goals:** broad fleet-management rewrite; root-wide unattended upgrades; model entitlement claims; speculative installation of software; recurring human busywork; maintenance inside the PhD vault.

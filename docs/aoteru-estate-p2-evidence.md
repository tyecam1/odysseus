---
title: Aoteru estate P2 evidence
status: compact-evidence
owner: odysseus
as_of: 2026-08-19
parent: docs/aoteru-estate-execution-contract.md
---

# P2 — private connectivity (audit-in-progress)

Compact durable record. Do not reread unless a dependency changes.

## Escalation on record

Read-only reconnaissance into the second tailnet peer (`DESKTOP-7DJ1HMA`)
was proposed with the contract's `BLOCKED` format and explicitly approved by
the operator before any cross-host action was taken (`tailscale ssh
DESKTOP-7DJ1HMA "whoami"` etc.). `glovebox` was explicitly excluded from the
approval scope while offline. No config/ACL/service mutation has been made
on this or any other tailnet node.

## What already exists (audited, not built by this session)

- Tailnet `tyecam1.github` is live; this host is already a member,
  authenticated as `tyecam1@`, with `cap/is-admin`, `cap/is-owner` and
  `cap/ssh` (i.e. this node's identity has tailnet admin/owner rights, and
  Tailscale SSH capability is present).
- MagicDNS is **enabled** (`MagicDNSSuffix: tail171792.ts.net`) — plan §5.2
  requirement already met.
- Two more devices are tailnet members: `DESKTOP-7DJ1HMA` (Windows, online,
  direct connection) and `glovebox` (Linux, offline, last seen 32d ago).
- `tailscale serve status` / `tailscale funnel status`: **no config on
  either** — nothing is publicly exposed. The "no public
  model/MCP/shell/control endpoints" safety invariant and the "no router
  port forwarding or Funnel/public exposure" plan invariant are both intact
  as of this check.

## What was tested and does not currently work

- `tailscale ssh DESKTOP-7DJ1HMA "whoami"` — timed out (exit 124, no
  output). **Correction (per `docs/p2-home-windows-bootstrap.md`):**
  Tailscale SSH does not terminate SSH on Windows at all, so this result is
  not evidence of a Grants denial or a misconfiguration — it was the wrong
  test for a Windows peer. Only `ssh DESKTOP-7DJ1HMA` failing (below) is
  meaningful for this host; Tailscale SSH remains the right tool for future
  Linux peers (e.g. `glovebox`).
- Deterministic TCP probe of `100.75.44.26` (all 4s timeout, single
  attempt per port, no retries/scanning beyond this):
  - `22` (SSH): filtered/timeout
  - `3389` (RDP): filtered/timeout
  - `5985`/`5986` (WinRM): filtered/timeout
  - `445` (SMB): **open**
  - `135` (RPC endpoint mapper): **open**
- Searched both repos + this host's `~/.ssh/known_hosts` for any existing
  admin path/credential reference to this machine: none found.
  `services/hwfit/hardware.py` / `core/platform_compat.py:run_ssh_command`
  confirm the app's own remote-Windows execution design is plain OS-level
  SSH (host/port passed at call time, auth via the ambient SSH agent/keys)
  — i.e. it's the same transport the plan wants, not a separate mechanism,
  but it has no built-in credential store and nothing here is pre-trusted:
  `ssh-keygen -F` against every known hostname/IP for this peer returned no
  match in `known_hosts`, so this host has never successfully SSH'd there.
- Net: no port that would give a *non-interactive admin* path (22/3389/
  5985/5986) is currently reachable. `445`/`135` being open doesn't help
  without credentials, and none were invented or attempted, per the
  bootstrap doc's explicit prohibition.
- The plan's §5.7 "Normal Windows OpenSSH over the tailnet is the
  management/parking transport" is **not yet functional** to the one
  online peer. This directly blocks P3 (parking + remote execution).

## Genuinely blocked items (human/credential-gated, not re-attempted)

1. **No reachable bootstrap port at all.** SSH, RDP and WinRM are all
   filtered from this host right now — there isn't even an interactive
   fallback (RDP) reachable over the tailnet, so this can't be resolved
   by finding a "lesser" remote path. Per the bootstrap doc's ordering
   rule, Grants/ACL should only be investigated *after* Windows `sshd` is
   confirmed locally listening — that precondition can't be checked
   remotely either, so a Tailscale API key is correctly **not** being
   requested yet.
2. **Windows-side enablement is circular.** Enabling OpenSSH Server (or
   Remote Desktop) on `DESKTOP-7DJ1HMA` needs either physical/interactive
   access to that machine, or a remote-management path to it — which is
   exactly what's missing.
3. **Phone.** Plan §10.3/§10.4 (mobile default surface, Remote Control
   escalation) needs a physical phone on the tailnet; none is reachable
   from this session.
4. **`glovebox`.** Offline; excluded from this phase's approval scope.
   Re-audit when it's online and the operator wants it in scope.

## Prepared: run immediately once home SSH becomes reachable

```bash
# 1. confirm the port opens
python3 -c "import socket; s=socket.socket(); s.settimeout(4); s.connect(('100.75.44.26',22)); print('open')"
# 2. confirm native OpenSSH auth (replace <winuser> with the Windows account name)
ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new \
    <winuser>@desktop-7dj1hma.tail171792.ts.net "whoami; hostname; Get-Service sshd | Select Status,StartType"
# 3. only if step 2 fails after port 22 is confirmed open: escalate to Grants/ACL
#    inspection (needs an operator-provided Tailscale API key or admin console check)
```

Also register in `config/repositories.yaml`/`config/estate.yaml` once reachable:
confirm/deny whether `misumi` and `obsidian-PhD` exist there (resolves the
open P0 item), and fill in `desktop-7dj1hma`'s real hardware/runtime specs
in `config/estate.yaml` (currently identity-only, no specs — couldn't be
inventoried without a working admin path).

## Registry updates this phase

`config/estate.yaml` now carries all three known tailnet members with
honest status: `hz2-workstation` (role `lab`, this host), `desktop-7dj1hma`
(role `home`, `admin_path: unresolved`), `glovebox` (role `unassigned`,
offline, out of scope). No fabricated specs — only what was actually
observed via `tailscale status --json`.

## Gate

Plan §12 P2 gate: "laptop + phone reach authenticated `svc:aoteru` from
outside home LAN; raw services are not publicly reachable; access-control
tests deny unapproved cross-domain paths."

- [x] raw services not publicly reachable (verified — no serve/funnel config)
- [ ] laptop + phone reach `svc:aoteru` — `svc:aoteru` doesn't exist yet
      (that's the P1 registry's `endpoint: null` placeholder; building the
      actual authenticated front door is P5/P6 work), and no phone is
      reachable from this session
- [ ] access-control tests deny unapproved cross-domain paths — can't test
      without ACL/Grants visibility (blocked item 1 above)

**P2: PARTIAL.** The network substrate (tailnet, MagicDNS, no public
exposure) pre-exists and is verified sound. The management-transport half of
the gate (SSH to the peer) does not currently work and needs either operator
action on `DESKTOP-7DJ1HMA` or ACL visibility I don't have credentials for.
Not fabricating a PASS here — recording the true state and stopping to ask
rather than guessing further into a live network.

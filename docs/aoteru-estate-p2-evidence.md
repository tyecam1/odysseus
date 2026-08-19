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
  output). Tailscale SSH may not be enabled on that node, or it requires an
  interactive re-auth step this non-interactive session can't complete.
- `ssh -o BatchMode=yes 100.75.44.26` (plain OpenSSH over the tailnet IP) —
  `Connection timed out` on port 22. Either Windows OpenSSH Server isn't
  running/listening there, or a Grant/firewall rule doesn't currently permit
  this host to reach it on 22.
- Net result: the plan's §5.7 "Normal Windows OpenSSH over the tailnet is
  the management/parking transport" is **not yet functional** from this
  host to the one online peer. This directly blocks P3 (parking + remote
  execution), which depends on this transport working.

## Genuinely blocked items (human/credential-gated, not re-attempted)

1. **Grants/ACL policy inspection.** `tailscale` CLI doesn't expose ACL
   read; that lives in the web admin console (`login.tailscale.com/admin/acl`)
   or the Tailscale API with an API key/OAuth client, neither available to
   this session. Can't confirm whether "deny-by-default least privilege"
   (plan §5.3) is actually configured, or whether the SSH timeout above is
   an ACL denial vs. a service simply not running.
2. **Windows-side SSH enablement.** If OpenSSH Server needs installing/
   starting on `DESKTOP-7DJ1HMA`, that requires either interactive access to
   that machine or working SSH to it — circular, needs the operator.
3. **Phone.** Plan §10.3/§10.4 (mobile default surface, Remote Control
   escalation) needs a physical phone on the tailnet; none is reachable
   from this session.
4. **`glovebox`.** Offline; excluded from this phase's approval scope.
   Re-audit when it's online and the operator wants it in scope.

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

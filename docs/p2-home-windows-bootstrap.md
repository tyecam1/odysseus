---
title: P2 home Windows bootstrap
status: execution-note
owner: odysseus
as_of: 2026-08-19
phase: P2
---

# P2 home Windows bootstrap

Continue P2 only. Do not skip its gate or proceed into P3+ authority-changing implementation.

## Correction

DESKTOP-7DJ1HMA is Windows. Tailscale SSH does not terminate SSH on Windows, so failed `tailscale ssh` is not evidence by itself of a Grants denial.

The intended home-worker management path is native Windows OpenSSH Server carried privately over Tailscale/MagicDNS.

## Objective

Restore a safe remote administrative path to DESKTOP-7DJ1HMA, preferably autonomously, then complete all remaining executable P2 work and prepare the exact P2 gate tests.

## Remote-bootstrap rule

Before declaring physical access necessary, exhaust existing authorised remote-management routes over the private tailnet.

Deterministically probe DESKTOP-7DJ1HMA for:

- SSH 22
- RDP 3389
- WinRM 5985/5986
- SMB 445
- RPC endpoint mapper 135

Also inspect existing Odysseus/Misumi/config/runtime evidence for any already-configured Windows remote-management mechanism or credential reference.

Do not:
- expose public ports;
- invent credentials;
- bypass UAC;
- weaken authentication;
- disable Secure Desktop;
- create ad-hoc insecure access;
- request a Tailscale API key prematurely.

If an already-authorised non-interactive admin path exists, use it to:

1. verify the target host identity;
2. install/enable Windows OpenSSH Server if absent;
3. start `sshd`;
4. set `sshd` startup to Automatic;
5. verify/create only the required TCP/22 firewall rule;
6. verify TCP/22 is locally listening;
7. test native SSH from the lab host over Tailscale/MagicDNS.

If RDP is reachable but no safe non-interactive admin path exists, identify RDP as the preferred one-time human bootstrap route.

Only investigate Tailscale Grants/ACL as a likely blocker after ALL are true:
- Windows `sshd` is confirmed locally listening on 22;
- the Windows firewall rule is correct;
- DESKTOP-7DJ1HMA is online in Tailscale;
- TCP/22 still fails across the tailnet.

Do not request a Tailscale API key unless inspection of Grants is then genuinely necessary and no existing authorised access route can answer the question.

## P2 continuation

While remote bootstrap is being resolved:

1. Complete every P2 item that does not require home-PC or phone physical access.
2. Correct any docs/config/code that assume Tailscale SSH can terminate on Windows:
   - Linux lab host may use Tailscale SSH where appropriate;
   - Windows home host uses native OpenSSH over Tailscale/MagicDNS.
3. Prepare exact deterministic tests to run immediately when home SSH becomes reachable.
4. Keep P2 marked partial until its real gate passes.
5. Do not implement P3/P4/etc merely to stay busy.
6. Read-only preparation for later phases is allowed only where it creates no new implementation, migration state, authority or duplicated capability.
7. Preserve the existing upstream/runtime Odysseus deployment and Aoteru target separation.

## Phone

Phone validation remains a legitimate P2 gate. Prepare everything needed, but do not weaken or bypass the phone/cellular test because the device is not reachable from this session.

## Human escalation

Before asking the operator for any action, independently establish:

1. the proposed action is correct;
2. human authority/credential/physical action is genuinely required;
3. no authorised remote alternative exists;
4. an independent verifier agrees.

If human action is required, ask for exactly one minimal bootstrap action.

Return only:

`REMOTE ROUTES:`
`AUTONOMOUS BOOTSTRAP:`
`P2 WORK COMPLETED:`
`REMAINING P2 GATE:`
`IF HUMAN REQUIRED:`
`EXACT ONE-TIME ACTION:`

Then continue autonomously wherever the P2 rules permit.

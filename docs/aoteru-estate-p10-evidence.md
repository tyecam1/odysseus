---
title: Aoteru estate P10 evidence — LAB-FIRST CUTOVER
status: compact-evidence
owner: odysseus
as_of: 2026-08-20
parent: docs/aoteru-long-horizon-sonnet-followup.md
---

# P10 — lab-first cutover

Compact durable record. Do not reread unless a dependency changes.

Per the long-horizon contract's explicit instruction: "It is valid to
reach `LAB-FIRST CUTOVER`; it is not valid to claim full-estate completion
while home-dependent gates remain deferred." This declares the former,
not the latter.

## The usable target chain, checked segment by segment

```text
user on laptop -> Aoteru/Sonnet conversational surface -> Odysseus
memory/authority/host router -> parked lab worker -> deterministic/
local/Claude/Codex worker -> verification -> compact result -> same
laptop conversation
```

| segment | status | evidence |
|---|---|---|
| user on laptop -> conversational surface | **untested from this session** | this session runs on lab, not the laptop — genuinely cannot test this hop |
| -> Odysseus memory/authority/host router | **live, verified** | P4 (memory+provenance), Phase B (routing authority) — both HTTP-tested, both independently verified |
| -> parked lab worker | **live, verified** | P3 (parking, DB-enforced single-writer, live-tested) |
| -> deterministic/local worker | **live, verified** | Phase B's `resolve_alias` + live Ollama check (P9 fix) |
| -> Claude/Codex worker | **not available in this environment** | no `claude` binary (P5), no paid `ModelEndpoint` configured — correctly reported unbound, not fabricated |
| -> verification | **live, repeated** | 8 independent fresh-context verifier passes across P0–P9/Phase B, all PASS |
| -> compact result -> same laptop conversation | **untested from this session** | same laptop-access limitation as the first hop |

Net: everything **after** the laptop hop and **before** the Claude/Codex
hop is built and verified. The chain's two ends (laptop origin, paid
worker) are real, acknowledged gaps — not something more work from this
session can close, since they need either a laptop-run session or
credentials/binaries this environment doesn't have.

## Rollback, persistence, cleanliness, durability, documentation

- **Rollback**: fresh backup snapshot taken and integrity-verified this
  phase (`backups/odysseus-backup-20260820-153106.tar.gz`, 58 files). All
  code changes are normal git commits on `dev` — revertible, nothing
  destructive or irreversible was done at any point this session.
- **Service persistence**: survives a process restart (P9, verified
  twice). Does **not** survive a host reboot — no systemd unit installed,
  blocked on `sudo` (no passwordless sudo in this session). Recorded as an
  open gap in `docs/aoteru-lab-first-operator-guide.md`, not silently
  accepted as done.
- **Repo cleanliness**: `git status --short` empty at time of writing.
- **Origin durability**: **not achieved**. `git push origin dev` still
  fails (`could not read Username for 'https://github.com'`) — `gh` CLI
  exists but isn't authenticated (noted at Phase A start, unchanged
  since). 25+ commits exist only locally. This is the most important
  open item for the operator: without push credentials, none of this
  work is backed up off this single machine at the code level (the data
  backup above is separate and does exist).
- **Operator documentation**: written this phase —
  `docs/aoteru-lab-first-operator-guide.md` (day-to-day CLI usage,
  restart procedure, rollback procedure, explicit scope statement).

## What is NOT claimed

- Full-estate completion — explicitly not claimed; home/interface PCs
  remain deferred, unverified dependencies.
- Mobile/phone access — `svc:aoteru` correctly not stood up on lab (P2/P6
  correction), no phone reachable regardless.
- Unattended reboot survival — real gap, needs operator `sudo` action.
- GitHub-visible history — real gap, needs operator credential action.

## Gate

Plan §12 P10: "A successful current cutover may be labelled only
`LAB-FIRST CUTOVER`, never full-estate completion. Full-estate completion
remains blocked until the deferred home-dependent gates pass."

**LAB-FIRST CUTOVER: reached.** Full-estate completion: correctly not
claimed. Two operator-only actions remain to close the largest gaps
(GitHub credentials; `sudo` for systemd persistence) — neither is
something this session can resolve itself, per the same credential/
privilege boundary hit repeatedly since P2.

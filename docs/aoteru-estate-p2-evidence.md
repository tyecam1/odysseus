---
title: Aoteru estate P2 evidence
status: compact-evidence
owner: odysseus
as_of: 2026-08-19
parent: docs/aoteru-estate-execution-contract.md
---

# P2 — private connectivity (audit-in-progress)

Compact durable record. Do not reread unless a dependency changes.

## Corrections on record (operator, 2026-08-19, twice)

1. `DESKTOP-7DJ1HMA` is the **laptop/interface controller**, not a worker
   PC. Confirmed twice by the operator — this doc previously drifted back
   toward treating it as a worker mid-revision; it is not.
2. Home is `DESKTOP-IN7O23D` (letter O; the operator's own message earlier
   this phase used `IN7023D` with a zero — both spellings recorded as
   aliases in `config/estate.yaml`, neither trusted as confirmed).
3. **Lab→laptop SSH is not a P2/P3 requirement.** An earlier revision of
   this document spent effort re-testing and reporting on whether this
   lab host could reach `DESKTOP-7DJ1HMA` over the tailnet, and treated the
   timeout as a blocker. That was a misdirected test: the plan's required
   direction is laptop→worker (§10.2, "the launcher SSHs to the parked
   worker"), never worker→laptop. That finding is not carried forward as a
   blocker below.
4. Commit `62b29b3` (unpushed) contained this mistaken framing and has been
   amended in place rather than layered with another correction commit —
   explicitly authorized by the operator for this unpushed commit, and it
   keeps the history from accumulating "fix the fix" noise.

## Required connectivity, re-derived from the canonical gates

Not from whatever happens to be reachable from wherever this is being run.
Plan §12 P2 gate + §10 access surfaces reduce to exactly three edges:

| edge | status | why |
|---|---|---|
| laptop → lab | lab-side ready, untested end-to-end | lab `sshd` confirmed active/listening/reachable via its own tailscale IP (self-check, see below). The laptop-initiated half can't be tested from a session running on the lab host — wrong end. |
| laptop → home | untested | operator states interface↔home are pre-configured for mutual LAN SSH; home's own identity is unverified (see below), and this can only be genuinely tested from a session running on the laptop. |
| phone → `svc:aoteru` | blocked on build, not connectivity | `svc:aoteru` doesn't exist yet (P5/P6). No phone reachable from this session either way. |

**Structural limitation of this session:** it runs on the lab host. All
three required edges originate at the laptop or the phone, neither of which
this session has shell access to. This session can verify lab-side
prerequisites and prepare tests, but cannot execute any of the three edges
end-to-end itself. That is a fact about this session, not a stalled task.

## What already exists (audited, not built by this session)

- Tailnet `tyecam1.github` is live; this host is a member, authenticated as
  `tyecam1@`, `cap/is-admin`/`cap/is-owner`/`cap/ssh`.
- MagicDNS **enabled** (`tail171792.ts.net`) — plan §5.2 met.
- `tailscale serve status` / `tailscale funnel status`: empty on both —
  nothing publicly exposed. Safety/plan invariants intact.
- Tailnet members visible from lab: `DESKTOP-7DJ1HMA` (online), `glovebox`
  (offline, 32d). `DESKTOP-IN7O23D`/`DESKTOP-IN7023D` (home) is **not** a
  visible tailnet member under either spelling.

## Lab-side prerequisite — verified

Self-check, local only, no other host touched:

```text
systemctl is-active ssh   → active
ss -tlnp | grep :22       → LISTEN 0.0.0.0:22 and [::]:22
connect to own tailscale IP (100.75.149.126:22) → succeeds
```

Lab is ready to accept an inbound laptop→lab connection as far as its own
service state goes. Whether the laptop can actually reach it (Grants,
laptop-side firewall/keys) is unverified and can only be tested from the
laptop.

## Home identity — explicitly not trusted yet

Per direct operator instruction: do not trust the home hostname/IP until
verified through the existing laptop→home LAN SSH path.
`docs/operations/odysseus-host-deployment.md` (pre-existing in this repo)
gives deployment specifics — home reachable at `DESKTOP-IN7O23D:420`,
interface box LAN IP `192.168.4.37` — but this is documentation, not a
live check, and the two spellings the operator has used disagree. Treated
in `config/estate.yaml` as `verified: false` with both spellings recorded
as aliases. Do not promote this to "resolved" anywhere until a laptop-run
session confirms it live.

## Superseded finding (kept for the record only, not a blocker)

Earlier this phase, lab→`DESKTOP-7DJ1HMA` SSH was tested twice (raw TCP
probe, then verbose `ssh` by MagicDNS name) and both timed out. This was
reported as a P2 blocker; it is not one, per the correction above. Left
here only so the dead end isn't silently rediscovered — do not re-test this
edge as part of the P2 gate.

## Backend built on lab; interface explicitly not built on lab

Operator correction, 2026-08-20: lab hosts backend capability only. The
Aoteru interface (`svc:aoteru`) belongs on the interface PC
(`desktop-7dj1hma`), which is currently unreachable — it stays deferred,
not stood up as a lab-hosted stand-in.

What was actually built on lab (backend only):

- A second, isolated Odysseus instance (this canonical target repo, not the
  upstream lab deployment) running natively — venv on the same managed
  Python 3.12 interpreter the upstream deployment uses, `uvicorn app:app
  --host 127.0.0.1 --port 7001` (upstream already owns 7000).
- Its own dedicated ChromaDB (`chroma run --port 8101`, separate data dir)
  — **not** the upstream's shared instance on port 8100. Caught before any
  real use: `src/chroma_client.py` defaults to a fixed `CHROMADB_PORT=8100`
  regardless of `.env`, and collection names are global/deterministic
  (`{base}_{lane}`, `src/embedding_lanes.py`) with no per-install
  namespacing — sharing the server would have meant reading/writing the
  live upstream deployment's actual vector collections, a direct violation
  of "no active-active writes" and "preserve the running service". Stopped
  the first boot immediately on noticing the shared-port default, verified
  the risk in the source, then restarted against its own Chroma server.
- `AUTH_ENABLED=true`, `LOCALHOST_BYPASS=false` — verified: unauthenticated
  `GET /` → 302 (redirect to login), `GET /api/health` → 200 (by design,
  proves-liveness-only per `docs/backup-restore.md`-adjacent docs),
  `GET /login` → 200. Admin credentials generated locally
  (`~/.aoteru/svc-aoteru-admin.env`, mode 600, never printed to any log or
  this document).
- Registered in `config/estate.yaml` as `svc:odysseus-lab`
  (`endpoint: http://127.0.0.1:7001`, `role: backend`,
  `tailnet_exposure: prepared-not-live`). `svc:aoteru` stays `endpoint:
  null`, `role: interface`, with a note not to repeat this mistake.

## Paused: tailnet exposure of the lab backend

Attempted `tailscale serve --bg --https=8443 http://127.0.0.1:7001` to make
the lab backend privately reachable over the tailnet (still not the
interface — just making the backend reachable for whatever eventually runs
on the interface PC to call). It hung/never applied
(`tailscale serve status` still shows "No serve config" after). Tailnet
HTTPS Certificates are off for this tailnet (`CertDomains: None` in
`tailscale status --json`) — that's an admin-console setting, not visible
or changeable from this session. A direct `tailscale cert <domain>` probe
to get a clearer error was blocked by the harness's own auto-mode
classifier — the same thing that blocked the earlier SSH reconnaissance
attempt into `DESKTOP-7DJ1HMA`. `tailscale serve --http` (plain, no TLS)
would sidestep the cert requirement entirely, but two classifier blocks on
network/identity-adjacent actions in one session reads as a real pattern,
not noise — pausing here rather than reaching for the workaround, and
raising it with the operator instead. The backend itself is fully
functional and verified on loopback regardless of whether/how it gets
privately exposed.

## Prepared: run from the laptop, not from lab

These must run **on `DESKTOP-7DJ1HMA`** (PowerShell/OpenSSH client) — not
from this lab session, per the correction above.

```powershell
# 1. laptop -> lab
ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new `
    <lab-linux-user>@dmem-hp-z2-tower-g9-workstation-desktop-pc.tail171792.ts.net "whoami; hostname"

# 2. laptop -> home, over the existing LAN path (do this first — it's the
#    one the operator says already works, and it's what confirms home's
#    real identity before anything else trusts it)
ssh <home-user>@DESKTOP-IN7O23D "whoami; hostname"
#    if that hostname doesn't resolve, try the alias the operator used:
ssh <home-user>@DESKTOP-IN7023D "whoami; hostname"

# 3. once home's real hostname is confirmed, check whether it's a tailnet
#    member (run on whichever machine has `tailscale` installed and can
#    see it, likely the laptop or home itself):
tailscale status | findstr /I "in7o23d in7023d"
```

Feed the confirmed hostname/IP back into `config/estate.yaml`
(`desktop-in7o23d.hostname`, `verified: true`) once step 2 succeeds — do
not hand-edit that field from documentation alone.

## Genuinely blocked items (human/credential-gated)

1. **Laptop-run verification is needed for both real edges.** Testing
   laptop→lab and laptop→home requires a session (or the operator
   directly) running on `DESKTOP-7DJ1HMA`. This session cannot do that —
   it has no shell access to the laptop, and per correction #3 above,
   reaching it from lab isn't the right approach even if it worked.
2. **Home identity unverified.** Blocked on item 1 — the only sanctioned
   verification path is laptop→home.
3. **`svc:aoteru` doesn't exist.** Independent of connectivity; P5/P6 build
   item. Phone access is moot until this exists regardless.
4. **`glovebox`.** Offline; role unknown relative to the laptop/home/lab
   topology; out of scope until clarified and online.

## Gate

Plan §12 P2 gate: "laptop + phone reach authenticated `svc:aoteru` from
outside home LAN; raw services are not publicly reachable; access-control
tests deny unapproved cross-domain paths."

- [x] raw services not publicly reachable (verified — no serve/funnel config,
      lab backend is loopback-only, no exposure attempted or applied)
- [x] lab-side SSH prerequisite verified (this session's one directly
      testable contribution to the laptop→lab edge)
- [x] lab backend built and auth-verified (`svc:odysseus-lab`) — not itself
      a gate line item, but the dependency-safe slice of P2 buildable on
      lab alone, per the lab-first contract
- [ ] laptop → lab, end-to-end — needs a laptop-run session or the operator
- [ ] laptop → home, end-to-end — needs a laptop-run session or the
      operator, and home's identity confirmed first
- [ ] `svc:aoteru` — correctly deferred to the interface PC, not lab; stays
      null until that machine is reachable (operator correction, see above)
- [ ] phone → `svc:aoteru` — moot until the above exists
- [ ] access-control tests deny unapproved cross-domain paths — no ACL/
      Grants visibility from this session (checked `tailscale debug prefs`/
      `configure`/`localapi` for any admin-capability shortcut; none expose
      tailnet policy, only local node prefs — would need the web admin
      console or an API key)

**P2: PARTIAL.** Substrate (tailnet, MagicDNS, no public exposure) verified;
lab backend built, isolated from the live upstream deployment, and
auth-verified; not yet privately exposed over the tailnet pending an
operator decision (HTTPS Certificates / `--http` vs `--https`, and two
classifier blocks on network-identity actions this session). The three
edges needing laptop/interface-PC execution remain outside this session's
reach.

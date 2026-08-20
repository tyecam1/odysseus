---
title: Aoteru estate P6 evidence
status: compact-evidence
owner: odysseus
as_of: 2026-08-20
parent: docs/aoteru-estate-execution-contract.md
---

# P6 — mobile universal access (lab-first slice)

Compact durable record. Do not reread unless a dependency changes.

## Assessment before building anything

Plan §10.3/§12 P6 wants: Aoteru mobile/PWA estate dispatch, a job/status/
result view, and an optional Claude Remote Control escalation link. The
actual mobile-facing surface is `svc:aoteru` — which
`docs/aoteru-estate-p2-evidence.md` already established, per direct
operator correction, belongs on the interface PC (`desktop-7dj1hma`), not
lab. Lab hosting a stand-in for it was explicitly ruled out in P2.

That leaves two real dependencies neither of which this session has:
a reachable interface PC to host the PWA/dispatch front door, and a
physical phone to test from. Per the lab-first contract ("do not require
the unavailable home worker for mobile UX" — the interface PC has the same
practical effect here as "home" does for P2/P3: a genuine, not
lab-buildable, dependency).

**Rather than inventing lab-only busywork to look like progress**, the
actual question worth answering is: is there any part of the mobile path's
*backend* (the thing `svc:aoteru` would eventually call into) that's
missing and buildable on lab alone? Checked before writing any code.

## Finding: the backend job/status/result surface already exists and is
## already privately reachable — nothing new to build

`routes/task_routes.py` (`setup_task_routes`, prefix `/api/tasks`) already
implements the job/status/result view plan §10.3 wants at the backend
layer: list/create/run/stop/pause/resume, per-task status, recent runs,
notifications — a mature, pre-existing feature (11 builtin tasks already
seeded), not something P6 needs to build.

It's already reachable exactly the way a future `svc:aoteru` would need to
reach it: through the same tailnet-private endpoint P2 already stood up
(`svc:odysseus-lab`, `tailscale serve --http`). Verified live, fresh (not
reusing an old session): logged in via the actual tailnet URL
(`http://dmem-hp-z2-tower-g9-workstation-desktop-pc.tail171792.ts.net:8080`),
`GET /api/tasks` → 200 (11 tasks listed), `GET /api/tasks/runs/recent` →
200.

Net: there is no lab-first-buildable gap in P6 right now. The backend half
already exists and is already exposed privately; the frontend half
(`svc:aoteru`, the PWA, the phone test) is a real, correctly-deferred
dependency on the interface PC — building a substitute for it on lab would
directly contradict the operator's P2 correction.

## Deferred (interface PC + phone — not lab-buildable)

- `svc:aoteru` itself (authenticated mobile/PWA front door)
- Job/status/result **view** as a mobile UI (the API it would call already
  exists and is reachable; only the UI/front-door layer is missing)
- Phone-reachability test ("from phone on cellular: ask, route, execute
  read task, execute approved parked repo task, inspect result")
- Claude Remote Control escalation launcher/session link (plan §10.4) —
  needs claude.ai auth + a running Claude Code process reachable from
  mobile; out of scope without the interface PC and, per P5, without a
  `claude` binary in this environment at all

## Gate

Plan §12 P6 gate: "from phone on cellular: ask, route, execute read task,
execute approved parked repo task, inspect result; phone never needs repo
paths/SSH/model names."

- [ ] entire gate — requires a phone and the interface PC's `svc:aoteru`,
      neither reachable from this session
- [x] (supporting finding, not a gate line item) the backend surface the
      gate would exercise already exists and is already privately
      reachable — confirmed live, not assumed

**P6: DEFERRED.** No fabricated lab-only substitute built. The one thing
worth checking (does lab already have what a future mobile front door
would need to call into) was checked and confirmed yes — recorded as a
finding, not busywork.

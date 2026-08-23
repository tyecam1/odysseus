# Interface PC — install / update / rollback

Workstream H's `svc:aoteru` front door (`config/estate.yaml`'s
`interface-pc` host entry, `role: interface`). This is the
Aoteru-estate-specific pointer doc H's next_action asked for; the actual
install mechanics already exist and are generic (`docs/setup.md`, this
repo's normal Docker/native/systemd paths) — this doc does not duplicate
them, it says which one applies and adds the three things `docs/setup.md`
doesn't cover: estate registration, acceptance, and rollback.

## Before anything: identify the OS — do not guess

`config/estate.yaml`'s `interface-pc` entry deliberately has `os: unknown`
and `verified: false`. Two different machines were previously conflated
under one `role: interface` entry (see the entry's own `notes:`) — do not
assume the interface PC is Windows, Linux, or the same box as the laptop
controller (`desktop-7dj1hma`) until a live session on the actual machine
confirms it. The first action once it's reachable is identity, not
install:

```
venv/bin/python scripts/home_reentry_inventory.py
```

(Generic — [[I-home-reentry]]'s own inventory script, works on any host,
reports OS/hardware/hostname facts without assuming what it'll find.)

## Install — pick the one path that matches what's actually there

Three install mechanisms already exist in this repo. **Do not mix them on
one host** — see "Found inconsistency" below for why that matters.

| If the host has/will have... | Use | Update | Rollback |
|---|---|---|---|
| Docker + Docker Compose | `docs/setup.md` "Docker (recommended)" | `update_windows.bat` (Windows) or `git pull --ff-only && docker compose up -d --build` (any OS) | `git checkout <known-good-ref> && docker compose up -d --build` |
| Native Windows, no Docker | `docs/setup.md` "Native Windows" (`launch-windows.ps1`) | `git pull --ff-only && powershell -ExecutionPolicy Bypass -File .\launch-windows.ps1` | `git checkout <known-good-ref>`, then re-run `launch-windows.ps1` (idempotent — skips the venv/deps it already has) |
| Native Linux/macOS, no Docker | `docs/setup.md` "Native Linux / macOS" + `odysseus-ui.service` (edit `User`/`WorkingDirectory`/`ExecStart` first — it ships with placeholder paths) | `git pull --ff-only && venv/bin/pip install -r requirements.txt && sudo systemctl restart odysseus-ui` | `git checkout <known-good-ref> && venv/bin/pip install -r requirements.txt && sudo systemctl restart odysseus-ui` |

**Found inconsistency (this checkpoint, not previously documented):**
`update_windows.bat` assumes a Docker Compose deployment already exists
(`docker compose up -d --build`) — it will fail cleanly (missing
`docker`/`docker compose` on PATH) rather than corrupt anything, but it
is **not** the update path for a host set up via `launch-windows.ps1`
(native, no Docker). Confirm which install mechanism was actually used
before running either update script.

`build-windows-portable.ps1` (a third path: a frozen `.exe` distribution)
exists but is a packaging tool for producing a distributable build, not
an in-place install/update mechanism — out of scope for this doc, not
something the interface PC itself needs to run.

## After install: register and accept, don't just trust reachability

1. Do **not** flip `config/estate.yaml`'s `interface-pc` entry to
   `verified: true` or fill in `hostname`/`os` from anything other than a
   live session actually running on that machine — "reachability alone
   is not sufficient" is this workstream's own invariant
   ([[H-interface-mobile-frontdoor]], enforced at the routing layer by
   `src.estate_router.host_reachable`).
2. Run the acceptance script against the real instance:
   ```
   venv/bin/python scripts/interface_frontdoor_acceptance.py --url http://<interface-pc-host>:<port>
   ```
   Checks: PWA manifest served, liveness, protected routes reject
   unauthenticated callers, login page reachable. Same command whether
   this is the first install or a post-rollback recheck.
3. Only after that passes: update `config/estate.yaml`'s `interface-pc`
   entry (`hostname`, `os`, `tailscale`, `verified: true`) in a normal
   commit, same as any other config change — not silently, not by a
   script.
4. `svc:aoteru`'s `endpoint` stays `null` until this is done for real.
   Do not stand up a lab-hosted stand-in and call it `svc:aoteru`
   ([[H-interface-mobile-frontdoor]]'s existing invariant, unchanged
   here).

## What this doc does not attempt

- Does not assume or hardcode interface-PC hardware/OS — see "identify
  the OS" above. Any Windows- or Linux-specific instruction below that
  line only applies once confirmed live.
- Does not add a fourth install mechanism. Docker / native-Windows /
  native-Linux+systemd already exist and are correct; this doc only says
  which one applies and what to do before/after.
- HTTPS/LAN/Tailscale exposure configuration is generic and already
  covered in `docs/setup.md` ("HTTPS + LAN/Tailscale exposure") — not
  repeated here.

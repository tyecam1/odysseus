---
title: Aoteru lab-first operator guide
status: operator-doc
owner: odysseus
as_of: 2026-08-20
parent: docs/aoteru-long-horizon-sonnet-followup.md
---

# Aoteru lab-first operator guide

What's actually running, how to use it, and how to undo it. This is the
operator-facing companion to the phase evidence docs (which are audit
trail, not usage instructions).

## What's live right now

- **`svc:odysseus-lab`** — an isolated Odysseus instance (this canonical
  repo, not the separate `pewdiepie-archdaemon/odysseus` lab deployment)
  running natively, loopback `127.0.0.1:7001`, privately reachable over
  the tailnet at
  `http://dmem-hp-z2-tower-g9-workstation-desktop-pc.tail171792.ts.net:8080`
  (Tailscale Serve, HTTP, tailnet-only — never public).
- Its own ChromaDB (`127.0.0.1:8101`) — deliberately separate from the
  upstream deployment's shared instance on port 8100.
- Admin login: username in `~/.aoteru/svc-aoteru-admin.env`
  (`ODYSSEUS_ADMIN_USER`/`ODYSSEUS_ADMIN_PASSWORD` — file mode 600, never
  committed).

## Day-to-day: the `agent` CLI

Run from the repo root with the venv active (`source venv/bin/activate`):

```bash
agent status              # live host + registry resolution
agent where                # current repo's registry identity + active lease
agent sync                 # regenerate bay/workspace/skill bootstraps
agent park <repo_id>       # acquire a write lease (fails closed on dirty tree / conflict)
agent release <repo_id>
agent claude auto "<task>" [--repo ID]   # resolve host+dispatch; home fails truthfully
agent claude lab "<task>"
agent claude home "<task>"               # will fail — home isn't on the tailnet yet
agent claude where                        # active logical sessions
```

## Querying the routing authority directly

```bash
curl -s http://127.0.0.1:7001/api/estate/route/hosts        # (needs a session cookie)
curl -s http://127.0.0.1:7001/api/estate/route/alias/local-fast
curl -s -X POST http://127.0.0.1:7001/api/estate/route \
     -d '{"task_class":"coding","requirements":{"capabilities":["local-fast"]}}'
```

Bound aliases today: `local-fast` → `qwen3:8b`, `local-strong` →
`gpt-oss:20b`, `embedding` → `qwen3-embedding:8b`, `reranker` →
`dengcao/Qwen3-Reranker-8B:Q4_K_M`. Everything else (`code-fast`,
`code-strong`, `reasoning-strong`, `vision`) is unbound — no evidence yet,
correctly reported as such rather than guessed.

## Restarting the service

```bash
# find and stop it
ss -tlnp | grep 7001                 # find the PID
kill <pid>
# start it again
cd /home/agent/projects/odysseus-aoteru && source venv/bin/activate
nohup python -m uvicorn app:app --host 127.0.0.1 --port 7001 > logs/svc-aoteru.log 2>&1 &
disown
```

**Known gap**: this is not yet a systemd service, so it will not survive a
host reboot automatically. Installing one needs `sudo` (a systemd unit
template already exists at `odysseus-ui.service`/`install-service.sh` in
this repo — adapt the port/paths), which this session couldn't run
(no passwordless sudo). This is the single biggest gap between "lab-first
cutover" and genuine unattended production persistence — flagged, not
silently accepted as done.

## Rollback

- **Data**: `./scripts/odysseus-backup snapshot` / `restore` (see
  `docs/backup-restore.md`). A fresh snapshot was taken and verified as
  part of this cutover (`backups/odysseus-backup-20260820-153106.tar.gz`,
  58 files, integrity-verified).
- **Code**: everything is a normal git commit on `dev` — `git revert
  <sha>` or checkout an earlier commit undoes any specific change.
  Nothing here required an irreversible action (no destructive migration,
  no schema drop).
- **Network**: `tailscale serve --http=8080 off` removes the tailnet
  exposure instantly if ever needed; the backend keeps running on
  loopback regardless.

## Explicit scope — what this cutover is and is not

This is a **lab-first cutover**, not full-estate completion:

**Works now, verified live:**
- Estate registry resolution (`agent status`/`where`) — host-agnostic,
  no hardcoded paths.
- Parking/leases with a real DB-enforced single-writer guarantee.
- Misumi memory (capsule/open-loop/handoff) with provenance
  (source-event) linking and a real revision trail.
- Central model+host routing authority, live-checked against Ollama,
  with per-decision telemetry.
- Fault handling: truthful failure on unavailable home, auth boundaries,
  service-restart persistence, malformed-config handling, telemetry-write
  resilience — all tested live, three real defects found and fixed.

**Explicitly not working / deferred, not fabricated:**
- The interface PC (`desktop-7dj1hma`) and home PC (`desktop-in7o23d`,
  identity itself unverified) — neither reachable from this session.
- `svc:aoteru` (the actual mobile/PWA front door) — belongs on the
  interface PC by design, not stood up here.
- Claude/Codex execution — no `claude` binary in this environment, no
  paid-provider `ModelEndpoint` configured.
- Origin durability — `git push` fails (no GitHub credentials in this
  session); every commit above is real and local but not yet reflected
  on GitHub.
- Automatic service persistence across a host reboot (see above).
- Dual-worker fault tests (split-brain, home-offline-primary) — need the
  home PC to exist first.

Full estate completion requires: the interface/home PCs coming online and
being live-verified (not assumed), GitHub push credentials being added,
and a systemd unit being installed (needs `sudo`, run by the operator).
None of these require redesigning anything already built — the schema,
registries and routing authority are already host-agnostic and were built
to extend, not to be rebuilt, once those dependencies clear.

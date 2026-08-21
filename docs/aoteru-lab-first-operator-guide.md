---
title: Aoteru lab-first operator guide
status: operator-doc
owner: odysseus
as_of: 2026-08-21
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
agent park <repo_id>       # acquire a write lease (fails closed on dirty tree / conflict; reclaims a stale one)
agent release <repo_id>
agent heartbeat <repo_id>  # renew an active lease's heartbeat_at — run periodically during long work
agent claude auto "<task>" [--repo ID]   # resolve host+dispatch; home fails truthfully
agent claude lab "<task>"
agent claude home "<task>"               # will fail — home isn't verified/on the tailnet yet
agent claude where                        # active logical sessions (failed/non-launched sessions no longer show as active)
```

## Querying the routing authority directly

```bash
curl -s http://127.0.0.1:7001/api/estate/route/hosts        # (needs a session cookie)
curl -s http://127.0.0.1:7001/api/estate/route/alias/local-fast
curl -s -X POST http://127.0.0.1:7001/api/estate/route \
     -d '{"task_class":"coding","requirements":{"capabilities":["local-fast"]}}'

# actually executes the resolved route (local executor only — no
# claude/codex binary/credentials available in this environment):
curl -s -X POST http://127.0.0.1:7001/api/estate/run \
     -d '{"task_class":"coding","objective":"say pong","requirements":{"capabilities":["local-fast"]}}'
```

Bound aliases today: `local-fast` → `qwen3:8b`, `local-strong` →
`gpt-oss:20b`, `embedding` → `qwen3-embedding:8b`, `reranker` →
`dengcao/Qwen3-Reranker-8B:Q4_K_M`. Everything else (`code-fast`,
`code-strong`, `reasoning-strong`, `vision`) is unbound — no evidence yet,
correctly reported as such rather than guessed.

## Restarting the service

**systemd (installed and enabled 2026-08-21)** — this is now the normal
path:

```bash
sudo systemctl restart odysseus-aoteru-lab.service
systemctl status odysseus-aoteru-lab.service
```

`odysseus-aoteru-lab.service` is installed at
`/etc/systemd/system/odysseus-aoteru-lab.service`, `enabled` (survives a
host reboot), `User=agent`, this checkout's own venv,
`127.0.0.1:7001` only, never `0.0.0.0`. Confirmed live: correct
user/bind, `GET /api/health` -> 200, Tailscale Serve mapping and Chroma
isolation on `8101` both unaffected, SQLite state (`routing_decisions`/
`park_leases`/`logical_sessions`) intact across a restart cycle, live
local-model execution smoke test still passes post-restart. Full evidence
in `docs/aoteru-systemd-cutover-evidence.md`.

`Restart=on-failure` deliberately does not fight a clean stop — verified:
sending the managed process SIGTERM (a graceful shutdown the app itself
handles) does **not** trigger an auto-restart, matching the unit's intent
that only a crash should. A consequence worth knowing operationally: if
you ever stop the process by signal rather than `systemctl stop`/
`restart`, the unit goes `inactive` and needs an explicit
`systemctl start` to resume — it will not silently restart itself in that
case.

Manual fallback (only if systemd itself is unavailable — this session
used it once, transiently, before the operator's next
`systemctl start` re-establishes supervision):

```bash
ss -tlnp | grep 7001                 # find the PID
kill <pid>
cd /home/agent/projects/odysseus-aoteru && source venv/bin/activate
nohup python -m uvicorn app:app --host 127.0.0.1 --port 7001 > logs/svc-aoteru.log 2>&1 &
disown
```

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

This is a **lab-first execution cutover**, not full-estate completion.
See `docs/aoteru-estate-p10-evidence.md` for the segment-by-segment chain
and `docs/aoteru-lab-execution-convergence.md` for this pass's specific
findings and fixes.

**Works now, verified live:**
- Estate registry resolution (`agent status`/`where`) — host-agnostic,
  no hardcoded paths.
- Parking/leases with a real DB-enforced single-writer guarantee, plus
  heartbeat renewal and stale-lease auto-reclaim (a crashed holder no
  longer blocks a repo forever).
- Misumi memory (capsule/open-loop/handoff) with provenance
  (source-event) linking and a real revision trail.
- Central model+host routing authority, live-checked against Ollama, with
  per-decision telemetry — validates *every* requested capability (not
  just the first), honors an explicit requested host, and never
  fabricates a quality-floor or budget-constraint pass it can't verify.
- **Actual execution**: `run_task()` / `POST /api/estate/run` routes
  *and then runs* the task against the resolved local model (reusing
  `src.llm_core.llm_call`), applies a minimal deterministic gate
  (non-empty response), and persists the real outcome/latency back to
  `routing_decisions` — closing the previous "resolves but never
  executes" gap. Live-tested against the real Ollama server on this
  host (`qwen3:8b` / `local-fast`).
- Host eligibility now requires an explicit `verified` flag in addition
  to reachability — a host that merely answers on the tailnet but was
  never operator-confirmed (currently `desktop-in7o23d`) cannot become
  eligible just by becoming reachable.
- `LogicalSession` rows for a dispatch that never actually launches a
  process are now written `failed` at creation, and a stale `active` row
  (crashed wrapper) self-heals via reconciliation — no more permanently
  "active" phantom sessions.
- GitHub origin durability: `git push`/`pull` both verified working over
  HTTPS with stored credentials — commits are no longer local-only.
- Dedicated systemd unit installed and enabled (survives reboot); active
  immediately after install with correct user/bind, verified restart
  correctly does not fight a clean stop, SQLite state and live local
  execution both confirmed intact across a restart cycle — see
  `docs/aoteru-systemd-cutover-evidence.md`.
- Fault handling: truthful failure on unavailable/unverified home, auth
  boundaries, service-restart persistence, malformed-config handling,
  telemetry-write resilience — all tested live.

**Explicitly not working / deferred, not fabricated:**
- The interface PC (`desktop-7dj1hma`) and home PC (`desktop-in7o23d`,
  identity itself unverified) — neither reachable from this session.
- `svc:aoteru` (the actual mobile/PWA front door) — belongs on the
  interface PC by design, not stood up here.
- Claude/Codex execution — no `claude` binary in this environment, no
  paid-provider `ModelEndpoint` configured. The execution path built this
  pass is real but local-model-only for that reason, not a limitation of
  the path itself.
- Automatic service persistence across a host reboot — unit **installed
  and enabled** 2026-08-21 (`systemctl is-enabled` -> `enabled`); an
  actual reboot has not been performed to prove it (deliberately, per the
  finalisation contract — not authorized without explicit operator
  sign-off). One more `sudo systemctl start` is needed right now to
  re-establish systemd's supervision of the currently-running process
  (see `docs/aoteru-systemd-cutover-evidence.md` for why).
- Dual-worker fault tests (split-brain, home-offline-primary) — need the
  home PC to exist first.

Full estate completion requires: the interface/home PCs coming online and
being live-verified (not assumed), and an actual reboot proving the
installed systemd unit's persistence (not yet performed, needs explicit
operator authorization). Neither requires redesigning anything already
built — the schema, registries and routing authority are already
host-agnostic and were built to extend, not to be rebuilt, once
those dependencies clear.

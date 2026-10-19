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

Manual fallback (only if systemd itself is unavailable — used once,
transiently, during this cutover's own restart-behavior test; resolved by
the operator's `systemctl start` re-establishing supervision, confirmed
with a fresh `MainPID`):

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
- Actual host-reboot persistence — unit **installed, enabled, and under
  active systemd supervision** 2026-08-21 (`systemctl is-enabled` ->
  `enabled`, `is-active` -> `active`, re-verified with a fresh `MainPID`
  after a supervised restart cycle). Only an actual host reboot itself
  has not been performed to prove this specific case, deliberately, per
  the finalisation contract — not authorized without explicit operator
  sign-off. Everything short of that physical reboot is verified; see
  `docs/aoteru-systemd-cutover-evidence.md`.
- Dual-worker fault tests (split-brain, home-offline-primary) — need the
  home PC to exist first.

Full estate completion requires: the interface/home PCs coming online and
being live-verified (not assumed), and an actual reboot proving the
installed systemd unit's persistence (not yet performed, needs explicit
operator authorization). Neither requires redesigning anything already
built — the schema, registries and routing authority are already
host-agnostic and were built to extend, not to be rebuilt, once
those dependencies clear.


## 2026-10-19 addendum: GLM Coding Plan on the lab host

**Purpose:** record the lab commissioning path and its evidence boundary.
This dated addendum supersedes the older guide's lab GLM availability
statements where they conflict; it does **not** update executor qualification.

- **Windows credential authority:** the operator's working
  \`~/.local/bin/claude-glm-flash.ps1\` decrypts a DPAPI \`CurrentUser\`
  credential from \`~/.aoteru/secrets/zai-glm-coding-key.dpapi\`. The
  PowerShell variable \`$glmKey\` exists *inside that script*, not
  automatically in an interactive PowerShell session. The encrypted DPAPI
  blob is not portable to Linux, and neither the blob nor the key belongs
  in Git.
- **Lab credential:** for an authorised lab user, the existing Windows
  launcher can decrypt the *same working Coding Plan credential* and
  transmit **only that credential** over an authenticated SSH connection
  into the lab's \`~/.config/glm/env\` (file mode \`0600\`, directory
  \`0700\`). Keep secret material out of prompts, terminal output,
  Git changes and remote command arguments. Do not copy the full
  Windows Claude profile or DPAPI store. Confirm account/subscription
  permission and institutional policy before placing a personal key on a
  shared university host.
- **Provider config:** the lab launcher
  \`~/.local/bin/claude-glm\` sources the host-local configuration;
  \`GLM_BASE_URL\` is \`https://api.z.ai/api/anthropic\`, and
  \`GLM_AUTH_TOKEN\` is the private key. Do not treat an ordinary
  pay-as-you-go key as interchangeable with a key known to work with the
  Coding Plan. The Windows Flash launcher clears inherited
  \`ANTHROPIC_MODEL\` and \`ANTHROPIC_CUSTOM_MODEL_OPTION*\`, then maps
  the Sonnet/Opus/Haiku tiers to \`glm-5.3-flash[1m]\`; this is distinct
  from a full \`glm-5.3\` implementation lane. Match model selections
  to the intended lane, without quietly substituting Flash.

### Observed lab result and outstanding gates

The operator observed before transferring the working laptop
credential: direct Z.AI and Claude Code requests returned HTTP
\`429\`, provider code \`1113\`, *insufficient balance or no resource
package*. After the credential transfer, the SSH-invoked lab launcher
printed an \`unrecognized_model\` diagnostic for \`glm-5.3\`, an empty-stdin
warning, and the model-style response:

> Hi! It looks like your message came through empty. What would you like
> to work on? I'm in \`/home/agent\` ...

This is **evidence of a returned response and of a changed failure
symptom**, but **not** verified success of the requested
\`Reply exactly: GLM connected\` prompt. The transcript did not
reliably establish exit status, effective provider/model attribution,
token usage, or Odysseus estate execution. The custom-model catalogue
diagnostic and the \`claude.ai connectors disabled\` warning are not, by
themselves, proof of failed authentication.

Run a non-interactive bounded test without forwarding SSH stdin (from
the operator's existing PowerShell session; \`$lab\` is the SSH target):

\`\`\`powershell
ssh -n -T $lab 'timeout 90s "$HOME/.local/bin/claude-glm" --print "Reply exactly: GLM connected" </dev/null; rc=$?; printf "\nexit_status=%s\n" "$rc"; exit "$rc"'
\`\`\`

Accept the **direct launcher** only if it returns the requested text,
exits successfully and exposes independent model/provider identification
through an appropriately redacted structured execution record. If the
prompt is lost or the result remains ambiguous, inspect only the command
argument/stdin handling (and the verified existing launcher code) before
modifying model/authentication configuration again.

**Odysseus runtime fallback is a further, separate gate:** GLM must
be integrated into the current estate execution lifecycle, qualify on the
actual host and task role, preserve park leases/verification, and prove
a live Codex-usage-exhausted → GLM switch. An installed launcher, active
subscription, response to an empty prompt or passing mocked tests does
not establish that automatic fallback is operational.


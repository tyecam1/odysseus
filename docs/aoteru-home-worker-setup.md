---
title: Aoteru home worker setup — operator runbook
status: runbook (operator-executed, no automation performs any of this)
as_of: 2026-09-22
owner: odysseus
source: docs/aoteru-multihost-execution-implementation-plan.md, Stage 4
---

# Home worker setup

This is the operator procedure for standing up `desktop-in7o23d` as an
`aoteru-worker/1` worker reachable from `hz2-workstation` over SSH. Nothing
in `src/` runs any of these steps automatically — no code path parks a
lease, flips `worker.enabled`, or writes the survival-check evidence file
for you. Each numbered step below is something you, the operator, run by
hand.

Every `~/`-relative path this runbook writes to on home
(`~/.aoteru/config.local.json`, step 3; the `worker_selftest_enabled`
sentinel, step 7; and `worker_capabilities.json`, also step 7) and the
forced-command worker process itself (step 4) must belong to and resolve
under the **same Windows account** configured in
`worker.ssh.target` (`<user>@...` in `config/estate.yaml`). Windows
resolves `~`/`%USERPROFILE%` per-account, not per-machine, so writing any
of these files as a different account — e.g. an elevated administrator
session that isn't actually the target account, or `SYSTEM` if sshd ever
invokes the forced command under a different identity than expected —
leaves the worker process reading an empty or wrong `.aoteru` directory,
silently failing checks this runbook says should pass.

This does **not** touch the existing household deployment on home
(`odysseus-releases\...`, port 420, `misumi_agent.py` on 4500, the STT
server on 4600, the `Odysseus-Misumi` scheduled task, or
`scripts/windows/odysseus-host.ps1`). The worker is a second, independent
checkout with no listener and no scheduled task of its own — it only ever
runs when lab's `SshTransport` invokes it over a forced SSH command.

## 1. Clone a dedicated checkout

Clone `tyecam1/odysseus` to a path that is **not** the household
`odysseus-releases\...` directory. Recommended:

```
E:\aoteru\odysseus-aoteru
```

## 2. Create the virtualenv

```
cd E:\aoteru\odysseus-aoteru
py -3 -m venv venv
venv\Scripts\pip install -r requirements.txt
```

## 3. Root-var config

Create `%USERPROFILE%\.aoteru\config.local.json` with the root vars for any
repos this worker should be able to resolve (`AI_ROOT`, `PHD_ROOT`,
`HOUSEHOLD_ROOT`, ...) — the same `${ROOT_VAR}` convention
`src/estate_router.py:resolve_repo_path` and `scripts/agent` already use.

## 4. Generate and authorize the SSH key

On lab, generate a dedicated key (never reused for anything else):

```
ssh-keygen -t ed25519 -f ~/.aoteru/worker_ssh_key -N ""
```

Authorize its **public** key on home with a forced command and every
restriction option, so the key can only ever run the worker entry point:

```
command="cmd.exe /c cd /d E:\aoteru\odysseus-aoteru && venv\Scripts\python.exe -m src.estate_worker --root E:\aoteru\odysseus-aoteru",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding ssh-ed25519 AAAA... aoteru-worker-lab
```

The explicit `cd /d E:\aoteru\odysseus-aoteru &&` is required, not
cosmetic: `python -m src.estate_worker` has to *import* `src.estate_worker`
before argparse ever runs, so `--root` (which does the rest of the work —
chdir, sys.path, `_CONFIG_DIR`, see `main()` in `src/estate_worker.py`) is
too late to fix its own import. Python's `-m` resolves that import
against whatever is on `sys.path`, which for `-m` means the process's
*current working directory* — and an OpenSSH forced command runs with
whatever starting directory that session happens to have, not necessarily
this checkout. Without the `cd` first, `-m src.estate_worker` fails with
`No module named src.estate_worker` before the worker ever gets a chance
to run, regardless of what `--root` says. Using
`E:\aoteru\odysseus-aoteru\venv\Scripts\python.exe` (the dedicated
checkout's own venv interpreter, not whatever `python` resolves to on
`PATH` for that session) is required for the same reason `--root` names
this checkout explicitly — the forced command must be self-contained and
not depend on ambient session state.

If the home account is an administrator, this goes in
`C:\ProgramData\ssh\administrators_authorized_keys` (OpenSSH on Windows
ignores the per-user `authorized_keys` file for administrator accounts).
That file also needs its own ACL or Windows OpenSSH's `sshd` refuses to
read it at all (a `LogLevel VERBOSE` sshd log shows `Bad owner or
permissions`, not a clear error at the client). From an elevated
PowerShell on home, after creating/editing the file:

```
icacls "C:\ProgramData\ssh\administrators_authorized_keys" /inheritance:r
icacls "C:\ProgramData\ssh\administrators_authorized_keys" /grant "SYSTEM:F"
icacls "C:\ProgramData\ssh\administrators_authorized_keys" /grant "BUILTIN\Administrators:F"
```

Only `SYSTEM` and `Administrators` may have any access to this file —
adding the target account itself (if it is not already in
`Administrators`) breaks the ACL check the same way a too-open ACL does.

`worker.ssh.command` in `config/estate.yaml` documents this forced command
for operators reading the config — it is never sent as an argument by
`SshTransport`, which only ever pipes JSON to stdin. The forced command on
the home side is what's actually authoritative.

## 5. Pin the host key and target (governed commit)

Record home's SSH host **public** key. Its fingerprint must equal the
already-pinned value:

```
SHA256:rmuPA4DUnFnR8UPXBHrksljQbT86l2aZZAztNZ1TIeU
```

Fill in, by governed commit to `config/estate.yaml`:

- `hosts[desktop-in7o23d].worker.ssh.host_public_key`: the host's SSH
  public key line (e.g. from `/etc/ssh/ssh_host_ed25519_key.pub`-style
  output, or Windows OpenSSH's `ssh_host_ed25519_key.pub`).
- `hosts[desktop-in7o23d].worker.ssh.target`: `<user>@<tailscale-ip-or-dns>`.
- `hosts[desktop-in7o23d].worker.ssh.command`: the forced command from
  step 4, for documentation only.

`SshTransport` refuses with `host_key_unpinned` until `host_public_key` is
set, and never accepts `StrictHostKeyChecking=no` as a substitute.

## 6. Read-only health check

From lab, with the config above committed:

```
venv/bin/python -c "from src.estate_worker_client import call_worker; print(call_worker('desktop-in7o23d', 'health', {}, deadline_s=20))"
```

This must return an attested `ok: true` response before continuing. It
does not require `worker.enabled: true` — `call_worker` talks to the
worker directly, independent of routing eligibility.

## 7. Detached-spawn survival check (Windows process layer)

This is the actual qualification gate for `codex-write` on Windows: the
sshd job object can silently refuse `CREATE_BREAKAWAY_FROM_JOB`, which
would mean a "detached" spawn actually dies the moment the SSH session
that started it closes.

On home, by hand (RDP, an existing interactive session — anything other
than a routed request), create the sentinel file that gates this check:

```
mkdir %USERPROFILE%\.aoteru 2>nul
type nul > %USERPROFILE%\.aoteru\worker_selftest_enabled
```

This is a file, not an environment variable, because every `call_worker()`
call from lab — including the `start` call in step 1 below — opens its
own fresh forced-command SSH session (`SshTransport`, `src/
estate_worker_client.py`), which never inherits environment set in some
other interactive session. A file under `~/.aoteru/` is visible to all of
them: the `start` call's session, and the detached spooled process it
launches. `src/estate_worker.py:_selftest_enabled()` reads this file; it
gates only the bounded `noop-sleep` kind and has no effect on
`codex-write`, which has its own, unrelated authority checks. From lab:

1. `start` a no-op spooled runner: `call_worker('desktop-in7o23d', 'start', {"execution_id": "<uuid>", "kind": "noop-sleep", "timeout_s": 60}, deadline_s=20)`.
2. Wait 30 seconds, then `call_worker('desktop-in7o23d', 'status', {"execution_id": "<uuid>"}, deadline_s=20)`.
3. On home, delete the sentinel file
   (`del %USERPROFILE%\.aoteru\worker_selftest_enabled`) so `noop-sleep`
   goes back to refusing outside an explicit, operator-controlled check.

**Stop gate:** if `process_alive` is not `true` at that point, the runner
did not survive the session close. Record this in
`docs/aoteru-multihost-execution-evidence.md` and stop — do not proceed to
any home write qualification. Home stays read-only-eligible only
(`codex-write` never enters `qualified_executors`); Stages 5–8 for
read-only capability can still proceed.

If it survives, write `~/.aoteru/worker_capabilities.json` on home by
hand:

```json
{"detached_spawn_verified": true}
```

`src/estate_worker.py:_detached_spawn_verified()` reads this file — it is
never written by any code path that routes work, only by this manual
check.

## 8. Per-alias qualification (Stage 7)

Once health and (for write) the survival check pass, run the LM4 canary
per alias against this worker (`--worker-host desktop-in7o23d`) before any
alias is added to `config/models.yaml`'s `qualified_hosts` for this host.
Expected first candidate: `local-fast` / `qwen3:8b`, the only model the
2026-08-29 inventory found already present on home.

## Non-goals

Nothing here changes `scripts/windows/odysseus-host.ps1`, the
`Odysseus-Misumi` scheduled task, or any household port/service. Nothing
here flips `worker.enabled` — that is a separate, later governed commit
(Stage 8) made only after this runbook's checks pass live.

# LM3 — production runtime + promotion cutover: evidence (preflight, blocked)

Task: `docs/aoteru-lm3-production-runtime-promotion-cutover.agent-task.md`.
Status: **blocked on a genuine human-only sudo boundary** after completing
every nonprivileged precheck. No production mutation has occurred. This
document will be updated in place once the operator action below unblocks
continuation — it is not a second task doc.

## Preflight (completed)

- `git pull --ff-only` on `dev`: fast-forwarded `ddb5ec3` -> `f1e731d`
  (adds this task doc only). `f1e731d` is a direct descendant of LM2's
  completion commit `ddb5ec37f55a21a802a938a4cdfef4e286a06607`. Working
  tree clean before and after.
- Host confirmed as the lab worker (`hz2-workstation`,
  `dmem-HP-Z2-Tower-G9-Workstation-Desktop-PC`), the only verified
  execution host per `config/estate.yaml`.
- Production Ollama state (before any change):
  - version: `0.19.0`
  - binary: `/usr/local/bin/ollama`, root:root, mode 755,
    sha256 `67d6bab88e63718d52782ee59db0e40436b35865f424b0ab13d9598e54d6e13a`
  - not an apt package (`dpkg -l` has no `ollama` entry) — installed via
    the standalone install mechanism (root-owned binary + dedicated
    `ollama` system user, uid/gid 999, groups `video`,`render`), matching
    the current systemd unit exactly.
  - systemd unit `/etc/systemd/system/ollama.service`: `User=ollama`,
    `Group=ollama`, `ExecStart=/usr/local/bin/ollama serve`,
    `Restart=always`, enabled, active since 2026-03-30 (PID 262108 at
    check time), no `OLLAMA_HOST` override in `Environment=` (so it
    defaults to loopback).
  - listener: `127.0.0.1:11434` only (`ss -tlnp`) — no `0.0.0.0` exposure.
  - model inventory (`ollama list`): `qwen3.6:35b`, `qwen3.5:9b`,
    `dmem-box-attest-20260802:sentinel` (unrelated, pre-existing, not
    touched), `gpt-oss:20b`, `qwen3:8b`,
    `dengcao/Qwen3-Reranker-8B:Q4_K_M`, `qwen3:30b`,
    `qwen3-embedding:8b`.
  - GPU idle (RTX 3080: 406MiB/10240MiB used, 5% util) and no leftover
    LM1/LM2 scratch Ollama or llama.cpp processes — only the one
    production `ollama serve` process (PID 262108) is running.
  - `odysseus-aoteru-lab.service`: active, healthy (`/api/health` 200 in
    recent logs).
  - `config/models.yaml`: `local-fast -> qwen3:8b`, `local-strong ->
    gpt-oss:20b` bound; `code-fast`/`code-strong`/`reasoning-strong`/
    `vision` all `null`; the three LM2 winners recorded as
    `benchmark-only` — matches memory/LM2 evidence exactly, unchanged
    since `ddb5ec3`.
- **Incumbent live smokes through the real production path**
  (`src.estate_router.run_task`, not a direct Ollama call), objective
  `"Reply with exactly the word: OK"`:
  - `local-fast` -> resolved `qwen3:8b`, executed, gate `pass`, output `"OK"`.
  - `local-strong` -> resolved `gpt-oss:20b`, executed, gate `pass`, output `"OK"`.

## Rollback manifest

If the upgrade regresses incumbent compatibility or breaks the service:

1. Stop service: `sudo systemctl stop ollama`.
2. Restore binary: reinstall Ollama `0.19.0` (same install mechanism used
   originally) so `/usr/local/bin/ollama` sha256 matches
   `67d6bab88e63718d52782ee59db0e40436b35865f424b0ab13d9598e54d6e13a`
   again, or restore from an operator-taken copy of the current binary
   before upgrading (recommend the operator `sudo cp /usr/local/bin/ollama
   /usr/local/bin/ollama.pre-lm3-0.19.0.bak` immediately before running
   the upgrade command below, so rollback needs no network access).
3. Restore unit file if the upgrade mechanism rewrites it (compare
   against the `User=ollama`/`Group=ollama`/no-`OLLAMA_HOST` unit
   recorded above) and `sudo systemctl daemon-reload`.
4. `sudo systemctl restart ollama`; re-verify `local-fast`/`local-strong`
   smokes above pass.
5. No `config/models.yaml` changes have been made yet, so no config
   rollback is needed at this stage.

## Privilege boundary (genuine)

`sudo -n true` was tested per the task's bounded-check requirement and
returned "sudo: a password is required" (exit 1) — this session has no
noninteractive sudo. Upgrading `/usr/local/bin/ollama` and restarting the
root-managed `ollama.service` both require root; there is no
nonprivileged path to either. No password was requested, printed,
captured, or persisted.

### Exact minimal operator commands

Run these as the operator (interactively, with sudo password) on
`hz2-workstation`:

```sh
# 1. optional but recommended — cheap local rollback point, no network needed
sudo cp /usr/local/bin/ollama /usr/local/bin/ollama.pre-lm3-0.19.0.bak

# 2. upgrade via the same install mechanism already in use on this host
curl -fsSL https://ollama.com/install.sh | sudo sh

# 3. confirm the service came back up under the existing unit (User=ollama,
#    loopback-only) rather than a rewritten/duplicated one
sudo systemctl status ollama
ollama --version
```

### Continuation instruction

Once the operator has run the above and `ollama --version` reports a
version newer than `0.19.0` with `ollama.service` active, resume this
same task from the "Runtime upgrade" verification step (service
active/version/loopback/incumbent-load checks) — do not restart LM3 from
scratch, and do not re-run LM2's benchmark matrices.

## Not yet done (blocked on the above)

- Runtime upgrade verification (version, loopback exposure post-upgrade,
  incumbent `qwen3:8b`/`gpt-oss:20b` reload).
- Installing the three LM2-qualified artifacts (`ornith:9b`,
  `nemotron-3.5-lightning:30b-a3b`, `gemma4:12b`) onto the upgraded
  production runtime.
- Per-alias production-path smoke + `config/models.yaml` binding for
  `code-fast`, `reasoning-strong`, `vision`.
- Post-cutover regression gates and focused test run.

`config/models.yaml` has not been modified — current bindings remain
exactly as LM2 left them.

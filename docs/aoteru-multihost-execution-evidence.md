# Multihost execution — live qualification evidence

Runbook: `docs/aoteru-home-worker-setup.md`. Architecture: `docs/aoteru-multihost-execution-implementation-plan.md`.
Adjudication history: `docs/aoteru-multihost-adjudication-log.md`.

This file records live evidence that a host was qualified (or deliberately not), so `config/estate.yaml` and
`config/models.yaml` promotions point at facts and not at a session's say-so.

## Stage 8 — home (`desktop-in7o23d`) qualified for deterministic compute only (2026-10-02)

Scope decided by the operator: qualify home **as compute**, not as a privileged write executor. Only `deterministic`
is qualified in this commit. `local`, `codex` and `codex-write` are **not**, for the reasons below.

### Authorisation and key installation (runbook step 4)

- The operator explicitly authorised adding the dedicated worker **public** key to
  `C:\ProgramData\ssh\administrators_authorized_keys` with the documented restrictions and the documented ACL repair, and
  nothing else (no unrestricted key, no reuse of the key, no change to unrelated SSH authorisation, host-key pinning
  unweakened, no `StrictHostKeyChecking=no`).
- Key: `aoteru-worker-lab`, `SHA256:uJEKTOnr4qkeT8C+TVMI5+3bk+F8MmGAfpD1ppAHv/0`, generated on lab, private half mode 600
  on lab only. The fingerprint was verified identical on the laptop copy and on lab before installing.
- Install: the file had 3 keys (303 bytes). One line was appended; the previous content was preserved byte-for-byte
  (verified by comparing every byte of the old file as a prefix of the new one) and backed up. ACL after: `SYSTEM:(F)`
  and `BUILTIN\Administrators:(F)` only. The three original fingerprints are unchanged.
- **Correction to the documented forced command.** The runbook's entry was
  `command="cmd.exe /c cd /d E:\aoteru\odysseus-aoteru && venv\Scripts\python.exe -m src.estate_worker --root ..."`. On
  this host it failed with "The system cannot find the path specified": sshd already runs the forced command through
  `cmd.exe /c`, so the extra `cmd.exe /c` nests two shells, the outer one evaluates `&&`, and the inner `cd /d` is lost
  before `python.exe` runs. Reproduced on home (the doc's form fails, a single `cmd` invocation prints the right working
  directory). The line this authorisation added was changed to
  `command="cd /d E:\aoteru\odysseus-aoteru && venv\Scripts\python.exe -m src.estate_worker --root E:\aoteru\odysseus-aoteru"`
  with the same four restrictions. Same checkout, interpreter, module and `--root`; only the redundant outer shell is
  gone. Only that one line was edited; the other four lines were verified unchanged. The runbook was corrected in the
  same commit.

### Transport and identity

- Host key: home's `ssh_host_ed25519_key.pub` fingerprint is `SHA256:rmuPA4DUnFnR8UPXBHrksljQbT86l2aZZAztNZ1TIeU`,
  exactly the pinned value. It is recorded in `config/estate.yaml` as `worker.ssh.host_public_key`; `SshTransport`
  connects with `StrictHostKeyChecking=yes` against that pinned key only.
- Target: `User@desktop-in7o23d.tail171792.ts.net` (resolves to `100.105.34.37`). The worker runs as `User`, a local
  Administrator: acceptable for this constrained compute qualification, and the reason `codex-write` is not qualified
  (see the hardening task below).

### Health and attestation (runbook step 6)

`call_worker('desktop-in7o23d', 'health', {}, deadline_s=30)` from lab returned `ok: true` with attestation
`host_id=desktop-in7o23d`, `hostname=DESKTOP-IN7O23D`, `machine_fingerprint=63bcf7a63d612973`, `os=windows`,
`worker_version=b3679ba981bf` (the home checkout head). Ollama reachable; `codex` not installed; GPU yield inactive at
that moment. `write_prerequisites.runner_units` is `false`: "runner units are not implemented on Windows (S6.12 job
objects pending, B12)". The machine fingerprint is now pinned in `config/estate.yaml`.

### Detached-process survival (runbook step 7)

**Not runnable with the current worker code.** With the sentinel in place, `start` of the `noop-sleep` runner was
refused with `executor_unavailable: ... runner units are not implemented on Windows (S6.12 job objects pending, B12)`.
The survival check therefore could not be executed, no `worker_capabilities.json` was written, and the sentinel was
removed again. Consequence: nothing that needs detached Windows runners (every write lane) can be qualified on home
until S6.12 is implemented. It does not affect deterministic compute or synchronous local inference.

### Inventory

`inventory` verb, attested: five live models (`qwen3:8b`, `llama3.1:8b`, `qwen2.5-coder-cc:latest`,
`qwen2.5-coder:7b`, `qwen2.5-math:7b`), executors `{deterministic: true, local: true, codex: false, codex-write: false}`,
repo `odysseus` resolved at `E:\aoteru\odysseus-aoteru` (head `b3679ba981bf`), other repos unresolved, 16 CPUs, NVIDIA
GeForce RTX 3070 8 GB, 223 GB free on the worker volume.

### Local-model qualification (runbook step 8): **not qualified**

`scripts/run_lm4_production_canary.py --worker-host desktop-in7o23d --aliases local-fast`, run id
`lm4-canary-32c8bfb757`, ran through the real worker path (`call_worker ... execute local-inference`, attested by
home). Result: **0 pass, 3 fail, 0 error**; every item failed with `502: POST http://127.0.0.1:11434/api/chat failed:
timed out` after its 120 s limit, and again on the single repeat.

This is not a model-quality result. Investigation on home:

- The GPU was at ~98-100% utilisation and ~7.8 GB of 8 GB memory in use for the whole investigation, **including with
  Ollama's model unloaded**.
- Per-process GPU counters attributed ~92% of the GPU to `OMDDSteam-Win64-Shipping.exe` (the game *Orcs Must Die
  Deathtrap*) running on the household desktop. The game was not touched.
- A 16-token `qwen3:8b` request with thinking disabled also timed out at 100 s while the game ran, so the host cannot
  currently serve inference at all. A first window of the contention was also my own backlog of timed-out thinking-mode
  requests, which drained.

Home is a shared household gaming desktop, so the GPU is not reliably available. `local-fast` is **not** added to
`qualified_hosts`. It must be measured again at a time the GPU is free, and the worker's GPU-yield behaviour deserves
its own review (a game can starve a routed local-inference call; the call times out rather than being refused up
front). The canary artifacts and the isolated results database from this run were not committed (artifact paths for
`qwen3:8b` contain `:`, which cannot be checked out on Windows).

### Routing proof

With home enabled for `deterministic` only, resolved against the real `config/estate.yaml` in a checkout with live worker
health (`eligible_hosts()` showed both hosts reachable and healthy):

| Case | Result |
|---|---|
| Request pinned to home (`placement.requested_host`), no capability | resolves to `desktop-in7o23d` ("eligible; no model capability was requested") |
| Request pinned to home for `local-fast` | **not** silently run elsewhere: "needs escalation: alias local-fast not qualified on desktop-in7o23d" |
| Unpinned request | resolves to `hz2-workstation`, unaffected |

So `route.host` names the machine that is physically selected, a missing qualification fails truthfully rather than
falling back to lab or the laptop, and lab stays independently usable.

### STT workload

Home-local speech-to-text is exercised by the live household deployment rather than through the worker: the transcript
runtime transcribes on `desktop-in7o23d` with `faster-whisper` `base.en` (about 0.7 s for a short utterance), with the
transcript row's `stt.host` attributing the home machine (see
`automation/review/misumi-long-horizon-programme-evidence.md`).

### Decision

Governed commit: `worker.enabled: true`, `qualified_executors: [deterministic]`, machine fingerprint pinned, host key
and target recorded. Not qualified: `local` (benchmark blocked by GPU contention), `codex` (not installed),
`codex-write` (operator decision, plus the missing detached-runner/job-object support above). Withdraw by setting
`enabled: false` or emptying `qualified_executors`.

Follow-ups: re-run the `local-fast` canary on a free GPU, then add `desktop-in7o23d` to `local-fast`
`qualified_hosts` in `config/models.yaml` by a governed commit; implement S6.12 job objects before any Windows write
lane; and the privilege-boundary task
`automation/review/agent-tasks/inbox/2026-10-02-home-worker-non-admin-identity.agent-task.md`.

---
title: Aoteru truthful multihost execution — implementation plan
status: plan (architecture authority for implementation; no production code changed by this document)
as_of: 2026-09-22
base: origin/dev d2fc0ba
owner: odysseus
source_task: tyecam1/obsidian-PhD automation/review/agent-tasks/ready/2026-09-22-odysseus-multihost-routing-plan.agent-task.md (PR #565)
reconciles_with: tyecam1/obsidian-PhD automation/review/agent-tasks/ready/2026-09-03-odysseus-cross-device-delegation-lifecycle-hardening.agent-task.md
contract: docs/aoteru-model-host-routing-contract.md
nondelegation_reason: architecture_judgement
---

# Aoteru truthful multihost execution — implementation plan

Central invariant this plan makes enforceable:

> `route.host` identifies the machine that physically executed the task.

Target chain:

```text
Aoteru -> one Odysseus control plane (lab backend, svc:odysseus-lab)
       -> resolve_route(host, capability)
       -> worker on the selected host (same logical contract on Linux lab and Windows home)
       -> execution on that host
       -> attested result / EstateExecution
       -> central telemetry (RoutingDecision) -> caller
```

Line numbers below refer to `origin/dev` at `d2fc0ba`. "Verified" means
read in live code or observed at runtime on 2026-09-22. "Inference" is
marked explicitly.

---

## A. Verified diagnosis

### A.0 Live state at planning time (verified 2026-09-22)

| Item | Observation |
|---|---|
| `origin/dev` | `d2fc0ba`; the live lab checkout `/home/agent/projects/odysseus-aoteru` is on `dev` at the same SHA, clean |
| Lab backend | `odysseus-aoteru-lab.service` active, `127.0.0.1:7001`, `GET /api/health` → `healthy` |
| Lab Ollama | `127.0.0.1:11434` lists `qwen3:8b`, `gpt-oss:20b`, `ornith:9b`, `nemotron-3.5-lightning:30b-a3b`, `gemma4:12b`, `qwen3-embedding:8b`, `dengcao/Qwen3-Reranker-8B:Q4_K_M` (all bound aliases present), plus unbound extras |
| Home (`desktop-in7o23d`) | `tailscale status`: **offline, last seen 1d ago**. TCP probes from lab to 22/420/4500/11434 all closed/filtered. No home runtime claim in this plan is re-verified today; home facts come from the 2026-08-29 evidence (`docs/aoteru-p13-laptop-reentry-evidence.md`) |
| Home Ollama (2026-08-29 evidence, not re-verified) | `qwen3:8b`, `llama3.1:8b`, `qwen2.5-coder-cc`, `qwen2.5-coder:7b`, `qwen2.5-math:7b` |
| Telemetry (`data/app.db`, read-only query) | Every `routing_decisions` row has `host_id = hz2-workstation` (≈480 rows) except one `none`. Every `estate_executions` row (10: 7 succeeded, 3 failed) has `host_id = hz2-workstation`. No active ParkLease |
| Open PRs | #39 (contract doc wording: dependency direction), #40 (AGENTS.md + repositories.yaml identity wording), #38 (GLM candidate worker), #35 (ingest). None touch host placement |
| `chatgpt/model-effort-routing-20260910` | 7 commits ahead of dev: effort vocabulary, GLM merge, native `claude` launch in `scripts/agent`. Keeps `execute_local` on `_OLLAMA_BASE` (its diff lines 110/121). **Does not address placement** |
| Sept 3 lifecycle task | Still `ready` and **not implemented on dev**: `companion/laptop_client/aoteru.py` has no execution status/wait subcommand; no branch implements it |
| Delegation preflight | `aoteru` CLI is not on PATH in this session; `POST /api/estate/preflight` returns `Not authenticated` without a token. This unit is retained with `nondelegation_reason: architecture_judgement` (the source task mandates a single Opus architecture pass) |

### A.1 Material defects

**D1 — Host selection is metadata; local inference always runs on the backend host.** *Verified.*
- Current behaviour: `resolve_route()` picks `host = eligible[0]` (`src/estate_router.py:486`). `run_task()` then calls `execute_local(concrete_model, objective)` (`:1704`), which calls `llm_call(_OLLAMA_BASE, ...)` (`:686`) with `_OLLAMA_BASE = "http://127.0.0.1:11434"` (`:239`). Nothing reads `route.host` between selection and execution.
- Evidence: code path above. Telemetry is 100% `hz2-workstation` because the eligible set has only ever been `{hz2-workstation}`, which is also the backend host.
- Contract consequence: the invariant holds **only by coincidence**. The moment any second host becomes eligible, `route.host = home` will be recorded while inference runs on lab's GPU. That makes telemetry false, and so the learning loop, locality and data-policy decisions are false too.
- Existing branch/PR: none. The effort branch keeps the backend-local call.

**D2 — Paid Codex (read-only advisory) launches on the backend host.** *Verified.*
- `run_task()` → `execute_codex(paid_objective, cwd=repo_cwd)` (`:1661`) → `_execute_codex_with_sandbox` (`:891`) → local `subprocess.Popen([codex_binary, "exec", ...])` (`:916`). `_codex_available()` (`:730`) checks the backend's `~/.local/codex-cli` and `~/.codex/auth.json`. `delegation_preflight.py:94` reuses the same backend-local check.
- Consequence: same as D1. The route response then rewrites `route.executor = "codex"` while keeping `route.host` (`:1683-1690`) without checking where it ran.
- Existing branch/PR: none (#38 adds another backend-local paid worker).

**D3 — Repository paths are resolved on the backend host.** *Verified.*
- `resolve_repo_path()` (`:101-134`) reads the backend's `~/.aoteru/config.local.json` and calls `Path.exists()` on the backend filesystem. `worktree_ops.verify_worktree`, `create_or_reuse_worktree` and `is_live_checkout_path` all run backend-local git.
- Consequence: "repo available" means available on lab, whatever host was routed.

**D4 — Governed writes are only possible on the backend host.** *Verified. This is correct fail-closed behaviour today, not a bug.*
- `run_task()` implementation mode refuses unless `route.host == current_host_id()` (`:1604-1613`). `_codex_write_authority()` (`:999-1025`) mixes DB lease authority with backend-local filesystem checks. `POST /api/estate/park/{repo_id}`, `/heartbeat` and `/release` all bind `host_id = current_host_id()` (`routes/estate_routing_routes.py`), so a lease can only be acquired for the backend host.
- Consequence: the guard is the only thing that stops untruthful write placement. The plan must keep it as a fail-closed rule, restated as "the lease holder must equal the executing, attested host", while adding a remote path.

**D5 — Model capability truth is global and lab-derived.** *Verified.*
- `config/models.yaml` has one global `binding` per alias. `resolve_alias()` (`:311-349`) checks liveness only against the backend's Ollama (`_ollama_model_live`, `:242`). The context-window check uses `get_context_length_known(_OLLAMA_BASE, ...)` (`:515-516`). GPU yield (`experiment_priority_active`, `:265`) reads lab's reservation file and lab's `nvidia-smi`.
- Concrete mismatch (inference from the 2026-08-29 home inventory): of the bound aliases, only `local-fast` (`qwen3:8b`) exists on home. `code-fast` (`ornith:9b`), `local-strong`, `reasoning-strong`, `vision`, `embedding` and `reranker` do not. If home were eligible today, a `home` + `code-fast` route would "resolve live" against **lab's** Ollama.
- Existing branch/PR: none.

**D6 — `verified` is overloaded.** *Verified.*
- `host_reachable()` (`:64-95`) uses one boolean for both "identity confirmed" and "may receive work". `config/estate.yaml:157` says so directly: "this is the sole gate". The P13 evidence (residual risk 3) records that home identity is confirmed while `verified: false` is kept only to block worker eligibility. Reachability is a TCP connect to port 22, not a worker-level health check.
- Consequence: there is no truthful way to say "identity verified, worker not qualified". Flipping the boolean would grant eligibility with zero qualification evidence.

**D7 — EstateExecution reconciliation and process cleanup assume the backend host and Linux.** *Verified.*
- `reconcile_stale_estate_executions()` checks liveness with `os.kill(pid, 0)` on the backend (`:1182`). `_kill_process_tree()`/`_process_tree_pids()` walk `/proc` (`:746-888`). A remote row's `worker_pid` means nothing locally. Such a row would be relabelled `interrupted` while its process may still be writing on the remote host, which re-opens admission under the same lease.
- Existing branch/PR: none.

**D8 — No first-class observation surface for callers (Sept 3 defect).** *Verified.*
- `GET /api/estate/run/{execution_id}` exists server-side but has no bounded wait. The laptop client has no read-only status command, so repeated `aoteru ask` gets used as a poll. That chains sequential paid executions (Sept 3 ground truth).
- Existing branch/PR: none. The Sept 3 task is still `ready`.

**D9 — Remote-native `agent claude` dispatch is unimplemented.** *Verified. Out of scope.*
- `scripts/agent` `cmd_claude` fails truthfully for non-local hosts. This plan neither changes nor depends on it.

**D10 — Stale documentation.** *Verified.*
- The contract's "Host model" block still uses the `verified/healthy/reachable` triple and `home: availability: unavailable`. `docs/aoteru-operating-handbook.md` says no HTTP park/heartbeat/release surface exists, but the routes exist. `docs/aoteru-interface-pc-deployment.md` says `interface-pc` is `os: unknown`/`verified: false`, while `config/estate.yaml` has Windows and `verified: true`.
- Only the contract host-model block is updated by this plan (Stage 1). The rest is listed under non-goals.

### A.2 What is already right and must be preserved

- ParkLease single-active-lease invariant (`ix_park_leases_active_repo_unique`) and `park_lease_is_stale`.
- EstateExecution admission control (`ix_estate_executions_active_lease_unique`, `_in_flight_execution_for_lease`).
- Codex process-tree timeout cleanup (Linux).
- `requested_host` narrowing without silent substitution (`:448-465`).
- `nondelegation_reason` validation at the decision-write boundary.
- The household/Misumi deployment on home: separate `odysseus-releases\e68288238b3c`, port 420, `misumi_agent.py` 4500, STT 4600, scheduled task `Odysseus-Misumi` managed by `scripts/windows/odysseus-host.ps1`. The 2026-08-29 audit found no estate router and no estate config there. It stays a household adapter (Q4).

### A.3 Answers to the task's questions

1. **Is host routing only metadata?** Yes, for every executor (D1–D3). Writes are protected only by the D4 equality guard. The smallest seam is one call, `run_task()` → *dispatch to worker on `route.host`*. The execution primitives (`execute_local`, `execute_codex`, `_execute_codex_with_sandbox`, `worktree_ops`, `resolve_repo_path`) are already correct *when run on the target host*, because they use host-local `127.0.0.1`, `~/.aoteru` and `~/.codex`. The defect is *where they are called from*, not what they do. The worker reuses them unchanged.
2. **Is capability host-specific enough?** No (D5). Minimum fix: per-alias `qualified_hosts` in `config/models.yaml`, plus per-host `qualified_executors` in `config/estate.yaml`, plus live per-host inventory from the worker. An alias is routable on host H only if all three agree. No scheduler.
3. **Is `verified` overloaded?** Yes (D6). Split it into `identity_verified` (static, config), live `healthy` (runtime, worker health probe) and `worker.enabled` + `worker.qualified_executors` (config, governed, evidence-backed), plus per-alias host qualification. Home becomes `identity_verified: true, worker.enabled: false`. `verified: true` is never set on home.
4. **Home service role?** Preserve the household service untouched. The home worker is a **separate checkout of this repo, invoked on demand over SSH**. It has no listener, no scheduled task, no database, and no routing, lease or lifecycle authority. `svc:odysseus-home.endpoint` stays `null`.
5. **Lifecycle integration?** EstateExecution stays the only lifecycle store. Remote write execution is observed through the worker's `status` verb and written into EstateExecution by the control plane. Stage 6 adds the bounded `wait` and the client `execution` command from the Sept 3 task, plus two distinct non-running states so worker loss is bounded rather than ambiguous: `interrupted` (worker reached, runner positively confirmed dead) and `lost` (outcome cannot currently be determined — unreachable, not a synonym for dead) (§I.2 sets the sequencing).

---

## B. Minimal target execution flow

```text
caller (laptop aoteru / scripts/agent / HTTP)
  │  POST /api/estate/run  {task envelope, placement.requested_host, mode?}
  ▼
CONTROL PLANE (lab backend, the only authority)
  1. resolve_route(task)
       static gates  : role∈{lab,home} ∧ identity_verified ∧ worker.enabled      (config/estate.yaml)
       live gate     : worker health OK + attested identity (cached ≤30s)       (estate_worker_client)
       lease gate    : no live lease for repo held by a different host          (ParkLease)
       per-route     : alias ∈ qualified_hosts[H] ∧ model ∈ inventory[H]        (models.yaml + inventory)
                       executor ∈ qualified_executors[H] ∧ repo ∈ inventory[H]
       selection     : first host in estate.yaml order passing all gates (no scoring)
       → RoutingDecision row (host_id = selected host)
  2. dispatch       : call_worker(route.host, verb, payload)
                       LocalTransport only if route.host == current_host_id(); else SshTransport
                       NEVER falls back to another host or to in-process execution
  3. attestation    : response.attestation.host_id == route.host ∧ nonce echo
                       ∧ machine_fingerprint == config (when pinned) — else placement_mismatch
  4a. read-only     : synchronous execute → result → RoutingDecision.executed_host_id, outcome
  4b. write         : lease authority (DB) → admission (EstateExecution) → worker start
                       → monitor thread polls worker status → EstateExecution transitions
                       → RoutingDecision outcome; caller observes via GET /run/{id}?wait=
  5. response       : route + placement{routed_host, executed_host, attested} + execution_id/next_action
  ▼
WORKER (lab: same checkout via subprocess; home: separate checkout via SSH)
  stateless per call; executes on its own host using host-local primitives;
  keeps a transient spool only for detached write runs (evidence, not authority)
```

| Responsibility | Owner |
|---|---|
| Routing, host/model selection, eligibility | `src/estate_router.py` (control plane) |
| Host identity / worker enablement / executor qualification (static) | `config/estate.yaml` (governed) |
| Alias-per-host qualification (static) | `config/models.yaml` (governed) |
| Live health, inventory, repo availability | Worker `health`/`inventory`/`repo.probe`, cached in `src/estate_worker_client.py` memory only |
| Write authority | ParkLease (control-plane DB) |
| Execution lifecycle | EstateExecution (control-plane DB) |
| Telemetry | RoutingDecision (control-plane DB), with new `executed_host_id` |
| Physical execution | Worker on the selected host |
| Transport | `LocalTransport` (subprocess) / `SshTransport` (pinned key, forced command) |

---

## C. Worker protocol — `aoteru-worker/1`

### C.1 Transport

- **Entry point:** `python -m src.estate_worker [--root <checkout>]`. Reads **one JSON request on stdin** and writes **one JSON response on stdout**. JSON is never passed through argv, which avoids the Windows quoting failure that PR #34 addressed. Exit code is `0` for any handled request, including an `ok: false` response. It is non-zero only when the protocol itself breaks (unparseable stdin, crash); the client maps that to `worker_protocol_error`.
- **LocalTransport:** `subprocess.run([sys.executable, "-m", "src.estate_worker"], input=..., cwd=<app root>, timeout=deadline_s + 15)`. It raises `WorkerTransportError("local transport refused for non-local host")` unless `host_id == current_host_id()`.
- **SshTransport:** runs `ssh` with this argv:
  - `-o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=<generated> -o ConnectTimeout=6 -o ServerAliveInterval=15 -o ServerAliveCountMax=2 -i <key> <target>`
  - `<generated>` is a temp known_hosts file built from `worker.ssh.host_public_key` in `config/estate.yaml`.
  - `<key>` is the host-local `~/.aoteru/worker_ssh_key` on the backend host, never committed.
  - No remote command argument is sent. The home `authorized_keys` entry pins it with `command="cmd.exe /c cd /d <checkout> && <checkout>\venv\Scripts\python.exe -m src.estate_worker --root <checkout>",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding` — the explicit `cd` is required because `python -m src.estate_worker` has to import the module before `--root` (parsed inside `main()`) ever runs, and an OpenSSH forced command does not guarantee the session starts in the checkout; see `docs/aoteru-home-worker-setup.md` step 4.
  - Missing `host_public_key` → `WorkerTransportError("host_key_unpinned")`. `StrictHostKeyChecking=no` is forbidden; do not reuse `routes/shell_routes.py:_ssh_base_argv`.
  - Timeout is `deadline_s + 15` (read-only codex: 180 + 15 = 195 s, below the 210 s `/api/estate/run` watchdog).
- There is no new listener, port, firewall rule or scheduled task on any host.

### C.2 Envelope

Request:

```json
{
  "protocol": "aoteru-worker/1",
  "request_id": "uuid4",
  "verb": "health | inventory | repo.probe | execute | worktree.prepare | worktree.verify | start | status | cancel | worktree.finalize",
  "expected_host_id": "desktop-in7o23d",
  "nonce": "32 hex chars",
  "deadline_s": 120,
  "payload": {}
}
```

Response:

```json
{
  "protocol": "aoteru-worker/1",
  "request_id": "echo",
  "ok": true,
  "error": null,
  "attestation": {
    "host_id": "desktop-in7o23d",
    "hostname": "DESKTOP-IN7O23D",
    "machine_fingerprint": "16 hex chars",
    "os": "windows",
    "worker_pid": 4242,
    "worker_version": "git HEAD sha of worker checkout",
    "nonce": "echo",
    "observed_at": "ISO-8601 UTC"
  },
  "result": {}
}
```

- `error` is `{"code": "<code>", "message": "<text>"}` when `ok` is false.
- `attestation.host_id` is computed by the worker from its own hostname against its own checkout's `config/estate.yaml`, using `estate_router.current_host_id()`. No match gives the error `identity_unregistered` and `host_id: null`.
- `expected_host_id != attestation.host_id` → the worker itself refuses with `identity_mismatch` before doing any work.
- `machine_fingerprint` is `sha256(machine id)[:16]`. On Linux the machine id is `/etc/machine-id`. On Windows it is `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid`, read with `winreg`. It is not secret.

Error codes (closed set): `unsupported_protocol`, `unknown_verb`, `bad_request`, `identity_unregistered`, `identity_mismatch`, `executor_unavailable`, `model_absent`, `context_limit`, `repo_unavailable`, `authority_denied`, `timeout`, `execution_failed`, `not_found`, `worker_protocol_error` (client-side only), `worker_unreachable` (client-side only), `placement_mismatch` (client-side only).

### C.3 Verbs

| Verb | Payload | Result | Reuses |
|---|---|---|---|
| `health` | `{}` | `ollama: {reachable, base_url, error}`, `codex: {available, detail}`, `gpu_yield: {active, reason}`, `in_flight: [execution_id]`, `time_utc` | `_codex_available`, `experiment_priority_active` (evaluated on the worker host) |
| `inventory` | `{models_of_interest: [name]}` | `models: [{name, digest}]`, `context: {name: {length, known}}` (only for `models_of_interest`), `executors: {deterministic, local, codex, "codex-write"}` (booleans: runtime present *and*, for `codex-write`, platform supported), `repos: [{repo_id, resolved, path, head_sha, clean}]`, `hardware` | Ollama `/api/tags`, `get_context_length_known("http://127.0.0.1:11434", m)`, `scripts/home_reentry_inventory._hardware` logic (move to an importable helper), `resolve_repo_path`, `park_lease_ops.git_is_clean` |
| `repo.probe` | `{repo_id}` | `{resolved, path, head_sha, branch, clean}` | same |
| `execute` | `{kind: "local-inference" \| "codex-readonly", model?, objective, repo_id?, timeout_s}` | `{ok, output, latency_ms, retries, provider, concrete_model, model_digest?}` | `estate_router.execute_local(model, objective, timeout=timeout_s)`; `estate_router.execute_codex(objective, cwd=resolve_repo_path(repo_id))` |
| `worktree.prepare` | `{repo_id, branch, base_ref, lease: {lease_id, host_id}}` — `lease` required from Stage 6 (§6.0 S6.7); missing → `bad_request` before any git mutation | `{path, branch, head_sha, clean}` | `worktree_ops.create_or_reuse_worktree`, `verify_worktree`, `git_is_clean` |
| `worktree.verify` | `{repo_id, worktree_path, branch}` | `{ok, path, reason, head_sha, clean}` (refuses the live checkout; `head_sha`/`clean` added in Stage 6, S6.1/S6.2) | `worktree_ops.verify_worktree`, `is_live_checkout_path`, `git_is_clean` |
| `start` | `{execution_id, kind: "codex-write", objective, repo_id, lease: {lease_id, worktree_path, branch}, timeout_s}` | `{accepted, state, handle: {pid, create_time, spool_id} \| null, reused: bool, spawned?}` — `state` per the S6.6 start state machine | re-runs `worktree.verify` (TOCTOU), atomically claims the spool with a durable `starting` state (S6.6), then spawns detached `python -m src.estate_worker --run-spooled <execution_id>`, which calls `_execute_codex_with_sandbox(sandbox="workspace-write", cwd=verified path, on_started=spool writer)` |
| `status` | `{execution_id}` | `{state: unknown\|starting\|accepted\|running\|succeeded\|failed\|timed_out\|start_failed, handle, process_alive, spawned, started_at, finished_at, result?}` (`starting`/`start_failed`/`spawned` added in Stage 6, S6.6) | spool + `estate_worker_procs.is_alive(handle)` |
| `cancel` | `{execution_id}` | `{killed, still_alive_pids}` | `estate_worker_procs.kill_tree(handle)` |
| `worktree.finalize` | `{repo_id, worktree_path, branch, commit_message}` | `{committed, pushed, commit_sha, dirty_paths, push_error?}` | git logic moved out of `finalize_execution` (`:1434-1476`) |

Rules:
- `start` is **idempotent per `execution_id`**. If a spool exists, it returns the existing state (and handle, once one exists) with `reused: true` and never spawns twice. That is the defence against a retried `start` after a lost response. From Stage 6 the spool is claimed atomically *already carrying* a durable `starting` state, so a same-ID `start` arriving before the handle is persisted gets a non-terminal `starting` answer, never `execution_failed` (S6.6 — replaces the pre-Stage-6 200 ms handle poll in `_existing_start_result`).
- The spool lives at `~/.aoteru/worker-spool/<execution_id>/` and holds `request.json`, `state.json` and `result.json`. It is transient evidence for the control plane, **not** a lifecycle authority. The worker garbage-collects terminal spools older than 7 days on any call.
- The worker **never** imports `core.database`, never reads or writes ParkLease or EstateExecution, and never decides routing. A test asserts `"core.database" not in sys.modules` after each verb.
- The worker never pulls, deletes or changes Ollama models. It never touches household data roots, the `Odysseus-Misumi` task, or port 420.
- `start` also accepts `kind: "noop-sleep"` (sleep `timeout_s`, then write a fixed result), but **only** when the home-local sentinel file `~/.aoteru/worker_selftest_enabled` exists (read by `estate_worker._selftest_enabled()`). Otherwise it returns `bad_request`. A sentinel file, not an environment variable, because every `call_worker()` call opens its own fresh forced-command SSH session and never inherits environment set in some other session — see `docs/aoteru-home-worker-setup.md` step 7. It exists for the Stage 4 survival check and integration test I4, and the control plane never sends it.
- `effort` is **not** part of `aoteru-worker/1`. It is added only when the effort branch is integrated after this plan (non-goal).

---

## D. State model

| State | Where | Written by | Meaning |
|---|---|---|---|
| Host identity | `config/estate.yaml` `hosts[].identity_verified` (+ `identity_evidence`) | Governed commit | Hostname and SSH host key confirmed live by a human-supervised session. **Grants no eligibility on its own.** |
| Transport pin | `hosts[].worker.transport` (`local`\|`ssh`), `worker.ssh.target`, `worker.ssh.host_public_key` (public key, non-secret), `worker.machine_fingerprint` | Governed commit | How to reach the worker, and which identity it must present |
| Worker enablement | `hosts[].worker.enabled` | Governed commit | Operator allows routing to this host at all |
| Executor qualification | `hosts[].worker.qualified_executors` (subset of `deterministic, local, codex, codex-write`) + `qualification_evidence` | Governed commit | Evidence-backed permission per executor |
| Alias-per-host qualification | `config/models.yaml` `capabilities[].qualified_hosts: {<host_id>: {evidence, binding?}}` | Governed commit | Alias measured adequate on that host. The optional per-host `binding` overrides the default concrete model |
| Live health | Worker `health`; in-memory TTL cache (30 s) in `estate_worker_client` | Runtime | Worker answered in time with a valid attestation |
| Live inventory | Worker `inventory`; in-memory TTL cache (60 s) | Runtime | Models, executors and repos physically present now |
| Repo availability | Worker `inventory.repos` / `repo.probe` | Runtime | Resolves on *that* host |
| Write authority | `park_leases` row (`host_id` = lease holder); `status` `preparing \| active \| released` (`preparing` added in Stage 6, S6.7) | Control plane | `host_id` may now be a remote host. Whether a lease is authoritative or reclaimable is decided only by `lease_authority_state()` (S6.4), never by heartbeat age alone |
| Execution lifecycle | `estate_executions.lifecycle_state` | Control plane only | Process/outcome only: `accepted → running → succeeded \| failed \| timed_out \| interrupted \| lost` |
| Worktree resolution | `estate_executions.worktree_resolution` (Stage 6, S6.1) | Control plane only | `unresolved \| not_started \| finalized \| recovered \| legacy_closed`. The **only** field admission, release and reclaim read to decide whether a lease's worktree is reusable; a terminal `lifecycle_state` never implies it |
| Routing telemetry | `routing_decisions` row | Control plane | `host_id` = routed. New `executed_host_id` = attested host (null if nothing executed) |

Rules:
- Eligible host = `role ∈ {lab, home} ∧ identity_verified ∧ worker.enabled ∧ live health OK`.
- Executable route on H requires, in addition:
  - `executor ∈ qualified_executors[H]`;
  - `executors[executor]` true in the live inventory;
  - every requested alias has `H ∈ qualified_hosts`, with its concrete model in inventory[H] and `gpu_yield` inactive for `yield_to_experiment` aliases;
  - the repo (if any) resolves on H;
  - no live lease for the repo held by a host other than H.
- Legacy `verified` key: Stages 1–8 read it as `identity_verified` only when `identity_verified` is absent. `verified: false` still hard-blocks. It never implies `worker.enabled`. Stage 9 removes the fallback.
- Nothing about health or inventory is persisted in a new table. `hosts_checked` in route responses, plus `executed_host_id`, carry the evidence.
- `lost` is terminal for **observation**: status/wait return promptly. It is still **blocking for admission** under the same lease (its `worktree_resolution` stays `unresolved`, S6.1) and dispatch returns `lease_has_unresolved_lost_execution`. Its `lifecycle_state` is corrected by the next successful worker `status` (to the spool's true state, or `interrupted` if the runner is confirmed dead). That correction changes the outcome only; it never resolves the worktree. Neither ordinary release nor recovery release (S6.2) accepts a `lost` row, because the writer might still be running. See §I.3 B9 for a host that never comes back.

---

## E. Ordered file/function patch plan

Each stage is one reviewable commit series with its own tests. Stages are sequential. Do not start stage N+1 until stage N's tests pass and it is committed. Suite to run at the end of every stage:

```text
venv/bin/python -m pytest tests/test_estate_router.py tests/test_estate_execution_runtime.py \
  tests/test_estate_routing_routes.py tests/test_laptop_client.py tests/test_park_lease_ops.py \
  tests/test_agent_cli_parking_lease.py tests/test_routing_decision_lookup.py tests/test_routing_evaluator.py \
  tests/test_estate_worker*.py -q
```

### Stage 1 — Truthful host state semantics (config and gates only; no behaviour change for lab)

Files and changes:
- `config/estate.yaml`:
  - lab `hz2-workstation`: add `identity_verified: true` and `worker: {enabled: true, transport: local, qualified_executors: [deterministic, local, codex, codex-write], qualification_evidence: [docs/aoteru-lm4-production-canary-evidence.md, docs/aoteru-p12-active-estate-convergence-evidence.md]}`.
  - home `desktop-in7o23d`: replace `verified: false` with `identity_verified: true`, `identity_evidence: docs/aoteru-p13-laptop-reentry-evidence.md`, and `worker: {enabled: false, transport: ssh, ssh: {target: null, host_public_key: null, command: null}, machine_fingerprint: null, qualified_executors: [], qualification_evidence: null}`.
  - interface-pc: rename `verified: true` to `identity_verified: true`, with no `worker` block.
  - Rewrite the header comment and the home note to describe the split.
- `src/estate_router.py`:
  - Add `host_static_state(host: dict) -> dict` returning `{identity_verified, worker_enabled, transport, qualified_executors}`.
    - `identity_verified`: read `identity_verified`. If absent, fall back to legacy `verified`. If both are absent, `False` (fail closed).
    - `worker_enabled`: `bool((host.get("worker") or {}).get("enabled"))`.
  - Rewrite `host_reachable(host, live_hostname) -> (bool, reason)`, keeping the signature because `scripts/agent` imports it. Gate order:
    - identity not verified → `"<id> identity not verified"`;
    - worker not enabled → `"<id> identity verified; worker not enabled (worker qualification pending)"`;
    - then the existing this-host / tailnet / TCP-22 logic, unchanged in Stage 1.
  - Change `eligible_hosts()` entries additively: add `identity_verified`, `worker_enabled`, `reachable`, and `healthy: None` (filled in Stage 5).
- `docs/aoteru-model-host-routing-contract.md`: replace the "Host model" YAML block and the "Home becomes eligible only…" text with the Section D semantics. Nothing else in the contract changes. If PR #39 has merged, rebase onto it. If not, keep the edit confined to that block so #39 still merges.
- `config/routing.yaml`: update only the `home:` comment to point at `worker.enabled`/`qualified_executors`.

Invariants:
- Production eligibility is unchanged: lab eligible, home ineligible.
- The home reason text now distinguishes identity from worker qualification.
- `verified: true` appears nowhere on home.

Tests (`tests/test_estate_router.py`, updating `fixture_config` to the new keys):
- `test_home_identity_verified_but_worker_disabled_is_ineligible_with_worker_reason`
- `test_legacy_verified_false_still_blocks`
- `test_missing_identity_keys_fail_closed`
- `test_identity_verified_never_implies_worker_enabled`
- `test_shipped_estate_config_home_worker_disabled`: loads the real `config/estate.yaml` and asserts home `worker.enabled is False` and has no `verified` key. **Only Stage 8's governed commit may change this assertion.**
- `test_shipped_estate_config_lab_worker_local`

Dependencies: none.

### Stage 2 — Worker contract: protocol, entry point, Linux process layer

Files:
- `src/estate_worker_protocol.py` (new, stdlib only):
  - `PROTOCOL = "aoteru-worker/1"`, `VERBS`, `ERROR_CODES`;
  - `build_request(verb, expected_host_id, payload, deadline_s) -> dict` (generates `request_id`, `nonce`);
  - `validate_request(obj) -> (ok, error)` and `validate_response(obj, request) -> (ok, error)`;
  - `error_response(request, code, message, attestation)`.
- `src/estate_worker_procs.py` (new):
  - **move** `_proc_stat_fields`, `_proc_ppid`, `_proc_is_live_nonzombie`, `_process_tree_pids` and `_kill_process_tree` from `src/estate_router.py` into this module unchanged;
  - re-export them from `estate_router` under the same names (`from src.estate_worker_procs import ...`), so existing tests and monkeypatches keep working;
  - add `spawn_detached(argv, cwd, log_path) -> {"pid", "create_time"}` (Linux: `subprocess.Popen(..., start_new_session=True, stdin=DEVNULL, stdout/stderr → log file)`; `create_time` = `/proc` starttime);
  - add `is_alive(handle) -> bool` (pid + starttime match, non-zombie) and `kill_tree(handle) -> dict` (wraps `_kill_process_tree`);
  - Windows functions are added in Stage 4. Until then they raise `NotImplementedError("windows process layer lands in stage 4")`.
- `src/estate_worker.py` (new):
  - `main(argv=None)`: parses `--root` (chdir + `sys.path` insert) and `--run-spooled <execution_id>`.
  - `handle(request: dict) -> dict`: validate → identity check → dispatch to `_verb_<name>` → attach `attestation()`.
  - One function per verb in §C.3. `_verb_execute` delegates to `estate_router.execute_local` / `execute_codex`. `_verb_start`, `_verb_status` and `_verb_cancel` use the spool and `estate_worker_procs`.
  - `_run_spooled(execution_id)`: the detached runner. It writes `state.json` (`running`, pid) through `on_started`, then `result.json` and the terminal state.
  - `attestation(nonce)` and `machine_fingerprint()`.
  - Spool GC.
- Keep `src/estate_worker.py` a plain module, not a package. `python -m src.estate_worker` works because it ends with an `if __name__ == "__main__": sys.exit(main())` block.

Invariants:
- Worker verbs never import `core.database`.
- `start` never spawns twice for one `execution_id`.
- Every response carries an attestation. The worker refuses when `expected_host_id` differs from its own identity.

Tests:
- `tests/test_estate_worker_protocol.py`: request/response validation, unknown verb, bad protocol, error code set closed.
- `tests/test_estate_worker.py`: uses the `fixture_config` pattern with `THIS-HOST` and monkeypatches `execute_local`, `execute_codex` and `_execute_codex_with_sandbox`. Tests:
  - `health` shape;
  - `inventory` lists `models_of_interest` context and repos;
  - `identity_mismatch` refusal;
  - `execute` local and codex-readonly delegate with the correct args;
  - `start` idempotency (second call `reused: true`, spawn called once);
  - `status` for running, terminal and unknown;
  - `cancel`;
  - `worktree.verify` refuses the live checkout;
  - no `core.database` import;
  - CLI round-trip through `subprocess` (stdin JSON → stdout JSON, exit 0 on `ok: false`).
- The existing `tests/test_estate_router.py` process-tree tests pass unchanged (via re-exports).

Dependencies: Stage 1 (the worker computes identity from the config).

### Stage 3 — Lab execution through the worker contract (LocalTransport) and truthful telemetry

Files:
- `src/estate_worker_client.py` (new):
  - `class WorkerTransportError(Exception)` (with `.code`).
  - `class LocalTransport` and `class SshTransport`. `SshTransport` gets a full implementation in Stage 4; here it raises `WorkerTransportError("worker_unreachable", "ssh transport lands in stage 4")`.
  - `transport_for_host(host_id) -> transport`: reads `config/estate.yaml`. `local` requires `host_id == current_host_id()`, else `WorkerTransportError("placement_mismatch")`.
  - `call_worker(host_id, verb, payload, *, deadline_s) -> dict` (build request → transport → validate → `verify_attestation`).
  - `verify_attestation(response, request, host_cfg) -> None`: raises `WorkerTransportError("placement_mismatch")` on a host_id or nonce mismatch, or on a fingerprint mismatch when `worker.machine_fingerprint` is set.
  - `worker_health(host_id)` and `worker_inventory(host_id, models_of_interest)` with TTL caches, plus `clear_caches()` for tests.
- `src/estate_router.py`:
  - Add `_dispatch_read_only(route, task) -> dict`, which calls `call_worker(route["host"], "execute", {...})` and maps transport or worker errors to `{"ok": False, "error": ..., "error_code": ...}`.
  - In `run_task()`: replace the `execute_local(concrete_model, objective)` call (`:1704`) and the advisory `provider_fn(paid_objective, cwd=repo_cwd)` call (`:1661`) with `_dispatch_read_only`. The provider table maps `codex` → worker kind `codex-readonly`.
  - Keep `_PAID_PROVIDER_FUNCTION_NAMES` for the write lane until Stage 6.
  - Add a `placement` block to every executed response: `{"routed_host", "executed_host" (attested or null), "attested": bool, "transport": "local"|"ssh"}`.
  - Implementation mode is unchanged in this stage. It still runs in-process under the existing `route.host == current_host_id()` guard, which is truthful.
  - `_update_decision_outcome(..., executed_host_id=None)`: new kwarg, written to the new column.
- `core/database.py`: add `RoutingDecision.executed_host_id = Column(String, nullable=True, index=True)`. Extend the tuple in `_migrate_add_routing_delegation_columns()` with `"executed_host_id"`.
- `src/routing_evaluator.py` `get_decision_by_id()`: include `executed_host_id` in its projection.

Invariants:
- `run_task()` never calls `execute_local` or `execute_codex` in-process.
- Transport failure → `executed: False`, `ok: False`, `escalation_reason: worker_failed`, `RoutingDecision.status = failed`, `executed_host_id = null`, **no retry on another host, no in-process fallback**.
- Attestation mismatch → the same, with `error_code: placement_mismatch` and the attested host recorded in `actual_route` as `placement_mismatch:<attested>`.

Tests (`tests/test_estate_router.py`, `tests/test_estate_worker_client.py` new):
- `test_run_task_local_dispatches_via_worker_and_records_executed_host`
- `test_run_task_never_calls_execute_local_in_process` (monkeypatch `estate_router.execute_local` to raise; LocalTransport patched to a fake worker)
- `test_worker_unreachable_fails_closed_without_fallback`
- `test_attestation_host_mismatch_is_placement_mismatch`
- `test_nonce_mismatch_is_placement_mismatch`
- `test_local_transport_refuses_non_local_host`
- `test_codex_readonly_dispatched_to_routed_host`
- `test_routing_decision_executed_host_id_migration_idempotent`
- An integration test that runs the real `LocalTransport` subprocess against a fake Ollama (monkeypatched base URL env or a `127.0.0.1` stub server) end to end.

Dependencies: Stage 2.

### Stage 4 — Windows/home worker adapter and SSH transport (home still disabled)

Files:
- `src/estate_worker_procs.py`, Windows implementation selected by `os.name == "nt"`:
  - `spawn_detached`: `subprocess.Popen(argv, cwd, stdin=DEVNULL, stdout/stderr → log, creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_BREAKAWAY_FROM_JOB, close_fds=True)`. `create_time` comes from `ctypes` `GetProcessTimes`.
  - `is_alive`: `ctypes` `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` + `GetExitCodeProcess == STILL_ACTIVE` + creation-time match.
  - `kill_tree`: `taskkill /PID <pid> /T /F`, then re-check `is_alive` for the root and report `still_alive_pids`.
  - If `CREATE_BREAKAWAY_FROM_JOB` is refused (`OSError`, access denied because the sshd job forbids breakaway), return `WorkerError("executor_unavailable", "detached spawn not permitted in this session")`. **No silent fallback.**
- `src/estate_worker.py`:
  - `machine_fingerprint()` Windows branch (`winreg`);
  - `codex-write` executor reported `false` in `inventory` when the process layer is not proven. A host-local flag file `~/.aoteru/worker_capabilities.json` `{"detached_spawn_verified": true}` is written only by the Stage 4 live check, never by code paths that route work.
- `src/estate_worker_client.py`: implement `SshTransport` exactly per §C.1. The known_hosts file is generated into a `tempfile.NamedTemporaryFile` from `worker.ssh.host_public_key`, with the target host alias `worker.ssh.target`'s host part.
- `docs/aoteru-home-worker-setup.md` (new runbook; operator-executed, no automation):
  1. Clone `tyecam1/odysseus` to a dedicated path, recommended `E:\aoteru\odysseus-aoteru`. This must **not** be the household `odysseus-releases\...` directory.
  2. `py -3 -m venv venv` + `venv\Scripts\pip install -r requirements.txt`.
  3. Create `%USERPROFILE%\.aoteru\config.local.json` with the root vars (`AI_ROOT`, `PHD_ROOT`, `HOUSEHOLD_ROOT`) for any repos home should serve.
  4. On lab, generate `~/.aoteru/worker_ssh_key` (ed25519, `agent` user) and authorise its public key on home with the forced-command options in §C.1. If the home account is an administrator, use `C:\ProgramData\ssh\administrators_authorized_keys`.
  5. Record home's SSH host **public key** (its fingerprint must equal the pinned `SHA256:rmuPA4DUnFnR8UPXBHrksljQbT86l2aZZAztNZ1TIeU`) into `worker.ssh.host_public_key`, and fill in `worker.ssh.target` and `worker.ssh.command` (documentation only; the forced command is authoritative) by governed commit.
  6. Run the read-only health check from lab: `venv/bin/python -c "from src.estate_worker_client import call_worker; print(call_worker('desktop-in7o23d','health',{},deadline_s=20))"`.
  7. Run the detached-spawn survival check: on home, create the sentinel file `~/.aoteru/worker_selftest_enabled` by hand, then from lab `start` a no-op spooled runner (`kind: "noop-sleep"`, test-only, 60 s), then `status` after 30 s. Record `process_alive: true` → write `detached_spawn_verified`, then delete the sentinel file.
- `scripts/windows/odysseus-host.ps1`: **not touched.**

Invariants:
- Home stays `worker.enabled: false`; the Stage 1 shipped-config test still passes.
- `SshTransport` never disables host-key checking.
- The request travels only on stdin.

Tests:
- `tests/test_estate_worker_client.py`: SSH argv contains `BatchMode=yes`, `StrictHostKeyChecking=yes` and `UserKnownHostsFile`, and never `StrictHostKeyChecking=no`; no remote command argument; JSON on stdin; unpinned host → `host_key_unpinned`; timeout → `worker_unreachable`; non-zero exit → `worker_protocol_error`.
- `tests/test_estate_worker_procs.py`: Windows branch tested with `monkeypatch` of `os.name`/`ctypes`/`subprocess` (flag composition, taskkill argv, breakaway refusal → `executor_unavailable`). The Linux branch is tested for real (spawn a `sleep`, `is_alive`, `kill_tree`, pid-reuse safety).

**Stop gate:** if step 7 shows the runner does not survive the SSH session close on home, do not proceed to any home write qualification. Record it in the evidence doc. Home remains read-only-only (`codex-write` never enters `qualified_executors`). Continue with Stages 5–8 for read-only.

Dependencies: Stage 3.

### Stage 5 — Route selection by live worker health and per-host inventory; fail-closed dispatch

Files:
- `src/estate_router.py`:
  - `eligible_hosts(repo_id=None)`: after the Stage 1 static gates, call `worker_health(host_id)` for each candidate. Failure → `eligible: False`, `healthy: False`, `reason: "worker unreachable: <code>: <msg>"`. Remove the TCP-22 probe from `host_reachable` (keep the function as the static-gate wrapper for `scripts/agent`). Keep the existing lease-conflict filter.
  - `resolve_alias(alias, host_id=None)`:
    - `host_id is None` keeps legacy behaviour, used only by `GET /route/alias/{alias}` and `scripts/agent explain`. Those callers switch to passing `current_host_id()` in this stage.
    - With `host_id`: binding lookup, then membership in `worker_inventory(host_id, [binding])["models"]`, then `gpu_yield` from `worker_health(host_id)` for `yield_to_experiment` aliases.
    - Remove the control-plane use of `_ollama_model_live` and `experiment_priority_active`; both now live in the worker.
  - `resolve_route(task)`: replace `host = eligible[0]` (`:486`) with `_select_host(eligible, capabilities, task) -> (host, capability_resolutions, executor)`:
    1. Walk hosts in `estate.yaml` order. Pick the first host where all requested aliases resolve **on that host** and `"local"` is in its `qualified_executors` → executor `local`.
    2. Otherwise, if no capabilities were requested → first host, executor `deterministic` (nothing executes; `executed_host_id` stays null).
    3. Otherwise → first host whose `qualified_executors` contains `"codex"` and whose live `health.codex.available` → executor `none` / `needs_escalation` (paid lane decides).
    4. Otherwise → first host, `needs_escalation`. The paid lane will then fail `executor_unavailable` truthfully.
    - An explicit `requested_host` narrows the candidates first. There is never a substitution.
  - Context-window check: use `worker_inventory(host, [model])["context"][model]` instead of `get_context_length_known(_OLLAMA_BASE, ...)`.
  - In `run_task()`, before any dispatch, the resolved executor must be in `qualified_executors[route.host]`. Otherwise → `blocked`, `escalation_reason: worker_failed`, `execution_error: "executor <x> not qualified on <host>"`.
- `src/delegation_preflight.py:94`: replace `estate_router._codex_available()` with `worker_health(<routed host>)["codex"]`.
- `routes/estate_routing_routes.py`: `/route/hosts` returns the richer entries; `/route/alias/{alias}` accepts `?host=`.
- `scripts/agent`: `cmd_explain` and `cmd_status` pass `current_host_id()` to `resolve_alias`; no other change.
- `companion/laptop_client/aoteru.py`: `cmd_status` prints `identity_verified`/`worker_enabled`/`healthy` per host (display only; reads keys defensively).

Invariants:
- Model truth for host H comes only from H's worker.
- An alias absent on H fails for H even if lab has it.
- A route never executes on a host other than `route.host`.

Tests are listed in the §G matrix, items U1–U12.

Dependencies: Stage 4. The SSH path is exercised by fakes in unit tests; home is still disabled in the shipped config.

### Stage 6 — EstateExecution through the worker; status/wait; remote leases (Sept 3 reconciliation)

#### 6.0 Authority and race contract (final pre-implementation correction, 2026-09-23)

This block governs every Stage 6 step below. Where an older sentence further down disagrees with it, this block wins, and the implementer must report the disagreement. It adds no second queue, lifecycle store, lease system or lock table. Everything is expressed with `EstateExecution` plus `ParkLease`, using one new column on each (`worktree_resolution`; one new `status` value `preparing`). Workers stay DB-free.

Live evidence behind it (branch `feat/multihost-stage1-3-20260922` at `ad1e55b`):
- `src/estate_worker.py` `_verb_start`: `spool.mkdir()` → `request.json` → `spawn_detached` → `state.json` with the handle, in that order. `_existing_start_result` polls 20 × 10 ms for a handle, then raises `execution_failed`. So a same-ID retry that lands before the handle is written fails while the first start may still be progressing.
- `_verb_worktree_prepare` calls `create_or_reuse_worktree`, which runs `git worktree add [-b]` with no lease. `park_lease_ops.park_repo_by_id(branch=...)` does the same before `park_repo` (`src/park_lease_ops.py:96-106`).
- `park_lease_is_stale()` (age only) decides "ignorable/reclaimable" in three places: `park_repo`'s reclaim (`park_lease_ops.py:133`), `active_lease_for_repo` (`:221`; used by `_codex_write_authority` and `git_finalizer.py:217`), and `eligible_hosts`' conflict filter (`estate_router.py:253`). `scripts/agent:587-608` presents `stale` as the "write-enforcement signal".
- The engine is SQLAlchemy 2.0.52 on pysqlite (Python 3.12, SQLite 3.53) with default deferred transactions (`core/database.py:76-79`). No `BEGIN IMMEDIATE` and no `with_for_update()` exist anywhere in the estate paths. So "one session" SELECT-then-INSERT is **not** serialized against a concurrent release: the partial index `ix_estate_executions_active_lease_unique` catches only a concurrent *admission*.
- Both partial unique indexes declare only `sqlite_where` (`core/database.py:778`, `:1013`). On PostgreSQL that silently becomes a *full* unique index.
- `ix_estate_executions_active_lease_unique` covers only `lifecycle_state IN ('accepted','running')`, so the database does not back the Stage 6 blocking states at all.

**Vocabulary.** Every rule below uses exactly one of these facts:

| Fact | Stored in | Values | Authority |
|---|---|---|---|
| Process state | worker spool `state.json`, read only through `status` | `unknown`, `starting`, `accepted`, `running`, `succeeded`, `failed`, `timed_out`, `start_failed`; plus `process_alive`, `spawned` | worker evidence (never authority) |
| Execution outcome | `EstateExecution.lifecycle_state` | `accepted` (with the `pending_start` placeholder sub-state), `running`, `succeeded`, `failed`, `timed_out`, `interrupted`, `lost` | control plane |
| Worktree resolution | `EstateExecution.worktree_resolution` (new) | `unresolved`, `not_started`, `finalized`, `recovered`, `legacy_closed` | control plane |
| Lease authority | `ParkLease.status` + `lease_authority_state()` | `preparing`, `active`, `released`; `authoritative: bool` | control plane |
| Lease heartbeat age | `park_lease_is_stale()` | bool | **telemetry only** |
| Lease reclaimability | `lease_authority_state()` | `reclaimable: bool`, `protected_by_execution_id` | control plane; the only rule |

**S6.1 Worktree resolution is separate from process outcome.**
- New column `EstateExecution.worktree_resolution` (String, NOT NULL, default `unresolved`). Admission inserts every row as `unresolved`. Only three transitions leave `unresolved`, and each commits inside the lease-serialized transaction of S6.5:
  - `not_started`: only on a **positively observed pre-spawn refusal**. Either `start` returns a deterministic refusal (`authority_denied`, `bad_request`, `executor_unavailable`) without claiming the spool, or `start`/`status` reports `start_failed` (S6.6: no writer ran). `lifecycle_state` becomes `failed` in the same write.
  - `finalized`: only in `finalize_execution`. Preconditions: the row is `succeeded`, the lease is still authoritative with the identical `lease_id`/`host_id`/`worktree_path`/`branch`, the worker `worktree.finalize` returned success, and a post-finalize `worktree.verify` reports `clean: true` for that exact path and branch. A failed push is recorded in `finalization_json` and reported. It does not keep the worktree unresolved, because the commit exists on the branch and the tree is clean.
  - `recovered`: only in recovery release (S6.2), atomically with releasing the lease.
- Admission effect of each combination (this replaces the lifecycle-state list formerly in step 4):

  | `lifecycle_state` | `worktree_resolution` | New dispatch under the same lease |
  |---|---|---|
  | `accepted` (incl. `pending_start`) / `running` | `unresolved` | duplicate → `dispatch: reused_in_flight`, same `execution_id`, no new `start` (U16) |
  | `lost` | `unresolved` | refused `lease_has_unresolved_lost_execution` |
  | `succeeded` | `unresolved` | refused `lease_has_unfinalized_execution`; `next_action` = finalize or recover |
  | `failed` / `timed_out` / `interrupted` | `unresolved` | refused `lease_has_unresolved_worktree`; `next_action` = recover (S6.2) |
  | `failed` | `not_started` | not blocking (no writer ran) |
  | `succeeded` | `finalized` | not blocking. A new admission still needs the lease authoritative and a fresh `worktree.verify` reporting `clean: true` (step 2) |
  | any | `recovered` / `legacy_closed` | not blocking; a `recovered` row's lease is already released, so a fresh park is needed anyway |
- **I6 (restated):** a terminal `lifecycle_state` never admits a fresh dispatch by itself. Admission requires, all at once:
  - the exact lease is authoritative;
  - no row under that `lease_id` has `worktree_resolution = 'unresolved'`;
  - the step-2 `worktree.verify` reported `clean: true`.
- **Database backstop:** `ix_estate_executions_active_lease_unique` is recreated with predicate `worktree_resolution = 'unresolved'`, declared with both `sqlite_where` and `postgresql_where`. That allows at most one unresolved row per lease, enforced by the database under any interleaving.
- **Migration** `_migrate_add_estate_execution_worker_columns()` also adds `worktree_resolution`, backfills it, and then drops and recreates the index:
  - Backfill: a row whose `lease_id` is not a currently `active` lease → `legacy_closed`; every other row → `unresolved`.
  - If the backfill leaves more than one `unresolved` row for one lease, the migration logs an error naming the lease and rows, keeps the old index, and does not raise. The in-Python rule then still sees the unresolved rows and blocks that lease until S6.2 recovery. The next start retries the index creation.
  - §A.0 recorded no active ParkLease on the live DB. Re-check this before deploying Stage 6.

**S6.2 Recovery release: the only way out of an unresolved worktree other than finalization.**
- Interface: `estate_router.recover_execution_lease(execution_id, *, lease_id, host_id, repo_id, branch, worktree_path) -> dict`. HTTP is `POST /api/estate/park/{repo_id}/recover` (scope `estate:execute`, JSON body with all five identifiers). The laptop client gets `aoteru recover <repo_id> --execution <id> --lease <id> --host <id> --branch <b> --worktree <path>`. Every identifier is required; none is inferred or defaulted.
- Preconditions. Any failure → refused, and nothing changes:
  1. The execution row exists, and its `lease_id`, `host_id`, `repo_id`, `branch` and `worktree_path` equal the supplied values exactly.
  2. The lease row with that id is `active`, and its `host_id`, `repo_id`, `branch` and `worktree_path` also match.
  3. `worktree_resolution == 'unresolved'` and `lifecycle_state ∈ {succeeded, failed, timed_out, interrupted}`. `accepted`, `running`, `pending_start` or `lost` → `execution_not_settled` (cancel/wait first; a `lost` row must first be reconciled by a successful `status`).
  4. A **fresh** worker `status` on `host_id` (not a cached observation) answers, its handle matches `worker_handle_json`, and it reports a terminal state or `process_alive: false`. Worker unreachable → `worker_unreachable`, refused. Anything the control plane cannot observe, it cannot recover.
  5. A **fresh** worker `worktree.verify` for the exact path and branch returns `ok: true` and `clean: true`. Dirty → `worktree_not_clean` with the evidence. The operator resets, commits or stashes, then retries. Operator commits are allowed. The resulting `head_sha` is recorded.
  6. In one S6.5 lease-serialized transaction, re-read both rows and require them unchanged since step 1. Then set `worktree_resolution = 'recovered'`, append `{recovery: {head_sha, clean: true, observed_state, at}}` to `finalization_json`, and set the lease `released`/`released_at`. Commit.
- Afterwards the repo needs a fresh park and a fresh `lease_id`. Recovery never re-arms the old lease.
- **Ordinary release stays closed.** `release_repo` (and `/park/{repo_id}/release`, `agent release`) re-reads the lease inside the S6.5 transaction. It is refused with `lease_has_unresolved_execution` (returning `execution_id`, `lifecycle_state` and `next_action`) whenever any row under that lease is `unresolved`. It gains no force flag. Ordinary release succeeds only for a lease with no executions, or with only `not_started`/`finalized` rows.

**S6.3 Execution-supervision renewal is separate from operator heartbeat.**
- New `park_lease_ops.renew_lease_for_execution(execution_id) -> bool`, called only by the control plane. It reads the execution row, then issues one conditional write keyed on the **exact** recorded lease:
  `UPDATE park_leases SET heartbeat_at = :now WHERE id = :row.lease_id AND status = 'active' AND repo_id = :row.repo_id AND host_id = :row.host_id`
  It runs only if the row is still `accepted`/`running` and `unresolved`. `rowcount == 0` → returns `False` and logs. It never falls back to a repo/host lookup, so it can never renew a later or reassigned lease. It cannot acquire, replace or broaden a lease.
- Callers: the monitor thread (step 8) and reconciliation, only right after a successful `status` for a **confirmed** execution (step 7 done) that positively reports `accepted`/`running` with `process_alive: true`. A `starting`/`pending_start` execution is not yet confirmed and is not renewed. S6.4 protects it anyway. It is not exposed on HTTP, the CLI or the worker protocol, and the DB-free worker has no equivalent.
- The operator heartbeat (`heartbeat_repo`, `/park/{repo_id}/heartbeat`, `agent heartbeat`) keeps its existing meaning: renew the caller's active lease for repo[/host], never acquire. It is **allowed** while an execution is active, since renewing is harmless and reclaim protection comes from S6.4, not from heartbeat age. It is refused only for a `preparing` reservation, which is not yet write authority. This replaces the old U32 "heartbeat refused while active" clause.
- Renewal is not the safety mechanism, because S6.4 already protects a lease with an unresolved execution whatever its heartbeat age. It exists so heartbeat-age telemetry stays truthful for a supervised lease.

**S6.4 One canonical, execution-aware reclaimability rule.**
- New `park_lease_ops.lease_authority_state(db, lease, *, now=None) -> {lease_id, status, heartbeat_stale, protected_by_execution_id, authoritative, reclaimable, reason}`:
  - `released` → `authoritative: False`, `reclaimable: False` (nothing to reclaim; not authority).
  - `preparing` → a reservation. It blocks competing parks and routing to other hosts, but is **not** write authority (`authoritative: False` for admission, finalize and recovery). `reclaimable` iff `heartbeat_at` is older than `PARK_PREPARE_STALE_SECONDS = 300` (prepare `deadline_s` + transport + margin). A `preparing` row can never have executions.
  - `active` → `protected_by_execution_id` = the id of any row under this `lease_id` with `worktree_resolution = 'unresolved'` (whatever its `lifecycle_state`, including `lost` and `pending_start`). `reclaimable = heartbeat_stale ∧ protected_by_execution_id is None`. `authoritative = ¬reclaimable`.
- Every write-authority decision goes through it:
  - `park_repo` stale reclaim: reclaim only if `reclaimable`;
  - `eligible_hosts(repo_id)` conflict filter: an `active` or `preparing` lease on another host blocks unless `reclaimable`;
  - `active_lease_for_repo` / `_lease_authority` / `_codex_write_authority` / `git_finalizer`: return the lease iff `status == 'active' ∧ authoritative`, including `heartbeat_stale` and `protected_by_execution_id`. A stale-but-protected lease is found and protected. A stale unprotected lease is `None`, which fails closed as today;
  - `release_repo` and recovery (S6.2);
  - admission (step 3);
  - `active_leases_summary` and `scripts/agent` status, which show `stale` next to `reclaimable`/`protected_by`. The `scripts/agent` comment calling `stale` the write-enforcement signal is corrected.
- `park_lease_is_stale()` stays as raw heartbeat-age telemetry. A test asserts it is referenced only by `core/database.py`, `lease_authority_state` and display projections. No other caller may infer "ignorable/reclaimable" from age.

**S6.5 Serialization of admission against release/reclaim.**
- Invariant: *no release or reclaim of lease L can commit between Stage 6's final authority validation of L and the commit of the EstateExecution row admitted under L; admission cannot slip past a release or reassignment of L committed concurrently.*
- New `core.database.lease_serialized_transaction(lease_id=None, repo_id=None)` context manager. Engine-specific code lives next to the engine, so this is one helper, not a lock table:
  - **SQLite:** a dedicated connection whose first statement is `BEGIN IMMEDIATE`. That takes the database write lock before any read in the transaction, so every read inside it (lease row, unresolved executions) is current and no other writer can commit until it ends. pysqlite defers `BEGIN` until the first DML by default, so the helper must issue `BEGIN IMMEDIATE` itself, scoped to that connection (SQLAlchemy's pysqlite recipe: driver-level autocommit on that connection, then `exec_driver_sql("BEGIN IMMEDIATE")`). It must **not** change transaction behaviour for other users of the global engine. The busy timeout is bounded (≥ 5 s). If it expires, the operation fails closed with a retryable error and never proceeds unlocked.
  - **Other backends:** an ordinary transaction whose first statement is `SELECT … FROM park_leases WHERE id = :lease_id FOR UPDATE` (`with_for_update()`). For park, where no lease row exists yet, it is `… WHERE repo_id = :repo_id AND status IN ('active','preparing') FOR UPDATE`. All later reads in the transaction run after the lock (READ COMMITTED takes a fresh snapshot per statement).
- Users, all of which change lease authority or admit under it:
  - admission steps 3–5;
  - ordinary release;
  - recovery release;
  - `park_repo` reclaim plus insert. These become **one** transaction; today they are two sessions (`park_lease_ops.py:130-155`);
  - the `preparing → active` bind and the `preparing` rollback (S6.7);
  - the resolution write in `finalize_execution`;
  - the `not_started` write.
  - Exception: S6.3 renewal is a single conditional `UPDATE` that cannot change authority, so it does not need the helper.
- No worker call (`worktree.verify`/`prepare`/`status`/`start`/`finalize`) is ever made while holding this lock. The lock scope is DB-only and short. That is exactly why authority is **re-validated inside** the transaction after the remote call, rather than held across it.
- Backstops stay in place: `ix_park_leases_active_repo_unique` (predicate becomes `status IN ('active','preparing')`) and the S6.1 execution index, both with `sqlite_where` **and** `postgresql_where`.

**S6.6 Race-safe same-`execution_id` `start` (worker).**
- Atomic claim: `_verb_start` builds `.<execution_id>.tmp-<uuid>/` containing `state.json = {state: "starting", handle: null, spawned: false, claimed_at}` and `request.json`, then `os.rename`s it to `<execution_id>/`. The rename is atomic on POSIX, and on Windows it fails if the target exists. The loser of a concurrent claim, or a later retry, therefore always sees a spool that already has a state. No spool directory is ever visible without `state.json`.
- Spawn succeeds → `state.json` is replaced with `{state: "accepted", handle, spawned: true}`, but only if the current state is still `starting`. A writer that finds a non-`starting` state leaves it alone.
- Spawn fails deterministically (`ProcessLayerError`/`OSError` before a child exists) → `state.json = {state: "start_failed", spawned: false, error}` plus `result.json`. The spool is **not** deleted. The pre-Stage-6 `rmtree` is what let a retry start fresh and be mistaken for a first attempt.
- Runner (`_run_spooled`) finds no handle within its bounded wait → it writes `start_failed` with `spawned: true, executed: false`, because it never ran the writer. Today it writes a generic `failed`.
- A `starting` spool older than `STARTING_STALE_SECONDS = 60` (well past the runner's 5 s handle wait) is rewritten to `start_failed` by the next `status`/`start` touching it. By then no child can be executing: either none was spawned, or it aborted itself for lack of a handle. Any remaining ambiguity resolves to a *blocking* control-plane state (`interrupted`/`unresolved`), never to a reusable one.
- Same-ID `start` answers from the existing spool and never raises `execution_failed` for an in-progress claim:
  - `starting` → `{accepted: false, state: "starting", handle: null, reused: true}` (non-terminal, pending);
  - `accepted`/`running`/terminal → `{accepted: true, state, handle, reused: true}`;
  - `start_failed` → `{accepted: false, state: "start_failed", spawned, reused: true}` plus the error.
- `status` distinguishes:
  - `unknown` (no spool: `start` never reached this worker);
  - `starting`;
  - `accepted`/`running` with a handle;
  - terminal `succeeded`/`failed`/`timed_out`;
  - `start_failed`.
- Control-plane mapping in step 6:
  - `starting` → stay `accepted` + placeholder (`pending_start`) and poll `status`, bounded by `execution_deadline_at`;
  - `accepted`/`running`/terminal with a handle → confirmed → step 7;
  - `start_failed` → `failed` + `not_started` (S6.1);
  - `status` returns `unknown` → re-issue `start` with the same `execution_id`. This is safe because of the atomic claim.

**S6.7 Worktree preparation happens under ParkLease authority (remote and local branch park).**
- New `park_lease_ops.park_with_worktree(repo_id, host_id, branch, *, prepare) -> dict` replaces the mutate-then-lease order for every park that creates or reuses a worktree:
  1. **Reserve.** In one S6.5 transaction, reclaim a prior lease only if `lease_authority_state` says `reclaimable`, then insert `ParkLease(status="preparing", host_id, repo_id, branch, worktree_path="")`. `worktree_path` stays `NOT NULL`, so there is no table rebuild. The empty string is the documented "not yet bound" value, and every write-authority reader already requires `status == 'active'`. A concurrent park loses here, on the unique index or the conflict check → `ParkConflict`, **before any worker call**.
  2. **Prepare under that authority.** `prepare(repo_id, branch, lease={lease_id, host_id})`. For a remote host this is worker `worktree.prepare`, whose payload now requires `lease` or returns `bad_request` before any git mutation. For the local host it is in-process `worktree_ops` (lab is the backend host). No lock is held during the call.
  3. **Evidence.** The result must carry `path`, `branch == requested`, `head_sha` and `clean: true`. `clean` is never inferred from a successful path or branch verification.
  4. **Bind.** In one S6.5 transaction, re-read the reservation by exact `lease_id` and require `status == 'preparing'` (not reclaimed meanwhile) with matching `host_id` and `branch`. Then set `worktree_path = path`, `status = 'active'`, `heartbeat_at = now`.
  5. **Failure** (worker error or unreachable, lost response, `clean != true`, branch mismatch, bind refused): in one S6.5 transaction, set the reservation `released`. Releasing a `preparing` row is always safe, because no execution can exist under a non-active lease. The call returns the existing 409 shapes (`RepoNotClean`, `WorktreeVerificationError`). A worktree the worker may already have created stays on disk as clean, unowned evidence. Automation never deletes it on a remote host. A later park reuses it only through the same sequence, and a dirty reused worktree fails closed at step 3.
- The branchless local park (the live checkout path, no worktree creation) is unchanged: clean check, then `park_repo`.

Files:
- `core/database.py`:
  - add `EstateExecution` columns `worker_handle_json` (Text), `worker_attestation_json` (Text), `last_observed_at` (DateTime) and `execution_deadline_at` (DateTime);
  - `execution_deadline_at` (item 5 — final contract-hardening review finding) is set once, when the row is created (`now + timeout`), and is what all `lost` reconciliation computes its `+ 120 s` bound from — never the `timeout` argument a particular `execute_write_via_worker`/monitor-thread call happened to be invoked with. This is specifically what makes the bound reconstructable after a control-plane restart: process-local arguments do not survive a restart, but this column does, so reconciliation started by a fresh process still applies the exact same deadline to a row it did not itself create;
  - add `lost` and `interrupted` to the lifecycle docstring, with the distinction stated explicitly (pre-Stage-6 contract-correction review finding): `lost` means the outcome **cannot currently be determined** (the worker is unreachable, or has not been observed within the bounded window) — it is never a synonym for "the process is dead." `interrupted` means the worker **was reached** and truthfully reported the stored `accepted`/`running` row's runner is no longer alive (`process_alive: false`) — a positively observed, not inferred, outcome;
  - `worker_handle_json` is set to a non-null durable dispatch-state placeholder **at row creation**, before `start` is even called (see step 5 below) — a legacy pre-Stage-6 row is the only case where this column is genuinely `NULL`; a new Stage-6 row is never `NULL`, even if it crashes or loses its `start` response before a confirmed handle exists (pre-Stage-6 review finding: `worker_handle_json IS NULL` stopped being a safe "legacy row" test the moment Stage 6 creates the durable row before `start`);
  - add `EstateExecution.worktree_resolution` (S6.1) and recreate `ix_estate_executions_active_lease_unique` with predicate `worktree_resolution = 'unresolved'` (`sqlite_where` + `postgresql_where`);
  - `ParkLease.status` gains `preparing` (S6.7); recreate `ix_park_leases_active_repo_unique` with predicate `status IN ('active','preparing')` (`sqlite_where` + `postgresql_where`);
  - add `lease_serialized_transaction()` (S6.5);
  - add migration `_migrate_add_estate_execution_worker_columns()` (same pattern as `_migrate_add_routing_delegation_columns`), called from `init_db()` after `create_all`. It performs the S6.1 backfill and both index recreations.
- `src/estate_router.py`:
  - `_lease_authority(repo_id, host_id) -> dict`: the DB-only half of `_codex_write_authority`. It requires an `active` lease held by `host_id` that is `authoritative` under `lease_authority_state()` (S6.4, not raw heartbeat age), with `allowed_write_scope == "repo"`, `branch` and `worktree_path`. It returns `heartbeat_stale` and `protected_by_execution_id` too.
  - `execute_write_via_worker(objective, *, repo_id, host_id, decision_id, wait_timeout=30.0, timeout=1800.0) -> dict`:
    1. `_lease_authority(repo_id, host_id)` — a preliminary check only, giving the `lease_id`, `branch` and `worktree_path` needed to ground the remote verify call below. This is evidence to act on, not the authority moment itself (pre-Stage-6 review finding, item 3: a single early check like this must never be relied on to still hold true by the time `start` is issued).
    2. `call_worker(host_id, "worktree.verify", ...)` against that `worktree_path`/`branch`. `ok != true` **or `clean != true`** (S6.1: every admission, including one reopened after finalization, requires a clean worktree) → `authority_denied`/`worktree_not_clean`, no row, no transaction opened.
    3. **Enter `lease_serialized_transaction(lease_id)`** (S6.5; a plain session is not enough on pysqlite, whose deferred `BEGIN` leaves these reads outside any write lock). Inside it, re-read the row for the **exact `lease_id`** from step 1. Do not do a fresh "current lease for repo/host" lookup, which could silently pick up a *different* lease issued after step 1. Require, all in the same transaction:
       - still `active` and `authoritative` under `lease_authority_state()` (S6.4);
       - still held by `route.host`;
       - `allowed_write_scope == "repo"`;
       - the same `worktree_path` and `branch` just verified in step 2.
       Any mismatch → `write_lease_missing`/`authority_denied`, no row is created, no `start` is ever issued, transaction rolled back. This is what closes the gap where a lease could be released or reassigned between step 1's early check and remote `start` — the moment that matters (row creation + dispatch) is re-validated, not assumed.
    4. Still inside that same transaction, look up any row under that exact `lease_id` with `worktree_resolution = 'unresolved'` (S6.1). The admission outcome is taken from the S6.1 table, never from `lifecycle_state` alone:
       - `accepted`/`running`, including `pending_start` → `dispatch: "reused_in_flight"` with that `execution_id`;
       - `lost` → `lease_has_unresolved_lost_execution`;
       - `succeeded` → `lease_has_unfinalized_execution`;
       - `failed`/`timed_out`/`interrupted` → `lease_has_unresolved_worktree`.

       Each refusal carries the blocking `execution_id` and a `next_action` (wait / finalize / recover). This keeps admission single-flight under one lease, with no second row and no second store. No second writer is ever dispatched into a worktree that an earlier writer, finished or not, may have left dirty. The only ways back to an admissible lease are finalization (`finalized`, same lease, clean) or explicit recovery: S6.2 `recover` → lease released → fresh park and fresh `lease_id` → new execution.
    5. Still inside the same transaction: `_create_estate_execution` (accepted), with `worker_handle_json` set to a non-null dispatch-state placeholder (e.g. `{"dispatch_state": "pending_start"}`), **not** `NULL` — the row is durably marked as a real, in-flight Stage-6 execution from the moment it exists, before `start` is even attempted (this is also what step 4's "unresolved `pending_start`" blocking state refers to). `execution_deadline_at` (see its `core/database.py` bullet above) is set here too, from `timeout`, so the value driving `lost` reconciliation is durable from the moment the row exists, not a process-local argument. Commit.
    6. Only after that transaction commits does the control plane call `call_worker(host_id, "start", ...)`. **A transport/protocol failure or lost response here is not proof nothing started** (pre-Stage-6 review finding: an earlier pass already corrected the plan's prior "row failed, because nothing started" claim — this restates the corrected state machine precisely; S6.6 makes the worker side race-safe). The worker may have already created the spool and spawned the detached writer before the response was lost; `start`'s own idempotency per `execution_id` (same `execution_id` in a retried `start` → existing handle, `reused: true`, never a second spawn) exists specifically so this can be resolved safely. The explicit state machine:
       - first `start` response lost/failed transport-side → the row is **not** marked `failed`; it stays `accepted` with the step-5 placeholder still in place (this is the "unresolved `pending_start`" state step 4 blocks new admission on);
       - retry `call_worker(host_id, "start", ...)` with the **same `execution_id`**;
       - retried `start` reports `reused: true` with `state: "starting"` → still unresolved (`pending_start`); poll `status` per S6.6, never `failed`;
       - retried `start` reports `reused: true` with a handle (`accepted`/`running`/terminal) → the execution is **confirmed**; proceed to step 7 (transition to `running`). A successful same-ID retry is **never** evidence for `failed`, however the first attempt's response was lost;
       - `start`/`status` reports `start_failed` → `failed` + `worktree_resolution = 'not_started'` (S6.1/S6.6; the writer positively never ran);
       - a clean new `start` with that same `execution_id` (the worker genuinely never received/processed the first one) → also **confirmed**; proceed to step 7 — likewise never evidence for `failed`;
       - a **deterministic pre-spawn refusal** from the worker (e.g. `authority_denied`, `bad_request`: the worker positively refused before claiming the spool) → this alone may transition the row to `failed` + `not_started`. The resolution write happens inside `lease_serialized_transaction`;
       - still unreachable or otherwise ambiguous after a retry → remain unresolved (`accepted` + placeholder); only the bounded observation rule in step 8 may later resolve it to `lost` — silence or unreachability alone is never, by itself, evidence for `failed`;
       - dispatch (`start`) and observation (`status` polling in step 8) stay separate calls throughout; resolving an uncertain `start` reuses the same two verbs, never a new one, and never opens a second admission window (step 4 already blocks that for the whole `accepted`/`pending_start` window).
    7. Once `start` is confirmed per step 6, update the row to `running`, replacing the step-5 placeholder with the real `worker_handle_json`, plus `worker_attestation_json`, `worker_pid` and `started_at`. Exactly one spawn happens across the whole step-6 sequence, however many `start` calls it took to confirm.
    8. Start the monitor thread `_observe_worker_execution(execution_id, host_id, timeout)`: poll `status` every 5 s. After each successful observation of a confirmed `accepted`/`running` execution with `process_alive: true`, call `renew_lease_for_execution(execution_id)` (S6.3, exact lease only). No transition in this step changes `worktree_resolution`; outcome and resolution are separate facts.
       - Worker reachable, stored state `accepted`/`running`, `status` reports `process_alive: false` → this is **not** unknown: the host answered and the runner is truthfully known dead. Write the row `interrupted` promptly (do not wait for the `lost` timeout below) and record `_update_decision_outcome(executed_host_id=host_id, ...)`. The worktree stays `unresolved`, so the lease stays blocked until S6.2 recovery.
       - Worker reachable and terminal (`succeeded`/`failed`/`timed_out`) → write the terminal row and `_update_decision_outcome(executed_host_id=host_id, ...)` as before. `worktree_resolution` stays `unresolved`: `succeeded` awaits finalization or recovery, and `failed`/`timed_out` await recovery (S6.1).
       - Worker unreachable, or otherwise not currently observable → keep polling; do not guess. With no successful observation past the row's persisted `execution_deadline_at + 120 s` → `lost` (outcome undetermined, not "process dead"). The persisted deadline is used rather than the `timeout` argument this call happened to be started with because after a control-plane restart, `_observe_worker_execution` may not even be the thread that resumes watching this row, so the bound must be reconstructable from the row alone.
       - No redispatch occurs merely because a row became `lost`, `interrupted` or any terminal state. Those are observations, not admission decisions. A new admission still goes through step 4's check, which stays blocked while the worktree is `unresolved`, i.e. until finalization or S6.2 recovery, not merely until observation.
    9. Bounded join (`wait_timeout`), same response contract as today plus `dispatch` and `next_action`.
  - `_PAID_PROVIDER_WRITE_FUNCTION_NAMES = {"codex": "execute_write_via_worker"}`.
  - `run_task()` implementation mode: replace the `route.host != current_host_id()` refusal (`:1609-1613`) with: the active lease for `repo` must be held by `route.host` (via `_lease_authority`), else `write_lease_missing`.
  - `reconcile_stale_estate_executions(db, EstateExecution)`:
    - rows with a **confirmed** `worker_handle_json` (post step 7) and `last_observed_at` older than 15 s → one bounded `status` call (`deadline_s=10`), then transition per step 8's rules above (`interrupted` on a reachable dead runner, terminal on a reachable terminal report, otherwise keep polling);
    - rows still carrying the step-5 **placeholder** (dispatch unresolved — crashed or lost `start` response before confirmation) → resolve exactly as step 6 describes (retry `start` with the same `execution_id` and/or `status`), never treated as legacy and never redispatched under a fresh `execution_id`;
    - rows past their persisted `execution_deadline_at + 120 s` (never a process-local `timeout` argument, so this survives a control-plane restart with the exact same bound) with no successful observation → `lost`;
    - `lost` rows → try `status` when the worker becomes reachable again, and reconcile to the truthful spool/process state this reveals (`interrupted` if the runner is confirmed dead, a terminal state if the spool already has one, or back to `running` if it is genuinely still alive) — `lost` was never itself the true state, only the bound on how long "undetermined" was tolerated. No redispatch follows from this reconciliation alone. Whatever outcome it reveals, the worktree stays `unresolved` until finalization or S6.2 recovery, the same as for a row reached directly by the monitor thread;
    - rows with `worker_handle_json == NULL` (true legacy, created before Stage 6 existed — the placeholder above did not exist yet for these) → the existing `os.kill` path **only if** `row.host_id == current_host_id()`, else `lost`.
  - `get_estate_execution(execution_id, wait_s=0)`: loop up to `min(wait_s, 60)`. Re-read every 2 s and return early on any state not in (`accepted`, `running`).
  - `finalize_execution(...)`: keep all DB/lease/worktree drift checks, and make the authority-ordering explicit: before calling worker `worktree.finalize`, re-prove — in the same style of re-check as admission's step 3-4 above, not trusting an earlier check —
    1. the `EstateExecution` row is `succeeded` (an `interrupted` or `lost` execution can never finalize; there is nothing proven-clean to commit);
    2. the exact `lease_id` recorded on the execution row is still active, held by the same `host_id`, and still bound to the same `worktree_path` and `branch` (a released or reassigned lease invalidates finalization, even if the execution itself succeeded);
    3. only then replace the local git block (`:1434-1476`) with `call_worker(execution.host_id, "worktree.finalize", ...)`. The worker performs the requested Git operation only because the control plane has already proven authority — it never decides the lease is valid itself. The branch-drift check moves into the worker verb and the result is echoed.
    4. then a fresh `worktree.verify` for the same path and branch. If it reports `clean: true`, enter `lease_serialized_transaction(lease_id)`, re-read the row (still `succeeded`/`unresolved`) and the lease (same identity, authoritative), and set `worktree_resolution = 'finalized'` with the finalize result in `finalization_json`. Anything else (worker failure, still dirty, drift) leaves the row `unresolved` and the lease blocked (S6.1).
- `src/park_lease_ops.py`. This is contract only. Stage 6 adds no second lock, lease or lifecycle store; it couples the *existing* ParkLease rules to `EstateExecution.worktree_resolution`:
  - `lease_authority_state()` (S6.4) is the single reclaimability/authority rule. Stale reclaim in `park_repo`, `active_lease_for_repo`, `release_repo` and recovery call it, and `park_repo`'s reclaim and insert become one S6.5 transaction. Any lease with an `unresolved` execution is protected whatever its heartbeat age: `accepted`, `running`, `pending_start`, `lost`, and terminal-but-unfinalized/unrecovered alike. `lost` is never itself a reason to reclaim;
  - `release_repo` refuses while any row under the lease is `unresolved` (S6.2). The only other exit is `recover_execution_lease` → `release_lease_after_recovery(...)` (S6.2). There is no force flag;
  - `heartbeat_repo` keeps operator semantics and is allowed during execution (S6.3). The separate `renew_lease_for_execution(execution_id)` is the control plane's exact-lease supervision renewal (S6.3). The worker has no DB access and never heartbeats or mutates ParkLease, consistent with the DB-free-worker invariant below;
  - `park_with_worktree()` (S6.7) replaces the create-worktree-then-lease order in `park_repo_by_id(branch=...)`.
- `routes/estate_routing_routes.py`:
  - `GET /run/{execution_id}?wait=<int 0..60>`;
  - `POST /park/{repo_id}?host=<host_id>&branch=`:
    - `host` absent or equal to `current_host_id()`: the existing path, except that a `branch` park now goes through `park_with_worktree` with in-process prepare (S6.7).
    - Otherwise: require that host to be eligible with `codex-write` in `qualified_executors`, then run `park_with_worktree` with worker `worktree.prepare` as the prepare step. That means reserve (`preparing` row) → prepare with `lease` in the payload → require explicit `clean: true` evidence (never inferred from a successful path/branch verification) → bind to `active`. `clean != true`, a worker error or a refused bind → the reservation is released and no active ParkLease exists. The refusal has the same 409 shape as the existing `RepoNotClean`/verification-failure path. A concurrent park loses at the reservation and never reaches the worker.
  - `/park/{repo_id}/heartbeat` and `/release` accept `?host=` (DB-only), subject to S6.2/S6.3.
  - `POST /park/{repo_id}/recover` (S6.2), JSON body `{execution_id, lease_id, host_id, branch, worktree_path}`, scope `estate:execute`.
  - The `/run` response includes `dispatch` and `next_action: {"http": "GET /api/estate/run/<id>?wait=60", "cli": "aoteru execution <id> --wait 60"}` whenever an `execution_id` is present.
- `companion/laptop_client/aoteru.py`:
  - new `execution <execution_id> [--wait SECONDS]` (GET only, never POST `/run`), printing `lifecycle_state`, `host_id`, `executed` provenance and the result;
  - `park`/`heartbeat`/`release` accept `--host`;
  - new `recover <repo_id> --execution --lease --host --branch --worktree` (S6.2; all required, POSTs only `/park/{repo_id}/recover`);
  - `ask`/`lab`/`home` print `next_action` when an `execution_id` is returned;
  - the synced skill text states: "never re-run ask/lab/home to observe an execution; use `aoteru execution <id> --wait`".
- `scripts/agent`: `park`/`heartbeat`/`release` already take `--host`. No change beyond pointing remote park at the HTTP surface in help text.

Invariants:
- EstateExecution stays the only lifecycle store.
- The spool is never read as authority except through `status` inside the control plane.
- Dispatch and observation are separate commands.
- Admission under one lease is single-flight on **worktree resolution**, not process state (S6.1). Any row with `worktree_resolution = 'unresolved'` blocks a fresh dispatch: `accepted`, `running`, `pending_start`, `lost`, `interrupted`, and also `succeeded`/`failed`/`timed_out` that have not been finalized or recovered. The database enforces this with the recreated partial unique index. A terminal state alone never reopens admission. Finalization (same lease, clean) or S6.2 recovery (release → fresh lease) does.
- Lease re-validation and EstateExecution admission are one `lease_serialized_transaction` (S6.5: `BEGIN IMMEDIATE` on SQLite, `SELECT … FOR UPDATE` on the lease row elsewhere). Ordinary release, recovery release, stale reclaim, park bind/rollback and resolution writes take the same serialization. So no release or reclaim of L can commit between admission's final validation of L and the row's commit, and admission cannot slip past a concurrently committed release.
- Whether a lease is authoritative or reclaimable is decided only by `lease_authority_state()` (S6.4). Heartbeat age is telemetry. A lease with an unresolved execution is never reclaimable, is still found by authority lookup, and still blocks routing to other hosts.
- Ordinary release never bypasses an unresolved worktree. The only other exit is exact-identifier, operator-driven recovery release, which requires a fresh observed non-running writer and a clean worktree (S6.2).
- Supervision renewal targets only the execution's exact `lease_id` and is control-plane-only (S6.3). Operator heartbeat semantics are unchanged.
- Worker `start` claims its spool atomically with a durable `starting` state. A same-ID `start` never gets `execution_failed` for an in-progress claim, and a pre-spawn failure is recorded as `start_failed`, never deleted (S6.6).
- No remote or local worktree is created or reused before a `preparing` ParkLease reservation exists for that exact repo/host/branch. Only a bound, clean, verified path becomes `active` (S6.7).
- A persisted `execution_deadline_at`, set when the row is created, is what `lost` reconciliation is computed from — never a process-local `timeout` argument — so a control-plane restart reconstructs the exact same bound.
- Remote `worktree.prepare` requires explicit worker-attested cleanliness evidence before a reservation is bound to `active` (S6.7). Cleanliness is never inferred from path/branch verification alone.
- The control plane proves ParkLease authority (`_lease_authority`, then the step 3-4 atomic re-validation above) before issuing any remote `worktree.verify`, `start`, or `worktree.finalize` call — `worktree.finalize` re-proves it a second time, immediately before the call. `worktree.prepare` is issued only under a committed `preparing` reservation for that exact lease (S6.7). The worker remains DB-free and never decides lease validity, routing, or lifecycle authority — the lease payload sent to the worker is evidence/instruction from the already-authenticated control plane, not an independent worker-side lease authority.

Tests are listed in the §G matrix, items U11a, U13–U36, U29a and U37–U54, and I4–I10.

Sept 3 reconciliation rule: before starting Stage 6, `git log origin/dev` for a Sept 3 implementation.
- If one has merged, reuse its status/wait surface and change it only to add host-awareness (`lost`, `interrupted`, worker observation).
- If none has merged, implement exactly the surface above. Record in the evidence doc that Sept 3 acceptance bullets 1–4 and 6–7 are covered, and that bullets 5 and 8 (LogicalSession/Remote Control bounded outcomes) stay with the Sept 3 task.
- Do not touch `LogicalSession` in this plan.

Dependencies: Stage 5.

### Stage 7 — Host-specific capability qualification

Files:
- `config/models.yaml`:
  - add `qualified_hosts: {hz2-workstation: {evidence: <existing evidence path>}}` to every alias with a non-null `binding` (`local-fast`, `local-strong`, `code-fast`, `reasoning-strong`, `vision`, `embedding`, `reranker`). The structural-only `embedding`/`reranker` get `evidence: structural-binding-only`;
  - `code-strong` stays `binding: null`;
  - add a header comment defining the semantics.
- `src/estate_router.py` `resolve_alias(alias, host_id)`:
  - if `host_id not in (entry.get("qualified_hosts") or {})` → `{"resolved": False, "reason": "alias <a> not qualified on <host>"}`;
  - the concrete model is `qualified_hosts[host].get("binding") or entry["binding"]`;
  - a missing `qualified_hosts` key means qualified nowhere (fail closed).
- `scripts/run_lm4_production_canary.py` (and/or the `evals/local_models` runner): add `--worker-host <host_id>`, which executes each canary item via `call_worker(host, "execute", {kind: "local-inference", ...})`. It deliberately bypasses routing eligibility, so a not-yet-enabled host can be measured through the real worker path. It writes results to the existing `BenchmarkResult` table with `host_id` recorded in its existing fields/notes. It never edits config.
- `docs/aoteru-home-worker-setup.md`: add the qualification procedure (run the canary per alias on home via `--worker-host desktop-in7o23d`, with the same pass criteria as LM4).

Invariants:
- Qualification is evidence plus a governed commit. Nothing auto-promotes.
- Removing a host from `qualified_hosts` immediately removes it from routing.

Tests:
- `test_alias_not_qualified_on_host_fails_even_if_model_present`
- `test_alias_qualified_but_model_absent_on_host_fails`
- `test_per_host_binding_override`
- `test_missing_qualified_hosts_fails_closed`
- `test_shipped_models_config_every_bound_alias_declares_qualified_hosts`
- `test_shipped_models_config_home_not_qualified` (changed only in Stage 8)
- canary `--worker-host` dry-run with a fake transport

Dependencies: Stage 5. It can run in parallel with Stage 6 review but merges after it.

### Stage 8 — Live lab and home proof (operator-approved)

Prerequisites (operator):
- the §I.3 blockers are cleared;
- home is online;
- the Stage 4 runbook steps 1–7 are done;
- the Stage 7 qualification canary has passed on home for the aliases to enable (expected first: `local-fast`/`qwen3:8b` only).

Governed commit (config only, approval required), which changes the two shipped-config guard tests in the same commit:
- `config/estate.yaml` home: `worker.enabled: true`, `qualified_executors: [deterministic, local]`, `machine_fingerprint: <observed>`, `qualification_evidence: docs/aoteru-multihost-execution-evidence.md`.
- `config/models.yaml`: add `desktop-in7o23d` under `qualified_hosts` **only** for aliases that passed.
- `codex` / `codex-write` on home are added only with separate evidence: codex installed and authenticated on home, the read-only proof passed, and Stage 4 `detached_spawn_verified` for `codex-write`.

Then run §H and record everything in `docs/aoteru-multihost-execution-evidence.md` (new).

## Repository-boundary trajectory

The current Odysseus implementation task trail in `obsidian-PhD` is a transitional consequence of that repository being the established agent workspace while this backend is being built. It is not the target ownership boundary.

Continue the multihost/backend stages without migrating that trail now. At the backend completion boundary, run the explicit convergence described in `docs/aoteru-repository-ownership-trajectory.md`: reusable backend-wide agentic/runtime capability is ingested into Odysseus, while `obsidian-PhD` remains the PhD knowledgebase and the separate Aoteru personal knowledgebase retains its own domain content and task queue. The same Odysseus backend should manage both queues with minimal friction and without taking ownership of their domain knowledge.

Detailed placement of individual agentic functions/files is deliberately deferred to that convergence pass and should be decided by authority, reuse and future operational overhead rather than current file location.

### Stage 9 — Compatibility cleanup

- Remove the legacy `verified` fallback in `host_static_state` and the `verified` handling in tests. Assert that no host in `config/estate.yaml` uses `verified`.
- Delete `execute_codex_write`, `execute_codex_write_durable` and `_codex_write_authority` once no caller remains (grep). Replace the tests that exercised them with the Stage 6 worker-path equivalents.
- Remove `resolve_alias(alias, host_id=None)` legacy mode; all callers pass a host.
- Remove `_ollama_model_live` and `experiment_priority_active` from `estate_router` if only the worker uses them. Move them into `src/estate_worker.py`.
- Update the operating handbook sections "Normal use" and "Host re-entry" to the new commands. The stale "no HTTP park surface" sentence is removed as part of that edit.

---

## F. Non-goals (do not touch)

- Adaptive or multi-host scoring, load balancing, exploration, effort optimisation (`chatgpt/model-effort-routing-20260910` is rebased *after* this plan; it must then add `effort` to `aoteru-worker/1` as a versioned payload field).
- GLM (#38), swarm or multi-agent scheduling, a new queue, lease or session store, or a worker daemon or listener.
- The household service on home: `scripts/windows/odysseus-host.ps1`, the `Odysseus-Misumi` scheduled task, port 420/4500/4600, `odysseus-releases\...`, the household data dir, and household Ollama models (no pulls or removals by automation). `svc:odysseus-home.endpoint` stays `null`.
- `LogicalSession`, `scripts/agent cmd_claude` remote-native launch, Claude Remote Control (Sept 3 items 5/8 stay with that task).
- Repo-grounded *local-model* execution (P13 finding: local executor gets no file content). Deferred; repo-grounded read-only work uses `codex-readonly` or deterministic `repo.probe`.
- Glovebox/`experiment-edge`, `interface-pc`, laptop roles. They never become workers.
- `routes/shell_routes.py`, `core/platform_compat.py` SSH helpers (do not reuse or modify; they allow `StrictHostKeyChecking=no`).
- Docker/compose files, `app.py` middleware, auth/token scopes (reuse `estate:read` / `estate:execute`).
- Tailscale ACL/serve config, `sudo` actions, systemd unit files.
- Stale docs other than the contract host-model block and handbook sections named in Stage 9 (`docs/aoteru-interface-pc-deployment.md` stays as is).
- PRs #39/#40/#35: merge independently; this plan only rebases over them.
- Quality floors, budgets, `routing.yaml` policy values.

---

## G. Test matrix

### Unit tests (deterministic, fakes only; `tests/test_estate_router.py`, `tests/test_estate_worker*.py`, `tests/test_estate_execution_runtime.py`)

The fake transport is `FakeWorker(host_id, models, executors, repos, fail=None)`, installed by monkeypatching `estate_worker_client.transport_for_host`. It records every call with its `host_id`.

| ID | Scenario | Expected |
|---|---|---|
| U1 | explicit lab placement, `local-fast` | route.host=`hz2-workstation`; FakeWorker(lab) got `execute`; `executed_host_id=hz2-workstation`; no call on home fake |
| U2 | explicit home placement (home enabled in fixture), `local-fast` on both | route.host=home; only home fake called; `placement.executed_host=desktop-in7o23d` |
| U3 | auto placement, both healthy, alias on both | first in estate.yaml order (lab); deterministic across runs |
| U4 | auto placement, alias only on home | home selected |
| U5 | home requested, worker unreachable | `ok: False`, "requested host … not eligible", reason `worker unreachable`; **zero** `execute` calls on any host |
| U6 | home requested, health stale beyond TTL then failing | cache expiry triggers re-probe; ineligible; no call |
| U7 | model only on lab (`code-fast`), home requested | `alias code-fast not qualified on desktop-in7o23d`; no execution anywhere |
| U8 | alias qualified on home but model absent from home inventory | `model absent` reason; no execution |
| U9 | repo requested, not resolvable on home | home ineligible for that task: `repo_unavailable`; auto falls to lab if lab has repo |
| U10 | worker returns `execution_failed` | `ok: False`, `worker_failed`, `executed_host_id` = attested host, no retry elsewhere |
| U11 | attestation host mismatch / well-formed-but-wrong nonce (32 hex, doesn't match request) / fingerprint mismatch | `placement_mismatch`; decision `failed`; `observed_host_id` retained where available (final contract-hardening review finding: distinct from the malformed-nonce case below, which never reaches this classification at all) |
| U11a | attestation nonce malformed (empty, wrong length, or non-hex) | `worker_protocol_error` from `validate_response` — envelope-shape rejection, before `verify_attestation` ever runs; never `placement_mismatch` |
| U12 | backend-local fallback prevention | `estate_router.execute_local`, `execute_codex` and `_execute_codex_with_sandbox` monkeypatched to raise inside the control plane; U1–U11 still pass |
| U13 | ParkLease-gated write, lease held by home, route home | worker `worktree.verify` then `start` on home; row `host_id=home` |
| U14 | write with lease held by lab, route home requested | refused `write_lease_missing` (lease holder ≠ route.host); no row |
| U15 | write without lease | refused; no row; no `start` |
| U16 | duplicate dispatch while non-terminal | same `execution_id`, `dispatch: reused_in_flight`, `start` called once |
| U17 | worker `start` response lost (transport/protocol failure), retried with the same `execution_id` | row is **not** marked `failed` in between (still `accepted`, placeholder `worker_handle_json` from step 5 in place); retried `start` returns `reused: true` → confirmed, transitions to `running`; exactly **one** spawn on the fake worker across both calls. A clean new `start` genuinely reaching the worker for the first time under the same `execution_id` (the lost-response case, not a duplicate spawn) is covered identically — also confirmed, also never evidence for `failed` |
| U18 | status without redispatch | `get_estate_execution(id, wait_s=10)` observes running→succeeded via fake `status`; **zero** `/run` or `start` calls during observation |
| U19 | worker reachable, stored `accepted`/`running`, `status` reports `process_alive: false` | row promptly `interrupted` (not `lost` — the worker answered and the runner is positively known dead); `_update_decision_outcome(executed_host_id=host_id, ...)` recorded; no wait for the `lost` timeout |
| U20 | worker unreachable for the full observation window | no observation past the row's persisted `execution_deadline_at + 120s` (clock monkeypatched; deadline read from the row, not passed as a fresh argument) → `lost` (outcome undetermined — distinct from U19's positively-observed `interrupted`); `status` returns promptly once the worker is reachable again |
| U21 | dispatch under lease with `lost` row | `lease_has_unresolved_lost_execution`; no new row |
| U22 | worker becomes reachable again after a `lost` row | reconcile resolves `lost` to the now-observable truthful state (`interrupted` if the runner is confirmed dead, a terminal state if the spool already has one, or back to `running` if it genuinely never stopped); no redispatch follows from this reconciliation alone — a fresh admission still goes through the same single-flight check as U21 |
| U23 | legacy row (`worker_handle_json IS NULL`, created before Stage 6 existed) on non-local host | `lost`, not `interrupted`; no `os.kill` |
| U24 | new Stage-6 row with only the step-5 placeholder dispatch-state marker (crash, or lost `start` response, before a confirmed handle) | resolved via the same retried `start` (same `execution_id`) / `status` logic as U17 — never treated as U23's legacy case, never redispatched under a fresh `execution_id` |
| U25 | truthful telemetry | for U1–U11, `RoutingDecision.host_id == route.host` and `executed_host_id ∈ {route.host, null}`; never another host except under `placement_mismatch` |
| U26 | identity verified / worker disabled | ineligible with the worker-specific reason |
| U27 | remote read-only repo work | `codex-readonly` on home fake gets `repo_id` and resolves cwd on home (fake asserts that path came from home inventory, not lab) |
| U28 | worker import hygiene | `core.database` absent from `sys.modules` after each worker verb |
| U29 | **true serialization race** (S6.5), file-backed SQLite (not `:memory:`/`StaticPool`), two threads. (a) Thread A enters admission and pauses on a test hook *after* its in-transaction authority validation of L, before insert/commit; thread B calls `release_repo` for L | B cannot commit while A holds the transaction: it blocks on the write lock. After A commits, B re-reads, sees the `unresolved` row and is refused `lease_has_unresolved_execution`. L is still `active` with exactly one row. (b) Reverse order: B's release commits first, then A validates | A sees L `released` and refuses. **No** row, **no** `start`. (c) As (a), with a stale-reclaim `park_repo` in place of release | same outcome as (a). A variant asserts that the helper actually issued `BEGIN IMMEDIATE` (e.g. a second raw connection's write gets `database is locked` while A is paused) |
| U29a | sequential variant (the former U29): lease valid at the step-1 `_lease_authority` check, then released or reassigned to a different host before the admission transaction opens | the in-transaction re-read refuses; no row; no `start`. Proves the early check alone is never relied on |
| U30 | running execution (`accepted`/`running`), lease heartbeat artificially aged past the ordinary stale threshold | `lease_authority_state` → `reclaimable: False`, `protected_by_execution_id` = that row; stale-reclaim refused |
| U31 | `lost` execution, lease heartbeat aged past the ordinary stale threshold | stale-reclaim still refused. Outcome-undetermined is exactly the case reclaim must not treat as free |
| U32 | ordinary `release_repo` while the lease has an `unresolved` row in each of `accepted`, `running`, `pending_start`, `lost`, `succeeded`, `failed`, `timed_out`, `interrupted` | refused `lease_has_unresolved_execution` with `execution_id`/`next_action`; lease unchanged. With only `not_started`/`finalized` rows, or none, release succeeds. Ordinary **operator** `heartbeat_repo` during `running` **succeeds** (S6.3) and is refused only on a `preparing` reservation |
| U33 | execution confirmed `running`, fake `status` returns `process_alive: true` | `renew_lease_for_execution` renews exactly `row.lease_id`. It is not called for a `starting`/`pending_start` row or after a failed `status`. The worker fake never receives any lease/heartbeat-shaped call |
| U34 | dispatch under a lease with an `interrupted` row | refused `lease_has_unresolved_worktree`; no new row, no `start` call |
| U35 | finalize called against an execution that is `interrupted` or `lost` | refused before any worker call — `succeeded` is a hard precondition, never merely "not obviously failed" |
| U36 | finalize called after the execution's lease has been released/reassigned since the execution `succeeded` | refused before any worker `worktree.finalize` call — the exact `lease_id`/`host_id`/`worktree_path`/`branch` are re-proven immediately before that call, not assumed from the execution's own success |
| U37 | `succeeded` row, `worktree_resolution = 'unresolved'` (not finalized), new dispatch under the same lease | refused `lease_has_unfinalized_execution`, `next_action` finalize/recover; no row; no `start` |
| U38 | `failed` and `timed_out` rows that actually started (`unresolved`), new dispatch, with the worktree both dirty and clean | refused `lease_has_unresolved_worktree` in both cases. A clean tree does not reopen admission; only S6.2 recovery does |
| U39 | finalization reopens admission | after `finalize_execution` succeeds with post-finalize `clean: true` → row `finalized`. New dispatch under the same authoritative lease with `worktree.verify` `clean: true` → admitted, `dispatch: new`. The same with `clean: false` → refused `worktree_not_clean`. A finalize whose post-verify is dirty leaves the row `unresolved` |
| U40 | deterministic pre-spawn refusal (`start` → `authority_denied` before spool claim, or `start_failed`) | row `failed` + `not_started`; the next dispatch under the same lease is admitted |
| U41 | recovery release success: `interrupted` row, fresh fake `status` `process_alive: false` with a matching handle, fresh `worktree.verify` `ok`+`clean` | in one transaction: row `recovered` with the recovery record, lease `released`. A following park yields a **new** `lease_id`. The old lease cannot be renewed (U43) or used for admission |
| U42 | recovery release refusals: (a) any one of the five identifiers mismatched; (b) row `running`/`pending_start`/`lost`; (c) worker unreachable; (d) handle mismatch; (e) worktree dirty; (f) row or lease changed between the precheck and the S6.5 transaction | each refused with its specific code; **nothing** changes (row still `unresolved`, lease still `active`) |
| U43 | exact-lease renewal cannot renew another lease: execution under L1; the fixture releases L1 and parks L2 for the same repo/host | `renew_lease_for_execution` returns `False`; `L2.heartbeat_at` unchanged; no repo/host fallback lookup is issued |
| U44 | canonical reclaimability: heartbeat stale **and** an `unresolved` row in each of `running`, `lost`, `succeeded`, `interrupted` | `eligible_hosts(repo_id)` still refuses the other host (lease authoritative); `active_lease_for_repo` still returns it with `heartbeat_stale: true`, `protected_by_execution_id`; `park_repo` reclaim refused. Control case, stale with no unresolved row: `reclaimable: True`, routing ignores it, lookup returns `None`, reclaim succeeds |
| U45 | staleness hygiene | source scan: `park_lease_is_stale` is referenced only in `core/database.py`, `lease_authority_state` and display projections (`active_leases_summary`, `scripts/agent` status) |
| U46 | worker same-ID `start` race (S6.6): the first `start` is paused by a test hook after the atomic claim, before spawn; a second same-ID `start` arrives | second → `{accepted: false, state: "starting", reused: true}`, **not** `execution_failed`. After the first resumes: exactly one `spawn_detached` call and `status` goes `starting → accepted`. The control plane keeps the row `pending_start` and never writes `failed` in between. No spool directory without `state.json` is observable at any point |
| U47 | deterministic spawn failure | `state.json` `start_failed`, `spawned: false`, spool retained. A same-ID retry returns `start_failed` and does not spawn. The control plane records `failed` + `not_started` |
| U48 | stale `starting` (clock past `STARTING_STALE_SECONDS`) / runner finds no handle | next `status` rewrites it to `start_failed`. The runner's no-handle abort writes `start_failed` with `spawned: true, executed: false`, never a generic `failed` |
| U49 | two concurrent remote park attempts (same repo, threads, file-backed SQLite) | exactly one `preparing` reservation. The loser gets `ParkConflict` **before any worker call**. FakeWorker receives exactly one `worktree.prepare`, carrying the winner's `lease_id` |
| U50 | ungoverned prepare is impossible | worker `worktree.prepare` without `lease` → `bad_request` with `create_or_reuse_worktree` never called. The control plane's FakeWorker asserts that a committed `preparing` row for that `lease_id` exists at the moment of every `prepare` call |
| U51 | prepare failure: worker error, unreachable, lost response, `clean: false`, branch mismatch, reservation reclaimed before bind | reservation `released`; no `active` or `preparing` lease remains; `eligible_hosts` shows no conflict. Separately, a `preparing` row older than `PARK_PREPARE_STALE_SECONDS` is `reclaimable` |
| U52 | successful prepare, including reuse of an existing **clean** worktree | exactly one `active` lease, `worktree_path` = the verified path, `branch` = requested, fresh `heartbeat_at`. Reuse of a **dirty** existing worktree fails closed at the evidence step |
| U53 | migration | the backfill assigns `legacy_closed`/`unresolved` per S6.1; both indexes are recreated with the new predicates; a duplicate-unresolved lease is logged, the old index kept, and the lease stays blocked; the migration is idempotent on a second `init_db()` |
| U54 | backend portability | DDL compiled for the PostgreSQL dialect includes the `postgresql_where` predicates for both partial indexes. `lease_serialized_transaction` on a PostgreSQL dialect compiles `SELECT … FOR UPDATE` on `park_leases` (compile-only, no server) |

### Integration tests (real subprocesses, no paid inference, no network)

| ID | Scenario |
|---|---|
| I1 | `LocalTransport` → real `python -m src.estate_worker` → `health`, `inventory` against a stub Ollama HTTP server on an ephemeral `127.0.0.1` port (worker Ollama base overridable by env `AOTERU_WORKER_OLLAMA_BASE`, test-only; default `127.0.0.1:11434`) |
| I2 | `/api/estate/run` (TestClient) lab placement end to end through LocalTransport with the stub Ollama; response `placement.attested: true` |
| I3 | `SshTransport` argv + stdin contract with `ssh` replaced by a shim script on PATH that execs the local worker (proves the stdin/forced-command shape without a network) |
| I4 | durable write lane through LocalTransport with `_execute_codex_with_sandbox` replaced in the **worker** by a sleep-then-write stub (via the `~/.aoteru/worker_selftest_enabled` sentinel file + `kind: "noop-sleep"`), a real detached spawn, real spool, real monitor thread → `succeeded`; `aoteru execution <id> --wait` (client against TestClient) observes it; `worker_handle_json` is non-null throughout (the step-5 placeholder, then the real handle after `start` confirms (step 7)) — never `NULL` at any point in this real subprocess run |
| I5 | kill the detached runner mid-run, worker stays reachable → real `status` truthfully reports `process_alive: false` for the stored `accepted`/`running` row → row promptly `interrupted` (not a generic "terminal", not `lost` — the worker was reachable and positively observed the runner dead); no redispatch |
| I6 | Sept 3 sequence: dispatch E, then a duplicate while running → same E (single-flight). Observe via status only, to `succeeded`. A new dispatch now → refused `lease_has_unfinalized_execution` (S6.1). `finalize_execution(E)` (noop-sleep wrote nothing, so nothing to commit and the tree is clean) → E `finalized`. New dispatch → new E′ with `dispatch: new`. Also covers the ambiguous-`start` cases through a real transport: (a) kill the transport after the worker has actually spawned but before its `start` response reaches the control plane → the row is not marked `failed`; a same-ID retry observes `reused: true` with a handle, and the row proceeds to `running` off the one real spawn. (b) A self-test-only spawn delay (read from the `worker_selftest_enabled` sentinel file, honoured only when it exists) holds the first `start` in `starting` while a second same-ID `start` arrives → `state: "starting"`, not `execution_failed`, and exactly one real spawn (S6.6). Neither case is ever treated as evidence for `failed` |
| I7 | remote-host park via `?host=` with FakeWorker `worktree.prepare` reporting a clean worktree → a `preparing` reservation exists when `prepare` is called and carries its `lease_id`, then is bound to `active` with `host_id=desktop-in7o23d` and the verified path; heartbeat/release with `?host=` |
| I8 | remote-host park via `?host=` with FakeWorker `worktree.prepare` reporting `clean: false` (S6.7) → the reservation is released and no `active` ParkLease exists. The failure has the same 409/`RepoNotClean` shape the local park path produces for a dirty worktree, not a silent success |
| I9 | real SQLite serialization (S6.5) against a file-backed DB from two OS processes: one runs admission paused after validation (test hook), the other runs `release_repo` → the release waits for the write lock and is then refused. In reverse order, admission is refused and no row exists. Proves the invariant with real locking, not mocks |
| I10 | recovery end to end through `LocalTransport`: noop-sleep runner killed → `interrupted` → ordinary release refused → a dirty file placed in the worktree → `aoteru recover …` refused `worktree_not_clean` → file removed → recover succeeds (row `recovered`, lease `released`) → fresh park gets a new `lease_id` → new dispatch admitted |

### Live acceptance tests

These are the procedures in §H, run by the operator or implementer in Stage 8 only.

---

## H. Live acceptance procedure

General:
- Each run uses a fresh nonce `N = $(openssl rand -hex 6)`.
- Record wall-clock UTC before and after each run.
- Every run must produce the evidence listed below. Route metadata alone is never accepted.
- A failure is recorded verbatim and stops that host's acceptance. Retrying an identical paid call is not allowed.

### H.1 Lab (hz2-workstation)

1. Pre-state: `journalctl -u ollama --since "<T0>" --no-pager | grep -c "POST \"/api/chat\""` (baseline) and `aoteru park-status` (expect no leases).
2. Read-only local inference:
   ```text
   aoteru lab "Reply with exactly this token and nothing else: LAB-$N" --capability local-fast
   ```
   Expected:
   - `route.host = hz2-workstation`;
   - `placement = {routed_host: hz2-workstation, executed_host: hz2-workstation, attested: true, transport: local}`;
   - output contains `LAB-$N`;
   - `decision_id` D.
3. Provenance:
   - `GET /api/estate/decision/D` (authenticated; the client has no `decision` subcommand) shows `host_id = executed_host_id = hz2-workstation`;
   - the lab Ollama journal shows exactly one new `/api/chat` POST between T0 and T1;
   - `ollama ps` shows `qwen3:8b` loaded.
4. Write lane (bounded, no push):
   ```text
   aoteru park odysseus --branch acceptance/multihost-lab-$N
   aoteru ask "Create a file named ACCEPTANCE-$N.txt at the worktree root containing exactly $N. Change nothing else." --repo odysseus --capability code-strong --allow-paid --implementation
   ```
   Then run `aoteru execution <E> --wait 60` until terminal.
   Expected:
   - EstateExecution `host_id = hz2-workstation`, `worker_attestation_json.hostname = dmem-HP-Z2-Tower-G9-Workstation-Desktop-PC`, lifecycle `succeeded`;
   - `git -C <worktree> status --porcelain` shows only `?? ACCEPTANCE-$N.txt`;
   - the live checkout `git status` is clean.
   Then `aoteru release odysseus` and remove the worktree. Do not finalise. The Codex usage limit is a recorded external blocker, not a failure of this plan.

### H.2 Home (desktop-in7o23d)

1. Pre-state:
   - `tailscale status` shows home online;
   - `aoteru status` lists home `identity_verified: true, worker_enabled: true, healthy: true`;
   - record the lab Ollama journal baseline (as H.1.1);
   - the operator, from the laptop SSH session, records `(Get-Item $env:LOCALAPPDATA\Ollama\server.log).Length` as the home log offset.
2. Read-only local inference:
   ```text
   aoteru home "Reply with exactly this token and nothing else: HOME-$N" --capability local-fast
   ```
   Expected:
   - `route.host = desktop-in7o23d`;
   - `placement = {executed_host: desktop-in7o23d, attested: true, transport: ssh}`;
   - `attestation.hostname = DESKTOP-IN7O23D`;
   - `machine_fingerprint` equals config;
   - output contains `HOME-$N`.
3. Physical provenance, all required:
   - the home Ollama `server.log` past the recorded offset contains a `POST "/api/chat"` at the run time;
   - the **lab** Ollama journal shows **no** new `/api/chat` in the window (negative control against backend-local fallback);
   - `RoutingDecision.executed_host_id = desktop-in7o23d`.
4. Host-specific capability:
   ```text
   aoteru home "x" --capability code-fast
   ```
   It must be refused with "not qualified on desktop-in7o23d". There must be no new `/api/chat` in either host's log.
5. Remote read-only repo work:
   - `GET /api/estate/route/hosts?repo=obsidian-phd` shows home's `repo.probe` `head_sha`, which must equal `git ls-remote https://github.com/tyecam1/obsidian-PhD.git refs/heads/main` (or home's checked-out branch as reported).
   - If and only if `codex` is qualified on home, also re-run the P13 PhD gate objective with `aoteru home ... --repo obsidian-phd --capability code-strong --allow-paid`. The expected deterministic answer is the one recorded in P13, and the attestation must show home.
6. Worker-loss / fail-closed:
   - the operator disconnects home from the tailnet (`tailscale down` on home) or temporarily renames the authorized key;
   - `aoteru home "Reply HOME-LOSS-$N" --capability local-fast` must return not eligible / `worker unreachable` within ≤ 20 s;
   - the lab Ollama journal shows no new `/api/chat`;
   - restore connectivity; `aoteru status` shows healthy again within the 30 s cache TTL.
7. Home write lane: **only** if `codex-write` was qualified (Stage 4 `detached_spawn_verified` + codex on home). Mirror H.1.4 with `aoteru park odysseus --host desktop-in7o23d --branch acceptance/multihost-home-$N`. Evidence is home `git status` in the home worktree (via laptop SSH), attestation home, and the lab worktree list unchanged. Otherwise record "home write lane not qualified" as the truthful outcome.

Evidence file: `docs/aoteru-multihost-execution-evidence.md`. It records the timestamps, nonces, decision/execution IDs, attestation JSON, log excerpts (lines containing the timestamp only; no prompt bodies) and the pass/fail per step.

---

## I. Migration and order strategy

### I.1 Sequence

This is the task's preferred order, kept because the live code supports it without reordering:

| Stage | Usable state after the stage |
|---|---|
| 1 truthful state semantics | identical routing; truthful reasons |
| 2 worker contract | worker exists, unused by routing |
| 3 lab through worker | all lab read-only execution attested; write lane unchanged (in-process, guarded) |
| 4 Windows adapter + SSH | home callable manually for health; still not routable |
| 5 route via worker health/inventory | routing reads per-host truth; home still disabled by config |
| 6 EstateExecution via worker + status/wait | write lane host-aware; observation separated from dispatch |
| 7 per-host qualification | alias routing requires per-host evidence |
| 8 live proof + governed enablement | home routable for qualified executors/aliases only |
| 9 cleanup | legacy paths removed |

Deploy note: the lab backend runs from `/home/agent/projects/odysseus-aoteru`. Deploying a stage means the operator pulls and restarts `odysseus-aoteru-lab.service`, as recorded in the P13 addendum. Stages 1–7 are safe to deploy one at a time because home stays disabled by the shipped config guard tests.

### I.2 Relation to other work

- **Sept 3 lifecycle task:** Stage 6 either consumes an already-merged implementation or implements its status/wait/dispatch-separation subset (rule in Stage 6). LogicalSession/Remote Control items stay with Sept 3. Recommendation: the operator marks Sept 3 as "partially superseded by multihost Stage 6" once Stage 6 merges.
- **PR #39:** touches the same contract doc as Stage 1. Merge #39 first, or rebase Stage 1 on it.
- **PR #40:** comment/description-only changes to `config/repositories.yaml` and `AGENTS.md`. No conflict expected.
- **Effort branch / #38 GLM:** rebase after Stage 9. Both must dispatch through the worker (`execute` kinds), not backend-local subprocesses.

### I.3 Unresolved decisions and blockers

| # | Item | Owner | Blocks |
|---|---|---|---|
| B1 | Home offline on the tailnet at planning time (last seen 1d) | operator | Stage 4 live steps, Stage 8 |
| B2 | Lab→home SSH key for `agent` with forced command, installed on home (admin vs non-admin authorized_keys path) | operator | Stage 4 live, 8 |
| B3 | Home SSH host public key captured and pinned in config (fingerprint must match the recorded pin) | operator + governed commit | Stage 4 live |
| B4 | Dedicated home checkout + venv + `config.local.json` roots (which repos home should serve) | operator decision | Stage 4 live |
| B5 | Codex on Windows home: installed? authenticated? sandbox behaviour? | operator | home `codex`/`codex-write` qualification (optional) |
| B6 | Detached spawn survival across SSH session close on Windows (`CREATE_BREAKAWAY_FROM_JOB` permitted by sshd job?) | Stage 4 live check | home `codex-write` only |
| B7 | Household contention: estate inference on home shares Ollama/GPU with Misumi. No priority mechanism beyond `gpu_yield` on non-Ollama GPU processes. Decide whether estate work on home is acceptable at all hours | operator decision | Stage 8 enablement scope |
| B8 | Contract doc edit (Stage 1) and config enablement (Stage 8) need operator approval (`approval_required`) | operator | Stages 1, 8 merge |
| B9 | A `lost` execution on a host that never becomes reachable again keeps its lease protected indefinitely (S6.2 deliberately refuses `lost`; there is no force flag). Clearing it needs the host back, or a separate governed, out-of-band DB decision. Stage 6 does not automate either | operator decision | only that repo's writes, and only after such a loss |
| B10 | Adjacent defect, not Stage 6 scope: `ix_source_events_source_external_unique` (`core/database.py:842`) also declares only `sqlite_where`, so on PostgreSQL it becomes a full unique index. Stage 6 fixes the two indexes it recreates (S6.5); this one is a follow-up | follow-up | nothing on SQLite |

---

## J. Sonnet handoff prompt

```text
You are implementing docs/aoteru-multihost-execution-implementation-plan.md in tyecam1/odysseus.
That plan is the architecture authority; do not redesign it.

Start from current origin/dev in a fresh worktree/branch (never the live checkout
/home/agent/projects/odysseus-aoteru). Read the plan fully, then implement Stages 1→9
strictly in order. For each stage: make exactly the file/function changes listed, write the
listed tests, run the stage test suite, and commit with a message naming the stage.
Keep commits small and reviewable; one PR per stage or per two adjacent stages.

Rules:
- Invariant: route.host must equal the attested execution host. Never add an in-process
  or cross-host fallback. Worker/transport failure fails closed.
- ParkLease is the only write authority; EstateExecution the only lifecycle store; the worker
  never touches core.database.
- Do not touch anything in the plan's Non-goals, especially the home household service.
- Stage 8 config enablement and the Stage 1 contract edit need operator approval: prepare
  them, do not merge them yourself.
- If live code or runtime contradicts a plan assumption (line numbers aside), stop and
  report the contradiction with evidence. Make no silent architectural substitution.
- Infrastructure failures (home offline, SSH/key missing, Codex quota) are recorded
  verbatim as blockers, never worked around.
- Do not expand scope; list any discovered adjacent defect as a follow-up instead.
```

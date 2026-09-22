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
5. **Lifecycle integration?** EstateExecution stays the only lifecycle store. Remote write execution is observed through the worker's `status` verb and written into EstateExecution by the control plane. Stage 6 adds the bounded `wait` and the client `execution` command from the Sept 3 task, plus a `lost` state so worker loss is bounded rather than ambiguous (§I.2 sets the sequencing).

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
| `worktree.prepare` | `{repo_id, branch, base_ref}` | `{path, branch, head_sha, clean}` | `worktree_ops.create_or_reuse_worktree`, `verify_worktree`, `git_is_clean` |
| `worktree.verify` | `{repo_id, worktree_path, branch}` | `{ok, path, reason}` (refuses the live checkout) | `worktree_ops.verify_worktree`, `is_live_checkout_path` |
| `start` | `{execution_id, kind: "codex-write", objective, repo_id, lease: {lease_id, worktree_path, branch}, timeout_s}` | `{accepted, handle: {pid, create_time, spool_id}, reused: bool}` | re-runs `worktree.verify` (TOCTOU), then spawns detached `python -m src.estate_worker --run-spooled <execution_id>`, which calls `_execute_codex_with_sandbox(sandbox="workspace-write", cwd=verified path, on_started=spool writer)` |
| `status` | `{execution_id}` | `{state: running\|succeeded\|failed\|timed_out\|unknown, handle, process_alive, started_at, finished_at, result?}` | spool + `estate_worker_procs.is_alive(handle)` |
| `cancel` | `{execution_id}` | `{killed, still_alive_pids}` | `estate_worker_procs.kill_tree(handle)` |
| `worktree.finalize` | `{repo_id, worktree_path, branch, commit_message}` | `{committed, pushed, commit_sha, dirty_paths, push_error?}` | git logic moved out of `finalize_execution` (`:1434-1476`) |

Rules:
- `start` is **idempotent per `execution_id`**. If a spool exists, it returns the existing handle with `reused: true` and never spawns twice. That is the defence against a retried `start` after a lost response.
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
| Write authority | `park_leases` row (`host_id` = lease holder) | Control plane | Unchanged semantics. `host_id` may now be a remote host |
| Execution lifecycle | `estate_executions` row | Control plane only | `accepted → running → succeeded \| failed \| timed_out \| interrupted \| lost` |
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
- `lost` is terminal for **observation**: status/wait return promptly. It is still **blocking for admission** under the same lease: `_in_flight_execution_for_lease` treats it as in flight and dispatch returns `lease_has_unresolved_lost_execution`. It is resolved automatically by the next successful worker `status` (the true terminal state is taken from the spool, or `interrupted` if the spool is absent). The other resolution is explicit operator lease release. Re-parking still fails closed on a dirty worktree.

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

Files:
- `core/database.py`:
  - add `EstateExecution` columns `worker_handle_json` (Text), `worker_attestation_json` (Text) and `last_observed_at` (DateTime);
  - add `lost` to the lifecycle docstring;
  - add migration `_migrate_add_estate_execution_worker_columns()` (same pattern as `_migrate_add_routing_delegation_columns`), called from `init_db()` after `create_all`.
- `src/estate_router.py`:
  - `_lease_authority(repo_id, host_id) -> dict`: the DB-only half of `_codex_write_authority` (active non-stale lease held by `host_id`, `allowed_write_scope == "repo"`, `branch`, `worktree_path`).
  - `execute_write_via_worker(objective, *, repo_id, host_id, decision_id, wait_timeout=30.0, timeout=1800.0) -> dict`:
    1. `_lease_authority`.
    2. `call_worker(host_id, "worktree.verify", ...)`. Failure → `authority_denied`, no row.
    3. `_in_flight_execution_for_lease`. Include `lost` rows: a `lost` row → `{ok: False, error_code: "lease_has_unresolved_lost_execution", execution_id}`; an accepted/running row → reuse, `dispatch: "reused_in_flight"`.
    4. `_create_estate_execution` (accepted).
    5. `call_worker(host_id, "start", ...)`. Transport failure → row `failed`, `error: worker_unreachable`, because nothing started. That is provable: `start` is idempotent and the spool check is part of the next reconcile.
    6. Update the row to `running` with `worker_handle_json`, `worker_attestation_json`, `worker_pid` and `started_at`.
    7. Start the monitor thread `_observe_worker_execution(execution_id, host_id, timeout)`: poll `status` every 5 s. On terminal, write the terminal row and `_update_decision_outcome(executed_host_id=host_id, ...)`. While unreachable, keep polling. With no successful observation for `timeout + 120 s` → `lost`.
    8. Bounded join (`wait_timeout`), same response contract as today plus `dispatch` and `next_action`.
  - `_PAID_PROVIDER_WRITE_FUNCTION_NAMES = {"codex": "execute_write_via_worker"}`.
  - `run_task()` implementation mode: replace the `route.host != current_host_id()` refusal (`:1609-1613`) with: the active lease for `repo` must be held by `route.host` (via `_lease_authority`), else `write_lease_missing`.
  - `reconcile_stale_estate_executions(db, EstateExecution)`:
    - rows with `worker_handle_json` and `last_observed_at` older than 15 s → one bounded `status` call (`deadline_s=10`), then transition accordingly;
    - rows past `timeout + 120 s` with no successful observation → `lost`;
    - `lost` rows → try `status`, and map spool-absent to `interrupted`;
    - rows **without** a worker handle (legacy, pre-Stage-6) → the existing `os.kill` path **only if** `row.host_id == current_host_id()`, else `lost`.
  - `get_estate_execution(execution_id, wait_s=0)`: loop up to `min(wait_s, 60)`. Re-read every 2 s and return early on any state not in (`accepted`, `running`).
  - `finalize_execution(...)`: keep all DB/lease/worktree drift checks. Replace the local git block (`:1434-1476`) with `call_worker(execution.host_id, "worktree.finalize", ...)`. The branch-drift check moves into the worker verb and the result is echoed.
- `routes/estate_routing_routes.py`:
  - `GET /run/{execution_id}?wait=<int 0..60>`;
  - `POST /park/{repo_id}?host=<host_id>&branch=`: if `host` is absent or equals `current_host_id()`, run the existing path. Otherwise require that host to be eligible with `codex-write` in `qualified_executors`, call worker `worktree.prepare`, then `park_repo(repo_id, host, path, branch)`. `RepoNotClean`/verification failures map to 409 as today.
  - `/park/{repo_id}/heartbeat` and `/release` accept `?host=` (DB-only).
  - The `/run` response includes `dispatch` and `next_action: {"http": "GET /api/estate/run/<id>?wait=60", "cli": "aoteru execution <id> --wait 60"}` whenever an `execution_id` is present.
- `companion/laptop_client/aoteru.py`:
  - new `execution <execution_id> [--wait SECONDS]` (GET only, never POST `/run`), printing `lifecycle_state`, `host_id`, `executed` provenance and the result;
  - `park`/`heartbeat`/`release` accept `--host`;
  - `ask`/`lab`/`home` print `next_action` when an `execution_id` is returned;
  - the synced skill text states: "never re-run ask/lab/home to observe an execution; use `aoteru execution <id> --wait`".
- `scripts/agent`: `park`/`heartbeat`/`release` already take `--host`. No change beyond pointing remote park at the HTTP surface in help text.

Invariants:
- EstateExecution stays the only lifecycle store.
- The spool is never read as authority except through `status` inside the control plane.
- Dispatch and observation are separate commands.
- Admission under one lease stays single-flight, including `lost`.

Tests are listed in the §G matrix, items U13–U22 and I4–I7.

Sept 3 reconciliation rule: before starting Stage 6, `git log origin/dev` for a Sept 3 implementation.
- If one has merged, reuse its status/wait surface and change it only to add host-awareness (`lost`, worker observation).
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
| U11 | attestation host mismatch / nonce mismatch / fingerprint mismatch | `placement_mismatch`; decision `failed` |
| U12 | backend-local fallback prevention | `estate_router.execute_local`, `execute_codex` and `_execute_codex_with_sandbox` monkeypatched to raise inside the control plane; U1–U11 still pass |
| U13 | ParkLease-gated write, lease held by home, route home | worker `worktree.verify` then `start` on home; row `host_id=home` |
| U14 | write with lease held by lab, route home requested | refused `write_lease_missing` (lease holder ≠ route.host); no row |
| U15 | write without lease | refused; no row; no `start` |
| U16 | duplicate dispatch while non-terminal | same `execution_id`, `dispatch: reused_in_flight`, `start` called once |
| U17 | worker `start` response lost, retried | worker returns `reused: true`; one spawn |
| U18 | status without redispatch | `get_estate_execution(id, wait_s=10)` observes running→succeeded via fake `status`; **zero** `/run` or `start` calls during observation |
| U19 | worker loss mid-run | no observation for `timeout+120s` (clock monkeypatched) → `lost`; status returns promptly |
| U20 | dispatch under lease with `lost` row | `lease_has_unresolved_lost_execution`; no new row |
| U21 | worker returns after loss | reconcile maps `lost` → spool terminal state; admission reopens |
| U22 | legacy row without worker handle on non-local host | `lost`, not `interrupted`; no `os.kill` |
| U23 | truthful telemetry | for U1–U11, `RoutingDecision.host_id == route.host` and `executed_host_id ∈ {route.host, null}`; never another host except under `placement_mismatch` |
| U24 | identity verified / worker disabled | ineligible with the worker-specific reason |
| U25 | remote read-only repo work | `codex-readonly` on home fake gets `repo_id` and resolves cwd on home (fake asserts that path came from home inventory, not lab) |
| U26 | worker import hygiene | `core.database` absent from `sys.modules` after each worker verb |

### Integration tests (real subprocesses, no paid inference, no network)

| ID | Scenario |
|---|---|
| I1 | `LocalTransport` → real `python -m src.estate_worker` → `health`, `inventory` against a stub Ollama HTTP server on an ephemeral `127.0.0.1` port (worker Ollama base overridable by env `AOTERU_WORKER_OLLAMA_BASE`, test-only; default `127.0.0.1:11434`) |
| I2 | `/api/estate/run` (TestClient) lab placement end to end through LocalTransport with the stub Ollama; response `placement.attested: true` |
| I3 | `SshTransport` argv + stdin contract with `ssh` replaced by a shim script on PATH that execs the local worker (proves the stdin/forced-command shape without a network) |
| I4 | durable write lane through LocalTransport with `_execute_codex_with_sandbox` replaced in the **worker** by a sleep-then-write stub (via the `~/.aoteru/worker_selftest_enabled` sentinel file + `kind: "noop-sleep"`), a real detached spawn, real spool, real monitor thread → `succeeded`; `aoteru execution <id> --wait` (client against TestClient) observes it |
| I5 | kill the detached runner mid-run → worker `status` reports `failed`/`unknown` → row terminal; no redispatch |
| I6 | Sept 3 sequence: dispatch E, duplicate while running → same E, observe via status only to terminal, new dispatch → new E with `dispatch: new` |
| I7 | remote-host park via `?host=` with FakeWorker `worktree.prepare` → ParkLease row `host_id=desktop-in7o23d`; heartbeat/release with `?host=` |

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

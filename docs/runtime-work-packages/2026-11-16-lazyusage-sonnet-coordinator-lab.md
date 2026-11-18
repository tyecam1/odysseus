---
title: /lazyUsage Sonnet coordinator — partial implementation, acceptance owed
owner: odysseus
task: 2026-11-16-lazyusage-sonnet-coordinator-lab
status: partial
created: 2026-11-16
updated: 2026-11-18
---

# Sonnet cognitive coordination for persistent /lazyUsage

Task `2026-11-16-lazyusage-sonnet-coordinator-lab` is **unfinished**. PR #282
created its contract; #283 merged a GLM-first candidate. That candidate and
this worktree's corrections do not satisfy Sonnet deployment acceptance. Odysseus
retains every scheduling, dispatch, persistence, budget, lease and verification
decision; the coordinator is ONE bounded advisory planning call per unchanged
frontier state inside the existing `lazy_usage_runtime` loop.

## Original merged candidate design (historical, #283)

The GLM-first ordering below describes the merged baseline, not the requested
Sonnet-only coordination contract. The 2026-11-18 correction is recorded below.

- **Opt-in per activation** (`POST /api/lazy-usage/start` `{"coordinator":
  {"enabled": true}}`, laptop `am lazy start --coordinator`). Default remains
  off for activations that do not ask for it.
- **Usage-aware lane selection by design** (`src/lazy_usage_coordinator.py`):
  each turn selects the cheapest adequate lane from (a) live provider health
  (`provider_allows_dispatch`), (b) host executor qualification
  (`config/estate.yaml`), and (c) the run's remaining paid budget — the call
  is skipped entirely when less than `min_paid_budget_remaining` (2) paid
  calls remain, reserving budget for real task dispatch. Routine turns prefer
  `glm-flash`; high-consequence turns (owed verification debt or repeated
  failures) prefer `claude-sonnet`, then `glm-standard`, then `glm-flash`.
  Lane order is central policy in `config/routing.yaml`, not code.
- **No second scheduler:** the strictly validated plan (exact JSON schema,
  bounded sizes, refs must exist in the live frontier) only reorders
  candidates and contributes a bounded advisory decomposition for the primary
  task. Every gate in `_choose` (buckets, terminal status, blocked/protected
  metadata, route qualification, reviewer allowlist, provider health) is
  unchanged and still authoritative.
- **Accounting and restart safety:** the call is charged to the run's own
  `paid_calls`/`tool_calls` BEFORE the provider boundary and committed; the
  validated plan, lane, attested model and frontier-digest key are
  checkpointed. An unchanged frontier digest reuses the persisted plan across
  restarts with no repeat paid call. Provider failures, invalid output,
  unqualified lanes and quota exhaustion all fail closed to the deterministic
  loop with a bounded skip reason.
- **Rollback:** `ODYSSEUS_LAZY_USAGE_COORDINATOR=0` in the service
  environment or `lazy_usage_coordinator.enabled: false` in
  `config/routing.yaml` disables the step without redeploying; per-run opt-in
  still governs. Existing stop/pause controls are unchanged.

## Provider lanes

- **GLM-Flash (`glm-flash`)** — `execute_glm(variant="flash")` through the
  operator-owned `~/.local/bin/claude-glm-flash` launcher (PR #38 boundary:
  the launcher, not Odysseus, owns endpoint/model/credential setup). Flash
  existence attested from the authenticated Z.AI catalogue on 2026-11-16
  (`glm-5.3-flash`, released 2026-08-14, latest flash family). This is the
  routine coordinator lane and the `glm` executor's qualification evidence
  for `hz2-workstation`.
- **Claude Sonnet subscription (`claude-sonnet`)** — new `execute_claude` in
  `src/estate_router.py`: one tool-less `--bare` call through the unmodified
  official Claude Code CLI under the host's existing subscription login, with
  rolling `sonnet` alias (subscription currency policy), single-Sonnet model
  attestation from the provider usage response, typed fail-closed outcomes
  (auth/quota/rate-limit/mismatch) and provider-health recording. **Not a
  qualified executor anywhere yet:** the lab CLI's OAuth session expired
  (probe 2026-11-16: "OAuth session expired and could not be refreshed").
  The genuine operator action owed is one interactive `claude login` on the
  lab; qualification then needs a live attested call plus a one-line governed
  `config/estate.yaml` commit. Until then the lane fails closed and the
  coordinator uses the GLM lanes.
- **GLM standard (`glm-standard`)** — existing `claude-glm` launcher
  (`glm-5.3`), now a qualified read-only advisory executor on
  `hz2-workstation` under this evidence.
- **Consultation routes:** task execution continues to dispatch exclusively
  through the existing router lanes (codex/codex-write, glm advisory
  failover). Codex consultation rides the existing ChatGPT-authenticated
  CLI; GLM/Flash consultation rides the qualified glm executor. Opus remains
  unqualified in the paid router (contract-documented dependency, unchanged);
  no premium review substitution is introduced (2026-11-10 review policy).

## Qualification and acceptance evidence

(Filled from live deployment; see git history of this file for the
implementation-time record. Live qualification runs and the post-deploy
acceptance record are appended below as they complete.)

## Live qualification (2026-11-16, pre-merge)

- Z.AI catalogue (authenticated read, operator env, token not exposed):
  `glm-5.3-flash` and `glm-5.3-flashx` present alongside `glm-5.3`; flash
  lane uses the newest flash-family standard model `glm-5.3-flash`.
- `claude-glm-flash` launcher installed (0700, sources the same operator
  env; model `glm-5.3-flash`).
- Claude subscription probe: OAuth session expired (see above); sonnet lane
  correctly fail-closed pending operator re-login.

## Live qualification (2026-11-16, branch feat/lazyusage-cognitive-coordinator 3c787d9b)

Full suite: **9583 passed, 47 skipped, 5 deselected (live units), 5 xfailed**
(plus 41 coordinator tests inside that count).

- **GLM-Flash lane live-attested:** `execute_glm(variant="flash")` against
  the live Z.AI endpoint through `claude-glm-flash`: `ok: true`,
  `concrete_model: glm-5.3-flash` (provider-usage-response attestation),
  strict-JSON plan output, 5.6 s latency. Provider health for `glm`
  recorded `state: ok, allowed: true` in the authoritative controller DB.
  This run is the `glm` executor qualification evidence for
  `hz2-workstation` (read-only advisory, standard + flash launchers).
- **Claude subscription lane fail-closed live:** `execute_claude` typed
  `auth_failed` (OAuth session expired), provider health `claude`
  `auth_failed, allowed: false` with 15-minute backoff. The lane correctly
  refuses rather than bypassing; owed operator action: one interactive
  `claude login` on the lab, then a live attested Sonnet call plus a
  one-line governed `config/estate.yaml` qualification commit.
- **Codex:** quota window expired 2026-11-13T17:03Z; `allowed: true`
  (retry permitted on next dispatch).

## Reconciliation and bounded correction (2026-11-18)

**Implemented in the admitted worktree; not merged, deployed, qualified or
accepted.** The owning card remains `ready`. No unrelated child task was
started, and no task was counted as shipped.

Authority and live evidence:

- Worktree/admission HEAD: `606fb81f62021ac62251438cfaede62130ad26bd` (#285).
  The registered lab checkout is on `deploy/dev-20261118` at that same SHA.
  This is checkout evidence, not an independent attestation of code loaded by
  the service. Systemd bus access is denied and loopback HTTP is unavailable
  inside this worker sandbox; current loaded SHA and health remain unverified.
- Existing `codex-write` execution `80a28363-e8cc-4198-b6b2-e3cda2e07cfb`,
  provider `codex`, host `hz2-workstation`, owns this exact worktree under active
  lease `c5c32a1d-66a9-4a4d-845c-c18e9f95bde3` (heartbeat reconfirmed
  11:18 UTC). No lease was acquired or widened here. Shared Git metadata and
  production DB are read-only to this packet; finalization remains with the
  existing execution controller after this worker becomes terminal.
- `aoteru` is absent from PATH. The canonical Python client preflight reports
  `no backend configured`. The actual `delegation_preflight` implementation
  was therefore exercised against a temporary SQLite backup of the deployed
  DB, with no mocked eligibility and no production mutation. It attests the
  lab worker and existing write authority, but refuses a **new** Codex dispatch
  because this already-running execution has the provider launch reservation
  until 11:53:05Z. This packet continues the already-admitted worker; it does
  not treat the refusal as permission for nested dispatch or provider fallback.
- Live run `fd499041-79d6-41a0-b819-1d2937e22c74` has coordinator lane
  `glm-flash`, model `glm-5.3-flash`, and the above in-flight Codex execution.
  At the 11:09 UTC read it had spent 2 paid / 11 tool calls against 6 / 150
  limits. Its advisory prose suggests qualification/status actions, but only
  owner acceptance can settle this task. This run proves real planning and
  write dispatch, **not** completed write delivery or Sonnet coordination.
- Latest provider records: GLM `ok` (2026-11-18 11:07 UTC); Claude `auth_failed`
  (2026-11-16 13:34 UTC, historical cooldown already expired); Codex has this
  packet's unresolved launch reservation. No remaining subscription quota or
  reset was inferred from aliases, those records or old reset dates.
- `claude --version` reports official CLI `2.1.281`. A bounded, non-inference
  `claude auth status` returns exit 1, `loggedIn: false`, `authMethod: none`,
  `apiProvider: firstParty`. No tokens, profiles or account identifiers were
  read/copied. No Claude inference or API charge was attempted.
- Current [official programmatic-use documentation](https://code.claude.com/docs/en/headless)
  says bare mode omits subscription OAuth and uses separately supplied API
  authentication. Thus the earlier one-login remedy is insufficient for this
  adapter. [Official authentication/legal guidance](https://code.claude.com/docs/en/legal-and-compliance)
  distinguishes native subscription use from integrations and forbids
  credential intermediation. This source check is not an account-specific or
  university/lab policy approval; those remain unverified. Tool isolation was
  retained. No API credentials, billing or permissions were enabled.

Corrections in this worktree:

- Both configured consequence paths require the rolling Sonnet lane. Missing
  qualification or capacity records a skip and leaves eligible deterministic
  work available; GLM/Opus are not substitute coordinators. The explicit
  operator role exception is recorded in the existing currency policy.
- Live host eligibility is checked through the existing router, alongside
  executor qualification and provider health. No new router or lifecycle exists.
- Effective-model acceptance requires a single `claude-sonnet-5-5` identity
  (optionally with a dated snapshot suffix). Other versions, aliases and mixed
  model evidence fail closed. Dispatch still uses `sonnet`; configured permanent
  pins are rejected before launch.
- The official CLI receives `--tools ''` as well as the existing bare/MCP/
  no-session restrictions. Token counts must be valid nonnegative integers;
  bounded actual token usage is checkpointed even when plan validation fails.
- Empty candidate inventories, non-running states and exhausted budgets make
  no planning call. Call timeout is capped by remaining run time. Charges and
  attempted-digest fences remain durable before the call. Historical GLM plans
  cannot be reused as Sonnet plans, and upgrade preserves their attempt fences
  rather than replaying or rebilling them.
- Candidate titles and gate metadata provide bounded prioritisation context;
  model-generated steps remain untrusted checkpoint evidence and never enter
  worker instructions. Protected-task advice cannot override owner gates.

Verification:

- Updated initial coordinator selection: 51 passed.
- Coordinator/runtime/router/worker/GLM/model-policy checks: 316 passed.
- Final coordinator, disposable acceptance and delegation-preflight selection:
  91 passed, including effective-model mismatch, unknown/pinned routes, real
  token-accounting validation, tool removal, no provider substitution, invalid
  plan spend, remaining deadline, spent tool budget, stop/pause, protected
  advice, persisted GLM rejection and no replay after restart/failure.
- The first broad pytest process stalled at sandbox-denied cross-thread socket
  wakeups and was interrupted; it was not counted as a pass. The broad and
  acceptance runs used a temporary `/tmp` test launcher capping selector sleeps
  to 50 ms, following the existing packet-A sandbox workaround. Repository tests
  and assertions were not weakened. Provider boundaries are fixtures; these
  passes are not live deployment, model qualification or independent review.
- Durable execution/finalization and lease regression selection: 26 passed.
- Python parsing, configuration YAML validation and `git diff --check` passed.

Remaining acceptance, owner and event-based recheck:

| Gate | Current disposition | Next event / owner |
| --- | --- | --- |
| Sonnet 5.5 auth, terms, lab policy and effective identity | Unqualified; logged out; current bare adapter cannot use subscription OAuth | Existing Odysseus implementation/qualification route must establish a permitted auth and isolation combination. Any necessary account login or paid API authorisation stays operator-owned; do not repeat the ineffective login-only remedy. Then one bounded attested live call, independently verified. |
| Codex consultation | Existing authenticated worker route dispatched this packet; final effective-model/usage and delivery evidence not yet terminal | Existing execution controller observes and finalizes this execution; do not redispatch it. |
| GLM standard / Flash consultation | Newer merged registry and real GLM-Flash planning evidence exist; no write qualification inferred | Owning GLM task must settle exact currency, role-specific review/write qualification and separately bounded consultation acceptance; this task does not close it. |
| Opus consultation | No qualified Opus paid-router route established here | Recheck only after governed provider/host qualification and a consequential evidenced ambiguity; no routine premium review. |
| Independent review | V3 gate for this final delta remains open; no qualified permitted reviewer dispatched from this sandbox | Controller must preflight the exact finalized delta through qualified Haiku 5.5, Terra 6.1 or GLM-Flash. No silent Sol/Opus substitution. |
| Prior packet-D review and finalize-commit debt | Not closed by old reports; the latest three prior terminal Odysseus write records still have `worktree_resolution: recovered` | Inspect this packet's terminal commit evidence and owed review under the owning contracts. A new dispatch or passing tests cannot settle either debt. |
| Real queued Sonnet write delivery, restart/disconnect controls, owner reconciliation | Not proven; this packet remains running at evidence capture | After qualification and governed merge/deploy, exercise one real accepted owner task, its independent verification, accounting, client controls and controlled service restart. |
| HEAD/revision-bound planning and broader consultation integration | Existing key is frontier-metadata based; no stronger HEAD/body binding or new consultation route proved by this correction | Complete before claiming full coordinator acceptance; review current head-pinned dispatch gates independently. |
| Merge, deployment, health and rollback exercise | Owed for this worktree delta | Existing S6 finalization and permitted review/merge/deploy controls, then live health/route/task evidence. Rollback remains the existing coordinator kill switch/per-run opt-out; keep its deployed baseline until validated. |

Prompt application and evolution evidence are recorded at
`evals/prompt-applications/estate-queue-priority-execution/2026-11-18-lazyusage-sonnet-coordinator.yaml`
and `evals/prompt-evolution/2026-11-18-lazyusage-sonnet-coordinator.yaml`.
The initializer's three-owner metadata frontier was read without starting sibling
work: Odysseus 16 ready / 33 inbox / 6 blocked; Misumi and PhD roots available.
These are metadata counts, not acceptance adjudications or baseline shipment counts.

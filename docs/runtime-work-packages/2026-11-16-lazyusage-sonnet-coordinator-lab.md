---
title: /lazyUsage cognitive coordinator (usage-aware GLM-Flash / Sonnet lanes)
owner: odysseus
task: 2026-11-16-lazyusage-sonnet-coordinator-lab
status: in-acceptance
created: 2026-11-16
---

# Usage-aware cognitive coordination for persistent /lazyUsage

Implements task `2026-11-16-lazyusage-sonnet-coordinator-lab` (PR #282). Odysseus
retains every scheduling, dispatch, persistence, budget, lease and verification
decision; the coordinator is ONE bounded advisory planning call per unchanged
frontier state inside the existing `lazy_usage_runtime` loop.

## Design

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

## Live acceptance (2026-11-18, deployed 606fb81f, service odysseus-aoteru-lab @127.0.0.1:7001)

Deploy chain: PR #283 (coordinator slice, merged 72c79b41) → deploy/dev-20261116;
PR #285 (preflight write-intent fix, merged 606fb81f) → deploy/dev-20261118.
`systemctl restart` + `/api/health` 200 on each. Laptop client updated
(`am lazy start --coordinator`).

Run `fd499041-79d6-41a0-b819-1d2937e22c74` (operator, scope `odysseus`,
budgets max_paid_calls=6 / max_seconds=7200, coordinator opted in):

- **Coordinator live:** lane `glm-flash`, attested `glm-5.3-flash`
  (provider-usage-response), strict-JSON plan persisted
  (`coordinator_order` across the real frontier, bounded decomposition,
  next_action), exactly ONE paid call charged; the frontier-digest fence
  prevented any repeat planning across restarts and later ticks.
- **Real queued write delivery (PR #279 debt):** the loop dispatched
  write execution `80a28363` through preflight (fixed by PR #285: the
  runtime's authoritative write classification now overrides the
  objective-text heuristic) → ParkLease `c5c32a1d` (session = the run) →
  codex-write worker on `gpt-6.1-sol`, exit 0, 796 s, 179,977 tokens,
  targeted suites 316/91/26 green. The worker independently confirmed the
  Claude OAuth blocker and left its correction **unmerged** on leased
  branch `task/lazyusage-fd499041-…-e1fa573782` (pushed, commit
  `3f3fae1d` after governed finalize) — owner acceptance and independent
  review of that branch remain owed (`owner_acceptance` debt recorded by
  the run itself).
- **Mid-flight service restart:** `systemctl restart` at ~2 min into the
  13-minute write execution. After restart: same `in_flight_execution_id`,
  counters byte-stable (paid=2), no duplicate dispatch, no repeat
  coordinator call; the durable worker spool carried the execution to
  `succeeded` laptop-independently.
- **Exactly-once accounting fence:** the worker result carried no
  authoritative child usage totals, so the run fenced further dispatch
  (`usage_accounting_pending`) rather than treating unknown usage as
  zero — the documented packet-A metering dependency, now demonstrated
  live.
- **Restart-observer gap + S6.2 recovery (packet-C diagnosis):** the
  restart killed the write lane's in-backend observer thread, leaving the
  succeeded execution unfinalized and the lease pinned. The documented
  recovery path worked end-to-end: `am finalize 80a28363` committed and
  pushed the worktree (`3f3fae1d`), `worktree_resolution: finalized`, and
  the lease released cleanly. Finalize's git commit itself did NOT
  reproduce the Nov-11 production commit failure — today's evidence
  attributes that symptom class to the lost-observer condition, not the
  commit step.
- **Laptop controls:** `am lazy start --coordinator / status / pause /
  resume / stop` all exercised from the laptop; stop terminalized the run
  (`operator_stop`, owed reviews preserved).
- **Bounded failure mode (2026-11-16 run `cefb1120`, pre-fix):** every
  activation parked at the preflight write-heuristic defect, terminalized
  `budget_exhausted` at exactly 1 paid call — no spin, no unbounded paid
  calls.

Counts: run fd499041 final — paid 2/6, tool 70/150, no_delivery 1,
repeated_failures 1, elapsed 905 s, terminal `operator_stop` with 1 owed
review (owner acceptance of the delivered branch).

### Owed

1. **Claude Sonnet subscription lane:** one interactive `claude login` on
   the lab (OAuth session expired 2026-11-16, typed `auth_failed`
   fail-closed live), then one live attested Sonnet call + a one-line
   governed `config/estate.yaml` qualification commit. Until then the
   coordinator runs the GLM lanes and `claude-sonnet` fails closed.
2. **Review/merge of the delivered branch**
   `task/lazyusage-fd499041-…-e1fa573782` (`3f3fae1d`, Sol 6.1 worker
   correction of this slice) — the run's `owner_acceptance` debt.
3. **Worker-boundary usage metering** (packet-A dependency): child
   paid/tool totals so the accounting fence can reconcile automatically.
4. **Opus consultation lane:** unqualified in the paid router
   (contract-documented dependency, unchanged by this slice).

Rollback (verified live): `POST /api/lazy-usage/stop` terminalizes;
`ODYSSEUS_LAZY_USAGE_COORDINATOR=0` or
`lazy_usage_coordinator.enabled: false` disables the coordinator without
redeploy; `git revert` of 72c79b41/606fb81f on dev + deploy-branch
redeploy restores pre-feature behaviour; prior deploy branch
`deploy/dev-20261111` retained.

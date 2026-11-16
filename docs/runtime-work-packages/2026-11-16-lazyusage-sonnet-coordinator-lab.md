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

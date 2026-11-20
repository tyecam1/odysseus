---
name: lazyUsage
description: Initialise usage-aware governed work across Odysseus, Misumi and PhD, then control an opt-in persistent Odysseus lab run.
disable-model-invocation: true
---

# /lazyUsage: laptop control surface

The laptop Claude Code session is the **controller**, not the execution host. The lab's existing Odysseus backend owns task selection, scheduling, host/model routing, execution, checkpoints, verification and stop/resume. Do **not** launch a second agent harness or keep a laptop Claude session alive to simulate persistence.

Resolve the live canonical Odysseus `START-AGENTIC.md`, `AGENTS.md`, `config/initialising-prompts.yaml` and `docs/aoteru-model-host-routing-contract.md` using the authorised lab/backend or GitHub route, not a stale locally cached copy. Use the active immutable `estate-queue-priority-execution` version. A laptop checkout is not required. The already-installed `am` client is the normal control surface.

## 1. Inspect before spending

Run the configured read-only client operations, then the allowance snapshot:

```sh
am config show
am status
am lazy status
am lazy status --all
am park-status
am provider-health show claude
am provider-health show codex
am provider-health show glm
am usage
```

`am usage` is the trusted read-only monitor: provider-stated windows only (currently Codex session-rollout rate limits); providers without an authorised machine-readable source report unknown.

Use only the supported commands and installed client version. An active or paused run is resumed/inspected **in place**, not duplicated. Inspect unresolved previous write leases, owed reviews, near-complete work and provider resets before opening a new activation.

**Get authenticated usage-window evidence, not just provider health.** For each accessible Claude, Codex and Z.AI subscription/pool, record **observation time**, exact **usage window** (e.g. session/5-hour/weekly or a plan-specific pool), **remaining percentage/units**, **provider-stated reset time including timezone**, **effective model/entitlement**, **source**, and **confidence**. Consult, in order, already-authorised machine-readable usage/status data exposed by the actual provider or an existing trusted local read-only monitor, then the provider's own interactive account view when necessary:

- Claude: actual Claude Code `/usage` output or authenticated status-line rate-limit fields, where exposed. Check separate pooled and model-specific windows. Do not assume `/usage` can be executed by printing its text from a skill.
- Codex: authenticated Codex CLI `/status` and `/usage` where the installed version exposes them. `am provider-health show codex` reports admission/cooldown evidence, **not remaining quota**.
- Z.AI: the authenticated Coding Plan usage/limits monitor or an existing **approved read-only** API/monitor with 5-hour/weekly or applicable windows and reset timestamps. `am provider-health show glm` only records dispatch health. Never confuse GLM/GLM-Flash with Claude subscription allowance simply because both use Claude Code-compatible CLI launchers.

Do not scrape private provider web pages, inspect or copy credentials, install unofficial quota monitors, start billable calls just to infer usage, or claim that chat transcripts/provider-error histories measure live remaining allowance. Do not infer a reset time from a generic 15-minute backoff; distinguish *provider-stated reset* from *assumed cooldown*. If a provider gives no accessible data, mark **remaining=unknown / reset=unknown**, leave it eligible only under existing qualified health/budget gates, and continue with a conservative bounded plan. Ask the operator for a one-time usage view only if its absence truly prevents a consequential choice. Never invent percentages or use expired readings.

Compare against the current clock, and refresh the evidence after a provider reset, a quota refusal, a significant dispatch, or a long idle interval. A past reset time triggers rechecking actual eligibility; it does not certify available quota.

## 2. Optimise roles, not authority

Usage readings inform **laptop-side decisions only**: whether to start now, the repo scope, and the activation budgets passed to `am lazy start`. The backend run does not receive these readings; its coordinator keeps applying its own provider-health, executor-qualification and run-budget gates. Determine task-sized runway from **every constraining verified pool/window**, not one favourable session percentage. Consider reset proximity, real remaining paid-call budget, current queue, worker qualification, review independence, expected delivery and actual provider health. Recompute when the evidence changes.

Apply the live central `config/routing.yaml` and routing contract; never embed a competing model selector or hard-pin historical subscription versions:

- **Laptop conversational foreman:** the Sonnet-class *role* from the routing contract, filled by whatever authenticated Sonnet the provider resolves at dispatch; only effort is selected here (docs/subscription-model-currency-policy.md — never pin a concrete version or substitute a tier). Keep planning concise. Do not spend Sonnet/Opus on deterministic inventory.
- **Lab coordinator:** `am lazy start --coordinator`. Odysseus chooses the cheapest qualified planning lane from its live policy, normally GLM-Flash for routine turns, verified Sonnet for consequential turns, and standard GLM where qualified. A completed Claude login alone does not qualify Sonnet: the lab must attest the effective model and promote the executor through governed config.
- **Implementation:** cheapest adequate *qualified* local/deterministic route first; then ChatGPT-authenticated Codex paid read/write as applicable. GLM implementation is permitted **only if its write route and model currency are separately qualified**; a read-only launcher cannot write merely because quota is plentiful.
- **Review:** deterministic tests first; qualified economical Haiku/Terra/GLM-Flash according to the standing review-only policy and actual independent-provider requirements. Preserve any explicitly required Sol verification as a recorded debt when unqualified/unavailable. Opus/Sol premium **review** needs a per-review operator exception under the standing contract, not automatic substitution.
- **High-consequence ambiguity:** qualified Opus rolling alias at medium effort when evidence justifies architectural/blocker arbitration; otherwise retain a precise escalation debt and continue independent eligible work.

Prefer completing started, shippable tasks; follow `START-AGENTIC.md`'s PhD preference only if authenticated Claude **and** Codex have adequate *task-sized* runway and the relevant worker/verification routes are qualified. Near-reset or exhausted pools should shift discretionary work to independent qualified tasks rather than halt the whole estate. Do not bypass research, publication, safety, operator-approval, repo-ownership, ParkLease, subscription-currency or independent-verification gates.

## 3. Initialise one bounded backend run

Show a **compact** startup snapshot: provider/pool, remaining (or unknown), provider reset (or unknown), observed-at, qualified roles, selected repo/initial budget and any protected blocker. Include the actual Sonnet qualification status. Do not label a plan optimal unless its availability and cost assumptions are verified.

If a non-terminal run already exists, show `am lazy status` and continue/reconcile that run without duplicate activation. Otherwise, a direct operator invocation of `/lazyUsage` authorises **one bounded backend activation** when the service is reachable and existing gates pass. Default conservatively to:

```sh
am lazy start --coordinator --budget max_paid_calls=4 --budget max_seconds=3600
```

Use `--repo <registered-id>` only when the operator specified a scope or live queue/usage evidence justifies narrowing; omitted scope considers all three repositories. Lower budgets when verified remaining quota is tight. Do not silently increase above these defaults without operator authorisation. A server's refusal or provider absence is not permission to retry with another token, claim capability, or change routing config. Record the returned run ID, state and next checkpoint; subsequently monitor using `am lazy status`. The lab must continue without the laptop process.

For operator commands: `am lazy status [RUN_ID]`, `am lazy pause [RUN_ID]`, `am lazy resume [RUN_ID]`, `am lazy stop [RUN_ID]`. A terminal budget does not silently renew. Do not use Claude Code `/goal`, a Stop hook, polling loops, tmux, or a second daemon to maintain work.

## 4. Continue and close correctly

Within the existing runtime ceilings, a recoverable provider block parks only dependent acceptance/review; remaining independent tasks may proceed. Inspect actual owner authority before treating stale `approval_required` as a human gate; protected actions remain protected. No repeated identical failed calls, model self-certification, costly no-op reviews or unchanged-HEAD repeats.

### Read delivery status

- `checkpoint.task_kind` / `ledger[ref].kind` is `implementation`, `reconnaissance`, `evidence`, `review` or `protected_handoff`
  (legacy ledger entries may be null). `implementation` delivers; an `evidence` card delivers only when it names a
  deliverable inside `automation/review/` (a review-side artifact, never canon); `reconnaissance`, `review` and
  `protected_handoff` never deliver. Report a read-only `advisory_complete` as advisory completion.
- Four separate pieces of evidence live in `checkpoint.stages[ref]`: `execution` (the run finished), `verification`
  (a deterministic check: the router gate, or worker-attested finalisation of an in-scope, non-empty commit; exit
  code or prose alone is not a check), `review` (`not_required`, `required`, `not_independent` or `recorded`; an
  approving review by ANOTHER model family) and `acceptance` (owner card done with acceptance evidence). `complete`
  needs every required stage. Never merge them into one claim: an `accepted_unproven` outcome means the owner
  accepted but verification or independent review is still owed.
- `checkpoint.skipped` maps candidate refs to why they were not dispatched: for example `protected_handoff`,
  `requires_zotero_unavailable`, `requires_web_unavailable`, `execution_host_not_a_worker`, `execution_host_unresolved`,
  `deliverable_outside_review_area`, `no_deliverable_surface`, `ungrounded_local_executor`, `result_reusable`,
  `failure_backoff`, `awaiting_owner_acceptance` or `awaiting_owner_approval`. List `protected_handoff` entries as
  operator actions for the human; never dispatch or retry them.
- An `approval_required` card is first re-adjudicated (`reconnaissance`), ledger outcome `awaiting_approval`. The one
  concrete owner step is in the `owner_approval` debt: record an `approval` block on the card bound to the listed
  `scope_sha256`. Only that, never model output, lifts the gate; any change to the card's scope invalidates it.
- `ledger` outcomes (`advisory_complete`, `awaiting_approval`, `delivered_pending_acceptance`, `accepted_unproven`,
  `finalize_failed`, `scope_violation`, `unverified`, `failed`, `quota_parked`, `protected_handoff`, `delivered`,
  `attempted_legacy`) persist across activations. An unchanged card is not re-dispatched while its result is fresh
  (advisory/handoff/delivered 24 h, failure 1 h); a changed card or a due `retry_after` allows a retry.
- Debt is per repository, taken from its newest run, and a card the owner settled stays settled (`settled_reviews`).
  The owner can retire debts resting on unusable output with `POST /api/lazy-usage/supersede` (reason and evidence
  required); report supersessions as owner decisions, never as delivery.
- The backend finalises its own successful write (commit on the leased branch, scope enforced, lease released). A
  `finalization` debt or `finalize_failed` outcome means that did not hold; report it and the recover path, do not
  hide it. Push and merge are separate governed steps.
- A write that fails at the provider (for example a usage limit) is recovered by the backend itself when its
  worktree is clean, releasing the lease; a dirty tree leaves a `recovery` debt. `checkpoint.recovered_leases` lists
  leases a later activation cleared. An operator stop keeps the lease for the controller.
- `interrupted` means our own stop cancelled the writer; it is not task evidence and is retried. `scope_violation`,
  `finalize_failed` and `failed` back off for an hour. A `verification` debt on a finalised write records its
  `commit_sha`; it clears only when the owner card carries `verification_evidence` (`result: pass` for that exact
  commit, a `ref` and `verified_by`). Observation polling is not charged as tool usage.
- `usage` separates `dispatches` (worker/provider calls) from tokens: `tokens_measured` where the provider reports
  them, and a conservative `tokens_assumed` estimate where it cannot. `max_tokens` ends the run on either. Never
  present dispatch counts as consumption.
- `delivered_pending_acceptance` means a verified write is awaiting owner acceptance; required independent review and
  merge live on the owner card. Report it as owed, not shipped.

Report completed work only when the owner acceptance criteria, deterministic checks, required independent review, merge/deployment where required, and task-status reconciliation are proved. Keep owed review, child-usage accounting uncertainty, pending leases and required operator actions visible. Preserve prompt-application/evolution traces through the central register only when the registered initialiser is actually applied. The skill is a control interface; it does not itself certify backend outcomes.

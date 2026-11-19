# /lazyUsage delivery corrections (2026-11-19)

Owning task: `2026-11-16-lazyusage-sonnet-coordinator-lab` (acceptance debt from run
`fd499041`), triggered by failed activation `b102b3ce`.

## What failed

Activation `b102b3ce` (all repos, coordinator on, `max_paid_calls=3`) ended
`budget_exhausted / max_repeat_failures` after 7.5 minutes with **zero deliveries**:
1 paid coordinator call, 4 tasks sent to the local `qwen3:8b`, 3 owed reviews.

Three root causes, each reproduced on the real cards:

1. **Failure accounting.** `_observe` recorded a *successful, verified but not yet
   accepted* execution as a failure whose signature was the card's status
   (`sha256("ready")`, identical in `b102b3ce` and `fd499041`). Three different tasks
   therefore looked like one task failing three times.
2. **Classification.** `approval_required: true` forced every card into the same
   read-only "reconnaissance" path regardless of what it was:
   `branch-protection-main` is a human-only GitHub settings handoff
   (`executor: human`, `execution_mode: handoff`); `icac2026-…` is evidence synthesis
   that needs Zotero; `opportunity-radar-…` is an implementation. All three were sent
   to a plain local model that has no repository access (it fabricates plausible
   text, see `aoteru-cli-quirks` item 3) and "passed" the minimal non-empty gate.
3. **Selection by metadata only.** Nothing validated tools, deliverable, lane or
   authority before dispatch, and the coordinator ranked candidates from
   `ref/bucket/priority/status` alone.

Two further defects sat behind them: a fresh activation re-attempted everything the
previous one had just tried (the attempted fence was per run), and the worker never
reported child usage, so every write execution fenced continuation
("worker did not report child paid/tool totals").

## Corrections

All in `src/lazy_usage_runtime.py` unless noted.

| Area | Change |
|---|---|
| Classification | `_classify` derives `implementation`, `reconnaissance`, `evidence`, `review` or `protected_handoff` from the card only. Only `implementation` can deliver (`DELIVERING_KINDS`). |
| Failure accounting | `_failure` signature is task + revision + cause. A successful non-delivering run is `_no_delivery` (spends a no-delivery turn, ends any failure streak), never a failure. |
| Feasibility | `_assess` is the single, side-effect-free dispatch gate: protected handoff, protected gate, `requires_zotero` (no estate host provides it), write without a deliverable surface (`allowed_paths`/`outputs`/`result_path`), no qualified lane, **ungrounded local executor for advisory work**, provider health, reviewer attestation. Advisory classes default to the paid, repo-grounded lane. |
| Coordinator context | `candidate_evidence` feeds the prompt only dispatchable candidates (with kind, `delivers`, verification route, approval flag, last outcome) plus a bounded `excluded` list with reason codes. No feasible candidate means no paid planning call. |
| Persistence | A per-task `ledger` (revision, kind, outcome, time, execution) is inherited from the last terminal runs together with owed acceptance debt. Windows: advisory/handoff results 24 h (`ADVISORY_REUSE_SECONDS`), failures 1 h (`FAILURE_RETRY_SECONDS`), quota debts until the stated reset, awaiting-owner-acceptance until the debt clears. A changed card revision always retries. Legacy runs' `attempted` map is inherited as a reuse window. |
| Worker usage | `estate_worker._execution_usage` reports `{paid_calls, tool_calls}` from the spool's decision files (writer = one paid call; each finalize/push attempt = one tool call); `estate_write_lane._apply_view` stores it with the terminal result so `_observe` meters it exactly once. A worker that reports nothing still fences continuation (absence is not zero). |
| Claude lane | `execute_claude` returns `provider_usage` (token counts); the coordinator checkpoints it. |

## Reconciliation of branch `3f3fae1d`

The branch (Sol 6.1 worker output of `fd499041`) was rebuilt on a pre-#286/#287/#288
base. Applied or rejected deliberately:

* **Kept:** live host eligibility for the coordinator lane check, coordinator
  budget/state/no-candidate gates and remaining-seconds timeout, Claude token
  accounting, the two prompt-application/evolution records.
* **Rejected: Sonnet-only lane policy.** It removed the GLM-Flash routine lane that
  the deployed policy and the 2026-11-19 operator instruction rely on.
* **Rejected: strict `claude-sonnet-5-5` model regex.** Live evidence (2026-11-19,
  lab, owned config dir, one tiny call): the CLI reports `modelUsage` key and
  `canonicalModel` **`claude-sonnet-5`**, never `claude-sonnet-5-5`. The branch's
  check would have rejected the currently qualified lane. The CLI therefore cannot
  attest the minor release; the card's "Sonnet 5.5 identity" acceptance condition
  is recorded as **not provable from the CLI** rather than silently asserted.
* **Rejected: stale `models.yaml` / policy text** saying the Claude executor is
  unqualified (it was qualified in #288).

## Known limits

* Advisory work on `obsidian-phd` and `misumi` still depends on the router's
  advisory dispatch resolving the repo on the worker host; this change only refuses
  the ungrounded local route.
* `requires_zotero` is a hard block until a host declares a Zotero capability.
* The three owed reviews from `b102b3ce` come from fabricated local-model output;
  they are inherited as debt and should be superseded by the owner, not accepted.

## Rollback

Revert the squash commit and redeploy the previous branch
(`deploy/dev-20261119` @ `5f918735`). The ledger/`skipped`/`task_kind` checkpoint
keys are additive and ignored by older code; `usage` in a stored write result is
additive. `ODYSSEUS_LAZY_USAGE_COORDINATOR=0` still disables the coordinator alone.

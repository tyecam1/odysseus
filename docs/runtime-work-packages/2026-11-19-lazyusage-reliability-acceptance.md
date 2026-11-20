# /lazyUsage reliability and acceptance (2026-11-19)

Follows `2026-11-19-lazyusage-delivery-corrections.md` (#289/#290). Each defect below was
reproduced by a failing regression test before it was fixed
(`tests/test_lazy_usage_reliability.py`, `tests/test_worker_finalize_paths.py`).

| # | Defect (deployed `ba4aa58b`) | Correction |
|---|---|---|
| 1 | Debt reconciled in one activation reappeared: `_inherited_history` unioned `owed_reviews` of the last 10 runs, so an older all-repo run resurrected what a newer run had settled. | A repository's debt comes from the **newest run that covered it**, never merged. Debts are keyed by task identity (`repo:card-name`, bucket-independent). Settling a card writes a `settled_reviews` tombstone that is inherited; a debt older than its tombstone is dropped, one opened later (`opened_at`) reopens. |
| 2 | Execution success, deterministic verification, independent review and owner acceptance were one boolean (`exit_code == 0 and output` counted as verified). | `evidence_stages` keeps four stages with their own evidence in `checkpoint.stages[ref]`. Verification is the router's deterministic gate or worker-attested finalisation of an in-scope non-empty commit; prose/exit code is not a check. Independent review must name an approving reviewer of **another model family**. An owner-accepted card without the other evidence is `accepted_unproven` and keeps `verification`/`independent_review` debts. |
| 3 | `approval_required` forced every card into reconnaissance forever; evidence/review cards could never deliver. | `evidence` cards with a deliverable inside `automation/review/` deliver through the write lane (scope-enforced). An approval-gated card ends reconnaissance as `awaiting_approval` with one `owner_approval` debt carrying `scope_sha256`; the owner records an `approval` block bound to that digest, and any scope change invalidates it. `review` cards still have no delivering lane (writer must be an attested economical reviewer; only codex writes). |
| 4 | The dispatch gate ignored `execution_host`, `requires_web`, `requires_mcp`, `requires_local_model`. | `_capability_blocker` validates them against the host actually selected and the estate registry: laptop/interface/edge hosts are not workers, unknown labels fail closed, tools must be declared in `estate.yaml` `worker.capabilities` (lab declares only `web`, probed 2026-11-19). Reconnaissance skips it (it only reads the repo). |
| 5 | `paid_calls` counted dispatches; nothing bounded tokens. | `usage` separates `dispatches` from `tokens_measured` (provider-reported) and `tokens_assumed` (150k advisory / 400k write per unmeasured paid dispatch). `max_tokens` (default and hard ceiling 2,000,000) ends the run on either. |
| 6 | Worker finalisation parsed text `git status --porcelain`: staged renames became one bogus `old -> new` pathspec, quoted/non-ASCII names failed; nothing finalised a successful write, so the controller had to commit by hand; the worker did not enforce the card scope. | `_finalize_logic` parses `status --porcelain=v1 -z`, stages with literal pathspecs and never names a fully staged entry. When the request carries `allowed_paths`/`denied_paths` it reverts out-of-scope changes, commits only in-scope ones and reports `scope_violations` (the owner-card directory is always denied, so a writer cannot approve or accept itself). `_observe` finalises its own successful writes (`estate_write_lane.finalize_execution`), records a `finalization` debt and parks on failure, and releases the lease. |
| 7 | Three fabricated review debts of `b102b3ce` had no retirement path. | `supersede_review_debts` / `POST /api/lazy-usage/supersede` (execute scope; reason and evidence required): moves the debt to `review_supersessions` with principal, reason, evidence and the original debt, and tombstones it for later activations. It never marks a task delivered. |
| 8 | Laptop skill copy lagged `dev`. | Skill text updated here; the installed copy is backed up and synchronised after merge. |

## Live findings after deploy of #293 (activation `ae1b1f20`, 2026-11-19 20:16Z, unattended)

The first activation on the deployed code exercised the real estate and exposed three further defects
that unit tests had missed (each now has a failing-first regression test):

* **A write that failed at the provider left its lease active.** Codex was at its weekly usage limit;
  the dispatched write failed, its execution stayed `unresolved`, `release_repo` refused ("has unresolved
  execution ... next action: recover") and every later write on the repo was skipped `repo_lease_held`.
  The backend now recovers it itself through `estate_write_lane.recover_execution_lease` (proves writer
  quiescence and a CLEAN worktree); a dirty tree is refused and recorded as a `recovery` debt. An operator
  stop still preserves the lease for the controller. At the start of the next activation
  `_recover_orphan_leases` clears leases left by a *terminal* lazyusage run the same way
  (`checkpoint.recovered_leases`); a live activation's lease is never touched.
* **A provider-refused dispatch was charged 400k assumed tokens** although nothing ran. The dispatch is
  still counted; tokens are only assumed when the provider did not refuse.
* **Coordinator tokens were never metered** (`coordinator_usage` was recorded but not charged). They are
  now charged as measured tokens, or a 60k estimate when unmeasured.

## Live findings on 2026-11-20 (activation `f4b6f653`, first successful unattended writes)

After Codex's weekly reset the backend ran real writes with the laptop idle. Delivered unattended: two
finalised commits on leased task branches (worker-owned `-z` finalisation, scope enforced: the writer's
attempt to edit its own task card and two `evals/` files was reverted and reported), the lease released
and the next write admitted, and the backend restarted mid-write with the detached writer unit surviving
and the new instance resuming observation. It also found five defects, each now covered by a failing-first test:

* **Stale model.** The write lane ran `gpt-6.1-sol` on a user-local npm Codex pinned to `^0.163.0` (a caret on a
  0.x release pins the minor) while 0.171.0 offered `gpt-6.2-sol`. The lab install was updated, and
  `_resolve_codex_binary` now prefers the newest installed binary (never replacing one whose version it
  cannot read).
* **Polling exhausted the tool-call ceiling.** Every observation tick (and lease renewal) was charged as a tool
  call, so a 12-minute write cost ~50 and a budget stop cancelled a healthy write. Polling is no longer charged;
  dispatch, finalize, recovery, release and the worker's own reported usage still are.
* **A stop-cancelled write was recorded as a task failure.** It is now `interrupted` (no failure counted, no
  backoff) only when the execution's own error shows our cancel/fence; a real failure that coincides with a
  pending stop stays a failure.
* **A wasted write was retried immediately.** `scope_violation` and `finalize_failed` now back off for an hour
  like `failed`.
* **A finalised write's verification debt could never clear.** Verification is the router's deterministic gate
  only (a commit, an exit code and prose are not checks; this part is the Codex worker's own change, reviewed).
  The debt records the finalised `commit_sha` and clears only when the owner card carries a
  `verification_evidence` entry (`result: pass`, that exact `commit_sha`, a `ref`, `verified_by`).

Both writers reported their task as unfinished (`ready`, not shipped), so neither card is accepted: acceptance
stays with the owner, and independent review and CI-equivalent verification remain owed per card.

## Known limits

* Verification for a write is worker-attested finalisation, not a repository test run; CI on
  the publishing PR remains the test gate. Push/merge stay separate governed steps (the lab has
  no GitHub credentials by design).
* The CLI cannot attest the Sonnet minor release (`claude-sonnet-5`, see the delivery work package).
* Codex-write token usage is not reported to the lab, so it is metered by the conservative estimate.
* `review` cards still cannot deliver; `compute-box` is an unresolved host label (fail closed).

## Rollback

Revert the squash commit and redeploy the previous branch (`deploy/dev-20261119d` @ `9c5549a0`),
then `sudo -n /usr/bin/systemctl restart odysseus-aoteru-lab.service`. New checkpoint keys
(`stages`, `settled_reviews`, `review_supersessions`, `write_scope`, `dispatch_*`) and counters
(`tokens_*`) are additive and ignored by older code; `max_tokens` is ignored as an unknown budget
key only on read, so stop any non-terminal activation before rolling back.
`ODYSSEUS_LAZY_USAGE_COORDINATOR=0` still disables the coordinator alone.

# Governed execution return through `aoteru` (partial evidence for the second #211 acceptance item)

Status: **partial evidence, not the acceptance item.** #211's second item asks to "validate the SSH path from the laptop without sibling checkouts, then test the lab task preflight, lease, independent verification and end-to-end return" **through `/lazyUsage`**. That skill is `disable-model-invocation: true`, so only the owner can invoke it; this record is **not** a run of the skill and #211's item stays **unticked**. It records what was observed on the same governed path (`aoteru` to the lab backend) in the 2026-11-02..06 working session, as a baseline for a later owner-invoked run. It was written by the Claude Sonnet 5.5 coordinator of that session from the session's own records; it is the author's account, partly backed by the three execution records below, and has had one Sol review round (the findings are applied here).

## Who did what

For the code changes listed below, the **implementation** ran as `codex-write` executions on the lab (model `gpt-6.1-sol`), orchestrated by the Claude coordinator, which prepared briefs, fetched the results from the lab worktree, published them to GitHub and applied review corrections. The **review** of each change was a separate, read-only `codex-write`-lane execution (also `gpt-6.1-sol`, with a fresh context and a brief containing the diff and the design intent) plus CI. So the review was independent in execution and context, **not** a different model family from the implementer; the Claude coordinator is not an independent reviewer of Sol-written code.

## Observed elements

| Element | What the records show |
|---|---|
| Laptop control plane | All calls were made with the installed `aoteru` client from the owner's laptop; no Odysseus checkout exists on the laptop. (Author's observation across the session; the original #211 acceptance record covers the discovery path.) |
| Route and preflight | A live preflight on the redeployed service on 2026-11-06 returned `ok: true` with the lab eligible, the home worker unreachable, and codex health "unknown: no recorded outcome; initial attempt permitted". Routing to the lab was observed on each of the calls inspected, not audited for every call of the session. |
| Lease | `write_lease_missing` is refused without a park lease; the runners park a lease before dispatch and recover it afterwards. Observed on every run the author inspected; one run (a #235 review) failed because the previous lease had not been recovered (see failures). |
| Governed execution | Read back from the live service (field `finished_at`, UTC): execution `9b73169c` finished 2026-11-06 13:57:59; `61399727` finished 2026-11-06 08:37:31; `d5fa99da` finished 2026-11-06 08:24:19. Each shows `lifecycle_state: succeeded`, `exit_status: 0`, `worktree_resolution: recovered`, executor `codex-write`, host `hz2-workstation`, model `gpt-6.1-sol`. |
| Independent verification | Review executions as described above plus CI, then merge with `--match-head-commit` on the reviewed head. Code PRs delivered this way: #219, #220, #225, #226, #227, #235. Documentation PRs #228 to #240 mostly received Sol review rounds; exceptions: #230 and #231 were merged under the docs-only rule before a late package review, #232 and #236 apply review notes without a fresh round, #233 is a condensed Sol consult, and #240 itself is under review. |
| Return and recovery | The execution record carries the result text and `worktree_resolution: recovered` after the worktree was cleaned and the lease recovered. Delivery of results to the laptop was observed as the printed result of each run; the coordinator, not the estate, then published changes to GitHub. |

## Failures and incidents in the same period (not exhaustive; see the queue checkpoint `queue_checkpoint_20261102.md` in the owner's memory directory)

- **Usage limits:** several Sol and GLM limit stops, each recorded with the provider's exact text and reset time; work waited rather than substituting another model for a Sol gate.
- **Classifier denials:** at least two in this period (an earlier one on a pull-request edit was resolved by the owner's explicit authorisation). The first blocked the lab-service deploy step until the owner explicitly approved it; the second flagged a read of the lab service's environment file as credential materialisation and was not worked around.
- **Deploy-time incident:** after the owner-approved deploy, paid launches on the lab were refused ("authoritative DATABASE_URL required") because the service environment lacked the variable that the fail-closed quota check requires; the owner approved adding it, with a backup, and launches then succeeded. No connection string is recorded here.
- **Provider outage:** on 2026-11-06 a Codex launch failed after five seconds with "provider transport unavailable"; the new health tracking blocked further paid launches for its backoff and the provider read as available again later the same day.
- **Tooling repeats:** one review ran against a stale diff and was rerun; one review failed to start because the previous lease had not been recovered; two background pollers were stopped by the harness for memory pressure and not restarted; one stray application start in a clean clone ran scheduled jobs briefly and was cleaned up.

## What was not exercised

- Not run through `/lazyUsage`: no usage-aware queue selection among the PhD, Odysseus and Misumi queues, no `START-AGENTIC.md` initialiser run.
- The sandboxed Codex lane cannot commit, so changes were published by the control plane through the GitHub Git Data API; the estate's own push and resolve-prepare endpoints (`/run/{id}/push`, `/park/{repo}/resolve-prepare`) were not used for these changes.

## For the owner-invoked run: the acceptance gates to check

| Gate (from #211) | Status in this record |
|---|---|
| Laptop SSH/remote path without sibling checkouts | inherited: original #211 acceptance record; observed again implicitly (no laptop checkout), not re-tested as such |
| Lab task preflight | newly observed (2026-11-06 preflight above), not through the skill |
| Lease authority (park, `write_lease_missing`, recovery) | newly observed, not through the skill |
| Independent verification of the delivered head | observed as described (separate Sol execution plus CI, merge on the reviewed head), not through the skill |
| Observable result return and recovery | observed as described, with coordinator-side publication |
| Usage-aware selection under real usage states | **not covered**; a single-sample same-family check exists in `2026-11-06-lazyusage-selection-check.md` |

Also compare, in a future run: whether the estate push and resolve-prepare path is used instead of control-plane publication, and whether the calls carry `--subject`, `--head-sha` and `--function` (the call telemetry is live on the lab since 2026-11-06).

# Governed execution return through `aoteru` (partial evidence for the second #211 acceptance item)

Status: **partial evidence, not the acceptance item.** #211's second item asks to "validate the SSH path from the laptop without sibling checkouts, then test the lab task preflight, lease, independent verification and end-to-end return" **through `/lazyUsage`**. That skill is `disable-model-invocation: true`, so only the owner can invoke it; this record is therefore **not** a run of the skill and #211's item stays **unticked**. It records what was exercised on the same governed path (`aoteru` to the lab backend) in the 2026-11-02..06 working session, so that a later owner-invoked `/lazyUsage` run has a baseline to compare with. Written by Claude Sonnet 5.5; no Sol review of this record yet.

## What was exercised (control plane: the owner's laptop; no sibling or local Odysseus checkout used)

| Element | Evidence |
|---|---|
| Route and preflight on the lab | `aoteru lab` resolved the route on `hz2-workstation` each time (live preflight on the deployed service returned `ok: true` with the lab eligible, the home worker unreachable and codex health "unknown: no recorded outcome; initial attempt permitted"). |
| Lease | A park lease was taken before each write-lane run (`write_lease_missing` is refused without one) and recovered afterwards. |
| Governed execution | `codex-write` executions on the lab under that lease. Read back from the live service: executions `9b73169c` (2026-11-06 13:57), `61399727` (08:37) and `d5fa99da` (08:24) each ended `lifecycle_state: succeeded`, `exit_status: 0`, `worktree_resolution: recovered`, model `gpt-6.1-sol`, host `hz2-workstation`. |
| Independent verification | Each code change was reviewed by Sol (`gpt-6.1-sol`, a different model family from the Claude author) read-only through the same governed path, with CI as a second check; merges used the exact reviewed head (`--match-head-commit`). PRs delivered this way: #219, #220, #225, #226, #227, #235 (plus documentation PRs #228 to #239 reviewed the same way). |
| Return | Results came back through the estate's execution record and output; the lease was recovered (`worktree_resolution: recovered`) after cleaning the worktree. |

## What was not exercised, and differences from the acceptance item

- Not run through `/lazyUsage`: no usage-aware queue selection, no `START-AGENTIC.md` initialiser run, no selection among the PhD, Odysseus and Misumi queues by verified usage.
- The sandboxed Codex lane cannot commit, so changes were returned as working-tree files and **published by the control plane through the GitHub Git Data API**; the estate's own push/resolve-prepare endpoints (`/run/{id}/push`, `/park/{repo}/resolve-prepare`) were not used for these changes.
- Several reviews and runs had to be repeated for tooling reasons (a stale diff staged for review; a lease not recovered before the next park; usage limits). These are recorded in the queue checkpoint, not here.
- The SSH discovery path from the laptop without sibling checkouts is covered by the original #211 acceptance record, not re-run here.

## For the owner-invoked run

Compare a future `/lazyUsage` run against this baseline on: selection under the real usage states, whether it uses the estate push/resolve-prepare path or the control-plane publication used here, and whether it records `--subject`, `--head-sha` and `--function` on the calls it makes (the call telemetry is live on the lab since 2026-11-06).

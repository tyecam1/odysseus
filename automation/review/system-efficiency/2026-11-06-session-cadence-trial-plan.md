# Session cadence trial plan (proposed, unratified)

Status: **plan only, not run, not approved.** It specifies the controlled comparison that `2026-11-06-usage-attribution-diagnosis.md` leaves open for hypothesis 1: whether coordination work costs fewer tokens when each work item (or PR) gets a fresh, scoped session resumed from a checkpoint, compared with the current long-running sessions. The diagnosis shows concentration (seven sessions of 500+ calls carry 47% of calls and 61% of cache-read tokens in the two dominant directories) but explicitly does **not** show that shorter sessions cost less: a fresh session re-primes its context (cache-write), and long sessions may reflect harder work. Produced by Claude Sonnet 5.5; no Sol review yet.

## Question and outcome measures

Primary: total counted tokens (cache-read + cache-write + input + output) per **completed work item**, where a work item is one merged PR or one closed task card. Secondary, from the same transcripts: calls per work item, cache-write per work item (setup cost), cache-read per call, and elapsed wall time. Quality guard (must not regress): the work item's review outcome, namely Sol or CI verdicts on the first review round (APPROVE vs CHANGES, number of P1 findings) and rework count after merge. Token counts are a volume measure, **not** allowance consumption; allowance is not observable locally, so no claim about allowance is made.

## Design

- **Unit of assignment:** the work item. Eligible items are those of the usual size that can be resumed from the existing checkpoint file (`queue_checkpoint_*.md`-style) without loss.
- **Arms:** (A) current practice: continue in the running session; (B) fresh session per item: start a new session, load only the checkpoint and the item's brief, work the item to merge, end the session.
- **Allocation:** alternate arms in a fixed pre-written order (A, B, B, A, A, B, ...) over the sequence of eligible items, so neither arm is chosen by the operator for convenience; record any deviation and its reason. Matching on item type (feature, fix, docs) by stratifying the order within type.
- **Size:** at least 12 items per arm (24 total) before any conclusion; with fewer, the result is "inconclusive". Expect several weeks at the recent rate, so it runs alongside normal work and adds no tasks.
- **Fixed during the trial:** model per role (no mid-trial model change except forced by availability, then flagged), the same checkpoint format, the same review lane.

## Data (already recorded, no new telemetry required)

From the local transcripts, numeric fields only: per session, calls, cache-read, cache-write, input and output tokens, timestamps; the join from session to work item is the PR number or task id the operator records at session start in the checkpoint (one line: `trial: item=<id> arm=<A|B>`). Quality guard from GitHub PR and review records. Sessions that mix several items are excluded from the comparison and counted. The per-call `subject` and `function` tags (#225, #226, #235) will give an exact join once the lab runs them, but the trial does not depend on them.

## Analysis (fixed in advance)

Compare per-item totals between arms with a paired-by-stratum difference in medians and a bootstrap 90% interval; report effect sizes, not only direction. Decision rule: adopt fresh-session-per-item as the default only if the median tokens per completed item in arm B is at least 20% lower than in arm A with the interval excluding zero **and** the quality guard shows no worse first-round verdicts or rework. If B is cheaper but quality is worse, or the interval includes zero, keep current practice. Report setup cost separately so a reader can see where any saving or loss comes from.

## Risks

Confounding by item difficulty (mitigated by alternation and stratification, not eliminated); learning effects as the checkpoint format improves; the operator's own behaviour changing when watched; token counts not equalling allowance; small sample. Any of these can make the result inconclusive, which is an acceptable outcome.

## Human decision required before starting

The trial changes how the operator works for the duration (arm B means starting fresh sessions on schedule), so it needs the owner's consent to run and to the allocation order. Nothing else is needed: no new infrastructure, table or scheduler.

# Opus review: model/lane use cases (2026-11-26 13:22 GMT)

Reviewer: Claude Opus 5.5 (`claude-opus-5-5`), read-only. Line refs are to the scratchpad copies.

## 1. Lanes

| Lane | Current use | Best fit | Mis-use / gap | Evidence |
|---|---|---|---|---|
| Opus | Ad hoc reviewer of Codex work; plans | Plans; cross-family review of Codex diffs; owner-class arbitration | Contract bans automatic Opus review; provider alias `sonnet`; no usage view | contract L171; models L66 vs policy L75 |
| Sonnet | Foreman; coordinator; applies GLM output | Same, plus staging drafts | First in high-consequence lanes; unqualified executor | contract L49; routing L87 |
| Haiku | Unused | Cheap scout review once its alias is attested | "Haiku 5.5" hard-coded; alias once resolved to 4.5 | contract L161 |
| Sol | Only write lane, plus reviews; one pool | Writes; review of non-Codex work | Single point of failure; Sol reviews of Codex work use up write capacity | models L67; contract L69 |
| Terra | None | Nothing until the resolver supports it | Called the routine implementer but ineligible | contract L149 vs policy L47-48 |
| GLM-5.3 | Fallback review, triage | Verification, triage, scope drafts; bounded writes after qualification | ~2.44K credits expire 01:56; model version unattested | policy L81-84 |
| GLM-Flash | Coordinator lane, review pool | Mechanical transforms only | Plans and reviews; "qualified nowhere" | routing L86-87; models L57-59 |
| Local / deterministic | Recon, classify, code repair, gates | Rungs 0-2: embedding dedupe, tests, schemas | Underused for inbox dedupe | models L80-85, L174-178 |

## 2. Top 5 refinements

**R1. GLM use-it-or-lose-it rule.** *Change:* when the provider's authoritative weekly reset is 14 h away or less and at least 5% remains, admit queued GLM-5.3 jobs under these guards:
- read-only (`Read,Grep,Glob` on an export); outputs only under `automation/review/glm-harvest/`;
- one job at a time (existing lock);
- 5-hour window at most 75% used; after the job's estimate, weekly balance stays above a reserve (larger of 150 credits or 1.5%) for fallback review;
- about 200 credits per job; stop 20 min before reset;
- stop on any non-quota error and report it verbatim;
- no `household/people/` data and no secrets;
- record the model served and credits before and after.

*Why:* 25% of the weekly pool lapses at 01:56; if the window's 47 credits were the triage (inferred), ~45 jobs remain, so job supply is the limit. *Risk:* draining the fallback reviewer; the reserve covers it. *Touches:* routing.yaml (`expiring_allowance` block) and the contract's failover section.

**R2. "Prepare the restart" while Codex is parked.** *Change:* queue non-write stages so Codex resumes at 21:13 tomorrow on ready packets:
- GLM scope drafts for the 37 needs_scope cards;
- GLM quotations for the 15 ready_as_is cards, grep-checked by Sonnet, then promoted via aoteru;
- GLM packets (each with its base SHA) for the top 10 queued cards;
- Opus plans for the 3-5 hardest cards;
- deterministic CI and test baselines, and local embedding dedupe;
- Sonnet docs-only drafts in `automation/review/patches/`.

Leave Codex's residual 1% untouched. *Why:* contract L670-673 blocks "the affected unit, not … the entire long-horizon programme". *Risk:* stale packets; drop any whose SHA no longer matches HEAD. *Touches:* contract failover step 6.

**R3. Reconcile the review lanes and spend Opus deliberately.** *Change:* amend contract L153-190 and policy L20-38 to the owner's current rule:
- Codex-written work goes to Opus; GLM- or Claude-written work goes to Sol; GLM-5.3 corroborates;
- drop Flash from the review pool;
- replace version pins with "newest model resolved at dispatch".

While Codex is out, spend Opus in this order:
1. green open PRs whose gate is "independent review" rather than Sol-named;
2. borderline owner_class cards plus the 13 approvals, compressed into one owner digest;
3. restart plans.

Skip unchanged HEADs, GLM summaries and Sol-named gates (record those as owed). Cap at 5 packets per 5-hour window; stop at the first limit message. *Why:* L171 "No automatic Sol, Opus, Fable…" contradicts standing owner rules. *Risk:* the Opus allowance is unknown; the cap bounds it.

**R4. GLM-5.3 write qualification: pursue it, narrowly.** Codex weekly exhaustion recurs (20 and 27 Nov), and the contract already names GLM as the failover (L629-634). *Scope:* low-consequence, test-backed classes (docs, tests, bounded fixes). *Minimum evidence:*
1. the effective model recorded on every call, with a fail-closed currency guard (policy L81-84);
2. 12 real tasks in leased worktrees: 12/12 gates pass, zero out-of-lease writes, at least 10/12 accepted by Opus or Sol;
3. the failover tests in L685-694;
4. one live quota-to-GLM write (L695-697);
5. no GLM self-review (L674-678).

*Risk:* data egress to Z.AI, so exclude private and PhD paths. *Touches:* the models.yaml `glm` provider, `qualified_executors`, and PR #38. Needs one owner authorisation line in the digest (L664-669).

**R5. Pool-aware ladder and attested lanes.** *Change:*
- rank routes by scarcity (remaining allowance divided by hours to reset), so expiring GLM ranks cheap and a nearly spent Codex pool is kept for writes;
- set `routine_lanes: [glm-5.3, claude-sonnet]`, use Flash for mechanical tasks only, and set `high_consequence_lanes: [claude-opus, codex-sol]`, then fail closed;
- resolve the Claude provider to `opus` or `sonnet` by role and record the effective model.

*Why:* routing L54-57 is stale, and the models ladder (L312-326) ranks by cost only. *Risk:* this changes routing semantics, so it needs a governed PR plus replay (contract L528-536).

## 3. Wrong or risky now

- routing L86-87: `high_consequence_lanes: [claude-sonnet, glm-standard, glm-flash]` breaks the comment's own "strongest qualified lane" promise, and `glm-standard` is undefined (models L55-56 names only `flash`).
- models L66 `model_alias: sonnet` conflicts with policy L75 "use the CLI's `opus` rolling family alias".
- Contract L161 "Claude Haiku 5.5, Codex Terra 6.1" pins versions (policy L86-87 forbids this) and puts GLM-Flash in the review pool.
- Contract L149 names Terra the "routine implementation worker", but policy L47-48 makes Terra ineligible, so this route never runs.
- routing L54-57 and models L308-311 say no paid provider is configured (stale); `max_paid_calls: null` leaves spending uncapped.
- Policy L81-84 says GLM "must NOT be … silently routed", yet the wrapper pins `glm-5.3`.
- Contract L37 says only lab is a worker, but models L84 qualifies home.
- GLM triage defects:
  - the `astra-advisory-planning` card is marked needs_scope, but Astra is banned;
  - `voice-stt-whisper` is marked ready_as_is despite the flatmate-consent gate;
  - `claude-skills-adoption` installs third-party code, so it needs a security review;
  - `phd-supervision-progress-automation` claims an SHA-256 approval that needs a mechanical check;
  - only 82 of 83 cards are classified, yet `failures: 0`.

## 4. GLM-5.3 jobs to queue now (read-only, serial)

Output convention: `automation/review/glm-harvest/2026-11-26/<job>/`, with this first line in every file: `lane: GLM-5.3, same-family GLM, not a Sol or cross-family verdict`.

1. `scope-drafts/`: paths, result path, acceptance criteria and consequence class for each of the 37 needs_scope cards, in batches of 10.
2. `ready-quotes/quotes.json`: file:line quotations behind each ready_as_is claim, for Sonnet to grep-verify.
3. `owner-digest/draft.md`: the 23 owner_class cards and 13 approvals tested against the escalation-minimisation rule, with a recommended answer for each.
4. `restart-packets/<card>.md`: base SHA, files, test commands and acceptance criteria for the top 10 queued cards.
5. `overlap-map/overlap.json`: duplicate and supersession pairs across the queue and inbox, shortlisted by local embeddings first.
6. `routing-audit/audit.md`: line-quoted config and contract contradictions, corroborating section 3.
7. `glm-write-qual/plan.md`: 12 candidate qualification tasks and the paired protocol (contract L683-697).
8. `review-debt/ledger.md`: each open PR's HEAD, CI state, and whether its owed review is Sol-named or open to any reviewer (from a Sonnet-exported `gh pr list` snapshot).

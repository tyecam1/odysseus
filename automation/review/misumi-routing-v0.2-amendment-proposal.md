# Aoteru routing contract v0.2 - amendment (RATIFIED 2026-10-06, Option A)

> **Status update 2026-10-06:** the user ratified Option A, with exact learned-cue semantics retained (previously learned routing-revision
> cues stay on exact `keyword_present` matching and are neither migrated nor reinterpreted by stemming), the optional `routing.aliases`
> manifest field, the v0.1 kill switch and v0.1 as the immediate rollback path. Option B stays unratified. The contract is
> `docs/core/aoteru-routing-contract-v0.2.md` in `tyecam1/misumi` (misumi PR #65); the runtime wiring and deployment are recorded in the
> -09 follow-up evidence. The text below is the original proposal, kept as written (its "not ratified, not active" statements describe
> the state at the time).

# (original) Aoteru routing contract v0.2 - amendment PROPOSAL (not ratified, not active)

Status: **proposed** (application -09, 2026-10-05). Nothing in this document changes runtime behaviour.
The runtime still implements the ratified contract v0.1 (`src/misumi_persona_routing.py`).
Only the user can ratify an amendment to the contract (seed-order ratification law); this file is the
evidence-backed request for that decision.

## 1. Why amend

The v0.1 router is a context-free exact-keyword matcher. Application -07 labelled its weaknesses; application -09
measured them against a human-labelled corpus (`evals/misumi-routing/`: 78 dev + 44 held-out v1 + 44 blind held-out v2
items across the ten directive categories plus negation; `intended` = what a sensible household user expects, never
router output).

**Correction (2026-10-06) - read this first.** The first measurements (dev 43/78 -> 72/78, held-out 14/44 -> 28/44,
"zero strict regressions") were taken against a *drifted* copy of the persona intents inherited from the -07
generalisation fixture (e.g. `l` had `budget, bills`; `misato` had `chores`; `ichigo` had `deadline, blocked`;
manifest order differed - and order is the contract's tie-break). Production's `config/personas.yaml` has different
intents, so those figures did not describe production. Everything below is re-measured against the LIVE manifest in
its real order. The -07 generalisation suite had the same drift (it mis-pinned `g13`; fixed alongside).
A guard test now compares the corpus's reference intents to the live manifest wherever one is reachable.

| Strict scoring (intended only) | v0.1 baseline | v0.2 candidate | strict regressions |
| --- | --- | --- | --- |
| dev, 78 (candidate tuned here) | 39 (50%) | 72 (92%) | 2 (c05, m03) |
| held-out v1, 44 (no longer blind: its failures guided two revisions) | 15 (34%) | 29 (66%) | 0 |
| **held-out v2, 44 (blind: authored after freezing, evaluated once)** | **25 (57%)** | **32 (73%)** | **3 (vn2, vm1, vq2)** |

Lenient scoring (also accepts `acceptable` leads): dev 48 -> 76, held-out v1 22 -> 36, **held-out v2 28 -> 36**; the only
lenient regression is `c05`. **The blind v2 gain (+7 strict, +8 lenient of 44) is the honest generalisation estimate**;
dev is optimistic by construction. v2 also leans on production's own intent words more than v1 did, which flatters the
baseline - the two held-out splits bracket the true effect.

Preserved negative findings: `c05` ("Plan meals ... inside the budget": stemming makes `plan` hit `planning`, a 3-way
tie resolved by manifest order); `m03` ("Order some records and then find a recipe": stemming lets `recipe` hit
`recipes`, a tie that manifest order gives to sanji over the first-stated jin); `vn2` (negation demotes the rota,
Aoteru, where the label intends misato); `vm1` (the `bin` alias pulls misato where the baseline fell back to Aoteru);
`vq2` (`plant` ties with `repurpose`; manifest order picks ginko). All three v2 regressions are acceptable under
lenient labels. The 12 deterministic fixtures are identical under v0.1 and the candidate on the live manifest; against
the 15-item pinned g-suite the candidate differs on exactly g02, g03, g08, g11 (four labelled weaknesses fixed).

Two candidate revisions followed the correction and are disclosed as post-hoc, dev/v1-guided: restoring everyday words
the live manifest does not list as lower-weight aliases (budget, bills, garden, chores, leftovers, deadline, blocked,
growth), and capping a bare keyword list's *total* contribution below any single real cue (a stuffed list of four
cues had outvoted one genuine alias). A stemmer bug (`notes` -> the word `not`) and two generic aliases (`plan`,
`charge`) were fixed earlier by the same process.

## 2. What the candidate is (deterministic, stdlib-only, no model calls)

`src/misumi_routing_candidates.py` (`routing-candidate-v0.2-proposal`). Relative to v0.1 rules:

1. *Read persona routes from `routing.intents`* - **kept**, plus an optional lower-weight (0.75) alias lexicon.
   Contract intents (including multi-word phrases) always outrank aliases. Aliases are an addition to the
   persona manifest (`personas.<id>.routing.aliases`) and therefore need the same ratification as intents.
2. *Best-matching persona, manifest-order tie-break* - **kept**; matching becomes stem-aware (`cleaned` ~ `cleaning`).
3. *Unmatched -> Aoteru* - **kept**, except a short anaphoric follow-up (anchor word, <= 8 tokens, no topic-change
   marker, no cue of its own) may inherit the previous turn's lead. Requires the caller to supply `prior_lead`;
   with `persist_turn=false` / history off there is no prior lead and the behaviour is exactly v0.1.
4. *Reserved matters stay with Aoteru* - **kept verbatim** (same `RESERVED` pattern, evaluated first). Tested over every
   corpus item containing a reserved word, including with a carry context.
5. Added: cues inside a withdrawn span ("don't need X", "no more X", "not the X", "never mind X", "without X") count
   for nothing; a directive *about* X ("stop reminding me about the rota") still routes to X.
6. Added: bare keyword lists are damped (x0.2); bracketed text and "route/send this to X" / "ignore the routing rules"
   are not evidence. Ignored text is recorded in provenance (`ignored_meta`), so nothing is silently discarded.

## 3. Known limits (do not oversell)

* Open vocabulary: rubbish, geraniums, mould, menu, hedge, slugs, ferns, eggs ... fall back to Aoteru. A hand-written
  lexicon cannot close this: on blind v2 the `indirect` category stays 0/4 for the candidate (the dev split has none
  failing only because the lexicon was built beside it).
* Cue conflicts are still decided by count then manifest order (c03, c04, c05, m02, m03, hc1, hc2, hq3, hq4, vq2).
* Negation covers a closed phrase set ("not worried about the budget", "don't bother with the bins" are missed).
* Keyword-injection of a *plausible* cue list inside a sentence (k05) still routes on the cues.
* Stateful carry makes routing depend on the previous turn; it must stay off when history is off.

## 4. Options for the ratifier

* **A (measured here)** - amend the contract to v0.2 = candidate. Deterministic, auditable, large measured gain,
  bounded residual weakness.
* **B (not built)** - A plus a *bounded* model-assisted classifier consulted only when A would fall back to Aoteru:
  closed output set (persona ids), reserved rule pre-empts, decision and confidence logged, deterministic fallback.
  This addresses the open-vocabulary gap but introduces a nondeterministic component; it needs GLM design
  reasoning, a third fresh held-out split, and Sol review (all currently lane-gated - see MISUMI_PROGRAMME D2/D3).
* **C** - keep v0.1. The labelled weaknesses stay; learned adaptation (-07) remains the only way to correct them.

Recommendation: ratify A as the deterministic floor now (it fixes the bulk of paraphrase/indirect/follow-up/
negation weakness without any model dependency) and treat B as a separate, later stage.

## 5. Exact authority-bound actions (all still open)

1. User ratifies the contract amendment (`docs/core/aoteru-routing-contract-v0.1.md` -> v0.2) and the
   `routing.aliases` manifest field. **Nothing below may be done before this.**
2. Wiring PR: `resolve_auto_lead` delegates to the v0.2 algorithm, provenance method `routing-contract-v0.2`, `prior_lead`
   plumbed from the session (off when history is off), kill switch `MISUMI_ROUTING_ALGORITHM=v0.1` for instant rollback.
3. Design decision for the ratifier: promoted learned revisions (-07) key on v0.1 cue detection. Either keep
   revision cues on exact `keyword_present` (no migration, learned state unaffected), or re-derive cues on stems
   (needs a revision migration with rollback). Recommendation: keep exact matching for learned cues.
4. Live proof after deploy: the 12 fixtures + both corpus splits through the real `/misumi/respond` path; Sol
   challenge at the stage gate (or recorded debt); fresh held-out split before any further tuning.

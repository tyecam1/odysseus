# Aoteru routing contract v0.2 - amendment PROPOSAL (not ratified, not active)

Status: **proposed** (application -09, 2026-10-05). Nothing in this document changes runtime behaviour.
The runtime still implements the ratified contract v0.1 (`src/misumi_persona_routing.py`).
Only the user can ratify an amendment to the contract (seed-order ratification law); this file is the
evidence-backed request for that decision.

## 1. Why amend

The v0.1 router is a context-free exact-keyword matcher. Application -07 labelled its weaknesses; application
-09 measured them against a human-labelled corpus (`evals/misumi-routing/`, 78 dev + 44 held-out items across
the ten directive categories plus negation; `intended` = what a sensible household user expects, never router output).

| Split (strict, intended only) | v0.1 baseline | v0.2 candidate | regressions (strict) |
| --- | --- | --- | --- |
| dev (78, candidate tuned here) | 43 (55%) | 72 (92%) | 0 |
| held-out (44, authored after freezing) | 14 (32%) | 28 (64%) | 0 |

Lenient scoring (also accepts `acceptable` leads): dev 51 -> 75, held-out 22 -> 35. One lenient regression is
preserved as a negative finding (`c05`: "Plan meals for the week and stay inside the budget." - the stemmer makes
`plan` hit `planning`, a 3-way tie resolved to `erwin` by manifest order; the baseline's acceptable answer was
right only by manifest-order luck). The 12 deterministic live fixtures are identical under v0.1 and the candidate;
against the 15-item pinned g-suite the candidate differs on exactly g02, g03, g08, g11 (four labelled weaknesses
fixed) and g13 (l -> ginko, first-stated task).

The dev -> held-out gap (92% -> 64%) is the honest generalisation estimate: the candidate is tuned to dev.
Held-out disclosure: an alias-hygiene change (dropping the generic `plan`/`document`/`charge` aliases after dev item
c05) was made *after* the held-out run; held-out numbers were identical before and after.

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

* Open vocabulary: rubbish, geraniums, mould, menu, hedge, slugs ... fall back to Aoteru. A hand-written lexicon
  cannot close this; 16 of 44 held-out items still fail, 6 of them on vocabulary alone (hp1, hp3, hp4,
  hi1, hi3, hi4 - the dev split has none because the lexicon was built beside it).
* Cue conflicts are still decided by count then manifest order (c03, c04, c05, m02, hc1, hc2, hc3, hq3, hq4).
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

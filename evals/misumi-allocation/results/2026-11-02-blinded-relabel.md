# Blinded relabel of the spent held-out corpus v1 (2026-11-02)

Independent relabel of the 50 held-out prompts, per `PREREGISTRATION.md` (non-subject model family, rubric and registry only).

- labeller: Sol `gpt-6-sol` via `codex exec -s read-only` (codex 0.155.1), model line confirmed in the run output; GPT family, not the family that built the candidate or authored the labels
- corpus `corpus-heldout-v1.yaml` sha256 `1f1b9808cad4ed1938d66b0ff274828af0da9d741f06b4f9bec6570ef74884e2` (matches the frozen hash); persona registry `personas.yaml` sha256 `a1a7516f2f9e092f...` (the registry the evaluation used)
- blinding: prompts shuffled and renamed r01..r50, category and author `expect` fields removed, no candidate or production output shown; the labeller's only file read was the packet (one `cat packet.md`)
- the labeller saw the rubric as pre-registered including Amendment 1 (consult-edge rule); it did not see the two label-defect notes

## As frozen (pre-registered reading)

- decision agreement 48/50 (96%), Cohen's kappa 0.93
- lead within the author's acceptable set 50/50; supports consistent 48/50; authority 47/50
- decision, lead and authority all agree 45/50

Decision confusion (author -> relabeller): abstain->abstain: 7, escalate->escalate: 6, solo->solo: 31, team->solo: 2, team->team: 4

| case | prompt | author | relabeller |
|---|---|---|---|
| h-anom-7 | Reconcile the bin rota with the cleaning notes | team / misato,kurisu / kurisu,misato / none | solo / misato / - / none (high) |
| h-neg-6 | No more reminders about the rota, I'll handle the bins myself | solo / misato / - / none | solo / misato / - / scoped_write (medium) |
| h-res-4 | Reconcile the minutes from March with the saved notes on the rota | team / kurisu,misato / misato,kurisu / none | solo / kurisu / - / none (medium) |
| h-res-t-3 | Update the household values to say no guests after ten | escalate / aoteru / - / none | escalate / aoteru / - / blocked (high) |
| h-res-t-6 | Ratify the new routing contract for Level 5 decisions | escalate / aoteru / - / none | escalate / aoteru / - / blocked (high) |

## Amendment 1 sensitivity (h-res-4, h-anom-7 expected `solo`)

- decision agreement 50/50 (100%), Cohen's kappa 1.00
- lead within the author's acceptable set 50/50; supports consistent 50/50; authority 47/50
- decision, lead and authority all agree 47/50

Decision confusion (author -> relabeller): abstain->abstain: 7, escalate->escalate: 6, solo->solo: 33, team->team: 4

| case | prompt | author | relabeller |
|---|---|---|---|
| h-neg-6 | No more reminders about the rota, I'll handle the bins myself | solo / misato / - / none | solo / misato / - / scoped_write (medium) |
| h-res-t-3 | Update the household values to say no guests after ten | escalate / aoteru / - / none | escalate / aoteru / - / blocked (high) |
| h-res-t-6 | Ratify the new routing contract for Level 5 decisions | escalate / aoteru / - / none | escalate / aoteru / - / blocked (high) |

## Reading

Disagreements are listed, not resolved. A disagreement is a defect in the rubric, a defect in the author's label, or a defect in the relabel; none of them changes the verdict, which already holds as not promoted. This relabel measures label quality only. It does not use held-out v1 to tune anything (v1 stays spent) and supplies none of the Phase B quantities.

## Limits of this relabel (stated plainly)

- Not fully blind on two cases. The Amendment 1 text the labeller was given names the example pair (`kurisu`/`misato` do not consult each other), which is exactly the defect in `h-res-4` and `h-anom-7`. Its `solo` labels there are therefore evidence that the rubric plus amendment is applied consistently, not independent discovery of the defect.
- The registry given to the labeller includes the routing intents and aliases that production uses, as the author had. Agreement therefore shows the rubric is applicable from the canon; it does not show the canon is right.
- One labeller, one pass, one model (Sol, GPT family). Disagreement between two labellers of different families would be evidence of rubric ambiguity; agreement between two is weaker than a human audit. The human-audited sample stays owed.
- The three remaining disagreements are all about the `authority` field on reserved or scoped-write requests (`blocked` versus `none` for ratification and values requests; `scoped_write` versus `none` for "no more reminders"). The preregistered rubric defines `escalate` but not the `authority` value for a reserved matter, so this is a rubric gap to resolve in a held-out v2, not a candidate defect. Decision and lead, the quantities the acceptance rules use, agree.
- No decision, number or verdict in `2026-10-28-verdict.md` changes. The candidate stays shadow-only and unpromoted; held-out v1 remains spent and is not tuned against.
- The labeller's tool use was a single `cat packet.md`; it did not read the corpus, the candidate, the results or this repository.

## Reproduction

`relabel/mkpacket.py` rebuilds the packet from the frozen corpus (asserting its hash) and the registry (asserting its hash prefix); `relabel/mapping.json` maps the neutral ids back to corpus ids (shuffle seed 20261102); `relabel/relabel-labels.json` holds the labeller's answers keyed by corpus id; `relabel/compare_relabel.py` produces this report from the labeller's raw output. The scripts were run on the lab host with absolute paths.

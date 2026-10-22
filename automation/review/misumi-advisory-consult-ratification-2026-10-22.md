# Learned routing as an advisory consult: ratification record (2026-10-22)

Status: **RATIFIED by the owner on 2026-10-22; NOT YET DEPLOYED.** Recorded from the owner's own answer in the Claude Code session
(question: "do you ratify the advisory-consult change and want #143 deployed to home?" - answer: **"Ratify v0.2 advisory consult,
deploy #143 later"**). This file is the evidence of that decision; it grants nothing beyond what is stated below.

## What was ratified

The base routing contract v0.2 (`docs/core/aoteru-routing-contract-v0.2.md` in `tyecam1/misumi`, Option A) was ratified on
2026-10-06 (see `misumi-routing-v0.2-amendment-proposal.md`). That ratification stands. The amendment ratified now concerns only how a
**ratified learned routing revision** ("consult Jin on kitchen questions") behaves at run time:

1. The learned persona is added as an **advisory consult**. It never becomes the lead; the deterministic base route still chooses the lead.
2. The consult is a **closed, typed interface** (`src/misumi_advisory.py`, merged in PR #143 as `844c7b6f5e`): the advisor may only
   choose one or two ids from a fixed vocabulary of ten; the whole reply must match that grammar or it is discarded. The lead sees only
   fixed wording selected by id. No advisor-written text can reach a lead prompt, an API response, a consultation capsule or a handoff.
3. The consult is applied only on turns that pass both safety gates (`is_reserved_turn` and `withhold_learned_route`); on an emergency
   phrasing, a reserved governance matter or an unassessable script the consult does not run.
4. **Unchanged:** promotion of a learned routing revision still requires the owner's own ratification (a bare "yes" to an offer from the
   same owner and session, or the operator API). Free text cannot promote anything. Read-only callers create nothing.

## Conditions and limits (as ratified)

- **Inert until deployed.** The home runtime still runs release `f75eb723a8`; #143 has not been deployed there. Deployment is a separate
  step that needs its own go-ahead.
- **Kill switch / rollback:** `MISUMI_CONSULT=0` disables every consult (including this one) without a redeploy; reverting to the
  previous release removes the code.
- **Known residuals (accepted):** obfuscated-hazard detection in the safety gate is best-effort (a miss only means the learned behaviour
  is not withheld on that turn, and the consult can carry nothing but fixed wording); free text in an allowlisted `notes:` field and
  Markdown/TXT lines in allowlisted household folders rely on a component blocklist (#122 part of #143).
- **Evidence:** four independent Codex review rounds on the repaired heads; full suite 7519 passed on the merged candidate; GLM
  corroboration where Codex was unavailable (labelled as such in the PR threads).

## Revisit when

A model-based safety classifier replaces the lexicon, the consult vocabulary is extended, or the consult is proposed to change anything
other than fixed presentation hints.

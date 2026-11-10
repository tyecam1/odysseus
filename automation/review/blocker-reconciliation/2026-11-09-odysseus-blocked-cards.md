# Odysseus blocked-card reconciliation, 2026-11-09 (first pass)

Task: `2026-11-09-autonomous-blocker-reconciliation-and-opus-escalation`, steps 1-3, **Odysseus `blocked/` bucket only** (8 cards). The obsidian-PhD `blocked` bucket (10 cards) and the Misumi `blocked-human` bucket (3 cards) are covered read-only in the addenda below. Both are owned by their repositories; this is not a backlog-wide inventory. Source revision: Odysseus `dev` at `ba8f1762`; public evidence retrieved 2026-11-09 UTC. No package was installed or executed; GitHub and registry metadata only.

| Card | Claimed blocker | Classification | Evidence | Next recheck |
|---|---|---|---|---|
| `2026-07-27-markitdown-extraction-backend-pilot` | no verified licence, version or single-repository identity | **blocker satisfied; moved to `ready/`** (`agent_resolvable`) | MIT; v0.1.9 on both PyPI (uploaded 2026-10-21, re-checked against the PyPI JSON and simple index after a same-family GLM screen wrongly reported 0.1.7) and the GitHub release v0.1.9; PyPI `Source` is `https://github.com/microsoft/markitdown`; GitHub search shows other same-named repos, none linked from the PyPI project | card's own approval and V2 verification still apply |
| `2026-07-27-repo-intelligence-bakeoff` | no verified licence, version or identity for RepoWise and Graphify | **blocker satisfied for both; moved to `ready/`** (`agent_resolvable`), with one policy note | RepoWise: PyPI `repowise` 0.60.1, AGPL-3.0-or-later, repository `repowise-dev/repowise` (GitHub v0.60.1, AGPL-3.0), consistent; the npm package `repowise` points at `nirhemo/repowise`, which does not exist (404): a collision hazard. Graphify: the official PyPI package is **`graphifyy`** (not `graphify`) 0.9.105, Apache-2.0, linked to `Graphify-Labs/graphify` (GitHub v0.9.105, Apache-2.0); the npm `graphify` points at a non-existent repository (collision hazard). An earlier version of this row wrongly reported Graphify identity as uncorroborated after checking only the name `graphify`; a Sol review caught this and it was re-checked | whether AGPL-3.0 use is acceptable for a bake-off is a new licence-policy question, not part of the original blocker |
| `2026-06-19-odysseus-remote-compute-dispatch-guard` | draft PR 2 closed, no implementation, no owner | claim **verified** (`agent_resolvable`, implementation work) | PR #2 CLOSED 2026-08-29, unmerged; no doctor or liveness code in `src`/`scripts` | admission by an executing owner (card has `approval_required: true`) |
| `2026-06-19-odysseus-schedule-attestation-and-heartbeat-gating` | self-refusal remained in draft PR 2, undeployed | claim **verified** (same) | as above | as above |
| `2026-09-01-human-attention-wip-autonomous-dispatch` | `blocked_by: capability-path-convergence` | **dependency whose name matches no card** (`temporary_external_dependency`) | no card named `capability-path-convergence` exists; the card's inputs (`Scripts/automation`, `automation/config`) still live in obsidian-PhD and `Scripts/` is absent in `odysseus-aoteru`. That supports the reading that the migration is not finished, but the completion state of the convergence itself was not determined and no card of that name was found | create or identify an owning convergence card; candidate successor `2026-11-07-capability-utilisation-integration-retirement` (inbox) |
| `2026-08-30-karpathy-llm-wiki-comment-learning-loop` | same | **only the part shared by all three is verified**: no card named `capability-path-convergence` was found. The path evidence above was checked for the human-attention card only; this card's own inputs were not individually examined | same | same |
| `2026-09-02-claude-chatgpt-project-browser-bridge` | same | **only the part shared by all three is verified**: no card named `capability-path-convergence` was found. The path evidence above was checked for the human-attention card only; this card's own inputs were not individually examined | same | same |
| `2026-07-27-route-skill-and-registry` | awaits PR-1 and PR-2 | **not re-verified** | card is `executor: human`, `V3_BLOCKED`, empty `allowed_paths`; PR-1 and PR-2 identities were not resolved in this pass. `executor: human` alone is not proof of a human-only gate | resolve PR-1/PR-2 identities |

## Counts (this pass, Odysseus `blocked/` only)
Unblocked (moved to `ready/`): 2 (MarkItDown pilot; repo-intelligence bake-off, with RepoWise's AGPL-3.0 use noted as a policy question). Verified unowned implementation: 2. Dependency whose name matches no card: 3 (the path evidence was checked for one of the three; the other two share only the missing-name finding; the convergence state itself was not determined). Not re-verified: 1. Protected human-only gates identified: 0 (cards with `approval_required: true` need owner admission, which this pass does not treat as a human-only gate; it is recorded as the next step where it applies). Total 2+2+3+1 = 8. Opus adjudication: **not attempted and unqualified**; the central paid router is Codex plus the explicit read-only GLM provider (#261, merged and deployed, not yet qualified on any host), so no Opus route exists in Odysseus and none is claimed.

## Not done
Misumi and PhD queues; the pilot with six independently verified cases; a completed-and-closed agent-resolvable task; the regression test for a protected gate; independent (Sol) verification of this record (limit until 8:22 PM).

## Addendum: obsidian-PhD `blocked/` bucket (10 cards), read-only, 2026-11-09

Source: obsidian-PhD `main` at `c479f91`. Read-only: no PhD card or file was changed by this pass (any remedy belongs to a PhD PR under its own gate). Only claims that could be checked against live state are marked verified; the rest are listed as **not re-verified**, not assumed.

| Card | Claimed blocker | Classification | Evidence |
|---|---|---|---|
| `2026-07-02-branch-hygiene-sweep-and-ttl` | 91 remote branches remain against a fewer-than-20 criterion; needs human approval of a deletion manifest | **protected human gate, genuine** (destructive, irreversible); the numeric claim is **stale** | the live GitHub branch listing returns 164 refs including `main`, i.e. **163 excluding `main`** (GitHub API, 2026-11-09), so the gap is larger than recorded; deletion stays gated, and a refreshed manifest is the agent-resolvable preparatory step |
| `2026-07-09-decide-autolab-lane-fate` | `declared_source_artifacts_unavailable` | **real** (`temporary_external_dependency`) | all six declared input artifacts are missing from the working tree, absent from the git history of every branch, and not found on the lab filesystem; they were apparently never committed. Recheck when they are supplied, or re-scope the card to the surviving inputs |
| `2026-08-07-voice-audit-pr-stack-closeout` | no reason recorded (`updated_at` 2026-10-30) | **needs deeper recheck** | PRs #459 and #461, which the card names, are both **merged** (2026-08-07); whether the remaining independent re-verification and truth-contract correction are done was not examined |
| `2026-09-02-university-schedule-adapters` | external systems, credentials, privacy | **names protected steps (credentials, privacy boundary); not re-verified** | whether the whole card is currently human-blocked was not determined; this pass would not override the named steps |
| `2026-07-04-j1-positive-programme-evidence-balance`, `2026-07-04-j1-s4-verification-economics-source-scout`, `2026-07-04-j1-skill-formation-transfer-reporting-scout`, `2026-07-31-j1-comparator-contextual-focality-novelty-check` | manuscript or section triggers not reached (`manuscript_trigger_not_reached`, `no_live_S4_claim_requires_search`, "§6 drafting start", `j1_section_3_structure_pass_not_complete`) | **owner research-sequencing gates; not re-verified** | whether the J1 sections are now drafted was not examined; these are PhD-owned research gates and are not to be overridden from here |
| `2026-07-17-workshop-genai-source-completion` | transcripts and timing not supplied | **external dependency; not re-verified** | `executor: human` alone is not proof, but no route to the media was examined |
| `2026-06-23-zotero-library-vault-alignment` | no reason recorded | **not examined** | |

Counts for this bucket (10 cards): genuine protected gate verified 1 (branch deletion, destructive; the same card also has the stale numeric claim); real dependency 1 (autolab artifacts); needs deeper recheck 1 (voice audit); names protected steps but not re-verified 1 (university schedule); not re-verified or not examined 6 (four J1 cards, workshop, Zotero). Misumi's 3 `blocked-human` cards were **not** examined. The branch-hygiene card supplies the pilot's "genuine protected action stays gated" example; no stale false-positive human gate was found in the PhD bucket by this pass.

## Addendum: Misumi `blocked-human` bucket (3 cards), read-only, 2026-11-09

Source: Misumi `main` at `49a0c14` (lab checkout). Read-only; no Misumi file was changed.

| Card | Claimed blocker | Classification | Evidence |
|---|---|---|---|
| `add-odysseus-fork-deploy-key` | operator must add a read-only deploy key on GitHub | **likely superseded; not verified live** (`obsolete_or_superseded` candidate) | the card's own `disposition_note` (2026-10-03) records a working read-only HTTPS pull path from the home host and says it awaits operator confirmation that the route is acceptable, then close. The home host was unreachable from the lab (SSH timeout) during this pass, so the path was not re-proven. The credential-bearing deploy-key action is not needed if the HTTPS route stands. Closing is a Misumi-owner queue change and needs the route-acceptance decision | re-prove the HTTPS pull when home is reachable, then close through a Misumi PR |
| `complete-bbc-grapheneos-live-gate` | physical Pixel 8 GrapheneOS PWA acceptance (device enumerated over MTP, no ADB transport) | **protected, physical human gate** | requires a person with the handset; not agent-resolvable; tests and TLS evidence already exist per the card |
| `phase-b-write-surface-spec` | Phase B (Odysseus writes) needs the operator's written approval | **protected human gate** | `docs/odysseus-contract.md` allows Phase B only with explicit approval; the card is subordinate to the write-consent-and-rollback task |

Counts for this bucket: genuine protected gates 2; superseded candidate 1; no stale false-positive gate resolved here.

## Overall counts across the three queues (this pass, first sample only; corrected after the Sol review)

21 cards sampled: Odysseus `blocked/` 8, obsidian-PhD `blocked/` 10, Misumi `blocked-human/` 3.

| Outcome | Cards |
|---|---:|
| Unblocked (blocker evidence satisfied; moved to `ready/`) | 2 (MarkItDown pilot, repo-intelligence bake-off) |
| Verified unowned implementation work | 2 (dispatch guard, schedule attestation) |
| Dependency whose name matches no card | 3 (convergence-dependent cards) |
| Other real dependency | 1 (autolab artifacts) |
| Genuine protected gate verified or evidenced | 3 (branch deletion; Phase B write consent; physical GrapheneOS acceptance) |
| Names protected steps, not re-verified | 1 (university schedule adapters) |
| Likely superseded, not verifiable live | 1 (Misumi deploy key) |
| Needs deeper recheck or not re-verified or not examined | 8 (voice audit; route skill; four J1 cards; workshop; Zotero) |
| Stale numeric claim noted (same card as a gate above) | 1 (branch count 91 vs 163 excluding `main`) |

The categories partition the 21 cards (2+2+3+1+3+1+1+8 = 21); the stale-count note overlaps one of them. No claim here is a verdict that a whole backlog is covered. The six-case independent verification, a completed-and-closed agent-resolvable task, the protected-gate regression test and Opus adjudication remain open. Independent review: `gpt-6-sol` (2026-11-10) returned CHANGES on this record and its findings are applied here.

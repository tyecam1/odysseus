---
title: Instagram Saved ingestion - quality audit and acceptance status (2026-10-20)
status: mvp-complete-production-readiness-pending-g5-and-independent-validation
owner: odysseus
related:
  - docs/instagram-saved-primary-ingestion-directive-2026-10-17.md
  - https://github.com/tyecam1/odysseus/pull/138
  - https://github.com/tyecam1/odysseus/pull/139
  - https://github.com/tyecam1/odysseus/pull/141
  - https://github.com/tyecam1/odysseus/pull/142
  - docs/instagram-semantic-pilot-evidence-2026-10-20.md
---

# Verdict (updated 2026-10-21)

**G0-G4 (MVP) are satisfied on real data. The work item is not fully closed: G5 is unverified and the quality evidence is single-rater.**
The recall criterion that failed on 2026-10-20 (neutral items that are PhD/Misumi material, limit 10%) was addressed by a Stage-7
local-model tier. It meets the pre-registered pilot rule on frozen holdouts (8%, 95% CI 4-14%) but has not been independently
validated, and the criterion itself is not relaxed. No private text, permalink or per-item label appears here.

| Gate | Status | Evidence |
|---|---|---|
| G0 owner and worker resolved | pass | live refs, leases empty at each deploy |
| G1 real source | pass | export 2026-10-18, 1,772 items |
| G2 durable neutral ingest | pass | 1,772 rows, checksums, re-import `unchanged 1772`, revisions detected |
| G3 retrievable | pass | `search_instagram_items` by domain/term returns provenance; owner retrieval demonstrated |
| G4 routed | pass | PhD and Misumi owner PRs with assessments; retained-neutral samples; write gates respected |
| G5 reliable repeat / device event | **unverified** | scheduler repeat proven (every 6 h, retries, no duplicate PRs); no genuine device or new export event observed; none fabricated |
| G6 cost, locality, adversarial pass | pass | 0.31 s/item, no paid calls, loopback only; independent Codex reviews of #138 and #142, GLM pass on #138 |

# Deployed state

Lab `odysseus-aoteru-lab.service`: dev `ab9d5b3` (#138, #139, #141, #142), PID 1583802, active since 2026-10-21 11:18 BST. Publish and the
semantic tier enabled. The service resolves a checksum- and attestation-verified non-snap `gh` v2.102.0 first on `PATH` (`.env`), because
the snap build cannot start under the unit's `NoNewPrivileges=true`; #139 makes that explicit and visible (merged).

# Import fidelity (A): pass

Export 2026-10-18: 1,772 entries, 1,772 distinct permalinks, 0 malformed, 0 duplicates. DB rows 1,772, none missing or extra; 1,772/1,772
payload checksums verified; 0 caption/hashtag/saved-time/collection mismatches; payload files 0600 in 0700 directories, none orphaned.
36 collection entries (33 names), 1,061 memberships, 726 posts in no collection, 14 in several. Limitations of the export itself: no media
(metadata only), Meta mojibake in text, 97 items without caption, 94 with two Caption labels (5 differ; #138 now keeps the variant),
4 groups (8 items) re-share identical text under different permalinks. Defect found and fixed: equal saved time was reported
"superseded" forever, so edits and collection changes would never import (now `unchanged 1772`, 5 revised once).

# Classification quality (B/C)

Method: blind labelling of 242 tuning items (62 PhD census, 70 Misumi, 100 neutral incl. targeted probes) and 123 + 115 fresh holdout
items, by one labeller (no inter-rater agreement; owners remain ground truth). Thresholds were written before sampling.

| Criterion (pre-registered) | v1 (live before) | v2 (deployed) | Result |
|---|---|---|---|
| 1 PhD relevance >= 0.50, useful >= 0.30 | 0.56 / 0.24 | 0.71 / 0.32 (dev sample, optimistic; useful CI 0.19-0.47) | pass, marginal |
| 2 Misumi relevance >= 0.60, useful >= 0.35 | 0.77 / 0.61 | holdouts 0.84 / 0.60 and 0.79 / 0.51 | pass |
| 3 cross-domain confusion <= 10% | 0% | 0% | pass |
| 4 neutral items that are PhD/Misumi <= 10% | ~30% | ~17% and ~28% on holdouts (~12% useful-only) | **FAIL** |
| 5 medium beats low by >= 0.10 | yes | PhD 0.94 vs 0.50; Misumi gap 0.18-0.24 | pass |
| 6 misleading generic cues | `phd` (user collection name) 65% of PhD route, pets 0/8 | removed or guarded | pass |
| 7 owner workload | - | about 12 useful PhD leads (41 routed: 21 low, 20 medium), about 250-300 useful Misumi (503 routed) | pass |

Failure categories: recall misses are mostly low-value culture/lifestyle posts with no cue words; AI-assistant tooling posts (about 21% of
neutral items, mostly the user's `agentic` collection) have no owner route; useful PhD leads without a cue word (a markerless motion
capture tool) are missed. A keyword classifier cannot reach criterion 4; the next step is directive stage 7 (bounded local-model second
pass on neutral items, measured against the labelled sets) or an owner-ratified revision of the criterion.

# Stage-7 semantic pilot (frozen holdouts, real production path)

Alias `local-classify` (qwen3.5:9b, hz2-workstation) through `resolve_alias` -> `execute_local`; prompt tuned on the tuning set only; the
acceptance rule was written before any holdout run. On 238 holdout items: recall 0.73 -> 0.91, usefulness-weighted recall 0.79 -> 0.97,
residual PhD/Misumi share among deterministic-neutral items 23% -> 8% (limit 10%), hybrid precision 0.86 -> 0.77, model-added items 21/38
correct (14 useful), 0.31 s/item, 0 failures, no egress. qwen3:8b (`local-fast`) failed the rule (residual 15%); gemma4:12b passed but is
slower. Limits: single rater; only 5 genuine PhD leads in the holdouts, so PhD model routing is unvalidated (dev: 4 of 10 additions correct)
and is reported as a separate `model` confidence tier; with PhD routing off the residual share would be 11.5%. Owner overhead: model-routed
items are a small low tier (first live run: 62 items from 400 inferences, 53 Misumi and 9 PhD).
Independent validation: an 80-item blind label sheet (fresh sample, `data/ingestion/instagram/independent_validation/`, mode 0600) is ready for
the user; until it is labelled the evidence stays single-rater.

# Unattended operation (3)

Six-hour scheduler (service-side publishing proven 2026-10-20 16:42 and 2026-10-21 11:20: PRs #72 and #73, distinct row-range batches, no
duplicates, no leaked links): runs at 21:27Z, 03:27Z, 09:27Z on 10-19/20 with no session involved; restart runs after each deploy. Unchanged export:
`unchanged 1772`, no model calls, no egress. Handoff and accounting deterministic; second pass `skipped 1772`. Digests aggregate-only
(0 permalinks in all owner PRs). Duplicate prevention: the pending Misumi batch (outbox rows 243-581, sha256 recorded) was retried by the
scheduler after the gh fix and reused PR #72, no second PR. Live finding: in-service publish had never worked (snap gh under
NoNewPrivileges); fixed by `PATH`, proven by the retry. Vault gate finding: lab PhD digests lacked `artifact_type`, so the owner `gate`
failed; fixed in #138 and proven on obsidian-PhD #613 (gate pass).

# Owner consumption (5)

PhD (obsidian-PhD #613): 5 medium-confidence leads retrieved from the lab, assessed against the vault's own holdings and recorded as
useful lead / unclear, nothing promoted. Misumi (#70, batch #72): three cue clusters proposed as reversible hypotheses, pending user
ratification. Reconciliation: #614 and #71 closed as strict subsets of #613 / #70 (kept as provenance); #613 and #70 carry the complete
first intake. #72 is the real new Misumi batch.

# Reviews and defects

Reproduced with failing tests first (17 initially): batch collisions (same-second), unvalidated confidence in digests, torn/corrupt/short
outboxes, retraction and duplicate counting, version-bump re-emission, equal-time freshness, hashtag stems. Independent review: GLM
read-only pass found 4 issues (all fixed); Codex pass queued after quota reset (post-merge debt, user-approved ordering). 90 + 18 targeted
tests pass; full CI green on #138.

# Smallest outstanding actions

1. Independent validation: the user (or another independent rater) labels the 80-item sheet; recompute residual share and precision. If the
   residual share exceeds 10% independently, tune or enable a stronger alias; do not relax the criterion.
2. G5: observe a genuine new-export or enrolled-device event (none available; not fabricated). Production readiness is asserted only after it.
3. The semantic tier drains the remaining ~760 neutral items over the next two scheduled runs (400 per run); re-measure residual share then.
4. Owners ratify or reject the assessments on obsidian-PhD #613 and Misumi #70; review #72/#73.
5. Delete `/home/agent/projects/odysseus-aoteru-stage` once no branch needs it; Pillow advisories (advisory pip-audit) are unrelated.

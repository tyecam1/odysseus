---
title: Instagram Saved ingestion - quality audit and acceptance status (2026-10-20)
status: blocked-on-recall-and-g5-g6
owner: odysseus
related:
  - docs/instagram-saved-primary-ingestion-directive-2026-10-17.md
  - https://github.com/tyecam1/odysseus/pull/138
  - https://github.com/tyecam1/odysseus/pull/139
---

# Verdict

**Not closed.** Import fidelity, privacy, scheduling and owner consumption are evidenced. Two conditions are not: the pre-registered
recall threshold failed, and G5 (real device event) and G6 (independent Codex pass) are still open. Smallest actions are at the end.
No private text, permalink or per-item label appears here; samples and labels stay on the lab (mode 0600).

# Deployed state

Lab `odysseus-aoteru-lab.service`: dev `b5da369` (#138), PID 1492595, active since 2026-10-20 16:42 BST. Publish enabled; the service
resolves a checksum- and attestation-verified non-snap `gh` v2.102.0 first on `PATH` (`.env`), because the snap build cannot start
under the unit's `NoNewPrivileges=true`. #139 makes that explicit (`ODYSSEUS_GH_BIN`, visible failure, `publish_unavailable`); unmerged.

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

# Unattended operation (3)

Six-hour scheduler: runs at 21:27Z, 03:27Z, 09:27Z on 10-19/20 with no session involved; restart runs after each deploy. Unchanged export:
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

1. Decide criterion 4: approve a stage-7 local-model second-pass pilot, or ratify a revised recall criterion (human decision).
2. Merge #139 (config is already live via `PATH`); record the Codex review of #138 when it completes (queued on the lab).
3. G5: observe a real enrolled-device or new-export event; none is available, so it stays `unverified`.
4. Owners ratify or reject the assessments on #613 and #70; merge or close #72.
5. Remove `/home/agent/projects/odysseus-aoteru-stage` after #139 merges.

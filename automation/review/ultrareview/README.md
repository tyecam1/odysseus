# Ultrareview candidate builder

`build_ultra.sh CLONE DEFAULT_BRANCH OLD_BASE_SHA TAG MERGES_FILE PATHS_FILE [CONTRACT_FILE] [--push]`

Builds three synthetic branches so one Ultrareview (limit 500 files / 8,000 changed lines) covers the
highest-value recent source, merged or not:

- `ultra/TAG-integ`: default branch plus normal merges of the open branches in MERGES_FILE.
- `ultra/TAG-base`: integ with the pathspecs in PATHS_FILE rewound to OLD_BASE_SHA.
- `ultra/TAG-head`: base plus one commit restoring the integ tree, plus the contract as `ULTRAREVIEW_CONTRACT.md`.

Open a draft PR head -> base and run `/code-review ultra <PR>`. Tests and documents stay out of the diff
but remain in the tree as reviewer context. The branches are never merged; delete them after the findings
are recorded. `20261110/` holds the inputs used for the first three candidates
(odysseus#266, misumi#108, obsidian-PhD#671).

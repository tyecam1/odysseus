# Task: CI gate hygiene — make red mean something again

- **Id:** 2026-10-02-ci-gate-hygiene
- **Status:** inbox
- **Origin:** Misumi long-horizon programme, observed while merging PRs #47–#53 (evidence: `automation/review/misumi-long-horizon-programme-evidence.md`)

## Problem
Three checks fail on every recent PR for reasons unrelated to the change, so a failing PR is indistinguishable from a broken one and merges rely on a human reading the logs each time.

1. **`gitleaks`** — 69 findings (`generic-api-key` on the field name `model_key`) in `evals/local_models/results/artifacts/**` from two old commits (`ddb5ec37`, `f88ec808`). They are false positives on a model identifier, not secrets. Add a narrowly scoped allowlist (path + rule + the two commits or fingerprints) in the gitleaks config rather than disabling the rule; confirm each finding is a model key, not a credential, first.
2. **`dependency-review`** — fails with "Dependency review is not supported on this repository" because the dependency graph is disabled. Either enable the dependency graph (operator/repository setting, not an agent action) or make the job conditional so it does not fail where it cannot run.
3. **`Python tests (pytest)`** — setup errors `no such table: source_events` in the source-event import tests (about 19 tests), present on docs-only PRs, so a test-isolation or ordering problem rather than a regression. Find why the table is missing at fixture setup (shared engine or metadata created conditionally, import-order dependence, xdist ordering) and fix the fixture so the tests are order-independent.

## Done when
- A docs-only PR is green on all three; a deliberately broken test still turns pytest red; a planted fake credential still turns gitleaks red.
- The allowlist and any setting change are recorded in the evidence file.

## Boundaries
No weakening of secret scanning beyond the verified false positives; repository settings are the operator's to change.
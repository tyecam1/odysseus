---
exemplar_id: phd-e1a-unmerged-evidence-recovery-2026-11-09
capture_date: 2026-11-09
status: candidate
capture_basis: agent-judged-high-value
source_repository: tyecam1/s2-e1-ros2-measurement-spine
task_context: Recovery of physical E1a experimental evidence present on unmerged remote branches and potentially unpushed local commits, after default-branch-only status incorrectly implied no experiments.
---

# Recover unmerged experimental evidence without redundant trials

## Exact prompt

Work in tyecam1/s2-e1-ros2-measurement-spine from its registered checkout. Reconcile live main, remote experiment branches, PRs, local worktrees, dirty/unpushed commits and Jetson evidence read-only before running or repeating any experiment. Prioritise experiment/s2-e1a-implementation-20261102 (58 commits ahead of main), experiment/s2-e1a-component-metrology-20261028 and any local five-point-validation commit (previously reported as 8500d3b).

Audit the physical 19–21 Oct five-point calibration, 2 Nov E1a can pilot and 4 Nov crossover against source records, checksums and analysis. Separate completed development experiments from unperformed confirmatory validation; document deviations, reference uncertainty, session-calibration policy, actual lighting/LED state and the 0.4.0 candidate’s 1.4–1.6 mm Y bias. Do not repeat existing valid trials or reinterpret tuned data as held-out evidence.

Preserve all raw data and commits. On an isolated branch, reconcile reviewable code/docs into a PR, verify relevant tests, diagnose the bias and define the minimum registered-placement confirmatory study with task-derived tolerance. Implement only authorised software work; no robot actuation, unsafe hardware actions, fabricated thresholds or unapproved research-claim promotion. Report verified completion, unresolved gates, PR links and only the indispensable physical actions.

## Capture rationale

- Treats repository `main`, remote experiment branches, local-only commits, worktrees and physical raw evidence as distinct incomplete sources of state, correcting the demonstrated default-branch-only false negative.
- Explicitly separates experiment execution, development analysis, independent confirmatory validation and scientific acceptance, preventing unnecessary repeat capture or false promotion.
- Combines preservation of immutable raw evidence with a bounded, independently reviewable software/documentation PR and minimal operator-required physical actions.

## Reusable behaviours worth evaluating

1. Search all plausible evidence tiers before classifying a scientific experiment incomplete.
2. Preserve raw experimental provenance and distinguish empirical stages from software completeness.
3. Resolve reproducibility and protocol flaws before collecting new observations.

## Assumptions and limits

- Exact branch names, dates, ahead/behind counts and candidate bias are point-in-time facts for this one repository and must be checked live if reused.
- This is a one-off prompt exemplar, not an active initialising prompt, delegated authority, endorsement of the experimental results or application trace.
- No execution or operator rating is available at capture.

# Branchable optimisation loop

## Objective

Create an isolated, score-driven candidate loop for harness changes using a frozen evaluator, explicit budget, keep/revert decisions and backtracking to prior candidates.

## Design

- one baseline commit and immutable evaluator revision;
- one candidate change per node;
- sandboxed execution and fixed resource budget;
- task-specific score plus blocking safety gates;
- branch from any historical candidate when the current path plateaus;
- preserve candidate tree, diffs, logs, score and rejection reason;
- require human-reviewed PR before any retained candidate reaches `dev`.

## Acceptance criteria

A pilot optimises one low-risk component such as context selection or output trimming, beats the held-out baseline without regressions, and proves that the candidate cannot edit its evaluator, permissions or acceptance criteria.

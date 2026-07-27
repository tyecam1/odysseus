# Run trace, loss and credit assignment

## Objective

Represent each agent run as ordered, sanitized spans and evaluate it against a multi-objective score with blocking safety constraints.

## Required spans

Objective, context assembly, skill activation, tool permission, tool execution, artifact output, validator, human intervention, closeout and rollback.

## Required evaluation

Task success, provenance, permission compliance, retrieval quality, regression, context cost, latency, operator burden and unresolved uncertainty. Hard safety failures cannot be averaged away.

## Acceptance criteria

The schema works for ordinary chat, agent mode, background jobs and scheduled tasks; raw logs remain recoverable; secrets and private document content are redacted; at least five existing runs are representable; score changes can be attributed only after controlled comparison.
